"""Markdown version of the report: same content as the HTML minus the charts."""

from pathlib import Path

from .analysis import COLUMNS, FORMULA, WHY_ROBUST, Report, usd


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return lines + [""]


def render_markdown(report: Report) -> str:
    w = report.windows
    out = [
        "# Báo cáo chi phí AWS bất thường",
        "",
        f"- Profile: `{report.profile}`",
        f"- Dữ liệu: {w.fetch_start.isoformat()} → {w.fetch_end.isoformat()} (không gồm ngày cuối)",
        f"- Khung đánh giá: {w.eval_days[0].isoformat()} → {w.eval_days[-1].isoformat()}",
        f"- Tạo lúc: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Tổng quan",
        "",
        f"- Bất thường: **{len(report.rows)}** ({report.kind_summary}) ở {len(report.rollups)} service",
        f"- Phần vượt mức bình thường: **{usd(report.excess)}**",
        f"- Chi phí khung đánh giá: {usd(report.eval_spend)}",
        "",
        "## Nhận định chính",
        "",
        *[f"- {i}" for i in report.insights],
        "",
    ]
    if report.next_steps:
        out += ["## Bước tiếp theo", "", *[f"- {s}" for s in report.next_steps], ""]

    out += ["## Bảng bất thường", ""]
    if report.rows:
        out += table(
            ["Ngày", "Service", "Loại", "Chi phí", "Median", "MAD", "z", "Delta", "Tác động tháng", "Mức", "Giải thích"],
            [
                [
                    r.anomaly.date.isoformat(),
                    r.anomaly.service,
                    " · ".join([r.anomaly.kind, *r.labels]),
                    usd(r.anomaly.cost),
                    usd(r.anomaly.baseline_median),
                    usd(r.anomaly.mad),
                    "—" if r.anomaly.robust_z is None else f"{r.anomaly.robust_z:.2f}",
                    usd(r.anomaly.delta),
                    usd(r.anomaly.month_impact),
                    r.severity,
                    r.explanation,
                ]
                for r in report.rows
            ],
        )
    else:
        out += ["Không có bất thường nào.", ""]

    if report.near_misses:
        out += ["## Biến động bị lọc", "", "Những ngày có dấu hiệu tăng nhưng không đủ điều kiện để báo.", ""]
        out += table(
            ["Ngày", "Service", "Chi phí", "Median", "Delta", "Lý do không báo"],
            [
                [m.date.isoformat(), m.service, usd(m.score.cost), usd(m.score.baseline_median), usd(m.score.delta), m.reason]
                for m in report.near_misses
            ],
        )

    out += ["## Cấu hình thuật toán", ""]
    out += table(
        ["Tham số", "Cờ CLI", "Giá trị", "Ý nghĩa"],
        [[f"`{p.name}`", f"`{p.flag}`" if p.flag else "—", p.value, p.meaning] for p in report.params],
    )
    out += ["## Cách tính", "", *[f"{i}. {f}" for i, f in enumerate(FORMULA, 1)], "", WHY_ROBUST, ""]
    out += ["## Giải thích các cột", ""]
    out += table(["Cột", "Ý nghĩa"], [[f"`{c}`", d] for c, d in COLUMNS])
    return "\n".join(out)


def write_markdown(report: Report, path: Path) -> None:
    path.write_text(render_markdown(report), encoding="utf-8")
