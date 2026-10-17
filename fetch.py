#!/usr/bin/env python3
"""Big Island Permit Pulse - fetch & parse REAL Hawaii County building permit data.

Sources (County of Hawaii Laserfiche WebLink, public, no login):
  * Permits Issued  -> monthly "Building Permits Extract" XLSX (one row per issued permit)
    PublicDocuments > Public Works > Building Division > Permits Issued > <year>
  * Permit Issuance Metrics -> monthly "Building Metrics" PDF (avg days to process + counts,
    rolling 3/6/12-month windows, by permit type)
Outputs in data/: permits.csv, permits.json, metrics.csv, metrics.json, summary.json
Nothing is estimated or invented; unparseable values are left blank.
"""
import csv, json, re, subprocess, sys, time, urllib.request, datetime, os
from collections import Counter, defaultdict
import openpyxl

BASE = "https://records.hawaiicounty.gov/WebLink"
PERMITS_ISSUED_FOLDER = 24977
METRICS_FOLDER = 143133
YEARS = sys.argv[1:] or ["2025", "2026"]
HERE = os.path.dirname(os.path.abspath(__file__))
RAW, DATA = os.path.join(HERE, "raw"), os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0 (PermitPulse research script)"}
# Hawaii County TMK first digit = tax-map zone (district)
ZONES = {"1": "Puna", "2": "South Hilo", "3": "North Hilo", "4": "Hamakua", "5": "North Kohala",
         "6": "South Kohala", "7": "North Kona", "8": "South Kona", "9": "Kau"}

def ls(folder):
    body = json.dumps({"repoName": "PublicDocuments", "folderId": folder, "getNewListing": True,
                       "start": 0, "end": 1000, "sortColumn": "", "sortAscending": True}).encode()
    req = urllib.request.Request(BASE + "/FolderListingService.aspx/GetFolderListing2", data=body,
                                 headers={**UA, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))["data"]["results"]

def download(docid, ext):
    path = os.path.join(RAW, f"{docid}.{ext}")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        url = f"{BASE}/ElectronicFile.aspx?docid={docid}&dbid=1&repo=PublicDocuments"
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        if len(data) < 100: raise RuntimeError(f"empty download {docid}")
        open(path, "wb").write(data); time.sleep(0.5)
    return path

def s(v): return "" if v is None else re.sub(r"\s+", " ", str(v)).strip()
def num(v):
    try: return float(str(v).replace(",", "").replace("$", ""))
    except Exception: return None

def parse_extract(path, label, src_url):
    ws = openpyxl.load_workbook(path, read_only=True).active
    it = ws.iter_rows(values_only=True)
    for hr in it:  # header row position varies between files
        if hr and "PERMITNUMBER" in [s(h) for h in hr]: break
    else:
        return []
    hdr = [s(h) for h in hr]; out = []
    for r in it:
        d = dict(zip(hdr, r))
        pn = s(d.get("PERMITNUMBER"))
        if not pn: continue
        iss = d.get("ISSUEDATE")
        iss = iss.date().isoformat() if isinstance(iss, datetime.datetime) else s(iss)[:10]
        tmk = s(d.get("PARCELNUMBER"))
        # Owner names are deliberately NOT stored (privacy).
        out.append({
            "permit_number": pn, "issue_date": iss, "address": s(d.get("MAL1")),
            "tmk": tmk, "district": ZONES.get(tmk[:1], ""),
            "scope": s(d.get("ScopeofWork")), "use": s(d.get("TypeOfUse")),
            "project_type": s(d.get("ProjectType")), "class": s(d.get("ProjectClassCategory")),
            "contractor": s(d.get("CONTRACTOR")), "plans_by": s(d.get("PLANSBY")),
            "floor_sqft": s(d.get("MajorFloorAreaSqFt")), "accessory_sqft": s(d.get("AccessoryFloorAreaSqFt")),
            "units": s(d.get("NumberofUnits")), "valuation": num(d.get("VALUATION")),
            "fees": num(d.get("FEETOTAL")), "source_file": label, "source_url": src_url})
    return out

def _url(docid): return f"{BASE}/ElectronicFile.aspx?docid={docid}&dbid=1&repo=PublicDocuments"
EXTRACT = re.compile(r"\s*(\d\d)\s*-\s*(.+?)\s+Building Permits Extract", re.I)

