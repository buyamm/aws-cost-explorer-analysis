"""Turn detection results into a human-readable summary (shared by the HTML and Markdown reports)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .config import Settings
from .dates import Windows, date_range
from .detect import AMORTIZED, DROP, MAD_TO_SIGMA, NEW_SERVICE, RATE, SPIKE, Anomaly, Score, score_pair
from .transform import CostMatrix

NEAR_MISS_LIMIT = 10
RATE_LABEL = "do giá/coverage"
PROVISIONAL_LABEL = "tạm tính"
KNOWN_LABEL = "đã biết"


def usd(v: float) -> str:
    return f"-${-v:,.2f}" if v < 0 else f"${v:,.2f}"


@dataclass(frozen=True)
class Param:
    name: str
    flag: str | None
    value: str
    meaning: str


@dataclass(frozen=True)
class AnomalyRow:
    anomaly: Anomaly
    score: Score
    severity: str
    explanation: str
    labels: list[str]  # short Vietnamese tags shown next to the kind


@dataclass(frozen=True)
class NearMiss:
    date: date
    service: str
    score: Score
    reason: str


@dataclass(frozen=True)
class ServiceRollup:
    service: str
    kinds: list[str]
    days: list[date]
    runs: list[tuple[date, date]]
    excess: float
    anomalies: list[Anomaly]
    ongoing: bool

    @property
    def peak(self) -> Anomaly:
        """Largest SPIKE if any (it has a z-score), else the largest anomaly."""
        spikes = [a for a in self.anomalies if a.kind == SPIKE] or self.anomalies
        return max(spikes, key=lambda a: a.delta)


@dataclass(frozen=True)
class ChartPoint:
    day: date
    cost: float
    median: float | None  # None until a full baseline is available
    threshold: float | None  # cost above this (and above median + min_delta) is flagged


@dataclass(frozen=True)
class Report:
    profile: str
    generated_at: datetime
    settings: Settings
    windows: Windows
    rows: list[AnomalyRow]  # same order as the CSV
    rollups: list[ServiceRollup]  # largest excess first
    near_misses: list[NearMiss]
    charts: dict[str, list[ChartPoint]]  # anomalous services, same order as rollups
    eval_spend: float
    excess: float
    insights: list[str]
    next_steps: list[str]
    params: list[Param]

    @property
    def spike_count(self) -> int:
        return sum(1 for r in self.rows if r.anomaly.kind == SPIKE)

    @property
    def new_count(self) -> int:
        return sum(1 for r in self.rows if r.anomaly.kind == NEW_SERVICE)

    @property
    def drop_count(self) -> int:
        return sum(1 for r in self.rows if r.anomaly.kind == DROP)

    @property
    def kind_summary(self) -> str:
        """e.g. "2 SPIKE, 1 NEW_SERVICE" (+ ", 1 DROP" when there are drops)."""
        return kind_summary([r.anomaly for r in self.rows])


COLUMNS = [
    ("date", "Ngày được đánh giá (UTC). Mỗi ngày được so với 30 ngày ngay trước nó."),
    ("service", "Tên service theo dimension SERVICE của Cost Explorer."),
    ("kind", "SPIKE: tăng đột biến so với lịch sử. NEW_SERVICE: service chưa đủ lịch sử nhưng chi phí đã vượt ngưỡng. DROP: service đang ổn định bỗng rơi về gần 0."),
    ("cost", "Chi phí của service trong ngày đó (USD) theo số đo ở cột metric. Dữ liệu gồm Usage và phần được Savings Plans/RI che (SavingsPlanCoveredUsage, DiscountedUsage)."),
    ("baseline_median", "Trung vị chi phí 30 ngày trước: mức \"bình thường\" của service. Ngày không có chi phí được tính là 0."),
    ("mad", "Median Absolute Deviation: trung vị của |chi phí − median|, thước đo độ dao động ít bị ảnh hưởng bởi các đỉnh cũ."),
    ("robust_z", "(cost − median) / σ̂, với σ̂ = max(1.4826 × MAD, 1% × median, $0.01). Nghĩa là chi phí cách mức bình thường bao nhiêu lần độ dao động thông thường. Để trống với NEW_SERVICE."),
    ("delta", "cost − baseline_median: số USD vượt mức bình thường trong ngày."),
    ("metric", "usage: số liệu theo UnblendedCost (giá on-demand tương đương với phần Savings Plans che, $0 với phần RI che). amortized: theo NetAmortizedCost, tức chi phí thực trả sau Savings Plans/RI; chỉ dùng khi usage không bất thường."),
    ("driver", "usage: mức sử dụng tăng, hai số đo cùng tăng xấp xỉ bằng nhau. rate: tăng do giá hoặc coverage Savings Plans/RI thay đổi (ví dụ cam kết hết hạn), không phải do dùng nhiều hơn."),
    ("month_impact", "delta × số ngày từ ngày đó tới hết tháng (tính cả hai đầu): chi phí thêm nếu mức bất thường tiếp diễn. Âm với DROP."),
    ("known", "true nếu service nằm trong danh sách known của file config: vẫn báo nhưng đã được giải thích."),
    ("provisional", "true: ngày thuộc 2 ngày gần nhất, Cost Explorer chưa chốt số liệu nên con số có thể còn thay đổi (tạm tính)."),
]

FORMULA = [
    "median = trung vị chi phí của 30 ngày baseline (ngày không có chi phí tính là $0)",
    "MAD = trung vị của |chi phí_ngày − median| trên 30 ngày đó",
    f"σ̂ = max({MAD_TO_SIGMA} × MAD, 1% × median, $0.01): độ lệch chuẩn ước lượng; hai giá trị sàn tránh chia cho 0 khi chi phí phẳng",
    "z = (cost − median) / σ̂",
    "SPIKE ⇔ service có ≥ min_history ngày có chi phí trong baseline, z > k và cost − median ≥ min_delta",
    "NEW_SERVICE ⇔ service có < min_history ngày có chi phí trong baseline và cost ≥ new_threshold",
    "Mỗi ngày được chấm trên hai số đo: usage (UnblendedCost) và amortized (NetAmortizedCost). Một ngày có \"chi phí\" nếu một trong hai số đo > 0",
    "DROP ⇔ đủ lịch sử, median ≥ drop_min_median, cost ≤ drop_ratio × median và z < −k, trên chi phí thực trả và cả usage (trừ khi usage luôn là $0 vì được RI che)",
    "driver = usage ⇔ cả hai số đo cùng tăng và Δamortized nằm trong ±driver_tolerance của Δusage; ngược lại driver = rate",
]

WHY_ROBUST = (
    "Median và MAD được dùng thay cho trung bình và độ lệch chuẩn vì chúng ít bị ảnh hưởng bởi các ngày đột biến "
    "trong quá khứ: một đỉnh cũ không kéo ngưỡng lên và không che đi đỉnh mới. Hệ số 1.4826 quy đổi MAD về cùng "
    "thang với độ lệch chuẩn khi dữ liệu xấp xỉ phân phối chuẩn, nên ngưỡng k = 3.5 được hiểu như \"3.5 sigma\"."
)


def override_value(key: str, value: float) -> str:
    return usd(value) if key in ("min_delta", "new_threshold", "drop_min_median") else f"{value:g}"


def build_params(s: Settings) -> list[Param]:
    overrides = [
        Param(f"{service} · {key}", "--config", override_value(key, value), "Ghi đè riêng cho service này trong file config.")
        for service, table in sorted(s.service_overrides.items())
        for key, value in sorted(table.items())
    ]
    lists = [
        Param(name, "--config", ", ".join(sorted(names)), meaning)
        for name, names, meaning in (
            ("ignore", s.ignore, "Không phân tích các service này."),
            ("known", s.known, f"Vẫn báo nhưng gắn nhãn {KNOWN_LABEL}: biến động đã được giải thích."),
        )
        if names
    ]
    return [
        Param("k", "--k", f"{s.k:g}", "Ngưỡng robust z-score. Ngày chỉ là SPIKE khi chi phí cao hơn median hơn k lần độ dao động thông thường. Tăng k thì ít cảnh báo hơn, giảm k thì nhạy hơn."),
        Param("min_delta", "--min-delta", usd(s.min_delta), "Mức tăng tối thiểu so với median. Loại các biến động có z cao nhưng giá trị tiền nhỏ, hay gặp ở service rẻ và ổn định."),
        Param("new_threshold", "--new-threshold", usd(s.new_threshold) + "/ngày", "Chi phí/ngày tối thiểu để báo NEW_SERVICE cho service chưa đủ lịch sử."),
        Param("detect_drops", "--no-drop", "có" if s.detect_drops else "không", "Báo DROP khi service ổn định bỗng rơi về gần 0 (backup ngừng, prod sập)."),
        Param("drop_ratio", None, f"{s.drop_ratio:.0%}", "DROP khi chi phí chỉ còn tối đa tỉ lệ này của median."),
        Param("drop_min_median", None, usd(s.drop_min_median) + "/ngày", "Median tối thiểu để xét DROP; service rẻ hơn không đáng báo."),
        Param("min_history", "--min-history", f"{s.min_history} ngày", "Số ngày có chi phí > 0 tối thiểu trong baseline để dùng z-score. Ít hơn thì service được coi là mới hoặc phát sinh thưa."),
        Param("baseline_days", None, f"{s.baseline_days} ngày", "Số ngày ngay trước mỗi ngày đánh giá được dùng làm mức chuẩn."),
        Param("eval_days", "--eval-days", f"{s.eval_days} ngày", "Số ngày được kiểm tra bất thường trong mỗi lần chạy (1–58, để mọi ngày đánh giá đều đủ 30 ngày baseline)."),
        Param("exclude_recent_days", None, f"{s.exclude_recent_days} ngày", "Số ngày gần nhất Cost Explorer chưa chốt số liệu. Chúng không được tính là ngày đã chốt trong --eval-days."),
        Param("include_provisional", "--no-provisional", "có" if s.include_provisional else "không", "Vẫn đánh giá các ngày chưa chốt và gắn nhãn tạm tính, để thấy chi phí hôm qua trong lần chạy hằng ngày. Con số có thể còn thay đổi."),
        Param("lookback_days", None, f"{s.lookback_days} ngày", "Tổng số ngày dữ liệu lấy từ Cost Explorer (phải đủ cho baseline của ngày đánh giá sớm nhất)."),
        Param("driver_tolerance", None, f"±{s.driver_tolerance:.0%}", "Độ lệch tối đa giữa mức tăng chi phí thực trả và mức tăng usage để coi là do dùng nhiều hơn (driver = usage)."),
        Param("max_pages", "--max-pages", str(s.max_pages), "Giới hạn số request GetCostAndUsage (mỗi request $0.01)."),
    ] + overrides + lists


def severity(z: float | None, k: float) -> str:
    if z is None:
        return "mới"
    z = abs(z)  # drops have negative z
    if z >= 4 * k:
        return "rất mạnh"
    if z >= 2 * k:
        return "mạnh"
    return "vừa"


def ratio_text(cost: float, med: float) -> str:
    return f"gấp {cost / med:.1f} lần median" if med > 0 else "median"


def driver_note(usage: Score, amortized: Score) -> str:
    return (
        f" Gắn nhãn {RATE_LABEL}: chi phí thực trả (NetAmortizedCost) thay đổi {usd(amortized.delta)} trong khi chi phí "
        f"usage theo giá on-demand thay đổi {usd(usage.delta)}, nên phần tăng đến từ thay đổi Savings Plans/RI hoặc đơn giá, "
        "không phải do dùng nhiều hơn."
    )


def labels(a: Anomaly) -> list[str]:
    return [RATE_LABEL] * (a.driver == RATE) + [PROVISIONAL_LABEL] * a.provisional + [KNOWN_LABEL] * a.known


def explain(a: Anomaly, s: Score, settings: Settings) -> str:
    if a.kind == NEW_SERVICE:
        history = (
            f"Chỉ {s.history_days}/{settings.baseline_days} ngày baseline có chi phí"
            if s.history_days
            else f"Không có chi phí nào trong {settings.baseline_days} ngày trước"
        )
        return (
            f"{history} (cần ≥ {settings.min_history}) nên chưa đủ lịch sử để tính z-score. "
            f"Bị gắn NEW_SERVICE vì {usd(a.cost)} ≥ ngưỡng {usd(settings.new_threshold)}/ngày."
        )
    if s.scale == MAD_TO_SIGMA * s.mad:
        scale = f"σ̂ = {MAD_TO_SIGMA} × MAD {usd(s.mad)} = {usd(s.scale)}"
    else:
        scale = f"MAD gần bằng 0 (chi phí rất ổn định) nên σ̂ lấy mức sàn {usd(s.scale)}"
    measure = "Chi phí thực trả (amortized)" if a.metric == AMORTIZED else "Chi phí"
    if a.kind == DROP:
        share = a.cost / a.baseline_median
        return (
            f"{measure} {usd(a.cost)}, chỉ còn {share:.0%} median {usd(a.baseline_median)} (≤ drop_ratio {settings.drop_ratio:.0%}), "
            f"giảm {usd(-a.delta)}; z = {s.robust_z:.2f} < −k = −{settings.k:g}. Service đang ổn định bỗng gần như không phát sinh chi phí."
        )
    return (
        f"{measure} {usd(a.cost)}, {ratio_text(a.cost, a.baseline_median)} {usd(a.baseline_median)}, vượt {usd(a.delta)} "
        f"(≥ min_delta {usd(settings.min_delta)}). {scale} → z = {s.robust_z:.2f}, vượt ngưỡng k = {settings.k:g}."
    )


def runs_of(days: list[date]) -> list[tuple[date, date]]:
    runs: list[tuple[date, date]] = []
    for d in sorted(days):
        if runs and d - runs[-1][1] == timedelta(days=1):
            runs[-1] = (runs[-1][0], d)
        else:
            runs.append((d, d))
    return runs


def near_miss(s: Score, settings: Settings) -> str | None:
    """Why a non-flagged day still deserves a look, or None if it's unremarkable."""
    if s.history_days < settings.min_history:
        if settings.new_threshold / 2 <= s.cost < settings.new_threshold:
            return f"Service mới/thưa ({s.history_days} ngày có chi phí), {usd(s.cost)} < new_threshold {usd(settings.new_threshold)}"
        return None
    if s.robust_z > settings.k and 0 < s.delta < settings.min_delta:
        return f"z = {s.robust_z:.1f} > k nhưng chỉ tăng {usd(s.delta)} < min_delta {usd(settings.min_delta)}"
    if s.delta >= settings.min_delta and settings.k / 2 <= s.robust_z <= settings.k:
        return f"Tăng {usd(s.delta)} nhưng z = {s.robust_z:.1f} ≤ k: vẫn trong biên độ dao động thường của service"
    if (
        settings.detect_drops
        and s.baseline_median >= settings.drop_min_median
        and s.robust_z < -settings.k
        and settings.drop_ratio * s.baseline_median < s.cost <= 0.5 * s.baseline_median
    ):
        return f"Giảm còn {s.cost / s.baseline_median:.0%} median, chưa tới ngưỡng DROP (≤ {settings.drop_ratio:.0%})"
    return None


