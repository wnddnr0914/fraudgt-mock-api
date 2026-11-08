"""SAML-D conversion: preserve strings and duplicates; separate training labels."""
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from app.schemas.transaction import GroundTruth, Provenance, Transaction

SAML_COLUMNS = (
    "Date", "Time", "Sender_account", "Receiver_account", "Amount",
    "Payment_currency", "Received_currency", "Sender_bank_location",
    "Receiver_bank_location", "Payment_type", "Is_laundering", "Laundering_type",
)


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def normalize_row(row: dict, *, row_number: int, source_file_id: str,
                  source_filename: str, source_timezone: str = "UTC",
                  transaction_id: str | None = None) -> tuple[Transaction, GroundTruth]:
    missing = set(SAML_COLUMNS) - row.keys()
    if missing:
        raise ValueError(f"Row {row_number}: missing columns {sorted(missing)}")
    empty = [key for key in SAML_COLUMNS if row[key] is None or str(row[key]).strip() == ""]
    if empty:
        raise ValueError(f"Row {row_number}: empty required values {empty}")
    if str(row["Is_laundering"]) not in {"0", "1"}:
        raise ValueError(f"Row {row_number}: Is_laundering must be 0 or 1")
    naive = datetime.fromisoformat(f"{row['Date']}T{row['Time']}")
    if naive.tzinfo is not None:
        raise ValueError(f"Row {row_number}: source Date/Time must be naive; use source_timezone")
    zone = ZoneInfo(source_timezone)
    # Ambiguous/nonexistent wall times cannot be silently assigned an instant.
    aware = naive.replace(tzinfo=zone, fold=0)
    if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError(f"Row {row_number}: nonexistent wall time in {source_timezone}")
    if naive.replace(tzinfo=zone, fold=1).utcoffset() != aware.utcoffset():
        raise ValueError(f"Row {row_number}: ambiguous wall time in {source_timezone}")
    digest = source_file_id.removeprefix("sha256:")
    tx_id = transaction_id or f"TX_{digest}_{row_number:09d}"
    transaction = Transaction(
        transaction_id=tx_id, timestamp=aware.astimezone(timezone.utc),
        sender_account=str(row["Sender_account"]), receiver_account=str(row["Receiver_account"]),
        amount=row["Amount"], payment_currency=row["Payment_currency"],
        received_currency=row["Received_currency"], sender_bank_location=row["Sender_bank_location"],
        receiver_bank_location=row["Receiver_bank_location"], payment_type=row["Payment_type"],
        provenance=Provenance(source_file_id=source_file_id, source_filename=source_filename,
                              source_row_number=row_number),
    )
    label = GroundTruth(transaction_id=tx_id, is_laundering=int(row["Is_laundering"]),
                        laundering_type=row["Laundering_type"])
    return transaction, label


def iter_csv(path: Path, source_timezone: str = "UTC") -> Iterator[tuple[Transaction, GroundTruth]]:
    """Two file passes: content hash first, streaming row validation second.

    IDs are stable for identical bytes independent of path; changing any bytes
    intentionally creates a new source namespace. A row is a logical CSV record,
    not a physical line, allowing quoted newlines without losing provenance.
    """
    path = Path(path)
    fingerprint = file_fingerprint(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise ValueError("CSV has duplicate column names")
        missing = set(SAML_COLUMNS) - set(columns)
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=1):
            if None in row:
                raise ValueError(f"Row {row_number}: more fields than header")
            yield normalize_row(row, row_number=row_number, source_file_id=fingerprint,
                                source_filename=path.name, source_timezone=source_timezone)
