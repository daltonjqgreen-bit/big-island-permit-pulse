# Big Island Permit Pulse

Every new Big Island job, every week, from the County record: a free weekly leads feed of Hawaiʻi County building permits (new builds, additions, alterations, pools, solar) with contractor, valuation and district, plus an estimated real permit wait. All numbers come from County of Hawaiʻi DPW Building Division public records (records.hawaiicounty.gov): weekly and monthly "Building Permits Extract" XLSX files (deduped on permit number) and monthly "Building Metrics" PDFs.

- `fetch.py` downloads and parses the County files into `data/` (permits.csv/json, metrics.csv/json, summary.json)
- `build_site.py` builds `site/index.html` (from `templates/index.html`) and the weekly newsletter draft in `newsletter/` (`latest.html` / `latest.md`, Beehiiv-ready)
- `.github/workflows/monthly-update.yml` refreshes every Monday 8:00 AM HST (plus manual trigger) and deploys to GitHub Pages

Local run: `pip install -r requirements.txt && python fetch.py 2025 2026 && python build_site.py` (needs `pdftotext` from poppler-utils).

Not affiliated with the County of Hawaiʻi.

Owner names are not stored or published.
