"""Build a translucent overlay highlighting structural (ink) differences between two layers.

Uses BT.601 luminance and alpha for ink detection, then exclusive regions with optional
dilated matching to ignore palette-only differences on shared strokes. numpy + PIL only.
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


def luma_bt601_rgba(rgba: np.ndarray) -> np.ndarray:
    """BT.601 luma per pixel from RGB channels (float32, shape HxW)."""
    r = rgba[..., 0].astype(np.float32)
    g = rgba[..., 1].astype(np.float32)
    b = rgba[..., 2].astype(np.float32)
    return 0.299 * r + 0.587 * g + 0.114 * b


def ink_mask_from_rgba(
    rgba: np.ndarray,
    *,
    luma_threshold: int = 248,
    alpha_threshold: int = 18,
) -> np.ndarray:
    """Boolean mask where a pixel counts as ink (dark enough and sufficiently opaque).

    Args:
        rgba: ``(H, W, 4)`` uint8 RGBA.
        luma_threshold: Pixels with BT.601 luma strictly below this are candidate ink.
        alpha_threshold: Alpha must be strictly greater than this value.

    Returns:
        Boolean array ``(H, W)``.
    """
    y = luma_bt601_rgba(rgba)
    a = rgba[..., 3].astype(np.int32)
    return (y < float(luma_threshold)) & (a > int(alpha_threshold))


def _mask_dilate_max(mask_bool: np.ndarray, size: int) -> np.ndarray:
    """Dilate a boolean mask with a square MaxFilter (odd size >= 3)."""
    if size < 3:
        return mask_bool
    h, w = mask_bool.shape
    if h == 0 or w == 0:
        return mask_bool
    u8 = (mask_bool.astype(np.uint8) * 255)
    pil = Image.fromarray(u8, mode="L")
    pil = pil.filter(ImageFilter.MaxFilter(size))
    return np.asarray(pil, dtype=np.uint8) > 127


def _apply_edge_suppress(mask_bool: np.ndarray, px: int) -> np.ndarray:
    """Clear a margin of ``px`` pixels on each edge of the mask."""
    if px <= 0:
        return mask_bool
    h, w = mask_bool.shape
    if h <= 2 * px or w <= 2 * px:
        return np.zeros_like(mask_bool)
    out = mask_bool.copy()
    out[:px, :] = False
    out[h - px :, :] = False
    out[:, :px] = False
    out[:, w - px :] = False
    return out


def refine_diff_mask_with_morphology(
    mask_bool: np.ndarray,
    *,
    open_size: int = 0,
    dilate_size: int = 5,
) -> np.ndarray:
    """Optional opening then MaxFilter dilation on a boolean mask.

    Args:
        mask_bool: Boolean mask ``(H, W)``.
        open_size: Min/Max opening side length (odd, >= 3), or 0 to skip.
        dilate_size: MaxFilter dilation side length (odd, >= 3), or 0 to skip.

    Returns:
        Boolean mask after morphology.
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


