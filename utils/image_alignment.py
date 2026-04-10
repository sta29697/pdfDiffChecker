"""Image alignment utilities for figure-frame and content detection.

Provides numpy/PIL-only implementations (no OpenCV) of:
- Frame-line tilt detection via least-squares on projection profiles
- Figure-frame bounding-rectangle detection via row/column projection
- Priority-based anchor-point detection (left→top→bottom→right strips)
- Overall ink-mass centroid detection
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional


def detect_top_line_angle(
    binary: "any",  # np.ndarray
    top_row: int,
    search_range: int = 10,
) -> float:
    """Detect the tilt angle of a near-horizontal frame line.

    For each column, find the topmost dark pixel inside
    ``[top_row ± search_range]`` and fit a line through the
    (column, row) pairs.  The slope gives the tilt.

    Args:
        binary: 2-D float array where 1.0 = dark (ink) pixel.
        top_row: Approximate row index of the horizontal frame line.
        search_range: ±row window to search around ``top_row``.

    Returns:
        Tilt angle in degrees (positive = right side lower in image coords).
    """
    try:
        import numpy as np

        h, w = binary.shape
        row_start = max(0, top_row - search_range)
        row_end = min(h, top_row + search_range + 1)

        col_positions: list[tuple[float, float]] = []
        for c in range(w):
            col_strip = binary[row_start:row_end, c]
            dark_indices = np.where(col_strip > 0.5)[0]
            if len(dark_indices) > 0:
                col_positions.append((float(c), float(row_start + dark_indices[0])))

        if len(col_positions) < max(10, w * 0.3):
            return 0.0

        cols_arr = np.array([p[0] for p in col_positions], dtype=float)
        rows_arr = np.array([p[1] for p in col_positions], dtype=float)

        median_r = float(np.median(rows_arr))
        mask = np.abs(rows_arr - median_r) < search_range
        if mask.sum() < 10:
            return 0.0

        A = np.column_stack([cols_arr[mask], np.ones(mask.sum())])
        result = np.linalg.lstsq(A, rows_arr[mask], rcond=None)
        m = float(result[0][0])  # drow / dcol
        return math.degrees(math.atan(m))
    except Exception:
        return 0.0


def detect_figure_frame_rect(
    image_path: Path,
) -> Optional[tuple[float, float, float, float, float]]:
    """Detect the 図枠 (drawing frame) bounding rectangle in an image file.

    Uses row/column projection profiles to find the outermost rectangular
    frame whose lines span a significant fraction of the image.

    Args:
        image_path: Path to a greyscale-convertible image (PNG, JPEG, …).

    Returns:
        ``(center_x, center_y, frame_width, frame_height, angle_deg)`` in
        image pixels, or ``None`` when no frame is detected.
    """
    try:
        import numpy as np
        from PIL import Image as _Image

        img = _Image.open(image_path).convert("L")
        arr = np.array(img, dtype=np.float32)
        h, w = arr.shape

        # Pixels darker than 200 are treated as ink (frame lines)
        binary = (arr < 200).astype(np.float32)

        row_sum = binary.sum(axis=1)  # dark pixels per row
        col_sum = binary.sum(axis=0)  # dark pixels per column

        # A frame line must span at least 30 % of the perpendicular dimension
        h_threshold = w * 0.30
        v_threshold = h * 0.30

        h_rows = np.where(row_sum > h_threshold)[0]
        v_cols = np.where(col_sum > v_threshold)[0]

        if len(h_rows) < 2 or len(v_cols) < 2:
            return None

        top = int(h_rows[0])
        bottom = int(h_rows[-1])
        left = int(v_cols[0])
        right = int(v_cols[-1])

        fw = right - left
        fh = bottom - top

        # Reject trivially small frames
        if fw < w * 0.1 or fh < h * 0.1:
            return None

        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0

        angle_deg = detect_top_line_angle(binary, top)
        return (cx, cy, float(fw), float(fh), angle_deg)
    except Exception:
        return None


def detect_priority_anchor(
    image_path: Path,
    frame_rect: tuple[float, float, float, float, float],
    *,
    inset_fraction: float = 0.03,
    strip_fraction: float = 0.30,
    min_ink_fraction: float = 0.005,
) -> Optional[tuple[float, float]]:
    """Detect a priority-based anchor point inside a detected figure frame.

    Examines four strips of the interior region in priority order
    (left → top → bottom → right) and returns the ink-cluster centroid of
    the first strip that contains a meaningful amount of ink.

    Within each strip the centroid is computed with **squared** ink-density
    weights so that large, dense components dominate over sparse labels or
    fine lines.

    Rationale for the priority order:
    - **Left**: In single-line diagrams the power source (stable reference)
      is on the left; load names that change extend rightward.
    - **Top**: In distribution diagrams the source busbar is at the top.
    - **Bottom**: Secondary fallback for bottom-heavy layouts.
    - **Right**: Last resort; most likely to contain changed elements.

    Args:
        image_path: Path to a greyscale-convertible image.
        frame_rect: ``(center_x, center_y, fw, fh, angle_deg)`` as returned
            by :func:`detect_figure_frame_rect`.
        inset_fraction: Fraction of frame size inset from each edge to skip
            the border lines themselves.
        strip_fraction: Width/height fraction used for each priority strip.
        min_ink_fraction: Minimum ratio of dark pixels in a strip required
            to treat it as a valid anchor candidate.

    Returns:
        ``(cx, cy)`` anchor in original image pixel coordinates for the
        highest-priority strip with sufficient ink, or ``None``.
    """
    try:
        import numpy as np
        from PIL import Image as _Image

        cx_f, cy_f, fw, fh, _angle = frame_rect
        img_left = cx_f - fw / 2.0
        img_top = cy_f - fh / 2.0

        inset_x = fw * inset_fraction
        inset_y = fh * inset_fraction
        crop_left = max(0, int(img_left + inset_x))
        crop_top = max(0, int(img_top + inset_y))

        img = _Image.open(image_path).convert("L")
        img_w, img_h = img.size
        crop_right = min(img_w, int(img_left + fw - inset_x))
        crop_bottom = min(img_h, int(img_top + fh - inset_y))

        if crop_right <= crop_left or crop_bottom <= crop_top:
            return None

        crop = img.crop((crop_left, crop_top, crop_right, crop_bottom))
        arr = np.array(crop, dtype=np.float32)
        binary = (arr < 200).astype(np.float32)

        h, w = binary.shape
        sw = max(1, int(w * strip_fraction))
        sh = max(1, int(h * strip_fraction))

        strips: list[tuple[any, int, int]] = [
            (binary[:, :sw],       0,      0),
            (binary[:sh, :],       0,      0),
            (binary[h - sh:, :],   0,  h - sh),
            (binary[:, w - sw:], w - sw,   0),
        ]

        for strip_arr, off_x, off_y in strips:
            s_h, s_w = strip_arr.shape
            if strip_arr.mean() < min_ink_fraction:
                continue

            col_w = (strip_arr ** 2).sum(axis=0)
            row_w = (strip_arr ** 2).sum(axis=1)

            col_total = col_w.sum()
            row_total = row_w.sum()
            if col_total == 0 or row_total == 0:
                continue

            cx_in = float(np.dot(np.arange(s_w, dtype=np.float32), col_w) / col_total)
            cy_in = float(np.dot(np.arange(s_h, dtype=np.float32), row_w) / row_total)

            return (crop_left + off_x + cx_in, crop_top + off_y + cy_in)

        return None

    except Exception:
        return None


def detect_content_centroid(
    image_path: Path,
    frame_rect: tuple[float, float, float, float, float],
    *,
    inset_fraction: float = 0.03,
) -> Optional[tuple[float, float]]:
    """Detect the overall ink-mass centroid inside a detected figure frame.

    Crops the interior of *frame_rect* and computes the weighted-average
    position of all dark pixels (centre of gravity of all drawing content).

    Args:
        image_path: Path to a greyscale-convertible image.
        frame_rect: ``(center_x, center_y, fw, fh, angle_deg)`` as returned
            by :func:`detect_figure_frame_rect`.
        inset_fraction: Fraction of frame size inset from each edge to skip
            the border lines.

    Returns:
        ``(cx, cy)`` centroid in original image pixel coordinates, or
        ``None`` when the interior contains no dark pixels.
    """
    try:
        import numpy as np
        from PIL import Image as _Image

        cx_f, cy_f, fw, fh, _angle = frame_rect
        img_left = cx_f - fw / 2.0
        img_top = cy_f - fh / 2.0

        inset_x = fw * inset_fraction
        inset_y = fh * inset_fraction
        crop_left = max(0, int(img_left + inset_x))
        crop_top = max(0, int(img_top + inset_y))

        img = _Image.open(image_path).convert("L")
        img_w, img_h = img.size
        crop_right = min(img_w, int(img_left + fw - inset_x))
        crop_bottom = min(img_h, int(img_top + fh - inset_y))

        if crop_right <= crop_left or crop_bottom <= crop_top:
            return None

        crop = img.crop((crop_left, crop_top, crop_right, crop_bottom))
        arr = np.array(crop, dtype=np.float32)
        binary = (arr < 200).astype(np.float32)

        if binary.sum() < 1.0:
            return None

        h_arr, w_arr = binary.shape
        col_weights = binary.sum(axis=0)
        row_weights = binary.sum(axis=1)

        col_idx = np.arange(w_arr, dtype=np.float32)
        row_idx = np.arange(h_arr, dtype=np.float32)

        cx_in_crop = float(np.dot(col_idx, col_weights) / col_weights.sum())
        cy_in_crop = float(np.dot(row_idx, row_weights) / row_weights.sum())

        return (crop_left + cx_in_crop, crop_top + cy_in_crop)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Canvas-space alignment helpers
# These accept raw transform tuples and return updated comp transform params
# so that the heavy logic lives here rather than in the large main_tab module.
# ---------------------------------------------------------------------------

def compute_frame_align(
    base_frame: tuple[float, float, float, float, float],
    comp_frame: tuple[float, float, float, float, float],
    base_t6: tuple,
    comp_t6: tuple,
) -> tuple[float, float, float, float]:
    """Compute new (r, tx, ty, s) for comp to align figure frames.

    Returns ``(new_c_r, new_c_tx, new_c_ty, new_c_s)``.
    """
    bcx, bcy, bfw, _bfh, b_frame_angle = base_frame
    ccx, ccy, cfw, _cfh, c_frame_angle = comp_frame
    b_r, b_tx, b_ty, b_s = float(base_t6[0]), float(base_t6[1]), float(base_t6[2]), float(base_t6[3])

    new_c_s = (bfw * b_s) / cfw if cfw > 0 else b_s
    base_canvas_cx = b_tx + bcx * b_s
    base_canvas_cy = b_ty + bcy * b_s
    new_c_tx = base_canvas_cx - ccx * new_c_s
    new_c_ty = base_canvas_cy - ccy * new_c_s
    new_c_r = b_r + (b_frame_angle - c_frame_angle)
    return (new_c_r, new_c_tx, new_c_ty, new_c_s)


def compute_content_align(
    base_centroid: tuple[float, float],
    comp_centroid: tuple[float, float],
    base_t6: tuple,
    comp_t6: tuple,
) -> tuple[float, float]:
    """Compute new (tx, ty) for comp to align ink-mass centroids.

    Returns ``(new_c_tx, new_c_ty)``.
    """
    b_tx, b_ty, b_s = float(base_t6[1]), float(base_t6[2]), float(base_t6[3])
    c_tx, c_ty, c_s = float(comp_t6[1]), float(comp_t6[2]), float(comp_t6[3])
    base_cx_canvas = b_tx + base_centroid[0] * b_s
    base_cy_canvas = b_ty + base_centroid[1] * b_s
    comp_cx_canvas = c_tx + comp_centroid[0] * c_s
    comp_cy_canvas = c_ty + comp_centroid[1] * c_s
    return (c_tx + (base_cx_canvas - comp_cx_canvas),
            c_ty + (base_cy_canvas - comp_cy_canvas))
