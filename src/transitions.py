"""
Custom video transitions for hand-drawn animation workflow.

Provides slide, zoom, and wipe transitions that can be applied
between scene clips. All transitions are designed with a smooth,
gentle feel aligned with the hand-drawn aesthetic.

Usage:
    from src.transitions import apply_transition

    # Apply a slide transition between two clips
    result = apply_transition(clip1, clip2, duration=1.0, transition_type="slide")

Requirements:
    - moviepy 2.x (from moviepy import VideoClip, CompositeVideoClip)
    - numpy
    - Pillow (PIL)
"""

import numpy as np
from PIL import Image
from moviepy import VideoClip, CompositeVideoClip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get_frame(clip, t):
    """
    Safely retrieve a frame from a clip at time t.

    Handles edge cases where the clip may be None, have no duration,
    or the requested time exceeds the clip's duration.

    Parameters
    ----------
    clip : VideoClip or None
        The clip to get a frame from. If None, returns a black frame.
    t : float
        Time in seconds.

    Returns
    -------
    ndarray
        Frame as numpy array of shape (H, W, 3), dtype uint8.
    """
    if clip is None:
        return None
    try:
        return clip.get_frame(t)
    except Exception:
        # Return last available frame if t exceeds duration
        if clip.duration is not None and clip.duration > 0:
            return clip.get_frame(clip.duration - 0.01)
        return clip.get_frame(0)


def _get_time_offsets(clip1, clip2, t, duration):
    """
    Compute the time offsets into clip1 and clip2 for a given transition time.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip.
    clip2 : VideoClip
        Incoming clip.
    t : float
        Current transition time (0 <= t <= duration).
    duration : float
        Total transition duration.

    Returns
    -------
    tuple of float
        (t1, t2) where t1 is the time into clip1 and t2 is the time into clip2.
    """
    # clip1 plays its last `duration` seconds; clip2 plays its first `duration` seconds
    if clip1 is not None and clip1.duration is not None:
        t1 = max(0, clip1.duration - duration + t)
    else:
        t1 = t

    t2 = t  # clip2 starts from the beginning

    return t1, t2


def _get_dimensions(clip1, clip2):
    """
    Get the frame dimensions (height, width) from the first available clip.

    Parameters
    ----------
    clip1 : VideoClip or None
    clip2 : VideoClip or None

    Returns
    -------
    tuple of int
        (height, width).

    Raises
    ------
    ValueError
        If neither clip can provide dimensions.
    """
    for clip in (clip1, clip2):
        if clip is not None:
            try:
                frame = clip.get_frame(0)
                return frame.shape[:2]
            except Exception:
                continue
    raise ValueError("Cannot determine dimensions: both clips are None or invalid.")


# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------

def _smoothstep(t):
    """Smooth Hermite interpolation: 3t^2 - 2t^3."""
    return t * t * (3.0 - 2.0 * t)


def _ease_in_out(t):
    """Ease-in-out: smooth acceleration and deceleration."""
    if t < 0.5:
        return 2.0 * t * t
    else:
        return -1.0 + (4.0 - 2.0 * t) * t


# ---------------------------------------------------------------------------
# Transition: Slide
# ---------------------------------------------------------------------------

