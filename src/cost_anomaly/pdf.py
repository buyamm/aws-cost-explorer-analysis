"""Print the HTML report to PDF with an installed Chromium-family browser (headless), no Python dependency."""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

BROWSER_ENV = "COST_ANOMALY_BROWSER"
PATH_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]
MAC_APPS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
TIMEOUT_SECONDS = 120


class PdfError(Exception):
    pass


def find_browser(
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    exists: Callable[[str], bool] | None = None,
) -> str:
    """$COST_ANOMALY_BROWSER, then Chrome/Chromium/Edge on PATH, then the macOS app bundles."""
    # Looked up at call time so tests can replace them.
    env = os.environ if env is None else env
    which = which or shutil.which
    exists = exists or os.path.exists
    if path := env.get(BROWSER_ENV):
        if not Path(path).is_file():
            raise PdfError(f"{BROWSER_ENV}={path} không tồn tại")
        return path
    for name in PATH_NAMES:
        if found := which(name):
            return found
    for app in MAC_APPS:
        if exists(app):
            return app
    raise PdfError(
        "--pdf cần Chrome, Chromium hoặc Edge để in report ra PDF. Hãy cài một trình duyệt này, "
        f"hoặc đặt {BROWSER_ENV} trỏ tới file chạy của nó."
    )


def write_pdf(html_path: Path, pdf_path: Path, browser: str, run: Callable = subprocess.run) -> None:
    """Headless print of the written HTML; the page's print stylesheet decides the layout."""
    pdf = pdf_path.resolve()
    with tempfile.TemporaryDirectory(prefix="cost-anomaly-pdf-") as profile:
        args = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",  # never touch the user's own browser profile
            f"--print-to-pdf={pdf}",
            html_path.resolve().as_uri(),
        ]
        try:
            result = run(args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise PdfError(f"trình duyệt không in xong sau {TIMEOUT_SECONDS} giây") from None
        except OSError as e:
            raise PdfError(f"không chạy được {browser}: {e}") from None
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()[-1:] or [""]
        raise PdfError(f"trình duyệt thoát với mã {result.returncode} {detail[0]}".strip())
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise PdfError(f"trình duyệt không tạo ra {pdf}")
