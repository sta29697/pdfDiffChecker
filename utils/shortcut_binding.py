"""Utility helpers for binding and unbinding multiple global keyboard shortcuts.

This module centralises the logic for registering (`bind_all`) and unregistering
(`unbind_all`) multiple keyboard shortcut patterns at once.  By funnelling all
binding operations through these helpers we avoid copy-pasting repetitive
`root.bind_all('<Key>', handler)` calls throughout the codebase.  It also makes
it trivial to extend the shortcut set – simply edit the pattern list in
``configurations.tool_settings.GLOBAL_SHORTCUT_PATTERNS``.

Example
-------
>>> from utils.shortcut_binding import bind_shortcuts
>>> from configurations.tool_settings import GLOBAL_SHORTCUT_PATTERNS as PAT
>>> bind_shortcuts(root, PAT["ROTATE_RIGHT"], handler)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Iterable
import tkinter as tk

logger = logging.getLogger(__name__)


def bind_shortcuts(root: tk.Misc, patterns: Iterable[str], handler: Callable) -> None:  # noqa: D401
    """Bind *all* shortcut ``patterns`` to *handler* using ``root.bind_all``.

    Args:
        root: Tkinter widget that owns the Tcl interpreter (usually ``Tk``).
        patterns: Iterable of event pattern strings (e.g. ``"<Control-r>"``).
        handler: Callback executed when an event matching a pattern occurs.
    """
    for pat in patterns:
        try:
            root.bind_all(pat, handler)
            logger.debug("Bound global shortcut pattern: %s", pat)
        except Exception as exc:  # pragma: no cover – guard against Tcl errors
            logger.error("Failed to bind pattern %s – %s", pat, exc)


def unbind_shortcuts(root: tk.Misc, patterns: Iterable[str]) -> None:  # noqa: D401
    """Unbind *all* shortcut ``patterns`` that were previously bound.

    Args:
        root: Tkinter widget that owns the Tcl interpreter (usually ``Tk``).
        patterns: Iterable of event pattern strings to unbind.
    """
    for pat in patterns:
        try:
            root.unbind_all(pat)
            logger.debug("Unbound global shortcut pattern: %s", pat)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to unbind pattern %s – %s", pat, exc)
