"""
DrowsiGuard — LED Driver (BLOCKED — Hardware Not Available)
STATUS: BLOCKED BY MISSING HARDWARE. GPIO pins are placeholders.
"""
from utils.logger import get_logger
import config

logger = get_logger("alerts.led")


class LEDController:
    """LED warning/danger/critical control. BLOCKED until hardware wired."""

    def __init__(self):
        if not config.HAS_LED:
            logger.warning("LEDController initialized — BLOCKED BY MISSING HARDWARE")

    def warning(self):
        if not config.HAS_LED:
            logger.info("LED warning — BLOCKED (no hardware)")
            return

    def danger(self):
        if not config.HAS_LED:
            logger.info("LED danger — BLOCKED (no hardware)")
            return

    def critical(self):
        if not config.HAS_LED:
            logger.info("LED critical — BLOCKED (no hardware)")
            return

    def off(self):
        if not config.HAS_LED:
            return

    def cleanup(self):
        self.off()
