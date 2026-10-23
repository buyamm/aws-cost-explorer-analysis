import json
import urllib.error
from datetime import date

import pytest

from cost_anomaly.alert import AlertError, build_message, send, validate_webhook, webhook_from_env
from cost_anomaly.detect import DROP, RATE, SPIKE
from cost_anomaly.state import NEW, WORSE, Change, Incident

URL = "https://hooks.slack.com/services/T000/B000/XXXXSECRET"


def incident(service="Amazon EC2", kind=SPIKE, peak=228.91, impact=4578.2, **kw) -> Incident:
    fields = dict(driver="usage", provisional=False, known=False)
    fields.update(kw)
    return Incident(service, kind, date(2026, 10, 11), date(2026, 10, 12), peak, impact, **fields)


def text_of(payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_message_lists_incidents_by_month_impact_in_vietnamese():
    changes = [
        Change(incident("Small", impact=100), NEW),
        Change(incident("AWS Backup", DROP, peak=-40, impact=-800), WORSE),
        Change(incident("Fargate", peak=28, impact=5000, driver=RATE, provisional=True), NEW),
    ]
    payload = build_message(changes, "project-cost", "s3://bucket/reports/2026-10-15/anomalies_report.html")
    assert payload["text"] == "cost-anomaly: 3 sự cố chi phí mới/xấu đi (profile project-cost)"
    sections = [b["text"]["text"] for b in payload["blocks"] if b["type"] == "section"]
    assert [s.split("*")[1] for s in sections] == ["SPIKE · Fargate", "DROP · AWS Backup", "SPIKE · Small"]
    assert "(mới)" in sections[0] and "do giá/coverage" in sections[0] and "tạm tính" in sections[0]
    assert "(xấu đi)" in sections[1] and "giảm $40.00/ngày" in sections[1] and "-$800.00" in sections[1]
    assert "s3://bucket/reports/2026-10-15/anomalies_report.html" in text_of(payload)


def test_message_caps_the_list_at_ten():
    payload = build_message([Change(incident(f"svc{i}"), NEW) for i in range(13)], "p", None)
    assert sum(b["type"] == "section" for b in payload["blocks"]) == 10
    assert "và 3 sự cố khác" in text_of(payload)


def test_service_names_are_escaped_for_slack():
    payload = build_message([Change(incident("<!channel> & co"), NEW)], "p", None)
    assert "&lt;!channel&gt; &amp; co" in text_of(payload) and "<!channel>" not in text_of(payload)


@pytest.mark.parametrize("url", [URL, "https://hooks.slack.com/triggers/abc"])
def test_valid_webhooks(url):
    validate_webhook(url)


@pytest.mark.parametrize("url", ["", "http://hooks.slack.com/services/x", "https://evil.example/services/x", "https://hooks.slack.com.evil.example/x"])
def test_invalid_webhooks_are_rejected_without_echoing_them(url):
    with pytest.raises(AlertError) as exc:
        validate_webhook(url)
    assert "evil" not in str(exc.value)


def test_webhook_from_env():
    assert webhook_from_env({"COST_ANOMALY_SLACK_WEBHOOK": f" {URL} "}) == URL
    assert webhook_from_env({}) is None


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"ok"


class FakeOpener:
    def __init__(self, *outcomes):
        self.outcomes, self.requests = list(outcomes), []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse()


def http_error(code):
    return urllib.error.HTTPError(URL, code, "boom", {}, None)


def test_send_posts_json_once():
    opener, sleeps = FakeOpener("ok"), []
    send(URL, {"text": "hi"}, opener=opener, sleep=sleeps.append)
    (request, timeout), = opener.requests
    assert (request.get_method(), request.full_url, timeout) == ("POST", URL, 10)
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == {"text": "hi"} and sleeps == []


def test_send_retries_transient_failures():
    opener, sleeps = FakeOpener(urllib.error.URLError("timed out"), http_error(429), "ok"), []
    send(URL, {"text": "hi"}, opener=opener, sleep=sleeps.append)
    assert len(opener.requests) == 3 and sleeps == [1, 2]


def test_send_gives_up_without_leaking_the_url():
    opener = FakeOpener(http_error(500), http_error(502), http_error(503))
    with pytest.raises(AlertError) as exc:
        send(URL, {"text": "hi"}, opener=opener, sleep=lambda s: None)
    assert "503" in str(exc.value) and "SECRET" not in str(exc.value)


def test_client_errors_are_not_retried():
    opener = FakeOpener(http_error(400))
    with pytest.raises(AlertError, match="400"):
        send(URL, {"text": "hi"}, opener=opener, sleep=lambda s: None)
    assert len(opener.requests) == 1
