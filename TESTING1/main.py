#!/usr/bin/env python3
"""
DrowsiGuard V1 — Main Orchestrator
Entry point for the drowsiness warning system on Jetson Nano A02.

Execution order follows jetson_execution_tasks.md:
1. Initialize logging
2. Initialize state machine (BOOTING)
3. Start camera pipeline (single owner)
4. Start face analyzer (drowsiness)
5. Start alert manager
6. Start RFID reader (USB HID)
7. Transition to IDLE
8. Main loop: process frames, update alerts, handle RFID events

Deferred modules: GPS, WebSocket, OTA, Face Verification (full), Speaker/Buzzer/LED
"""
import signal
import sys
import time
import threading
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from utils.logger import setup_logger, get_logger
from state_machine import StateMachine, State
from camera.capture import CSICamera
from camera.frame_buffer import FrameBuffer
from camera.face_analyzer import FaceAnalyzer
from camera.face_verifier import FaceVerifier, VerifyResult
from alerts.alert_manager import AlertManager, AlertLevel
from alerts.buzzer import Buzzer
from alerts.led import LEDController
from alerts.speaker import Speaker
from sensors.rfid_reader import RFIDReader
from sensors.gps_reader import GPSReader
from sensors.hardware_monitor import HardwareMonitor
from network.ws_client import WSClient
from storage.local_queue import LocalQueue

# ─── Setup ──────────────────────────────────────────────────
root_logger = setup_logger(
    level=config.LOG_LEVEL,
    log_file=config.LOG_FILE,
)
logger = get_logger("main")

# ─── Globals ────────────────────────────────────────────────
shutdown_event = threading.Event()


