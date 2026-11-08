import csv
import json
import shutil
from pathlib import Path

import pytest

from app.repositories.loader import SAML_COLUMNS, iter_csv
from app.repositories.mock_repository import DEFAULT_DATA_DIR, MockRepository
from scripts.import_csv import import_csv


def source_row(**changes):
    row = dict(Date="2022-11-01", Time="10:00:00", Sender_account="000123",
               Receiver_account="000456", Amount="123.45", Payment_currency="UK pounds",
               Received_currency="Dirham", Sender_bank_location="UK", Receiver_bank_location="UAE",
               Payment_type="Cross-border", Is_laundering="1", Laundering_type="Fan_In")
    row.update(changes)
    return row


def write_csv(path: Path, rows: list[dict], columns=SAML_COLUMNS):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_same_bytes_duplicate_rows_have_stable_unique_ids_and_preserved_accounts(tmp_path):
    path = write_csv(tmp_path / "source.csv", [source_row(), source_row()])
    first = list(iter_csv(path))
    second = list(iter_csv(path))
    renamed = tmp_path / "renamed.csv"
    renamed.write_bytes(path.read_bytes())
    third = list(iter_csv(renamed))
    assert first == second
    assert first[0][0].transaction_id != first[1][0].transaction_id
    assert [tx.transaction_id for tx, _ in first] == [tx.transaction_id for tx, _ in third]
    assert first[0][0].sender_account == "000123"
    assert first[0][0].payment_currency == "UK pounds"
    assert first[0][0].received_currency == "Dirham"
    assert [tx.provenance.source_row_number for tx, _ in first] == [1, 2]
    assert first[0][0].provenance.source_file_id.startswith("sha256:")
    assert len(first[0][0].provenance.source_file_id) == 71


def test_csv_changed_content_creates_new_source_namespace(tmp_path):
    path = write_csv(tmp_path / "source.csv", [source_row()])
    first = list(iter_csv(path))[0][0]
    write_csv(path, [source_row(Amount="999")])
    second = list(iter_csv(path))[0][0]
    assert first.transaction_id != second.transaction_id
    assert first.provenance.source_file_id != second.provenance.source_file_id


def test_source_timezone_is_configurable_and_comparison_uses_utc(tmp_path):
    path = write_csv(tmp_path / "source.csv", [source_row()])
    utc = list(iter_csv(path, "UTC"))[0][0]
    seoul = list(iter_csv(path, "Asia/Seoul"))[0][0]
    assert utc.timestamp.isoformat() == "2022-11-01T10:00:00+00:00"
    assert seoul.timestamp.isoformat() == "2022-11-01T01:00:00+00:00"
    assert utc.transaction_id == seoul.transaction_id


@pytest.mark.parametrize("changes", [
    {"Amount": "nan"}, {"Amount": "inf"}, {"Amount": "-1"},
    {"Date": "2022-02-30"}, {"Time": "25:00:00"},
    {"Is_laundering": "2"}, {"Sender_account": ""},
    {"Time": "10:00:00+09:00"},
])
def test_invalid_source_values_are_rejected(tmp_path, changes):
    path = write_csv(tmp_path / "source.csv", [source_row(**changes)])
    with pytest.raises(ValueError):
        list(iter_csv(path))


@pytest.mark.parametrize("when", [("2022-03-13", "02:30:00"), ("2022-11-06", "01:30:00")])
def test_ambiguous_or_nonexistent_dst_wall_times_are_rejected(tmp_path, when):
    path = write_csv(tmp_path / "source.csv", [source_row(Date=when[0], Time=when[1])])
    with pytest.raises(ValueError, match="wall time"):
        list(iter_csv(path, "America/New_York"))


def test_missing_or_duplicate_csv_columns_are_rejected(tmp_path):
    missing = tmp_path / "missing.csv"
    missing.write_text("Date,Time\n2022-11-01,10:00:00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        list(iter_csv(missing))
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("Date,Date\n2022-11-01,2022-11-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate column"):
        list(iter_csv(duplicate))


def test_import_artifacts_separate_labels_and_node_indices_from_features(tmp_path):
    path = write_csv(tmp_path / "source.csv", [source_row(), source_row()])
    target = tmp_path / "imported"
    metadata = import_csv(path, target)
    transactions = [json.loads(line) for line in (target / "transactions.jsonl").read_text(encoding="utf-8").splitlines()]
    labels = [json.loads(line) for line in (target / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    nodes = [json.loads(line) for line in (target / "node_map.jsonl").read_text(encoding="utf-8").splitlines()]
    assert metadata["row_count"] == 2
    assert metadata["predictions_included"] is False
    assert metadata["source_laundering_type_counts"] == {"Fan_In": 2}
    assert metadata["source_is_laundering_counts"] == {"1": 2}
    assert [tx["transaction_id"] for tx in transactions] == [label["transaction_id"] for label in labels]
    assert all(not {"is_laundering", "laundering_type", "Is_laundering", "Laundering_type", "node_index"} & tx.keys() for tx in transactions)
    assert nodes == [{"account_id": "000123", "node_index": 0}, {"account_id": "000456", "node_index": 1}]
    with pytest.raises(ValueError, match="never overwritten"):
        import_csv(path, target)


def test_failed_import_removes_partial_files(tmp_path):
    path = write_csv(tmp_path / "source.csv", [source_row(), source_row(Amount="bad")])
    target = tmp_path / "imported"
    with pytest.raises(ValueError):
        import_csv(path, target)
    assert list(target.iterdir()) == []


def test_fixture_keeps_duplicate_transactions_and_labels_separate():
    repository = MockRepository()
    assert len(repository.transactions()) == 31
    first, duplicate = repository.get_transaction("TX000001"), repository.get_transaction("TX000029")
    assert first.sender_account == duplicate.sender_account
    assert first.receiver_account == duplicate.receiver_account
    assert first.amount == duplicate.amount
    assert first.timestamp == duplicate.timestamp
    assert first.transaction_id != duplicate.transaction_id
    assert first.provenance.source_row_number == 1
    assert duplicate.provenance.source_row_number == 29
    assert "is_laundering" not in first.model_dump()
    assert "laundering_type" not in first.model_dump()
    assert repository.account_to_node_index["A"] != "A"


def test_repository_rejects_invalid_snapshot_references_at_startup(tmp_path):
    for source in DEFAULT_DATA_DIR.glob("*.json"):
        shutil.copyfile(source, tmp_path / source.name)
    path = tmp_path / "mock_explanations.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    records[0]["snapshot"]["edge_transaction_ids"].append("TX_DOES_NOT_EXIST")
    path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="unique known transactions"):
        MockRepository(tmp_path)
