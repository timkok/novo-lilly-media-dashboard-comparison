from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fetch_gdelt import fetch_gdelt_window
from import_csv import load_optional_csv_imports
from normalize import QUERY_DEFINITIONS, dedupe_mentions, normalize_gdelt_article


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "data" / "generated"
IMPORT_DIR = ROOT / "data" / "imports"


def date_windows(days: int = 90, window_days: int = 7) -> list[tuple[datetime, datetime]]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    windows = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=window_days), end)
        windows.append((cursor, window_end))
        cursor = window_end
    return windows


def write_json(name: str, payload: Any) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    target = GENERATED_DIR / name
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_daily_counts(mentions: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in mentions:
        counts[item["date"]][item["company"]] += 1
    rows = []
    day = datetime.fromisoformat(start).date()
    last = datetime.fromisoformat(end).date()
    while day <= last:
        key = day.isoformat()
        novo = counts[key]["Novo Nordisk"]
        lilly = counts[key]["Eli Lilly"]
        total = novo + lilly
        rows.append({
            "date": key,
            "Novo Nordisk": novo,
            "Eli Lilly": lilly,
            "total": total,
            "novoShare": round(novo / total, 4) if total else 0,
            "lillyShare": round(lilly / total, 4) if total else 0,
        })
        day += timedelta(days=1)
    return rows


def grouped_summary(mentions: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for item in mentions:
        groups[item.get(field) or "Unknown"][item["company"]] += 1
    rows = []
    for name, counter in sorted(groups.items(), key=lambda pair: sum(pair[1].values()), reverse=True):
        total = counter["Novo Nordisk"] + counter["Eli Lilly"]
        rows.append({
            field: name,
            "Novo Nordisk": counter["Novo Nordisk"],
            "Eli Lilly": counter["Eli Lilly"],
            "total": total,
            "novoShare": round(counter["Novo Nordisk"] / total, 4) if total else 0,
            "lillyShare": round(counter["Eli Lilly"] / total, 4) if total else 0,
        })
    return rows


def generate_alerts(mentions: list[dict[str, Any]], daily_counts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts = []
    recent_cutoff = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    recent = [m for m in mentions if m["date"] >= recent_cutoff]
    older = [m for m in mentions if m["date"] < recent_cutoff]

    def add(kind: str, severity: str, title: str, detail: str, company: str = "Both") -> None:
        alerts.append({
            "id": f"{kind}-{len(alerts) + 1}",
            "type": kind,
            "severity": severity,
            "company": company,
            "title": title,
            "detail": detail,
            "date": datetime.now(timezone.utc).date().isoformat(),
        })

    recent_negative = sum(1 for m in recent if m["sentiment"] == "Negative")
    older_negative_rate = (sum(1 for m in older if m["sentiment"] == "Negative") / len(older)) if older else 0
    recent_negative_rate = recent_negative / len(recent) if recent else 0
    if recent and recent_negative_rate >= max(0.25, older_negative_rate * 1.5):
        add("Negative sentiment spike", "High", "Negative sentiment is elevated", f"{recent_negative_rate:.0%} of recent mentions are negative versus {older_negative_rate:.0%} earlier.")

    for topic, kind in [
        ("Side effects / safety", "Safety topic spike"),
        ("Drug pricing / insurance / access", "Pricing/access topic spike"),
        ("Legal / regulatory", "Legal/regulatory topic spike"),
        ("Supply shortage", "Supply shortage spike"),
    ]:
        count = sum(1 for m in recent if m["topic"] == topic)
        if count >= 3:
            add(kind, "High" if topic in {"Side effects / safety", "Legal / regulatory"} else "Medium", f"{topic} coverage is active", f"{count} recent mentions are classified as {topic}.")

    for item in recent:
        if item["sourceTier"] == "Tier 1":
            add("Tier 1 article published", "Medium", "Tier 1 article published", f"{item['source']} covered {item['company']}: {item['title']}", item["company"])
            break

    total_recent = len(recent)
    if total_recent:
        novo = sum(1 for m in recent if m["company"] == "Novo Nordisk")
        lilly = sum(1 for m in recent if m["company"] == "Eli Lilly")
        diff = (lilly - novo) / total_recent
        if diff > 0.10:
            add("Lilly SOV exceeds Novo by more than 10 percentage points", "Medium", "Lilly leads recent share of voice", f"Lilly leads Novo by {diff:.0%} in the last seven days.", "Eli Lilly")
        elif diff < -0.10:
            add("Novo SOV exceeds Lilly by more than 10 percentage points", "Medium", "Novo leads recent share of voice", f"Novo leads Lilly by {abs(diff):.0%} in the last seven days.", "Novo Nordisk")

    pipeline_count = sum(1 for m in recent if {"orforglipron", "retatrutide"} & set(m.get("matchedKeywords", [])))
    if pipeline_count >= 2:
        add("Pipeline term spike: orforglipron or retatrutide", "Medium", "Lilly pipeline terms are spiking", f"{pipeline_count} recent mentions reference orforglipron or retatrutide.", "Eli Lilly")

    return alerts


def main() -> int:
    warnings: list[str] = []
    gdelt_mentions: list[dict[str, Any]] = []
    coverage_end = datetime.now(timezone.utc).date()
    coverage_start = coverage_end - timedelta(days=90)

    for company, definition in QUERY_DEFINITIONS.items():
        consecutive_failures = 0
        max_consecutive_failures = int(os.getenv("GDELT_MAX_CONSECUTIVE_FAILURES", "6"))
        for start, end in date_windows():
            articles, window_warnings = fetch_gdelt_window(definition["query"], start, end)
            warnings.extend(window_warnings)
            if window_warnings and not articles:
                consecutive_failures += 1
            else:
                consecutive_failures = 0
            if consecutive_failures >= max_consecutive_failures:
                warnings.append(f"Stopped additional GDELT windows for {company} after {consecutive_failures} consecutive fetch failures.")
                break
            for article in articles:
                normalized = normalize_gdelt_article(article, company)
                if normalized:
                    gdelt_mentions.append(normalized)

    csv_records, csv_warnings = load_optional_csv_imports(IMPORT_DIR)
    warnings.extend(csv_warnings)
    mentions = dedupe_mentions(gdelt_mentions + csv_records)

    if not mentions:
        warnings.append("GDELT returned zero records for the configured queries.")

    daily_counts = build_daily_counts(mentions, coverage_start.isoformat(), coverage_end.isoformat())
    source_summary = grouped_summary(mentions, "sourceDomain")
    topic_summary = grouped_summary(mentions, "topic")
    alerts = generate_alerts(mentions, daily_counts)

    metadata = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "coverageStart": coverage_start.isoformat(),
        "coverageEnd": coverage_end.isoformat(),
        "recordCount": len(mentions),
        "sourcesUsed": ["GDELT"] + (["CSV"] if csv_records else []),
        "sourcesUnavailable": ["Mediastack", "NewsAPI", "Brandwatch", "Meltwater", "Talkwalker"],
        "proxyMetricFields": ["reach", "sourceAuthority", "engagement"],
        "warnings": warnings,
        "queryDefinitions": QUERY_DEFINITIONS,
        "version": "codex",
    }

    write_json("mentions.json", mentions)
    write_json("daily_counts.json", daily_counts)
    write_json("source_summary.json", source_summary)
    write_json("topic_summary.json", topic_summary)
    write_json("alerts.json", alerts)
    write_json("metadata.json", metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
