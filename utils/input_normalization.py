"""Strict numeric parsing with full-width to half-width normalization."""

from __future__ import annotations

import re
import unicodedata


def normalize_numeric_input_text(text: str) -> str:
    """Normalize user-typed numeric text (NFKC + common IME dash).

    Args:
        text: Raw entry text.

    Returns:
        Stripped half-width-oriented string safe to parse.
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\u30FC", "-")
    return normalized.strip()


def parse_strict_int(text: str) -> int:
    """Parse an integer string after normalization; reject non-digit junk.

    Args:
        text: User input.

    Returns:
        Parsed int.

    Raises:
        ValueError: If the string is not a plain integer (optional leading minus).
    """
    t = normalize_numeric_input_text(text)
    if not re.fullmatch(r"-?\d+", t):
        raise ValueError(f"not a strict integer: {text!r}")
    return int(t)


def parse_strict_float(text: str) -> float:
    """Parse a float after normalization; only digits, one optional dot, optional leading minus.

    Args:
        text: User input.

    Returns:
        Parsed float.

    Raises:
        ValueError: If the pattern is not a simple decimal literal.
    """
    t = normalize_numeric_input_text(text)
    if not re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", t):
        raise ValueError(f"not a strict float: {text!r}")
    return float(t)
