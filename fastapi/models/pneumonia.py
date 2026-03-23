"""
models/pneumonia.py — Pneumonia detection model (previously new2.py).

FIXES applied:
  1. Model path is now loaded from the PNEUMONIA_MODEL_PATH env variable
     instead of a hardcoded absolute Windows path, so it works on any machine.
  2. preprocess_image() now explicitly handles RGBA images (e.g. PNG with
     transparency) by converting to RGB before any channel checks, preventing
     silent wrong-shape model inputs.
  3. Model is loaded lazily (on first call) so the app starts even if the
     model file is temporarily unavailable.
"""
import base64
import os
import random
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from config import get_settings


@lru_cache()
def _load_model():
    """Load the Keras model once and cache it."""
    from keras.models import load_model  # lazy import — only needed for prediction

    path = get_settings().pneumonia_model_path
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Pneumonia model not found at '{path}'. "
            "Set PNEUMONIA_MODEL_PATH in your .env file."
        )
    return load_model(path)


def preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Convert a PIL image to a normalised (1, 64, 64, 3) NumPy array.

    FIX: Added explicit RGB conversion before channel checks so that RGBA
    images (common PNGs) no longer produce a 4-channel array that bypasses
    the grayscale→RGB branch and silently feeds wrong data to the model.
    """
    # Normalise to RGB regardless of source mode (RGBA, L, P, etc.)
    image = image.convert("RGB")
    img_array = np.array(image)

    resized = cv2.resize(img_array, (64, 64))
    normalized = resized / 255.0
    return np.expand_dims(normalized, axis=0)


def display_infected(image: np.ndarray) -> np.ndarray:
    """
    Draw a circle around the largest region matching the infection colour mask.
    Input and output are BGR NumPy arrays (OpenCV format).
    """
    selected_color = (153, 153, 153)
    tolerance = 10
    lower = np.array([c - tolerance for c in selected_color])
    upper = np.array([c + tolerance for c in selected_color])

    mask = cv2.inRange(image, lower, upper)

    if cv2.countNonZero(mask) == 0:
        return image

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    largest = max(contours, key=cv2.contourArea)
    M = cv2.moments(largest)
    if M["m00"] == 0:
        return image

    center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
    radius = random.randint(200, 250)

    image_copy = image.copy()
    cv2.circle(image_copy, center, radius, (0, 0, 0), 4)
    return image_copy


def display_images(raw: np.ndarray, infected: np.ndarray) -> np.ndarray:
    """Resize both images to fit 800×600 and stack them side by side."""
    max_w, max_h = 800, 600

    def resize(img):
        h, w = img.shape[:2]
        scale = min(max_w / w, max_h / h)
        return cv2.resize(img, None, fx=scale, fy=scale)

    return np.hstack((resize(raw), resize(infected)))


def encode_image_to_base64(image: np.ndarray) -> str:
    """Encode a BGR NumPy array to a base64 JPEG string."""
    success, buffer = cv2.imencode(".jpg", image)
    if not success:
        raise ValueError("Could not encode image to base64.")
    return base64.b64encode(buffer).decode("utf-8")


def handler(image: Image.Image) -> dict:
    """
    Run pneumonia prediction on a PIL image.

    Returns:
        {
            "result": "INFECTED" | "NORMAL",
            "probability": 0.0,
            "CombinedImg": np.ndarray | None
        }
    """
    model = _load_model()
    processed = preprocess_image(image)
    prediction = model.predict(processed)
    probability = float(prediction[0][0])

    if probability > 0.5:
        result = "INFECTED"
        img_bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        infected = display_infected(img_bgr)
        combined = display_images(img_bgr, infected)
    else:
        result = "NORMAL"
        combined = None

    print(f"Prediction: {result} ({probability * 100:.2f}%)")

    return {
        "result": result,
        "probability": round(probability * 100, 2),
        "CombinedImg": combined,
    }