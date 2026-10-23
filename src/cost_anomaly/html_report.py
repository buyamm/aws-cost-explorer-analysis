"""Self-contained HTML report (inline CSS/JS, no network) for one detection run."""

import json
from html import escape
from pathlib import Path

from .analysis import COLUMNS, FORMULA, KNOWN_LABEL, PROVISIONAL_LABEL, WHY_ROBUST, AnomalyRow, Report, usd
from .detect import DROP, NEW_SERVICE, SPIKE

KIND_LABEL = {SPIKE: "SPIKE", NEW_SERVICE: "NEW_SERVICE", DROP: "DROP"}
KIND_CLASS = {SPIKE: "spike", NEW_SERVICE: "new", DROP: "drop"}
KIND_MARK = {SPIKE: '<i class="dot"></i>', NEW_SERVICE: '<i class="diamond"></i>', DROP: '<i class="tri"></i>'}
THEME_KEY = "cost-anomaly-theme"

LIGHT = """
  --page: #f4f5f7; --surface: #ffffff; --sunken: #eceef2;
  --ink: #15171c; --ink-2: #464b55; --muted: #646a75;
  --grid: #e3e5ea; --axis: #c4c8d0; --border: #d9dce2;
  --series: #2a78d6; --band: rgba(42,120,214,0.10); --eval: rgba(21,23,28,0.04);
  --spike: #d03b3b; --new: #ec835a; --drop: #6250d6; --calm: #0c8a0c; --focus: #2a78d6;"""

DARK = """
  --page: #0f1115; --surface: #181b21; --sunken: #20242c;
  --ink: #eceef2; --ink-2: #b9bec8; --muted: #8f95a0;
  --grid: #2a2e36; --axis: #3b404a; --border: #2f343d;
  --series: #3987e5; --band: rgba(57,135,229,0.16); --eval: rgba(255,255,255,0.05);
  --spike: #e05555; --new: #ec835a; --drop: #9085e9; --calm: #3fb83f; --focus: #3987e5;"""

# Runs before the stylesheet so a saved theme applies on first paint (no flash of the wrong theme).
HEAD_JS = f"""(() => {{
  const d = document.documentElement;
  d.classList.add('js');
  try {{
    const t = localStorage.getItem('{THEME_KEY}');
    if (t === 'light' || t === 'dark') d.dataset.theme = t;
  }} catch (e) {{}}
}})();"""

