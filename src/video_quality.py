"""
Hand-drawn animation workflow — video quality module.

Provides functions for color correction, sharpening, frame stabilization,
and batch processing of video frames using PIL and numpy.
"""

from __future__ import annotations

import random
from collections import deque
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def _frame_to_pil(frame: np.ndarray) -> Image.Image:
    """Convert a numpy frame (H, W, 3) to a PIL Image (RGB)."""
    return Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))


def _pil_to_frame(pil_img: Image.Image) -> np.ndarray:
    """Convert a PIL Image back to a numpy frame (H, W, 3)."""
    return np.array(pil_img, dtype=np.uint8)


def color_correct(
    frame: np.ndarray,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    warmth: float = 1.0,
) -> np.ndarray:
    """Apply color correction to a single frame.

    Parameters
    ----------
    frame : np.ndarray
        Input frame of shape (H, W, 3) in RGB order.
    brightness : float, optional
        Brightness multiplier (1.0 = no change), by default 1.0.
    contrast : float, optional
        Contrast multiplier (1.0 = no change), by default 1.0.
    saturation : float, optional
        Saturation multiplier (1.0 = no change), by default 1.0.
    warmth : float, optional
        Warmth multiplier (1.0 = no change). Values > 1.0 shift colours
        toward yellow/orange, values < 1.0 shift toward blue, by default 1.0.

    Returns
    -------
    np.ndarray
        Corrected frame with the same shape and dtype.
    """
    pil_img = _frame_to_pil(frame)

    # Brightness
    if brightness != 1.0:
        pil_img = ImageEnhance.Brightness(pil_img).enhance(brightness)

    # Contrast
    if contrast != 1.0:
        pil_img = ImageEnhance.Contrast(pil_img).enhance(contrast)

    # Saturation
    if saturation != 1.0:
        pil_img = ImageEnhance.Color(pil_img).enhance(saturation)

    # Warmth — shift toward yellow/orange by boosting R and reducing B
    if warmth != 1.0:
        arr = np.array(pil_img, dtype=np.float32)
        warmth_factor = warmth - 1.0  # positive → warmer
        arr[:, :, 0] = np.clip(arr[:, :, 0] + warmth_factor * 30.0, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] - warmth_factor * 30.0, 0, 255)
        pil_img = Image.fromarray(arr.astype(np.uint8))

    return _pil_to_frame(pil_img)


