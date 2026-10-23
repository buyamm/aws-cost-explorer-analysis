import subprocess
from pathlib import Path

import pytest

from cost_anomaly.pdf import BROWSER_ENV, MAC_APPS, PdfError, find_browser, write_pdf


def test_env_browser_wins(tmp_path):
    exe = tmp_path / "chrome"
    exe.write_text("")
    assert find_browser({BROWSER_ENV: str(exe)}, which=lambda n: "/usr/bin/chromium") == str(exe)


def test_env_browser_must_exist(tmp_path):
    with pytest.raises(PdfError, match=BROWSER_ENV):
        find_browser({BROWSER_ENV: str(tmp_path / "nope")}, which=lambda n: "/usr/bin/chromium")


def test_path_lookup_then_mac_apps():
    found = find_browser({}, which=lambda n: "/usr/bin/chromium" if n == "chromium" else None)
    assert found == "/usr/bin/chromium"
    assert find_browser({}, which=lambda n: None, exists=lambda p: p == MAC_APPS[1]) == MAC_APPS[1]


def test_no_browser_raises_vietnamese_hint():
    with pytest.raises(PdfError) as e:
        find_browser({}, which=lambda n: None, exists=lambda p: False)
    assert "Chrome" in str(e.value) and BROWSER_ENV in str(e.value) and "cần" in str(e.value)


class Runner:
    def __init__(self, returncode=0, write=b"%PDF-1.4 fake", exc=None):
        self.calls, self.returncode, self.write, self.exc = [], returncode, write, exc

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc:
            raise self.exc
        out = next(a for a in args if a.startswith("--print-to-pdf=")).split("=", 1)[1]
        if self.write is not None:
            Path(out).write_bytes(self.write)
        return subprocess.CompletedProcess(args, self.returncode, "", "boom" if self.returncode else "")


def test_write_pdf_runs_headless_print(tmp_path):
    html, pdf = tmp_path / "r.html", tmp_path / "r.pdf"
    html.write_text("<html></html>")
    run = Runner()
    write_pdf(html, pdf, "/bin/chrome", run=run)
    (args, kwargs), = run.calls
    assert args[0] == "/bin/chrome"
    assert "--headless" in args and "--no-pdf-header-footer" in args
    assert f"--print-to-pdf={pdf.resolve()}" in args
    assert any(a.startswith("--user-data-dir=") for a in args)
    assert args[-1] == html.resolve().as_uri()
    assert kwargs["timeout"] > 0 and kwargs["capture_output"]
    assert pdf.read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize(
    "runner",
    [
        Runner(returncode=1),
        Runner(write=None),
        Runner(write=b""),
        Runner(exc=subprocess.TimeoutExpired("chrome", 120)),
        Runner(exc=OSError("exec format error")),
    ],
)
def test_write_pdf_failures_raise(tmp_path, runner):
    html = tmp_path / "r.html"
    html.write_text("<html></html>")
    with pytest.raises(PdfError):
        write_pdf(html, tmp_path / "r.pdf", "/bin/chrome", run=runner)