CSS = f"""
:root {{ color-scheme: light;{LIGHT}
  --topbar-h: 104px;
  --sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ color-scheme: dark;{DARK}
  }}
}}
:root[data-theme="dark"] {{ color-scheme: dark;{DARK}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
body {{ margin: 0; background: var(--page); color: var(--ink); font: 15px/1.6 var(--sans); }}
html:not(.js) .js-only {{ display: none !important; }}
:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 4px; }}
a {{ color: inherit; }}
code {{ font: 13px var(--mono); }}

.topbar {{ position: sticky; top: 0; z-index: 10; background: var(--surface); border-bottom: 1px solid var(--border); }}
.topbar-in {{ max-width: 1120px; margin: 0 auto; padding: 10px 16px 0; display: flex; flex-wrap: wrap;
  align-items: center; gap: 4px 16px; }}
.brand {{ font-weight: 650; text-decoration: none; font-size: 15px; white-space: nowrap; }}
.actions {{ margin-left: auto; display: flex; gap: 8px; }}
.btn {{ font: inherit; font-size: 13px; color: var(--ink); background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 5px 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }}
.btn:hover {{ background: var(--sunken); }}
.btn.primary {{ background: var(--ink); color: var(--surface); border-color: var(--ink); }}
.btn.primary:hover {{ opacity: 0.88; }}
.btn[aria-pressed="true"] {{ background: var(--sunken); border-color: var(--focus); }}
.btn .switch {{ width: 22px; height: 12px; border-radius: 6px; background: var(--axis); position: relative; flex: none; }}
.btn .switch::after {{ content: ""; position: absolute; top: 2px; left: 2px; width: 8px; height: 8px; border-radius: 50%;
  background: var(--surface); transition: left 0.15s; }}
.btn[aria-pressed="true"] .switch {{ background: var(--focus); }}
.btn[aria-pressed="true"] .switch::after {{ left: 12px; }}
@media (prefers-reduced-motion: reduce) {{ .btn .switch::after {{ transition: none; }} }}
.toc {{ flex-basis: 100%; display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; margin: 0 -8px; }}
.toc::-webkit-scrollbar {{ display: none; }}
.toc a {{ font-size: 13px; color: var(--ink-2); text-decoration: none; padding: 8px; white-space: nowrap;
  border-bottom: 2px solid transparent; }}
.toc a:hover {{ color: var(--ink); border-bottom-color: var(--axis); }}

main {{ max-width: 1120px; margin: 0 auto; padding: 28px 16px 72px; }}
section[id] {{ scroll-margin-top: calc(var(--topbar-h) + 12px); }}
h1 {{ font-size: 15px; font-weight: 600; color: var(--ink-2); margin: 0 0 6px; }}
@media screen {{ h1 {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }} }}
h2 {{ font-size: 20px; line-height: 1.3; font-weight: 650; margin: 48px 0 6px; }}
h3 {{ font-size: 15px; font-weight: 600; margin: 0 0 8px; overflow-wrap: anywhere; }}
p, li {{ color: var(--ink-2); max-width: 78ch; }}
.section-lede {{ margin: 0 0 14px; }}

.verdict {{ font-size: clamp(24px, 4.2vw, 36px); line-height: 1.2; font-weight: 680; letter-spacing: -0.01em;
  color: var(--ink); margin: 0; padding-left: 18px; border-left: 6px solid var(--muted); max-width: 30ch; }}
.verdict.alert {{ border-left-color: var(--spike); }}
.verdict.drop {{ border-left-color: var(--drop); }}
.verdict.calm {{ border-left-color: var(--calm); }}
.runmeta {{ display: flex; flex-wrap: wrap; gap: 6px 28px; margin: 18px 0 0; font-size: 13px; }}
.runmeta div {{ display: flex; gap: 6px; }}
.runmeta dt {{ color: var(--muted); }}
.runmeta dd {{ margin: 0; color: var(--ink-2); font-variant-numeric: tabular-nums; }}

.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 24px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px; }}
.stat {{ padding: 14px 18px; border-left: 1px solid var(--border); min-width: 0; }}
.stat:first-child {{ border-left: 0; }}
.stat .label {{ font-size: 13px; color: var(--ink-2); }}
.stat .value {{ display: block; font-size: 26px; font-weight: 650; font-variant-numeric: tabular-nums; margin-top: 2px; }}
.stat .sub {{ display: block; font-size: 13px; color: var(--muted); }}
.stat.excess .value {{ color: var(--spike); }}
.verdict.calm ~ .stats .stat.excess .value {{ color: var(--ink); }}
.kindcounts {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
@media (max-width: 760px) {{
  .stats {{ grid-template-columns: 1fr 1fr; }}
  .stat:nth-child(3) {{ border-left: 0; }}
  .stat:nth-child(n+3) {{ border-top: 1px solid var(--border); }}
}}

.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }}
ul.points {{ margin: 0; padding: 0; list-style: none; }}
ul.points li {{ margin: 0 0 10px; padding-left: 14px; border-left: 2px solid var(--border); }}
ul.points li:last-child {{ margin-bottom: 0; }}

.badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 1px 8px 1px 7px; border-radius: 999px;
  font-size: 12px; font-weight: 600; white-space: nowrap; color: var(--ink); border: 1px solid; }}
.badge.spike {{ background: color-mix(in srgb, var(--spike) 13%, transparent); border-color: color-mix(in srgb, var(--spike) 45%, transparent); }}
.badge.new {{ background: color-mix(in srgb, var(--new) 16%, transparent); border-color: color-mix(in srgb, var(--new) 55%, transparent); }}
.badge.drop {{ background: color-mix(in srgb, var(--drop) 14%, transparent); border-color: color-mix(in srgb, var(--drop) 50%, transparent); }}
.badge b {{ font-variant-numeric: tabular-nums; }}
.tag {{ display: inline-block; margin: 4px 4px 0 0; padding: 0 6px; border: 1px dashed var(--axis); border-radius: 4px;
  font-size: 12px; color: var(--ink-2); white-space: nowrap; }}
.dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--spike); flex: none; display: inline-block; }}
.diamond {{ width: 8px; height: 8px; background: var(--new); transform: rotate(45deg); flex: none; display: inline-block; }}
.tri {{ width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
  border-top: 9px solid var(--drop); flex: none; display: inline-block; }}

.legend {{ display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--ink-2); margin-bottom: 12px; }}
.legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
.key-line {{ width: 16px; height: 2px; background: var(--series); border-radius: 1px; }}
.key-median {{ width: 16px; height: 1px; background: var(--ink-2); }}
.key-band {{ width: 14px; height: 10px; background: var(--band); border-top: 1px solid var(--axis); }}
.key-eval {{ width: 14px; height: 10px; background: var(--eval); border: 1px solid var(--border); }}
.multiples {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 12px; }}
.chart {{ position: relative; min-height: 210px; }}
.chart svg {{ display: block; overflow: visible; }}
.grid {{ stroke: var(--grid); stroke-width: 1; }}
.axis {{ stroke: var(--axis); stroke-width: 1; }}
.tick {{ fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }}
.evalwash {{ fill: var(--eval); }}
.band {{ fill: var(--band); }}
.median {{ fill: none; stroke: var(--ink-2); stroke-width: 1; }}
.cost {{ fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }}
.mk {{ stroke: var(--surface); stroke-width: 2; }}
.mk.spike {{ fill: var(--spike); }} .mk.new {{ fill: var(--new); }} .mk.drop {{ fill: var(--drop); }}
.cross {{ stroke: var(--muted); stroke-width: 1; }}
.tip {{ position: absolute; pointer-events: none; z-index: 2; min-width: 170px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 12px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.14); display: none; }}
.tip .d {{ color: var(--ink-2); margin-bottom: 4px; }}
.tip .row {{ display: flex; align-items: center; gap: 8px; }}
.tip .row b {{ font-variant-numeric: tabular-nums; min-width: 72px; color: var(--ink); }}
.tip .row span {{ color: var(--ink-2); }}
.tip .k {{ width: 12px; height: 2px; flex: none; }}

.bars {{ display: grid; grid-template-columns: minmax(120px, 34%) 1fr; gap: 8px 12px; align-items: center; }}
.bars .name {{ font-size: 13px; color: var(--ink-2); overflow-wrap: anywhere; }}
.bars .track {{ display: flex; align-items: center; gap: 8px; }}
.bars .bar {{ height: 18px; background: var(--series); border-radius: 0 4px 4px 0; min-width: 2px; }}
.bars .val {{ font-size: 13px; font-variant-numeric: tabular-nums; white-space: nowrap; }}

.filters {{ display: flex; flex-wrap: wrap; align-items: end; gap: 10px 16px; margin: 0 0 12px; font-size: 13px; }}
.filters fieldset {{ border: 0; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; }}
.filters legend {{ color: var(--ink-2); padding: 0; margin-bottom: 4px; float: left; width: 100%; }}
.filters label {{ display: inline-flex; align-items: center; gap: 6px; color: var(--ink); }}
.filters .field {{ flex-direction: column; align-items: stretch; gap: 4px; color: var(--ink-2); }}
.filters select {{ font: inherit; color: var(--ink); background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; padding: 4px 6px; max-width: 260px; }}
.filters input {{ accent-color: var(--series); margin: 0; }}
.filters .count {{ margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; }}
.is-hidden {{ display: none; }}

.table-wrap {{ overflow-x: auto; padding: 4px 8px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }}
tbody tr:last-child td {{ border-bottom: 0; }}
th {{ color: var(--ink-2); font-weight: 600; white-space: nowrap; }}
th.num {{ text-align: right; }}
th button {{ font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px; }}
th button::after {{ content: "↕"; color: var(--axis); font-size: 11px; }}
th[aria-sort="ascending"] button::after {{ content: "↑"; color: var(--ink); }}
th[aria-sort="descending"] button::after {{ content: "↓"; color: var(--ink); }}
html:not(.js) th button::after {{ content: none; }}
.print-label, .why-row {{ display: none; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
td.why {{ min-width: 320px; color: var(--ink-2); }}
td.date, td code {{ white-space: nowrap; }}
td.svc {{ min-width: 150px; overflow-wrap: anywhere; }}
td.svc, td.num.strong {{ font-weight: 600; }}
.no-match td {{ color: var(--muted); text-align: center; padding: 20px; }}
.linkish {{ font: inherit; color: var(--series); background: none; border: 0; padding: 0; cursor: pointer; text-decoration: underline; }}
ol.formula {{ padding-left: 20px; margin: 0 0 8px; }} ol.formula li {{ margin: 4px 0; }}
.empty {{ color: var(--muted); }}
@media (max-width: 760px) {{ .runmeta div {{ display: grid; grid-template-columns: 7.5em 1fr; }} }}
@media (max-width: 760px) {{ :root {{ --topbar-h: 96px; }} .brand {{ font-size: 14px; }} .btn .txt {{ display: none; }} }}

@page {{ size: A4 portrait; margin: 14mm 12mm; }}
@media print {{
  :root, :root[data-theme="dark"], :root:not([data-theme="light"]) {{ color-scheme: light;{LIGHT}
    --page: #ffffff;
  }}
  body {{ font-size: 11.5px; background: #ffffff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .topbar, .js-only, .tip, .cross {{ display: none !important; }}
  main {{ max-width: none; padding: 0; }}
  h2 {{ margin-top: 22px; }}
  .verdict {{ font-size: 24px; max-width: none; }}
  .stats, .stat, .chart-card, tr, li, .bars > * {{ break-inside: avoid; }}
  h2, .section-lede, .legend {{ break-after: avoid; }}
  td:first-child code {{ white-space: normal; }}  /* long per-service parameter names wrap at spaces */
  .multiples {{ grid-template-columns: 1fr; }}
  .chart svg {{ max-width: 100%; height: auto; }}
  .table-wrap {{ overflow: visible; padding: 0; border: 0; }}
  thead {{ display: table-header-group; }}
  tr.is-hidden {{ display: table-row !important; }}
  /* Chrome drops <button> text in repeated table headers, so print a plain label instead. */
  th button {{ display: none; }}
  th .print-label {{ display: inline; }}
  /* On paper the explanation gets its own full-width line under the numbers. */
  #anomaly-rows td.why, th.why {{ display: none; }}
  tr.why-row {{ display: table-row; }}
  tr.why-row td {{ padding-top: 0; color: var(--ink-2); }}
  tr.arow {{ break-after: avoid; }}
  tr.arow td {{ border-bottom: 0; }}
  table, code {{ font-size: 10.5px; }}
  th, td {{ padding: 6px 5px; }}
  td.why {{ min-width: 0; }}
  td.svc {{ min-width: 0; overflow-wrap: break-word; }}
  .badge {{ font-size: 10px; }}
  p, li {{ max-width: none; }}
}}
"""

