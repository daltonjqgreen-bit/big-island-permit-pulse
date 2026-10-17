#!/usr/bin/env python3
"""Build site/index.html (leads-first) and newsletter/ drafts from data/ (run fetch.py first).
Static HTML + inline SVG + a little vanilla JS for table filters. Owner names are never used."""
import json, os, re, html, datetime as dt, statistics as st
from collections import Counter, defaultdict

H = os.path.dirname(os.path.abspath(__file__))
D, S, N = (os.path.join(H, x) for x in ("data", "site", "newsletter"))
permits = json.load(open(f"{D}/permits.json")); metrics = json.load(open(f"{D}/metrics.json"))
summ = json.load(open(f"{D}/summary.json"))
e = lambda x: html.escape(str(x if x is not None else ""))
SITE_URL = "https://daltonjqgreen-bit.github.io/big-island-permit-pulse/"

def work_type(p):
    sc = p["scope"]
    if "Swimming Pool" in sc: return "Pool / spa"
    if sc in ("Photovoltaic", "Solar Water Heater"): return "Solar"
    if "New" in sc.split(","): return "New build"
    if sc.startswith("Addition"): return "Addition"
    if sc.startswith("Alteration"): return "Alteration"
    return None

def is_contractor(c): return bool(c) and "CT-" in c
def money(v):
    if v is None: return "n/a"
    return f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:,.0f}K" if v >= 1e3 else f"${v:,.0f}"
def nice_date(s): d = dt.date.fromisoformat(s); return d.strftime("%b %-d, %Y")

latest = max(p["issue_date"] for p in permits)
LD = dt.date.fromisoformat(latest)
week_start = (LD - dt.timedelta(days=6)).isoformat()
yr_start = (LD - dt.timedelta(days=364)).isoformat()
leads = [dict(p, wt=work_type(p)) for p in permits if work_type(p)]
leads12 = [p for p in leads if p["issue_date"] >= yr_start]
week = [p for p in leads if p["issue_date"] >= week_start]
big_week = sorted([p for p in week if p["wt"] != "Solar" and (p["valuation"] or 0) > 0], key=lambda p: -p["valuation"])[:8]

# ---- real wait estimate (method in the page text) ----
P = re.compile(r"PW\.B(20\d\d)-0*(\d+)")
maxseq = defaultdict(int)
for p in permits:
    m = P.match(p["permit_number"])
    if m: maxseq[int(m.group(1))] = max(maxseq[int(m.group(1))], int(m.group(2)))
def year_days(y):  # days of the year covered by numbers issued so far
    if y < LD.year: return (dt.date(y + 1, 1, 1) - dt.date(y, 1, 1)).days
    return (LD - dt.date(y, 1, 1)).days
lags = []
for p in permits:
    m = P.match(p["permit_number"])
    if not m or p["scope"] != "New" or "Dwelling" not in p["use"] or p["issue_date"] < yr_start: continue
    y, n = int(m.group(1)), int(m.group(2))
    if y < LD.year - 2 or y not in maxseq: continue
    est_app = dt.date(y, 1, 1) + dt.timedelta(days=year_days(y) * n / maxseq[y])
    lag = (dt.date.fromisoformat(p["issue_date"]) - est_app).days
    if lag >= 0: lags.append(lag)
real_median = round(st.median(lags)); q1, _, q3 = st.quantiles(lags, n=4)
over90 = round(100 * sum(l > 90 for l in lags) / len(lags)); over180 = round(100 * sum(l > 180 for l in lags) / len(lags))
mlatest = max(r["report_month"] for r in metrics)
county_days = next(r["last_3mo"] for r in metrics if r["report_month"] == mlatest and r["metric"] == "avg_days" and r["permit_type"] == "Residential New Construction")
mdoc = next(r["source_url"] for r in metrics if r["report_month"] == mlatest)

