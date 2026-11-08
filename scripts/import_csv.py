"""Validate/import actual CSV without inventing predictions or using labels as features."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories.loader import SAML_COLUMNS, file_fingerprint, iter_csv


def import_csv(source: Path, output: Path, source_timezone: str = "UTC") -> dict:
    source, output = Path(source), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be absent or empty; existing artifacts are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    names = ("transactions.jsonl", "labels.jsonl", "node_map.jsonl")
    partial = [output / (name + ".part") for name in names]
    accounts: dict[str, int] = {}
    rows = 0
    samples = []
    source_types = Counter()
    source_flags = Counter()
    try:
        with partial[0].open("w", encoding="utf-8") as features, partial[1].open("w", encoding="utf-8") as labels, partial[2].open("w", encoding="utf-8") as nodes:
            for transaction, label in iter_csv(source, source_timezone):
                rows += 1
                source_types[label.laundering_type] += 1
                source_flags[str(label.is_laundering)] += 1
                features.write(transaction.model_dump_json() + "\n")
                labels.write(label.model_dump_json() + "\n")
                for account in (transaction.sender_account, transaction.receiver_account):
                    if account not in accounts:
                        index = len(accounts)
                        accounts[account] = index
                        nodes.write(json.dumps({"account_id": account, "node_index": index}) + "\n")
                if len(samples) < 3:
                    samples.append(transaction.model_dump(mode="json"))
        if rows == 0:
            raise ValueError("CSV must contain at least one transaction")
        metadata = {
            "source_file_id": file_fingerprint(source), "source_filename": source.name,
            "source_timezone_assumption": source_timezone, "timestamp_output_timezone": "UTC",
            "row_count": rows, "account_count": len(accounts), "required_columns": list(SAML_COLUMNS),
            "source_laundering_type_counts": dict(sorted(source_types.items())),
            "source_is_laundering_counts": dict(sorted(source_flags.items())),
            "id_policy": "TX_<full source-file SHA256>_<1-based logical data record, width >= 9>",
            "features_file": names[0], "ground_truth_file": names[1], "node_index_file": names[2],
            "predictions_included": False,
            "next_step": "A model worker must produce versioned predictions; adapt Repository to this storage before serving real CSV rows.",
            "samples": samples,
        }
        for staged, name in zip(partial, names):
            staged.rename(output / name)
        (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return metadata
    except Exception:
        for staged in partial:
            staged.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-timezone", default="UTC", help="Explicit assumption for naive CSV Date+Time")
    args = parser.parse_args()
    try:
        metadata = import_csv(args.csv, args.output, args.source_timezone)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(json.dumps({key: metadata[key] for key in ("source_file_id", "row_count", "account_count", "predictions_included")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
