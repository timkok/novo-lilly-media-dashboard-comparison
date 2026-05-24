# Comparison Notes

The Codex version is built as a static dashboard backed by generated JSON files. It prioritizes:

- GDELT DOC 2.0 as the default no-key media source
- Transparent keyword rules for company matching, false-positive control, topic buckets, source tiering, and fallback sentiment
- Hosted GitHub Pages compatibility from the `/media-dashboard-comparison/codex/` subpath
- No mock or fake media records
- Clear proxy metric labeling for reach, engagement, and source authority

When comparing with an Antigravity implementation, check the landing page links, metadata warnings, generated record counts, topic classification rules, alert thresholds, and whether both dashboards make the same distinction between real media records and proxy exposure metrics.