def apply_slide(clip1, clip2, duration):
    """
    Slide transition: clip1 slides out to the left while clip2 slides in from the right.

    Creates a smooth horizontal sliding effect. The outgoing clip moves
    off-screen to the left as the incoming clip enters from the right,
    with a gentle easing for a hand-drawn feel.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip (first scene).
    clip2 : VideoClip
        Incoming clip (second scene).
    duration : float
        Duration of the transition in seconds.

    Returns
    -------
    VideoClip
        A single clip representing the slide transition.
    """
    H, W = _get_dimensions(clip1, clip2)

    def make_frame(t):
        # Clamp t to valid range
        t = max(0, min(t, duration))

        progress = t / duration  # 0 -> 1
        eased = _ease_in_out(progress)

        t1, t2 = _get_time_offsets(clip1, clip2, t, duration)

        frame1 = _safe_get_frame(clip1, t1)
        frame2 = _safe_get_frame(clip2, t2)

        # If one frame is missing, use the other as fallback
        if frame1 is None and frame2 is None:
            return np.zeros((H, W, 3), dtype=np.uint8)
        if frame1 is None:
            return frame2.copy()
        if frame2 is None:
            return frame1.copy()

        # Calculate offsets with easing
        offset1 = -int(eased * W)      # clip1 slides left (off-screen)
        offset2 = int((1 - eased) * W)  # clip2 slides in from right

        result = np.zeros((H, W, 3), dtype=np.uint8)

        # Place clip1 (visible portion)
        x1_start = max(0, offset1)
        x1_end = min(W, offset1 + W)
        src_x1_start = max(0, -offset1)
        src_x1_end = src_x1_start + (x1_end - x1_start)
        if x1_end > x1_start and src_x1_end > src_x1_start:
            result[:, x1_start:x1_end] = frame1[:, src_x1_start:src_x1_end]

        # Place clip2 (visible portion)
        x2_start = max(0, offset2)
        x2_end = min(W, offset2 + W)
        src_x2_start = max(0, -offset2)
        src_x2_end = src_x2_start + (x2_end - x2_start)
        if x2_end > x2_start and src_x2_end > src_x2_start:
            result[:, x2_start:x2_end] = frame2[:, src_x2_start:src_x2_end]

        return result.astype(np.uint8)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Transition: Zoom
# ---------------------------------------------------------------------------

def apply_zoom(clip1, clip2, duration):
    """
    Zoom transition: clip1 zooms in (scale up) while fading out,
    and clip2 simultaneously zooms out (scale down from bigger) while fading in.

    Creates a "push through" effect where the camera appears to move
    through the scene into the next one. The gentle scaling and opacity
    blending suit the hand-drawn aesthetic.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip (first scene).
    clip2 : VideoClip
        Incoming clip (second scene).
    duration : float
        Duration of the transition in seconds.

    Returns
    -------
    VideoClip
        A single clip representing the zoom transition.
    """
    H, W = _get_dimensions(clip1, clip2)
    max_zoom = 0.35  # Maximum zoom factor (gentle, hand-drawn feel)

    def make_frame(t):
        t = max(0, min(t, duration))
        progress = t / duration
        eased = _ease_in_out(progress)

        t1, t2 = _get_time_offsets(clip1, clip2, t, duration)

        frame1 = _safe_get_frame(clip1, t1)
        frame2 = _safe_get_frame(clip2, t2)

        if frame1 is None and frame2 is None:
            return np.zeros((H, W, 3), dtype=np.uint8)
        if frame1 is None:
            return frame2.copy()
        if frame2 is None:
            return frame1.copy()

        # clip1: scale from 1.0 -> (1.0 + max_zoom), opacity from 1.0 -> 0.0
        scale1 = 1.0 + max_zoom * eased
        alpha1 = 1.0 - eased

        # clip2: scale from (1.0 + max_zoom) -> 1.0, opacity from 0.0 -> 1.0
        scale2 = 1.0 + max_zoom * (1.0 - eased)
        alpha2 = eased

        # Resize and center-crop clip1
        new_w1 = int(round(W * scale1))
        new_h1 = int(round(H * scale1))
        img1 = Image.fromarray(frame1)
        img1_resized = np.array(img1.resize((new_w1, new_h1), Image.Resampling.LANCZOS))
        x1 = (new_w1 - W) // 2
        y1 = (new_h1 - H) // 2
        frame1_scaled = img1_resized[y1:y1 + H, x1:x1 + W]

        # Resize and center-crop clip2
        new_w2 = int(round(W * scale2))
        new_h2 = int(round(H * scale2))
        img2 = Image.fromarray(frame2)
        img2_resized = np.array(img2.resize((new_w2, new_h2), Image.Resampling.LANCZOS))
        x2 = (new_w2 - W) // 2
        y2 = (new_h2 - H) // 2
        frame2_scaled = img2_resized[y2:y2 + H, x2:x2 + W]

        # Blend
        result = (frame1_scaled.astype(np.float32) * alpha1 +
                  frame2_scaled.astype(np.float32) * alpha2)

        return np.clip(result, 0, 255).astype(np.uint8)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Transition: Wipe
