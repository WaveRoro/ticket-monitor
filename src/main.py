from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import ScraperEvent, TicketmasterEvent, load_events
from .monitors.generic_scraper import check_all_scrapers
from .monitors.ticketmaster import check_all_ticketmaster
from .notifier import DiscordNotifier
from .state import State


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def main() -> int:
    load_dotenv()
    _setup_logging()
    log = logging.getLogger("main")

    root = Path(__file__).resolve().parent.parent
    events = load_events(root / "events.yaml")
    if not events:
        log.info("no events configured, nothing to do")
        return 0

    tm_events = [e for e in events if isinstance(e, TicketmasterEvent)]
    sc_events = [e for e in events if isinstance(e, ScraperEvent)]
    log.info(
        "starting check: %d ticketmaster events, %d scraper events",
        len(tm_events),
        len(sc_events),
    )

    state = State(root / "state.json")
    notifier = DiscordNotifier()

    if tm_events:
        check_all_ticketmaster(tm_events, state, notifier)
    if sc_events:
        check_all_scrapers(sc_events, state, notifier)

    changed = state.save()
    log.info("run complete, state changed=%s", changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
