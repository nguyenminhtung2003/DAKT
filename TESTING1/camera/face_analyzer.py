"""
DrowsiGuard — Face Analyzer (MediaPipe Face Mesh)
Computes EAR, MAR, Head Pose (pitch), confidence, and PERCLOS.
Runs on frames from FrameBuffer. Does NOT own camera.
"""
import math
import time
from collections import deque

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    mp = None

from utils.logger import get_logger
import config

logger = get_logger("camera.face_analyzer")

# ─── Landmark Indices ────────────────────────────────────
# Left eye
L_EYE = [362, 385, 387, 263, 373, 380]
# Right eye
R_EYE = [33, 160, 158, 133, 153, 144]
# Mouth
MOUTH = [13, 14, 78, 308, 81, 311]
# Head pose reference points (nose tip, chin, left/right eye corner, left/right mouth corner)
POSE_POINTS = [1, 152, 33, 263, 61, 291]

# 3D model points (generic face model) for solvePnP
MODEL_POINTS = np.array([
    (0.0, 0.0, 0.0),        # Nose tip
    (0.0, -330.0, -65.0),   # Chin
    (-225.0, 170.0, -135.0),  # Left eye left corner
    (225.0, 170.0, -135.0),   # Right eye right corner
    (-150.0, -150.0, -125.0), # Left mouth corner
    (150.0, -150.0, -125.0),  # Right mouth corner
], dtype=np.float64)


def _dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def _ema(prev, cur, alpha):
    if prev is None:
        return cur
    return alpha * cur + (1 - alpha) * prev


class FaceMetrics:
    """Data class holding per-frame analysis results."""
    __slots__ = (
        "face_present", "ear", "mar", "pitch", "confidence",
        "face_bbox", "raw_ear", "raw_mar", "raw_pitch",
    )

    def __init__(self):
        self.face_present = False
        self.ear = 0.0
        self.mar = 0.0
        self.pitch = 0.0
        self.confidence = 0.0
        self.face_bbox = None
        self.raw_ear = 0.0
        self.raw_mar = 0.0
        self.raw_pitch = 0.0


class FaceAnalyzer:
    """MediaPipe Face Mesh based drowsiness analyzer."""

    def __init__(self):
        if mp is None:
            raise ImportError("mediapipe is not installed")

        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=config.MAX_NUM_FACES,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Smoothed values
        self._ear_smooth = None
        self._mar_smooth = None
        self._pitch_smooth = None

        # PERCLOS tracking
        self._perclos_window = deque(maxlen=int(config.PERCLOS_WINDOW * config.AI_TARGET_FPS))

        # Performance
        self._process_time = 0.0

        logger.info("FaceAnalyzer initialized with MediaPipe Face Mesh")

    def analyze(self, frame) -> FaceMetrics:
        """Process a single BGR frame and return FaceMetrics."""
        metrics = FaceMetrics()
        if frame is None:
            return metrics

        t0 = time.monotonic()
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            self._perclos_window.append(1)  # eyes "closed" if no face
            return metrics

        face = results.multi_face_landmarks[0]
        lm = face.landmark

        # ── Confidence check ────────────────────────────────
        # Use detection score approximation from landmark visibility
        vis_sum = sum(lm[i].visibility for i in POSE_POINTS if hasattr(lm[i], 'visibility'))
        metrics.confidence = vis_sum / len(POSE_POINTS) if vis_sum else 0.5

        # ── Convert to pixel coords ────────────────────────
        def px(idx):
            return (lm[idx].x * w, lm[idx].y * h)

        # ── EAR (Eye Aspect Ratio) ──────────────────────────
        def ear_single(indices):
            p = [px(i) for i in indices]
            v1 = _dist(p[1], p[5])
            v2 = _dist(p[2], p[4])
            h_dist = _dist(p[0], p[3])
            if h_dist < 1e-6:
                return 0.3
            return (v1 + v2) / (2.0 * h_dist)

        ear_l = ear_single(L_EYE)
        ear_r = ear_single(R_EYE)
        raw_ear = (ear_l + ear_r) / 2.0

        # ── MAR (Mouth Aspect Ratio) ────────────────────────
        mp_pts = [px(i) for i in MOUTH]
        v_mouth = _dist(mp_pts[0], mp_pts[1])
        h_mouth = _dist(mp_pts[2], mp_pts[3])
        raw_mar = v_mouth / h_mouth if h_mouth > 1e-6 else 0.0

        # ── Head Pose (Pitch) ───────────────────────────────
        image_points = np.array([px(i) for i in POSE_POINTS], dtype=np.float64)
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        success, rotation_vec, _ = cv2.solvePnP(
            MODEL_POINTS, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        raw_pitch = 0.0
        if success:
            rmat, _ = cv2.Rodrigues(rotation_vec)
            angles = cv2.decomposeProjectionMatrix(
                np.hstack((rmat, np.zeros((3, 1))))
            )[6]
            raw_pitch = float(angles[0])

        # ── Smoothing ───────────────────────────────────────
        self._ear_smooth = _ema(self._ear_smooth, raw_ear, config.EAR_SMOOTHING_ALPHA)
        self._mar_smooth = _ema(self._mar_smooth, raw_mar, config.MAR_SMOOTHING_ALPHA)
        self._pitch_smooth = _ema(self._pitch_smooth, raw_pitch, config.PITCH_SMOOTHING_ALPHA)

        # ── PERCLOS ─────────────────────────────────────────
        eye_closed = 1 if self._ear_smooth < config.EAR_THRESHOLD else 0
        self._perclos_window.append(eye_closed)

        # ── Bounding box ────────────────────────────────────
        xs = [lm[i].x * w for i in range(468)]
        ys = [lm[i].y * h for i in range(468)]
        x_min, x_max = int(min(xs)), int(max(xs))
        y_min, y_max = int(min(ys)), int(max(ys))
        metrics.face_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        # ── Populate metrics ────────────────────────────────
        metrics.face_present = True
        metrics.ear = self._ear_smooth
        metrics.mar = self._mar_smooth
        metrics.pitch = self._pitch_smooth
        metrics.raw_ear = raw_ear
        metrics.raw_mar = raw_mar
        metrics.raw_pitch = raw_pitch

        self._process_time = time.monotonic() - t0
        return metrics

    @property
    def perclos(self) -> float:
        """PERCLOS over sliding window (0.0 ~ 1.0)."""
        if not self._perclos_window:
            return 0.0
        return sum(self._perclos_window) / len(self._perclos_window)

    @property
    def process_time_ms(self) -> float:
        return self._process_time * 1000

    def release(self):
        if self._face_mesh:
            self._face_mesh.close()
            logger.info("FaceAnalyzer released")
