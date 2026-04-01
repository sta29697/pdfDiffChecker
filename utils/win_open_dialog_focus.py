"""Windows-only: move keyboard focus to the file list in the native Open dialog.

Tk's ``filedialog.askopenfilename`` blocks the event loop, but scheduled ``after``
callbacks on the parent still run while the modal dialog is shown. We repeatedly
try to focus the list view (classic ``lst2`` / ``SysListView32``) so arrow keys
navigate folders without starting in the file-name edit.
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from typing import Any, List

user32 = ctypes.windll.user32

# Resource id for the file list in the classic GetOpenFileName dialog (lst2).
_OFN_LST2 = 0x0461


def _get_class_name(hwnd: int) -> str:
    """Return the Win32 window class name for ``hwnd``."""
    buf = ctypes.create_unicode_buffer(260)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 260)
    return buf.value


def _dfs_find_sys_listview(root_hwnd: int) -> int:
    """Depth-first search for the first ``SysListView32`` under ``root_hwnd``."""
    stack: List[int] = [root_hwnd]
    seen: set[int] = set()
    while stack:
        h = stack.pop()
        if h in seen:
            continue
        seen.add(h)
        if _get_class_name(h) == "SysListView32":
            return h
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        kids: List[int] = []

        def _collect(child: wintypes.HWND, _lp: wintypes.LPARAM) -> bool:
            kids.append(int(child))
            return True

        user32.EnumChildWindows(wintypes.HWND(h), WNDENUMPROC(_collect), 0)
        stack.extend(reversed(kids))
    return 0


def try_focus_foreground_open_file_list() -> None:
    """If the foreground window looks like an Open dialog, focus its file list."""
    if sys.platform != "win32":
        return
    try:
        fg = int(user32.GetForegroundWindow())
        if fg == 0:
            return
        lst = int(user32.GetDlgItem(wintypes.HWND(fg), _OFN_LST2))
        if lst != 0:
            user32.SetFocus(wintypes.HWND(lst))
            return
        target = _dfs_find_sys_listview(fg)
        if target != 0:
            user32.SetFocus(wintypes.HWND(target))
    except (AttributeError, OSError, ValueError, TypeError, ctypes.ArgumentError):
        pass


def schedule_open_file_dialog_list_focus_attempts(
    parent: tk.Misc,
    delays_ms: tuple[int, ...] = (30, 80, 160, 320, 600, 1000),
) -> List[Any]:
    """Schedule repeated attempts to focus the Open dialog file list.

    Args:
        parent: Tk widget used for ``after`` scheduling (usually the app root).
        delays_ms: Delays after which each attempt runs.

    Returns:
        Tk ``after`` ids; cancel in ``finally`` when the dialog closes.
    """
    job_ids: List[Any] = []
    for ms in delays_ms:

        def _fire(_m: int = ms) -> None:
            try_focus_foreground_open_file_list()

        job_ids.append(parent.after(ms, _fire))
    return job_ids


def cancel_scheduled_focus_attempts(parent: tk.Misc, job_ids: List[Any]) -> None:
    """Cancel jobs returned by ``schedule_open_file_dialog_list_focus_attempts``."""
    for jid in job_ids:
        try:
            parent.after_cancel(jid)
        except (tk.TclError, ValueError, AttributeError, TypeError):
            pass
