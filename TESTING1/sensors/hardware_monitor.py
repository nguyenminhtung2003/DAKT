"""
DrowsiGuard — Hardware Monitor
Aggregates health status of all connected hardware.
Reports honest status — does NOT fake success for missing hardware.
"""
import time

from utils.logger import get_logger
import config

logger = get_logger("sensors.hardware_monitor")


class HardwareMonitor:
    """Periodically samples hardware health and creates status payload."""

    def __init__(self, camera=None, rfid=None, gps=None, ws_client=None):
        self._camera = camera
        self._rfid = rfid
        self._gps = gps
        self._ws_client = ws_client

    def snapshot(self) -> dict:
        """Return current hardware status dict matching Backend schema.

        Uses key "level" (not "alert_level") to match WebQuanLi backend expectation.
        """
        return {
            "power": True,  # Jetson is running = power ok (no external sensor)
            "camera": self._check_camera(),
            "rfid": self._check_rfid(),
            "gps": self._check_gps(),
            "speaker": self._check_speaker(),
            "cellular": self._check_cellular(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    def _check_camera(self) -> bool:
        if self._camera is None:
            return False
        try:
            return self._camera.is_alive
        except Exception:
            return False

    def _check_rfid(self) -> bool:
        if self._rfid is None:
            return False
        try:
            return self._rfid.is_alive
        except Exception:
            return False

    def _check_gps(self) -> bool:
        if not config.HAS_GPS:
            return False
        if self._gps is None:
            return False
        try:
            return self._gps.is_alive
        except Exception:
            return False

    def _check_speaker(self) -> bool:
        # BLOCKED — no speaker hardware confirmed
        return False

    def _check_cellular(self) -> bool:
        if self._ws_client is None:
            return False
        try:
            return self._ws_client.is_connected
        except Exception:
            return False