JS = r"""
(() => {
  const DATA = JSON.parse(document.getElementById('report-data').textContent);
  const root = document.documentElement;
  const NS = 'http://www.w3.org/2000/svg';
  const usd = v => (v < 0 ? '-$' : '$') + Math.abs(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const ddmm = s => s.slice(8, 10) + '/' + s.slice(5, 7);
  const compact = v => v >= 1000 ? (v / 1000).toFixed(v >= 10000 ? 0 : 1).replace(/\.0$/, '') + 'K' : String(+v.toFixed(2));
  const niceMax = v => {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  };
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    parent.appendChild(e);
    return e;
  };
  const div = (cls, parent, text) => {
    const e = document.createElement('div');
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    parent.appendChild(e);
    return e;
  };
  const tipRow = (tip, color, value, label) => {
    const r = div('row', tip);
    const k = div('k', r); k.style.background = color;
    const b = document.createElement('b'); b.textContent = value; r.appendChild(b);
    const s = document.createElement('span'); s.textContent = label; r.appendChild(s);
  };
  const css = name => getComputedStyle(root).getPropertyValue(name);

  function lineChart(box, svc) {
    box.textContent = '';
    const W = Math.max(box.clientWidth, 280), H = 210, m = {l: 52, r: 12, t: 22, b: 26};
    const pts = svc.points, n = pts.length;
    const yMax = niceMax(1.05 * Math.max(...pts.map(p => Math.max(p.c, p.t ?? 0, p.m ?? 0))));
    const step = (W - m.l - m.r) / Math.max(n - 1, 1);
    const x = i => m.l + i * step, y = v => m.t + (H - m.t - m.b) * (1 - v / yMax);
    const svg = el('svg', {width: W, height: H, viewBox: `0 0 ${W} ${H}`, tabindex: 0, role: 'img'}, box);
    svg.setAttribute('aria-label', `Chi phí theo ngày của ${svc.name}`);

    for (let i = 0; i <= 4; i++) {
      const v = yMax * i / 4;
      el('line', {x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: i ? 'grid' : 'axis'}, svg);
      el('text', {x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end', class: 'tick'}, svg).textContent = '$' + compact(v);
    }
    const i0 = pts.findIndex(p => p.d === DATA.evalStart), i1 = pts.findIndex(p => p.d === DATA.evalEnd);
    if (i0 >= 0 && i1 >= 0) {
      el('rect', {x: x(i0) - step / 2, y: m.t, width: x(i1) - x(i0) + step, height: H - m.t - m.b, class: 'evalwash'}, svg);
      el('text', {x: x(i1) + step / 2, y: m.t - 8, 'text-anchor': 'end', class: 'tick'}, svg).textContent = 'Khung đánh giá';
    }
    const scored = pts.map((p, i) => [p, i]).filter(([p]) => p.m !== null);
    if (scored.length) {
      const top = scored.map(([p, i]) => `${x(i)},${y(Math.max(p.t, p.m))}`);
      const bottom = scored.slice().reverse().map(([p, i]) => `${x(i)},${y(p.m)}`);
      el('polygon', {points: top.concat(bottom).join(' '), class: 'band'}, svg);
      el('polyline', {points: scored.map(([p, i]) => `${x(i)},${y(p.m)}`).join(' '), class: 'median'}, svg);
    }
    el('polyline', {points: pts.map((p, i) => `${x(i)},${y(p.c)}`).join(' '), class: 'cost'}, svg);

    const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((W - m.l - m.r) / 70))));
    for (let i = 0; i < n; i += every) {
      el('text', {x: x(i), y: H - 8, 'text-anchor': 'middle', class: 'tick'}, svg).textContent = ddmm(pts[i].d);
    }

    const kinds = {};
    for (const a of svc.anomalies) {
      kinds[a.d] = a.kind;
      const i = pts.findIndex(p => p.d === a.d);
      if (i < 0) continue;
      const cx = x(i), cy = y(pts[i].c);
      if (a.kind === 'SPIKE') el('circle', {cx, cy, r: 5, class: 'mk spike'}, svg);
      else if (a.kind === 'DROP') el('path', {d: `M${cx - 6},${cy - 5}L${cx + 6},${cy - 5}L${cx},${cy + 6}Z`, class: 'mk drop'}, svg);
      else el('path', {d: `M${cx},${cy - 6.5}L${cx + 6.5},${cy}L${cx},${cy + 6.5}L${cx - 6.5},${cy}Z`, class: 'mk new'}, svg);
    }

    const cross = el('line', {y1: m.t, y2: H - m.b, class: 'cross', visibility: 'hidden'}, svg);
    const hit = el('rect', {x: m.l - step / 2, y: 0, width: W - m.l - m.r + step, height: H, fill: 'transparent'}, svg);
    const tip = div('tip', box);
    let cur = i1 >= 0 ? i1 : n - 1;

    const show = i => {
      cur = Math.min(n - 1, Math.max(0, i));
      const p = pts[cur];
      cross.setAttribute('x1', x(cur)); cross.setAttribute('x2', x(cur)); cross.setAttribute('visibility', 'visible');
      tip.textContent = '';
      div('d', tip, p.d);
      tipRow(tip, css('--series'), usd(p.c), 'Chi phí');
      if (p.m !== null) {
        tipRow(tip, css('--ink-2'), usd(p.m), 'Median 30 ngày trước');
        tipRow(tip, css('--axis'), usd(Math.max(p.t, p.m)), 'Ngưỡng cảnh báo');
      }
      const kind = kinds[p.d];
      if (kind) tipRow(tip, css({SPIKE: '--spike', DROP: '--drop'}[kind] || '--new'), kind, 'bất thường');
      tip.style.display = 'block';
      const left = x(cur) + 12 + tip.offsetWidth > W ? x(cur) - 12 - tip.offsetWidth : x(cur) + 12;
      tip.style.left = left + 'px';
      tip.style.top = '8px';
    };
    const hide = () => { cross.setAttribute('visibility', 'hidden'); tip.style.display = 'none'; };
    hit.addEventListener('pointermove', e => {
      const r = svg.getBoundingClientRect();
      show(Math.round((e.clientX - r.left - m.l) / step));
    });
    hit.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', () => show(cur));
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        show(cur + (e.key === 'ArrowRight' ? 1 : -1));
      }
    });
  }

  const render = () => document.querySelectorAll('.chart').forEach(box => lineChart(box, DATA.services[+box.dataset.index]));
  render();
  let t;
  window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(render, 150); });

  // Theme: an explicit choice wins over the OS setting and is remembered when storage is available.
  const osDark = matchMedia('(prefers-color-scheme: dark)');
  const isDark = () => root.dataset.theme ? root.dataset.theme === 'dark' : osDark.matches;
  const toggle = document.getElementById('theme-toggle');
  const sync = () => toggle.setAttribute('aria-pressed', String(isDark()));
  toggle.addEventListener('click', () => {
    const next = isDark() ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('cost-anomaly-theme', next); } catch (e) {}
    sync();
    render();
  });
  osDark.addEventListener('change', () => { if (!root.dataset.theme) { sync(); render(); } });
  sync();
  document.getElementById('print-btn').addEventListener('click', () => window.print());

  // Anomaly table: filters combine with AND; sorting never changes what gets printed.
  const tbody = document.getElementById('anomaly-rows');
  const filters = document.getElementById('filters');
  if (!tbody || !filters) return;
  const rows = [...tbody.querySelectorAll('tr.arow')];
  const noMatch = tbody.querySelector('tr.no-match');
  const count = document.getElementById('row-count');
  const kindBoxes = [...filters.querySelectorAll('input[name="kind"]')];
  const selects = [...filters.querySelectorAll('select')];
  const pick = id => document.getElementById(id);
  const service = pick('f-service'), provisional = pick('f-provisional'), known = pick('f-known');
  const flagOk = (sel, v) => !sel || !sel.value || (sel.value === 'only' ? v === '1' : v !== '1');

  const apply = () => {
    const kinds = new Set(kindBoxes.filter(b => b.checked).map(b => b.value));
    let shown = 0;
    for (const r of rows) {
      const d = r.dataset;
      const ok = kinds.has(d.kind) && (!service.value || d.service === service.value)
        && flagOk(provisional, d.provisional) && flagOk(known, d.known);
      r.classList.toggle('is-hidden', !ok);
      shown += ok;
    }
    noMatch.hidden = shown > 0;
    count.textContent = `${shown} / ${rows.length} dòng`;
  };

  const NUMERIC = new Set(['cost', 'median', 'z', 'delta', 'impact']);
  const heads = [...document.querySelectorAll('th[data-sort]')];
  let sortKey = null, sortDir = 1;
  const why = new Map(rows.map(r => [r, r.nextElementSibling]));  // print-only explanation row
  const place = list => { for (const r of list) { tbody.insertBefore(r, noMatch); tbody.insertBefore(why.get(r), noMatch); } };
  const ordered = () => {
    if (!sortKey) return rows;
    return rows.slice().sort((a, b) => {
      const x = a.dataset[sortKey], y = b.dataset[sortKey];
      let c;
      if (NUMERIC.has(sortKey) && (x === '' || y === '')) c = (x === '') - (y === '');  // blank z stays last
      else c = sortDir * (NUMERIC.has(sortKey) ? x - y : x.localeCompare(y, 'vi'));
      return c || a.dataset.idx - b.dataset.idx;
    });
  };
  const sortBy = key => {
    if (sortKey === key) sortDir = -sortDir;
    else { sortKey = key; sortDir = key === 'service' || key === 'kind' ? 1 : -1; }
    for (const h of heads) {
      h.setAttribute('aria-sort', h.dataset.sort !== sortKey ? 'none' : sortDir > 0 ? 'ascending' : 'descending');
    }
    place(ordered());
  };
  const clear = () => {
    kindBoxes.forEach(b => { b.checked = true; });
    selects.forEach(s => { s.value = ''; });
    sortKey = null;
    heads.forEach(h => h.setAttribute('aria-sort', 'none'));
    place(rows);
    apply();
  };

  heads.forEach(h => h.querySelector('button').addEventListener('click', () => sortBy(h.dataset.sort)));
  kindBoxes.forEach(b => b.addEventListener('change', apply));
  selects.forEach(s => s.addEventListener('change', apply));
  document.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', clear));
  window.addEventListener('beforeprint', () => place(rows));
  window.addEventListener('afterprint', () => place(ordered()));
})();
"""


