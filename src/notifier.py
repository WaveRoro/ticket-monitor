from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

DISCORD_MAX_CONTENT = 1900  # leave headroom under the 2000-char Discord limit


class DiscordNotifier:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not self.webhook_url:
            log.warning("DISCORD_WEBHOOK_URL not set — notifications will be skipped")

    def send(self, title: str, body: str) -> bool:
        if not self.webhook_url:
            log.info("[DRY-RUN NOTIF] %s\n%s", title, body)
            return False
        content = f"**{title}**\n{body}"
        if len(content) > DISCORD_MAX_CONTENT:
            content = content[: DISCORD_MAX_CONTENT - 20] + "\n… (tronqué)"
        try:
            r = requests.post(
                self.webhook_url,
                json={"content": content},
                timeout=10,
            )
            if r.status_code >= 300:
                log.error("discord webhook failed: %s %s", r.status_code, r.text[:200])
                return False
            log.info("discord notif sent: %s", title)
            return True
        except requests.RequestException as e:
            log.error("discord webhook error: %s", e)
            return False
