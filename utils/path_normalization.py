"""Normalize filesystem path strings for consistent storage and display."""

from __future__ import annotations

import os


def normalize_host_path(path_str: str) -> str:
    """Normalize a user or dialog path for the current OS.

    On Windows, ``os.path.normpath`` converts forward slashes to backslashes and
    collapses ``..`` / ``.`` so paths match other tabs and native APIs.

    Args:
        path_str: Raw path from an entry, dialog, or settings JSON.

    Returns:
        Normalized path string, or the stripped original if empty.
    """
    if path_str is None:
        return ""
    stripped = str(path_str).strip()
    if not stripped:
        return ""
    expanded = os.path.expandvars(os.path.expanduser(stripped))
    return os.path.normpath(expanded)
