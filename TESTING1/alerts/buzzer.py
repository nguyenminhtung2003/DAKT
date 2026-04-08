"""
DrowsiGuard — Buzzer Driver (BLOCKED — Hardware Not Available)
STATUS: BLOCKED BY MISSING HARDWARE. GPIO pin is placeholder.
"""
from utils.logger import get_logger
import config

logger = get_logger("alerts.buzzer")


class Buzzer:
    """Buzzer control via GPIO relay. BLOCKED until hardware is wired."""

    def __init__(self):
        self._active = False
        if not config.HAS_BUZZER:
            logger.warning("Buzzer initialized — BLOCKED BY MISSING HARDWARE")

    def beep(self, count: int = 1):
        if not config.HAS_BUZZER:
            logger.info(f"Buzzer beep({count}) — BLOCKED (no hardware)")
            return
        # TODO: GPIO pulse implementation

    def beep_pattern(self, pattern: str = "intermittent"):
        if not config.HAS_BUZZER:
            logger.info(f"Buzzer pattern({pattern}) — BLOCKED (no hardware)")
            return
        # TODO: threaded pattern playback

    def on(self):
        if not config.HAS_BUZZER:
            return
        # TODO: GPIO high

    def off(self):
        self._active = False
        if not config.HAS_BUZZER:
            return
        # TODO: GPIO low

    def cleanup(self):
        self.off()
