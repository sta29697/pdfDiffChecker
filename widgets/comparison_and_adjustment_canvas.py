from __future__ import annotations

import tkinter as tk
import os
from logging import getLogger
from typing import Dict, Any, Optional, List, Tuple

from PIL import Image, ImageTk

from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.image_visibility_toggle_frame import ImageVisibilityToggleFrame
from widgets.page_control_frame import PageControlFrame
from controllers.mouse_event_handler import MouseEventHandler
from widgets.pdf_save_dialog import PDFSaveDialog
from utils.utils import show_balloon_message
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()


class PDFCompareCanvas(tk.Frame, ThemeColorApplicable, ColoringThemeIF):
    """
    A tkinter Frame that displays two images ("base" and "comp") on a Canvas.
    Uses external frames for toggle buttons (ImageVisibilityToggleFrame),
    and page control (PageControlFrame).
    Finally exports all pages to a single PDF with the same background size,
    derived from PDF metadata or display size.
    """

    def __init__(
        self,
        parent: tk.Frame,
        base_pages: List[str],
        comp_pages: List[str],
        output_folder: str,
        pdf_metadata: (
            Dict[str, Any] | None
        ) = None,  # e.g. from file2png_by_page metadata
    ):
        """
        :param parent: the parent frame
        :param base_pages: a list of base PNG file paths
        :param comp_pages: a list of comp PNG file paths
        :param output_folder: path for the final exported PDF
        :param pdf_metadata: optional dictionary containing page_width, page_height, etc.
        """
        self.__parent = parent
        super().__init__(self.__parent)

        # Lists of file paths
        self.__base_pages = base_pages
        self.__comp_pages = comp_pages

        self.__output_folder = output_folder
        self.__pdf_metadata = (
            pdf_metadata or {}
        )  # e.g. {"page_width":1000, "page_height":1400}

        # Current page index
        self.__current_page_index = 0

        # Transform data (rotation, offset_x, offset_y, scale)
        self.__base_transform_data: List[Tuple[float, float, float, float]] = [
            (0.0, 0.0, 0.0, 1.0) for _ in self.__base_pages
        ]
        self.__comp_transform_data: List[Tuple[float, float, float, float]] = [
            (0.0, 0.0, 0.0, 1.0) for _ in self.__comp_pages
        ]

        # Visibility toggles
        self.__base_visible = True
        self.__comp_visible = True

        # Build UI
        self.__create_layout()

        # Update display
        self.__update_page_label()
        self.__show_current_page()

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    def __create_layout(self) -> None:
        """
        Create all UI layout with grid geometry, referencing external frames and classes.
        """
        self.grid_rowconfigure(0, weight=0)  # top row doesn't expand
        self.grid_rowconfigure(1, weight=1)  # canvas row expands
        self.grid_columnconfigure(0, weight=0)  # page control frame has fixed size
        self.grid_columnconfigure(1, weight=1)  # canvas column expands

        # 1) Top frame for toggles
        self.__top_frame = tk.Frame(self)
        self.__top_frame.grid(row=0, column=0, columnspan=2, sticky="nw")

        # Place the toggle frame (external class)
        self.__toggle_frame = ImageVisibilityToggleFrame(
            self.__top_frame,
            color_key="image_visibility_toggle",
            callback=self.__toggle_visibility,
        )
        self.__toggle_frame.grid(row=0, column=0)

        # Register toggle frame for theme updates
        WidgetsTracker().add_widgets(self.__toggle_frame)

        # 2) Canvas (expanded to fill the frame) - positioned on the right
        self.__canvas = tk.Canvas(self, bg="white")
        self.__canvas.grid(row=1, column=1, sticky="nsew")

        # 3) Page control frame - positioned on the left
        self.__page_control_frame = PageControlFrame(
            self,
            color_key="page_control",
            base_pages=self.__base_pages,
            comp_pages=self.__comp_pages,
            base_transform_data=self.__base_transform_data,
            comp_transform_data=self.__comp_transform_data,
            visualized_image=tk.StringVar(value="base"),
            page_amount_limit=100,
            on_prev_page=self.__show_previous_page,
            on_next_page=self.__show_next_page,
            on_insert_blank=self.__insert_blank_page,
            on_export=self.__on_export_click,
            on_page_entry=self.__on_page_entry,
        )
        self.__page_control_frame.grid(row=1, column=0, sticky="nsw")
        
        # Configure grid weights for expansion
        self.grid_columnconfigure(1, weight=1)  # Canvas column expands
        self.grid_rowconfigure(1, weight=1)     # Canvas row expands

        # Initialize mouse event handler
        # Merge transformation data to provide a unified format
        layer_transform_data = {
            0: self.__base_transform_data,  # Layer 0 = base
            1: self.__comp_transform_data   # Layer 1 = comparison
        }
        
        # Define visibility state as a dictionary
        visible_layers = {}
        if self.__base_visible:
            visible_layers[0] = True
        if self.__comp_visible:
            visible_layers[1] = True
            
        self.__mouse_handler = MouseEventHandler(
            layer_transform_data=layer_transform_data,
            current_page_index=self.__current_page_index,
            visible_layers=visible_layers,
            on_transform_update=self.__show_current_page
        )
        
        # Attach mouse handler to canvas for keyboard shortcuts
        self.__mouse_handler.attach_to_canvas(self.__canvas)

        # Bind mouse events
        self.__bind_mouse_events()

    def __bind_mouse_events(self) -> None:
        """Bind mouse events to the canvas."""
        try:
            # Use simple and direct event handlers
            def on_click(e: tk.Event) -> None:
                logger.debug("Mouse down event triggered")
                self.__canvas.focus_set()
                self.__mouse_handler.on_mouse_down(e)
                
            def on_drag(e: tk.Event) -> None:
                logger.debug("Mouse drag event triggered")
                self.__mouse_handler.on_mouse_drag(e)
                
            def on_release(e: tk.Event) -> None:
                logger.debug("Mouse release event triggered")
                self.__mouse_handler.on_mouse_up(e)
                
            def on_wheel(e: tk.Event) -> None:
                logger.debug("Mouse wheel event triggered")
                self.__mouse_handler.on_mouse_wheel(e)
            
            # Perform bindings
            self.__canvas.bind("<Button-1>", on_click)
            self.__canvas.bind("<B1-Motion>", on_drag)
            self.__canvas.bind("<ButtonRelease-1>", on_release)
            self.__canvas.bind("<MouseWheel>", on_wheel)
            
            # Make canvas focusable
            self.__canvas.config(takefocus=1)
            
            # Mouse events bound successfully
            logger.debug(message_manager.get_log_message("L137"))
        except Exception as e:
            # Failed to bind mouse events: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def __toggle_visibility(self, image_type: str, new_state: bool) -> None:
        """
        Callback from the toggle buttons frame.
        """
        if image_type == "base":
            self.__base_visible = new_state
        elif image_type == "comp":
            self.__comp_visible = new_state
        self.__show_current_page()

    def __show_previous_page(self) -> None:
        """
        Go to the previous page if available.
        """
        if self.__current_page_index > 0:
            self.__current_page_index -= 1
            # Update mouse handler state
            visible_layers = {}
            if self.__base_visible:
                visible_layers[0] = True
            if self.__comp_visible:
                visible_layers[1] = True
            self.__mouse_handler.update_state(self.__current_page_index, visible_layers)
            self.__update_page_label()
            self.__show_current_page()

    def __show_next_page(self) -> None:
        """
        Go to the next page if available.
        """
        max_pages = max(len(self.__base_pages), len(self.__comp_pages))
        if self.__current_page_index < max_pages - 1:
            self.__current_page_index += 1
            # Update mouse handler state
            visible_layers = {}
            if self.__base_visible:
                visible_layers[0] = True
            if self.__comp_visible:
                visible_layers[1] = True
            self.__mouse_handler.update_state(self.__current_page_index, visible_layers)
            self.__update_page_label()
            self.__show_current_page()

    def __insert_blank_page(self) -> None:
        """
        Insert blank page(s) for the visible side(s).
        """
        try:
            if self.__base_visible:
                new_filename = f"blank_base_{len(self.__base_pages)}.png"
                new_path = os.path.join(self.__output_folder, new_filename)
                # Create a blank RGBA image
                blank_img = Image.new("RGBA", (1000, 1400), (0, 0, 0, 0))
                blank_img.save(new_path)
                insert_pos = self.__current_page_index + 1
                self.__base_pages.insert(insert_pos, new_path)
                self.__base_transform_data.insert(insert_pos, (0.0, 0.0, 0.0, 1.0))
                # Inserted blank page into base: {path}
                logger.info(message_manager.get_log_message("L138", new_path))

            if self.__comp_visible:
                new_filename = f"blank_comp_{len(self.__comp_pages)}.png"
                new_path = os.path.join(self.__output_folder, new_filename)
                blank_img = Image.new("RGBA", (1000, 1400), (0, 0, 0, 0))
                blank_img.save(new_path)
                insert_pos = self.__current_page_index + 1
                self.__comp_pages.insert(insert_pos, new_path)
                self.__comp_transform_data.insert(insert_pos, (0.0, 0.0, 0.0, 1.0))
                # Inserted blank page into comp: {path}
                logger.info(message_manager.get_log_message("L139", new_path))

        except Exception as e:
            # Failed to insert blank page: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

        self.__update_page_label()
        self.__show_current_page()

    def __on_page_entry(self, event: tk.Event | None = None) -> None:
        """
        Handler for pressing Enter in the page number entry.

        Args:
            event (tk.Event | None): Event object (optional)
        """
        try:
            page_num = int(self.__page_control_frame.page_var.get())
            page_index = page_num - 1  # 0-based
            max_pages = max(len(self.__base_pages), len(self.__comp_pages))
            if 0 <= page_index < max_pages:
                self.__current_page_index = page_index
                # Update mouse handler state with new page index
                visible_layers = {}
                if self.__base_visible:
                    visible_layers[0] = True
                if self.__comp_visible:
                    visible_layers[1] = True
                self.__mouse_handler.update_state(self.__current_page_index, visible_layers)
                self.__update_page_label()
                self.__show_current_page()
        except ValueError:
            # Invalid page number
            logger.warning(message_manager.get_log_message("L140"))

    def __update_page_label(self) -> None:
        """
        Update the page label in PageControlFrame.
        """
        max_pages = max(len(self.__base_pages), len(self.__comp_pages))
        self.__page_control_frame.update_page_label(
            self.__current_page_index, max_pages
        )

    def __show_current_page(self) -> None:
        """
        Show base and comp images on Canvas with transformations, respecting visibility.
        """
        self.__canvas.delete("all")

        # Update mouse handler state with current page and visibility
        visible_layers = {}
        if self.__base_visible:
            visible_layers[0] = True
        if self.__comp_visible:
            visible_layers[1] = True
        self.__mouse_handler.update_state(self.__current_page_index, visible_layers)

        base_img = None
        comp_img = None
        base_load_failed = False
        comp_load_failed = False

        # Load base if in range
        if self.__current_page_index < len(self.__base_pages):
            try:
                path = self.__base_pages[self.__current_page_index]
                base_img = Image.open(path).convert("RGBA")
            except Exception as e:
                # Failed to open base image: {error}
                logger.error(message_manager.get_log_message("L127", str(e)))
                base_load_failed = True
                # Create a small empty image as fallback
                base_img = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
                # UI balloon for image load failure
                show_balloon_message(self.__canvas, message_manager.get_ui_message("U027"))

        # Load comp if in range
        if self.__current_page_index < len(self.__comp_pages):
            try:
                path = self.__comp_pages[self.__current_page_index]
                comp_img = Image.open(path).convert("RGBA")
            except Exception as e:
                # Failed to open comp image: {error}
                logger.error(message_manager.get_log_message("L128", str(e)))
                comp_load_failed = True
                # Create a small empty image as fallback
                comp_img = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
                # UI balloon for image load failure
                show_balloon_message(self.__canvas, message_manager.get_ui_message("U027"))

        # Draw base
        if base_img and self.__base_visible:
            try:
                r, offx, offy, scale = self.__base_transform_data[
                    self.__current_page_index
                ]
                new_w = int(base_img.width * scale)
                new_h = int(base_img.height * scale)
                base_img = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                base_img = base_img.rotate(r, expand=True)
                self.__base_tk_image = ImageTk.PhotoImage(base_img)
                self.__canvas.create_image(
                    offx, offy, image=self.__base_tk_image, anchor=tk.NW
                )
            except Exception as e:
                # Failed to process base image: {error}
                logger.error(message_manager.get_log_message("L129", str(e)))
                if not base_load_failed:
                    # UI balloon for image load failure
                    show_balloon_message(self.__canvas, message_manager.get_ui_message("U027"))

        # Draw comp
        if comp_img and self.__comp_visible:
            try:
                r, offx, offy, scale = self.__comp_transform_data[
                    self.__current_page_index
                ]
                new_w = int(comp_img.width * scale)
                new_h = int(comp_img.height * scale)
                comp_img = comp_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                comp_img = comp_img.rotate(r, expand=True)
                self.__comp_tk_image = ImageTk.PhotoImage(comp_img)
                self.__canvas.create_image(
                    offx, offy, image=self.__comp_tk_image, anchor=tk.NW
                )
            except Exception as e:
                # Failed to process comp image: {error}
                logger.error(message_manager.get_log_message("L130", str(e)))
                if not comp_load_failed and not base_load_failed:
                    # UI balloon for image load failure
                    show_balloon_message(self.__canvas, message_manager.get_ui_message("U027"))

    def __on_export_click(self) -> None:
        """Handle export button click."""
        try:
            # Show save dialog
            PDFSaveDialog(
                self,
                on_save=self.__save_pdf,
            )
        except Exception as e:
            # Failed to handle export click: {error}
            logger.error(message_manager.get_log_message("L122", str(e)))
            raise

    def __save_pdf(self, filename: str, parent_widget: tk.Widget) -> None:
        """Save the current state as a PDF file.

        Args:
            filename: Name of the file to save
            parent_widget: Widget that invoked the save (for balloon, etc.)
        """
        try:
            # Get output directory from settings
            output_dir = self.__get_output_directory()
            if not output_dir:
                # Skip silently without error log as this is an expected case
                logger.debug(message_manager.get_log_message("L191", "output_directory", "False"))
                return

            # Create full path
            output_path = os.path.join(output_dir, filename)

            # Save PDF logic here
            # TODO: Implement PDF saving
            logger.info(f"[APP_SAVE] {message_manager.get_log_message('L189', output_path)}")

        except Exception as e:
            # Failed to save PDF: {error}
            logger.error(message_manager.get_log_message("L123", str(e)))
            raise

    def __get_output_directory(self) -> Optional[str]:
        """Get the output directory from settings or user selection.

        Returns:
            Selected output directory or None if cancelled
        """
        try:
            # TODO: Implement output directory selection
            return "output"
        except Exception as e:
            # Failed to get output directory: {error}
            logger.error(message_manager.get_log_message("L124", str(e)))
            raise

    def set_base_visible(self, visible: bool) -> None:
        """Set base PDF visibility.

        Args:
            visible: Whether to show base PDF
        """
        self.__base_visible = visible
        # Create visibility dictionary
        visible_layers = {}
        if self.__base_visible:
            visible_layers[0] = True
        if self.__comp_visible:
            visible_layers[1] = True
        # Update mouse handler state
        self.__mouse_handler.update_state(
            self.__current_page_index,
            visible_layers
        )

    def set_comp_visible(self, visible: bool) -> None:
        """Set comparison PDF visibility.

        Args:
            visible: Whether to show comparison PDF
        """
        self.__comp_visible = visible
        # Create visibility dictionary
        visible_layers = {}
        if self.__base_visible:
            visible_layers[0] = True
        if self.__comp_visible:
            visible_layers[1] = True
        # Update mouse handler state
        self.__mouse_handler.update_state(
            self.__current_page_index,
            visible_layers
        )

    def apply_theme_color(self, theme_data: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the canvas frame and its components.

        Args:
            theme_data: Dictionary containing theme color data.
        """
        try:
            # Apply theme to the frame itself
            frame_theme_config = theme_data.get("Frame", {})
            self.configure(**frame_theme_config)

            # Apply theme to the canvas
            canvas_theme_config = theme_data.get("Canvas", {})
            if (
                hasattr(self, "_PDFCompareCanvas__canvas")
                and self._PDFCompareCanvas__canvas is not None
            ):
                self._PDFCompareCanvas__canvas.configure(**canvas_theme_config)

            # Theme color applied to PDFCompareCanvas
            logger.debug(message_manager.get_log_message("L141"))
        except Exception as e:
            # Failed to apply theme to PDFCompareCanvas: {error}
            logger.error(message_manager.get_log_message("L125", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Dictionary containing theme settings.
        """
        try:
            self.configure(**theme_settings)
            # Configured PDFCompareCanvas with settings
            logger.debug(message_manager.get_log_message("L142"))
        except Exception as e:
            # Failed to configure PDFCompareCanvas: {error}
            logger.error(message_manager.get_log_message("L126", str(e)))
