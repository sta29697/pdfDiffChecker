"""Build a translucent overlay highlighting pixel differences between two preview layers.

Used by the main tab when both base and comparison transformed RGBA images are available.
Implements M6 plan: numpy + PIL only, no OpenCV.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
from PIL import Image, ImageFilter
from PIL.Image import Image as PILImage


def placed_image_union_bbox(
    base_img: PILImage,
    base_xy: Tuple[int, int],
    comp_img: PILImage,
    comp_xy: Tuple[int, int],
) -> Tuple[int, int, int, int]:
    """Return an axis-aligned bbox ``(x0, y0, x1, y1)`` covering both placed images.

    Args:
        base_img: Base layer image (already transformed for preview).
        base_xy: Canvas position (left, top) for the base image (anchor nw).
        comp_img: Comparison layer image (already transformed for preview).
        comp_xy: Canvas position for the comparison image (anchor nw).

    Returns:
        Integer canvas coordinates covering both images.
    """
    bx, by = int(base_xy[0]), int(base_xy[1])
    cx, cy = int(comp_xy[0]), int(comp_xy[1])
    bw, bh = base_img.size
    cw, ch = comp_img.size
    x0 = min(bx, cx)
    y0 = min(by, cy)
    x1 = max(bx + bw, cx + cw)
    y1 = max(by + bh, cy + ch)
    return (x0, y0, x1, y1)


def _rasterize_placed_rgba(
    img: PILImage,
    paste_xy: Tuple[int, int],
    bbox: Tuple[int, int, int, int],
) -> np.ndarray:
    """Paste ``img`` into an RGBA canvas sized to ``bbox``; return uint8 ``(H, W, 4)``."""
    x0, y0, x1, y1 = bbox
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    rgba = img.convert("RGBA")
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = int(paste_xy[0]) - x0
    py = int(paste_xy[1]) - y0
    canvas.paste(rgba, (px, py), rgba)
    return np.asarray(canvas, dtype=np.uint8)


def rgba_pixel_diff_mask(
    a: np.ndarray,
    b: np.ndarray,
    *,
    squared_diff_threshold: int = 180,
) -> np.ndarray:
    """Return a boolean mask where per-pixel squared channel error exceeds the threshold.

    Args:
        a: First image array ``(H, W, 4)`` uint8.
        b: Second image array, same shape as ``a``.
        squared_diff_threshold: Threshold on sum of squared channel differences (RGBA).

    Returns:
        Boolean array ``(H, W)``.

    Raises:
        ValueError: If ``a`` and ``b`` shapes differ.
    """
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch for diff mask: {a.shape} vs {b.shape}")
    # int16 overflows for large channel deltas (e.g. 200^2 * 3 > 32767).
    da = a.astype(np.int32) - b.astype(np.int32)
    sq = np.sum(da * da, axis=2)
    return sq > squared_diff_threshold


def refine_diff_mask_with_morphology(
    mask_bool: np.ndarray,
    *,
    open_size: int = 3,
    dilate_size: int = 9,
) -> np.ndarray:
    """Reduce salt noise with a small opening, then dilate to thicken regions.

    Args:
        mask_bool: Boolean mask ``(H, W)``.
        open_size: Side length for Min/Max opening (must be odd, >= 3), or 0 to skip.
        dilate_size: Side length for MaxFilter dilation (must be odd, >= 3), or 0 to skip.

    Returns:
        Boolean mask ``(H, W)`` after morphology.
    """
    h, w = mask_bool.shape
    if h == 0 or w == 0:
        return mask_bool
    u8 = (mask_bool.astype(np.uint8) * 255)
    pil = Image.fromarray(u8, mode="L")
    if open_size >= 3:
        pil = pil.filter(ImageFilter.MinFilter(open_size))
        pil = pil.filter(ImageFilter.MaxFilter(open_size))
    if dilate_size >= 3:
        pil = pil.filter(ImageFilter.MaxFilter(dilate_size))
    arr = np.asarray(pil, dtype=np.uint8)
    return arr > 127


def build_diff_highlight_overlay_rgba(
    base_img: PILImage,
    base_xy: Tuple[int, int],
    comp_img: PILImage,
    comp_xy: Tuple[int, int],
    *,
    squared_diff_threshold: int = 180,
    open_size: int = 3,
    dilate_size: int = 9,
    highlight_rgba: Tuple[int, int, int, int] = (255, 220, 0, 110),
) -> Tuple[Image.Image, Tuple[int, int]]:
    """Build an RGBA overlay and its canvas top-left position.

    Compares full-alpha transformed layers (before any display-only alpha softening).

    Args:
        base_img: Transformed base RGBA image.
        base_xy: Canvas (x, y) for base (nw).
        comp_img: Transformed comparison RGBA image (not softened).
        comp_xy: Canvas (x, y) for comparison (nw).
        squared_diff_threshold: Pixel difference sensitivity.
        open_size: Morphological opening size (odd, >= 3).
        dilate_size: Dilation MaxFilter size (odd, >= 3).
        highlight_rgba: Fill color including alpha.

    Returns:
        Tuple of ``(overlay_rgba, (x0, y0))`` where ``(x0, y0)`` is the bbox top-left.
    """
    bbox = placed_image_union_bbox(base_img, base_xy, comp_img, comp_xy)
    x0, y0, x1, y1 = bbox
    ra = _rasterize_placed_rgba(base_img, base_xy, bbox)
    rb = _rasterize_placed_rgba(comp_img, comp_xy, bbox)
    raw = rgba_pixel_diff_mask(ra, rb, squared_diff_threshold=squared_diff_threshold)
    refined = refine_diff_mask_with_morphology(
        raw,
        open_size=open_size,
        dilate_size=dilate_size,
    )
    hr, hg, hb, ha = highlight_rgba
    overlay = np.zeros_like(ra)
    overlay[refined] = (hr, hg, hb, ha)
    return Image.fromarray(overlay, mode="RGBA"), (x0, y0)