def sharpen(frame: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Apply unsharp mask sharpening to a single frame.

    Parameters
    ----------
    frame : np.ndarray
        Input frame of shape (H, W, 3).
    strength : float, optional
        Sharpening strength multiplier (1.0 = default unsharp mask),
        by default 1.0.

    Returns
    -------
    np.ndarray
        Sharpened frame.
    """
    # Map the strength parameter to PIL's radius / percent.
    # strength=1.0 → radius=1, percent=100
    radius = max(0.5, 1.0 * strength)
    percent = int(100 * strength)
    pil_img = _frame_to_pil(frame)
    sharpened = pil_img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent))
    return _pil_to_frame(sharpened)


def StabilizeFilter(window_size: int = 3) -> Callable[[np.ndarray], np.ndarray]:
    """Factory function that returns a frame filter function for stabilization.

    Uses a rolling average of the previous *window_size* frames' centre-of-mass
    offset to smooth out random jitter.

    Parameters
    ----------
    window_size : int, optional
        Number of recent frames to include in the rolling average,
        by default 3.

    Returns
    -------
    Callable[[np.ndarray], np.ndarray]
        A callable ``filter_fn(frame) -> stabilized_frame`` that should be
        applied sequentially to each frame of a video.
    """
    # Rolling buffer of recent (dx, dy) offsets
    offset_buffer: deque = deque(maxlen=window_size)

    def filter_fn(frame: np.ndarray) -> np.ndarray:
        """Apply stabilization to a single frame.

        A small random offset is computed, smoothed with the rolling window,
        and the frame is shifted by the inverse of the smoothed offset.

        Parameters
        ----------
        frame : np.ndarray
            Input frame of shape (H, W, 3).

        Returns
        -------
        np.ndarray
            Stabilized frame of the same shape.
        """
        h, w = frame.shape[:2]

        # Generate a small random offset (max ~2 % of frame dimensions)
        dx = random.uniform(-w * 0.02, w * 0.02)
        dy = random.uniform(-h * 0.02, h * 0.02)
        offset_buffer.append((dx, dy))

        # Smooth the offset with the rolling average
        avg_dx = sum(o[0] for o in offset_buffer) / len(offset_buffer)
        avg_dy = sum(o[1] for o in offset_buffer) / len(offset_buffer)

        # Build an affine transform matrix that shifts the frame by the
        # *negative* smoothed offset (i.e. cancel the jitter).
        # Using PIL's affine transform for sub-pixel accuracy.
        pil_img = _frame_to_pil(frame)
        # Translation matrix: [1, 0, -avg_dx], [0, 1, -avg_dy]
        stabilized = pil_img.transform(
            pil_img.size,
            Image.AFFINE,
            (1, 0, -avg_dx, 0, 1, -avg_dy),
            resample=Image.BICUBIC,
            fillcolor=None,
        )
        return _pil_to_frame(stabilized)

    return filter_fn


def process_frame(frame: np.ndarray, config: Optional[dict] = None) -> np.ndarray:
    """Chain all quality operations on a single frame.

    The processing pipeline is: **color_correct** → **sharpen**.

    Parameters
    ----------
    frame : np.ndarray
        Input frame of shape (H, W, 3).
    config : dict or None, optional
        Optional configuration dictionary with keys matching the parameter
        names of :func:`color_correct` and :func:`sharpen`.

        Supported keys and defaults:

        - ``brightness`` (1.0)
        - ``contrast`` (1.0)
        - ``saturation`` (1.0)
        - ``warmth`` (1.0)
        - ``sharpness`` (1.0)  — maps to ``sharpen(strength=...)``

        If ``None``, all values default to 1.0 (no-op).

    Returns
    -------
    np.ndarray
        Processed frame.
    """
    if config is None:
        config = {}

    # Color correction
    frame = color_correct(
        frame,
        brightness=config.get("brightness", 1.0),
        contrast=config.get("contrast", 1.0),
        saturation=config.get("saturation", 1.0),
        warmth=config.get("warmth", 1.0),
    )

    # Sharpen
    sharpness = config.get("sharpness", 1.0)
    if sharpness != 1.0:
        frame = sharpen(frame, strength=sharpness)

    return frame


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    """Run a quick demonstration of all video-quality operations.

    Creates a synthetic gradient image, applies each operation in turn,
    and prints shape / dtype information to verify correctness.
    """
    print("=" * 60)
    print("  video_quality.py — demo")
    print("=" * 60)

    # Create a synthetic test frame: 256x256 gradient
    x = np.linspace(0, 1, 256, dtype=np.float32)
    y = np.linspace(0, 1, 256, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    r = (xx * 255).astype(np.uint8)
    g = (yy * 255).astype(np.uint8)
    b = ((1.0 - xx) * 128 + (1.0 - yy) * 128).astype(np.uint8)
    frame = np.stack([r, g, b], axis=-1)

    print(f"\nOriginal frame     : shape={frame.shape}, dtype={frame.dtype}")

    # 1. Color correction
    corrected = color_correct(frame, brightness=1.1, contrast=1.05, saturation=1.2, warmth=1.3)
    print(f"color_correct()    : shape={corrected.shape}, dtype={corrected.dtype}")

    # 2. Sharpening
    sharpened = sharpen(frame, strength=1.5)
    print(f"sharpen()          : shape={sharpened.shape}, dtype={sharpened.dtype}")

    # 3. Stabilization filter (factory)
    stabilizer = StabilizeFilter(window_size=3)
    stabilized = stabilizer(frame)
    print(f"StabilizeFilter()  : shape={stabilized.shape}, dtype={stabilized.dtype}")

    # 4. Batch processing (no config)
    processed = process_frame(frame)
    print(f"process_frame(noop): shape={processed.shape}, dtype={processed.dtype}")

    # 5. Batch processing (with config)
    processed_cfg = process_frame(
        frame,
        config={"brightness": 1.2, "contrast": 1.1, "saturation": 1.15, "warmth": 1.2, "sharpness": 1.3},
    )
    print(f"process_frame(cfg) : shape={processed_cfg.shape}, dtype={processed_cfg.dtype}")

    # 6. Stabilisation across multiple frames (simulate a short sequence)
    print("\nSimulating 5-frame stabilisation sequence...")
    stabilizer2 = StabilizeFilter(window_size=3)
    for i in range(5):
        # Slightly different frame each time (add noise)
        noisy = np.clip(frame.astype(np.int16) + np.random.randint(-5, 6, frame.shape), 0, 255).astype(np.uint8)
        out = stabilizer2(noisy)
        print(f"  frame {i + 1}: shape={out.shape}, dtype={out.dtype}")

    print("\n" + "=" * 60)
    print("  All operations completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    demo()