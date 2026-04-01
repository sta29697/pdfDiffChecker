"""Application-wide keyboard navigation: notebook tab-strip mode and custom Tab order.

Supports Alt-alone activation of tab switching (Left/Right), custom focus chains
for the main tab, Combobox dropdown via Down arrow, and Shift+Tab reverse.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Sequence

# Optional Tcl helper to open ttk.Combobox popdown (Windows/macOS/Linux Tk 8.6+).
_TTK_COMBO_POST = "ttk::combobox::Post"


class KeyboardNavigationShell:
    """Binds global keys for notebook tab mode and per-tab focus chains.

    Attributes:
        root: Main Tk window.
        notebook: Main ttk.Notebook.
        tab_frames: Notebook page widgets in tab index order.
        chain_for_index: Returns focus chain for a tab index, or None for default Tk traversal.
    """

    def __init__(
        self,
        root: tk.Tk,
        notebook: ttk.Notebook,
        tab_frames: Sequence[tk.Widget],
        chain_for_index: Callable[[int], Optional[List[tk.Widget]]],
    ) -> None:
        """Initialize the shell and install bindings.

        Args:
            root: Application root window.
            notebook: Tabbed notebook widget.
            tab_frames: Container frames for each tab (same order as notebook tabs).
            chain_for_index: Factory returning ordered focusable widgets for a tab, or None.
        """
        self._root = root
        self._notebook = notebook
        self._tab_frames = list(tab_frames)
        self._chain_for_index = chain_for_index
        self._tab_strip_mode = False
        self._alt_down = False
        self._alt_combo = False

        root.bind_all("<KeyPress>", self._on_key_press, add="+")
        root.bind_all("<KeyRelease>", self._on_key_release, add="+")
        root.bind_all("<Left>", self._on_left_in_tab_mode, add="+")
        root.bind_all("<Right>", self._on_right_in_tab_mode, add="+")
        root.bind_all("<Tab>", self._on_tab_forward, add="+")
        root.bind_all("<Shift-Tab>", self._on_tab_backward, add="+")
        # X11/Linux often emits ISO_Left_Tab for Shift+Tab; Windows Tk rejects this sequence.
        try:
            root.bind_all("<ISO_Left_Tab>", self._on_tab_backward, add="+")
        except tk.TclError:
            pass
        root.bind_all("<Escape>", self._on_escape, add="+")
        root.bind_all("<KeyPress-Down>", self._on_down_combobox, add="+")

    def _current_tab_index(self) -> int:
        """Return the index of the currently selected notebook tab.

        Returns:
            Zero-based tab index, or 0 if the notebook state is invalid.
        """
        try:
            return int(self._notebook.index(self._notebook.select()))
        except tk.TclError:
            return 0

    def _tab_frame_for_focus(self, w: Optional[tk.Widget]) -> Optional[tk.Widget]:
        """Find which registered tab frame contains the focus widget.

        Args:
            w: Widget that has keyboard focus, or None.

        Returns:
            The matching tab container from ``tab_frames``, or None.
        """
        if w is None:
            return None
        cur: Optional[tk.Widget] = w
        while cur is not None:
            if cur in self._tab_frames:
                return cur
            cur = cur.master  # type: ignore[assignment]
        return None

    def _chain_index(self, chain: List[tk.Widget], w: tk.Widget) -> Optional[int]:
        """Resolve which chain element owns this widget (walk up masters).

        Args:
            chain: Ordered focus targets.
            w: Current focus widget.

        Returns:
            Index in chain, or None if not part of the chain.
        """
        cur: Optional[tk.Widget] = w
        while cur is not None:
            try:
                return chain.index(cur)
            except ValueError:
                cur = cur.master  # type: ignore[assignment]
        return None

    @staticmethod
    def _is_focusable_state(w: tk.Widget) -> bool:
        """Return False if the widget reports a disabled state.

        Args:
            w: Candidate widget.

        Returns:
            True if focus should be allowed.
        """
        try:
            st = w.cget("state")
            if str(st).lower() == "disabled":
                return False
        except tk.TclError:
            pass
        return True

    def _next_chain_index(self, chain: List[tk.Widget], start: int, step: int) -> int:
        """Step along chain skipping disabled widgets (wrap).

        Args:
            chain: Focus order.
            start: Starting index (exclusive for first hop from current).
            step: +1 forward, -1 backward.

        Returns:
            New index in ``chain``.
        """
        n = len(chain)
        if n == 0:
            return 0
        i = start
        for _ in range(n + 1):
            i = (i + step) % n
            if self._is_focusable_state(chain[i]):
                return i
        return start

    def _on_key_press(self, event: tk.Event) -> None:
        """Track Alt chords for tab-strip mode."""
        keysym = getattr(event, "keysym", "") or ""
        if keysym in ("Alt_L", "Alt_R"):
            self._alt_down = True
            self._alt_combo = False
        elif self._alt_down and keysym not in ("Alt_L", "Alt_R"):
            self._alt_combo = True

    def _on_key_release(self, event: tk.Event) -> None:
        """Enter tab-strip mode on Alt-alone release."""
        keysym = getattr(event, "keysym", "") or ""
        if keysym in ("Alt_L", "Alt_R"):
            if self._alt_down and not self._alt_combo:
                self._tab_strip_mode = True
            self._alt_down = False
            self._alt_combo = False

    def _on_escape(self, event: tk.Event) -> Optional[str]:
        """Leave tab-strip mode on Escape."""
        if self._tab_strip_mode:
            self._tab_strip_mode = False
            return "break"
        return None

    def _on_left_in_tab_mode(self, event: tk.Event) -> Optional[str]:
        """Select previous notebook tab when tab-strip mode is active."""
        if not self._tab_strip_mode:
            return None
        try:
            n = self._notebook.index("end")
            if n <= 0:
                return "break"
            idx = int(self._notebook.index(self._notebook.select()))
            self._notebook.select((idx - 1) % n)
        except tk.TclError:
            pass
        return "break"

    def _on_right_in_tab_mode(self, event: tk.Event) -> Optional[str]:
        """Select next notebook tab when tab-strip mode is active."""
        if not self._tab_strip_mode:
            return None
        try:
            n = self._notebook.index("end")
            if n <= 0:
                return "break"
            idx = int(self._notebook.index(self._notebook.select()))
            self._notebook.select((idx + 1) % n)
        except tk.TclError:
            pass
        return "break"

    def _on_tab_forward(self, event: tk.Event) -> Optional[str]:
        """Custom Tab order for tabs that provide a chain; else default."""
        if self._tab_strip_mode:
            self._tab_strip_mode = False
            chain = self._chain_for_index(self._current_tab_index())
            if chain:
                nxt = self._next_chain_index(chain, -1, 1)
                chain[nxt].focus_set()
                return "break"
            return None

        w = self._root.focus_get()
        tab_frame = self._tab_frame_for_focus(w)
        if tab_frame is None:
            return None
        idx = self._tab_frames.index(tab_frame)
        chain = self._chain_for_index(idx)
        if not chain:
            return None
        pos = self._chain_index(chain, w) if w else None
        if pos is None:
            return None
        nxt = self._next_chain_index(chain, pos, 1)
        chain[nxt].focus_set()
        return "break"

    def _on_tab_backward(self, event: tk.Event) -> Optional[str]:
        """Shift+Tab: reverse custom chain."""
        w = self._root.focus_get()
        tab_frame = self._tab_frame_for_focus(w)
        if tab_frame is None:
            return None
        idx = self._tab_frames.index(tab_frame)
        chain = self._chain_for_index(idx)
        if not chain:
            return None
        pos = self._chain_index(chain, w) if w else None
        if pos is None:
            return None
        nxt = self._next_chain_index(chain, pos, -1)
        chain[nxt].focus_set()
        return "break"

    def _on_down_combobox(self, event: tk.Event) -> Optional[str]:
        """Open ttk.Combobox list when Down is pressed and list is closed."""
        w = self._root.focus_get()
        if not isinstance(w, ttk.Combobox):
            return None
        if not self._is_focusable_state(w):
            return None
        try:
            self._root.tk.call(_TTK_COMBO_POST, w._w)  # type: ignore[attr-defined]
            return "break"
        except tk.TclError:
            return None