def attr(value: object) -> str:
    return escape(str(value), quote=True)


def num(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}".rstrip("0").rstrip(".")


def badge(kind: str, count: int | None = None) -> str:
    text = KIND_LABEL[kind] if count is None else f"<b>{count}</b> {KIND_LABEL[kind]}"
    return f'<span class="badge {KIND_CLASS[kind]}">{KIND_MARK[kind]}{text}</span>'


def tags(labels: list[str]) -> str:
    return "".join(f'<span class="tag">{escape(label)}</span>' for label in labels)


def stat(label: str, value: str, sub: str = "", cls: str = "") -> str:
    sub_html = f'<span class="sub">{escape(sub)}</span>' if sub else ""
    return (
        f'<div class="stat{" " + cls if cls else ""}"><span class="label">{escape(label)}</span>'
        f'<span class="value">{escape(value)}</span>{sub_html}</div>'
    )


def chart_data(report: Report) -> str:
    services = []
    for r in report.rollups:
        services.append(
            {
                "name": r.service,
                "points": [
                    {
                        "d": p.day.isoformat(),
                        "c": round(p.cost, 4),
                        "m": None if p.median is None else round(p.median, 4),
                        "t": None if p.threshold is None else round(p.threshold, 4),
                    }
                    for p in report.charts[r.service]
                ],
                "anomalies": [{"d": a.date.isoformat(), "kind": a.kind} for a in r.anomalies],
            }
        )
    data = {
        "evalStart": report.windows.eval_days[0].isoformat(),
        "evalEnd": report.windows.eval_days[-1].isoformat(),
        "services": services,
    }
    # "</" would end the <script> element early; service names are untrusted input.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def verdict(report: Report) -> tuple[str, str]:
    """The headline sentence and its severity class (alert / drop / calm)."""
    rows = len(report.rows)
    if not rows:
        return f"Không có chi phí bất thường trong {len(report.windows.eval_days)} ngày được đánh giá.", "calm"
    text = f"{rows} bất thường ở {len(report.rollups)} service"
    if report.excess > 0:
        text += f", chi thêm {usd(report.excess)} so với mức bình thường"
    elif report.drop_count:
        text += ": chi phí rơi về gần 0"
    return text + ".", "alert" if report.spike_count + report.new_count else "drop"


