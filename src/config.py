from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

log = logging.getLogger(__name__)

Mode = Literal["ticketmaster", "scraper"]
ScraperMethod = Literal["keywords", "hash"]


@dataclass
class TicketmasterEvent:
    id: str
    name: str
    tm_event_id: str
    mode: Mode = "ticketmaster"


@dataclass
class ScraperEvent:
    id: str
    name: str
    url: str
    mode: Mode = "scraper"
    method: ScraperMethod = "keywords"
    selector: str | None = None
    keywords_available: list[str] = field(default_factory=list)
    keywords_soldout: list[str] = field(default_factory=list)


EventConfig = TicketmasterEvent | ScraperEvent


def load_events(path: str | Path = "events.yaml") -> list[EventConfig]:
    path = Path(path)
    if not path.exists():
        log.warning("config file %s not found, no events to monitor", path)
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    events: list[EventConfig] = []
    for item in (raw.get("events") or []):
        mode = item.get("mode")
        if mode == "ticketmaster":
            events.append(
                TicketmasterEvent(
                    id=item["id"],
                    name=item["name"],
                    tm_event_id=item["tm_event_id"],
                )
            )
        elif mode == "scraper":
            events.append(
                ScraperEvent(
                    id=item["id"],
                    name=item["name"],
                    url=item["url"],
                    method=item.get("method", "keywords"),
                    selector=item.get("selector"),
                    keywords_available=item.get("keywords_available", []),
                    keywords_soldout=item.get("keywords_soldout", []),
                )
            )
        else:
            log.error("unknown mode %r for event %r, skipping", mode, item.get("id"))
    return events
