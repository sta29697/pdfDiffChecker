from __future__ import annotations
from logging import getLogger
from pathlib import Path
import tkinter as tk
from typing import Optional, Any, List, Dict
from PIL import Image, ImageTk, ImageFile
from PIL.Image import Resampling
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from utils.utils import get_resource_path, resolve_initial_dir

from configurations.message_manager import get_message_manager
from configurations import tool_settings
from models.class_dictionary import FilePathInfo
from controllers.drag_and_drop_file import DragAndDropHandler
from controllers.file2png_by_page import Pdf2PngByPages
from controllers.pdf_export_handler import PDFExportHandler
from widgets.base_button import BaseButton
from widgets.base_label_class import BaseLabelClass
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_file_analyze_button import BaseFileAnalyzeButton
from widgets.base_image_color_change_button import BaseImageColorChangeButton
from widgets.color_theme_change_button import ColorThemeChangeButton  # type: ignore
from widgets.progress_window import ProgressWindow
from widgets.language_select_combobox import LanguageSelectCombo
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.page_control_frame import PageControlFrame

from configurations.user_setting_manager import UserSettingManager
from controllers.image_sw_paths import ImageSwPaths
from controllers.mouse_event_handler import MouseEventHandler
from controllers.widgets_tracker import WidgetsTracker
from widgets.base_path_entry import BasePathEntry
from widgets.base_entry_class import BaseEntryClass
from controllers.color_theme_manager import ColorThemeManager

logger = getLogger(__name__)
message_manager = get_message_manager()


