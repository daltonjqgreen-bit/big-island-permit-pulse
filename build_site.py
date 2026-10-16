#!/usr/bin/env python3
"""Build static site/index.html from data/ (run fetch.py first). Pure HTML + inline SVG, no JS deps."""
import json, os, html, datetime
from collections import Counter
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, "data"); S = os.path.join(H, "site")
permits = json.load(open(f"{D}/permits.json")); metrics = json.load(open(f"{D}/metrics.json"))
summ = json.load(open(f"{D}/summary.json")); e = lambda x: html.escape(str(x or ""))
latest = max(r["report_month"] for r in metrics)
def mlabel(ym): return datetime.date(int(ym[:4]), int(ym[5:]), 1).strftime("%b %Y")

def line_svg(series, w=560, h=200, unit=""):
    pts = [(k, v) for k, v in series if v is not None]
    mx = max(v for _, v in pts) * 1.15; n = len(pts); pad = 34
    xy = [(pad + i * (w - 2 * pad) / max(n - 1, 1), h - 24 - v / mx * (h - 44)) for i, (_, v) in enumerate(pts)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(xy))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3"/>' for x, y in xy)
    lab = "".join(f'<text x="{x:.1f}" y="{h-6}" text-anchor="middle">{mlabel(k)[:3]} {k[2:4]}</text>'
                  for i, ((k, _), (x, _)) in enumerate(zip(pts, xy)) if i % 3 == 0 or i == n - 1)
    val = "".join(f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" class="v">{v}{unit}</text>'
                  for i, ((_, v), (x, y)) in enumerate(zip(pts, xy)) if i in (0, n - 1))
    return f'<svg viewBox="0 0 {w} {h}" class="chart"><path d="{path}"/>{dots}{lab}{val}</svg>'

def bar_svg(items, w=560, rowh=24):
    mx = max(v for _, v in items); h = rowh * len(items) + 6
    out = "".join(f'<text x="0" y="{i*rowh+16}">{e(k)}</text><rect x="190" y="{i*rowh+4}" width="{max(v/mx*(w-250),2):.0f}" height="{rowh-8}" rx="3"/>'
                  f'<text x="{196+v/mx*(w-250):.0f}" y="{i*rowh+16}" class="v">{v:,}</text>' for i, (k, v) in enumerate(items))
    return f'<svg viewBox="0 0 {w} {h}" class="chart bars">{out}</svg>'

def M(month, metric, ptype=None, cat=None):
    for r in metrics:
        if r["report_month"] == month and r["metric"] == metric and (ptype is None or r["permit_type"] == ptype) and (cat is None or (r["category"] == cat and r["is_category_total"])):
            return r

# wait-time cards (latest month, 3-month avg days)
cards = []
for pt in ["Residential New Construction", "Residential Addition", "Residential Alteration", "Residential PV Permit",
           "Non-Residential New Construction", "Non-Residential Alteration"]:
    r = M(latest, "avg_days", pt); prev = M(f"{int(latest[:4])-1}{latest[4:]}", "avg_days", pt)
    if not r or r["last_3mo"] is None: continue
    d = "" if not prev or prev["last_3mo"] is None else f'<div class="delta">{prev["last_3mo"]} days a year ago</div>'
    cards.append(f'<div class="card"><div class="big">{r["last_3mo"]}<span> days</span></div><div>{e(pt)}</div>{d}</div>')

trend = [(m, (M(m, "avg_days", "Residential New Construction") or {}).get("last_3mo")) for m in sorted({r["report_month"] for r in metrics})]
vol = sorted((k, sum(v.values())) for k, v in summ["by_month_scope"].items())
last12 = [p for p in permits if p["issue_date"] >= vol[-12][0]]
by_scope = Counter(p["scope"] or "Other" for p in last12).most_common(8)
by_dist = Counter(p["district"] or "Unknown" for p in last12).most_common()
cat_tot = [(r["category"], r["last_12mo"]) for r in metrics if r["report_month"] == latest and r["metric"] == "count" and r["is_category_total"] and r["category"] != "TOTAL"]

leads = [p for p in permits if p["scope"] in ("New", "Addition", "Alteration") and (p["valuation"] or 0) > 0][:25]
lead_rows = "".join(f'<tr><td>{e(p["issue_date"])}</td><td>{e(p["district"])}</td><td>{e(p["address"]) or "TMK " + e(p["tmk"])}</td>'
                    f'<td>{e(p["scope"])} · {e(p["use"] or p["class"])}</td><td class="r">${p["valuation"]:,.0f}</td><td>{e(p["contractor"])}</td></tr>' for p in leads)

