"""Small in-memory adapter, with independent feature/output/label collections.

The HTTP layer never reads a fixture. Replace this class with a PostgreSQL
implementation of Repository when persisted worker output becomes available.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from app.repositories.loader import file_fingerprint, normalize_row
from app.schemas.transaction import ExplanationFixture, Prediction, Transaction, TypologyRecord

if TYPE_CHECKING:
    from app.schemas.explanation import ExplanationJob

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class MockRepository:
    def __init__(self, data_dir: Path | None = None, source_timezone: str = "UTC"):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        source = self.data_dir / "mock_transactions.json"
        data = self._read(source.name)
        if data.get("is_synthetic") is not True:
            raise ValueError("Mock fixture must explicitly declare is_synthetic=true")
        fingerprint = file_fingerprint(source)
        rows, labels = [], []
        for number, row in enumerate(data["rows"], start=1):
            transaction, label = normalize_row(
                row, row_number=number, source_file_id=fingerprint, source_filename=source.name,
                source_timezone=source_timezone, transaction_id=f"TX{number:06d}",
            )
            rows.append(transaction)
            labels.append(label)
        self._transactions = {row.transaction_id: row for row in rows}
        if len(rows) != len(self._transactions) or not rows:
            raise ValueError("Fixture must contain nonempty, unique transaction IDs")
        # These training labels are intentionally unreachable through Repository.
        self._ground_truth = {row.transaction_id: row for row in labels}
        self.account_to_node_index = {
            account: index for index, account in enumerate(sorted(
                {row.sender_account for row in rows} | {row.receiver_account for row in rows}
            ))
        }
        predictions = TypeAdapter(list[Prediction]).validate_python(self._read("mock_predictions.json"))
        typologies = TypeAdapter(list[TypologyRecord]).validate_python(self._read("mock_typologies.json"))
        explanations = TypeAdapter(list[ExplanationFixture]).validate_python(self._read("mock_explanations.json"))
        self._predictions = {(row.transaction_id, row.model_version): row for row in predictions}
        self._typologies = {row.transaction_id: row for row in typologies}
        self._explanations = {(row.transaction_id, row.model_version): row for row in explanations}
        if len(self._predictions) != len(predictions):
            raise ValueError("Duplicate transaction/model prediction")
        if len(self._typologies) != len(typologies):
            raise ValueError("Duplicate transaction typology")
        if len(self._explanations) != len(explanations):
            raise ValueError("Duplicate transaction/model explanation fixture")
        self._validate_references()
        self._jobs: dict[tuple[str, str], ExplanationJob] = {}
        self._lock = RLock()

    def _read(self, name: str):
        return json.loads((self.data_dir / name).read_text(encoding="utf-8"))

    def _validate_references(self) -> None:
        known = set(self._transactions)
        if {row.transaction_id for row in self._predictions.values()} != known:
            raise ValueError("Predictions must reference and cover the transaction fixture")
        for typology in self._typologies.values():
            if typology.transaction_id not in known or not set(typology.related_transaction_ids) <= known:
                raise ValueError("Typology references an unknown transaction")
            if typology.transaction_id not in typology.related_transaction_ids:
                raise ValueError("Typology evidence must include its target transaction")
            target = self._transactions[typology.transaction_id]
            related = [self._transactions[tx_id] for tx_id in typology.related_transaction_ids]
            if any(row.timestamp > target.timestamp for row in related):
                raise ValueError("Typology evidence cannot use future transactions")
            links = {(row.sender_account, row.receiver_account) for row in related}
            if any(pair not in links for pair in zip(typology.account_path, typology.account_path[1:])):
                raise ValueError("Typology account path must exist in its directed evidence")
        graph_ids = set()
        for explanation in self._explanations.values():
            snapshot = explanation.snapshot
            if (explanation.transaction_id, explanation.model_version) not in self._predictions:
                raise ValueError("Explanation must reference an existing model prediction")
            if snapshot.transaction_id != explanation.transaction_id or snapshot.model_version != explanation.model_version:
                raise ValueError("Explanation snapshot target/model mismatch")
            if snapshot.graph_id in graph_ids:
                raise ValueError("Graph snapshot IDs must be unique")
            graph_ids.add(snapshot.graph_id)
            edge_ids = snapshot.edge_transaction_ids
            if len(edge_ids) != len(set(edge_ids)) or not set(edge_ids) <= known:
                raise ValueError("Snapshot edges must be unique known transactions")
            if explanation.transaction_id not in edge_ids:
                raise ValueError("Snapshot must contain the target edge")
            target = self._transactions[explanation.transaction_id]
            start = target.timestamp - timedelta(days=snapshot.lookback_days)
            edges = [self._transactions[tx_id] for tx_id in edge_ids]
            if any(not start <= row.timestamp <= target.timestamp for row in edges):
                raise ValueError("Snapshot cannot contain edges outside its prediction-time window")
            nodes = {row.sender_account for row in edges} | {row.receiver_account for row in edges}
            if nodes != set(snapshot.node_account_ids) or len(snapshot.node_account_ids) != len(nodes):
                raise ValueError("Snapshot nodes must match the edge endpoints")
            important = [edge.transaction_id for edge in explanation.edge_importance]
            if len(important) != len(set(important)) or not set(important) <= set(edge_ids):
                raise ValueError("Importance must reference unique edges in its snapshot")
            if explanation.status == "failed" and not explanation.error_code:
                raise ValueError("Failed explanation fixture must contain an error code")

    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions.values())

    def get_transaction(self, transaction_id: str) -> Transaction | None:
        return self._transactions.get(transaction_id)

    def get_prediction(self, transaction_id: str, model_version: str) -> Prediction | None:
        return self._predictions.get((transaction_id, model_version))

    def get_typology(self, transaction_id: str) -> TypologyRecord | None:
        row = self._typologies.get(transaction_id)
        return row.model_copy(deep=True) if row else None

    def get_explanation_fixture(self, transaction_id: str, model_version: str) -> ExplanationFixture | None:
        row = self._explanations.get((transaction_id, model_version))
        return row.model_copy(deep=True) if row else None

    def get_job(self, transaction_id: str, model_version: str) -> ExplanationJob | None:
        with self._lock:
            job = self._jobs.get((transaction_id, model_version))
            return job.model_copy(deep=True) if job else None

    def create_job(self, job: ExplanationJob) -> ExplanationJob:
        """Atomic insert-if-absent gives transaction/model idempotency."""
        with self._lock:
            key = (job.transaction_id, job.model_version)
            stored = self._jobs.setdefault(key, job.model_copy(deep=True))
            return stored.model_copy(deep=True)

    def save_job(self, job: ExplanationJob) -> None:
        with self._lock:
            self._jobs[(job.transaction_id, job.model_version)] = job.model_copy(deep=True)
