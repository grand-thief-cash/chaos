#!/usr/bin/env python3
"""
将所有字段的 contract_version 统一更新为 2026-06-27
"""
import json
from pathlib import Path


def update_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                row["contract_version"] = "2026-06-27"
                rows.append(row)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    print(f"Updated {len(rows)} rows in {path.name}")


def update_datasets(path: Path):
    datasets = json.loads(path.read_text(encoding="utf-8"))
    for ds in datasets:
        ds["contract_version"] = "2026-06-27"

    path.write_text(json.dumps(datasets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated datasets.json")


def main():
    out_dir = Path(__file__).parent

    update_jsonl(out_dir / "financial_statement.fields.jsonl")
    update_jsonl(out_dir / "corporate_action.fields.jsonl")
    update_jsonl(out_dir / "equity_structure.fields.jsonl")
    update_jsonl(out_dir / "enums.jsonl")
    update_datasets(out_dir / "datasets.json")

    print("\nAll done! Now re-run regenerate_seed_sql.py")


if __name__ == "__main__":
    main()