# ---------------------------------------------------------------------------

def apply_wipe(clip1, clip2, duration):
    """
    Wipe transition: a vertical line wipes across the screen,
    revealing the next clip behind it.

    Like a curtain being drawn horizontally, this creates a clean
    reveal effect. A soft feathering at the wipe edge gives it a
    gentle, hand-drawn feel.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip (first scene).
    clip2 : VideoClip
        Incoming clip (second scene).
    duration : float
        Duration of the transition in seconds.

    Returns
    -------
    VideoClip
        A single clip representing the wipe transition.
    """
    H, W = _get_dimensions(clip1, clip2)

    def make_frame(t):
        t = max(0, min(t, duration))
        progress = t / duration
        eased = _smoothstep(progress)

        t1, t2 = _get_time_offsets(clip1, clip2, t, duration)

        frame1 = _safe_get_frame(clip1, t1)
        frame2 = _safe_get_frame(clip2, t2)

        if frame1 is None and frame2 is None:
            return np.zeros((H, W, 3), dtype=np.uint8)
        if frame1 is None:
            return frame2.copy()
        if frame2 is None:
            return frame1.copy()

        # Wipe position: left to right
        wipe_x = int(eased * W)

        result = frame1.copy().astype(np.float32)

        # Show clip2 to the left of the wipe line
        if wipe_x > 0:
            result[:, :wipe_x] = frame2[:, :wipe_x].astype(np.float32)

        # Soft feathering at the wipe edge
        feather_width = max(2, int(W * 0.025))  # 2.5% of width
        feather_start = max(0, wipe_x - feather_width // 2)
        feather_end = min(W, wipe_x + feather_width // 2)

        for x in range(feather_start, feather_end):
            local_progress = (x - feather_start) / (feather_end - feather_start)
            blend = _smoothstep(local_progress)
            result[:, x] = (frame2[:, x].astype(np.float32) * blend +
                            frame1[:, x].astype(np.float32) * (1.0 - blend))

        return np.clip(result, 0, 255).astype(np.uint8)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Transition: Crossfade (fallback)
# ---------------------------------------------------------------------------

def _apply_fade(clip1, clip2, duration):
    """
    Simple crossfade transition: clip1 fades out while clip2 fades in.

    This is a basic fallback transition used as the default.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip.
    clip2 : VideoClip
        Incoming clip.
    duration : float
        Duration of the transition.

    Returns
    -------
    VideoClip
        A single clip representing the crossfade transition.
    """
    H, W = _get_dimensions(clip1, clip2)

    def make_frame(t):
        t = max(0, min(t, duration))
        progress = t / duration
        eased = _smoothstep(progress)

        t1, t2 = _get_time_offsets(clip1, clip2, t, duration)

        frame1 = _safe_get_frame(clip1, t1)
        frame2 = _safe_get_frame(clip2, t2)

        if frame1 is None and frame2 is None:
            return np.zeros((H, W, 3), dtype=np.uint8)
        if frame1 is None:
            return frame2.copy()
        if frame2 is None:
            return frame1.copy()

        alpha1 = 1.0 - eased
        alpha2 = eased

        result = (frame1.astype(np.float32) * alpha1 +
                  frame2.astype(np.float32) * alpha2)

        return np.clip(result, 0, 255).astype(np.uint8)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def apply_transition(clip1, clip2, duration, transition_type="fade"):
    """
    Unified dispatcher for all transition types.

    Routes to the appropriate transition function based on the
    ``transition_type`` string.

    Parameters
    ----------
    clip1 : VideoClip
        Outgoing clip (first scene).
    clip2 : VideoClip
        Incoming clip (second scene).
    duration : float
        Duration of the transition in seconds. Must be > 0.
    transition_type : str, optional
        Type of transition to apply. One of ``"slide"``, ``"zoom"``,
        ``"wipe"``, or ``"fade"``. Default is ``"fade"`` (simple crossfade).

    Returns
    -------
    VideoClip
        A single clip representing the transition.

    Raises
    ------
    ValueError
        If ``transition_type`` is not recognized.
    """
    if duration <= 0:
        raise ValueError(f"Transition duration must be > 0, got {duration}")

    transitions = {
        "slide": apply_slide,
        "zoom": apply_zoom,
        "wipe": apply_wipe,
        "fade": _apply_fade,
    }

    if transition_type not in transitions:
        raise ValueError(
            f"Unknown transition type: '{transition_type}'. "
            f"Supported types: {', '.join(sorted(transitions.keys()))}"
        )

    return transitions[transition_type](clip1, clip2, duration)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo():
    """
    Test all transitions with simple colored clips.

    Creates four test clips (red, green, blue, yellow) with a small
    moving element for visual reference, then runs each transition
    type between them and prints verification results.

    This function is useful for verifying that the transitions work
    correctly and for previewing their visual effects.
    """
    print("=" * 60)
    print("  Transition Demo")
    print("=" * 60)

    W, H = 480, 360
    clip_duration = 1.0
    transition_duration = 0.5

    # Create simple colored test clips
    colors = [
        (200, 50, 50),    # Red
        (50, 180, 50),    # Green
        (50, 50, 200),    # Blue
        (200, 200, 50),   # Yellow
    ]

    clips = []
    for i, color in enumerate(colors):
        def make_color_frame(t, rgb=color):
            frame = np.zeros((H, W, 3), dtype=np.uint8)
            frame[:, :] = rgb
            # Add a small moving white dot for visual reference
            cx = int(W * (0.2 + 0.6 * (t / clip_duration)))
            cy = H // 2
            for dy in range(-15, 16):
                for dx in range(-15, 16):
                    if dx * dx + dy * dy <= 225:
                        x, y = cx + dx, cy + dy
                        if 0 <= x < W and 0 <= y < H:
                            frame[y, x] = (255, 255, 255)
            return frame

        clip = VideoClip(make_color_frame, duration=clip_duration)
        clips.append(clip)

    # Test each transition type
    transition_types = ["slide", "zoom", "wipe", "fade"]

    for ttype in transition_types:
        print(f"\n  --- Testing '{ttype}' transition ---")
        try:
            transition = apply_transition(clips[0], clips[1], transition_duration, ttype)

            # Verify basic properties
            assert transition is not None, "Transition clip should not be None"
            assert abs(transition.duration - transition_duration) < 0.01, \
                f"Expected duration {transition_duration}, got {transition.duration}"

            # Test a few frames
            for t in [0, transition_duration / 2, transition_duration - 0.01]:
                frame = transition.get_frame(t)
                assert frame.shape == (H, W, 3), \
                    f"Frame shape mismatch at t={t}: {frame.shape}"
                assert frame.dtype == np.uint8, \
                    f"Frame dtype mismatch at t={t}: {frame.dtype}"

            print(f"    [OK] Duration: {transition.duration:.2f}s")
            print(f"    [OK] Frame shape: {transition.get_frame(0).shape}")
            print(f"    [OK] Frame dtype: {transition.get_frame(0).dtype}")

        except Exception as e:
            print(f"    [FAIL] {e}")

    # Test dispatching all transitions between all clip pairs
    print(f"\n  --- Testing sequential transitions ---")
    try:
        for i in range(len(clips) - 1):
            for ttype in transition_types:
                trans = apply_transition(clips[i], clips[i + 1], transition_duration, ttype)
                assert trans is not None
                _ = trans.get_frame(0.1)
        print(f"    [OK] All {len(clips) - 1} x {len(transition_types)} transitions pass")
    except Exception as e:
        print(f"    [FAIL] {e}")

    # Test invalid transition type
    print(f"\n  --- Testing error handling ---")
    try:
        apply_transition(clips[0], clips[1], transition_duration, "invalid_type")
        print(f"    [FAIL] Should have raised ValueError")
    except ValueError:
        print(f"    [OK] Invalid type raises ValueError")

    try:
        apply_transition(clips[0], clips[1], 0, "fade")
        print(f"    [FAIL] Should have raised ValueError for zero duration")
    except ValueError:
        print(f"    [OK] Zero duration raises ValueError")

    print(f"\n  {'=' * 60}")
    print(f"  All demo tests completed.")
    print(f"  {'=' * 60}")

    return clips


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo()