"""
DrowsiGuard — Alert Manager (3-Level Local Alerting)
Consumes FaceMetrics from FaceAnalyzer and decides alert level.
Delegates hardware output to buzzer/led/speaker drivers.
"""
import time
from collections import deque

from utils.logger import get_logger
import config

logger = get_logger("alerts.alert_manager")


class AlertLevel:
    NONE = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3

    NAMES = {0: "NONE", 1: "LEVEL_1", 2: "LEVEL_2", 3: "LEVEL_3"}


class AlertEvent:
    """Represents a state change in alert level."""
    __slots__ = ("level", "ear", "mar", "pitch", "perclos", "timestamp")

    def __init__(self, level, ear, mar, pitch, perclos):
        self.level = level
        self.ear = ear
        self.mar = mar
        self.pitch = pitch
        self.perclos = perclos
        self.timestamp = time.time()


class AlertManager:
    """3-level drowsiness alert logic with cooldown and hysteresis."""

    def __init__(self, buzzer=None, led=None, speaker=None, on_alert=None):
        self._buzzer = buzzer
        self._led = led
        self._speaker = speaker
        self._on_alert = on_alert  # callback for event dispatch

        self._current_level = AlertLevel.NONE
        self._level_start_time = 0.0
        self._last_alert_time = 0.0

        # EAR low tracking
        self._ear_low_start = None

        # Yawn tracking
        self._yawn_times = deque()
        self._yawning = False

        # Level 2 repeat tracking for Level 3 escalation
        self._level2_times = deque()

        # Calibration baselines (set by calibration module)
        self._ear_threshold = config.EAR_THRESHOLD
        self._pitch_threshold = config.PITCH_DELTA_THRESHOLD

        logger.info("AlertManager initialized")

    def set_calibrated_thresholds(self, ear_baseline: float, pitch_neutral: float):
        """Apply calibrated thresholds from session start."""
        self._ear_threshold = min(config.EAR_THRESHOLD, 0.75 * ear_baseline)
        self._pitch_threshold = config.PITCH_DELTA_THRESHOLD
        logger.info(f"Calibrated thresholds: EAR={self._ear_threshold:.3f}, pitch_neutral={pitch_neutral:.1f}")

    def update(self, metrics, perclos: float):
        """Process metrics and determine alert level.

        Args:
            metrics: FaceMetrics from FaceAnalyzer
            perclos: current PERCLOS value
        """
        now = time.time()

        if not metrics.face_present:
            # No face — treat as potentially dangerous but don't immediately alert
            return

        ear = metrics.ear
        mar = metrics.mar
        pitch = metrics.pitch

        # ── Track EAR low duration ──────────────────────────
        if ear < self._ear_threshold:
            if self._ear_low_start is None:
                self._ear_low_start = now
            ear_low_duration = now - self._ear_low_start
        else:
            self._ear_low_start = None
            ear_low_duration = 0.0

        # ── Track yawns ─────────────────────────────────────
        is_yawning = mar > config.MAR_THRESHOLD
        if is_yawning and not self._yawning:
            self._yawn_times.append(now)
        self._yawning = is_yawning
        # Clean old yawns
        while self._yawn_times and (now - self._yawn_times[0]) > config.YAWN_COUNT_WINDOW:
            self._yawn_times.popleft()

        # ── Determine new level ─────────────────────────────
        new_level = AlertLevel.NONE

        # Level 3: extreme drowsiness
        if ear_low_duration >= config.LEVEL3_DURATION:
            new_level = AlertLevel.LEVEL_3
        else:
            # Check Level 2 repeat escalation
            while self._level2_times and (now - self._level2_times[0]) > 120:
                self._level2_times.popleft()
            if len(self._level2_times) >= 3:
                new_level = AlertLevel.LEVEL_3

        if new_level < AlertLevel.LEVEL_3:
            # Level 2
            if (ear_low_duration >= config.LEVEL2_DURATION
                    or pitch < self._pitch_threshold
                    or perclos > config.PERCLOS_THRESHOLD):
                new_level = max(new_level, AlertLevel.LEVEL_2)

        if new_level < AlertLevel.LEVEL_2:
            # Level 1
            if (ear_low_duration >= config.LEVEL1_DURATION
                    or len(self._yawn_times) >= config.YAWN_COUNT_THRESHOLD):
                new_level = max(new_level, AlertLevel.LEVEL_1)

        # ── Apply level change with cooldown ────────────────
        if new_level != self._current_level:
            if (now - self._last_alert_time) >= config.ALERT_COOLDOWN or new_level > self._current_level:
                old_level = self._current_level
                self._current_level = new_level
                self._last_alert_time = now
                self._level_start_time = now

                if new_level == AlertLevel.LEVEL_2:
                    self._level2_times.append(now)

                logger.info(f"Alert level changed: {AlertLevel.NAMES[old_level]} -> {AlertLevel.NAMES[new_level]}")
                self._activate_outputs(new_level)

                if self._on_alert:
                    event = AlertEvent(new_level, ear, mar, pitch, perclos)
                    try:
                        self._on_alert(event)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")

    def _activate_outputs(self, level: int):
        """Trigger hardware outputs for alert level."""
        if level == AlertLevel.NONE:
            if self._buzzer:
                self._buzzer.off()
            if self._led:
                self._led.off()
            if self._speaker:
                self._speaker.stop()
        elif level == AlertLevel.LEVEL_1:
            logger.info("[ALERT L1] Buzzer intermittent + LED warning")
            if self._buzzer:
                self._buzzer.beep_pattern("intermittent")
            if self._led:
                self._led.warning()
        elif level == AlertLevel.LEVEL_2:
            logger.info("[ALERT L2] Buzzer continuous + Speaker + LED danger")
            if self._buzzer:
                self._buzzer.beep_pattern("continuous")
            if self._speaker:
                self._speaker.play_alert(2)
            if self._led:
                self._led.danger()
        elif level == AlertLevel.LEVEL_3:
            logger.info("[ALERT L3] CRITICAL - Full alarm")
            if self._buzzer:
                self._buzzer.beep_pattern("urgent")
            if self._speaker:
                self._speaker.play_alert(3)
            if self._led:
                self._led.critical()

        # Log if hardware is missing
        if not self._buzzer and level > 0:
            logger.warning(f"[ALERT L{level}] BUZZER BLOCKED — hardware not available")
        if not self._led and level > 0:
            logger.warning(f"[ALERT L{level}] LED BLOCKED — hardware not available")
        if not self._speaker and level > 0:
            logger.warning(f"[ALERT L{level}] SPEAKER BLOCKED — hardware not available")

    @property
    def current_level(self) -> int:
        return self._current_level

    @property
    def current_level_name(self) -> str:
        return AlertLevel.NAMES.get(self._current_level, "UNKNOWN")

    def reset(self):
        """Reset alert state (e.g. when session ends)."""
        self._current_level = AlertLevel.NONE
        self._ear_low_start = None
        self._yawn_times.clear()
        self._level2_times.clear()
        self._activate_outputs(AlertLevel.NONE)
        logger.info("AlertManager reset")
