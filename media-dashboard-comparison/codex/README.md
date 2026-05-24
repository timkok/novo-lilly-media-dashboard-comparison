# Codex Novo Nordisk vs Eli Lilly Media Dashboard

This is a pure static HTML/CSS/vanilla JavaScript dashboard. It is designed for GitHub Pages and does not require React, Next.js, Vite, a Node build step, browser-side API keys, or browser-side data API calls.

## Data pipeline

GitHub Actions runs:

```bash
python media-dashboard-comparison/codex/scripts/build_dataset.py
```

The pipeline fetches real GDELT DOC 2.0 records for the last 90 days, in manageable windows with retry/backoff behavior. It writes:

- `data/generated/mentions.json`
- `data/generated/daily_counts.json`
- `data/generated/source_summary.json`
- `data/generated/topic_summary.json`
- `data/generated/alerts.json`
- `data/generated/metadata.json`

If GDELT returns zero records, the pipeline writes valid empty files and records the warning in `metadata.json`. It never creates fake media records.

## Proxy metric caveat

GDELT does not provide true impressions or true social engagement. For GDELT records:

- `isProxyMetrics` is `true`
- `reach` is a source-tier proxy
- `sourceAuthority` is rule-based
- `engagement` is `0` unless an imported dataset supplies actual engagement

The Data Quality tab labels this explicitly.

## Manual run

From the repository root:

```bash
python -m pip install -r media-dashboard-comparison/codex/scripts/requirements.txt
python media-dashboard-comparison/codex/scripts/build_dataset.py
```

Then open `media-dashboard-comparison/codex/index.html` or serve the repository with any static server. Hosted use does not depend on local files.

## Optional CSV imports

Place CSV files in `media-dashboard-comparison/codex/data/imports/`. The importer is intentionally optional and does not replace GDELT as the default no-key source.
