"""Run cost-anomaly straight from a checkout, without installing the package.

    python run.py --profile project-cost

Only needs boto3 importable (see README, "Chạy trực tiếp từ mã nguồn").
"""

import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"error: cost-anomaly needs Python >= 3.11 (this is {sys.version.split()[0]} at {sys.executable})")

try:
    import boto3  # noqa: F401
except ImportError:
    sys.exit(f"error: boto3 is not installed for {sys.executable}; run: {sys.executable} -m pip install boto3")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cost_anomaly.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