def fetch_permits():
    """Monthly extracts + weekly extracts (Weekly Details/<month>/). Deduped on permit number;
    the monthly file wins when both carry a permit, weekly fills anything newer/missing."""
    years = {e["name"]: e["entryId"] for e in ls(PERMITS_ISSUED_FOLDER) if e["type"] == 0}
    monthly, weekly = {}, {}
    for y in YEARS:
        if y not in years: print("no permits folder for", y); continue
        for e in ls(years[y]):
            if e["type"] == 0 and e["name"].strip().lower() == "weekly details":
                for mf in ls(e["entryId"]):
                    if mf["type"] != 0: continue
                    for w in ls(mf["entryId"]):
                        m = EXTRACT.match(w["name"])
                        if not (m and w.get("extension") == "xlsx"): continue
                        rows = parse_extract(download(w["entryId"], "xlsx"), f"{y} weekly {w['name'].strip()}", _url(w["entryId"]))
                        for r in rows: weekly[r["permit_number"]] = r
                        print(f"weekly {y} {w['name'].strip()}: {len(rows)}")
                continue
            m = EXTRACT.match(e["name"])
            if not (m and e.get("extension") == "xlsx" and m.group(2).strip().isalpha()): continue
            rows = parse_extract(download(e["entryId"], "xlsx"), f"{y}-{m.group(1)} monthly", _url(e["entryId"]))
            for r in rows: monthly[r["permit_number"]] = r
            print(f"monthly {y}-{m.group(1)}: {len(rows)}")
    merged = {**weekly, **monthly}
    print(f"monthly {len(monthly)}, weekly {len(weekly)}, weekly-only {len(set(weekly)-set(monthly))}, merged {len(merged)}")
    return sorted(merged.values(), key=lambda r: (r["issue_date"], r["permit_number"]), reverse=True)

VAL = r"(No Data|[\d,]+)"
LINE = re.compile(rf"^\s*(?:(\d)\s+)?([A-Za-z][A-Za-z/\-() ,.]*?[A-Za-z)])\s{{2,}}{VAL}\s+{VAL}\s+{VAL}\s*$")
def fetch_metrics():
    docs = []
    for e in ls(METRICS_FOLDER):
        if e["type"] == 0 and e["name"] in YEARS: docs += ls(e["entryId"])
        elif e["type"] != 0: docs.append(e)
    out = []
    for e in docs:
        m = re.match(r"(\d{4}) (\d\d)_Building Metrics", e["name"])
        if not m or m.group(1) not in YEARS: continue
        txt = subprocess.run(["pdftotext", "-layout", download(e["entryId"], "pdf"), "-"],
                             capture_output=True, text=True).stdout
        section, cat = "avg_days", ""
        for line in txt.splitlines():
            if "QUANTITY" in line: section = "count"; continue
            mm = LINE.match(line)
            if not mm: continue
            lvl, name = mm.group(1), re.sub(r"\s+", " ", mm.group(2))
            if lvl: cat = name
            v = [None if x == "No Data" else int(x.replace(",", "")) for x in mm.groups()[2:]]
            out.append({"report_month": f"{m.group(1)}-{m.group(2)}", "metric": section,
                        "category": name if (lvl or name == "TOTAL") else cat, "permit_type": "" if lvl or name == "TOTAL" else name,
                        "is_category_total": bool(lvl) or name == "TOTAL",
                        "last_3mo": v[0], "last_6mo": v[1], "last_12mo": v[2],
                        "source_url": f"{BASE}/ElectronicFile.aspx?docid={e['entryId']}&dbid=1&repo=PublicDocuments"})
        print("metrics", e["name"], sum(1 for r in out if r["report_month"] == f"{m.group(1)}-{m.group(2)}"))
    return sorted(out, key=lambda r: r["report_month"])

def write(name, rows):
    json.dump(rows, open(os.path.join(DATA, name + ".json"), "w"), indent=1, default=str)
    if rows:
        with open(os.path.join(DATA, name + ".csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    os.makedirs(RAW, exist_ok=True); os.makedirs(DATA, exist_ok=True)
    permits, metrics = fetch_permits(), fetch_metrics()
    write("permits", permits); write("metrics", metrics)
    by_month = defaultdict(Counter)
    for p in permits: by_month[p["issue_date"][:7]][p["scope"] or "Other"] += 1
    summary = {"generated_at": datetime.datetime.now().isoformat(timespec="minutes"),
               "permit_count": len(permits),
               "issue_date_range": [permits[-1]["issue_date"], permits[0]["issue_date"]] if permits else None,
               "by_month_scope": {k: dict(v) for k, v in sorted(by_month.items())},
               "by_district": dict(Counter(p["district"] or "Unknown" for p in permits).most_common()),
               "latest_metrics_month": metrics[-1]["report_month"] if metrics else None}
    json.dump(summary, open(os.path.join(DATA, "summary.json"), "w"), indent=1)
    print(json.dumps({k: summary[k] for k in ("permit_count", "issue_date_range", "latest_metrics_month")}))

if __name__ == "__main__": main()
