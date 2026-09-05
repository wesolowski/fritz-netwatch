#!/usr/bin/env python3
# Builds dashboard.html from netcheck.log + docsis.log.
import re, os, html
from datetime import datetime
from collections import defaultdict, OrderedDict

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "netcheck.log")
DOCLOG = os.path.join(DIR, "docsis.log")
OUT = os.path.join(DIR, "dashboard.html")

meas_re = re.compile(r'^(\d{4}-\d\d-\d\d) (\d\d):\d\d:\d\d (OK|STURM)\s+Router: (\d+)% Verlust, (?:max )?(\d+)ms \| Internet: (\d+)%')
doc_re  = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) DOCSIS uncorr=(\d+) corr=(\d+) ds_pwr=(\S+) us_pwr=(\S+)')

rows, events = [], []
reboots = failed = 0
if os.path.exists(LOG):
    for line in open(LOG, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        m = meas_re.match(line)
        if m:
            date, hour, kind, rloss, rrtt, iloss = m.groups()
            rows.append({"date":date,"hour":int(hour),"ts":f"{date} {hour}","kind":kind,
                         "rloss":int(rloss),"rrtt":int(rrtt),"iloss":int(iloss)})
        if "Repeater-Reboot ausgel" in line: reboots += 1
        if "FEHLGESCHLAGEN" in line or "failed" in line.lower(): failed += 1
        if any(k in line for k in ("STURM","Reboot","SELFTEST")): events.append(line)

docs = []
if os.path.exists(DOCLOG):
    for line in open(DOCLOG, encoding="utf-8", errors="replace"):
        m = doc_re.match(line.rstrip("\n"))
        if m:
            ts, un, co, dsp, usp = m.groups()
            docs.append({"ts":ts,"uncorr":int(un),"corr":int(co),"ds":dsp,"us":usp})

total = len(rows); oks = sum(1 for r in rows if r["kind"]=="OK")
storms = total - oks
uptime = (oks/total*100) if total else 100.0
rtts = [r["rrtt"] for r in rows] or [0]
avg_rtt = sum(rtts)/len(rtts); max_rtt = max(rtts)
worst_loss = max((r["rloss"] for r in rows), default=0)
last = rows[-1] if rows else None
cur_ok = (last["kind"]=="OK") if last else True

# ---------- helpers ----------
def card(label, value, sub="", cls=""):
    return (f'<div class="card {cls}"><div class="cval">{value}</div>'
            f'<div class="clabel">{label}</div>{f"<div class=csub>{sub}</div>" if sub else ""}</div>')

def line_chart(pts, yval, cap, title, unit, threshold=None, colorfn=None, second=None, legend=None):
    W,H,PAD = 900,190,34
    def sx(i,n): return PAD+(W-2*PAD)*(i/max(n-1,1))
    def sy(v): return PAD+(H-2*PAD)*(1-min(v,cap)/cap)
    svg=[f'<svg viewBox="0 0 {W} {H}">']
    for gv in [0,cap*0.25,cap*0.5,cap*0.75,cap]:
        svg.append(f'<text x="6" y="{sy(gv)+4:.0f}" class="axis">{gv:.0f}</text>')
    if threshold is not None:
        ty=sy(threshold)
        svg.append(f'<line x1="{PAD}" y1="{ty:.0f}" x2="{W-PAD}" y2="{ty:.0f}" class="thr"/>')
        svg.append(f'<text x="{W-PAD-4}" y="{ty-5:.0f}" class="axis" text-anchor="end">{title}</text>')
    def poly(series, cls):
        p=" ".join(f"{sx(i,len(pts)):.1f},{sy(series(pt)):.1f}" for i,pt in enumerate(pts))
        return f'<polyline class="{cls}" points="{p}"/>'
    if second: svg.append(poly(second,"line2"))
    svg.append(poly(yval,"line1"))
    for i,pt in enumerate(pts):
        c = colorfn(pt) if colorfn else "dot-ok"
        r = 3.5 if c=="dot-storm" else 1.8
        svg.append(f'<circle cx="{sx(i,len(pts)):.1f}" cy="{sy(yval(pt)):.1f}" r="{r}" class="{c}">'
                   f'<title>{pt["ts"]} — {yval(pt):.0f}{unit}</title></circle>')
    svg.append('</svg>')
    leg = f'<div class="legend">{legend}</div>' if legend else ''
    return "".join(svg)+leg

# ---------- charts ----------
pts = rows[-120:]
rtt_chart = line_chart(pts, lambda p:p["rrtt"], 1500, "Alarmschwelle 800ms","ms",
    threshold=800, colorfn=lambda p:"dot-storm" if p["kind"]=="STURM" else "dot-ok",
    legend='<span><i class="sw a"></i>OK</span><span><i class="sw b"></i>Sturm</span>') if pts else '<p class="muted">Noch keine Daten.</p>'

loss_chart = line_chart(pts, lambda p:p["rloss"], 100, None,"%",
    second=lambda p:p["iloss"],
    colorfn=lambda p:"dot-storm" if p["rloss"]>=30 else "dot-ok",
    legend='<span><i class="sw a"></i>Router-Verlust</span><span><i class="sw c"></i>Internet-Verlust</span>') if pts else ''

# ---------- DOCSIS ----------
docs_panel = '<p class="muted">Keine DOCSIS-Daten (kein Kabelmodell oder noch kein Lauf).</p>'
if docs:
    latest = docs[-1]
    # rate of NEW uncorrectable errors per hour over available window
    rate_txt = "–"
    if len(docs) >= 2:
        a,b = docs[0], docs[-1]
        try:
            dt = (datetime.strptime(b["ts"],"%Y-%m-%d %H:%M:%S")-datetime.strptime(a["ts"],"%Y-%m-%d %H:%M:%S")).total_seconds()/3600
            dun = b["uncorr"]-a["uncorr"]
            if dt>0: rate_txt = f"{dun/dt:.0f}/h"
        except: pass
    # health verdict
    try:
        rate_val = float(rate_txt[:-2]) if rate_txt.endswith("/h") else 0
    except: rate_val = 0
    dv = "good" if rate_val<50 else ("warn" if rate_val>=500 else "")
    # sparkline of uncorr deltas
    deltas=[max(0,docs[i]["uncorr"]-docs[i-1]["uncorr"]) for i in range(1,len(docs))][-60:]
    spark=""
    if deltas:
        mx=max(deltas) or 1; Wc=560; bw=Wc/max(len(deltas),1)
        bars="".join(f'<rect x="{i*bw:.1f}" y="{40-38*d/mx:.1f}" width="{max(bw-1,1):.1f}" height="{38*d/mx:.1f}" class="bar"/>'
                     for i,d in enumerate(deltas))
        spark=f'<svg viewBox="0 0 {Wc} 42" class="spark">{bars}</svg><div class="csub">neue nicht-korrigierbare Fehler pro Check (max {mx})</div>'
    tot_fmt = f"{latest['uncorr']:,}".replace(",", ".")
    docs_panel=(f'<div class="grid">'
        f'{card("Fehlerrate", rate_txt, "neue nicht-korr.", dv)}'
        f'{card("Fehler gesamt", tot_fmt, "seit Box-Neustart")}'
        f'{card("Downstream-Pegel", latest["ds"]+" dBmV", "gut: -10…+10")}'
        f'{card("Upstream-Pegel", latest["us"]+" dBmV", "gut: <50")}'
        f'</div>{spark}')

# ---------- daily overview ----------
byday = OrderedDict()
for r in rows:
    d=byday.setdefault(r["date"],{"n":0,"ok":0,"storm":0})
    d["n"]+=1; d["ok"]+= (r["kind"]=="OK"); d["storm"]+=(r["kind"]=="STURM")
day_rows="".join(
    f'<tr><td>{d}</td><td>{v["n"]}</td><td>{(v["ok"]/v["n"]*100):.0f}%</td>'
    f'<td class="{"muted" if v["storm"]==0 else "bad"}">{v["storm"]}</td></tr>'
    for d,v in list(byday.items())[-7:]) or '<tr><td class="muted" colspan="4">Noch keine Tagesdaten</td></tr>'

# ---------- heatmap (days x 24h) ----------
cell = defaultdict(lambda:None)  # (date,hour)->worst
for r in rows:
    k=(r["date"],r["hour"]); cur=cell[k]
    st = "storm" if r["kind"]=="STURM" else "ok"
    if cur!="storm": cell[k]=st
days=list(byday.keys())[-7:]
heat='<table class="heat"><tr><th></th>'+"".join(f'<th>{h}</th>' for h in range(24))+'</tr>'
for d in days:
    heat+=f'<tr><th>{d[5:]}</th>'
    for h in range(24):
        s=cell.get((d,h))
        cls="hc-"+(s if s else "none")
        heat+=f'<td class="{cls}"><span title="{d} {h}:00 — {s or "kein Check"}"></span></td>'
    heat+='</tr>'
heat+='</table>' if days else ''
if not days: heat='<p class="muted">Noch keine Daten für die Heatmap.</p>'

rows_html="".join(f'<tr class="{"r-storm" if "STURM" in e else ""}"><td>{html.escape(e)}</td></tr>'
    for e in reversed(events[-60:])) or '<tr><td class="muted">Alles ruhig – keine Ereignisse 👍</td></tr>'
status_badge=('<span class="badge ok">● Alles OK</span>' if cur_ok else '<span class="badge bad">● Störung aktiv</span>')
last_ts=last["ts"] if last else "–"; gen_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

htmlout=f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>fritz-netwatch</title><style>
:root{{--bg:#f5f6f8;--fg:#1a1d21;--muted:#6b7280;--card:#fff;--line:#e3e6ea;--ok:#16a34a;--bad:#dc2626;--accent:#2563eb;--accent2:#f59e0b}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e6e8eb;--muted:#9aa1ab;--card:#171a20;--line:#262b33;--ok:#22c55e;--bad:#f04747;--accent:#4f8cff;--accent2:#fbbf24}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,system-ui,sans-serif}}
.wrap{{max-width:980px;margin:0 auto;padding:26px 20px 60px}}
header{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px}}
h1{{font-size:22px;margin:0;letter-spacing:-.02em}} .sub{{color:var(--muted);font-size:13px}}
.badge{{font-weight:600;padding:4px 12px;border-radius:999px;font-size:13px}}
.badge.ok{{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}}
.badge.bad{{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin:16px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}}
.cval{{font-size:24px;font-weight:700;letter-spacing:-.02em}} .clabel{{color:var(--muted);font-size:12px;margin-top:2px}}
.csub{{font-size:11px;color:var(--muted);margin-top:4px}} .card.good .cval{{color:var(--ok)}} .card.warn .cval{{color:var(--bad)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:16px 0}}
.panel h2{{font-size:14px;margin:0 0 12px;font-weight:600}}
svg{{width:100%;height:auto;display:block}} .axis{{fill:var(--muted);font-size:10px}}
.dot-ok{{fill:var(--accent)}} .dot-storm{{fill:var(--bad)}}
.line1{{fill:none;stroke:var(--accent);stroke-width:2}} .line2{{fill:none;stroke:var(--accent2);stroke-width:1.6;opacity:.85}}
.thr{{stroke:var(--bad);stroke-dasharray:4 4;stroke-width:1;opacity:.6}} .bar{{fill:var(--accent2)}}
.legend{{display:flex;gap:16px;font-size:11px;color:var(--muted);margin-top:8px}}
.sw{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}}
.sw.a{{background:var(--accent)}}.sw.b{{background:var(--bad)}}.sw.c{{background:var(--accent2)}}
table{{width:100%;border-collapse:collapse;font:12px/1.5 ui-monospace,Menlo,monospace}}
td,th{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}} .r-storm td{{color:var(--bad)}}
.muted{{color:var(--muted)}} .bad{{color:var(--bad)}}
.heat{{border-collapse:separate;border-spacing:2px}} .heat th{{border:none;color:var(--muted);font:10px system-ui;font-weight:500;padding:2px}}
.heat td{{border:none;padding:0}} .heat td span{{display:block;width:26px;height:16px;border-radius:3px;background:var(--line)}}
.hc-ok span{{background:var(--ok);opacity:.75}} .hc-storm span{{background:var(--bad)}} .hc-none span{{background:var(--line)}}
footer{{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}}
.scroll{{overflow-x:auto}}
</style></head><body><div class="wrap">
<header><h1>🛰️ fritz-netwatch</h1>{status_badge}<span class="sub">letzter Check: {last_ts}</span></header>
<div class="grid">
{card("Verfügbarkeit", f"{uptime:.1f}%", f"{oks}/{total} OK", "good" if uptime>=99 else ("warn" if uptime<95 else ""))}
{card("Checks", total, "gesamt")}
{card("Störungen", storms, "Sturm", "warn" if storms else "good")}
{card("Auto-Reboots", reboots, f"{failed} fehlgeschlagen" if failed else "Repeater", "warn" if failed else "")}
{card("Ø Antwortzeit", f"{avg_rtt:.0f} ms", "Router")}
{card("Max / Verlust", f"{max_rtt} ms", f"Verlust {worst_loss}%", "warn" if max_rtt>=800 else "")}
</div>
<div class="panel"><h2>Antwortzeit zum Router (letzte {len(pts)})</h2>{rtt_chart}</div>
<div class="panel"><h2>Paketverlust – Router vs. Internet</h2>{loss_chart}</div>
<div class="panel"><h2>📡 DOCSIS-Leitungsqualität (Vodafone-Kabel)</h2>{docs_panel}</div>
<div class="panel"><h2>Ausfall-Heatmap (letzte 7 Tage · Stunde 0–23)</h2><div class="scroll">{heat}</div>
<div class="legend"><span><i class="sw a" style="background:var(--ok)"></i>OK</span><span><i class="sw b"></i>Sturm</span><span><i class="sw" style="background:var(--line)"></i>kein Check</span></div></div>
<div class="panel"><h2>Tagesübersicht</h2><table><tr><th>Tag</th><th>Checks</th><th>Verfügbar</th><th>Störungen</th></tr>{day_rows}</table></div>
<div class="panel"><h2>Ereignisse</h2><table>{rows_html}</table></div>
<footer>Erzeugt {gen_ts} · aktualisiert sich alle 60s · Check alle 15min</footer>
</div></body></html>"""
open(OUT,"w",encoding="utf-8").write(htmlout)
print(f"Dashboard: {total} Checks, {storms} Stürme, {reboots} Reboots, {len(docs)} DOCSIS-Punkte")
