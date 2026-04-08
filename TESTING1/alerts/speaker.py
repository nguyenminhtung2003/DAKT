"""
DrowsiGuard — Speaker/Audio Driver (BLOCKED — Hardware Not Confirmed)
STATUS: BLOCKED BY MISSING HARDWARE.
"""
from utils.logger import get_logger
import config

logger = get_logger("alerts.speaker")


class Speaker:
    """Audio alert playback. BLOCKED until audio output is confirmed on Jetson."""

    def __init__(self):
        if not config.HAS_SPEAKER:
            logger.warning("Speaker initialized — BLOCKED BY MISSING HARDWARE")

    def play_alert(self, level: int):
        if not config.HAS_SPEAKER:
            logger.info(f"Speaker play_alert(level={level}) — BLOCKED (no hardware)")
            return
        # TODO: aplay or subprocess playback of sounds/alert_levelX.wav

    def stop(self):
        if not config.HAS_SPEAKER:
            return

    def test_tone(self) -> bool:
        """Play a test tone and return True if successful."""
        if not config.HAS_SPEAKER:
            logger.info("Speaker test_tone — BLOCKED (no hardware)")
            return False
        # TODO: implement
        return False

    def cleanup(self):
        self.stop()
