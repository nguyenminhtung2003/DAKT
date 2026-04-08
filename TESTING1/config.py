"""
DrowsiGuard V1 — Configuration
All tunable parameters in one place.
GPIO pins are PLACEHOLDERS until real wiring is confirmed.
"""
import os

# ─── Device Identity ───────────────────────────────────────
DEVICE_ID = os.getenv("DROWSIGUARD_DEVICE_ID", "JETSON-001")

# ─── Camera ────────────────────────────────────────────────
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
CAMERA_FPS = 30
AI_TARGET_FPS = 12
MAX_NUM_FACES = 1

GSTREAMER_PIPELINE = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
    "nvvidconv flip-method=0 ! "
    "video/x-raw, width={w}, height={h}, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! "
    "appsink drop=true sync=false"
).format(w=CAMERA_WIDTH, h=CAMERA_HEIGHT)

CAMERA_RECONNECT_DELAY = 3.0
CAMERA_WATCHDOG_TIMEOUT = 5.0

# ─── Drowsiness Thresholds (default fallback) ─────────────
EAR_THRESHOLD = 0.21
MAR_THRESHOLD = 0.65
PITCH_DELTA_THRESHOLD = -15.0
PERCLOS_THRESHOLD = 0.35

# Smoothing
EAR_SMOOTHING_ALPHA = 0.3
MAR_SMOOTHING_ALPHA = 0.3
PITCH_SMOOTHING_ALPHA = 0.3

# ─── Alert Timing ──────────────────────────────────────────
LEVEL1_DURATION = 2.0
LEVEL2_DURATION = 4.0
LEVEL3_DURATION = 6.0
ALERT_COOLDOWN = 3.0

YAWN_COUNT_WINDOW = 60.0
YAWN_COUNT_THRESHOLD = 2

PERCLOS_WINDOW = 30.0

# ─── Calibration ──────────────────────────────────────────
CALIBRATION_DURATION = 7.0
CALIBRATION_MIN_SAMPLES = 30

# ─── Reverification ───────────────────────────────────────
REVERIFY_INTERVAL = 300
REVERIFY_FAST_INTERVAL = 180
REVERIFY_MAX_CONSECUTIVE_FAILS = 2

# ─── Hardware Pins (PLACEHOLDER — not confirmed) ──────────
# These MUST be updated once real wiring is done.
HAS_BUZZER = False
HAS_LED = False
HAS_SPEAKER = False
HAS_GPS = False

BUZZER_RELAY_PIN = 18      # placeholder
LED_WARNING_PIN = 16       # placeholder
LED_CRITICAL_PIN = 22      # placeholder

# ─── GPS ───────────────────────────────────────────────────
GPS_PORT = "/dev/ttyTHS1"
GPS_BAUDRATE = 9600
GPS_SEND_INTERVAL = 3.0

# ─── RFID (USB HID) ───────────────────────────────────────
RFID_DEVICE_PATH = None  # auto-detect or set to e.g. "/dev/input/event3"
RFID_DEBOUNCE_SEC = 2.0
RFID_GRAB_EXCLUSIVE = True

# ─── WebSocket ─────────────────────────────────────────────
WS_SERVER_URL = os.getenv(
    "DROWSIGUARD_WS_URL",
    "ws://SERVER_IP:8000/ws/jetson/{device_id}"
).format(device_id=DEVICE_ID)
WS_RECONNECT_BASE = 1.0
WS_RECONNECT_MAX = 60.0

# ─── Local Store ───────────────────────────────────────────
QUEUE_DB_PATH = os.path.join(os.path.dirname(__file__), "storage", "local_events.db")
QUEUE_MAX_RECORDS = 1000

# ─── Hardware Monitor ─────────────────────────────────────
HW_REPORT_INTERVAL = 5.0

# ─── OTA ───────────────────────────────────────────────────
OTA_DOWNLOAD_DIR = "/tmp/drowsiguard_ota"
OTA_PROJECT_DIR = os.path.dirname(__file__)
OTA_BACKUP_DIR = os.path.join(os.path.dirname(__file__), "_backup")

# ─── Logging ───────────────────────────────────────────────
LOG_LEVEL = os.getenv("DROWSIGUARD_LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "drowsiguard.log")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

# ─── Feature Flags for deferred hardware ──────────────────
FEATURES = {
    "camera": True,
    "drowsiness": True,
    "rfid": True,
    "gps": HAS_GPS,
    "buzzer": HAS_BUZZER,
    "led": HAS_LED,
    "speaker": HAS_SPEAKER,
    "websocket": False,   # deferred until local pipeline stable
    "ota": False,         # deferred
    "face_verify": False, # scaffold only — blocked by missing enrollment data
}
