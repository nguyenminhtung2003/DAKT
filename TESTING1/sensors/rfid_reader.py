"""
DrowsiGuard — RFID Reader (USB HID Keyboard-like Device)
This is NOT an SPI/UART MFRC522. It's a USB reader that behaves like
a keyboard, typing the UID as keystrokes followed by Enter.

Implementation uses Linux evdev to capture input exclusively,
preventing the UID from leaking into random terminal/UI fields.
"""
import threading
import time

from utils.logger import get_logger
import config

logger = get_logger("sensors.rfid_reader")

# Try importing evdev (Linux only)
try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False
    logger.warning("evdev not available — RFID reader will not work on this platform")


# evdev keycode to character mapping for numeric UIDs
_KEY_MAP = {
    ecodes.KEY_0: "0", ecodes.KEY_1: "1", ecodes.KEY_2: "2",
    ecodes.KEY_3: "3", ecodes.KEY_4: "4", ecodes.KEY_5: "5",
    ecodes.KEY_6: "6", ecodes.KEY_7: "7", ecodes.KEY_8: "8",
    ecodes.KEY_9: "9",
    ecodes.KEY_A: "A", ecodes.KEY_B: "B", ecodes.KEY_C: "C",
    ecodes.KEY_D: "D", ecodes.KEY_E: "E", ecodes.KEY_F: "F",
} if HAS_EVDEV else {}


class RFIDReader:
    """USB HID RFID reader via Linux evdev.

    Responsibilities:
    - Read UID from USB HID input events
    - Debounce repeated scans
    - Emit rfid_scanned callback
    - Does NOT open camera or run face verification
    """

    def __init__(self, device_path: str = None, callback=None):
        """
        Args:
            device_path: e.g. "/dev/input/event3". If None, will attempt auto-detect.
            callback: function(uid: str) called when a card is scanned.
        """
        self._device_path = device_path or config.RFID_DEVICE_PATH
        self._callback = callback
        self._debounce_sec = config.RFID_DEBOUNCE_SEC
        self._grab_exclusive = config.RFID_GRAB_EXCLUSIVE
        self._running = False
        self._thread = None
        self._device = None
        self._last_uid = None
        self._last_scan_time = 0.0

    def start(self):
        if not HAS_EVDEV:
            logger.error("Cannot start RFID reader: evdev not installed")
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True,
                                        name="rfid-reader")
        self._thread.start()
        logger.info("RFID reader thread started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        if self._device and self._grab_exclusive:
            try:
                self._device.ungrab()
            except Exception:
                pass
        logger.info("RFID reader stopped")

    @property
    def is_alive(self) -> bool:
        return self._running and self._device is not None

    def _find_device(self) -> str:
        """Auto-detect RFID reader from /dev/input/event* devices."""
        if self._device_path:
            return self._device_path

        logger.info("Auto-detecting RFID USB HID device...")
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            name_lower = dev.name.lower()
            # Common USB RFID reader identifiers
            if any(kw in name_lower for kw in ["rfid", "hid", "card", "reader", "rf"]):
                logger.info(f"Found RFID device: {dev.path} — {dev.name}")
                return dev.path

        # Fallback: list all devices for manual selection
        if devices:
            logger.warning("No RFID-specific device found. Available input devices:")
            for dev in devices:
                logger.warning(f"  {dev.path}: {dev.name} (phys={dev.phys})")
        else:
            logger.error("No input devices found at all")
        return None

    def _read_loop(self):
        while self._running:
            try:
                path = self._find_device()
                if not path:
                    logger.error("RFID device not found, retrying in 5s...")
                    time.sleep(5.0)
                    continue

                self._device = InputDevice(path)
                logger.info(f"RFID reader opened: {self._device.name} at {path}")

                if self._grab_exclusive:
                    try:
                        self._device.grab()
                        logger.info("Exclusive grab acquired on RFID device")
                    except Exception as e:
                        logger.warning(f"Could not grab device exclusively: {e}")

                uid_buffer = []

                for event in self._device.read_loop():
                    if not self._running:
                        break

                    if event.type != ecodes.EV_KEY:
                        continue

                    key_event = categorize(event)
                    if key_event.keystate != 1:  # key down only
                        continue

                    keycode = key_event.scancode

                    if keycode == ecodes.KEY_ENTER:
                        # UID complete
                        uid = "".join(uid_buffer).strip()
                        uid_buffer.clear()
                        if uid:
                            self._process_uid(uid)
                    elif keycode in _KEY_MAP:
                        uid_buffer.append(_KEY_MAP[keycode])

            except OSError as e:
                logger.warning(f"RFID device error: {e}, reconnecting in 3s...")
                self._device = None
                time.sleep(3.0)
            except Exception as e:
                logger.error(f"RFID unexpected error: {e}")
                self._device = None
                time.sleep(3.0)

    def _process_uid(self, uid: str):
        now = time.time()
        # Debounce
        if uid == self._last_uid and (now - self._last_scan_time) < self._debounce_sec:
            logger.debug(f"RFID debounce: ignoring repeated scan of {uid}")
            return

        self._last_uid = uid
        self._last_scan_time = now
        logger.info(f"RFID scanned: UID={uid}")

        if self._callback:
            try:
                self._callback(uid)
            except Exception as e:
                logger.error(f"RFID callback error: {e}")
