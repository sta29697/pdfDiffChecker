from __future__ import annotations

import sys
import tkinter as tk
import os

from typing import Dict, Any, Optional, Callable, Union
from logging import getLogger

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


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
            self._graph_status = False
            self.subwin: Optional[tk.Toplevel] = None
            self.__ax: Optional[plt.Axes] = None
            self.sub_win_canvas: Optional[FigureCanvasTkAgg] = None
            self.__current_setting_keys: Dict[str, Any] = {}

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
            widget_type = self.winfo_class()
            if widget_type in theme_data:
                self._config_widget(dict(theme_data[widget_type]))
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
            activeforeground=theme_data.get("activeforeground", self["activeforeground"])
        )

    def _graph_btn_clicked(self) -> None:
        """Handle button click.

        Raises:
            Exception: If button click handling fails
        """
        try:
            if self._graph_status:
                # If subwindow is open -> close it
                self._graph_status = False
                # Log message for subgraph toggle status
                logger.debug(message_manager.get_log_message("L068", self.__window_id, self._graph_status))
                # Close subwindow
                if (
                    hasattr(self, "subwin")
                    and self.subwin is not None
                    and self.subwin.winfo_exists()
                ):
                    # Save geometry
                    self.set_subwin_user_settings(self.subwin)
                    WidgetsTracker().remove_widgets(self.subwin)
                    # UI text for toggle subgraph window
                    self.config(text=message_manager.get_ui_message("U026"))
                    self.__parent_window.update()
                    self.subwin.destroy()
                return

            # If subwindow is not open -> create it
            self._graph_status = True
            # Log message for subgraph toggle status
            logger.debug(message_manager.get_log_message("L068", self.__window_id, self._graph_status))
            
            # Create subwindow
            if not hasattr(self, "subwin") or self.subwin is None:
                self.subwin = tk.Toplevel(self.__parent_window)
                self.subwin.title(self.__window_id)
                self.subwin.geometry(
                    self.__current_setting_keys.get(
                        f"{self.__window_id}_subwindow_geometry", "500x300+300+300"
                    )
                )
                self.subwin.config(bg=self.__current_setting_keys.get("base_bg_color", "#1d1d29"))

                # Main processing: apply application icon to this Toplevel window.
                icon_multi_ico_path = get_resource_path("images/icon_multi.ico")
                runtime_ico_path = get_resource_path("temp/LOGOm.ico")
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

            # Define on-close function
            def on_close() -> None:
                """Handle subwindow close."""
                if self._graph_status:
                    # If subwindow is open -> close it
                    self._graph_status = False
                    # Log message for subgraph toggle status
                    logger.debug(message_manager.get_log_message("L068", self.__window_id, self._graph_status))
                    # Close subwindow
                    if (
                        hasattr(self, "subwin")
                        and self.subwin is not None
                        and self.subwin.winfo_exists()
                    ):
                        # Save geometry
                        self.set_subwin_user_settings(self.subwin)
                        WidgetsTracker().remove_widgets(self.subwin)
                        # UI text for toggle subgraph window
                        self.config(text=message_manager.get_ui_message("U026"))
                        self.__parent_window.update()
                        self.subwin.destroy()

            self.subwin.protocol("WM_DELETE_WINDOW", on_close)

            # Create graph canvas
            self._create_graph_canvas()

        except Exception as e:
            logger.error(message_manager.get_error_message("E015", str(e)))
            raise

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
            # Validate data range
            if not all(0 <= x <= 255 for x in new_data):
                raise ValueError("Graph data must be in range 0-255")
                
            self.__graph_data = new_data
            self.__y = self.__graph_data
            if self.__ax is not None and self.sub_win_canvas is not None:
                self.__ax.clear()
                self.__ax.plot(self.__x, self.__y, color=f"tab:{self.__graph_color}")
                self.__ax.vlines(
                    self.__threshold_var.get(),
                    0,
                    np.max(self.__y),
                    color="tab:orange"
                )
                self.sub_win_canvas.draw()

        except ValueError as e:
            logger.error(message_manager.get_error_message("E016", str(e)))
            raise
        except Exception as e:
            logger.error(message_manager.get_error_message("E016", str(e)))
            raise

    def _create_graph_canvas(self) -> None:
        """Create graph canvas."""
        try:
            # Prepare graph data
            self.__x = np.arange(0, 255, 1)
            self.__y = self.__graph_data

            # Create figure and axis
            self.__fig, self.__ax = plt.subplots()

            # Create canvas
            self.sub_win_canvas = FigureCanvasTkAgg(self.__fig, master=self.subwin)
            self.sub_win_canvas_widget = self.sub_win_canvas.get_tk_widget()
            self.sub_win_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # Plot data
            if self.__ax is not None:
                self.__ax.clear()
                self.__ax.plot(self.__x, self.__y, color=f"tab:{self.__graph_color}")
                self.__ax.vlines(
                    self.__threshold_var.get(),
                    0,
                    np.max(self.__y),
                    color="tab:orange"
                )
            if self.sub_win_canvas is not None:
                self.sub_win_canvas.draw()

        except Exception as e:
            logger.error(message_manager.get_error_message("E018", str(e)))
            raise

    def update_graph(self) -> None:
        """Update graph data."""
        try:
            if self.__ax is not None and self.sub_win_canvas is not None:
                self.__ax.clear()
                self.__ax.plot(self.__x, self.__y, color=f"tab:{self.__graph_color}")
                self.__ax.vlines(
                    self.__threshold_var.get(),
                    0,
                    np.max(self.__y),
                    color="tab:orange"
                )
                self.sub_win_canvas.draw()

        except Exception as e:
            logger.error(message_manager.get_error_message("E018", str(e)))
            raise

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
        self.__threshold_var.set(value)
