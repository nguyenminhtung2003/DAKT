"""
DrowsiGuard — Face Verifier (Scaffold V1)
Event-driven face verification. NOT continuous.
BLOCKED: Full implementation requires enrollment/reference face data.
"""
from utils.logger import get_logger

logger = get_logger("camera.face_verifier")


class VerifyResult:
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    BLOCKED = "BLOCKED_BY_MISSING_ASSETS"


class FaceVerifier:
    """Scaffold face verifier — real matching blocked until enrollment data exists.

    This module will:
    1. Accept a cropped face image and a driver_id / rfid_uid
    2. Compare against stored reference embeddings
    3. Return MATCH / MISMATCH / LOW_CONFIDENCE

    Current status: SCAFFOLD ONLY.
    """

    def __init__(self):
        self._enrolled_drivers = {}  # rfid_uid -> reference_data
        logger.warning("FaceVerifier initialized in SCAFFOLD mode — no enrollment data loaded")

    def verify(self, face_frame, rfid_uid: str) -> str:
        """Verify face against enrolled driver for given RFID UID.

        Returns VerifyResult constant.
        """
        if not self._enrolled_drivers:
            logger.info(f"Verify requested for UID={rfid_uid} — BLOCKED (no enrollment data)")
            return VerifyResult.BLOCKED

        if face_frame is None:
            logger.warning("Verify called with no face frame")
            return VerifyResult.LOW_CONFIDENCE

        # TODO: Implement actual face embedding comparison when assets are available
        # Planned approach:
        # 1. Use face_recognition or similar lightweight embedding model
        # 2. Compare L2 distance or cosine similarity against stored embedding
        # 3. Threshold-based decision
        logger.info(f"Verify for UID={rfid_uid} — returning BLOCKED (not implemented)")
        return VerifyResult.BLOCKED

    def enroll_driver(self, rfid_uid: str, reference_images: list):
        """Enroll a driver's face for future verification.

        BLOCKED: requires reference images from backend/registry.
        """
        logger.warning(f"Enrollment for UID={rfid_uid} — BLOCKED (not implemented in V1 scaffold)")

    @property
    def has_enrollments(self) -> bool:
        return len(self._enrolled_drivers) > 0
