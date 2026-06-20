"""
liveness.py — Anti-Spoofing dengan Local Binary Pattern (LBP) Texture Analysis
Letakkan file ini di app/liveness.py
"""

import cv2
import numpy as np


LBP_THRESHOLD      = 0.78
VARIANCE_THRESHOLD = 120.0


def _compute_lbp(gray: np.ndarray) -> np.ndarray:
    """Hitung LBP dengan cara yang aman dan efisien pakai np.roll."""
    h, w   = gray.shape
    lbp    = np.zeros((h, w), dtype=np.uint8)
    center = gray.astype(np.float32)

    # 8 tetangga searah jarum jam: atas, kanan-atas, kanan, kanan-bawah,
    # bawah, kiri-bawah, kiri, kiri-atas
    neighbors = [
        (-1,  0), (-1,  1), (0,  1), (1,  1),
        ( 1,  0), ( 1, -1), (0, -1), (-1, -1),
    ]

    for bit, (dy, dx) in enumerate(neighbors):
        shifted = np.roll(np.roll(gray.astype(np.float32), dy, axis=0), dx, axis=1)
        lbp += ((shifted >= center) * (1 << bit)).astype(np.uint8)

    return lbp


def _extract_face_roi(img_bgr: np.ndarray):
    """Crop region wajah menggunakan Haar Cascade."""
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    if len(faces) == 0:
        return None

    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    return gray[y:y + fh, x:x + fw]


def analyze_liveness(img_bgr: np.ndarray) -> dict:
    """
    Analisa liveness dari gambar BGR (hasil cv2.imdecode).

    Returns:
        {
            'is_live' : bool,
            'score'   : float,   # 0.0 – 1.0
            'reason'  : str,
        }
    """
    face_roi = _extract_face_roi(img_bgr)
    if face_roi is None:
        face_roi = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    face_resized = cv2.resize(face_roi, (128, 128))

    # LBP
    lbp  = _compute_lbp(face_resized)
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(np.float32)
    hist /= (hist.sum() + 1e-6)

    # Entropy
    entropy     = -np.sum(hist[hist > 0] * np.log2(hist[hist > 0] + 1e-6))
    max_entropy = np.log2(256)
    score_lbp   = float(np.clip(entropy / max_entropy, 0, 1))

    # Variance
    variance  = float(np.var(face_resized.astype(np.float32)))
    var_score = float(np.clip(variance / VARIANCE_THRESHOLD, 0, 1))

    # DCT frequency
    dct        = cv2.dct(face_resized.astype(np.float32))
    high_freq  = float(np.mean(np.abs(dct[64:, 64:])))
    low_freq   = float(np.mean(np.abs(dct[:64, :64])))
    freq_ratio = high_freq / (low_freq + 1e-6)
    freq_score = float(np.clip(freq_ratio * 50, 0, 1))

    # Gabungkan
    final_score = (
        0.45 * score_lbp +
        0.30 * var_score +
        0.25 * freq_score
    )

    is_live = final_score >= LBP_THRESHOLD

    if not is_live:
        if score_lbp < 0.5:
            reason = "Tekstur wajah tidak natural (kemungkinan foto atau layar)."
        elif var_score < 0.5:
            reason = "Gambar terlalu smooth — kemungkinan foto tercetak."
        else:
            reason = "Pola frekuensi mencurigakan — kemungkinan gambar dari layar."
    else:
        reason = "Liveness OK"

    return {
        'is_live': is_live,
        'score'  : round(final_score, 4),
        'reason' : reason,
        '_lbp'   : round(score_lbp,  4),
        '_var'   : round(var_score,  4),
        '_freq'  : round(freq_score, 4),
    }