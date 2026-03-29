"""Helpers for preview/export transform tuples with optional mirror flags."""

from __future__ import annotations

from typing import Sequence, Tuple, Union

# (rotation_deg, tx, ty, scale, flip_h, flip_v) — flip_* are 0/1 toggles (mirror before rotation).
TransformTuple = Tuple[float, float, float, float, int, int]


def as_transform6(value: Union[Sequence[float], Sequence[int], TransformTuple]) -> TransformTuple:
    """Coerce a 4- or 6-element sequence to a full transform tuple.

    Args:
        value: Stored transform (legacy 4-tuple or 6-tuple).

    Returns:
        ``(r, tx, ty, s, flip_h, flip_v)`` with flip flags defaulting to 0.
    """
    if len(value) >= 6:
        return (
            float(value[0]),
            float(value[1]),
            float(value[2]),
            float(value[3]),
            int(value[4]) & 1,
            int(value[5]) & 1,
        )
    if len(value) >= 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]), 0, 0)
    raise ValueError(f"transform tuple must have at least 4 elements, got {len(value)}")


def pack_transform6(
    r: float,
    tx: float,
    ty: float,
    s: float,
    flip_h: int = 0,
    flip_v: int = 0,
) -> TransformTuple:
    """Build a normalized 6-element transform tuple."""
    return (float(r), float(tx), float(ty), float(s), int(flip_h) & 1, int(flip_v) & 1)
