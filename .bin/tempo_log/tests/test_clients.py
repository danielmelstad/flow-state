import io
import json
import urllib.error
import urllib.request
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from tempo_log.http import HttpError, TokenError, UrllibTransport, token_from_env
from tempo_log.jira import JiraClient
from tempo_log.tempo import TempoClient, slots_from_worklogs


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)  # list of (status, body)
        self.calls = []

    def request(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return self.responses.pop(0)


def test_token_from_env(monkeypatch):
    monkeypatch.delenv("X_TOKEN", raising=False)
    with pytest.raises(TokenError, match="X_TOKEN"):
        token_from_env("X_TOKEN")
    monkeypatch.setenv("X_TOKEN", "abc")
    assert token_from_env("X_TOKEN") == "abc"


def test_jira_issue_lookup_uses_basic_auth():
    t = FakeTransport([(200, {"id": "10042", "fields": {"summary": "Do it"}})])
    client = JiraClient("https://x.atlassian.net", "me@x", "tok", t)
    assert client.issue("ADA-1") == (10042, "Do it")
    method, url, headers, body = t.calls[0]
    assert method == "GET" and url == "https://x.atlassian.net/rest/api/3/issue/ADA-1?fields=summary"
    assert headers["Authorization"].startswith("Basic ") and body is None


def test_jira_myself():
    t = FakeTransport([(200, {"accountId": "712020:abc", "displayName": "Dev"})])
    assert JiraClient("https://x", "me@x", "tok", t).myself() == ("712020:abc", "Dev")


def test_jira_404_raises_http_error():
    t = FakeTransport([(404, {"errorMessages": ["Issue does not exist"]})])
    with pytest.raises(HttpError) as exc:
        JiraClient("https://x", "me@x", "tok", t).issue("NOPE-1")
    assert exc.value.status == 404 and "Issue does not exist" in str(exc.value)


def test_tempo_create_and_delete():
    t = FakeTransport([(200, {"tempoWorklogId": 555}), (204, None)])
    client = TempoClient("https://api.eu.tempo.io", "tok", t)
    payload = {"authorAccountId": "a", "issueId": 1, "startDate": "2026-08-25",
               "startTime": "09:00:00", "timeSpentSeconds": 1800, "description": "x"}
    assert client.create_worklog(payload) == 555
    client.delete_worklog(555)
    assert t.calls[0][:2] == ("POST", "https://api.eu.tempo.io/4/worklogs")
    assert t.calls[0][2]["Authorization"] == "Bearer tok"
    assert t.calls[0][3] == payload
    assert t.calls[1][:2] == ("DELETE", "https://api.eu.tempo.io/4/worklogs/555")


def test_tempo_list_paginates():
    page1 = {"results": [{"tempoWorklogId": 1}], "metadata": {"next": "https://api.eu.tempo.io/4/worklogs/user/a?from=2026-08-25&to=2026-08-25&offset=50&limit=50"}}
    page2 = {"results": [{"tempoWorklogId": 2}], "metadata": {}}
    t = FakeTransport([(200, page1), (200, page2)])
    res = TempoClient("https://api.eu.tempo.io", "tok", t).worklogs_for_user("a", date(2026, 8, 25))
    assert [r["tempoWorklogId"] for r in res] == [1, 2]
    assert t.calls[0][1] == "https://api.eu.tempo.io/4/worklogs/user/a?from=2026-08-25&to=2026-08-25&limit=50"


def test_tempo_401_hint():
    t = FakeTransport([(401, {"errors": [{"message": "Unauthorized"}]})])
    with pytest.raises(HttpError) as exc:
        TempoClient("https://api.tempo.io", "tok", t).create_worklog({})
    assert "region" in str(exc.value).lower()


def test_slots_from_worklogs_in_local_tz():
    results = [
        {"tempoWorklogId": 1, "startDate": "2026-08-25", "startTime": "08:00:00", "timeSpentSeconds": 3600,
         "issue": {"id": 10042}, "description": "ADA-470: thing"},
        {"tempoWorklogId": 2, "startDate": "2026-08-24", "startTime": "08:00:00", "timeSpentSeconds": 3600,
         "issue": {"id": 1}, "description": "other day"},
    ]
    slots = slots_from_worklogs(results, ZoneInfo("UTC"), date(2026, 8, 25))
    assert len(slots) == 1
    assert (slots[0].start.hour, slots[0].end.hour, slots[0].ticket) == (8, 9, "ADA-470: thing")


class _FakeUrlResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeUrlResponse":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def _no_sleep(monkeypatch):
    monkeypatch.setattr("tempo_log.http.time.sleep", lambda *a, **k: None)


def test_urllib_transport_success_json(monkeypatch):
    _no_sleep(monkeypatch)
    captured = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return _FakeUrlResponse(200, json.dumps({"ok": True}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()

    result = transport.request("GET", "https://x/y", {"Authorization": "Bearer tok"}, None)
    assert result == (200, {"ok": True})
    req = captured[-1]
    assert req.get_header("Accept") == "application/json"
    assert req.get_header("Authorization") == "Bearer tok"
    assert req.get_header("Content-type") is None

    result = transport.request("POST", "https://x/y", {"Authorization": "Bearer tok"}, {"a": 1})
    assert result == (200, {"ok": True})
    assert captured[-1].get_header("Content-type") == "application/json"


def test_urllib_transport_4xx_no_retry(monkeypatch):
    _no_sleep(monkeypatch)
    url = "https://x/y"
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        raise urllib.error.HTTPError(url, 404, "nf", {}, io.BytesIO(json.dumps({"message": "nope"}).encode()))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()

    result = transport.request("GET", url, {}, None)
    assert len(calls) == 1
    assert result == (404, {"message": "nope"})


def test_urllib_transport_5xx_retries_once_then_returns(monkeypatch):
    _no_sleep(monkeypatch)
    url = "https://x/y"
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        raise urllib.error.HTTPError(url, 503, "unavailable", {}, io.BytesIO(json.dumps({"message": "down"}).encode()))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()

    status, body = transport.request("GET", url, {}, None)
    assert len(calls) == 2
    assert status == 503


def test_urllib_transport_5xx_then_success(monkeypatch):
    _no_sleep(monkeypatch)
    url = "https://x/y"
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 503, "unavailable", {}, io.BytesIO(json.dumps({"message": "down"}).encode()))
        return _FakeUrlResponse(200, json.dumps({"ok": True}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()

    status, body = transport.request("GET", url, {}, None)
    assert len(calls) == 2
    assert (status, body) == (200, {"ok": True})


def test_urllib_transport_network_error_becomes_http_error(monkeypatch):
    _no_sleep(monkeypatch)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()

    with pytest.raises(HttpError) as exc:
        transport.request("GET", "https://x/y", {}, None)
    assert exc.value.status == 0
    assert "network" in str(exc.value).lower()


def test_extract_message_dict_errors():
    err = HttpError(400, "u", {"errors": {"summary": "required"}})
    assert "summary: required" in str(err)


def test_tempo_pagination_loop_detected():
    first_url = "https://api.eu.tempo.io/4/worklogs/user/a?from=2026-08-25&to=2026-08-25&limit=50"
    page = {"results": [], "metadata": {"next": first_url}}
    t = FakeTransport([(200, page)])
    with pytest.raises(HttpError, match="pagination"):
        TempoClient("https://api.eu.tempo.io", "tok", t).worklogs_for_user("a", date(2026, 8, 25))
