from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class State:
    def __init__(self, path: str | Path = "state.json"):
        self.path = Path(path)
        self._data: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.info("no existing state at %s, starting fresh", self.path)
            self._data = {"events": {}}
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            if "events" not in self._data:
                self._data["events"] = {}
        except json.JSONDecodeError as e:
            log.error("state file corrupted (%s), starting fresh", e)
            self._data = {"events": {}}

    def get(self, event_id: str) -> dict[str, Any]:
        return self._data["events"].get(event_id, {})

    def set(self, event_id: str, entry: dict[str, Any]) -> None:
        current = self._data["events"].get(event_id, {})
        if current != entry:
            self._data["events"][event_id] = entry
            self._dirty = True

    def save(self) -> bool:
        if not self._dirty:
            return False
        self.path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("state saved to %s", self.path)
        self._dirty = False
        return True
