from __future__ import annotations

import sys
import tkinter as tk
import os

from typing import Dict, Any, Optional, Callable, Union
from logging import getLogger

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


from configurations import tool_settings
from configurations.user_setting_manager import get_user_setting_manager
from controllers.widgets_tracker import WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager
from utils.utils import get_resource_path


logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()


class CreateSubGraphWindowButton(tk.Button, ColoringThemeIF):
    """
    Button class for creating graph subwindows.

    This class is designed to manage multiple graph subwindows.
    Each subwindow has a unique identifier (window_id) to manage
    features such as data, graph color, and title.

    Attributes:
        __window_id (str): Unique identifier for the subwindow
        __graph_data (list): Data to display in the graph
        __graph_color (str): Color of the graph
        __window_title (str): Title of the subwindow
        __sub_window_size (Dict[str, Any]): Size information of the subwindow
        __current_setting_keys (Dict[str, Any]): Current setting keys

    Methods:
        create_sub_window(): Create a graph subwindow
        close_sub_window(): Close the graph subwindow
        update_graph_data(new_data: list): Update graph data
        update_graph_color(new_color: str): Update graph color
        update_window_title(new_title: str): Update window title
    """

    def __init__(
        self,
        master: tk.Frame,
        window_id: str,
        graph_data: list,
        graph_color: str,
        color_key: str,
        common_setting_key: str,
        threshold_var: tk.IntVar,
        command: Optional[Union[str, Callable[[], Any]]] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize the graph subwindow creation button.

        Args:
            master (tk.Frame): Parent frame
            window_id (str): Unique identifier for the subwindow
            graph_data (list): Data to display in the graph
            graph_color (str): Color of the graph
            color_key (str): Color theme key
            common_setting_key (str): Common setting key for shared settings
            threshold_var (tk.IntVar): Threshold value variable
            command (Optional[Union[str, Callable[[], Any]]]): Callback function when button is clicked
            **kwargs (Any): Additional keyword arguments

        Raises:
            Exception: If initialization fails
        """
        try:
            super().__init__(master, command=command, **kwargs)  # type: ignore[arg-type]
            self.__parent_window = master
            self.__window_id = window_id
            self.__graph_data = graph_data
            self.__graph_color = graph_color
            self.__color_key = color_key
            self.__common_setting_key = common_setting_key
            self.__threshold_var = threshold_var
            self.__default_button_text = str(kwargs.get("text", message_manager.get_ui_message("U026")))
            self._graph_status = False
            self.__last_theme_data: Dict[str, Any] = {}
            self._disabled_visual_bg: Optional[str] = None
            self._disabled_visual_fg: Optional[str] = None
            self.subwin: Optional[tk.Toplevel] = None
            self.__fig: Optional[plt.Figure] = None
            self.__ax: Optional[plt.Axes] = None
            self.sub_win_canvas: Optional[FigureCanvasTkAgg] = None
            self.sub_win_canvas_widget: Optional[tk.Widget] = None
            self.__control_frame: Optional[tk.Frame] = None
            self.__top_values_label: Optional[tk.Label] = None
            self.__threshold_label: Optional[tk.Label] = None
            self.__threshold_scale: Optional[tk.Scale] = None
            self.__threshold_apply_button: Optional[tk.Button] = None
            self.__threshold_entry: Optional[tk.Entry] = None
            self.__threshold_preview_var = tk.StringVar(value=str(self.__threshold_var.get()))
            self.__threshold_scale_var = tk.IntVar(value=self.__threshold_var.get())
            self.__threshold_preview_trace_id: Optional[str] = None
            self.__current_setting_keys: Dict[str, Any] = {}
            WidgetsTracker().add_widgets(self)

            if command is None:
                # Main processing: default to opening the graph subwindow when no external command is provided.
                self.configure(command=self._graph_btn_clicked)

            # Explicit theme application removed; managed globally

        except Exception as e:
            logger.error(message_manager.get_error_message("E001", str(e)))
            raise

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme colors to the widget.

        Args:
            theme_data (dict[str, Any]): Theme color data from ColorThemeManager. Accepts ThemeColors type or dict.
        """
        try:
            self.__last_theme_data = dict(theme_data)
            button_theme = dict(theme_data.get(self.__color_key, {}))
            if "bg" not in button_theme or "fg" not in button_theme:
                fallback_theme = dict(theme_data.get("process_button", theme_data.get("Button", {})))
                fallback_theme.update(button_theme)
                button_theme = fallback_theme
            if button_theme:
                self._config_widget(button_theme)
            self._apply_subwindow_theme()
        except Exception as e:
            logger.error(message_manager.get_error_message("E006", str(e)))
            raise

    def _config_widget(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme settings to the widget.

        Args:
            theme_data (dict[str, Any]): Theme settings to apply.
        """
        self.config(
            bg=theme_data.get("bg", self["bg"]),
            fg=theme_data.get("fg", self["fg"]),
            activebackground=theme_data.get("activebackground", self["activebackground"]),
            activeforeground=theme_data.get("activeforeground", self["activeforeground"]),
            disabledforeground=theme_data.get("disabledforeground", self.cget("disabledforeground")),
            relief=tk.RAISED,
            bd=2,
            highlightthickness=1,
            highlightbackground=theme_data.get("activebackground", theme_data.get("bg", self["bg"])),
        )
        if str(self.cget("state")) == str(tk.DISABLED):
            disabled_bg = str(self._disabled_visual_bg or self.cget("bg"))
            disabled_fg = str(self._disabled_visual_fg or self.cget("disabledforeground"))
            self.config(
                bg=disabled_bg,
                fg=disabled_fg,
                activebackground=disabled_bg,
                activeforeground=disabled_fg,
            )

    def _get_threshold_upper_bound(self) -> int:
        """Return the highest threshold value supported by the current graph."""
        return max(0, len(self.__graph_data) - 1)

    def _get_preview_threshold_value(self) -> int:
        """Return the current preview threshold, clamped to the graph range."""
        try:
            threshold_value = int(self.__threshold_preview_var.get())
        except (TypeError, ValueError):
            threshold_value = int(self.__threshold_var.get())
        return max(0, min(self._get_threshold_upper_bound(), threshold_value))

    def _apply_subwindow_theme(self) -> None:
        """Apply the stored theme data to the subwindow and threshold controls."""
        if not self.__last_theme_data:
            return

        window_theme = dict(self.__last_theme_data.get("Window", {}))
        frame_theme = dict(self.__last_theme_data.get("Frame", {}))
        label_theme = dict(self.__last_theme_data.get("Label", {}))
        entry_theme = dict(self.__last_theme_data.get("create_fb_threshold_entry", self.__last_theme_data.get("Entry", {})))
        button_theme = dict(self.__last_theme_data.get("process_button", self.__last_theme_data.get("Button", {})))

        window_bg = window_theme.get("bg", frame_theme.get("bg", "#ffffff"))
        frame_bg = frame_theme.get("bg", window_bg)
        label_fg = label_theme.get("fg", button_theme.get("fg", "#000000"))
        entry_bg = entry_theme.get("bg", entry_theme.get("background_color", "#ffffff"))
        entry_fg = entry_theme.get("fg", "#000000")

        if self.subwin is not None and self.subwin.winfo_exists():
            self.subwin.configure(bg=window_bg)

        if self.__control_frame is not None:
            self.__control_frame.configure(bg=frame_bg)

        if self.__top_values_label is not None:
            self.__top_values_label.configure(
                bg=frame_bg,
                fg=label_fg,
                justify="left",
                anchor="w",
            )

        if self.__threshold_label is not None:
            self.__threshold_label.configure(bg=frame_bg, fg=label_fg)

        if self.__threshold_scale is not None:
            self.__threshold_scale.configure(
                bg=frame_bg,
                fg=label_fg,
                activebackground=button_theme.get("activebackground", frame_bg),
                troughcolor=button_theme.get("bg", frame_bg),
                highlightthickness=0,
            )

        if self.__threshold_entry is not None:
            self.__threshold_entry.configure(
                bg=entry_bg,
                fg=entry_fg,
                insertbackground=entry_fg,
                highlightthickness=1,
                highlightbackground=button_theme.get("bg", frame_bg),
            )

        if self.__threshold_apply_button is not None:
            self.__threshold_apply_button.configure(
                bg=button_theme.get("bg", frame_bg),
                fg=button_theme.get("fg", label_fg),
                activebackground=button_theme.get("activebackground", frame_bg),
                activeforeground=button_theme.get("activeforeground", label_fg),
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
                highlightbackground=button_theme.get("activebackground", frame_bg),
            )

        if self.sub_win_canvas_widget is not None:
            try:
                self.sub_win_canvas_widget.configure(bg=window_bg, highlightthickness=0)
            except Exception:
                pass

        if self.__fig is not None:
            try:
                self.__fig.patch.set_facecolor(window_bg)
            except Exception:
                pass

        if self.__ax is not None:
            try:
                self.__ax.set_facecolor(window_bg)
                self.__ax.tick_params(colors=label_fg)
                self.__ax.xaxis.label.set_color(label_fg)
                self.__ax.yaxis.label.set_color(label_fg)
                self.__ax.title.set_color(label_fg)
                for spine in self.__ax.spines.values():
                    spine.set_color(label_fg)
                    spine.set_zorder(1)
                if self.sub_win_canvas is not None:
                    self.sub_win_canvas.draw()
            except Exception:
                pass

    def _subwindow_exists(self) -> bool:
        """Return whether the current subwindow reference is still valid."""
        if self.subwin is None:
            return False
        try:
            return bool(self.subwin.winfo_exists())
        except Exception:
            return False

    def _close_graph_window_impl(self) -> None:
        """Close the graph subwindow and clear transient widget references."""
        if self.subwin is None:
            self._graph_status = False
            return

        if self._subwindow_exists():
            self.set_subwin_user_settings(self.subwin)
            WidgetsTracker().remove_widgets(self.subwin)
            self.subwin.destroy()

        self._graph_status = False
        self.config(text=self.__default_button_text)
        self.subwin = None
        self.sub_win_canvas = None
        self.sub_win_canvas_widget = None
        self.__fig = None
        self.__ax = None
        self.__control_frame = None
        self.__top_values_label = None
        self.__threshold_label = None
        self.__threshold_scale = None
        self.__threshold_apply_button = None
        self.__threshold_entry = None

    def _build_top_values_summary(self) -> str:
        """Build a readable Top 3 summary from the current histogram data."""
        raw_y = np.asarray(self.__y, dtype=float)
        x_values = np.asarray(self.__x, dtype=int)
        positive_indices = np.flatnonzero(raw_y > 0)
        if len(positive_indices) == 0:
            return "Top 3: no positive values"

        sorted_indices = sorted(
            positive_indices,
            key=lambda idx: (-raw_y[idx], x_values[idx])
        )[:3]
        summary_lines = ["Top 3"]
        for rank, idx in enumerate(sorted_indices, start=1):
            rgb_total_value = int(x_values[idx])
            pixel_count = int(raw_y[idx])
            summary_lines.append(f"{rank}. value={rgb_total_value}, count={pixel_count}")
        return "\n".join(summary_lines)

    def _update_top_values_summary(self) -> None:
        """Refresh the Top 3 summary label using the latest graph data."""
        if self.__top_values_label is None:
            return

        self.__top_values_label.configure(text=self._build_top_values_summary())

    def _on_threshold_scale_changed(self, _value: str) -> None:
        """Reflect slider changes immediately in the preview line and entry field."""
        threshold_value = int(self.__threshold_scale_var.get())
        self.__threshold_preview_var.set(str(threshold_value))
        self._redraw_graph(threshold_value)

    def _on_threshold_entry_changed(self, *_args: Any) -> None:
        """Reflect entry changes immediately when the input is a valid integer."""
        raw_value = self.__threshold_preview_var.get().strip()
        if not raw_value:
            return
        try:
            threshold_value = int(raw_value)
        except ValueError:
            return

        threshold_value = max(0, min(self._get_threshold_upper_bound(), threshold_value))
        if self.__threshold_scale_var.get() != threshold_value:
            self.__threshold_scale_var.set(threshold_value)
        self._redraw_graph(threshold_value)

    def _apply_threshold_from_subwindow(self) -> None:
        """Persist the subwindow threshold and update the main shared threshold variable."""
        threshold_value = self._get_preview_threshold_value()
        self.__threshold_var.set(threshold_value)
        self.__threshold_scale_var.set(threshold_value)
        self.__threshold_preview_var.set(str(threshold_value))

        settings = get_user_setting_manager()
        settings.update_setting(self.__common_setting_key, threshold_value)
        settings.save_settings()
        self.update_graph()

    def _graph_btn_clicked(self) -> None:
        """Handle button click.

        Raises:
            Exception: If button click handling fails
        """
        try:
            if self._graph_status:
                logger.debug(message_manager.get_log_message("L068", self.__window_id, False))
                self._close_graph_window_impl()
                return

            if self.subwin is not None and not self._subwindow_exists():
                self._close_graph_window_impl()

            self._graph_status = True
            logger.debug(message_manager.get_log_message("L068", self.__window_id, self._graph_status))

            if not hasattr(self, "subwin") or self.subwin is None:
                self.subwin = tk.Toplevel(self.__parent_window)
                self.subwin.title(self.__window_id)
                self.subwin.geometry(
                    self.__current_setting_keys.get(
                        f"{self.__window_id}_subwindow_geometry", "760x520+300+240"
                    )
                )
                self.subwin.minsize(720, 500)
                self.subwin.config(bg=self.__current_setting_keys.get("base_bg_color", "#1d1d29"))

                icon_multi_ico_path = get_resource_path("images/icon_multi.ico")
                runtime_ico_path = str(tool_settings.RUNTIME_ICON_ICO_PATH)
                ico_path = (
                    icon_multi_ico_path
                    if os.path.exists(icon_multi_ico_path)
                    else runtime_ico_path
                )
                if os.path.exists(ico_path):
                    try:
                        self.subwin.iconbitmap(ico_path)
                    except Exception as e:
                        logger.warning(
                            message_manager.get_log_message(
                                "L227", f"Failed to set subwindow icon: {str(e)}"
                            )
                        )

                icon_png_candidates = (
                    get_resource_path("images/icon_256x256.png"),
                    get_resource_path("images/icon_128x128.png"),
                    get_resource_path("images/icon_64x64.png"),
                    get_resource_path("images/icon_48x48.png"),
                    get_resource_path("images/icon_32x32.png"),
                    get_resource_path("images/icon_24x24.png"),
                    get_resource_path("images/icon_16x16.png"),
                )
                try:
                    icon_imgs = [
                        tk.PhotoImage(file=p)
                        for p in icon_png_candidates
                        if os.path.exists(p)
                    ]
                    if icon_imgs:
                        self.subwin.iconphoto(True, *icon_imgs)
                        setattr(self.subwin, "_icon_photos", icon_imgs)
                    else:
                        icon_png_path = get_resource_path("images/LOGOm.png")
                        if os.path.exists(icon_png_path):
                            icon_img = tk.PhotoImage(file=icon_png_path)
                            self.subwin.iconphoto(True, icon_img)
                            setattr(self.subwin, "_icon_photo", icon_img)
                except Exception as e:
                    logger.warning(
                        message_manager.get_log_message(
                            "L227", f"Failed to set subwindow icon (iconphoto): {str(e)}"
                        )
                    )

            def on_close() -> None:
                """Handle subwindow close."""
                logger.debug(message_manager.get_log_message("L068", self.__window_id, False))
                self._close_graph_window_impl()

            self.subwin.protocol("WM_DELETE_WINDOW", on_close)
            self._create_graph_canvas()
            self._apply_subwindow_theme()

        except Exception as e:
            logger.error(message_manager.get_error_message("E015", str(e)))
            raise

    def open_graph_window(self) -> None:
        """Open the graph subwindow if it is not already open."""
        if not self._graph_status:
            self._graph_btn_clicked()

    def close_graph_window(self) -> None:
        """Close the graph subwindow if it is currently open."""
        if self._graph_status:
            self._graph_btn_clicked()

    def grid(self, *args: Any, **kwargs: Any) -> None:
        """Shortcut method to call grid on the main button.

        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments

        Raises:
            Exception: If grid method fails
        """
        try:
            super().grid(*args, **kwargs)
        except Exception as e:
            logger.error(message_manager.get_error_message("E007", str(e)))
            raise

    def _windows_set_titlebar_color(self, theme_name: str) -> None:
        """Set the titlebar color for Windows.

        Args:
            theme_name (str): Theme name ("dark" or "light")
        """
        try:
            if sys.platform == "win32":
                # Windows-specific titlebar color handling
                pass

        except Exception as e:
            logger.error(message_manager.get_error_message("E006", str(e)))
            raise

    def update_subwindow_geometry(self, geometry: str) -> None:
        """Update the geometry of the subwindow.

        Args:
            geometry (str): New geometry string (e.g., "800x600+100+100")
        """
        try:
            if hasattr(self, "subwin") and self.subwin is not None:
                self.subwin.geometry(geometry)
                usm = get_user_setting_manager()
                usm.update_setting(
                    f"{self.__window_id}_subwindow_geometry", geometry
                )

        except Exception as e:
            logger.error(message_manager.get_error_message("E009", str(e)))
            raise

    def set_subwin_user_settings(self, subwin: tk.Toplevel) -> None:
        """Save subwindow settings to user settings.

        Args:
            subwin (tk.Toplevel): Subwindow to save settings for
        """
        try:
            usm = get_user_setting_manager()
            settings = {
                f"{self.__window_id}_subwindow_geometry": subwin.geometry(),
                f"{self.__window_id}_subwindow_title": subwin.title(),
            }
            for key, value in settings.items():
                usm.update_setting(key, value)

        except Exception as e:
            logger.error(message_manager.get_error_message("E018", str(e)))
            raise

    def update_graph_data(self, new_data: list) -> None:
        """Update graph data.

        Args:
            new_data (list): New data to display in the graph

        Raises:
            ValueError: If graph data is out of range 0-255
            Exception: If graph data update fails
        """
        try:
            normalized_data = [max(0, int(x)) for x in new_data]
            if not normalized_data:
                normalized_data = [0]

            self.__graph_data = normalized_data
            self.__x = np.arange(0, len(self.__graph_data), 1)
            self.__y = self.__graph_data
            if self.__threshold_scale is not None:
                self.__threshold_scale.configure(to=self._get_threshold_upper_bound())
            self._redraw_graph()

        except ValueError as e:
            logger.error(message_manager.get_error_message("E016", str(e)))
            raise
        except Exception as e:
            logger.error(message_manager.get_error_message("E016", str(e)))
            raise

    def _create_graph_canvas(self) -> None:
        """Create graph canvas."""
        try:
            normalized_data = [max(0, int(x)) for x in self.__graph_data]
            if not normalized_data:
                normalized_data = [0]

            self.__x = np.arange(0, len(normalized_data), 1)
            self.__y = normalized_data

            self.__fig, self.__ax = plt.subplots(figsize=(7.2, 4.6), dpi=100)

            if self.subwin is None:
                return

            self.subwin.grid_rowconfigure(0, weight=1)
            self.subwin.grid_rowconfigure(1, weight=0)
            self.subwin.grid_columnconfigure(0, weight=1)
            self.__fig.subplots_adjust(left=0.12, right=0.985, top=0.92, bottom=0.16)

            self.sub_win_canvas = FigureCanvasTkAgg(self.__fig, master=self.subwin)
            self.sub_win_canvas_widget = self.sub_win_canvas.get_tk_widget()
            self.sub_win_canvas_widget.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 2))

            self.__control_frame = tk.Frame(self.subwin)
            self.__control_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
            self.__control_frame.grid_columnconfigure(1, weight=1)

            self.__top_values_label = tk.Label(
                self.__control_frame,
                text="",
                justify="left",
                anchor="w",
            )
            self.__top_values_label.grid(row=0, column=0, columnspan=4, pady=(0, 2), sticky="ew")

            self.__threshold_label = tk.Label(self.__control_frame, text="閾値")
            self.__threshold_label.grid(row=1, column=0, padx=(0, 6), sticky="w")

            self.__threshold_scale_var.set(self.__threshold_var.get())
            self.__threshold_preview_var.set(str(self.__threshold_var.get()))
            self.__threshold_scale = tk.Scale(
                self.__control_frame,
                from_=0,
                to=self._get_threshold_upper_bound(),
                orient=tk.HORIZONTAL,
                variable=self.__threshold_scale_var,
                command=self._on_threshold_scale_changed,
                showvalue=False,
                length=260,
            )
            self.__threshold_scale.grid(row=1, column=1, padx=(0, 8), sticky="ew")

            self.__threshold_entry = tk.Entry(
                self.__control_frame,
                textvariable=self.__threshold_preview_var,
                width=7,
                justify="right",
            )
            self.__threshold_entry.grid(row=1, column=2, padx=(0, 8), sticky="e")

            self.__threshold_apply_button = tk.Button(
                self.__control_frame,
                text="決定",
                command=self._apply_threshold_from_subwindow,
            )
            self.__threshold_apply_button.grid(row=1, column=3, sticky="e")

            if self.__threshold_preview_trace_id is not None:
                self.__threshold_preview_var.trace_remove("write", self.__threshold_preview_trace_id)
            self.__threshold_preview_trace_id = self.__threshold_preview_var.trace_add("write", self._on_threshold_entry_changed)
            self._redraw_graph()
            self._apply_subwindow_theme()

        except Exception as e:
            logger.error(message_manager.get_error_message("E018", str(e)))
            raise

    def update_graph(self) -> None:
        """Update graph data."""
        try:
            self._redraw_graph(int(self.__threshold_var.get()))

        except Exception as e:
            logger.error(message_manager.get_error_message("E018", str(e)))
            raise

    def _redraw_graph(self, threshold_value: Optional[int] = None) -> None:
        """Redraw the graph with the provided threshold preview line."""
        if self.__ax is None or self.sub_win_canvas is None:
            return

        graph_threshold = self._get_preview_threshold_value() if threshold_value is None else threshold_value
        graph_threshold = max(0, min(self._get_threshold_upper_bound(), graph_threshold))
        raw_y = np.asarray(self.__y, dtype=float)
        positive_y = raw_y[raw_y > 0]
        y_max = float(np.max(positive_y)) if len(positive_y) > 0 else 1.0
        nonzero_mask = raw_y > 0
        x_values = np.asarray(self.__x, dtype=float)
        nonzero_x = x_values[nonzero_mask]
        nonzero_y = raw_y[nonzero_mask]

        # Main processing: refresh the textual Top 3 summary together with the graph.
        self._update_top_values_summary()

        self.__ax.clear()
        if len(nonzero_x) > 0:
            self.__ax.vlines(
                nonzero_x,
                1.0,
                nonzero_y,
                color=f"tab:{self.__graph_color}",
                linewidth=1.4,
                alpha=0.95,
                zorder=5,
            )
            self.__ax.scatter(
                nonzero_x,
                nonzero_y,
                color=f"tab:{self.__graph_color}",
                s=8,
                alpha=0.9,
                zorder=6,
            )
        self.__ax.axvline(
            graph_threshold,
            color="tab:orange",
            linewidth=2.4,
            alpha=1.0,
            zorder=20,
        )
        x_upper = max(len(self.__y) - 1, 1)
        x_padding = max(6.0, x_upper * 0.02)
        self.__ax.set_xlim(-x_padding, x_upper + x_padding)
        self.__ax.set_ylim(1.0, y_max if y_max > 1.0 else 10.0)
        self.__ax.set_yscale("log", nonpositive="mask")
        self.__ax.set_xlabel("RGB total value", labelpad=6)
        self.__ax.set_ylabel("Pixel count (log)")
        self.__ax.set_title(self.__window_id, pad=8)
        self._apply_subwindow_theme()
        self.sub_win_canvas.draw()

    def get_threshold_value(self) -> int:
        """Get the current threshold value.

        Returns:
            int: Current threshold value
        """
        return self.__threshold_var.get()

    def set_threshold_value(self, value: int) -> None:
        """Set the threshold value.

        Args:
            value (int): New threshold value
        """
        clamped_value = max(0, min(self._get_threshold_upper_bound(), int(value)))
        self.__threshold_var.set(clamped_value)
        self.__threshold_scale_var.set(clamped_value)
        self.__threshold_preview_var.set(str(clamped_value))
