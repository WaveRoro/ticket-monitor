from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from ..config import TicketmasterEvent
from ..notifier import DiscordNotifier
from ..state import State

log = logging.getLogger(__name__)

TM_BASE = "https://app.ticketmaster.com/discovery/v2"
TM_TIMEOUT = 15

# Quota-friendly minimum spacing between calls in a single run (5 req/sec limit).
INTER_CALL_DELAY_SEC = 0.25


def _tm_get(path: str, api_key: str, **params: Any) -> dict[str, Any] | None:
    url = f"{TM_BASE}/{path}"
    params = {**params, "apikey": api_key}
    try:
        r = requests.get(url, params=params, timeout=TM_TIMEOUT)
    except requests.RequestException as e:
        log.error("ticketmaster network error on %s: %s", path, e)
        return None
    if r.status_code == 429:
        log.warning("ticketmaster rate limited on %s", path)
        return None
    if r.status_code == 404:
        log.warning("ticketmaster event not found: %s", path)
        return None
    if r.status_code >= 300:
        log.error("ticketmaster HTTP %s on %s: %s", r.status_code, path, r.text[:200])
        return None
    return r.json()


def _extract_status(event_json: dict[str, Any]) -> str:
    dates = event_json.get("dates") or {}
    status = (dates.get("status") or {}).get("code")
    return status or "unknown"


def check_ticketmaster_event(
    event: TicketmasterEvent,
    state: State,
    notifier: DiscordNotifier,
    api_key: str | None = None,
) -> None:
    api_key = api_key or os.environ.get("TICKETMASTER_API_KEY", "").strip()
    if not api_key:
        log.error("[%s] no TICKETMASTER_API_KEY set, skipping", event.id)
        return

    log.info("[%s] checking ticketmaster event %s", event.id, event.tm_event_id)
    data = _tm_get(f"events/{event.tm_event_id}.json", api_key=api_key)
    if data is None:
        return
    status = _extract_status(data)
    url = (data.get("url") or "").strip()

    prev = state.get(event.id)
    prev_status = prev.get("last_status")

    entry = {
        "mode": "ticketmaster",
        "last_status": status,
        "last_check": datetime.now(timezone.utc).isoformat(),
        "last_notified": prev.get("last_notified"),
    }

    if prev_status is None:
        log.info("[%s] first check, status=%s (no notif)", event.id, status)
    elif prev_status != status:
        log.info("[%s] status changed: %s -> %s", event.id, prev_status, status)
        title = f"🎟️ {event.name} — statut : {prev_status} → {status}"
        body_lines = [f"Événement Ticketmaster : `{event.tm_event_id}`"]
        if url:
            body_lines.append(f"Lien : {url}")
        body_lines.append(f"Nouveau statut : **{status}**")
        if notifier.send(title, "\n".join(body_lines)):
            entry["last_notified"] = entry["last_check"]
    else:
        log.info("[%s] no change, status=%s", event.id, status)

    state.set(event.id, entry)


def check_all_ticketmaster(
    events: list[TicketmasterEvent],
    state: State,
    notifier: DiscordNotifier,
) -> None:
    for i, ev in enumerate(events):
        if i > 0:
            time.sleep(INTER_CALL_DELAY_SEC)
        try:
            check_ticketmaster_event(ev, state, notifier)
        except Exception as e:  # noqa: BLE001 - want to keep the loop alive
            log.exception("[%s] unexpected error: %s", ev.id, e)