# ---- simple big charts (one idea each) ----
def hbar(items, fmt=lambda v: f"{v:,}", color="#0f766e", w=700, rowh=58):
    mx = max(v for _, v in items) or 1; h = rowh * len(items)
    rows = []
    for i, (k, v) in enumerate(items):
        y = i * rowh; bw = max(v / mx * (w - 130), 4)
        rows.append(f'<text x="0" y="{y+20}" class="lab">{e(k)}</text>'
                    f'<rect x="0" y="{y+28}" width="{bw:.0f}" height="22" rx="4" fill="{color}"/>'
                    f'<text x="{bw+10:.0f}" y="{y+46}" class="val">{e(fmt(v))}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img">{"".join(rows)}</svg>'

def vbar(items, w=700, h=300):
    mx = max(v for _, v in items) or 1; n = len(items); gap = w / n; bw = gap * 0.68
    out = []
    for i, (k, v) in enumerate(items):
        x = i * gap + (gap - bw) / 2; bh = v / mx * (h - 80); y = h - 40 - bh
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="4" fill="#0f766e"/>'
                   f'<text x="{x+bw/2:.0f}" y="{y-8:.0f}" text-anchor="middle" class="val">{v}</text>'
                   f'<text x="{x+bw/2:.0f}" y="{h-12}" text-anchor="middle" class="lab">{k}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img">{"".join(out)}</svg>'

new_homes = Counter(p["issue_date"][:7] for p in leads if p["wt"] == "New build" and "Dwelling" in p["use"])
months = sorted(new_homes)[-12:]
chart_homes = vbar([(dt.date.fromisoformat(m + "-01").strftime("%b"), new_homes[m]) for m in months])
chart_dist = hbar(Counter(p["district"] or "Unknown" for p in leads12 if p["wt"] != "Solar").most_common(9))
chart_wait = hbar([("County's number (clean permits only)", county_days), ("Our estimated real median", real_median)],
                  fmt=lambda v: f"{v} days", color="#b45309")

# ---- leaderboard (licensed contractors, last 12 months, excluding solar) ----
cnt, val = Counter(), Counter()
for p in leads12:
    if p["wt"] == "Solar" or not is_contractor(p["contractor"]): continue
    cnt[p["contractor"]] += 1; val[p["contractor"]] += p["valuation"] or 0
top_cnt = cnt.most_common(10); top_val = sorted(val.items(), key=lambda kv: -kv[1])[:10]
sol = Counter(p["contractor"] for p in leads12 if p["wt"] == "Solar" and is_contractor(p["contractor"])).most_common(5)
def lb(rows, f): return "".join(f"<tr><td class='rk'>{i+1}</td><td>{e(k)}</td><td class='r'>{f(v)}</td></tr>" for i, (k, v) in enumerate(rows))

# ---- leads data for the JS table (no owner names) ----
tbl = [{"d": p["issue_date"], "di": p["district"], "a": p["address"] or ("TMK " + p["tmk"]), "w": p["wt"],
        "u": p["use"] or p["class"], "v": p["valuation"], "c": p["contractor"], "sq": p["floor_sqft"], "n": p["permit_number"]}
       for p in leads12]
districts = sorted({p["district"] for p in leads12 if p["district"]})
opts = "".join(f"<option>{e(d)}</option>" for d in districts)

def card(p):
    return (f'<div class="job"><div class="jv">{money(p["valuation"])}</div><div class="jw">{e(p["wt"])} · {e(p["use"] or p["class"])}</div>'
            f'<div class="ja">{e(p["address"] or "TMK " + p["tmk"])}, {e(p["district"])}</div>'
            f'<div class="jc">{e(p["contractor"])} · issued {nice_date(p["issue_date"])}</div></div>')

wk_counts = Counter(p["wt"] for p in week)
wk_val = sum(p["valuation"] or 0 for p in week if p["wt"] != "Solar")
TPL = open(os.path.join(H, "templates", "index.html")).read()
page = (TPL.replace("{{WEEK_RANGE}}", f"{nice_date(week_start)} – {nice_date(latest)}")
        .replace("{{WEEK_NEW}}", str(wk_counts["New build"])).replace("{{WEEK_ADD}}", str(wk_counts["Addition"] + wk_counts["Alteration"]))
        .replace("{{WEEK_POOL}}", str(wk_counts["Pool / spa"])).replace("{{WEEK_SOLAR}}", str(wk_counts["Solar"]))
        .replace("{{WEEK_VALUE}}", money(wk_val)).replace("{{BIG_JOBS}}", "".join(card(p) for p in big_week))
        .replace("{{DISTRICT_OPTS}}", opts).replace("{{LEADS_JSON}}", json.dumps(tbl, separators=(",", ":")).replace("</", "<\\/"))
        .replace("{{N_LEADS}}", f"{len(tbl):,}")
        .replace("{{COUNTY_DAYS}}", str(county_days)).replace("{{REAL_MEDIAN}}", str(real_median))
        .replace("{{Q1}}", str(round(q1))).replace("{{Q3}}", str(round(q3))).replace("{{OVER90}}", str(over90)).replace("{{OVER180}}", str(over180))
        .replace("{{N_LAGS}}", f"{len(lags):,}").replace("{{MLATEST}}", dt.date.fromisoformat(mlatest + "-01").strftime("%B %Y")).replace("{{MDOC}}", e(mdoc))
        .replace("{{CHART_WAIT}}", chart_wait).replace("{{CHART_HOMES}}", chart_homes).replace("{{CHART_DIST}}", chart_dist)
        .replace("{{LB_COUNT}}", lb(top_cnt, lambda v: f"{v} permits")).replace("{{LB_VALUE}}", lb(top_val, money))
        .replace("{{LB_SOLAR}}", lb(sol, lambda v: f"{v:,} permits"))
        .replace("{{N_PERMITS}}", f"{summ['permit_count']:,}").replace("{{RANGE}}", f"{nice_date(summ['issue_date_range'][0])} – {nice_date(latest)}")
        .replace("{{BUILT}}", dt.date.today().strftime("%b %-d, %Y")))
os.makedirs(S, exist_ok=True); open(f"{S}/index.html", "w").write(page)
print("site:", len(tbl), "leads (12 mo),", len(week), "this week, real median", real_median, "n", len(lags))

# ---- newsletter draft (Beehiiv-ready HTML + Markdown) ----
os.makedirs(N, exist_ok=True)
wk_list = sorted([p for p in week if p["wt"] != "Solar"], key=lambda p: -(p["valuation"] or 0))
by_d = defaultdict(list)
for p in wk_list: by_d[p["district"] or "Unknown"].append(p)
title = f"Permit Pulse: {len(wk_list)} new Big Island jobs, {nice_date(week_start)} – {nice_date(latest)}"
md = [f"# {title}", "", f"Every new Big Island job, every week, from the County record. This week: **{wk_counts['New build']} new builds**, "
      f"**{wk_counts['Addition'] + wk_counts['Alteration']} additions/alterations**, **{wk_counts['Pool / spa']} pools**, "
      f"**{wk_counts['Solar']} solar** permits issued. Declared value (non-solar): **{money(wk_val)}**.", "",
      "## This week's biggest jobs", ""]
md += [f"{i+1}. **{money(p['valuation'])}** — {p['wt']}, {p['use'] or p['class']} — {p['address'] or 'TMK ' + p['tmk']}, {p['district']} — {p['contractor']}"
       for i, p in enumerate(big_week[:5])]
md += ["", f"## Real wait check", "", f"The County reports **{county_days} days** for residential new construction ({dt.date.fromisoformat(mlatest+'-01').strftime('%B %Y')} report), "
       f"but that only counts permits never sent back for corrections. Our estimate of the real application-to-issue median: **~{real_median} days** (estimate; method on the site).", "",
       "## [Sponsor slot]", "", "_Your message to Big Island contractors here. Reply to sponsor._", "", "## All new jobs by district", ""]
for d in sorted(by_d, key=lambda d: -len(by_d[d])):
    md += [f"### {d} ({len(by_d[d])})", ""]
    md += [f"- {nice_date(p['issue_date'])} · {p['wt']} · {p['use'] or p['class']} · {p['address'] or 'TMK ' + p['tmk']} · {money(p['valuation'])} · {p['contractor']}" for p in by_d[d]]
    md += [""]
md += [f"Full searchable list: {SITE_URL}", "", "_Source: County of Hawaiʻi DPW Building Division public permit records. Owner names omitted. Not affiliated with the County._"]
mdtxt = "\n".join(md)

TD = 'style="padding:6px 8px;border-bottom:1px solid #e2dccf;font-size:14px;vertical-align:top"'
def row(p): return (f"<tr><td {TD}>{e(nice_date(p['issue_date']))}</td><td {TD}>{e(p['wt'])}<br><span style='color:#5b6a70'>{e(p['use'] or p['class'])}</span></td>"
                    f"<td {TD}>{e(p['address'] or 'TMK ' + p['tmk'])}</td><td {TD} align='right'><b>{money(p['valuation'])}</b></td><td {TD}>{e(p['contractor'])}</td></tr>")
h = [f'<div style="font-family:Arial,Helvetica,sans-serif;color:#1d2a2f;max-width:640px;margin:0 auto">',
     f'<h1 style="font-size:26px;margin:0 0 6px">{e(title)}</h1>',
     f'<p style="font-size:16px">Every new Big Island job, every week, from the County record.</p>',
     f'<table width="100%" cellpadding="0" cellspacing="0"><tr>' + "".join(
        f'<td align="center" style="background:#f6f1e7;padding:12px;font-size:14px"><div style="font-size:30px;font-weight:bold;color:#0f766e">{v}</div>{k}</td>'
        for k, v in [("New builds", wk_counts["New build"]), ("Adds/alts", wk_counts["Addition"] + wk_counts["Alteration"]), ("Pools", wk_counts["Pool / spa"]), ("Solar", wk_counts["Solar"])]) + "</tr></table>",
     f'<h2 style="font-size:20px;margin-top:24px">This week\'s biggest jobs</h2><ol style="font-size:16px;padding-left:20px">' +
     "".join(f"<li style='margin-bottom:8px'><b>{money(p['valuation'])}</b> · {e(p['wt'])}, {e(p['use'] or p['class'])}<br>{e(p['address'] or 'TMK ' + p['tmk'])}, {e(p['district'])} · {e(p['contractor'])}</li>" for p in big_week[:5]) + "</ol>",
     f'<div style="background:#fff8ed;border:2px solid #b45309;border-radius:8px;padding:14px;margin:18px 0"><b style="font-size:18px">Real wait check</b><br>'
     f'County says <b>{county_days} days</b> (clean permits only). Our estimated real median: <b>~{real_median} days</b>. <i>Estimate; method on the site.</i></div>',
     '<div style="border:2px dashed #b45309;border-radius:8px;padding:14px;margin:18px 0;color:#5b6a70">[Sponsor slot] Your message to Big Island contractors here.</div>',
     '<h2 style="font-size:20px">All new jobs by district</h2>']
for d in sorted(by_d, key=lambda d: -len(by_d[d])):
    h.append(f'<h3 style="font-size:17px;margin:16px 0 4px">{e(d)} ({len(by_d[d])})</h3><table width="100%" cellpadding="0" cellspacing="0">{"".join(row(p) for p in by_d[d])}</table>')
h.append(f'<p style="font-size:16px;margin-top:20px"><a href="{SITE_URL}" style="color:#0f766e;font-weight:bold">Search every lead on Permit Pulse →</a></p>'
         '<p style="font-size:12px;color:#5b6a70">Source: County of Hawaiʻi DPW Building Division public permit records. Owner names omitted. Not affiliated with the County.</p></div>')
for ext, txt in (("md", mdtxt), ("html", "\n".join(h))):
    open(f"{N}/{latest}.{ext}", "w").write(txt); open(f"{N}/latest.{ext}", "w").write(txt)
print("newsletter:", f"{N}/{latest}.html", len(wk_list), "non-solar jobs")
