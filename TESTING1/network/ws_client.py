"""
DrowsiGuard — WebSocket Client (Scaffold / Deferred)
2-way WebSocket connection to backend.
STATUS: DEFERRED until local pipeline is stable.
"""
import json
import threading
import time

from utils.logger import get_logger
import config

logger = get_logger("network.ws_client")


class WSClient:
    """WebSocket client with auto-reconnect and local queue support.

    Deferred for now — local pipeline must be stable first.
    When activated, connects to the WebQuanLi backend and:
    - sends: hardware, driver, session_start, session_end, alert, gps, face_mismatch, ota_status
    - receives: test_alert, update_software
    """

    def __init__(self, on_command=None):
        self._url = config.WS_SERVER_URL
        self._on_command = on_command
        self._connected = False
        self._running = False
        self._thread = None
        logger.info(f"WSClient initialized (deferred) — target: {self._url}")

    def start(self):
        if not config.FEATURES.get("websocket"):
            logger.info("WebSocket disabled via feature flag")
            return
        logger.warning("WSClient start() — DEFERRED (local pipeline not yet validated)")

    def stop(self):
        self._running = False
        self._connected = False

    def send(self, msg_type: str, data: dict):
        """Queue a message for sending. Uses key 'level' for alerts (not 'alert_level')."""
        if not self._connected:
            logger.debug(f"WSClient not connected, message queued: type={msg_type}")
            # TODO: push to local_queue
            return
        # TODO: ws.send_json
        logger.debug(f"WSClient send: type={msg_type}")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def test_connect(self):
        """Quick connection test — DEFERRED."""
        logger.warning("WSClient test_connect — DEFERRED")
        return False
