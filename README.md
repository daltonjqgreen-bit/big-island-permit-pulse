# Big Island Permit Pulse

Free tracker of Hawaiʻi County building permit wait times, permit volume by type and district, and newly issued permits. All numbers come from County of Hawaiʻi DPW Building Division public records (records.hawaiicounty.gov): monthly "Building Permits Extract" XLSX files and monthly "Building Metrics" PDFs.

- `fetch.py` downloads and parses the County files into `data/` (permits.csv/json, metrics.csv/json, summary.json)
- `build_site.py` builds `site/index.html`
- `.github/workflows/monthly-update.yml` refreshes on the 3rd (and 6th) of each month and deploys to GitHub Pages

Local run: `pip install -r requirements.txt && python fetch.py 2025 2026 && python build_site.py` (needs `pdftotext` from poppler-utils).

Not affiliated with the County of Hawaiʻi.
