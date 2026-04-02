"""Application-wide keyboard navigation: notebook shortcuts and custom Tab order.

Supports Alt+number (1..9) to select notebook tabs. Left/Right arrow keys do **not**
switch tabs (avoids false positives from ``VK_MENU`` / modifier state); use Alt+digits
instead. Horizontal and vertical arrows move focus within the current tab when spatial
navigation applies. Also: tab-strip focus helpers, per-tab focus chains, Combobox list opened with
Enter (not arrow keys when the list is closed), and Shift+Tab reverse.

On Windows, ``GetAsyncKeyState`` polling tracks Alt for chord detection; it does not
move notebook tabs via arrow keys.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Sequence, Tuple

# Optional Tcl helper to open ttk.Combobox popdown (Windows/macOS/Linux Tk 8.6+).
_TTK_COMBO_POST = "ttk::combobox::Post"


def _ttk_combobox_popdown_is_mapped(w: tk.Misc) -> bool:
    """Return True if this combobox's listbox popdown exists and is visible.

    Used so Up/Down can move spatial focus when the list is closed, while list
    navigation still works when the popdown is open.

    Args:
        w: Focus widget (typically ``ttk.Combobox``).

    Returns:
        True when the Tcl popdown toplevel is mapped, else False.
    """
    try:
        if w.winfo_class() != "TCombobox":
            return False
        pop = w.tk.call("ttk::combobox::PopdownWindow", w._w)
        if not pop:
            return False
        return str(w.tk.call("winfo", "ismapped", pop)) == "1"
    except tk.TclError:
        return False


# Bindtag prepended to every descendant so notebook tab arrows run before widget defaults
# (Entry/Text consume <Left>/<Right> with "break", so bind_all("all") never runs).
_TAB_NAV_BINDTAG = "PdfDiffTabNav"

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
        # Windows: sync Alt with hardware; Tk KeyPress for Alt is often missing.
        self._poll_prev_vk_menu: bool = False

        root.bind_all("<KeyPress>", self._on_key_press, add="+")
        root.bind_all("<KeyRelease>", self._on_key_release, add="+")
        # Left/Right: also on "all" for widgets created later without the prepended tag.
        root.bind_all("<Left>", self._on_left_in_tab_mode, add="+")
        root.bind_all("<Right>", self._on_right_in_tab_mode, add="+")
        root.bind_all("<Up>", self._on_up_down_spatial, add="+")
        root.bind_all("<Down>", self._on_up_down_spatial, add="+")
        root.bind_all("<Tab>", self._on_tab_forward, add="+")
        root.bind_all("<Shift-Tab>", self._on_tab_backward, add="+")
        # X11/Linux often emits ISO_Left_Tab for Shift+Tab; Windows Tk rejects this sequence.
        try:
            root.bind_all("<ISO_Left_Tab>", self._on_tab_backward, add="+")
        except tk.TclError:
            pass
        root.bind_all("<Escape>", self._on_escape, add="+")
        root.bind_all("<Return>", self._on_return_activate_focus_widget, add="+")
        root.bind_all("<KP_Enter>", self._on_return_activate_focus_widget, add="+")

        self._install_alt_digit_notebook_bindings(root)

        for _seq in ("<KeyPress-Alt_L>", "<KeyPress-Alt_R>"):
            try:
                root.bind_all(_seq, self._on_explicit_alt_press, add="+")
            except tk.TclError:
                pass
        for _seq in ("<KeyRelease-Alt_L>", "<KeyRelease-Alt_R>"):
            try:
                root.bind_all(_seq, self._on_explicit_alt_release, add="+")
            except tk.TclError:
                pass

        self._install_tab_arrow_priority_bindings()

        try:
            self._notebook.configure(takefocus=1)
        except tk.TclError:
            pass

        if sys.platform == "win32":
            self._root.after(40, self._poll_windows_vk_alt_loop)

    def _safe_focus_get(self) -> Optional[tk.Widget]:
        """Return ``Tk.focus_get()`` or None when the focus path cannot be resolved.

        While a ``ttk.Combobox`` popdown is open, Tk may report a focus path that
        includes a transient ``popdown`` segment; ``nametowidget`` then raises
        ``KeyError`` (seen on Windows with Python 3.12).

        Returns:
            The focused widget, or None if unknown or resolution failed.
        """
        try:
            return self._root.focus_get()  # type: ignore[no-any-return]
        except (KeyError, tk.TclError):
            return None

    def _install_alt_digit_notebook_bindings(self, root: tk.Misc) -> None:
        """Register Alt+1..9 on the main row and keypad to jump to notebook tabs."""
        for digit in range(1, 10):
            for pattern in (
                f"<Alt-{digit}>",
                f"<Alt-Key-{digit}>",
                f"<Alt-KeyPress-{digit}>",
            ):
                try:
                    root.bind_all(
                        pattern,
                        lambda e, d=digit: self._select_notebook_tab_by_alt_digit(e, d),
                        add="+",
                    )
                except tk.TclError:
                    pass
            try:
                root.bind_all(
                    f"<Alt-KP_{digit}>",
                    lambda e, d=digit: self._select_notebook_tab_by_alt_digit(e, d),
                    add="+",
                )
            except tk.TclError:
                pass

    def _select_notebook_tab_by_alt_digit(self, event: tk.Event, digit_one_based: int) -> str:
        """Select a notebook tab using Alt+number (1 = leftmost tab).

        If the digit is greater than the number of tabs, the event is ignored.

        Args:
            event: Tk key event.
            digit_one_based: 1-based index from the left (1..9).

        Returns:
            ``\"break\"`` so the chord is not processed as normal typing.
        """
        _ = event
        try:
            n = int(self._notebook.index("end"))
        except tk.TclError:
            return "break"
        if n <= 0 or digit_one_based < 1:
            return "break"
        idx = digit_one_based - 1
        if idx >= n:
            return "break"
        try:
            self._notebook.select(idx)
        except tk.TclError:
            pass
        return "break"

    def _focus_notebook_for_tab_strip(self) -> None:
        """Move keyboard focus to the main ``ttk.Notebook`` (tab strip host).

        Users expect Alt to move the caret context to the tab row; Tk does not do
        this automatically for ``ttk.Notebook``.
        """
        try:
            self._notebook.configure(takefocus=1)
        except tk.TclError:
            pass
        try:
            self._notebook.focus_force()
        except tk.TclError:
            pass

        def _retry_focus() -> None:
            try:
                if not self._tab_strip_mode or not self._root.winfo_exists():
                    return
                self._notebook.focus_force()
            except tk.TclError:
                pass

        self._root.after_idle(_retry_focus)

    def _arm_tab_strip_from_alt(self) -> None:
        """Enable tab-strip mode and focus the notebook (Alt / VK_MENU detection)."""
        self._tab_strip_mode = True
        self._alt_down = True
        self._alt_combo = False
        self._focus_notebook_for_tab_strip()

    @staticmethod
    def _vk_menu_physically_down() -> bool:
        """Return True if either Alt key is physically held (Windows only).

        Tk often does not deliver Alt as KeyPress/KeyRelease; this reads the OS.

        Returns:
            True when VK_MENU / left-menu / right-menu high bit is set.
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            u32 = ctypes.windll.user32
            for vk in (0x12, 0xA4, 0xA5):  # VK_MENU, VK_LMENU, VK_RMENU
                if int(u32.GetAsyncKeyState(vk)) & 0x8000:
                    return True
        except (AttributeError, OSError, ValueError, TypeError):
            pass
        return False

    def _keyboard_focus_in_this_app(self) -> bool:
        """Return True if keyboard focus belongs to a widget under our root.

        Returns:
            True when ``focus_get()`` is this app (not another window).
        """
        w = self._safe_focus_get()
        if w is None:
            return False
        cur: Optional[tk.Misc] = w
        while cur is not None:
            try:
                if cur == self._root:
                    return True
                cur = cur.master  # type: ignore[assignment]
            except tk.TclError:
                break
        try:
            return w.winfo_toplevel() == self._root
        except tk.TclError:
            return False

    def _windows_foreground_is_our_toplevel(self) -> bool:
        """Return True if the active Win32 HWND belongs to this Tk toplevel.

        After launch, ``focus_get()`` can be None even while our window is active;
        without this, Alt polling never arms tab-strip mode.

        ``GetForegroundWindow`` is often the decorative frame while ``winfo_id()``
        is an inner client HWND; comparing ``GetAncestor(..., GA_ROOT)`` ties them
        to the same top-level window.

        Returns:
            True when the foreground window shares our root ancestor, or ``fg`` is
            our widget or a descendant by parent walk.
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            u32 = ctypes.windll.user32
            ga_root = 2
            our = int(self._root.winfo_id())
            fg = int(u32.GetForegroundWindow())
            if fg == 0 or our == 0:
                return False
            our_root = int(u32.GetAncestor(our, ga_root))
            fg_root = int(u32.GetAncestor(fg, ga_root))
            if our_root and fg_root and our_root == fg_root:
                return True
            if fg == our:
                return True
            parent = fg
            for _ in range(64):
                parent = int(u32.GetParent(parent))
                if parent == 0:
                    break
                if parent == our:
                    return True
        except (tk.TclError, AttributeError, OSError, ValueError, TypeError):
            pass
        return False

    def _alt_poll_context_active(self) -> bool:
        """Return True when Alt polling should update tab-strip state (Windows).

        Returns:
            True if focus is in this app or this toplevel is the foreground window.
        """
        if self._keyboard_focus_in_this_app():
            return True
        return self._windows_foreground_is_our_toplevel()

    def _poll_windows_vk_alt_loop(self) -> None:
        """Poll hardware Alt so tab-strip mode works when Tk omits Alt events."""
        if sys.platform != "win32":
            return
        try:
            if not self._root.winfo_exists():
                return
        except tk.TclError:
            return
        self._root.after(40, self._poll_windows_vk_alt_loop)

        down = self._vk_menu_physically_down()
        if not self._alt_poll_context_active():
            self._poll_prev_vk_menu = down
            return

        if down and not self._poll_prev_vk_menu:
            self._arm_tab_strip_from_alt()
        elif not down and self._poll_prev_vk_menu:
            if self._alt_combo:
                self._tab_strip_mode = False
            self._alt_down = False
            self._alt_combo = False
        self._poll_prev_vk_menu = down

    def _install_tab_arrow_priority_bindings(self) -> None:
        """Prepend ``_TAB_NAV_BINDTAG`` so spatial Left/Right run before widget defaults.

        Without this, focused Entry/Text stops propagation before the ``all`` tag, so
        in-tab spatial navigation would not see arrow keys.
        """
        self._root.bind_class(_TAB_NAV_BINDTAG, "<Left>", self._on_left_in_tab_mode)
        self._root.bind_class(_TAB_NAV_BINDTAG, "<Right>", self._on_right_in_tab_mode)
        self._root.bind_class(_TAB_NAV_BINDTAG, "<Up>", self._on_up_down_spatial)
        self._root.bind_class(_TAB_NAV_BINDTAG, "<Down>", self._on_up_down_spatial)
        self._prepend_tab_nav_bindtag(self._root)

    def _prepend_tab_nav_bindtag(self, widget: tk.Misc) -> None:
        """Prepend ``_TAB_NAV_BINDTAG`` once per widget subtree.

        Args:
            widget: Root of the subtree (typically the application Tk toplevel).
        """
        try:
            tags = widget.bindtags()
        except tk.TclError:
            return
        if tags and tags[0] == _TAB_NAV_BINDTAG:
            pass
        elif _TAB_NAV_BINDTAG in tags:
            widget.bindtags((_TAB_NAV_BINDTAG,) + tuple(t for t in tags if t != _TAB_NAV_BINDTAG))
        else:
            widget.bindtags((_TAB_NAV_BINDTAG,) + tags)
        for child in widget.winfo_children():
            self._prepend_tab_nav_bindtag(child)

    def _on_explicit_alt_press(self, event: tk.Event) -> None:
        """Force tab-strip mode when the platform delivers Alt as a dedicated sequence."""
        _ = event
        self._arm_tab_strip_from_alt()

    def _on_explicit_alt_release(self, event: tk.Event) -> None:
        """Alt release cleanup (same rules as generic KeyRelease)."""
        self._on_key_release(event)

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
            if cur is self._notebook or cur is self._root:
                try:
                    return self._tab_frames[self._current_tab_index()]
                except IndexError:
                    return self._tab_frames[0] if self._tab_frames else None
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

    @staticmethod
    def _physical_alt_keycode(event: tk.Event) -> bool:
        """Return True if the key event is likely the Alt/Meta hardware key.

        Windows often omits reliable Alt ``KeyRelease`` / ``keysym`` pairing; using
        ``keycode`` keeps tab-strip mode usable. X11 commonly uses 64/108 for Alt.

        Args:
            event: Tk key event.

        Returns:
            True when the event should be treated as left/right Alt.
        """
        kc = int(getattr(event, "keycode", 0) or 0)
        if sys.platform == "win32":
            return kc in (18, 164, 165)
        return kc in (64, 108)

    @classmethod
    def _is_alt_modifier_key_event(cls, event: tk.Event) -> bool:
        """Detect Alt key press or release across platforms.

        Args:
            event: Tk key event.

        Returns:
            True if this event is for the Alt key itself.
        """
        keysym = getattr(event, "keysym", "") or ""
        if keysym in ("Alt_L", "Alt_R", "Meta_L", "Meta_R"):
            return True
        if keysym == "??" and cls._physical_alt_keycode(event):
            return True
        return cls._physical_alt_keycode(event)

    def _on_key_press(self, event: tk.Event) -> None:
        """Track Alt chords and enable tab-strip mode as soon as Alt is pressed."""
        keysym = getattr(event, "keysym", "") or ""
        if self._is_alt_modifier_key_event(event):
            self._arm_tab_strip_from_alt()
            return
        if not self._is_alt_modifier_key_event(event) and keysym not in ("Left", "Right"):
            alt_like = self._alt_down or (
                sys.platform == "win32" and self._vk_menu_physically_down()
            )
            if alt_like:
                self._alt_combo = True

    def _on_key_release(self, event: tk.Event) -> None:
        """Clear Alt tracking; drop tab-strip mode if Alt was used as a chord."""
        if not self._is_alt_modifier_key_event(event):
            return
        if self._alt_combo:
            self._tab_strip_mode = False
        self._alt_down = False
        self._alt_combo = False

    def _on_escape(self, event: tk.Event) -> Optional[str]:
        """Leave tab-strip mode on Escape."""
        if self._tab_strip_mode:
            self._tab_strip_mode = False
            return "break"
        return None

    def _on_left_in_tab_mode(self, event: tk.Event) -> Optional[str]:
        """Spatial focus left within the tab, or pass through to the widget."""
        if self._try_spatial_arrow_focus(event):
            return "break"
        return None

    def _on_right_in_tab_mode(self, event: tk.Event) -> Optional[str]:
        """Spatial focus right within the tab, or pass through to the widget."""
        if self._try_spatial_arrow_focus(event):
            return "break"
        return None

    def _on_up_down_spatial(self, event: tk.Event) -> Optional[str]:
        """Move focus to a chain widget above/below when not editing text-like widgets."""
        if self._try_spatial_arrow_focus(event):
            return "break"
        w = self._safe_focus_get()
        keysym = getattr(event, "keysym", "") or ""
        if (
            isinstance(w, ttk.Combobox)
            and keysym in ("Up", "Down")
            and self._is_focusable_state(w)
            and not _ttk_combobox_popdown_is_mapped(w)
        ):
            # Tk opens the list on Down when nothing else handles the key; require Enter
            # to post instead (see _on_return_activate_focus_widget).
            return "break"
        return None

    @staticmethod
    def _spatial_arrow_prefers_local_widget(w: Optional[tk.Widget], keysym: str) -> bool:
        """Return True when this arrow should be handled by the widget, not spatial focus.

        Single-line ``Entry`` / ``TEntry`` keep Left/Right for the caret; Up/Down can
        move focus to controls above/below (e.g. page number field to prev-page button).

        Args:
            w: Widget that currently has keyboard focus.
            keysym: Arrow keysym (``Up``, ``Down``, ``Left``, ``Right``).

        Returns:
            True when the key should not trigger spatial navigation.
        """
        if w is None:
            return False
        if keysym not in ("Up", "Down", "Left", "Right"):
            return False
        try:
            cls = w.winfo_class()
        except tk.TclError:
            return False
        if cls == "Text":
            return True
        if cls in ("Entry", "TEntry"):
            return keysym in ("Left", "Right")
        if cls in ("Spinbox", "TSpinbox", "Listbox", "TListbox", "Treeview"):
            return True
        if cls == "TCombobox":
            if keysym in ("Up", "Down"):
                if isinstance(w, ttk.Combobox) and _ttk_combobox_popdown_is_mapped(w):
                    return True
                return False
            return True
        return False

    @staticmethod
    def _widget_bbox_center_root(w: tk.Widget) -> Optional[Tuple[float, float]]:
        """Return the center of ``w`` in root screen coordinates.

        Args:
            w: Any widget.

        Returns:
            ``(x, y)`` center, or None if geometry is unavailable.
        """
        try:
            if not w.winfo_viewable():
                return None
            w.update_idletasks()
            rx = int(w.winfo_rootx())
            ry = int(w.winfo_rooty())
            rw = max(int(w.winfo_width()), 1)
            rh = max(int(w.winfo_height()), 1)
        except (tk.TclError, TypeError, ValueError):
            return None
        return (rx + rw * 0.5, ry + rh * 0.5)

    def _try_spatial_arrow_focus(self, event: tk.Event) -> bool:
        """If appropriate, focus the nearest tab-chain widget in the arrow direction.

        Ignores the key when the focused widget uses arrows locally (entries, lists).
        Uses the current tab's custom focus chain and screen geometry.

        Args:
            event: Arrow KeyPress.

        Returns:
            True when focus was moved and the event should be consumed.
        """
        cur = self._safe_focus_get()
        keysym = getattr(event, "keysym", "") or ""
        if self._spatial_arrow_prefers_local_widget(cur, keysym):
            return False
        direction = {
            "Left": (-1, 0),
            "Right": (1, 0),
            "Up": (0, -1),
            "Down": (0, 1),
        }.get(keysym)
        if direction is None:
            return False
        dx, dy = direction
        try:
            self._root.update_idletasks()
        except tk.TclError:
            pass
        tab_frame = self._tab_frame_for_focus(cur)
        if tab_frame is None:
            return False
        try:
            tab_idx = self._tab_frames.index(tab_frame)
        except ValueError:
            return False
        chain = self._chain_for_index(tab_idx)
        if not chain:
            return False
        origin = self._widget_bbox_center_root(cur) if cur is not None else None
        if origin is None:
            return False
        cx, cy = origin
        margin = 8.0
        skip_idx = self._chain_index(chain, cur) if cur is not None else None
        best_key: Optional[Tuple[float, int]] = None
        chosen: Optional[tk.Widget] = None
        for order_i, cand in enumerate(chain):
            if skip_idx is not None and order_i == skip_idx:
                continue
            if not self._is_focusable_state(cand):
                continue
            cc = self._widget_bbox_center_root(cand)
            if cc is None:
                continue
            ccx, ccy = cc
            if dx < 0 and not (ccx < cx - margin):
                continue
            if dx > 0 and not (ccx > cx + margin):
                continue
            if dy < 0 and not (ccy < cy - margin):
                continue
            if dy > 0 and not (ccy > cy + margin):
                continue
            dist_sq = (ccx - cx) ** 2 + (ccy - cy) ** 2
            key = (dist_sq, order_i)
            if best_key is None or key < best_key:
                best_key = key
                chosen = cand
        if chosen is None:
            return False
        try:
            chosen.focus_set()
        except tk.TclError:
            return False
        return True

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

        w = self._safe_focus_get()
        tab_frame = self._tab_frame_for_focus(w)
        if tab_frame is None:
            return None
        idx = self._tab_frames.index(tab_frame)
        chain = self._chain_for_index(idx)
        if not chain:
            return None
        pos = self._chain_index(chain, w) if w else None
        # When focus is not on (or inside) a chain widget, defer to Tk traversal.
        # Otherwise Shift+Tab used start_idx=0 and jumped to the chain end, skipping
        # the reverse of whatever Tk Tab order had reached.
        if pos is None:
            return None
        nxt = self._next_chain_index(chain, pos, 1)
        chain[nxt].focus_set()
        return "break"

    def _on_tab_backward(self, event: tk.Event) -> Optional[str]:
        """Shift+Tab: reverse custom chain (inverse of Tab)."""
        if self._tab_strip_mode:
            self._tab_strip_mode = False
            chain = self._chain_for_index(self._current_tab_index())
            if chain:
                prv = self._next_chain_index(chain, 0, -1)
                chain[prv].focus_set()
                return "break"
            return None

        w = self._safe_focus_get()
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
        prv = self._next_chain_index(chain, pos, -1)
        chain[prv].focus_set()
        return "break"

    @staticmethod
    def _widget_reserves_return_for_text_commit(w: tk.Widget) -> bool:
        """Return True if Return should keep default behavior (text fields, lists).

        Args:
            w: Widget with keyboard focus.

        Returns:
            True when Enter must not be turned into a button activate.
        """
        try:
            cls = w.winfo_class()
        except tk.TclError:
            return True
        if cls in (
            "Text",
            "Entry",
            "TEntry",
            "Spinbox",
            "TSpinbox",
            "Listbox",
            "TListbox",
            "Treeview",
        ):
            return True
        if cls == "TCombobox":
            try:
                st = str(w.cget("state")).lower()
            except tk.TclError:
                return True
            return "readonly" not in st
        return False

    @staticmethod
    def _invoke_widget_if_enabled(w: tk.Widget) -> bool:
        """Call ``invoke()`` on a classic Tk button-like widget if not disabled.

        Args:
            w: ``tk.Button``, ``Checkbutton``, or ``Radiobutton``.

        Returns:
            True if ``invoke`` ran.
        """
        try:
            st = str(w.cget("state")).lower()
            if st == "disabled":
                return False
        except tk.TclError:
            pass
        try:
            w.invoke()  # type: ignore[attr-defined]
            return True
        except tk.TclError:
            return False

    @staticmethod
    def _invoke_ttk_button_like_if_enabled(w: tk.Widget) -> bool:
        """Call ``invoke()`` on a ttk button-like widget if not disabled.

        Args:
            w: ``ttk.Button``, ``Checkbutton``, or ``Radiobutton``.

        Returns:
            True if ``invoke`` ran.
        """
        try:
            if "disabled" in w.state():
                return False
        except tk.TclError:
            pass
        try:
            w.invoke()  # type: ignore[attr-defined]
            return True
        except tk.TclError:
            return False

    def _on_return_activate_focus_widget(self, event: tk.Event) -> Optional[str]:
        """Activate the focused button (or check/radio) with Enter / KP_Enter.

        Tk does not always bind Return to ``invoke`` for ``Button``; this matches
        common keyboard UX while leaving Entry/Text/List behavior unchanged.

        Args:
            event: Key event (unused).

        Returns:
            ``\"break\"`` when the key was consumed.
        """
        _ = event
        w = self._safe_focus_get()
        if w is None:
            return None
        if isinstance(w, ttk.Combobox):
            try:
                st = str(w.cget("state")).lower()
            except tk.TclError:
                st = ""
            if "readonly" in st and self._is_focusable_state(w):
                try:
                    self._root.tk.call(_TTK_COMBO_POST, w._w)  # type: ignore[attr-defined]
                    return "break"
                except tk.TclError:
                    return None
            if "readonly" not in st:
                return None
        if self._widget_reserves_return_for_text_commit(w):
            return None
        if isinstance(w, (tk.Button, tk.Checkbutton, tk.Radiobutton)):
            if self._invoke_widget_if_enabled(w):
                return "break"
            return None
        if isinstance(w, (ttk.Button, ttk.Checkbutton, ttk.Radiobutton)):
            if self._invoke_ttk_button_like_if_enabled(w):
                return "break"
            return None
        return None
