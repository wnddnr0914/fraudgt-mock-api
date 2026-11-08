"""Stored transaction features and independent model-output records.

Ground-truth labels deliberately live in a separate collection and never enter
Transaction, the feature-bearing object consumed by graph/model adapters.
"""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(Record):
    source_file_id: str = Field(description="sha256:<full source-file digest>")
    source_filename: str
    source_row_number: int = Field(ge=1, description="1-based data record, excluding CSV header")


class Transaction(Record):
    transaction_id: str
    timestamp: AwareDatetime
    sender_account: str
    receiver_account: str
    amount: float = Field(ge=0, allow_inf_nan=False)
    payment_currency: str
    received_currency: str
    sender_bank_location: str
    receiver_bank_location: str
    payment_type: str
    provenance: Provenance


class GroundTruth(Record):
    transaction_id: str
    is_laundering: Literal[0, 1]
    laundering_type: str


class Prediction(Record):
    transaction_id: str
    fraud_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    model_version: str


class TypologyRecord(Record):
    transaction_id: str
    predicted_type: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    verification_status: Literal["unverified", "verified", "rejected"] = "unverified"
    model_version: str
    related_transaction_ids: list[str]
    account_path: list[str]
    description: str


class GraphSnapshot(Record):
    graph_id: str
    transaction_id: str
    model_version: str
    preprocessing_version: str
    sampler: str
    seed: int
    hops: int = Field(ge=1, le=3)
    lookback_days: int = Field(ge=1, le=30)
    edge_transaction_ids: list[str]
    node_account_ids: list[str]


class EdgeImportance(Record):
    transaction_id: str
    importance: float = Field(ge=0, le=1, allow_inf_nan=False)


class ExplanationFixture(Record):
    transaction_id: str
    model_version: str
    status: Literal["completed", "failed"]
    snapshot: GraphSnapshot
    edge_importance: list[EdgeImportance]
    error_code: str | None = None
