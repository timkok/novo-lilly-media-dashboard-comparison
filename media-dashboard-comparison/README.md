# Novo vs Lilly Media Dashboard Comparison

This folder hosts a combined GitHub Pages comparison surface for independent Novo Nordisk vs Eli Lilly media exposure dashboards.

## Hosted deployment

GitHub Actions deploys the entire `media-dashboard-comparison` folder as one Pages artifact. The expected URLs are:

- Landing page: `https://USERNAME.github.io/REPO_NAME/media-dashboard-comparison/`
- Codex dashboard: `https://USERNAME.github.io/REPO_NAME/media-dashboard-comparison/codex/`
- Antigravity dashboard: `https://USERNAME.github.io/REPO_NAME/media-dashboard-comparison/antigravity/` when that folder exists

## Real data generation

The Codex implementation uses a Python pipeline under `codex/scripts/`. It fetches real media records from GDELT DOC 2.0, normalizes records, deduplicates by URL or title/date/domain, and writes static JSON files to `codex/data/generated/`.

The hosted dashboard has no local data requirement because it reads those generated JSON files from the deployed Pages artifact.

## Comparison workflow

Use the landing page to open each implementation and compare:

- Data coverage and warnings in each metadata file
- Query definitions and false-positive controls
- Share of voice, topic mix, sentiment, alerts, and explorer behavior
- Proxy metric caveats

The Codex dashboard defaults to GDELT as a no-key source. Optional CSV imports can be added under `codex/data/imports/` before running the pipeline.
