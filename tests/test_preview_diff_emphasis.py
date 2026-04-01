"""Tests for preview diff-emphasis overlay utilities."""

from __future__ import annotations

import numpy as np
from PIL import Image

from utils.preview_diff_emphasis import (
    build_diff_highlight_overlay_rgba,
    ink_mask_from_rgba,
    placed_image_union_bbox,
    rgba_pixel_diff_mask,
)


def test_placed_image_union_bbox() -> None:
    base = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    comp = Image.new("RGBA", (8, 8), (0, 255, 0, 255))
    x0, y0, x1, y1 = placed_image_union_bbox(base, (5, 10), comp, (20, 5))
    assert (x0, y0, x1, y1) == (5, 5, 28, 20)


def test_rgba_pixel_diff_mask_detects_change() -> None:
    a = np.zeros((4, 4, 4), dtype=np.uint8)
    b = np.zeros((4, 4, 4), dtype=np.uint8)
    b[1, 1] = (50, 0, 0, 255)
    m = rgba_pixel_diff_mask(a, b, squared_diff_threshold=100)
    assert m[1, 1]
    assert not m[0, 0]


def test_build_diff_highlight_overlay_non_empty_on_difference() -> None:
    base = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
    comp = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
    comp_px = comp.load()
    for x in range(6, 14):
        for y in range(6, 14):
            comp_px[x, y] = (0, 0, 0, 255)
    ov, (ox, oy) = build_diff_highlight_overlay_rgba(
        base,
        (0, 0),
        comp,
        (0, 0),
    )
    assert (ox, oy) == (0, 0)
    arr = np.asarray(ov)
    assert arr[..., 3].max() > 0


def test_same_geometry_blue_vs_red_line_no_emphasis() -> None:
    """Shared stroke with different palette: ink XOR should cancel (no overlay)."""
    w, h = 48, 48
    base = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    comp = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    bp = base.load()
    cp = comp.load()
    for y in range(10, 38):
        bp[24, y] = (0, 0, 255, 255)
        cp[24, y] = (255, 0, 0, 255)
    ov, _ = build_diff_highlight_overlay_rgba(base, (0, 0), comp, (0, 0))
    arr = np.asarray(ov)
    assert arr[..., 3].max() == 0


def test_edge_suppress_blocks_left_edge_comp_only() -> None:
    """Default edge strip removes highlights when the only ink change hugs the bbox border."""
    base = Image.new("RGBA", (24, 24), (255, 255, 255, 255))
    comp = Image.new("RGBA", (24, 24), (255, 255, 255, 255))
    comp.putpixel((0, 12), (0, 0, 0, 255))
    ov_open, _ = build_diff_highlight_overlay_rgba(
        base, (0, 0), comp, (0, 0), edge_suppress_px=0
    )
    assert np.asarray(ov_open)[..., 3].max() > 0
    ov_sup, _ = build_diff_highlight_overlay_rgba(
        base, (0, 0), comp, (0, 0), edge_suppress_px=6
    )
    assert np.asarray(ov_sup)[..., 3].max() == 0


def test_ink_mask_respects_luma_and_alpha() -> None:
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[0, 0] = (250, 250, 250, 255)
    rgba[0, 1] = (0, 0, 0, 255)
    rgba[1, 0] = (0, 0, 0, 10)
    m = ink_mask_from_rgba(rgba, luma_threshold=248, alpha_threshold=18)
    assert not m[0, 0] and m[0, 1] and not m[1, 0]
