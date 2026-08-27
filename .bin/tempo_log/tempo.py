"""Tempo Cloud REST v4 client: list, create, delete worklogs."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tempo_log.http import HttpError, Transport
from tempo_log.models import Slot

_REGION_HINT = "401 from Tempo usually means the token is wrong or base_url points at the wrong region; try api.eu.tempo.io / api.us.tempo.io"


class TempoClient:
    def __init__(self, base_url: str, token: str, transport: Transport):
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.headers = {"Authorization": f"Bearer {token}"}

    def _call(self, method: str, url: str, body: dict | None = None) -> object:
        status, payload = self.transport.request(method, url, self.headers, body)
        if status >= 400:
            raise HttpError(status, url, payload, hint=_REGION_HINT if status == 401 else "")
        return payload

    def worklogs_for_user(self, account_id: str, day: date) -> list[dict]:
        url = f"{self.base_url}/4/worklogs/user/{account_id}?from={day.isoformat()}&to={day.isoformat()}&limit=50"
        results: list[dict] = []
        while url:
            page = self._call("GET", url)
            if not isinstance(page, dict):
                break
            results.extend(page.get("results", []))
            url = (page.get("metadata") or {}).get("next")
        return results

    def create_worklog(self, payload: dict) -> int:
        body = self._call("POST", f"{self.base_url}/4/worklogs", payload)
        if not isinstance(body, dict) or "tempoWorklogId" not in body:
            raise HttpError(200, f"{self.base_url}/4/worklogs", body, hint="response had no tempoWorklogId")
        return int(body["tempoWorklogId"])

    def delete_worklog(self, worklog_id: int) -> None:
        self._call("DELETE", f"{self.base_url}/4/worklogs/{worklog_id}")


def slots_from_worklogs(results: list[dict], tz: ZoneInfo, day: date) -> list[Slot]:
    """Existing worklogs on the local day as occupied slots. Tempo stores startDate/startTime in the user's Tempo timezone; we treat them as local."""
    slots: list[Slot] = []
    for w in results:
        try:
            start_dt = datetime.combine(date.fromisoformat(w["startDate"]), time.fromisoformat(w.get("startTime") or "00:00:00"))
        except (KeyError, ValueError):
            continue
        if start_dt.date() != day:
            continue
        end_dt = start_dt + timedelta(seconds=int(w.get("timeSpentSeconds", 0)))
        end_t = end_dt.time() if end_dt.date() == day else time(23, 59, 59)
        label = str(w.get("description") or "").strip() or f"issue {w.get('issue', {}).get('id', '?')}"
        slots.append(Slot(start=start_dt.time(), end=end_t, ticket=label))
    slots.sort(key=lambda s: s.start)
    return slots