class CreateComparisonFileApp(tk.Frame, ColoringThemeIF):
    """Main tab of the application for comparing PDF files.

    This class provides the main interface for PDF file comparison functionality.
    It includes UI elements for:
    1. File selection (base and comparison PDFs)
    2. Output folder selection
    3. DPI settings
    4. Page navigation
    5. Theme customization
    6. PDF comparison and analysis

    Attributes:
        root (tk.Widget): Parent widget
        base_widgets (BaseTabWidgets): Base tab widget container
        base_file_obj (Optional[FilePathInfo]): Base PDF file information
        comparison_file_obj (Optional[FilePathInfo]): Comparison PDF file information
        output_folder_obj (Optional[Path]): Output folder path
        base_path (str): Path to base PDF file
        comparison_path (str): Path to comparison PDF file
        output_path (str): Path to output folder
        base_pages (List[fitz.Page]): List of pages from base PDF
        comp_pages (List[fitz.Page]): List of pages from comparison PDF
        selected_dpi_value (int): Selected DPI value for rendering
    """

    def __init__(
        self, master: tk.Misc, settings: UserSettingManager
    ) -> None:
        """Initialize the main comparison tab.

        Args:
            master (tk.Misc): Parent window
            settings (UserSettingManager): Application settings
        """
        # Init main tab class
        logger.debug(message_manager.get_log_message("L243"))
        super().__init__(master)
        WidgetsTracker().add_widgets(self)
        self.settings = settings
        self.master = master
        self.file_operation_status: bool = True
        self.selected_dpi_value: int = self._get_selected_dpi()
        self.base_widgets = BaseTabWidgets(self)
        self.status_var = tk.StringVar(value="")
        self.base_path = tk.StringVar(value=message_manager.get_ui_message("U053"))
        self.comparison_path = tk.StringVar(value=message_manager.get_ui_message("U053"))
        self.output_path = tk.StringVar(value=message_manager.get_ui_message("U054"))
        self.visualized_image = tk.StringVar(value="base")
        self.current_page_index = 0
        self.page_count = 0
        self.base_pages: List[str] = []
        self.comp_pages: List[str] = []
        self.base_transform_data: List[tuple[float, float, float, float]] = []
        self.comp_transform_data: List[tuple[float, float, float, float]] = []
        self.page_control_frame: Optional[PageControlFrame] = None
        self.mouse_handler: Optional[MouseEventHandler] = None
        self.photo_image: Optional[tk.PhotoImage] = None
        self._base_photo_image: Optional[ImageTk.PhotoImage] = None
        self._comp_photo_image: Optional[ImageTk.PhotoImage] = None
        self._automatic_execute_button: Optional[tk.Button] = None
        self._custom_execute_button: Optional[tk.Button] = None
        self._automatic_button_images: Dict[str, ImageTk.PhotoImage] = {}
        self._custom_button_images: Dict[str, ImageTk.PhotoImage] = {}
        self._visual_adjustments_enabled = False
        self._copy_protected = False
        self._conversion_dpi = self._get_selected_dpi()
        self.base_page_paths: List[Path] = []
        self.comp_page_paths: List[Path] = []
        self.base_file_info: Optional[FilePathInfo] = None
        self.comp_file_info: Optional[FilePathInfo] = None
        self.base_pdf_metadata: Dict[str, Any] = {}
        self.comp_pdf_metadata: Dict[str, Any] = {}
        self.base_pdf_converter: Optional[Pdf2PngByPages] = None
        self.comp_pdf_converter: Optional[Pdf2PngByPages] = None

        # Button images
        self.auto_conv_btn_img: Optional[ImageSwPaths] = None
        self.custom_conv_btn_img: Optional[ImageSwPaths] = None
        self.move_start_page_btn_img: Optional[ImageSwPaths] = None
        self.move_prev_page_btn_img: Optional[ImageSwPaths] = None
        self.move_next_page_btn_img: Optional[ImageSwPaths] = None
        self.move_end_page_btn_img: Optional[ImageSwPaths] = None

        # Setup UI components
        self._setup_frames()
        self._setup_widgets()
        self._setup_drag_and_drop()
        self.after_idle(self._sync_shared_paths_from_settings)
        self.after_idle(self._apply_current_theme_after_build)
        # Completed main tab init
        logger.debug(message_manager.get_log_message("L244"))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings.

        Args:
            theme_settings: Theme settings for the main comparison canvas.
        """
        if hasattr(self, "canvas"):
            self.canvas.configure(
                background=theme_settings.get("background", theme_settings.get("bg", "#ffffff")),
                highlightbackground=theme_settings.get("highlightbackground", "#e0e0e0"),
                highlightcolor=theme_settings.get("highlightcolor", "#e0e0e0"),
            )

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply theme to this tab and its widgets.

        Args:
            theme_data: Theme data obtained from the current theme manager.
        """
        window_settings = theme_data.get("Window", {})
        window_bg = window_settings.get("bg", "#ffffff")
        frame_settings = theme_data.get("Frame", {})
        frame_bg = frame_settings.get("bg", window_bg)
        frame_fg = frame_settings.get("fg", "#000000")

        self.configure(bg=frame_bg)
        for attr_name in ["frame_main0", "frame_main1", "frame_main2", "frame_main3"]:
            frame = getattr(self, attr_name, None)
            if frame is not None:
                frame.configure(bg=frame_bg)

        notebook_settings = theme_data.get("Notebook", {})
        canvas_theme = theme_data.get("canvas", {})
        canvas_background = notebook_settings.get("tab_bg", notebook_settings.get("bg", frame_bg))
        self._config_widget(
            {
                "background": canvas_theme.get("background", canvas_background),
                "highlightbackground": canvas_theme.get("highlightbackground", frame_bg),
                "highlightcolor": canvas_theme.get("highlightcolor", frame_fg),
            }
        )

        process_button_theme = dict(theme_data.get("process_button", {}))
        if process_button_theme:
            for action_button in [
                getattr(self, "_automatic_execute_button", None),
                getattr(self, "_custom_execute_button", None),
            ]:
                if action_button is not None:
                    action_button.configure(
                        bg=process_button_theme.get("bg", frame_bg),
                        fg=process_button_theme.get("fg", frame_fg),
                        activebackground=process_button_theme.get("activebackground", process_button_theme.get("bg", frame_bg)),
                        activeforeground=process_button_theme.get("activeforeground", process_button_theme.get("fg", frame_fg)),
                        highlightbackground=frame_bg,
                    )

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.apply_theme_color(theme_data)
            except Exception:
                pass

    def _apply_current_theme_after_build(self) -> None:
        """Apply the current theme after all child widgets are created."""
        self.apply_theme_color(ColorThemeManager.get_instance().get_current_theme())

    def _load_action_button_image(self, image_path: object, fallback_text: str) -> Optional[ImageTk.PhotoImage]:
        """Load and resize an action button image for the main tab.

        Args:
            image_path: Candidate image path resolved by ``ImageSwPaths``.
            fallback_text: Human-readable label used only for logging context.

        Returns:
            Optional[ImageTk.PhotoImage]: Loaded image reference when available.
        """
        try:
            if image_path is None:
                return None

            resolved_path = Path(str(image_path))
            if not resolved_path.exists():
                return None

            # Main processing: normalize action button artwork to a stable display height.
            with Image.open(resolved_path) as pil_image:
                prepared = pil_image.convert("RGBA")
                target_height = 34
                scale = target_height / float(max(1, prepared.height))
                target_width = max(1, int(prepared.width * scale))
                resized = prepared.resize((target_width, target_height), Resampling.LANCZOS)
                return ImageTk.PhotoImage(resized)
        except Exception as exc:
            logger.warning(f"Failed to load main tab action button image ({fallback_text}): {exc}")
            return None

    def _build_action_button_images(self, image_kind: str) -> Dict[str, ImageTk.PhotoImage]:
        """Build the active and inactive images for a main-tab action button.

        Args:
            image_kind: Either ``automatic`` or ``custom``.

        Returns:
            Dict[str, ImageTk.PhotoImage]: Loaded ``on``/``off`` image dictionary.
        """
        switch_paths = (
            ImageSwPaths().set_automatic_convert_btn_image(
                program_mode=tool_settings.program_mode == "PRODUCTION_MODE"
            )
            if image_kind == "automatic"
            else ImageSwPaths().set_custom_convert_btn_image(
                program_mode=tool_settings.program_mode == "PRODUCTION_MODE"
            )
        )

        loaded_images: Dict[str, ImageTk.PhotoImage] = {}
        on_image = self._load_action_button_image(switch_paths.on_img_path, f"{image_kind}-on")
        off_image = self._load_action_button_image(switch_paths.off_img_path, f"{image_kind}-off")
        if on_image is not None:
            loaded_images["on"] = on_image
        if off_image is not None:
            loaded_images["off"] = off_image
        return loaded_images

    def _apply_action_button_visual(self, image_kind: str, active: bool, refresh_random: bool = False) -> None:
        """Apply the current image state to one of the restored action buttons.

        Args:
            image_kind: Either ``automatic`` or ``custom``.
            active: Whether the button should show its active artwork.
            refresh_random: Whether the random custom artwork should be refreshed first.
        """
        button = self._automatic_execute_button if image_kind == "automatic" else self._custom_execute_button
        if button is None:
            return

        if image_kind == "automatic":
            if not self._automatic_button_images:
                self._automatic_button_images = self._build_action_button_images("automatic")
            image_map = self._automatic_button_images
            fallback_text = message_manager.get_ui_message("U023")
        else:
            if refresh_random or not self._custom_button_images:
                self._custom_button_images = self._build_action_button_images("custom")
            image_map = self._custom_button_images
            fallback_text = "Execute"

        requested_key = "on" if active else "off"
        requested_image = image_map.get(requested_key) or image_map.get("off") or image_map.get("on")
        if requested_image is not None:
            button.configure(image=requested_image, text="")
            button.image = requested_image
        else:
            button.configure(image="", text=fallback_text)

    def _restore_action_buttons_after_execute(self) -> None:
        """Restore the image buttons after an execute operation completes.

        The custom button intentionally refreshes its inactive artwork again so the
        remembered random-image gimmick is visible after each execute action.
        """
        self._apply_action_button_visual("automatic", False)
        self._apply_action_button_visual("custom", False, refresh_random=True)

    def _on_automatic_image_button_click(self) -> None:
        """Handle the restored automatic image button click event."""
        self._apply_action_button_visual("automatic", True)
        try:
            self._on_process_click()
        finally:
            self.after(180, lambda: self._apply_action_button_visual("automatic", False))

    def _on_custom_image_button_click(self) -> None:
        """Handle the restored custom image button click event."""
        self._apply_action_button_visual("custom", True)
        try:
            self._on_execute_click()
        finally:
            # Main processing: restore both image buttons so the custom artwork can reshuffle.
            self.after(180, self._restore_action_buttons_after_execute)

    def _get_initial_dir_from_setting(self, setting_key: str) -> str:
        """Return an initial directory for file and folder dialogs.

        Args:
            setting_key: User setting key for the target path.

        Returns:
            A directory path suitable for ``initialdir``.
        """
        try:
            saved_value = self.settings.get_setting(setting_key)
        except Exception:
            saved_value = None

        if isinstance(saved_value, str) and saved_value:
            try:
                path = Path(saved_value)
                if path.exists() and path.is_dir():
                    return str(path)
                if path.parent.exists() and path.parent.is_dir():
                    return str(path.parent)
            except Exception:
                return str(Path.cwd())

        return str(Path.cwd())

    def _sync_shared_paths_from_settings(self, event: Any = None) -> None:
        """Synchronize persisted paths into the main tab inputs.

        Args:
            event: Tkinter visibility event.
        """
        _ = event
        placeholder_file = message_manager.get_ui_message("U053")
        placeholder_output = message_manager.get_ui_message("U054")

        try:
            saved_base = self.settings.get_setting("base_file_path")
            if isinstance(saved_base, str) and saved_base and saved_base != placeholder_file:
                saved_base_path = Path(saved_base)
                if saved_base_path.exists() and saved_base_path.is_file():
                    if self._base_file_path_entry.path_var.get() != saved_base:
                        self._base_file_path_entry.path_var.set(saved_base)
                        self.base_path.set(saved_base)

            saved_comparison = self.settings.get_setting("comparison_file_path")
            if isinstance(saved_comparison, str) and saved_comparison and saved_comparison != placeholder_file:
                saved_comparison_path = Path(saved_comparison)
                if saved_comparison_path.exists() and saved_comparison_path.is_file():
                    if self._comparison_file_path_entry.path_var.get() != saved_comparison:
                        self._comparison_file_path_entry.path_var.set(saved_comparison)
                        self.comparison_path.set(saved_comparison)

            saved_output = self.settings.get_setting("output_folder_path")
            if isinstance(saved_output, str) and saved_output and saved_output != placeholder_output:
                saved_output_path = Path(saved_output)
                if saved_output_path.exists() and saved_output_path.is_dir():
                    if self._output_folder_path_entry.path_var.get() != saved_output:
                        self._output_folder_path_entry.path_var.set(saved_output)
                        self.output_path.set(saved_output)
            self._refresh_workspace_state()
        except Exception as exc:
            logger.warning(f"Shared path sync failed in main tab: {exc}")

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop for input and output path entries."""
        try:
            DragAndDropHandler.register_drop_target(
                self._base_file_path_entry,
                self._on_drop_base_file,
                [".pdf"],
                self._show_status_feedback,
            )
            DragAndDropHandler.register_drop_target(
                self._comparison_file_path_entry,
                self._on_drop_comparison_file,
                [".pdf"],
                self._show_status_feedback,
            )
            DragAndDropHandler.register_drop_target(
                self._output_folder_path_entry,
                self._on_drop_output_folder,
                feedback_callback=self._show_status_feedback,
                allow_directories=True,
            )
        except Exception as e:
            logger.error(message_manager.get_log_message("L206", str(e)))

    def _on_drop_base_file(self, file_path: str) -> None:
        """Handle base PDF drop.

        Args:
            file_path: Dropped file path.
        """
        self._base_file_path_entry.path_var.set(file_path)
        self.base_path.set(file_path)
        self.status_var.set("Base PDF selected for comparison workspace.")
        self._refresh_workspace_state()

    def _on_drop_comparison_file(self, file_path: str) -> None:
        """Handle comparison PDF drop.

        Args:
            file_path: Dropped file path.
        """
        self._comparison_file_path_entry.path_var.set(file_path)
        self.comparison_path.set(file_path)
        self.status_var.set("Comparison PDF selected for comparison workspace.")
        self._refresh_workspace_state()

    def _on_drop_output_folder(self, folder_path: str) -> None:
        """Handle output folder drop.

        Args:
            folder_path: Dropped folder path.
        """
        self._output_folder_path_entry.path_var.set(folder_path)
        self.output_path.set(folder_path)
        self.status_var.set("Output folder updated for future comparison export.")
        if not self._has_loaded_workspace_pages():
            self._render_comparison_placeholder()

    def _show_status_feedback(self, message: str, is_success: bool) -> None:
        """Store drag-and-drop feedback and mirror it to the logger.

        Args:
            message: Feedback message.
            is_success: Whether the operation succeeded.
        """
        self.status_var.set(message)
        if is_success:
            logger.info(message)
        else:
            logger.warning(message)
        if self._has_loaded_workspace_pages():
            return
        self._render_comparison_placeholder()

    def _clear_loaded_workspace_data(self) -> None:
        """Clear converted page data and active converter references."""
        self.base_page_paths = []
        self.comp_page_paths = []
        self.base_pages = []
        self.comp_pages = []
        self.base_transform_data = []
        self.comp_transform_data = []
        self.page_count = 0
        self.current_page_index = 0
        self._copy_protected = False
        self._visual_adjustments_enabled = False
        self.base_file_info = None
        self.comp_file_info = None
        self.base_pdf_metadata = {}
        self.comp_pdf_metadata = {}
        self.base_pdf_converter = None
        self.comp_pdf_converter = None
        self._base_photo_image = None
        self._comp_photo_image = None

    def _has_loaded_workspace_pages(self) -> bool:
        """Return whether converted workspace pages are available.

        Returns:
            ``True`` when at least one rendered page image exists.
        """
        return bool(self.base_page_paths or self.comp_page_paths)

    def _get_selected_dpi(self) -> int:
        """Return a safe DPI value from user settings.

        Returns:
            Integer DPI value used for PDF rendering.
        """
        # Main processing: accept numeric settings and fall back safely when settings store labels like "default".
        raw_dpi = self.settings.get_setting("setted_dpi", 150)
        try:
            resolved_dpi = int(raw_dpi)
        except (TypeError, ValueError):
            resolved_dpi = 150
        return max(1, resolved_dpi)

    def _path_points_to_file(self, path_value: str) -> bool:
        """Return whether the given path points to an existing file.

        Args:
            path_value: Candidate path string.

        Returns:
            ``True`` when the path exists and is a file.
        """
        try:
            if not path_value:
                return False
            return Path(path_value).exists() and Path(path_value).is_file()
        except Exception:
            return False

    def _ensure_transform_slots(self, target_length: int) -> None:
        """Resize transform arrays to match the current page count.

        Args:
            target_length: Required transform list length.
        """
        default_transform = (0.0, 0.0, 0.0, 1.0)
        while len(self.base_transform_data) < len(self.base_pages):
            self.base_transform_data.append(default_transform)
        while len(self.comp_transform_data) < len(self.comp_pages):
            self.comp_transform_data.append(default_transform)
        self.base_transform_data = self.base_transform_data[: len(self.base_pages)]
        self.comp_transform_data = self.comp_transform_data[: len(self.comp_pages)]
        if target_length <= 0:
            self.base_transform_data = []
            self.comp_transform_data = []

    def _get_or_create_converter(
        self, pdf_path: str, name_flag: str
    ) -> tuple[Pdf2PngByPages, FilePathInfo]:
        """Create or reuse a PDF converter for the requested side.

        Args:
            pdf_path: Source PDF path.
            name_flag: Side identifier, either ``"base"`` or ``"comp"``.

        Returns:
            Tuple of converter and file information.
        """
        existing_converter = self.base_pdf_converter if name_flag == "base" else self.comp_pdf_converter
        existing_info = self.base_file_info if name_flag == "base" else self.comp_file_info
        requested_path = Path(pdf_path)

        if (
            existing_converter is not None
            and existing_info is not None
            and existing_info.file_path == requested_path
        ):
            return existing_converter, existing_info

        file_info = FilePathInfo(
            file_path=requested_path,
            file_page_count=0,
            file_meta_info={},
            file_histogram_data=[],
        )
        converter = Pdf2PngByPages(
            pdf_obj=file_info,
            program_mode=tool_settings.program_mode,
            name_flag=name_flag,
        )

        if name_flag == "base":
            self.base_pdf_converter = converter
            self.base_file_info = file_info
            self.base_pdf_metadata = dict(file_info.file_meta_info)
        else:
            self.comp_pdf_converter = converter
            self.comp_file_info = file_info
            self.comp_pdf_metadata = dict(file_info.file_meta_info)

        return converter, file_info

    def _collect_png_page_paths(self, temp_dir: str, name_flag: str, page_count: int) -> List[Path]:
        """Collect converted PNG page paths from a converter output directory.

        Args:
            temp_dir: Directory where the converter wrote PNG files.
            name_flag: ``"base"`` or ``"comp"``.
            page_count: Expected page count.

        Returns:
            Existing PNG path list in page order.
        """
        page_paths: List[Path] = []
        temp_dir_path = Path(str(temp_dir))
        for page_num in range(1, page_count + 1):
            candidate = temp_dir_path / f"{name_flag}_{page_num:04d}.png"
            if candidate.exists():
                page_paths.append(candidate)
        return page_paths

    def _analyze_pdf_path(self, pdf_path: str, name_flag: str) -> Dict[str, Any]:
        """Analyze one selected PDF and return a compact summary.

        Args:
            pdf_path: Source PDF path.
            name_flag: ``"base"`` or ``"comp"``.

        Returns:
            Summary containing file path, page count, and protection flags.
        """
        converter, file_info = self._get_or_create_converter(pdf_path, name_flag)
        metadata = dict(file_info.file_meta_info)
        summary = {
            "path": str(file_info.file_path),
            "page_count": int(file_info.file_page_count),
            "copy_protected": bool(metadata.get("CopyProtected", metadata.get("Encrypted", False))),
            "temp_dir": str(converter._temp_dir),
        }
        if name_flag == "base":
            self.base_pdf_metadata = metadata
        else:
            self.comp_pdf_metadata = metadata
        return summary

    def _convert_pdf_for_workspace(self, pdf_path: str, name_flag: str) -> List[Path]:
        """Convert a PDF to page PNGs and return the collected output paths.

        Args:
            pdf_path: Source PDF path.
            name_flag: ``"base"`` or ``"comp"``.

        Returns:
            Converted page path list.
        """
        converter, file_info = self._get_or_create_converter(pdf_path, name_flag)
        self._conversion_dpi = self._get_selected_dpi()
        converter.process_with_progress_window(self.frame_main3, dpi=self._conversion_dpi)
        page_paths = self._collect_png_page_paths(
            temp_dir=str(converter._temp_dir),
            name_flag=name_flag,
            page_count=int(file_info.file_page_count),
        )
        if name_flag == "base":
            self.base_pdf_metadata = dict(file_info.file_meta_info)
        else:
            self.comp_pdf_metadata = dict(file_info.file_meta_info)
        return page_paths

    def _refresh_operation_restriction_state(self) -> None:
        """Refresh whether transform operations should be enabled."""
        # Main processing: disable transform editing when either source is copy protected.
        base_protected = bool(self.base_pdf_metadata.get("CopyProtected", self.base_pdf_metadata.get("Encrypted", False)))
        comp_protected = bool(self.comp_pdf_metadata.get("CopyProtected", self.comp_pdf_metadata.get("Encrypted", False)))
        self._copy_protected = base_protected or comp_protected
        self._visual_adjustments_enabled = self._has_loaded_workspace_pages() and not self._copy_protected

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.set_edit_buttons_enabled(self._has_loaded_workspace_pages() and not self._copy_protected)
            except Exception:
                pass

        if self.mouse_handler is not None:
            try:
                self.mouse_handler.set_operations_enabled(self._visual_adjustments_enabled)
            except Exception:
                pass

    def _apply_transform_to_image(
        self,
        pil_image: Image.Image,
        transform: tuple[float, float, float, float],
    ) -> Image.Image:
        """Apply rotation and scale to a rendered page image.

        Args:
            pil_image: Source page image.
            transform: Transform tuple ``(rotation, tx, ty, scale)``.

        Returns:
            Transformed PIL image.
        """
        rotation, _translate_x, _translate_y, scale = transform
        transformed_image = pil_image
        if rotation != 0:
            transformed_image = transformed_image.rotate(rotation, resample=Resampling.BICUBIC, expand=True)
        if scale != 1.0:
            new_width = int(transformed_image.width * scale)
            new_height = int(transformed_image.height * scale)
            if new_width > 0 and new_height > 0:
                transformed_image = transformed_image.resize((new_width, new_height), Resampling.LANCZOS)
        return transformed_image

    def _get_display_page_path(self, page_paths: List[Path], page_index: int) -> Optional[Path]:
        """Return the page PNG path for the requested index when available.

        Args:
            page_paths: Converted page list.
            page_index: Zero-based page index.

        Returns:
            Matching page path or ``None``.
        """
        if 0 <= page_index < len(page_paths):
            return page_paths[page_index]
        return None

    def _display_page(self, page_index: int) -> None:
        """Display one page of the converted comparison workspace.

        Args:
            page_index: Zero-based page index.
        """
        if not self._has_loaded_workspace_pages():
            self._render_comparison_placeholder()
            return
        if not (0 <= page_index < self.page_count):
            self._show_status_feedback("Requested page is out of range.", False)
            return

        try:
            self.canvas.delete("pdf_image")
        except Exception:
            self.canvas.delete("all")

        base_path = self._get_display_page_path(self.base_page_paths, page_index)
        comp_path = self._get_display_page_path(self.comp_page_paths, page_index)
        base_image: Optional[Image.Image] = None
        comp_image: Optional[Image.Image] = None

        if base_path is not None and base_path.exists():
            base_image = Image.open(base_path).convert("RGBA")
        if comp_path is not None and comp_path.exists():
            comp_image = Image.open(comp_path).convert("RGBA")

        if base_image is None and comp_image is None:
            self._show_status_feedback("Rendered page images could not be found.", False)
            return

        reference_image = base_image if base_image is not None else comp_image
        if reference_image is not None:
            self._original_page_width = reference_image.width
            self._original_page_height = reference_image.height
            if self.mouse_handler is not None and hasattr(self.mouse_handler, "set_original_image_size"):
                try:
                    self.mouse_handler.set_original_image_size(reference_image.width, reference_image.height)
                except Exception:
                    pass

        if base_image is not None and page_index < len(self.base_transform_data):
            base_image = self._apply_transform_to_image(base_image, self.base_transform_data[page_index])
        if comp_image is not None and page_index < len(self.comp_transform_data):
            comp_image = self._apply_transform_to_image(comp_image, self.comp_transform_data[page_index])

        self._base_photo_image = None
        self._comp_photo_image = None

        if base_image is not None:
            _, translate_x, translate_y, _ = self.base_transform_data[page_index]
            self._base_photo_image = ImageTk.PhotoImage(base_image)
            self.canvas.create_image(
                int(translate_x),
                int(translate_y),
                anchor="nw",
                image=self._base_photo_image,
                tags=("pdf_image", "base_image"),
            )

        if comp_image is not None:
            # Main processing: make the comparison layer semi-transparent so both pages stay visible while aligned.
            if comp_image.mode != "RGBA":
                comp_image = comp_image.convert("RGBA")
            overlay_image = comp_image.copy()
            overlay_image.putalpha(150)
            _, translate_x, translate_y, _ = self.comp_transform_data[page_index]
            self._comp_photo_image = ImageTk.PhotoImage(overlay_image)
            self.canvas.create_image(
                int(translate_x),
                int(translate_y),
                anchor="nw",
                image=self._comp_photo_image,
                tags=("pdf_image", "comp_image"),
            )

        try:
            self.canvas.config(scrollregion=self.canvas.bbox("pdf_image"))
        except Exception:
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

        previous_page_index = getattr(self, "current_page_index", None)
        self.current_page_index = page_index

        visible_layers: Dict[int, bool] = {}
        if base_image is not None:
            visible_layers[0] = True
        if comp_image is not None:
            visible_layers[1] = True

        if self.mouse_handler is not None:
            self.mouse_handler.update_state(
                current_page_index=page_index,
                visible_layers=visible_layers,
            )
            if hasattr(self.mouse_handler, "refresh_overlay_positions"):
                self.mouse_handler.refresh_overlay_positions()

        if self.page_control_frame is not None:
            if previous_page_index != page_index:
                self.page_control_frame.update_page_label(page_index, self.page_count)
            rotation, tx, ty, scale = self._get_active_transform()
            self.page_control_frame.update_transform_info(rotation, tx, ty, scale)

        try:
            self.canvas.focus_set()
        except Exception:
            pass

    def _get_active_transform(self) -> tuple[float, float, float, float]:
        """Return the transform currently shown in the placeholder canvas.

        Returns:
            Transform tuple ``(rotation, tx, ty, scale)``.
        """
        if self.base_transform_data and self.current_page_index < len(self.base_transform_data):
            return self.base_transform_data[self.current_page_index]
        if self.comp_transform_data and self.current_page_index < len(self.comp_transform_data):
            return self.comp_transform_data[self.current_page_index]
        return (0.0, 0.0, 0.0, 1.0)

    def _refresh_workspace_state(self) -> None:
        """Refresh comparison workspace state from the selected paths."""
        # Main processing: reset to the pre-conversion state whenever the selected source paths change.
        self._clear_loaded_workspace_data()
        base_selected = self._path_points_to_file(self.base_path.get())
        comparison_selected = self._path_points_to_file(self.comparison_path.get())

        self.base_pages = [self.base_path.get()] if base_selected else []
        self.comp_pages = [self.comparison_path.get()] if comparison_selected else []
        self.page_count = 0
        self.current_page_index = 0
        self._create_page_control_frame(0)
        self._setup_mouse_events(0)
        self._render_comparison_placeholder()

    def _render_comparison_placeholder(self) -> None:
        """Render the current minimal comparison workspace on the canvas."""
        if not hasattr(self, "canvas"):
            return

        # Main processing: show selected input state before real page conversion is executed.
        self.canvas.delete("all")
        canvas_width = max(self.canvas.winfo_width(), 720)
        canvas_height = max(self.canvas.winfo_height(), 420)
        active_theme = ColorThemeManager.get_instance().get_current_theme()
        notebook_theme = active_theme.get("Notebook", {})
        frame_theme = active_theme.get("Frame", {})
        canvas_bg = notebook_theme.get("tab_bg", notebook_theme.get("bg", frame_theme.get("bg", "#ffffff")))
        text_fg = frame_theme.get("fg", "#000000")
        accent_fg = active_theme.get("process_button", {}).get("fg", text_fg)
        border_fg = active_theme.get("canvas", {}).get("highlightbackground", "#6c6c6c")

        self.canvas.configure(bg=canvas_bg)
        self.canvas.create_rectangle(
            16,
            16,
            canvas_width - 16,
            canvas_height - 16,
            outline=border_fg,
            width=2,
            tags=("workspace",),
        )

        title_text = "Main tab comparison workspace"
        self.canvas.create_text(
            32,
            36,
            anchor="nw",
            text=title_text,
            fill=accent_fg,
            font=("", 12, "bold"),
            tags=("workspace",),
        )

        page_display = self.current_page_index + 1 if self.page_count > 0 else 0
        rotation, tx, ty, scale = self._get_active_transform()
        body_lines = [
            f"Base PDF: {self.base_path.get()}",
            f"Comparison PDF: {self.comparison_path.get()}",
            f"Output folder: {self.output_path.get()}",
            f"Page: {page_display} / {self.page_count}",
            f"Transform: rotation={rotation:.1f}, tx={tx:.1f}, ty={ty:.1f}, scale={scale:.3f}",
            f"Analyze button: reads selected PDF metadata for each side.",
            f"Process button: converts PDFs to page PNGs and builds the workspace.",
            f"Automatic image button: builds the page workspace from selected PDFs.",
            f"Execute image button: refreshes the real comparison display and reshuffles its custom artwork.",
            f"Save button: exports the current transformed pages to PDF.",
        ]
        if self.status_var.get():
            body_lines.append(f"Status: {self.status_var.get()}")

        self.canvas.create_text(
            32,
            74,
            anchor="nw",
            text="\n".join(body_lines),
            fill=text_fg,
            width=max(canvas_width - 72, 320),
            font=("", 10),
            tags=("workspace",),
        )

    def _create_page_control_frame(self, page_count: int) -> None:
        """Create or recreate the page control frame for the current workspace.

        Args:
            page_count: Number of pages currently available in the workspace.
        """
        # Main processing: recreate the page control so callbacks and list references stay aligned.
        if self.page_control_frame is not None:
            try:
                self.page_control_frame.destroy()
            except Exception:
                pass
            self.page_control_frame = None

        self.page_control_frame = PageControlFrame(
            parent=self.frame_main3,
            color_key="page_control",
            base_pages=self.base_pages,
            comp_pages=self.comp_pages,
            base_transform_data=self.base_transform_data,
            comp_transform_data=self.comp_transform_data,
            visualized_image=self.visualized_image,
            page_amount_limit=max(1, page_count),
            on_prev_page=self._on_prev_page,
            on_next_page=self._on_next_page,
            on_insert_blank=self._on_insert_blank_placeholder,
            on_delete_page=self._on_delete_page_placeholder,
            on_export=self._on_pdf_save_click,
            on_page_entry=self._on_page_entry,
            on_transform_value_change=self._on_transform_value_input,
        )
        self.page_control_frame.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        self.page_control_frame.update_page_label(page_count - 1 if page_count == 0 else self.current_page_index, page_count)
        self.page_control_frame.set_edit_buttons_enabled(self._has_loaded_workspace_pages() and not self._copy_protected)
        self.page_control_frame.set_batch_edit_enabled(False)

    def _setup_mouse_events(self, page_count: int) -> None:
        """Set up mouse handling for the minimal comparison workspace.

        Args:
            page_count: Number of pages currently available.
        """
        # Main processing: only enable transform shortcuts when a placeholder page is present.
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Button-3>")
        self.canvas.unbind("<MouseWheel>")
        self.canvas.unbind("<Button-4>")
        self.canvas.unbind("<Button-5>")

        if page_count <= 0:
            self.mouse_handler = None
            return

        layer_transform_data: dict[int, list[tuple[float, float, float, float]]] = {}
        visible_layers: dict[int, bool] = {}
        if self.base_transform_data:
            layer_transform_data[0] = self.base_transform_data
            visible_layers[0] = True
        if self.comp_transform_data:
            layer_transform_data[1] = self.comp_transform_data
            visible_layers[1] = True

        self.mouse_handler = MouseEventHandler(
            layer_transform_data=layer_transform_data,
            current_page_index=self.current_page_index,
            visible_layers=visible_layers,
            on_transform_update=self._on_transform_update,
            operations_enabled=self._visual_adjustments_enabled,
        )
        self.mouse_handler.attach_to_canvas(self.canvas)
        self.mouse_handler.update_state(
            current_page_index=self.current_page_index,
            visible_layers=visible_layers,
        )

        self.canvas.bind(
            "<Button-1>",
            lambda e: (self.canvas.focus_set() or (self.mouse_handler.on_mouse_down(e) if self.mouse_handler else None)),
        )
        self.canvas.bind("<B1-Motion>", lambda e: self.mouse_handler.on_mouse_drag(e) if self.mouse_handler else None)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.mouse_handler.on_mouse_up(e) if self.mouse_handler else None)
        self.canvas.bind("<Button-3>", lambda e: self.mouse_handler.on_right_click(e) if self.mouse_handler and hasattr(self.mouse_handler, "on_right_click") else None)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)

    def _on_mouse_wheel(self, event: Any) -> None:
        """Forward mouse wheel events to the current mouse handler.

        Args:
            event: Mouse wheel event object.
        """
        if self.mouse_handler is None:
            return
        self.mouse_handler.on_mouse_wheel(event)

    def _on_prev_page(self) -> None:
        """Move to the previous placeholder page when available."""
        if self.page_count <= 0:
            self._show_status_feedback("No comparison workspace is ready yet.", False)
            return
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._on_transform_update()

    def _on_next_page(self) -> None:
        """Move to the next placeholder page when available."""
        if self.page_count <= 0:
            self._show_status_feedback("No comparison workspace is ready yet.", False)
            return
        if self.current_page_index < self.page_count - 1:
            self.current_page_index += 1
            self._on_transform_update()

    def _on_page_entry(self, event: tk.Event) -> None:
        """Jump to the requested page number in the minimal workspace.

        Args:
            event: Page-entry event.
        """
        _ = event
        if self.page_count <= 0 or self.page_control_frame is None:
            self._show_status_feedback("No comparison workspace is ready yet.", False)
            return

        requested_page = int(self.page_control_frame.page_var.get()) - 1
        if requested_page < 0 or requested_page >= self.page_count:
            self._show_status_feedback("Requested page is out of range.", False)
            return
        self.current_page_index = requested_page
        self._on_transform_update()

    def _on_transform_value_input(self, rotation: float, tx: float, ty: float, scale: float) -> None:
        """Apply the transform values entered in the page control frame.

        Args:
            rotation: Rotation angle.
            tx: X translation.
            ty: Y translation.
            scale: Scale factor.
        """
        if self.base_transform_data and self.current_page_index < len(self.base_transform_data):
            self.base_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
        if self.comp_transform_data and self.current_page_index < len(self.comp_transform_data):
            self.comp_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
        self._on_transform_update()

    def _on_transform_update(self) -> None:
        """Refresh page control and placeholder display after a transform update."""
        if self.mouse_handler is not None:
            visible_layers: dict[int, bool] = {}
            if self.base_page_paths:
                visible_layers[0] = True
            if self.comp_page_paths:
                visible_layers[1] = True
            self.mouse_handler.update_state(
                current_page_index=self.current_page_index,
                visible_layers=visible_layers,
            )
            if hasattr(self.mouse_handler, "refresh_overlay_positions"):
                self.mouse_handler.refresh_overlay_positions()

        if self._has_loaded_workspace_pages():
            self._display_page(self.current_page_index)
            return

        if self.page_control_frame is not None:
            self.page_control_frame.update_page_label(
                self.page_count - 1 if self.page_count == 0 else self.current_page_index,
                self.page_count,
            )
            rotation, tx, ty, scale = self._get_active_transform()
            self.page_control_frame.update_transform_info(rotation, tx, ty, scale)
        self._render_comparison_placeholder()

    def _on_insert_blank_placeholder(self) -> None:
        """Explain that blank-page insertion will be wired after real page conversion."""
        self._show_status_feedback(
            "Blank-page insertion will be enabled after real comparison page conversion is connected.",
            False,
        )

    def _on_delete_page_placeholder(self) -> None:
        """Explain that page deletion will be wired after real page editing is defined."""
        self._show_status_feedback(
            "Page deletion will be enabled after the comparison editing rules are finalized.",
            False,
        )

    def _setup_frames(self) -> None:
        """Setup the main frame layout.

        Creates and configures the following frames:
        1. frame_main0: Top frame for theme controls
        2. frame_main1: File selection frame
        3. frame_main2: Analysis controls frame
        4. frame_main3: Canvas display frame

        Raises:
            Exception: If frame setup fails

        Note:
            This method creates a responsive layout using grid geometry manager,
            which allows for better widget positioning and resizing behavior.
        """
        # Start setting up frames
        logger.debug(message_manager.get_log_message("L245"))
        try:
            # Configure grid weights for main frame
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)

            # Setup main frames
            # Main processing: keep the header compact without forcing an undersized fixed height.
            self.frame_main0 = tk.Frame(self, relief=tk.RIDGE, borderwidth=1)
            self.frame_main0.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="ew", ipady=3)
            # Configure frame_main0 to right-align its contents
            self.frame_main0.columnconfigure(0, weight=1)  # Make first column expandable
            self.frame_main0.columnconfigure(1, weight=0)  # Keep second column fixed size
            self.frame_main0.grid_rowconfigure(0, minsize=40)

            self.frame_main1 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main1.grid(row=1, column=0, padx=5, pady=1, sticky="nsew")
            self.frame_main1.grid_columnconfigure(1, weight=1)
            self.frame_main1.grid_columnconfigure(2, weight=1)

            self.frame_main2 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main2.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
            self.frame_main2.grid_columnconfigure(1, weight=1)

            self.frame_main3 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main3.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")
            self.frame_main3.grid_rowconfigure(0, weight=1)
            self.frame_main3.grid_columnconfigure(0, weight=1)
            # Make canvas area expand more
            self.grid_rowconfigure(3, weight=8)

            # Frames setup completed
            logger.debug(message_manager.get_log_message("L246"))
        except Exception as e:
            # Failed to setup frames
            logger.error(message_manager.get_log_message("L066", str(e)))
            raise

    def _setup_widgets(self) -> None:
        """Setup all widgets in the application.

        Creates and configures the following widgets:
        1. Color theme change button
        2. PDF display canvas
        3. File analysis buttons
        4. File path labels and entries
        5. DPI selection controls

        Raises:
            Exception: If widget setup fails

        Note:
            This method initializes all interactive elements of the application,
            including buttons, labels, and input fields. Each widget is configured
            with appropriate event handlers and visual properties.
        """
        # Start setting up widgets
        logger.debug(message_manager.get_log_message("L247"))
        try:
            # Create language selection combobox
            lang_combo = LanguageSelectCombo(self.frame_main0)
            lang_combo.grid(row=0, column=0, padx=3, pady=3, sticky="e")

            # Create theme change button
            # UI text for Change Theme button
            self._color_theme_change_btn = ColorThemeChangeButton(
                fr=self.frame_main0,
                color_theme_change_btn_status=False,
                text=message_manager.get_ui_message("U025"),
            )
            self._color_theme_change_btn.grid(
                row=0, column=1, padx=3, pady=2, sticky="e"
            )

            # Base file path label and entry
            # UI text for Base File Path label
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

            # Base image color change button
            self._base_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="base_image_color_change_button",
                command=self._on_base_image_color_change,
                width=2,
            )
            self._base_image_color_change_btn.grid(column=3, row=1, padx=2, pady=2)

            # Base file path select button
            # UI text for Base File Path select button
            self._base_file_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="base_file_path_button",
                entry_setting_key="base_file_path",
                share_path_entry=self._base_file_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_base_file_select,
            )
            self._base_file_path_button.grid(column=4, row=1, padx=5, pady=8)

            # Base file analyze button
            # UI text for Analyze Base File button
            self._base_file_analyze_btn = BaseFileAnalyzeButton(
                fr=self.frame_main1,
                color_key="base_file_analyze_button",
                text=message_manager.get_ui_message("U016"),
                command=self._on_base_analyze_click,
            )
            self._base_file_analyze_btn.grid(column=5, row=1, padx=5, pady=8)

            # Comparison file path label and entry
            # UI text for Comparison File Path label
            self._comparison_file_path_label = BaseLabelClass(
                fr=self.frame_main1,
                color_key="comparison_file_path_label",
                text=message_manager.get_ui_message("U020"),
            )
            self._comparison_file_path_label.grid(
                column=0, row=2, padx=5, pady=8, sticky="nw"
            )

            # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
            self._comparison_file_path_entry = BasePathEntry(
                fr=self.frame_main1,
                color_key="comparison_file_path_entry",
                entry_setting_key="comparison_file_path"
            )
            self._comparison_file_path_entry.grid(
                column=1, row=2, columnspan=2, padx=5, pady=8, sticky="we"
            )
            self._comparison_file_path_entry.path_var.set(self.comparison_path.get())

            # Comparison image color change button
            self._comparison_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="comparison_image_color_change_button",
                command=self._on_comparison_image_color_change,
                width=2,
            )
            self._comparison_image_color_change_btn.grid(column=3, row=2, padx=2, pady=2)

            # Comparison file path button
            # UI text for Comparison File Path select button
            self._comparison_file_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="comparison_file_path_button",
                entry_setting_key="comparison_file_path",
                share_path_entry=self._comparison_file_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_comparison_file_select,
            )
            self._comparison_file_path_button.grid(column=4, row=2, padx=5, pady=8)

            # Comparison file analyze button
            # UI text for Analyze Comparison File button
            self._comparison_file_analyze_btn = BaseFileAnalyzeButton(
                fr=self.frame_main1,
                color_key="comparison_file_analyze_button",
                text=message_manager.get_ui_message("U017"),
                command=self._on_comparison_analyze_click,
            )
            self._comparison_file_analyze_btn.grid(column=5, row=2, padx=5, pady=8)

            # Output folder path label and entry
            # UI text for Output Folder Path label
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
                column=1, row=3, columnspan=2, padx=5, pady=8, sticky="we"
            )
            self._output_folder_path_entry.path_var.set(self.output_path.get())

            # Output folder path button
            # UI text for Output Folder Path select button
            self._output_folder_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="output_folder_path_button",
                entry_setting_key="output_folder_path",
                share_path_entry=self._output_folder_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_output_folder_select,
            )
            self._output_folder_path_button.grid(column=4, row=3, padx=5, pady=8)

            # DPI selection controls
            # UI text for DPI Setting label
            self._dpi_label = BaseLabelClass(
                fr=self.frame_main2,
                color_key="dpi_label",
                text=message_manager.get_ui_message("U022"),
            )
            self._dpi_label.grid(
                column=0, row=0, padx=5, pady=5, sticky="nswe"
            )

            self._dpi_entry = BaseEntryClass(
                fr=self.frame_main2,
                color_key="dpi_entry"
            )
            self._dpi_entry.grid(
                column=1, row=0, padx=5, pady=5, sticky="nswe"
            )
            # Initialize DPI entry with current setting
            self._dpi_entry.insert(0, str(self.selected_dpi_value))

            # Process button
            # UI text for Process button
            self._process_button = BaseButton(
                fr=self.frame_main2,
                color_key="process_button",
                text=message_manager.get_ui_message("U023"),
                command=self._on_process_click,
            )
            self._process_button.grid(column=2, row=0, padx=5, pady=5)

            # Canvas for PDF comparison display with fallback for tab_bg
            notebook_theme = ColorThemeManager.get_instance().get_current_theme().get("Notebook", {})
            self.canvas = tk.Canvas(
                self.frame_main3,
                bg=notebook_theme.get("tab_bg", notebook_theme.get("bg", "#1d1d29")),
                relief=tk.SUNKEN,
                bd=2,
            )
            self.canvas.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

            self._create_page_control_frame(self.page_count)
            self._render_comparison_placeholder()

            # Main processing: restore the two image action buttons used by the original main tab workflow.
            self._automatic_execute_button = tk.Button(
                self.frame_main1,
                command=self._on_automatic_image_button_click,
                text=message_manager.get_ui_message("U023"),
                relief=tk.RAISED,
                bd=1,
            )
            self._automatic_execute_button.grid(column=5, row=3, padx=5, pady=8)

            self._custom_execute_button = tk.Button(
                self.frame_main1,
                command=self._on_custom_image_button_click,
                text="Execute",
                relief=tk.RAISED,
                bd=1,
            )
            self._custom_execute_button.grid(column=6, row=3, padx=5, pady=8)

            self._apply_action_button_visual("automatic", False)
            self._apply_action_button_visual("custom", False, refresh_random=True)

            # PDF Save button
            # UI text for Save PDF button
            self._pdf_save_button = BaseButton(
                fr=self.frame_main1,
                color_key="pdf_save_button",
                text=message_manager.get_ui_message("U041"),
                command=self._on_pdf_save_click
            )
            self._pdf_save_button.grid(column=7, row=3, padx=5, pady=8)

            # Widgets setup completed - using message code for multilingual support
            logger.debug(message_manager.get_log_message("L230", "CreateComparisonFileApp"))
        except Exception as e:
            # Failed to setup widgets
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def _on_base_image_color_change(self) -> None:
        """Handle base image color change button click (dummy handler)."""
        pass

    def _on_comparison_image_color_change(self) -> None:
        """Handle comparison image color change button click (dummy handler)."""
        pass

    def _on_base_file_select(self) -> None:
        """Handle base file selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("base_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._base_file_path_entry.path_var.set(file_path)
            self.base_path.set(file_path)
            self.status_var.set("Base PDF route has been prepared. Use Analyze to validate the input side.")
            self._refresh_workspace_state()
            logger.debug(message_manager.get_log_message("L070", file_path))

    def _on_comparison_file_select(self) -> None:
        """Handle comparison file selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("comparison_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U023",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._comparison_file_path_entry.path_var.set(file_path)
            self.comparison_path.set(file_path)
            self.status_var.set("Comparison PDF route has been prepared. Use Analyze to validate the comparison side.")
            self._refresh_workspace_state()
            logger.debug(message_manager.get_log_message("L071", file_path))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("output_folder_path")
        folder_path = ask_folder_dialog(
            initialdir=initial_dir,
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            self.output_path.set(folder_path)
            self.status_var.set("Output folder is ready for later comparison export.")
            if self._has_loaded_workspace_pages():
                self._display_page(self.current_page_index)
            else:
                self._render_comparison_placeholder()
            logger.debug(message_manager.get_log_message("L072", folder_path))

    def _on_pdf_save_click(self) -> None:
        """Handle PDF save button click event."""
        from widgets.pdf_save_dialog import PDFSaveDialog

        if not self._has_loaded_workspace_pages():
            self._show_status_feedback("Run Process before saving the comparison PDF.", False)
            return

        def on_save(filename: str, parent_widget: tk.Widget) -> None:
            output_folder = self.output_path.get() if Path(self.output_path.get()).is_dir() else resolve_initial_dir(self._output_folder_path_entry.path_obj)
            pdf_metadata = self._build_export_metadata()
            handler = PDFExportHandler(
                base_pages=[str(path) for path in self.base_page_paths],
                comp_pages=[str(path) for path in self.comp_page_paths],
                base_transform_data=self.base_transform_data,
                comp_transform_data=self.comp_transform_data,
                output_folder=output_folder,
                pdf_metadata=pdf_metadata,
            )
            handler.export_to_pdf(filename, parent_widget)
        PDFSaveDialog(self, on_save)

    def _build_export_metadata(self) -> Dict[str, Any]:
        """Build PDF export metadata from the currently rendered page set.

        Returns:
            Metadata containing at least ``page_width`` and ``page_height``.
        """
        export_metadata = dict(self.base_pdf_metadata or self.comp_pdf_metadata)
        first_page_path = None
        if self.base_page_paths:
            first_page_path = self.base_page_paths[0]
        elif self.comp_page_paths:
            first_page_path = self.comp_page_paths[0]

        if first_page_path is not None and first_page_path.exists():
            with Image.open(first_page_path) as first_image:
                export_metadata.setdefault("page_width", first_image.width)
                export_metadata.setdefault("page_height", first_image.height)
        return export_metadata

    def _on_process_click(self) -> None:
        """Handle process button click event."""
        try:
            # Main processing: convert the selected PDFs into actual page images and build the live workspace.
            logger.debug(message_manager.get_log_message("L074"))
            base_selected = self._path_points_to_file(self.base_path.get())
            comparison_selected = self._path_points_to_file(self.comparison_path.get())
            if not base_selected and not comparison_selected:
                self._show_status_feedback("Select at least one PDF before processing.", False)
                return

            self.base_page_paths = self._convert_pdf_for_workspace(self.base_path.get(), "base") if base_selected else []
            self.comp_page_paths = self._convert_pdf_for_workspace(self.comparison_path.get(), "comp") if comparison_selected else []
            self.base_pages = [str(path) for path in self.base_page_paths]
            self.comp_pages = [str(path) for path in self.comp_page_paths]
            self.page_count = max(len(self.base_page_paths), len(self.comp_page_paths))
            self.current_page_index = 0
            self._ensure_transform_slots(self.page_count)
            self._create_page_control_frame(self.page_count)
            self._refresh_operation_restriction_state()
            self._setup_mouse_events(self.page_count)
            self._display_page(self.current_page_index)
            self.status_var.set(
                f"Workspace built from rendered pages. base={len(self.base_page_paths)} page(s), comparison={len(self.comp_page_paths)} page(s)."
            )
        except Exception as e:
            # Failed to process files: {error}
            logger.error(message_manager.get_log_message("L080", str(e)))
            self._show_status_feedback(f"Process failed: {e}", False)

    def _on_base_analyze_click(self) -> None:
        """Handle base file analyze button click event."""
        try:
            # Main processing: inspect the selected base PDF without starting the full workspace conversion.
            logger.debug(message_manager.get_log_message("L075"))
            if self._path_points_to_file(self.base_path.get()):
                summary = self._analyze_pdf_path(self.base_path.get(), "base")
                self.status_var.set(
                    f"Base analyze: {summary['page_count']} page(s), copy_protected={summary['copy_protected']}."
                )
                if not self._has_loaded_workspace_pages():
                    self._render_comparison_placeholder()
            else:
                self._show_status_feedback("Base analyze could not find a valid base PDF path.", False)
        except Exception as e:
            # Failed to analyze base file: {error}
            logger.error(message_manager.get_log_message("L081", str(e)))
            self._show_status_feedback(f"Base analyze failed: {e}", False)

    def _on_comparison_analyze_click(self) -> None:
        """Handle comparison file analyze button click event."""
        try:
            # Main processing: inspect the selected comparison PDF without starting the full workspace conversion.
            logger.debug(message_manager.get_log_message("L076"))
            if self._path_points_to_file(self.comparison_path.get()):
                summary = self._analyze_pdf_path(self.comparison_path.get(), "comp")
                self.status_var.set(
                    f"Comparison analyze: {summary['page_count']} page(s), copy_protected={summary['copy_protected']}."
                )
                if not self._has_loaded_workspace_pages():
                    self._render_comparison_placeholder()
            else:
                self._show_status_feedback("Comparison analyze could not find a valid comparison PDF path.", False)
        except Exception as e:
            # Failed to analyze comparison file: {error}
            logger.error(message_manager.get_log_message("L082", str(e)))
            self._show_status_feedback(f"Comparison analyze failed: {e}", False)

    def _on_execute_click(self) -> None:
        """Handle execute button click event."""
        if not self._has_loaded_workspace_pages():
            self._on_process_click()
            return

        self._display_page(self.current_page_index)
        self.status_var.set(
            "Execute refreshed the live comparison display from the converted workspace pages."
        )