def section_overview(report: Report) -> str:
    w = report.windows
    headline, severity = verdict(report)
    counts = [(SPIKE, report.spike_count), (NEW_SERVICE, report.new_count), (DROP, report.drop_count)]
    kinds = "".join(badge(kind, n) for kind, n in counts if n)
    kind_cell = (
        f'<div class="stat"><span class="label">Theo loại</span><span class="kindcounts">{kinds}</span></div>'
        if kinds
        else stat("Theo loại", "0", "không có bất thường")
    )
    meta = [
        ("Profile", f"<code>{escape(report.profile)}</code>"),
        ("Dữ liệu", f"{w.fetch_start.isoformat()} → {w.fetch_end.isoformat()} (không gồm ngày cuối)"),
        ("Khung đánh giá", f"{w.eval_days[0].isoformat()} → {w.eval_days[-1].isoformat()}"),
        ("Tạo lúc", report.generated_at.strftime("%Y-%m-%d %H:%M UTC")),
    ]
    dl = "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in meta)
    stats = "".join(
        [
            stat("Vượt mức bình thường", usd(report.excess), "tổng delta của các ngày bất thường", "excess"),
            stat("Chi phí khung đánh giá", usd(report.eval_spend), f"{len(w.eval_days)} ngày, mọi service"),
            stat("Service bị ảnh hưởng", str(len(report.rollups))),
            kind_cell,
        ]
    )
    return (
        "<h1>Báo cáo chi phí AWS bất thường</h1>"
        f'<p class="verdict {severity}">{escape(headline)}</p>'
        f'<dl class="runmeta">{dl}</dl>'
        f'<div class="stats">{stats}</div>'
    )


