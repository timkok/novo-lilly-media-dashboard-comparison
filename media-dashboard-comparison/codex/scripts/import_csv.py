from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_optional_csv_imports(import_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load optional analyst-provided CSV rows without making them required."""
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    for csv_path in sorted(import_dir.glob("*.csv")):
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    row["rawSource"] = row.get("rawSource") or "CSV"
                    row["channel"] = row.get("channel") or "CSV Import"
                    row["isProxyMetrics"] = row.get("isProxyMetrics", "false").lower() == "true"
                    records.append(row)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"CSV import skipped for {csv_path.name}: {exc}")
    return records, warnings
