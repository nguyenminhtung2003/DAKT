"""
DrowsiGuard — GPS Reader (BLOCKED — Hardware Not Available)
Reads GPS GY-NEO 6M V2 from UART, parses NMEA ($GPRMC, $GPGGA).
STATUS: BLOCKED BY MISSING HARDWARE
"""
import threading
import time

from utils.logger import get_logger
import config

logger = get_logger("sensors.gps_reader")


class GPSData:
    __slots__ = ("lat", "lng", "speed", "heading", "fix_ok", "timestamp")

    def __init__(self):
        self.lat = 0.0
        self.lng = 0.0
        self.speed = 0.0
        self.heading = 0.0
        self.fix_ok = False
        self.timestamp = 0.0


class GPSReader:
    """GPS UART reader — currently BLOCKED by missing hardware.

    When hardware is available, validation command:
        python -c "from sensors.gps_reader import GPSReader; g = GPSReader(); print(g.read_once())"
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._latest = GPSData()
        self._module_ok = False
        logger.warning("GPSReader initialized — BLOCKED BY MISSING HARDWARE")

    def start(self):
        if not config.HAS_GPS:
            logger.info("GPS disabled via config (HAS_GPS=False)")
            return
        # TODO: implement UART reading when hardware arrives
        logger.warning("GPS start() — no-op, hardware not available")

    def stop(self):
        self._running = False
        logger.info("GPS stopped")

    @property
    def latest(self) -> GPSData:
        return self._latest

    @property
    def is_alive(self) -> bool:
        return self._module_ok

    def read_once(self) -> dict:
        """Single read for testing — BLOCKED."""
        logger.warning("GPS read_once() — BLOCKED BY MISSING HARDWARE")
        return {"status": "BLOCKED", "reason": "GPS hardware not connected"}
