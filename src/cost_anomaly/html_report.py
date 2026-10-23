"""Self-contained HTML report (inline CSS/JS, no network) for one detection run."""

import json
from html import escape
from pathlib import Path

from .analysis import COLUMNS, FORMULA, WHY_ROBUST, Report, usd
from .detect import DROP, NEW_SERVICE, SPIKE

KIND_LABEL = {SPIKE: "SPIKE", NEW_SERVICE: "NEW_SERVICE", DROP: "DROP"}

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --series: #2a78d6; --band: rgba(42,120,214,0.10); --eval: rgba(11,11,11,0.04);
  --spike: #d03b3b; --new: #ec835a; --drop: #7b4fc9;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series: #3987e5; --band: rgba(57,135,229,0.14); --eval: rgba(255,255,255,0.05);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --series: #3987e5; --band: rgba(57,135,229,0.14); --eval: rgba(255,255,255,0.05);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; font-weight: 650; }
h2 { font-size: 18px; margin: 40px 0 12px; font-weight: 650; }
h3 { font-size: 15px; margin: 0 0 8px; font-weight: 600; }
p, li { color: var(--ink-2); }
.meta { color: var(--muted); margin: 0; font-size: 14px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 24px; }
.tile .label { color: var(--ink-2); font-size: 13px; }
.tile .value { font-size: 28px; font-weight: 600; margin-top: 2px; }
.tile .sub { color: var(--muted); font-size: 13px; }
ul.insights { margin: 0; padding-left: 20px; }
ul.insights li { margin: 6px 0; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--ink-2); margin-bottom: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.key-line { width: 16px; height: 2px; background: var(--series); border-radius: 1px; }
.key-median { width: 16px; height: 1px; background: var(--ink-2); }
.key-band { width: 14px; height: 10px; background: var(--band); border-top: 1px solid var(--axis); }
.key-eval { width: 14px; height: 10px; background: var(--eval); border: 1px solid var(--border); }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--spike); flex: none; }
.diamond { width: 8px; height: 8px; background: var(--new); transform: rotate(45deg); flex: none; }
.tri { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
  border-top: 9px solid var(--drop); flex: none; }
