#!/usr/bin/env python3
# Liest ~/netmon/netcheck.log und erzeugt ein lokales Dashboard (dashboard.html).
import re, os, html, json
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "netcheck.log")
OUT = os.path.join(DIR, "dashboard.html")

meas_re = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (OK|STURM)\s+Router: (\d+)% Verlust, (?:max )?(\d+)ms \| Internet: (\d+)%')
rows, events = [], []
reboots = skipped = failed = selftests = 0

if os.path.exists(LOG):
    for line in open(LOG, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        m = meas_re.match(line)
        if m:
            ts, kind, rloss, rrtt, iloss = m.groups()
            rows.append({"ts": ts, "kind": kind, "rloss": int(rloss),
                         "rrtt": int(rrtt), "iloss": int(iloss)})
        if "Repeater-Reboot ausgelöst" in line: reboots += 1
        if "Reboot übersprungen" in line: skipped += 1
        if "Reboot FEHLGESCHLAGEN" in line or "Reboot fehlgeschlagen" in line: failed += 1
        if "SELFTEST" in line: selftests += 1
        if any(k in line for k in ("STURM", "Reboot", "SELFTEST")):
            events.append(line)

total = len(rows)
oks = sum(1 for r in rows if r["kind"] == "OK")
storms = sum(1 for r in rows if r["kind"] == "STURM")
uptime = (oks / total * 100) if total else 100.0
rtts = [r["rrtt"] for r in rows] or [0]
avg_rtt = sum(rtts) / len(rtts)
max_rtt = max(rtts)
worst_loss = max((r["rloss"] for r in rows), default=0)
last = rows[-1] if rows else None
cur_ok = (last["kind"] == "OK") if last else True

# --- Chart (letzte 120 Messpunkte), Inline-SVG, RTT-Linie mit Sturm-Punkten ---
pts = rows[-120:]
W, H, PAD = 900, 220, 34
def sx(i, n): return PAD + (W - 2*PAD) * (i / max(n-1, 1))
CAP = 1500
def sy(v): 
    v = min(v, CAP)
    return PAD + (H - 2*PAD) * (1 - v / CAP)
thr_y = sy(800)
poly = " ".join(f"{sx(i,len(pts)):.1f},{sy(p['rrtt']):.1f}" for i, p in enumerate(pts))
dots = "".join(
    f'<circle cx="{sx(i,len(pts)):.1f}" cy="{sy(p["rrtt"]):.1f}" r="{3.5 if p["kind"]=="STURM" else 2}" '
    f'class="{"dot-storm" if p["kind"]=="STURM" else "dot-ok"}"><title>{p["ts"]} — {p["rrtt"]}ms, {p["rloss"]}% Verlust</title></circle>'
    for i, p in enumerate(pts))
yl = "".join(f'<text x="6" y="{sy(v)+4:.0f}" class="axis">{v}</text>' for v in (0,400,800,1200))

def card(label, value, sub="", cls=""):
    return (f'<div class="card {cls}"><div class="cval">{value}</div>'
            f'<div class="clabel">{label}</div>{f"<div class=csub>{sub}</div>" if sub else ""}</div>')

rows_html = "".join(
    f'<tr class="{("r-storm" if e.split(maxsplit=2)[1] not in ("OK","SELFTEST") and "STURM" in e else "")}">'
    f'<td>{html.escape(e)}</td></tr>' for e in reversed(events[-60:])) or '<tr><td class="muted">Noch keine besonderen Ereignisse – alles ruhig 👍</td></tr>'

status_badge = ('<span class="badge ok">● Alles OK</span>' if cur_ok
                else '<span class="badge bad">● Störung aktiv</span>')
last_ts = last["ts"] if last else "–"
gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

htmlout = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>fritz-netwatch</title>
<style>
:root{{--bg:#f5f6f8;--fg:#1a1d21;--muted:#6b7280;--card:#fff;--line:#e3e6ea;--ok:#16a34a;--bad:#dc2626;--accent:#2563eb;--grid:#eceff3}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e6e8eb;--muted:#9aa1ab;--card:#171a20;--line:#262b33;--ok:#22c55e;--bad:#f04747;--accent:#4f8cff;--grid:#1c2028}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,system-ui,sans-serif}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 20px 60px}}
header{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:6px}}
h1{{font-size:22px;margin:0;letter-spacing:-.02em}}
.sub{{color:var(--muted);font-size:13px}}
.badge{{font-weight:600;padding:4px 12px;border-radius:999px;font-size:13px}}
.badge.ok{{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}}
.badge.bad{{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:20px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}}
.cval{{font-size:26px;font-weight:700;letter-spacing:-.02em}}
.clabel{{color:var(--muted);font-size:12px;margin-top:2px}}
.csub{{font-size:11px;color:var(--muted);margin-top:4px}}
.card.good .cval{{color:var(--ok)}}.card.warn .cval{{color:var(--bad)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:16px 0}}
.panel h2{{font-size:14px;margin:0 0 12px;font-weight:600}}
svg{{width:100%;height:auto;display:block}}
.axis{{fill:var(--muted);font-size:10px}}
.dot-ok{{fill:var(--accent)}}.dot-storm{{fill:var(--bad)}}
.rttline{{fill:none;stroke:var(--accent);stroke-width:2}}
.thr{{stroke:var(--bad);stroke-dasharray:4 4;stroke-width:1;opacity:.6}}
table{{width:100%;border-collapse:collapse;font:12px/1.5 ui-monospace,Menlo,monospace}}
td{{padding:6px 8px;border-bottom:1px solid var(--line);white-space:pre-wrap}}
.r-storm td{{color:var(--bad)}}
.muted{{color:var(--muted)}}
.legend{{display:flex;gap:16px;font-size:11px;color:var(--muted);margin-top:8px}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}}
footer{{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}}
</style></head><body><div class="wrap">
<header><h1>🛰️ fritz-netwatch</h1>{status_badge}<span class="sub">letzter Check: {last_ts}</span></header>
<div class="grid">
{card("Verfügbarkeit", f"{uptime:.1f}%", f"{oks} von {total} Checks OK", "good" if uptime>=99 else ("warn" if uptime<95 else ""))}
{card("Checks gesamt", total, "seit Start")}
{card("Störungen", storms, "Sturm erkannt", "warn" if storms else "good")}
{card("Auto-Reboots", reboots, f"{failed} fehlgeschlagen" if failed else "Repeater neugestartet", "warn" if failed else "")}
{card("Ø Antwortzeit", f"{avg_rtt:.0f} ms", "zum Router")}
{card("Max / Verlust", f"{max_rtt} ms", f"schlimmster Verlust {worst_loss}%", "warn" if max_rtt>=800 else "")}
</div>
<div class="panel"><h2>Antwortzeit zum Router (letzte {len(pts)} Checks)</h2>
<svg viewBox="0 0 {W} {H}">
<line x1="{PAD}" y1="{thr_y:.0f}" x2="{W-PAD}" y2="{thr_y:.0f}" class="thr"/>
<text x="{W-PAD-4}" y="{thr_y-5:.0f}" class="axis" text-anchor="end">Alarmschwelle 800ms</text>
{yl}
<polyline class="rttline" points="{poly}"/>
{dots}
</svg>
<div class="legend"><span><span class="dot" style="background:var(--accent)"></span>OK</span><span><span class="dot" style="background:var(--bad)"></span>Sturm</span></div>
</div>
<div class="panel"><h2>Ereignisse (Stürme, Reboots, Tests)</h2>
<table>{rows_html}</table></div>
<footer>Automatisch erzeugt {gen_ts} · Seite aktualisiert sich alle 60 s · Check alle 15 min</footer>
</div></body></html>"""

open(OUT, "w", encoding="utf-8").write(htmlout)
print(f"Dashboard geschrieben: {OUT}  ({total} Checks, {storms} Stürme, {reboots} Reboots)")