def chart_points(
    series: dict[date, float], windows: Windows, settings: Settings, paid: dict[date, float] | None = None
) -> list[ChartPoint]:
    first_scored = windows.fetch_start + timedelta(days=settings.baseline_days)
    points = []
    for d in date_range(windows.fetch_start, windows.fetch_end):
        if d < first_scored:
            points.append(ChartPoint(d, series.get(d, 0.0), None, None))
            continue
        s, _ = score_pair(series, series if paid is None else paid, d, settings)
        if s.history_days < settings.min_history:
            threshold = settings.new_threshold
        else:
            threshold = s.baseline_median + max(settings.k * s.scale, settings.min_delta)
        points.append(ChartPoint(d, s.cost, s.baseline_median, threshold))
    return points


def build_rollups(rows: list[AnomalyRow], last_eval: date) -> list[ServiceRollup]:
    by_service: dict[str, list[Anomaly]] = {}
    for r in rows:
        by_service.setdefault(r.anomaly.service, []).append(r.anomaly)
    rollups = [
        ServiceRollup(
            service=svc,
            kinds=sorted({a.kind for a in items}),
            days=sorted(a.date for a in items),
            runs=runs_of([a.date for a in items]),
            excess=sum(a.delta for a in items),
            anomalies=items,
            ongoing=any(a.date == last_eval for a in items),
        )
        for svc, items in by_service.items()
    ]
    return sorted(rollups, key=lambda r: r.excess, reverse=True)


