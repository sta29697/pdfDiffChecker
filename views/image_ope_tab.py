from __future__ import annotations
from logging import getLogger
from typing import Dict, Any, Optional

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk

from configurations.message_manager import get_message_manager
from controllers.color_theme_manager import ColorThemeManager
from controllers.file2png_by_page import BaseImageConverter

from models.class_dictionary import FilePathInfo, FolderPathInfo
from models.class_dictionary import WidgetPosition as ClassDictWidgetPosition

from widgets.base_label_class import BaseLabelClass
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.color_theme_change_button import ColorThemeChangeButton
from widgets.language_select_combobox import LanguageSelectCombo
from widgets.base_path_entry import BasePathEntry
from widgets.base_path_select_button import BasePathSelectButton
# BaseTabFrame is used in inheritance class
from widgets.base_image_color_change_button import (
    BaseImageColorChangeButton,
)
from widgets.base_entry import BaseEntry
from widgets.convert_image_button import ConvertImageButton
from controllers.drag_and_drop_file import DragAndDropHandler
from themes.coloring_theme_interface import ColoringThemeIF
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog

logger = getLogger(__name__)
message_manager = get_message_manager()


class ImageOperationApp(ttk.Frame, ColoringThemeIF):
    """Image operation tab."""

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the image operation tab.

        Args:
            master (Optional[tk.Misc]): Parent widget
            **kwargs: Additional keyword arguments
        """
        super().__init__(master, **kwargs)
        self.base_widgets = BaseTabWidgets(self)
        # Bind window events on the toplevel window
        self.bind_window_events(self.winfo_toplevel())
        self.status_var: tk.StringVar = tk.StringVar(value="")
        self.after_id: Optional[str] = None

        self.base_path = tk.StringVar()
        self.base_path.set("直接入力、参照選択")
        self.output_path = tk.StringVar()
        self.output_path.set("直接入力、参照選択")

        # Get current Notebook theme colors
        theme_colors = ColorThemeManager.get_instance().get_current_theme()
        # Fallback for Notebook colors: tab_bg -> bg -> default
        notebook = theme_colors.get("Notebook", {})
        bg_color = notebook.get("bg", "#1d1d29")
        tab_bg = notebook.get("tab_bg", bg_color)

        # Arrange widgets into 3 vertical frames:
        # frame_main0: file info and theme switch
        # frame_main1: image format conversion
        # frame_main2: image size conversion
        ttk.Style().configure("default", background=bg_color)

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.frame_main0 = tk.Frame(self, relief=tk.RIDGE, bd=2)
        self.frame_main0.grid(row=0, column=0, sticky="we", ipady=2)
        self.frame_main0.grid_columnconfigure(0, weight=1)
        self.frame_main0.grid_rowconfigure(0, weight=0)
        self.frame_main1 = tk.Frame(self, relief=tk.RIDGE, bd=2)
        self.frame_main1.grid(row=1, column=0, sticky="we", ipady=2)
        self.frame_main1.grid_columnconfigure(0, weight=1)
        self.frame_main1.grid_rowconfigure(1, weight=0)
        self.frame_main2 = tk.Frame(self, relief=tk.RIDGE, bd=2)
        self.frame_main2.grid(row=2, column=0, sticky="nsew", ipady=2)
        self.frame_main2.grid_columnconfigure(0, weight=1)
        self.frame_main2.grid_rowconfigure(2, weight=1)

        # Create canvas for image preview
        self.canvas = tk.Canvas(
            self.frame_main2,
            bg=tab_bg,
            width=400,
            height=300,
            relief=tk.SUNKEN,
            bd=2,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.base_widgets.add_widget(self.canvas)

        # Setup drag and drop for canvas
        self._setup_drag_and_drop()

        # Create language selection combobox
        lang_combo = LanguageSelectCombo(self.frame_main0)
        lang_combo.grid(column=0, row=0, padx=5, pady=2, sticky="we")

        # Initialize and place theme change button
        self._color_theme_change_btn_pos = ClassDictWidgetPosition(
            col=1, row=0, padx=5, pady=0, sticky="we"
        )
        self._color_theme_change_btn = ColorThemeChangeButton(
            fr=self.frame_main0, color_theme_change_btn_status=True
        )
        self._color_theme_change_btn.grid(
            column=self._color_theme_change_btn_pos.col,
            row=self._color_theme_change_btn_pos.row,
            padx=self._color_theme_change_btn_pos.padx,
            pady=self._color_theme_change_btn_pos.pady,
            sticky=self._color_theme_change_btn_pos.sticky,
        )

        # Set base file path
            # Base file path label and entry
            # Base file path label text
        self._base_file_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="base_file_path_label",
            text=message_manager.get_ui_message("U018"),
        )
        self._base_file_path_label.grid(
            column=0, row=1, padx=5, pady=8, sticky="nw"
        )
        # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
        self._base_file_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="base_file_path_entry",
            entry_setting_key="base_file_path"
        )
        self._base_file_path_entry.grid(
            column=1, row=1, columnspan=2, padx=5, pady=8, sticky="ew"
        )
        self._base_file_path_entry.path_var.set(self.base_path.get())
        self._base_image_color_select_btn_pos = ClassDictWidgetPosition(
            col=2, row=0, padx=5, pady=5
        )
        # Initialize and place image color change button
        self._base_image_color_change_btn = BaseImageColorChangeButton(
            fr=self.frame_main1,
            color_key="base_image_color_change_button",
        )
        self._base_image_color_change_btn.grid(
            column=self._base_image_color_select_btn_pos.col,
            row=self._base_image_color_select_btn_pos.row,
            padx=self._base_image_color_select_btn_pos.padx,
            pady=self._base_image_color_select_btn_pos.pady,
        )
        self.base_file_info = self._base_file_path_entry.path_obj
        # Button for base file path selection
        self._base_file_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="base_file_path_button",
            entry_setting_key="base_file_path",
            share_path_entry=self._base_file_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_base_file_select,
        )
        self._base_file_path_button.grid(column=3, row=1, padx=5, pady=8)


        # Output folder path label and entry
        # Output folder path label text
        self._output_folder_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="output_folder_path_label",
            text=message_manager.get_ui_message("U021"),
        )
        self._output_folder_path_label.grid(
            column=0, row=3, padx=5, pady=8, sticky="nw"
        )
        # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
        self._output_folder_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="output_folder_path_entry",
            entry_setting_key="output_folder_path"
        )
        self._output_folder_path_entry.grid(
            column=1, row=3, padx=5, pady=8, sticky="we"
        )
        self._output_folder_path_entry.path_var.set(self.output_path.get())
        self.output_folder_info = self._output_folder_path_entry.path_obj
        # Output folder path button
        # U019: Select
        self._output_folder_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="output_folder_path_button",
            entry_setting_key="output_folder_path",
            share_path_entry=self._output_folder_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_output_folder_select,
        )
        self._output_folder_path_button.grid(column=2, row=3, padx=5, pady=8)

        # Status bar
        self._status_label = ttk.Label(self, textvariable=self.status_var)
        self._status_label.grid(row=3, column=0, columnspan=3, sticky="we", padx=5, pady=2)

    def bind_window_events(self, master: tk.Tk | tk.Toplevel) -> None:
        """Bind window resize and close events to exit window.
        When running in tab mode, do not bind window events.
        """
        # This method is intentionally empty
        # All window events are now centrally managed by WindowEventManager in main.py
        # DO NOT set any protocol handlers or bindings here
        # This prevents conflicts with the central event handling system
        pass

    def _on_base_file_select(self) -> None:
        """Handle base file selection.

        Prompt user to select a PDF file and update the base path entry.
        """
        file_path = ask_file_dialog(
            initialdir=self._base_file_path_entry.path_var.get(),
            title_code="U022",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._base_file_path_entry.path_var.set(file_path)
            # Log base file selection
            logger.debug(message_manager.get_log_message("L070", file_path))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection.

        Prompt user to select a folder and update the output path entry.
        """
        folder_path = ask_folder_dialog(
            initialdir=self._output_folder_path_entry.path_var.get(),
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            # Log output folder selection
            logger.debug(message_manager.get_log_message("L072", folder_path))

        # Add image size conversion controls
        self._size_conversion_frame = tk.Frame(self.frame_main2, relief=tk.RIDGE, bd=2)
        self._size_conversion_frame.grid(row=1, column=0, sticky="we", padx=5, pady=5)

        # Width control
        self._width_label = BaseLabelClass(
            fr=self._size_conversion_frame,
            color_key="width_size_set_label",
            text=message_manager.get_ui_message("U012"),
        )
        self._width_label.grid(row=0, column=0, padx=5, pady=5)

        self.width_var = tk.StringVar()
        self._width_entry = BaseEntry(
            master=self._size_conversion_frame,
            color_key="entry_normal",
            textvariable=self.width_var,
            width=10,
        )
        self._width_entry.grid(column=1, row=0, padx=5, pady=5)

        # Height control
        self._height_label = BaseLabelClass(
            fr=self._size_conversion_frame,
            color_key="height_size_set_label",
            text=message_manager.get_ui_message("U013"),
        )
        self._height_label.grid(row=0, column=2, padx=5, pady=5)

        self.height_var = tk.StringVar()
        self._height_entry = BaseEntry(
            master=self._size_conversion_frame,
            color_key="entry_normal",
            textvariable=self.height_var,
            width=10,
        )
        self._height_entry.grid(column=3, row=0, padx=5, pady=5)

        # Convert button
        self._convert_btn = ConvertImageButton(
            fr=self._size_conversion_frame,
            color_key="convert_image_button",
            text=message_manager.get_ui_message("U014"),
            command=self._convert_image,
        )
        self._convert_btn.grid(row=0, column=4, padx=5, pady=5)

    def standardization_image_file_extensions(self, extension: str) -> str:
        """Standardize image file extensions.

        Args:
            extension: File extension to standardize

        Returns:
            Standardized file extension
        """
        # Image file format standardization
        # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html

        self._extension = extension
        match self._extension.lower():
            case "jpg" | "jpeg":
                return "jpg"
            case "png":
                return "png"
            case "gif":
                return "gif"
            case "tiff" | "tif":
                return "tiff"
            case "bmp":
                return "bmp"
            case _:
                logger.error(message_manager.get_log_message("L205", self._extension))
                return ""

    def image_file_format_conversion(
        self, before_format: str, after_format: str
    ) -> None:
        self._before_format = self.standardization_image_file_extensions(before_format)
        self._after_format = self.standardization_image_file_extensions(after_format)

        # Initialize FilePathInfo with temp file path; extension derived in __post_init__
        temp_file_info = FilePathInfo(Path(f"temp.{self._before_format}"))

        # Create converter with the file info
        self._ifec = BaseImageConverter(temp_file_info, "base")

        if self._before_format == "gif" and self._after_format == "png":
            # Use the appropriate method for GIF to PNG conversion
            self._ifec.convert_to_grayscale_pngs(
                progress_callback=NullProgressCallback()
            )

    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the widgets.

        Args:
            theme_colors: Dictionary of theme colors
        """
        if "Frame" in theme_colors:
            frame_colors = theme_colors["Frame"]
            self.configure(**frame_colors)

            # Apply theme to child frames
            if hasattr(self, "frame_main0"):
                self.frame_main0.configure(**frame_colors)
            if hasattr(self, "frame_main1"):
                self.frame_main1.configure(**frame_colors)
            if hasattr(self, "frame_main2"):
                self.frame_main2.configure(**frame_colors)

        # Apply theme to all child widgets that implement ThemeColorApplicable
        for widget in self.base_widgets.get_widgets():
            if hasattr(widget, "apply_theme_color"):
                widget.apply_theme_color(theme_colors)

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Theme settings dictionary
        """
        # Apply theme settings to this widget
        if theme_settings:
            self.configure(**theme_settings)

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop functionality for the canvas."""
        try:
            DragAndDropHandler.register_drop_target(
                self.canvas, self._on_drop,
                [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"],
                self._show_drop_feedback
            )
            # Log successful initialization of drag and drop
            logger.info(message_manager.get_log_message("L234"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L206", str(e)))

    def _on_drop(self, file_path: str) -> None:
        """Handle file drop event.

        Args:
            file_path: Path to dropped file
        """
        try:
            ext = Path(file_path).suffix.lower()
            if ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"]:
                img = Image.open(file_path)
                self.image_tk = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)
                self.base_path.set(file_path)
                self._show_drop_feedback(f"Image loaded: {file_path}", True)
            else:
                self._show_drop_feedback("Unsupported image format", False)
        except Exception as e:
            logger.error(message_manager.get_log_message("L207", str(e)))
            self._show_drop_feedback(f"Error: {str(e)}", False)

    def _show_drop_feedback(self, message: str, success: bool) -> None:
        """Show feedback message for drag and drop operation.

        Args:
            message: Feedback message to show
            success: Whether the operation was successful
        """
        try:
            if success:
                logger.info(message)
            else:
                logger.error(message)
            if self.status_var is not None:
                self.status_var.set(message)
            if self.after_id is not None:
                self.after_cancel(self.after_id)
            self.after_id = self.after(
                5000,
                lambda: self.status_var.set("") if self.status_var is not None else None,
            )
        except Exception as e:
            logger.error(message_manager.get_log_message("L204", str(e)))

    def _convert_image(self) -> None:
        """Convert image size based on user input."""
        try:
            # Validate input values
            width = int(self.width_var.get())
            height = int(self.height_var.get())

            if width <= 0 or height <= 0:
                raise ValueError("Width and height must be positive numbers")

            # Load image: validate base_file_info
            if not isinstance(self.base_file_info, FilePathInfo):
                raise FileNotFoundError(f"Base file not set or invalid: {self.base_file_info}")
            if not self.base_file_info.file_path.exists():
                raise FileNotFoundError(f"Base file not found: {self.base_file_info.file_path}")
            with Image.open(self.base_file_info.file_path) as img:
                # Create converter
                converter = ImageSizeConverter()

                # Convert image
                resized_img = converter.resize_image(img, width, height)

                # Construct output filename and path
                output_filename = (
                    self.base_file_info.file_path.stem
                    + "_resized"
                    + self.base_file_info.file_path.suffix
                )
                if not isinstance(self.output_folder_info, FolderPathInfo):
                    raise FileNotFoundError(f"Output folder not set or invalid: {self.output_folder_info}")
                output_path = self.output_folder_info.folder_path / output_filename

                # Save image
                converter.save_resized_image(resized_img, output_path)

                # Update canvas
                self._update_canvas(resized_img)

                messagebox.showinfo(
                    "Success", f"Image converted successfully:\n{output_path}"
                )

        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except FileNotFoundError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            logger.error(message_manager.get_log_message("L208", str(e)))
            messagebox.showerror("Error", "Image conversion failed")

    def _update_canvas(self, image: Image.Image) -> None:
        """Update canvas with the specified image."""
        self.canvas.delete("all")

        # Convert to PhotoImage for display
        self._canvas_photo = ImageTk.PhotoImage(image)

        # Center image on canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        self.canvas.create_image(
            canvas_width // 2, canvas_height // 2, image=self._canvas_photo, anchor="center"
        )


class NullProgressCallback:
    def __call__(self, current: int, total: int, message: Optional[str] = None) -> None:
        pass

    def current(self, current: int, total: int, message: str) -> None:
        pass

    def total(self, current: int, total: int, message: str) -> None:
        pass

    def message(self, current: int, total: int, message: str) -> None:
        pass


class ImageSizeConverter:
    def resize_image(self, image: Image.Image, width: int, height: int) -> Image.Image:
        return image.resize((width, height))

    def save_resized_image(self, image: Image.Image, output_path: Path) -> None:
        image.save(output_path)