src_m = M(latest, "count", cat="TOTAL")["source_url"]
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Big Island Permit Pulse – Hawaiʻi County building permit wait times & new permits</title>
<meta name="description" content="Free tracker of Hawaiʻi County building permit approval times, permit volume by type and district, and newly issued permits.">
<style>
:root{{--ink:#1d2a2f;--accent:#0f766e;--sand:#f6f1e7;--line:#e2dccf}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:#fff}}
header{{background:var(--ink);color:#fff;padding:28px 20px}}header h1{{margin:0;font-size:28px}}header p{{margin:6px 0 0;opacity:.85}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 20px}}section{{padding:22px 0;border-bottom:1px solid var(--line)}}
h2{{font-size:19px;margin:0 0 4px}}.sub{{color:#5b6a70;font-size:13px;margin:0 0 14px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}
.card{{background:var(--sand);border-radius:10px;padding:14px}}.big{{font-size:34px;font-weight:700;color:var(--accent)}}.big span{{font-size:14px;font-weight:500}}
.delta{{font-size:12px;color:#5b6a70}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
.chart{{width:100%;height:auto;font-size:11px}}.chart path{{fill:none;stroke:var(--accent);stroke-width:2.5}}.chart circle{{fill:var(--accent)}}
.chart .v{{font-weight:700;fill:var(--ink)}}.bars rect{{fill:var(--accent);opacity:.85}}.bars text{{font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}td:first-child{{white-space:nowrap}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:var(--sand)}}.r{{text-align:right}}
.cta{{display:grid;grid-template-columns:2fr 1fr;gap:20px}}.box{{border:2px dashed var(--accent);border-radius:10px;padding:16px}}
input{{padding:9px;border:1px solid #bbb;border-radius:6px;width:60%}}button{{padding:9px 14px;border:0;border-radius:6px;background:var(--accent);color:#fff;font-weight:600}}
.sponsor{{border-color:#b45309;background:#fff8ed}}footer{{font-size:12px;color:#5b6a70;padding:18px 0 30px}}
@media(max-width:760px){{.grid2,.cta{{grid-template-columns:1fr}}}}
</style></head><body>
<header><div class="wrap"><h1>Big Island Permit Pulse</h1><p>How long Hawaiʻi County permits are taking, what's being built, and where. Updated monthly from County public records.</p></div></header>
<main class="wrap">
<section><h2>Approval wait times</h2><p class="sub">Average days to process, last 3 months (County report for {mlabel(latest)}). County note: counts only permits <b>not returned for corrections</b>, so real-world waits with corrections run longer.</p>
<div class="cards">{''.join(cards)}</div></section>
<section class="grid2"><div><h2>Residential new-construction wait trend</h2><p class="sub">Rolling 3-month average days, by County report month</p>{line_svg(trend)}</div>
<div><h2>Permits issued per month</h2><p class="sub">All building permits issued, from County monthly extracts</p>{line_svg(vol)}</div></section>
<section class="grid2"><div><h2>Permits by type (last 12 months)</h2><p class="sub">County metrics report, {mlabel(latest)}</p>{bar_svg(cat_tot)}</div>
<div><h2>Permits by district (last 12 months)</h2><p class="sub">From parcel TMK zone of each issued permit</p>{bar_svg(by_dist)}</div></section>
<section><h2>Latest permits issued: new builds, additions & alterations</h2><p class="sub">Newest 25 with a declared valuation. Owner names are omitted.</p>
<table><tr><th>Issued</th><th>District</th><th>Address</th><th>Work</th><th class="r">Valuation</th><th>Contractor</th></tr>{lead_rows}</table></section>
<section class="cta"><div class="box"><h2>Get the Permit Pulse every Monday</h2><p class="sub">Wait times, new permits in your district, and who's building. Free.</p>
<form onsubmit="alert('Newsletter signup coming soon');return false"><input type="email" placeholder="you@example.com" aria-label="email"> <button>Subscribe</button></form></div>
<div class="box sponsor"><h2>Sponsor this spot</h2><p class="sub">Reach Big Island contractors, owner-builders and trades. Lumber yards, suppliers, bonding & insurance welcome.</p><a href="#">Sponsor this →</a></div></section>
<footer>Data: County of Hawaiʻi Dept. of Public Works, Building Division public records (<a href="{e(src_m)}">latest metrics report</a>, monthly "Building Permits Extract" files). {summ['permit_count']:,} permits issued {summ['issue_date_range'][0]} to {summ['issue_date_range'][1]}. Not affiliated with the County. Built {summ['generated_at'][:10]}.</footer>
</main></body></html>"""
os.makedirs(S, exist_ok=True); open(f"{S}/index.html", "w").write(page); print("wrote", f"{S}/index.html")