def fmt_run(run: tuple[date, date]) -> str:
    return run[0].isoformat() if run[0] == run[1] else f"{run[0].isoformat()} → {run[1].isoformat()}"


def service_insight(
    r: ServiceRollup, matrix: CostMatrix, amortized: CostMatrix, windows: Windows, settings: Settings
) -> str:
    series, paid = matrix.get(r.service, {}), amortized.get(r.service, {})
    last_eval = windows.eval_days[-1]

    if r.kinds == [NEW_SERVICE]:
        flagged = [series[d] for d in r.days]
        first, last = flagged[0], flagged[-1]
        trend = "tăng dần" if last > first * 1.2 else "giảm dần" if last < first * 0.8 else "khá ổn định"
        s, _ = score_pair(series, paid, r.days[0], settings)
        text = (
            f"{r.service}: chi phí mới xuất hiện, bị gắn NEW_SERVICE {len(r.days)} ngày ({fmt_run((r.days[0], r.days[-1]))}), "
            f"{trend} từ {usd(first)} đến {usd(last)}/ngày, tổng {usd(sum(flagged))}. "
            f"Nếu giữ mức ngày cuối, ước tính thô khoảng {usd(last * 30)}/30 ngày."
        )
        if s.history_days:
            text += (
                f" Service đã có chi phí rải rác trước đó ({s.history_days}/{settings.baseline_days} ngày): "
                "có thể là job định kỳ hoặc dùng thất thường, không hẳn là service mới."
            )
        return text + (
            f" Service sẽ hết bị gắn NEW_SERVICE khi baseline có đủ {settings.min_history} ngày có chi phí; "
            "từ đó mới được so bằng z-score."
        )

    if r.kinds == [DROP]:
        low = min(r.anomalies, key=lambda a: a.cost)
        runs = ", ".join(fmt_run(x) for x in r.runs)
        text = (
            f"{r.service}: chi phí rơi về gần 0 trong {len(r.days)} ngày ({runs}), thấp nhất {usd(low.cost)}/ngày "
            f"so với mức bình thường {usd(low.baseline_median)}."
        )
        if r.ongoing:
            return text + f" Vẫn còn ở ngày đánh giá mới nhất ({last_eval.isoformat()}): kiểm tra service còn chạy không."
        return text + " Chi phí đã quay lại sau đó."

    p = r.peak
    if len(r.runs) == 1 and r.runs[0][0] == r.runs[0][1]:
        text = (
            f"{r.service}: tăng đột biến ngày {p.date.isoformat()} lên {usd(p.cost)} "
            f"({ratio_text(p.cost, p.baseline_median)} {usd(p.baseline_median)}, z = {p.robust_z:.1f}, mức {severity(p.robust_z, settings.k)})."
        )
    else:
        runs = ", ".join(fmt_run(x) for x in r.runs)
        longest = max((b - a).days + 1 for a, b in r.runs)
        shape = f"kéo dài {longest} ngày liên tiếp" if len(r.runs) == 1 else f"{len(r.runs)} đợt"
        text = (
            f"{r.service}: bất thường {shape} ({runs}), đỉnh {usd(p.cost)} ngày {p.date.isoformat()} "
            f"(z = {p.robust_z:.1f}), tổng vượt {usd(r.excess)}."
        )
    if NEW_SERVICE in r.kinds:
        text += " Một số ngày khác bị gắn NEW_SERVICE vì service chưa đủ lịch sử."

    if r.ongoing:
        latest = max(r.anomalies, key=lambda a: a.date)
        return text + (
            f" Bất thường vẫn còn ở ngày đánh giá mới nhất ({last_eval.isoformat()}), nên kiểm tra ngay. "
            f"Nếu tiếp diễn với mức {usd(latest.delta)}/ngày, tháng {latest.date.month} tốn thêm khoảng "
            f"{usd(latest.month_impact)} tính từ ngày đó."
        )
    # Not ongoing, so the day after the last run is an evaluated day that was not flagged.
    after = r.runs[-1][1] + timedelta(days=1)
    su, sa = score_pair(series, paid, after, settings)
    s = sa if p.metric == AMORTIZED else su
    return text + (
        f" Ngày {after.isoformat()} chi phí đã về {usd(s.cost)} (median {usd(s.baseline_median)}), "
        "trong biên độ bình thường: có vẻ là sự kiện nhất thời."
    )