.multiples { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 12px; }
.chart { position: relative; min-height: 210px; }
.chart svg { display: block; overflow: visible; }
.chart svg:focus { outline: 2px solid var(--series); outline-offset: 2px; border-radius: 4px; }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--axis); stroke-width: 1; }
.tick { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.evalwash { fill: var(--eval); }
.band { fill: var(--band); }
.median { fill: none; stroke: var(--ink-2); stroke-width: 1; }
.cost { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.mk { stroke: var(--surface); stroke-width: 2; }
.mk.spike { fill: var(--spike); } .mk.new { fill: var(--new); } .mk.drop { fill: var(--drop); }
.cross { stroke: var(--muted); stroke-width: 1; }
.tip { position: absolute; pointer-events: none; z-index: 2; min-width: 170px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12); display: none; }
.tip .d { color: var(--ink-2); margin-bottom: 4px; }
.tip .row { display: flex; align-items: center; gap: 8px; }
.tip .row b { font-variant-numeric: tabular-nums; min-width: 72px; color: var(--ink); }
.tip .row span { color: var(--ink-2); }
.tip .k { width: 12px; height: 2px; flex: none; }
.bars { display: grid; grid-template-columns: minmax(120px, 34%) 1fr; gap: 8px 12px; align-items: center; }
.bars .name { font-size: 13px; color: var(--ink-2); overflow-wrap: anywhere; }
.bars .track { display: flex; align-items: center; gap: 8px; }
.bars .bar { height: 18px; background: var(--series); border-radius: 0 4px 4px 0; min-width: 2px; }
.bars .val { font-size: 13px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; white-space: nowrap; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.why { min-width: 320px; color: var(--ink-2); }
td.date, td code { white-space: nowrap; }
td.svc { min-width: 150px; }
.tag { display: inline-block; margin-top: 4px; padding: 0 6px; border: 1px solid var(--border); border-radius: 4px;
  font-size: 12px; color: var(--ink-2); white-space: nowrap; }
.badge { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-weight: 600; }
code { font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; }
ol.formula { padding-left: 20px; } ol.formula li { margin: 4px 0; }
.empty { color: var(--muted); }
"""

JS = r"""
(() => {
  const DATA = JSON.parse(document.getElementById('report-data').textContent);
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
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name);

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
})();
"""


def badge(kind: str) -> str:
    mark = {SPIKE: '<span class="dot"></span>', DROP: '<span class="tri"></span>'}.get(kind, '<span class="diamond"></span>')
    return f'<span class="badge">{mark}{KIND_LABEL[kind]}</span>'


def tags(labels: list[str]) -> str:
    return "".join(f' <span class="tag">{escape(label)}</span>' for label in labels)


def tile(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="sub">{escape(sub)}</div>' if sub else ""
    return f'<div class="card tile"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div>{sub_html}</div>'


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


def section_charts(report: Report) -> str:
    if not report.rollups:
        return ""
    cards = "".join(
        f'<div class="card"><h3>{escape(r.service)}</h3><div class="chart" data-index="{i}"></div></div>'
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
        f"<p>Toàn bộ {len(report.charts[report.rollups[0].service])} ngày dữ liệu. Median và ngưỡng chỉ có từ ngày thứ "
        f"{report.settings.baseline_days + 1}, khi đã đủ baseline. Rê chuột (hoặc focus rồi dùng phím ←/→) để xem số liệu từng ngày.</p>"
    )
    return f"<h2>Diễn biến chi phí của các service bất thường</h2>{hint}{legend}<div class=\"multiples\">{cards}</div>"


def section_bars(report: Report) -> str:
    positive = [r for r in report.rollups if r.excess > 0]
    if not positive:
        return ""
    top = max(r.excess for r in positive)
    rows = "".join(
        f'<div class="name">{escape(r.service)}</div>'
        f'<div class="track"><div class="bar" style="width:{max(r.excess / top * 82, 0.5):.2f}%"></div>'
        f'<span class="val">{escape(usd(r.excess))} · {len(r.days)} ngày</span></div>'
        for r in positive
    )
    return (
        "<h2>Phần vượt mức bình thường theo service</h2>"
        "<p>Tổng delta (chi phí − median) của các ngày bất thường, tức số tiền chi thêm so với mức thường ngày.</p>"
        f'<div class="card"><div class="bars">{rows}</div></div>'
    )


def section_table(report: Report) -> str:
    if not report.rows:
        return '<h2>Bảng bất thường</h2><p class="empty">Không có bất thường nào.</p>'
    body = "".join(
        "<tr>"
        f'<td class="date">{r.anomaly.date.isoformat()}</td>'
        f'<td class="svc">{escape(r.anomaly.service)}</td>'
        f"<td>{badge(r.anomaly.kind)}{tags(r.labels)}</td>"
        f'<td class="num">{escape(usd(r.anomaly.cost))}</td>'
        f'<td class="num">{escape(usd(r.anomaly.baseline_median))}</td>'
        f'<td class="num">{escape(usd(r.anomaly.mad))}</td>'
        f'<td class="num">{"—" if r.anomaly.robust_z is None else f"{r.anomaly.robust_z:.2f}"}</td>'
        f'<td class="num">{escape(usd(r.anomaly.delta))}</td>'
        f'<td class="num">{escape(usd(r.anomaly.month_impact))}</td>'
        f"<td>{escape(r.severity)}</td>"
        f'<td class="why">{escape(r.explanation)}</td>'
        "</tr>"
        for r in report.rows
    )
    return (
        "<h2>Bảng bất thường</h2>"
        f"<p>Cùng nội dung với file CSV, kèm giải thích từng dòng. Mức độ của SPIKE: vừa (z &lt; {2 * report.settings.k:g}), "
        f"mạnh (z &lt; {4 * report.settings.k:g}), rất mạnh (z ≥ {4 * report.settings.k:g}).</p>"
        '<div class="card table-wrap"><table><thead><tr>'
        "<th>Ngày</th><th>Service</th><th>Loại</th><th>Chi phí</th><th>Median</th><th>MAD</th>"
        "<th>z</th><th>Delta</th><th>Tác động tháng</th><th>Mức</th><th>Giải thích</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
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
        "<p>Những ngày có dấu hiệu tăng nhưng không đủ điều kiện để báo. Mục này giúp hiểu các ngưỡng đang lọc gì và có nên chỉnh không.</p>"
        '<div class="card table-wrap"><table><thead><tr>'
        "<th>Ngày</th><th>Service</th><th>Chi phí</th><th>Median</th><th>Delta</th><th>Lý do không báo</th>"
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
        '<div class="card table-wrap"><table><thead><tr><th>Thời gian</th><th>Service</th><th>Tổng tác động</th>'
        f"<th>Điểm</th></tr></thead><tbody>{rows}</tbody></table></div>"
        if rows
        else ""
    )
    return (
        "<h2>Đối chiếu AWS CAD</h2>"
        f"<p>Cả hai cùng phát hiện: {report.cad_both} dòng · chỉ tool: {report.cad_tool_only} dòng · "
        f"chỉ AWS CAD: {len(report.cad_only)} anomaly. CAD dùng mô hình ML của AWS (hộp đen); tool không xem được cách CAD tính, "
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
        '<div class="card table-wrap"><table><thead><tr><th>Tham số</th><th>Cờ CLI</th><th>Giá trị</th><th>Ý nghĩa</th></tr></thead>'
        f"<tbody>{params}</tbody></table></div>"
        "<h2>Cách tính</h2>"
        f'<div class="card"><ol class="formula">{formula}</ol><p>{escape(WHY_ROBUST)}</p></div>'
        "<h2>Giải thích các cột</h2>"
        f'<div class="card table-wrap"><table><thead><tr><th>Cột</th><th>Ý nghĩa</th></tr></thead><tbody>{columns}</tbody></table></div>'
    )


def render_html(report: Report) -> str:
    w = report.windows
    affected = len(report.rollups)
    tiles = "".join(
        [
            tile("Bất thường", str(len(report.rows)), report.kind_summary.replace(", ", " · ")),
            tile("Phần vượt mức bình thường", usd(report.excess), "tổng delta của các ngày bất thường"),
            tile("Chi phí khung đánh giá", usd(report.eval_spend), f"{len(w.eval_days)} ngày, mọi service"),
            tile("Service bị ảnh hưởng", str(affected)),
        ]
    )
    insights = "".join(f"<li>{escape(i)}</li>" for i in report.insights)
    steps = (
        "<h2>Bước tiếp theo</h2><div class=\"card\"><ul class=\"insights\">"
        + "".join(f"<li>{escape(s)}</li>" for s in report.next_steps)
        + "</ul></div>"
        if report.next_steps
        else ""
    )
    meta = (
        f"Profile <code>{escape(report.profile)}</code> · Dữ liệu {w.fetch_start.isoformat()} → "
        f"{w.fetch_end.isoformat()} (không gồm ngày cuối) · Đánh giá {w.eval_days[0].isoformat()} → "
        f"{w.eval_days[-1].isoformat()} · Tạo lúc {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Báo cáo chi phí bất thường</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Báo cáo chi phí AWS bất thường</h1>
<p class="meta">{meta}</p>
<div class="tiles">{tiles}</div>
<h2>Nhận định chính</h2>
<div class="card"><ul class="insights">{insights}</ul></div>
{steps}
{section_charts(report)}
{section_bars(report)}
{section_table(report)}
{section_near_misses(report)}
{section_cad(report)}
{section_config(report)}
</main>
<script id="report-data" type="application/json">{chart_data(report)}</script>
<script>{JS}</script>
</body>
</html>
"""


def write_html(report: Report, path: Path) -> None:
    path.write_text(render_html(report), encoding="utf-8")
