import csv
from pathlib import Path

from .detect import Anomaly

FIELDS = ["date", "service", "kind", "cost", "baseline_median", "mad", "robust_z", "delta"]


def write_csv(anomalies: list[Anomaly], path: Path) -> None:
    rows = sorted(anomalies, key=lambda a: (a.date, a.delta), reverse=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for a in rows:
            writer.writerow(
                {
                    "date": a.date.isoformat(),
                    "service": a.service,
                    "kind": a.kind,
                    "cost": f"{a.cost:.4f}",
                    "baseline_median": f"{a.baseline_median:.4f}",
                    "mad": f"{a.mad:.4f}",
                    "robust_z": "" if a.robust_z is None else f"{a.robust_z:.2f}",
                    "delta": f"{a.delta:.4f}",
                }
            )
