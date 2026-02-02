"""Face detection and comparison service using InsightFace."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

# Try to import numpy, handle if not installed
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not installed, face service features limited")

if TYPE_CHECKING:
    import numpy as np

# Lazy loading of heavy dependencies
_face_app: Any = None
_model_loaded: bool = False
_model_load_error: str | None = None


def _get_face_app():
    """Get or initialize InsightFace app (lazy loading)."""
    global _face_app, _model_loaded, _model_load_error

    if not NUMPY_AVAILABLE:
        _model_load_error = "numpy not installed"
        return None

    if _model_load_error:
        return None

    if _face_app is None:
        try:
            from insightface.app import FaceAnalysis

            logger.info("Initializing InsightFace...")
            _face_app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
            )
            _face_app.prepare(ctx_id=0, det_size=(640, 640))
            _model_loaded = True
            logger.info("InsightFace initialized successfully")
        except ImportError:
            _model_load_error = "insightface not installed"
            logger.warning("InsightFace not installed, face features disabled")
            return None
        except Exception as e:
            _model_load_error = str(e)
            logger.error(f"Failed to initialize InsightFace: {e}")
            return None

    return _face_app


def is_face_service_available() -> bool:
    """Check if face service is available and models are loaded."""
    if not NUMPY_AVAILABLE:
        return False
    app = _get_face_app()
    return app is not None


def extract_face(image_path: str) -> Any | None:
    """
    Extract face embedding from an image.

    Args:
        image_path: Path to the image file

    Returns:
        Face embedding as numpy array (512-dimensional) or None if no face found
    """
    if not NUMPY_AVAILABLE:
        return None

    app = _get_face_app()
    if app is None:
        return None

    if not Path(image_path).exists():
        logger.error(f"Image file not found: {image_path}")
        return None

    try:
        import cv2

        # Read image
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to read image: {image_path}")
            return None

        # Detect faces
        faces = app.get(img)

        if not faces:
            logger.info(f"No face detected in image: {image_path}")
            return None

        if len(faces) > 1:
            logger.warning(f"Multiple faces detected in {image_path}, using largest")
            # Use the face with largest bounding box
            faces = sorted(
                faces,
                key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]),
                reverse=True,
            )

        # Return embedding of the first (or largest) face
        return faces[0].embedding

    except ImportError:
        logger.warning("OpenCV not installed")
        return None
    except Exception as e:
        logger.error(f"Error extracting face from {image_path}: {e}")
        return None


def extract_face_from_bytes(image_bytes: bytes) -> Any | None:
    """
    Extract face embedding from image bytes.

    Args:
        image_bytes: Image data as bytes

    Returns:
        Face embedding or None
    """
    if not NUMPY_AVAILABLE:
        return None

    import numpy as np

    app = _get_face_app()
    if app is None:
        return None

    try:
        import cv2

        # Decode image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            logger.error("Failed to decode image from bytes")
            return None

        # Detect faces
        faces = app.get(img)

        if not faces:
            logger.info("No face detected in image")
            return None

        if len(faces) > 1:
            logger.warning("Multiple faces detected, using largest")
            faces = sorted(
                faces,
                key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]),
                reverse=True,
            )

        return faces[0].embedding

    except ImportError:
        logger.warning("OpenCV not installed")
        return None
    except Exception as e:
        logger.error(f"Error extracting face from bytes: {e}")
        return None


def compare_faces(embedding1: Any, embedding2: Any) -> float:
    """
    Compare two face embeddings and return similarity score.

    Args:
        embedding1: First face embedding (512-dimensional)
        embedding2: Second face embedding (512-dimensional)

    Returns:
        Similarity score between 0 and 1 (higher = more similar)
    """
    if embedding1 is None or embedding2 is None:
        return 0.0

    if not NUMPY_AVAILABLE:
        return 0.0

    import numpy as np

    try:
        # Normalize embeddings
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        embedding2 = embedding2 / np.linalg.norm(embedding2)

        # Cosine similarity
        similarity = np.dot(embedding1, embedding2)

        # Convert from [-1, 1] to [0, 1]
        similarity = (similarity + 1) / 2

        return float(similarity)
    except Exception as e:
        logger.error(f"Error comparing faces: {e}")
        return 0.0


def faces_match(
    embedding1: Any,
    embedding2: Any,
    threshold: float = 0.6,
) -> bool:
    """
    Check if two face embeddings are from the same person.

    Args:
        embedding1: First face embedding
        embedding2: Second face embedding
        threshold: Similarity threshold (default 0.6)

    Returns:
        True if faces match (same person)
    """
    similarity = compare_faces(embedding1, embedding2)
    return similarity >= threshold


def embedding_to_bytes(embedding: Any) -> bytes:
    """
    Convert face embedding to bytes for storage.

    Args:
        embedding: Face embedding numpy array

    Returns:
        Bytes representation
    """
    if embedding is None:
        return b""
    return embedding.tobytes()


def bytes_to_embedding(data: bytes) -> Any:
    """
    Convert bytes back to face embedding.

    Args:
        data: Bytes representation of embedding

    Returns:
        Face embedding numpy array
    """
    if not NUMPY_AVAILABLE:
        return None

    import numpy as np

    if not data:
        return None
    return np.frombuffer(data, dtype=np.float32)


def detect_faces_count(image_path: str) -> int:
    """
    Count number of faces in an image.

    Args:
        image_path: Path to image

    Returns:
        Number of faces detected
    """
    if not NUMPY_AVAILABLE:
        return 0

    app = _get_face_app()
    if app is None:
        return 0

    try:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            return 0

        faces = app.get(img)
        return len(faces)
    except Exception as e:
        logger.error(f"Error counting faces: {e}")
        return 0


def get_face_quality_score(image_path: str) -> float:
    """
    Get a quality score for the face in an image.
    Higher score = better quality for verification.

    Args:
        image_path: Path to image

    Returns:
        Quality score between 0 and 1
    """
    if not NUMPY_AVAILABLE:
        return 0.0

    app = _get_face_app()
    if app is None:
        return 0.0

    try:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            return 0.0

        faces = app.get(img)
        if not faces:
            return 0.0

        face = faces[0]

        # Calculate quality based on various factors
        quality = 1.0

        # Face detection confidence
        if hasattr(face, "det_score"):
            quality *= face.det_score

        # Face size relative to image
        bbox = face.bbox
        face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        image_area = img.shape[0] * img.shape[1]
        face_ratio = face_area / image_area

        # Ideal face ratio is 10-40% of image
        if face_ratio < 0.05:
            quality *= 0.5  # Face too small
        elif face_ratio > 0.6:
            quality *= 0.8  # Face too close

        return float(quality)
    except Exception as e:
        logger.error(f"Error calculating face quality: {e}")
        return 0.0
