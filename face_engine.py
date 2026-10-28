"""Face verification, loaded once per process.

The model is built at import time (and baked into the Docker image at build
time), so each scan only runs inference instead of reloading TensorFlow.
"""
import base64
import os
import threading

import cv2
import numpy as np
from deepface import DeepFace
from deepface.modules.verification import find_distance, find_threshold

MODEL_NAME = os.environ.get('FACE_MODEL', 'Facenet')
DETECTOR = os.environ.get('FACE_DETECTOR', 'opencv')
DISTANCE_METRIC = 'cosine'
# DeepFace's tuned threshold for this model + metric (same value DeepFace.verify uses)
THRESHOLD = float(os.environ.get('FACE_THRESHOLD', find_threshold(MODEL_NAME, DISTANCE_METRIC)))

# TensorFlow inference isn't guaranteed thread-safe; scans are short, so serialise them.
_lock = threading.Lock()


def warm_up():
    """Load model weights into memory (downloads them on first run)."""
    DeepFace.build_model(MODEL_NAME)


def decode_bytes(raw):
    """Decode raw image bytes (JPEG/PNG) into a BGR image, or None."""
    if not raw:
        return None
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def decode_image(data_url):
    """Turn a browser data URL (data:image/jpeg;base64,...) into a BGR image, or None."""
    if not data_url:
        return None
    encoded = data_url.split(',', 1)[1] if ',' in data_url else data_url
    try:
        return decode_bytes(base64.b64decode(encoded))
    except (ValueError, TypeError):
        return None


def has_face(image):
    """True if at least one face is detected in the image."""
    try:
        with _lock:
            faces = DeepFace.extract_faces(
                img_path=image, detector_backend=DETECTOR, enforce_detection=True
            )
        return len(faces) >= 1
    except ValueError:
        return False


def _embed(image):
    """Face embedding for the most prominent face. Raises ValueError if no face is found."""
    with _lock:
        reps = DeepFace.represent(
            img_path=image,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR,
            enforce_detection=True,
            max_faces=1,
        )
    return np.array(reps[0]['embedding'])


# Enrolled photos don't change, so their embeddings are computed once and reused.
_enrolled_cache = {}


def _enrolled_embedding(photo_path):
    mtime = os.path.getmtime(photo_path)
    cached = _enrolled_cache.get(photo_path)
    if cached and cached[0] == mtime:
        return cached[1]
    embedding = _embed(photo_path)
    _enrolled_cache[photo_path] = (mtime, embedding)
    return embedding


def _is_match(live_embedding, enrolled_embedding):
    distance = find_distance(live_embedding, enrolled_embedding, DISTANCE_METRIC)
    return distance <= THRESHOLD, float(distance)


def verify(live_image, enrolled_photo_path):
    """Compare a live frame against one enrolled photo.

    Returns (verified, reason) where reason is 'match', 'no_match' or 'no_face'.
    """
    try:
        live = _embed(live_image)
    except ValueError:
        return False, 'no_face'
    try:
        enrolled = _enrolled_embedding(enrolled_photo_path)
    except (ValueError, OSError):
        return False, 'no_match'
    matched, _ = _is_match(live, enrolled)
    return (True, 'match') if matched else (False, 'no_match')


def identify(live_image, candidates):
    """Find who is in a live frame among enrolled students.

    candidates: iterable of (key, photo_path). Returns (key or None, reason).
    The live frame is embedded once and compared against every cached enrolled embedding,
    picking the closest match under the threshold.
    """
    try:
        live = _embed(live_image)
    except ValueError:
        return None, 'no_face'

    best_key, best_distance = None, None
    for key, photo_path in candidates:
        try:
            matched, distance = _is_match(live, _enrolled_embedding(photo_path))
        except (ValueError, OSError):
            continue
        if matched and (best_distance is None or distance < best_distance):
            best_key, best_distance = key, distance
    return (best_key, 'match') if best_key is not None else (None, 'no_match')


warm_up()
