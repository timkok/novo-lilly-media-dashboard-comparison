from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARISON_ROOT = ROOT.parent
CODEX_GENERATED = COMPARISON_ROOT / "codex" / "data" / "generated"
GENERATED = ROOT / "data" / "generated"
FILES = [
    "mentions.json",
    "daily_counts.json",
    "source_summary.json",
    "topic_summary.json",
    "alerts.json",
    "metadata.json",
]


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload) -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    for name in FILES:
        if name == "metadata.json":
            continue
        default = [] if name != "daily_counts.json" else []
        write_json(name, read_json(CODEX_GENERATED / name, default))

    codex_metadata = read_json(CODEX_GENERATED / "metadata.json", {})
    warnings = list(codex_metadata.get("warnings") or [])
    warnings.append("Antigravity comparison dataset generated from the same GitHub Actions real-data pipeline outputs for deployment validation; no fake records were added.")
    metadata = {
        **codex_metadata,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "recordCount": codex_metadata.get("recordCount", 0),
        "sourcesUsed": codex_metadata.get("sourcesUsed", ["GDELT"]),
        "warnings": warnings,
        "version": "antigravity",
    }
    write_json("metadata.json", metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
