"""Tests for preview diff-emphasis overlay utilities."""

from __future__ import annotations

import numpy as np
from PIL import Image

from utils.preview_diff_emphasis import (
    build_diff_highlight_overlay_rgba,
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
    base = Image.new("RGBA", (20, 20), (200, 200, 200, 255))
    comp = Image.new("RGBA", (20, 20), (200, 200, 200, 255))
    comp_px = comp.load()
    for x in range(6, 14):
        for y in range(6, 14):
            comp_px[x, y] = (0, 0, 0, 255)
    ov, (ox, oy) = build_diff_highlight_overlay_rgba(
        base,
        (0, 0),
        comp,
        (0, 0),
        squared_diff_threshold=50,
        open_size=3,
        dilate_size=5,
    )
    assert (ox, oy) == (0, 0)
    arr = np.asarray(ov)
    assert arr[..., 3].max() > 0
