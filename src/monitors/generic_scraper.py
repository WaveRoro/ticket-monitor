from __future__ import annotations

import difflib
import hashlib
import logging
import re
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..config import ScraperEvent
from ..notifier import DiscordNotifier
from ..state import State

log = logging.getLogger(__name__)

# Honest UA — identifies this as a personal monitoring script, not a browser.
USER_AGENT = (
    "TicketMonitorBot/1.0 (personal availability watcher; "
    "contact: set your email in the code)"
)
REQUEST_TIMEOUT = 20

_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _get_robots(url: str) -> urllib.robotparser.RobotFileParser | None:
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root in _robots_cache:
        return _robots_cache[root]

    robots_url = urljoin(root, "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(robots_url, timeout=10, headers={"User-Agent": USER_AGENT})
        if r.status_code >= 400:
            log.info("no robots.txt at %s (HTTP %s), assuming allow", robots_url, r.status_code)
            _robots_cache[root] = None
            return None
        rp.parse(r.text.splitlines())
        _robots_cache[root] = rp
        return rp
    except requests.RequestException as e:
        log.warning("could not fetch robots.txt for %s: %s (assuming allow)", root, e)
        _robots_cache[root] = None
        return None


def _is_allowed(url: str) -> bool:
    rp = _get_robots(url)
    if rp is None:
        return True
    return rp.can_fetch(USER_AGENT, url)


def _fetch_html(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
            allow_redirects=True,
        )
    except requests.RequestException as e:
        log.error("fetch error for %s: %s", url, e)
        return None
    if r.status_code == 403:
        log.warning("HTTP 403 on %s — site likely blocks bots, giving up on this url", url)
        return None
    if r.status_code == 429:
        log.warning("HTTP 429 on %s — rate limited, skipping this cycle", url)
        return None
    if r.status_code >= 400:
        log.warning("HTTP %s on %s", r.status_code, url)
        return None
    ctype = r.headers.get("Content-Type", "")
    if "html" not in ctype.lower():
        log.warning("unexpected content-type %r for %s", ctype, url)
        return None
    return r.text


def _extract_zone(html: str, selector: str | None) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    if selector:
        nodes = soup.select(selector)
        if not nodes:
            return ""
        text = "\n".join(n.get_text(" ", strip=True) for n in nodes)
    else:
        text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _classify_keywords(
    text: str, available: list[str], soldout: list[str]
) -> str:
    low = text.lower()
    has_avail = any(k.lower() in low for k in available)
    has_sold = any(k.lower() in low for k in soldout)
    if has_avail and not has_sold:
        return "available"
    if has_sold and not has_avail:
        return "soldout"
    if has_avail and has_sold:
        return "mixed"
    return "unknown"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _short_diff(old: str, new: str, max_chars: int = 800) -> str:
    old_lines = old.split(". ")
    new_lines = new.split(". ")
    diff = list(
        difflib.unified_diff(old_lines, new_lines, lineterm="", n=1)
    )[2:]  # drop the file headers
    joined = "\n".join(diff)
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n… (diff tronqué)"
    return joined or "(diff vide)"


def check_scraper_event(
    event: ScraperEvent,
    state: State,
    notifier: DiscordNotifier,
) -> None:
    log.info("[%s] checking scraper url %s", event.id, event.url)

    if not _is_allowed(event.url):
        log.warning("[%s] robots.txt disallows %s — skipping", event.id, event.url)
        return

    html = _fetch_html(event.url)
    if html is None:
        return

    text = _extract_zone(html, event.selector)
    if not text:
        log.error(
            "[%s] ALERT: zone extraction returned empty (selector=%r) — site HTML may have changed",
            event.id,
            event.selector,
        )
        # notify once so a broken selector doesn't just silently stop working
        prev = state.get(event.id)
        if prev.get("last_broken") is not True:
            notifier.send(
                f"⚠️ {event.name} — sélecteur cassé",
                f"Le sélecteur `{event.selector or '(page entière)'}` "
                f"ne renvoie rien sur {event.url}.\n"
                f"Le HTML du site a probablement changé — mets à jour events.yaml.",
            )
        state.set(
            event.id,
            {
                **prev,
                "mode": "scraper",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "last_broken": True,
            },
        )
        return

    prev = state.get(event.id)
    entry: dict = {
        "mode": "scraper",
        "method": event.method,
        "last_check": datetime.now(timezone.utc).isoformat(),
        "last_notified": prev.get("last_notified"),
        "last_broken": False,
    }

    if event.method == "keywords":
        cls = _classify_keywords(text, event.keywords_available, event.keywords_soldout)
        entry["last_keyword_state"] = cls
        prev_cls = prev.get("last_keyword_state")
        if prev_cls is None:
            log.info("[%s] first check, keyword_state=%s (no notif)", event.id, cls)
        elif prev_cls != cls:
            log.info("[%s] keyword_state changed: %s -> %s", event.id, prev_cls, cls)
            title = f"🎟️ {event.name} — {prev_cls} → {cls}"
            body = (
                f"Page : {event.url}\n"
                f"État précédent : `{prev_cls}` · nouveau : `{cls}`\n"
                f"Méthode : mots-clés"
            )
            if notifier.send(title, body):
                entry["last_notified"] = entry["last_check"]
        else:
            log.info("[%s] no change, keyword_state=%s", event.id, cls)

    elif event.method == "hash":
        h = _hash(text)
        entry["last_hash"] = h
        entry["last_text_preview"] = text[:400]
        prev_hash = prev.get("last_hash")
        if prev_hash is None:
            log.info("[%s] first check, hash=%s (no notif)", event.id, h)
        elif prev_hash != h:
            log.info("[%s] hash changed: %s -> %s", event.id, prev_hash, h)
            diff = _short_diff(prev.get("last_text_preview", ""), text[:2000])
            title = f"🎟️ {event.name} — page modifiée"
            body = (
                f"Page : {event.url}\n"
                f"Hash : `{prev_hash}` → `{h}`\n"
                f"Diff (extrait) :\n```diff\n{diff}\n```"
            )
            if notifier.send(title, body):
                entry["last_notified"] = entry["last_check"]
        else:
            log.info("[%s] no change, hash=%s", event.id, h)

    state.set(event.id, entry)


def check_all_scrapers(
    events: list[ScraperEvent],
    state: State,
    notifier: DiscordNotifier,
) -> None:
    for ev in events:
        try:
            check_scraper_event(ev, state, notifier)
        except Exception as e:  # noqa: BLE001
            log.exception("[%s] unexpected error: %s", ev.id, e)