def section_insights(report: Report) -> str:
    items = "".join(f"<li>{escape(i)}</li>" for i in report.insights)
    return f'<h2>Nhận định chính</h2><div class="card"><ul class="points">{items}</ul></div>'


def section_steps(report: Report) -> str:
    if not report.next_steps:
        return ""
    items = "".join(f"<li>{escape(s)}</li>" for s in report.next_steps)
    return f'<h2>Bước tiếp theo</h2><div class="card"><ul class="points">{items}</ul></div>'


def section_charts(report: Report) -> str:
    if not report.rollups:
        return ""
    cards = "".join(
        f'<div class="card chart-card"><h3>{escape(r.service)}</h3><div class="chart" data-index="{i}"></div></div>'
        for i, r in enumerate(report.rollups)
    )
    legend = (
        '<div class="legend">'
        '<span><i class="key-line"></i>Chi phí/ngày</span>'
        '<span><i class="key-median"></i>Median 30 ngày trước</span>'
        '<span><i class="key-band"></i>Vùng bình thường (từ median tới ngưỡng cảnh báo)</span>'
        '<span><i class="dot"></i>SPIKE</span>'
        '<span><i class="diamond"></i>NEW_SERVICE</span>'
        '<span><i class="tri"></i>DROP</span>'
        '<span><i class="key-eval"></i>Khung đánh giá</span>'
        "</div>"
    )
    hint = (
        f'<p class="section-lede">Toàn bộ {len(report.charts[report.rollups[0].service])} ngày dữ liệu. Median và ngưỡng chỉ có từ ngày thứ '
        f"{report.settings.baseline_days + 1}, khi đã đủ baseline. Rê chuột (hoặc focus rồi dùng phím ←/→) để xem số liệu từng ngày.</p>"
    )
    return f'<h2>Diễn biến chi phí của các service bất thường</h2>{hint}{legend}<div class="multiples">{cards}</div>'


def section_bars(report: Report) -> str:
    positive = [r for r in report.rollups if r.excess > 0]
    if not positive:
        return ""
    top = max(r.excess for r in positive)
    rows = "".join(
        f'<div class="name">{escape(r.service)}</div>'
        f'<div class="track"><div class="bar" style="width:{max(r.excess / top * 82, 0.5):.2f}%"></div>'
        f'<span class="val">{escape(usd(r.excess))}, {len(r.days)} ngày</span></div>'
        for r in positive
    )
    return (
        "<h2>Phần vượt mức bình thường theo service</h2>"
        '<p class="section-lede">Tổng delta (chi phí − median) của các ngày bất thường, tức số tiền chi thêm so với mức thường ngày.</p>'
        f'<div class="card"><div class="bars">{rows}</div></div>'
    )