class DrowsiGuard:
    """Main orchestrator for the drowsiness warning system."""

    def __init__(self):
        logger.info("=" * 60)
        logger.info("DrowsiGuard V1 starting...")
        logger.info(f"Device ID: {config.DEVICE_ID}")
        logger.info(f"Features: {config.FEATURES}")
        logger.info("=" * 60)

        # State Machine
        self.state = StateMachine(on_transition=self._on_state_change)

        # Camera (single owner)
        self.camera = CSICamera()
        self.frame_buffer = FrameBuffer()

        # Drowsiness
        self.face_analyzer = FaceAnalyzer()

        # Alert hardware (scaffold — blocked)
        self.buzzer = Buzzer() if config.FEATURES["buzzer"] else None
        self.led = LEDController() if config.FEATURES["led"] else None
        self.speaker = Speaker() if config.FEATURES["speaker"] else None

        # Alert Manager
        self.alert_manager = AlertManager(
            buzzer=self.buzzer,
            led=self.led,
            speaker=self.speaker,
            on_alert=self._on_alert,
        )

        # RFID
        self.rfid = RFIDReader(callback=self._on_rfid_scan) if config.FEATURES["rfid"] else None

        # GPS (blocked)
        self.gps = GPSReader() if config.FEATURES["gps"] else None

        # Network (deferred)
        self.ws_client = WSClient(on_command=self._on_backend_command) if config.FEATURES["websocket"] else None

        # Storage
        self.local_queue = LocalQueue()

        # Hardware monitor
        self.hw_monitor = HardwareMonitor(
            camera=self.camera,
            rfid=self.rfid,
            gps=self.gps,
            ws_client=self.ws_client,
        )

        # Face Verifier (scaffold)
        self.verifier = FaceVerifier() if config.FEATURES["face_verify"] else None

        # Session state
        self._current_driver_uid = None
        self._session_active = False

        # Performance tracking
        self._frame_count = 0
        self._ai_fps = 0.0

    def run(self):
        """Main entry point."""
        try:
            self._boot()
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Shutdown requested via Ctrl+C")
        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
        finally:
            self._shutdown()

    # ── Boot Sequence ───────────────────────────────────────

    def _boot(self):
        logger.info("BOOT: Starting camera...")
        self.camera.start()
        # Wait for camera to be ready
        for i in range(10):
            time.sleep(0.5)
            if self.camera.is_alive:
                break
        if not self.camera.is_alive:
            logger.error("BOOT: Camera failed to start!")
        else:
            logger.info(f"BOOT: Camera alive, FPS={self.camera.fps:.1f}")

        if self.rfid:
            logger.info("BOOT: Starting RFID reader...")
            self.rfid.start()

        if self.gps:
            logger.info("BOOT: Starting GPS...")
            self.gps.start()

        if self.ws_client:
            logger.info("BOOT: Starting WebSocket...")
            self.ws_client.start()

        # Transition to IDLE
        self.state.transition(State.IDLE, "boot complete")

    # ── Main Loop ───────────────────────────────────────────

    def _main_loop(self):
        logger.info("Entering main loop")
        frame_interval = 1.0 / config.AI_TARGET_FPS
        ai_fps_counter = 0
        ai_fps_timer = time.monotonic()

        while not shutdown_event.is_set():
            loop_start = time.monotonic()

            # Read frame from camera
            frame, frame_id, ts = self.camera.read()
            if frame is not None:
                self.frame_buffer.update_frame(frame, frame_id, ts)

            # Only process drowsiness in RUNNING state
            if self.state.state == State.RUNNING and frame is not None:
                metrics = self.face_analyzer.analyze(frame)
                perclos = self.face_analyzer.perclos

                # Update good face frame for verifier
                if metrics.face_present and metrics.face_bbox:
                    self.frame_buffer.update_good_face(frame, metrics.face_bbox)

                # Feed alert manager
                self.alert_manager.update(metrics, perclos)

                ai_fps_counter += 1

                # Log periodic metrics
                self._frame_count += 1
                if self._frame_count % (config.AI_TARGET_FPS * 10) == 0:
                    elapsed = time.monotonic() - ai_fps_timer
                    self._ai_fps = ai_fps_counter / elapsed if elapsed > 0 else 0
                    ai_fps_counter = 0
                    ai_fps_timer = time.monotonic()
                    logger.info(
                        f"Metrics: AI_FPS={self._ai_fps:.1f} "
                        f"CAM_FPS={self.camera.fps:.1f} "
                        f"EAR={metrics.ear:.3f} MAR={metrics.mar:.3f} "
                        f"Pitch={metrics.pitch:.1f} PERCLOS={perclos:.2f} "
                        f"Alert={self.alert_manager.current_level_name} "
                        f"Queue={self.local_queue.pending_count}"
                    )

            # Pace to target FPS
            elapsed = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ── Callbacks ───────────────────────────────────────────

    def _on_rfid_scan(self, uid: str):
        """Handle RFID card scan. Module responsibility stays clean."""
        logger.info(f"RFID event: UID={uid}, current_state={self.state.state}")

        if self.state.state == State.IDLE:
            self.state.transition(State.VERIFYING_DRIVER, f"RFID scan UID={uid}")
            self._verify_driver(uid)
        elif self.state.state == State.RUNNING:
            # End session
            logger.info(f"RFID scan during RUNNING — ending session for UID={uid}")
            self._end_session()

    def _verify_driver(self, uid: str):
        """Verify driver face after RFID scan."""
        if not self.verifier:
            # No verifier available — go straight to RUNNING (scaffold mode)
            logger.warning("Face verifier not available — entering RUNNING without verification")
            self._current_driver_uid = uid
            self._session_active = True
            self.state.transition(State.RUNNING, f"session started (no verify) UID={uid}")
            self.local_queue.push("session_start", {"rfid_tag": uid})
            return

        # Get face frame from buffer
        face_frame, bbox, ts = self.frame_buffer.get_good_face_frame()
        result = self.verifier.verify(face_frame, uid)

        if result == VerifyResult.MATCH:
            self._current_driver_uid = uid
            self._session_active = True
            self.state.transition(State.RUNNING, f"driver verified UID={uid}")
            self.local_queue.push("session_start", {"rfid_tag": uid})
        elif result == VerifyResult.MISMATCH:
            self.state.transition(State.MISMATCH_ALERT, f"face mismatch UID={uid}")
            self.local_queue.push("face_mismatch", {"rfid_tag": uid, "expected": "unknown"})
            time.sleep(3.0)
            self.state.transition(State.IDLE, "mismatch cleared")
        elif result == VerifyResult.BLOCKED:
            # Scaffold mode — allow session
            logger.info("Verify BLOCKED by missing assets — allowing session (scaffold)")
            self._current_driver_uid = uid
            self._session_active = True
            self.state.transition(State.RUNNING, f"session started (verify blocked) UID={uid}")
            self.local_queue.push("session_start", {"rfid_tag": uid})
        else:
            logger.warning(f"Verify returned {result} — staying in IDLE")
            self.state.transition(State.IDLE, f"verify inconclusive: {result}")

    def _end_session(self):
        """End current driving session."""
        uid = self._current_driver_uid
        self._current_driver_uid = None
        self._session_active = False
        self.alert_manager.reset()
        self.state.transition(State.IDLE, "session ended")
        self.local_queue.push("session_end", {"rfid_tag": uid or "unknown"})
        logger.info(f"Session ended for UID={uid}")

    def _on_alert(self, event):
        """Handle alert level change from AlertManager."""
        logger.info(f"Alert event: level={AlertLevel.NAMES[event.level]} "
                     f"EAR={event.ear:.3f} MAR={event.mar:.3f} Pitch={event.pitch:.1f}")
        # Queue for backend (uses 'level' key to match WebQuanLi)
        self.local_queue.push("alert", {
            "level": AlertLevel.NAMES[event.level],
            "ear": round(event.ear, 3),
            "mar": round(event.mar, 3),
            "pitch": round(event.pitch, 1),
        })

    def _on_state_change(self, old_state, new_state, reason):
        """Log state transitions."""
        logger.info(f"STATE TRANSITION: {old_state} -> {new_state} ({reason})")

    def _on_backend_command(self, command: dict):
        """Handle commands from backend via WebSocket."""
        action = command.get("action")
        logger.info(f"Backend command received: {action}")
        # TODO: implement test_alert and update_software handlers

    # ── Shutdown ────────────────────────────────────────────

    def _shutdown(self):
        logger.info("Shutting down DrowsiGuard...")
        shutdown_event.set()

        if self._session_active:
            self._end_session()

        self.camera.stop()
        self.face_analyzer.release()

        if self.rfid:
            self.rfid.stop()
        if self.gps:
            self.gps.stop()
        if self.ws_client:
            self.ws_client.stop()
        if self.buzzer:
            self.buzzer.cleanup()
        if self.led:
            self.led.cleanup()
        if self.speaker:
            self.speaker.cleanup()

        logger.info("DrowsiGuard stopped")


def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down...")
    shutdown_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    app = DrowsiGuard()
    app.run()
