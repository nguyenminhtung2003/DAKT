"""
DrowsiGuard — OTA Handler (Scaffold / Deferred)
Safe file-level OTA: download -> py_compile -> backup -> replace -> restart -> rollback.
STATUS: DEFERRED for V1.
"""
from utils.logger import get_logger

logger = get_logger("network.ota_handler")


class OTAHandler:
    """Safe OTA handler — DEFERRED.

    V1 scope (when implemented):
    1. Download file to /tmp
    2. py_compile check
    3. Backup current file
    4. Replace target
    5. Restart systemd service
    6. Rollback on failure
    7. Report ota_status
    """

    def __init__(self, on_status=None):
        self._on_status = on_status
        logger.info("OTAHandler initialized — DEFERRED")

    def handle_update_command(self, command: dict):
        """Process update_software command from backend."""
        logger.warning("OTA update_software received — DEFERRED (not implemented in this phase)")
        if self._on_status:
            self._on_status({"status": "DEFERRED", "reason": "OTA not active in current phase"})