def table_row(i: int, r: AnomalyRow) -> str:
    a = r.anomaly
    keys = {
        "idx": i,
        "date": a.date.isoformat(),
        "service": a.service,
        "kind": a.kind,
        "cost": num(a.cost),
        "median": num(a.baseline_median),
        "z": num(a.robust_z),
        "delta": num(a.delta),
        "impact": num(a.month_impact),
        "provisional": int(a.provisional),
        "known": int(a.known),
    }
    data = "".join(f' data-{k}="{attr(v)}"' for k, v in keys.items())
    return (
        f'<tr class="arow"{data}>'
        f'<td class="date">{a.date.isoformat()}</td>'
        f'<td class="svc">{escape(a.service)}</td>'
        f"<td>{badge(a.kind)}<br>{tags(r.labels)}</td>"
        f'<td class="num">{escape(usd(a.cost))}</td>'
        f'<td class="num">{escape(usd(a.baseline_median))}</td>'
        f'<td class="num">{escape(usd(a.mad))}</td>'
        f'<td class="num">{"—" if a.robust_z is None else f"{a.robust_z:.2f}"}</td>'
        f'<td class="num strong">{escape(usd(a.delta))}</td>'
        f'<td class="num">{escape(usd(a.month_impact))}</td>'
        f"<td>{escape(r.severity)}</td>"
        f'<td class="why">{escape(r.explanation)}</td>'
        "</tr>"
        f'<tr class="why-row" aria-hidden="true"><td></td><td colspan="9">{escape(r.explanation)}</td></tr>'
    )


def label_select(ident: str, title: str, label: str) -> str:
    return (
        f'<label class="field">{title}<select id="{ident}"><option value="">Tất cả</option>'
        f'<option value="only">Chỉ {label}</option><option value="hide">Ẩn {label}</option></select></label>'
    )


def table_filters(report: Report) -> str:
    present = {r.anomaly.kind for r in report.rows}
    kinds = "".join(
        f'<label><input type="checkbox" name="kind" value="{kind}" checked>{KIND_MARK[kind]}{KIND_LABEL[kind]}</label>'
        for kind in (SPIKE, NEW_SERVICE, DROP)
        if kind in present
    )
    services = "".join(
        f'<option value="{attr(s)}">{escape(s)}</option>' for s in sorted({r.anomaly.service for r in report.rows})
    )
    labels = ""
    if any(r.anomaly.provisional for r in report.rows):
        labels += label_select("f-provisional", "Tạm tính", PROVISIONAL_LABEL)
    if any(r.anomaly.known for r in report.rows):
        labels += label_select("f-known", "Đã biết", KNOWN_LABEL)
    n = len(report.rows)
    return (
        '<div id="filters" class="filters js-only">'
        f"<fieldset><legend>Loại</legend>{kinds}</fieldset>"
        f'<label class="field">Service<select id="f-service"><option value="">Tất cả service</option>{services}</select></label>'
        f"{labels}"
        '<button type="button" class="btn" data-clear>Xóa lọc</button>'
        f'<span id="row-count" class="count" aria-live="polite">{n} / {n} dòng</span>'
        "</div>"
    )


def section_table(report: Report) -> str:
    if not report.rows:
        return '<h2>Bảng bất thường</h2><p class="empty">Không có bất thường nào.</p>'
    sortable = [
        ("date", "Ngày", ""), ("service", "Service", ""), ("kind", "Loại", ""), ("cost", "Chi phí", "num"),
        ("median", "Median", "num"),
    ]
    after_mad = [("z", "z", "num"), ("delta", "Delta", "num"), ("impact", "Tác động tháng", "num")]

    def head(key: str, label: str, cls: str) -> str:
        c = f' class="{cls}"' if cls else ""
        return (
            f'<th data-sort="{key}" aria-sort="none"{c}><button type="button">{label}</button>'
            f'<span class="print-label" aria-hidden="true">{label}</span></th>'
        )

    heads = (
        "".join(head(*h) for h in sortable)
        + '<th class="num">MAD</th>'
        + "".join(head(*h) for h in after_mad)
        + '<th>Mức</th><th class="why">Giải thích</th>'
    )
    body = "".join(table_row(i, r) for i, r in enumerate(report.rows))
    no_match = (
        '<tr class="no-match" hidden><td colspan="11">Không có dòng nào khớp bộ lọc. '
        '<button type="button" class="linkish" data-clear>Xóa lọc</button></td></tr>'
    )
    return (
        "<h2>Bảng bất thường</h2>"
        f'<p class="section-lede">Cùng nội dung với file CSV, kèm giải thích từng dòng. Mức độ của SPIKE: vừa (z &lt; {2 * report.settings.k:g}), '
        f'mạnh (z &lt; {4 * report.settings.k:g}), rất mạnh (z ≥ {4 * report.settings.k:g}).<span class="js-only"> Bấm tiêu đề cột để sắp xếp.</span></p>'
        f"{table_filters(report)}"
        f'<div class="card table-wrap"><table><thead><tr>{heads}</tr></thead>'
        f'<tbody id="anomaly-rows">{body}{no_match}</tbody></table></div>'
    )


