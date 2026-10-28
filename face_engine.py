"""Face detection, embedding and matching.

Two interchangeable engines, chosen with the FACE_ENGINE environment variable:

- "opencv" (default): OpenCV's YuNet detector + SFace recogniser (ONNX models in models/).
  Small and fast. About 100 MB of RAM in total, so it runs on free hosting.
- "deepface": DeepFace with the Facenet model on TensorFlow. Heavier (about 2 GB RAM).

Both expose the same functions: decode_image, decode_bytes, has_face, verify, identify.
Models load once per process, and each enrolled photo's embedding is computed once and cached,
so a scan only has to embed the live frame.
"""
import base64
import os
import threading

import cv2
import numpy as np

ENGINE = os.environ.get('FACE_ENGINE', 'opencv').lower()
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')

# Model inference isn't guaranteed thread-safe; scans are short, so serialise them.
_lock = threading.Lock()


# ── Image decoding ─────────────────────────────────────────────

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


def _load(image):
    """Accept a file path or an already-decoded image."""
    if isinstance(image, str):
        img = cv2.imread(image, cv2.IMREAD_COLOR)
        if img is None:
            raise OSError(f'Could not read image: {image}')
        return img
    return image


# ── OpenCV engine (YuNet + SFace) ──────────────────────────────

class _OpenCVEngine:
    MAX_SIDE = 1280           # downscale very large photos before detection
    MATCH_THRESHOLD = 0.363   # SFace cosine similarity; OpenCV's recommended value

    def __init__(self):
        self.detector = cv2.FaceDetectorYN.create(
            os.path.join(MODEL_DIR, 'face_detection_yunet_2023mar.onnx'), '', (320, 320),
            score_threshold=0.8, nms_threshold=0.3, top_k=50,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(
            os.path.join(MODEL_DIR, 'face_recognition_sface_2021dec.onnx'), ''
        )

    def _prepare(self, img):
        h, w = img.shape[:2]
        scale = min(1.0, self.MAX_SIDE / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        return img

    def detect(self, img):
        """Return the largest detected face row, or None."""
        img = self._prepare(img)
        h, w = img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        if faces is None or len(faces) == 0:
            return img, None
        largest = max(faces, key=lambda f: f[2] * f[3])
        return img, largest

    def embed(self, image):
        img, face = self.detect(_load(image))
        if face is None:
            raise ValueError('No face detected')
        aligned = self.recognizer.alignCrop(img, face)
        return self.recognizer.feature(aligned)

    def compare(self, a, b):
        similarity = self.recognizer.match(a, b, cv2.FaceRecognizerSF_FR_COSINE)
        return similarity >= self.MATCH_THRESHOLD, 1.0 - float(similarity)


# ── DeepFace engine (Facenet) ──────────────────────────────────

class _DeepFaceEngine:
    MODEL_NAME = os.environ.get('FACE_MODEL', 'Facenet')
    DETECTOR = os.environ.get('FACE_DETECTOR', 'opencv')

    def __init__(self):
        from deepface import DeepFace
        from deepface.modules.verification import find_distance, find_threshold
        self.DeepFace = DeepFace
        self.find_distance = find_distance
        self.threshold = float(os.environ.get('FACE_THRESHOLD', find_threshold(self.MODEL_NAME, 'cosine')))
        DeepFace.build_model(self.MODEL_NAME)

    def embed(self, image):
        reps = self.DeepFace.represent(
            img_path=image, model_name=self.MODEL_NAME, detector_backend=self.DETECTOR,
            enforce_detection=True, max_faces=1,
        )
        return np.array(reps[0]['embedding'])

    def compare(self, a, b):
        distance = float(self.find_distance(a, b, 'cosine'))
        return distance <= self.threshold, distance


_engine = _DeepFaceEngine() if ENGINE == 'deepface' else _OpenCVEngine()


# ── Public API ─────────────────────────────────────────────────

def _embed(image):
    """Embedding of the most prominent face. Raises ValueError if no face is found."""
    with _lock:
        return _engine.embed(image)


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


def has_face(image):
    """True if at least one face is detected in the image."""
    try:
        _embed(image)
        return True
    except ValueError:
        return False


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
    matched, _ = _engine.compare(live, enrolled)
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
            matched, distance = _engine.compare(live, _enrolled_embedding(photo_path))
        except (ValueError, OSError):
            continue
        if matched and (best_distance is None or distance < best_distance):
            best_key, best_distance = key, distance
    return (best_key, 'match') if best_key is not None else (None, 'no_match')