def kind_summary(anomalies: list[Anomaly]) -> str:
    drops = sum(a.kind == DROP for a in anomalies)
    parts = [f"{sum(a.kind == SPIKE for a in anomalies)} SPIKE", f"{sum(a.kind == NEW_SERVICE for a in anomalies)} NEW_SERVICE"]
    return ", ".join(parts + [f"{drops} DROP"] * (drops > 0))


def build_report(
    matrix: CostMatrix,
    windows: Windows,
    settings: Settings,
    anomalies: list[Anomaly],
    profile: str,
    generated_at: datetime,
    amortized: CostMatrix | None = None,
) -> Report:
    amortized = matrix if amortized is None else amortized
    services = sorted((matrix.keys() | amortized.keys()) - settings.ignore)

    def pair(service: str, day: date) -> tuple[Score, Score]:
        return score_pair(matrix.get(service, {}), amortized.get(service, {}), day, settings.for_service(service))

    ordered = sorted(anomalies, key=lambda a: (a.date, a.delta), reverse=True)
    rows = []
    for a in ordered:
        su, sa = pair(a.service, a.date)
        s = sa if a.metric == AMORTIZED else su
        svc = settings.for_service(a.service)
        text = explain(a, s, svc) + (driver_note(su, sa) if a.driver == RATE else "")
        rows.append(AnomalyRow(a, s, severity(a.robust_z, svc.k), text, labels(a)))

    flagged = {(a.service, a.date) for a in anomalies}
    misses = []
    for service in services:
        for d in windows.eval_days:
            if (service, d) in flagged:
                continue
            s, _ = pair(service, d)
            reason = near_miss(s, settings.for_service(service))
            if reason:
                misses.append(NearMiss(d, service, s, reason))
    misses = sorted(misses, key=lambda m: m.score.delta, reverse=True)[:NEAR_MISS_LIMIT]

    last_eval = windows.eval_days[-1]
    rollups = build_rollups(rows, last_eval)
    # What was actually paid: the usage measure prices Savings Plan covered usage at on-demand rates.
    eval_spend = sum(amortized[svc].get(d, 0.0) for svc in services if svc in amortized for d in windows.eval_days)
    excess = sum(a.delta for a in anomalies if a.kind != DROP)

    period = f"{windows.eval_days[0].isoformat()} → {last_eval.isoformat()}"
    if not anomalies:
        insights = [
            f"Không phát hiện bất thường nào trong {len(windows.eval_days)} ngày đánh giá ({period}) "
            f"trên {len(services)} service. Tổng chi phí khung đánh giá {usd(eval_spend)}."
        ]
    else:
        share = f" ({excess / eval_spend:.0%} tổng chi phí khung)" if eval_spend else ""
        insights = [
            f"Trong {len(windows.eval_days)} ngày đánh giá ({period}), tổng chi phí là {usd(eval_spend)} trên {len(services)} service. "
            f"Phát hiện {len(anomalies)} bất thường ({kind_summary(anomalies)}) ở {len(rollups)} service, "
            f"tổng phần vượt mức bình thường {usd(excess)}{share}."
        ]
        top = rollups[0]
        if len(rollups) > 1 and excess > 0:
            insights.append(f"Đóng góp lớn nhất: {top.service} với {usd(top.excess)} ({top.excess / excess:.0%} phần vượt).")
        insights += [service_insight(r, matrix, amortized, windows, settings.for_service(r.service)) for r in rollups]
    if misses:
        insights.append(
            f"Có {len(misses)} biến động không bị báo nhờ bộ lọc ngưỡng (xem mục \"Biến động bị lọc\"). "
            "Nếu thấy cần bắt các trường hợp này, hãy cân nhắc giảm --min-delta hoặc --k."
        )
    unsettled = f"{settings.exclude_recent_days} ngày gần nhất"
    if windows.provisional_days:
        span = f"{windows.provisional_days[0].isoformat()} → {windows.provisional_days[-1].isoformat()}"
        insights.append(
            f"Lưu ý: {unsettled} ({span}) được đánh giá với nhãn {PROVISIONAL_LABEL} vì Cost Explorer chưa chốt số liệu; "
            "con số có thể còn thay đổi ở lần chạy sau."
        )
    else:
        insights.append(
            f"Lưu ý: {unsettled} ({(last_eval + timedelta(days=1)).isoformat()} → "
            f"{(windows.fetch_end - timedelta(days=1)).isoformat()}) không được đánh giá vì Cost Explorer chưa chốt số liệu."
        )

    next_steps = []
    if any(a.kind == SPIKE for a in anomalies):
        next_steps.append(
            "Với SPIKE: mở Cost Explorer, lọc đúng service và ngày, group by Usage type / Region / Linked account "
            "để tìm nguồn tăng; đối chiếu CloudTrail cùng ngày để biết ai tạo hoặc thay đổi tài nguyên."
        )
    if any(a.kind == NEW_SERVICE for a in anomalies):
        next_steps.append(
            "Với NEW_SERVICE: xác nhận service được bật có chủ đích, đã có owner và budget; "
            "nếu không, tắt tài nguyên trước khi chi phí tích lũy."
        )
    if any(a.kind == DROP for a in anomalies):
        next_steps.append(
            "Với DROP: kiểm tra service còn chạy không (job backup, pipeline định kỳ, workload production); xem "
            "CloudWatch và AWS Health cùng ngày. Nếu đã chủ động tắt, thêm service vào danh sách known trong file config."
        )
    if any(r.ongoing for r in rollups):
        next_steps.append("Ưu tiên các service còn bất thường ở ngày đánh giá mới nhất, vì chi phí có thể vẫn đang tăng.")

    charts = {
        r.service: chart_points(
            matrix.get(r.service, {}), windows, settings.for_service(r.service), amortized.get(r.service, {})
        )
        for r in rollups
    }
    return Report(
        profile=profile,
        generated_at=generated_at,
        settings=settings,
        windows=windows,
        rows=rows,
        rollups=rollups,
        near_misses=misses,
        charts=charts,
        eval_spend=eval_spend,
        excess=excess,
        insights=insights,
        next_steps=next_steps,
        params=build_params(settings),
    )