def section_near_misses(report: Report) -> str:
    if not report.near_misses:
        return ""
    body = "".join(
        "<tr>"
        f'<td class="date">{m.date.isoformat()}</td><td class="svc">{escape(m.service)}</td>'
        f'<td class="num">{escape(usd(m.score.cost))}</td>'
        f'<td class="num">{escape(usd(m.score.baseline_median))}</td>'
        f'<td class="num">{escape(usd(m.score.delta))}</td>'
        f'<td class="why">{escape(m.reason)}</td>'
        "</tr>"
        for m in report.near_misses
    )
    return (
        "<h2>Biến động bị lọc</h2>"
        '<p class="section-lede">Những ngày có dấu hiệu tăng nhưng không đủ điều kiện để báo. Mục này giúp hiểu các ngưỡng đang lọc gì và có nên chỉnh không.</p>'
        '<div class="card table-wrap"><table><thead><tr>'
        '<th>Ngày</th><th>Service</th><th class="num">Chi phí</th><th class="num">Median</th><th class="num">Delta</th><th>Lý do không báo</th>'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def section_cad(report: Report) -> str:
    if report.cad_error:
        return (
            "<h2>Đối chiếu AWS CAD</h2>"
            f'<div class="card"><p>Lần chạy này không lấy được anomaly của AWS Cost Anomaly Detection: {escape(report.cad_error)}</p></div>'
        )
    if report.cad is None:
        return ""
    rows = "".join(
        "<tr>"
        f'<td class="date">{c.start.isoformat()} → {c.end.isoformat() if c.end else "đang diễn ra"}</td>'
        f'<td class="svc">{escape(", ".join(sorted(c.services)))}</td>'
        f'<td class="num">{escape(usd(c.total_impact))}</td><td class="num">{c.max_score:.2f}</td>'
        "</tr>"
        for c in report.cad_only
    )
    table = (
        '<div class="card table-wrap"><table><thead><tr><th>Thời gian</th><th>Service</th><th class="num">Tổng tác động</th>'
        f'<th class="num">Điểm</th></tr></thead><tbody>{rows}</tbody></table></div>'
        if rows
        else ""
    )
    return (
        "<h2>Đối chiếu AWS CAD</h2>"
        f'<p class="section-lede">Cả hai cùng phát hiện: {report.cad_both} dòng. Chỉ tool: {report.cad_tool_only} dòng. '
        f"Chỉ AWS CAD: {len(report.cad_only)} anomaly. CAD dùng mô hình ML của AWS (hộp đen); tool không xem được cách CAD tính, "
        "nên các anomaly chỉ CAD thấy là gợi ý để xem thêm.</p>"
        f"{table}"
    )


def section_config(report: Report) -> str:
    params = "".join(
        f"<tr><td><code>{escape(p.name)}</code></td><td>{f'<code>{escape(p.flag)}</code>' if p.flag else '—'}</td>"
        f'<td class="num">{escape(p.value)}</td><td class="why">{escape(p.meaning)}</td></tr>'
        for p in report.params
    )
    formula = "".join(f"<li>{escape(f)}</li>" for f in FORMULA)
    columns = "".join(f"<tr><td><code>{escape(c)}</code></td><td class=\"why\">{escape(d)}</td></tr>" for c, d in COLUMNS)
    return (
        "<h2>Cấu hình thuật toán</h2>"
        '<div class="card table-wrap"><table><thead><tr><th>Tham số</th><th>Cờ CLI</th><th class="num">Giá trị</th><th>Ý nghĩa</th></tr></thead>'
        f"<tbody>{params}</tbody></table></div>"
        "<h2>Cách tính</h2>"
        f'<div class="card"><ol class="formula">{formula}</ol><p>{escape(WHY_ROBUST)}</p></div>'
        "<h2>Giải thích các cột</h2>"
        f'<div class="card table-wrap"><table><thead><tr><th>Cột</th><th>Ý nghĩa</th></tr></thead><tbody>{columns}</tbody></table></div>'
    )


# (id, table-of-contents label, renderer); a section is listed only when it renders something.
SECTIONS = [
    ("tong-quan", "Tổng quan", section_overview),
    ("nhan-dinh", "Nhận định", section_insights),
    ("buoc-tiep-theo", "Bước tiếp theo", section_steps),
    ("bieu-do", "Biểu đồ", section_charts),
    ("vuot-muc", "Vượt mức", section_bars),
    ("bang", "Bảng bất thường", section_table),
    ("bi-loc", "Biến động bị lọc", section_near_misses),
    ("cad", "AWS CAD", section_cad),
    ("cau-hinh", "Cấu hình và cách tính", section_config),
]


def render_html(report: Report) -> str:
    rendered = [(ident, label, render(report)) for ident, label, render in SECTIONS]
    rendered = [s for s in rendered if s[2]]
    nav = "".join(f'<a href="#{ident}">{label}</a>' for ident, label, _ in rendered)
    sections = "\n".join(f'<section id="{ident}">{content}</section>' for ident, _, content in rendered)
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Báo cáo chi phí bất thường</title>
<script>{HEAD_JS}</script>
<style>{CSS}</style>
</head>
<body>
<header class="topbar"><div class="topbar-in">
<a class="brand" href="#tong-quan">Báo cáo chi phí AWS bất thường</a>
<div class="actions js-only">
<button type="button" id="theme-toggle" class="btn" aria-pressed="false" aria-label="Giao diện tối" title="Đổi giao diện sáng/tối"><span class="switch" aria-hidden="true"></span><span class="txt">Giao diện tối</span></button>
<button type="button" id="print-btn" class="btn primary">Xuất PDF</button>
</div>
<nav class="toc" aria-label="Mục lục">{nav}</nav>
</div></header>
<main>
{sections}
</main>
<script id="report-data" type="application/json">{chart_data(report)}</script>
<script>{JS}</script>
</body>
</html>
"""


def write_html(report: Report, path: Path) -> None:
    path.write_text(render_html(report), encoding="utf-8")