def rgba_pixel_diff_mask(
    a: np.ndarray,
    b: np.ndarray,
    *,
    squared_diff_threshold: int = 180,
) -> np.ndarray:
    """Return a boolean mask where per-pixel squared channel error exceeds the threshold.

    Legacy helper for tests; main overlay uses :func:`ink_mask_from_rgba` flow.

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
    da = a.astype(np.int32) - b.astype(np.int32)
    sq = np.sum(da * da, axis=2)
    return sq > squared_diff_threshold


def build_diff_highlight_overlay_rgba(
    base_img: PILImage,
    base_xy: Tuple[int, int],
    comp_img: PILImage,
    comp_xy: Tuple[int, int],
    *,
    base_highlight_rgba: Tuple[int, int, int, int] = (62, 119, 210, 110),
    comp_highlight_rgba: Tuple[int, int, int, int] = (192, 55, 85, 110),
    luma_threshold: int = 248,
    alpha_threshold: int = 18,
    ink_match_dilate_size: int = 5,
    edge_suppress_px: int = 6,
    open_size: int = 0,
    dilate_size: int = 5,
    same_cell_pixel_diff: bool = True,
    same_cell_sq_diff_threshold: int = 220,
    same_cell_supplement_dilate: int = 5,
) -> Tuple[Image.Image, Tuple[int, int]]:
    """Build an RGBA overlay from structural (ink) exclusive regions.

    Comparison-only ink is tinted with ``comp_highlight_rgba``; base-only ink with
    ``base_highlight_rgba``. Shared stroke locations (after dilated matching) do not
    highlight, so palette-only differences on the same geometry are suppressed.

    Args:
        base_img: Transformed base RGBA image.
        base_xy: Canvas (x, y) for base (nw).
        comp_img: Transformed comparison RGBA (not display-softened).
        comp_xy: Canvas (x, y) for comparison (nw).
        base_highlight_rgba: Semi-transparent RGBA for base-only ink.
        comp_highlight_rgba: Semi-transparent RGBA for comparison-only ink.
        luma_threshold: BT.601 luma below this counts as ink.
        alpha_threshold: Alpha above this counts as ink.
        ink_match_dilate_size: Dilate opponent ink before XOR (0 = strict masks).
        edge_suppress_px: Clear highlights in a border this many pixels wide (0 = off).
        open_size: Morphological opening size (0 = off).
        dilate_size: Final dilation of exclusive masks (0 = off).
        same_cell_pixel_diff: When True, add highlights where both layers show ink but
            RGBA still differs (catches small glyph edits suppressed by dilated XOR).
        same_cell_sq_diff_threshold: Squared channel-difference threshold for that mask.
        same_cell_supplement_dilate: Odd MaxFilter size (>=3) to widen thin supplement
            regions for visibility; 0 skips dilation.

    Returns:
        Tuple of ``(overlay_rgba, (x0, y0))`` where ``(x0, y0)`` is the bbox top-left.
    """
    bbox = placed_image_union_bbox(base_img, base_xy, comp_img, comp_xy)
    x0, y0, x1, y1 = bbox
    ra = _rasterize_placed_rgba(base_img, base_xy, bbox)
    rb = _rasterize_placed_rgba(comp_img, comp_xy, bbox)

    base_ink = ink_mask_from_rgba(
        ra, luma_threshold=luma_threshold, alpha_threshold=alpha_threshold
    )
    comp_ink = ink_mask_from_rgba(
        rb, luma_threshold=luma_threshold, alpha_threshold=alpha_threshold
    )

    if ink_match_dilate_size >= 3:
        base_for_match = _mask_dilate_max(base_ink, ink_match_dilate_size)
        comp_for_match = _mask_dilate_max(comp_ink, ink_match_dilate_size)
    else:
        base_for_match = base_ink
        comp_for_match = comp_ink

    comp_only = comp_ink & ~base_for_match
    base_only = base_ink & ~comp_for_match

    comp_only = _apply_edge_suppress(comp_only, edge_suppress_px)
    base_only = _apply_edge_suppress(base_only, edge_suppress_px)

    comp_only = refine_diff_mask_with_morphology(
        comp_only, open_size=open_size, dilate_size=dilate_size
    )
    base_only = refine_diff_mask_with_morphology(
        base_only, open_size=open_size, dilate_size=dilate_size
    )

    br, bg, bb, ba = base_highlight_rgba
    cr, cg, cb, ca = comp_highlight_rgba
    overlay = np.zeros_like(ra)
    # Comparison-side emphasis wins where both masks overlap after morphology.
    overlay[base_only] = (br, bg, bb, ba)
    overlay[comp_only] = (cr, cg, cb, ca)

    if same_cell_pixel_diff:
        pd = rgba_pixel_diff_mask(
            ra, rb, squared_diff_threshold=int(same_cell_sq_diff_threshold)
        )
        overlap_raw = base_ink & comp_ink & pd
        overlap_raw = _apply_edge_suppress(overlap_raw, edge_suppress_px)
        supp_d = int(same_cell_supplement_dilate)
        supp = refine_diff_mask_with_morphology(
            overlap_raw,
            open_size=0,
            dilate_size=supp_d if supp_d >= 3 else 0,
        )
        already = base_only | comp_only
        supp &= ~already
        if np.any(supp):
            overlay[supp] = (cr, cg, cb, ca)

    return Image.fromarray(overlay, mode="RGBA"), (x0, y0)
