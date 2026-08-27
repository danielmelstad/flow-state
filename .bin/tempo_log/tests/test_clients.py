from datetime import date
from zoneinfo import ZoneInfo

import pytest

from tempo_log.http import HttpError, TokenError, token_from_env
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
