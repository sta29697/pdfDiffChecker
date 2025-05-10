from __future__ import annotations
from logging import getLogger
import tkinter as tk
from typing import Optional, Any, List, Dict
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from utils.utils import get_resource_path, resolve_initial_dir

from configurations.message_manager import get_message_manager
from widgets.base_button import BaseButton
from widgets.base_button_image_change_toggle_button import BaseButtonImageChangeToggleButton
from widgets.base_label_class import BaseLabelClass
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_file_analyze_button import BaseFileAnalyzeButton
from widgets.base_image_color_change_button import BaseImageColorChangeButton
from widgets.color_theme_change_button import ColorThemeChangeButton  # type: ignore
from widgets.progress_window import ProgressWindow
from widgets.language_select_combobox import LanguageSelectCombo
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets

from configurations.user_setting_manager import UserSettingManager
from controllers.image_sw_paths import ImageSwPaths
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
        self.settings = settings
        self.master = master
        self.file_operation_status: bool = True
        self.selected_dpi_value: int = int(self.settings.get_setting("setted_dpi", "default"))
        self.base_widgets = BaseTabWidgets(self)

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
        # Completed main tab init
        logger.debug(message_manager.get_log_message("L244"))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings."""
        pass

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply theme to this tab and its widgets."""
        pass

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
            # Set Frame0 height even smaller for more compact layout
            self.frame_main0 = tk.Frame(self, relief=tk.RIDGE, borderwidth=1, height=25)
            self.frame_main0.grid(row=0, column=0, padx=2, pady=0, sticky="new")
            # Configure frame_main0 to right-align its contents
            self.frame_main0.columnconfigure(0, weight=1)  # Make first column expandable
            self.frame_main0.columnconfigure(1, weight=0)  # Keep second column fixed size
            self.frame_main0.grid_propagate(False)  # Fix the height

            self.frame_main1 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main1.grid(row=1, column=0, padx=5, pady=1, sticky="nsew")

            self.frame_main2 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main2.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

            self.frame_main3 = tk.Frame(self, relief=tk.RIDGE, borderwidth=2)
            self.frame_main3.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")
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
            lang_combo.grid(row=0, column=0, padx=1, pady=1, sticky="e")

            # Create theme change button
            # UI text for Change Theme button
            self._color_theme_change_btn = ColorThemeChangeButton(
                fr=self.frame_main0,
                color_theme_change_btn_status=False,
                text=message_manager.get_ui_message("U025"),
            )
            self._color_theme_change_btn.grid(
                row=0, column=1, padx=1, pady=0, sticky="e"
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

            # Base image color change button
            self._base_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="base_image_color_change_button",
                command=self._on_base_image_color_change,
                width=2,
            )
            self._base_image_color_change_btn.grid(column=2, row=1, padx=2, pady=2)

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
            self._base_file_path_button.grid(column=3, row=1, padx=5, pady=8)

            # Base file analyze button
            # UI text for Analyze Base File button
            self._base_file_analyze_btn = BaseFileAnalyzeButton(
                fr=self.frame_main1,
                color_key="base_file_analyze_button",
                text=message_manager.get_ui_message("U016"),
                command=self._on_base_analyze_click,
            )
            self._base_file_analyze_btn.grid(column=4, row=1, padx=5, pady=8)

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
                column=1, row=2, padx=5, pady=8, sticky="we"
            )

            # Comparison image color change button
            self._comparison_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="comparison_image_color_change_button",
                command=self._on_comparison_image_color_change,
                width=2,
            )
            self._comparison_image_color_change_btn.grid(column=2, row=2, padx=2, pady=2)

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
            self._comparison_file_path_button.grid(column=2, row=2, padx=5, pady=8)

            # Comparison file analyze button
            # UI text for Analyze Comparison File button
            self._comparison_file_analyze_btn = BaseFileAnalyzeButton(
                fr=self.frame_main1,
                color_key="comparison_file_analyze_button",
                text=message_manager.get_ui_message("U017"),
                command=self._on_comparison_analyze_click,
            )
            self._comparison_file_analyze_btn.grid(column=3, row=2, padx=5, pady=8)

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
                column=1, row=3, padx=5, pady=8, sticky="we"
            )

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
            self._output_folder_path_button.grid(column=2, row=3, padx=5, pady=8)

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

            # Progress window
            self._progress_window = ProgressWindow(
                parent=self.frame_main2,
            )
            # Calculate position relative to parent
            parent_x = self.frame_main2.winfo_rootx()
            parent_y = self.frame_main2.winfo_rooty()
            parent_width = self.frame_main2.winfo_width()
            parent_height = self.frame_main2.winfo_height()

            # Set window position
            self._progress_window.geometry(f"+{parent_x + parent_width - 200}+{parent_y + parent_height // 2}")

            # Canvas for PDF comparison display with fallback for tab_bg
            notebook_theme = ColorThemeManager.get_instance().get_current_theme().get("Notebook", {})
            self.canvas = tk.Canvas(
                self.frame_main3,
                bg=notebook_theme.get("tab_bg", notebook_theme.get("bg", "#1d1d29")),
                relief=tk.SUNKEN,
                bd=2,
            )
            self.canvas.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

            # Execute button
            self._execute_button = BaseButtonImageChangeToggleButton(
                parent=self.frame_main1,
                command=self._on_execute_click,
                image_path=get_resource_path("images/execute_button.png")
            )
            self._execute_button.grid(column=3, row=3, padx=5, pady=8)

            # PDF Save button
            # UI text for Save PDF button
            self._pdf_save_button = BaseButton(
                fr=self.frame_main1,
                color_key="pdf_save_button",
                text=message_manager.get_ui_message("U041"),
                command=self._on_pdf_save_click
            )
            self._pdf_save_button.grid(column=4, row=3, padx=5, pady=8)

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
        file_path = ask_file_dialog(
            initialdir=resolve_initial_dir(self._base_file_path_entry.path_obj),
            title_code="U022",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._base_file_path_entry.path_var.set(file_path)
            logger.debug(message_manager.get_log_message("L070", file_path))

    def _on_comparison_file_select(self) -> None:
        """Handle comparison file selection event using common dialog."""
        file_path = ask_file_dialog(
            initialdir=resolve_initial_dir(self._comparison_file_path_entry.path_obj),
            title_code="U023",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._comparison_file_path_entry.path_var.set(file_path)
            logger.debug(message_manager.get_log_message("L071", file_path))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection event using common dialog."""
        folder_path = ask_folder_dialog(
            initialdir=resolve_initial_dir(self._output_folder_path_entry.path_obj),
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            logger.debug(message_manager.get_log_message("L072", folder_path))

    def _on_pdf_save_click(self) -> None:
        """Handle PDF save button click event."""
        from widgets.pdf_save_dialog import PDFSaveDialog
        from controllers.pdf_export_handler import PDFExportHandler
        # This would normally gather the necessary data for export
        def on_save(filename: str, parent_widget: tk.Widget) -> None:
            # Dummy data for demonstration; replace with actual data gathering logic
            base_pages: List[Any] = []
            comp_pages: List[Any] = []
            base_transform_data: List[Any] = []
            comp_transform_data: List[Any] = []
            output_folder = resolve_initial_dir(self._output_folder_path_entry.path_obj)
            pdf_metadata: Dict[str, Any] = {}
            handler = PDFExportHandler(
                base_pages=base_pages,
                comp_pages=comp_pages,
                base_transform_data=base_transform_data,
                comp_transform_data=comp_transform_data,
                output_folder=output_folder,
                pdf_metadata=pdf_metadata,
            )
            handler.export_to_pdf(filename, parent_widget)
        PDFSaveDialog(self, on_save)

    def _on_process_click(self) -> None:
        """Handle process button click event."""
        try:
            # Process button clicked
            logger.debug(message_manager.get_log_message("L074"))
            # Process implementation will be added later
            pass
        except Exception as e:
            # Failed to process files: {error}
            logger.error(message_manager.get_log_message("L080", str(e)))

    def _on_base_analyze_click(self) -> None:
        """Handle base file analyze button click event."""
        try:
            # Base file analysis started
            logger.debug(message_manager.get_log_message("L075"))
            # Base file analysis implementation will be added later
            pass
        except Exception as e:
            # Failed to analyze base file: {error}
            logger.error(message_manager.get_log_message("L081", str(e)))

    def _on_comparison_analyze_click(self) -> None:
        """Handle comparison file analyze button click event."""
        try:
            # Comparison file analysis started
            logger.debug(message_manager.get_log_message("L076"))
            # Comparison file analysis implementation will be added later
            pass
        except Exception as e:
            # Failed to analyze comparison file: {error}
            logger.error(message_manager.get_log_message("L082", str(e)))

    def _on_execute_click(self) -> None:
        """Handle execute button click event."""
        # TODO: Implement execution logic
        pass
