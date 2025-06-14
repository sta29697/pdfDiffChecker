# PDF Diff Checker - File Structure and Architecture

## Project Overview

PDF Diff Checker is an application for displaying differences between two PDF files. This document explains the file structure and the role of each component in the application.

## Directory Structure

```bash
pdfDiffChecker/
├── configurations/     # Configuration files and message codes
├── controllers/        # Event handling and controllers
├── docs/               # Documentation and ER diagrams
├── images/             # Images used in the application
├── logs/               # Log files
├── models/             # Data models and business logic
├── tests/              # Test code
├── themes/             # Color themes
├── utils/              # Utility functions
├── views/              # UI views
├── widgets/            # Reusable UI components
└── main.py             # Application entry point
```

## Detailed File Structure with Classes and Methods

```bash
pdfDiffChecker/
├── configurations/
│   ├── message_manager.py
│   │   └── MessageManager class
│   │       ├── get_message(code, *args) - Get message based on code
│   │       ├── get_log_message(code, *args) - Get log message
│   │       └── set_language(lang) - Change language setting
│   ├── tool_settings.py - Font settings and general configuration values
│   └── user_setting_manager.py
│       └── UserSettingManager class
│           ├── load_settings() - Load settings from JSON
│           ├── save_settings() - Save settings to JSON
│           └── update_setting(section, key, value) - Update setting value
├── controllers/
│   ├── color_theme_manager.py
│   │   └── ColorThemeManager class
│   │       ├── load_theme(theme_name) - Load theme
│   │       ├── apply_theme(widget) - Apply theme to widget
│   │       └── change_theme(theme_name) - Change theme
│   ├── event_bus.py
│   │   └── EventBus class
│   │       ├── subscribe(event_name, callback) - Subscribe to event
│   │       ├── publish(event_name, *args, **kwargs) - Publish event
│   │       └── unsubscribe(event_name, callback) - Unsubscribe
│   ├── file2png_by_page.py
│   │   └── PDFConverter class
│   │       ├── convert_pdf_to_png(pdf_path, output_dir) - Convert PDF to PNG
│   │       ├── extract_metadata(pdf_path) - Extract metadata from PDF
│   │       └── update_progress(progress, page, total) - Update progress
│   ├── image_operations.py
│   │   └── ImageOperations class
│   │       ├── __init__(self, canvas: tk_Canvas, image_id: int, pil_image: Image.Image) -> None - Initialize the ImageOperations
│   │       ├── move(self, dx: int, dy: int) -> None - Move the image by the specified amount
│   │       ├── set_rotation_center(self, x: int, y: int) -> None - Set the center point for rotation
│   │       ├── rotate(self, angle_degrees: float) -> None - Rotate the image by the specified angle
│   │       ├── zoom(self, scale_factor: float) -> None - Zoom the image by the specified factor
│   │       ├── update_image(self, new_image: Image.Image) -> None - Update the image on the canvas
│   │       ├── flip_horizontal(self) -> None - Flip the image horizontally using PIL's transpose method
│   │       └── flip_vertical(self) -> None - Flip the image vertically using PIL's transpose method
│   ├── mouse_event_handler.py
│   │   └── MouseEventHandler class
│   │       ├── __init__(self, layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]], current_page_index: int, visible_layers: Dict[int, bool], on_transform_update: Callable[[], None]) - Initialize handler
│   │       ├── attach_to_canvas(self, canvas: tk.Canvas) - Attach to a canvas for visual feedback
│   │       ├── update_state(self, current_page_index: int, visible_layers: Dict[int, bool]) - Update state (e.g., on page change)
│   │       ├── set_current_page_index(self, page_index: int) - Set the current page index
│   │       ├── set_visible_layers(self, visible_layers: Dict[int, bool]) - Set the visibility of layers
│   │       ├── get_current_transform_for_layer(self, layer_id: int) -> Optional[Tuple[float, float, float, float]] - Get current transformation for a layer
│   │       ├── on_mouse_down(self, event: tk.Event) -> str - Handle mouse button press
│   │       ├── on_mouse_drag(self, event: tk.Event) -> None - Handle mouse drag
│   │       ├── on_mouse_up(self, event: tk.Event) -> None - Handle mouse button release
│   │       ├── on_mouse_move(self, event: tk.Event) -> None - Handle mouse movement (updates cursor position)
│   │       ├── on_mouse_wheel(self, event: tk.Event) -> None - Handle mouse wheel for zooming
│   │       ├── on_key_press(self, event: tk.Event) -> Optional[str] - Handle key press events (shortcuts)
│   │       ├── on_key_release(self, event: tk.Event) -> None - Handle key release events (Ctrl key state)
│   │       ├── on_rotate_right(self, event: tk.Event | None = None) -> str | None - Handle Ctrl+R for 90° clockwise rotation
│   │       ├── on_rotate_left(self, event: tk.Event | None = None) -> str | None - Handle Ctrl+L for 90° counter-clockwise rotation
│   │       ├── on_flip_vertical(self, event: tk.Event | None = None) -> str | None - Handle Ctrl+V for vertical flip
│   │       ├── on_flip_horizontal(self, event: tk.Event | None = None) -> str | None - Handle Ctrl+H for horizontal flip
│   │       ├── on_reset_transform(self, event: tk.Event | None = None) -> str | None - Handle Ctrl+B to reset transformations for the current page
│   │       ├── toggle_shortcut_guide(self, event: Optional[tk.Event] = None) -> str - Toggle shortcut guide visibility
│   │       ├── show_guidance_text(self, text: str, duration: float = 2.0, is_rotation: bool = False, tag: Optional[str] = None) -> None - Show guidance text on canvas
│   │       ├── hide_guidance_text(self, event: Optional[tk.Event] = None) -> None - Hide any displayed guidance text
│   │       ├── show_notification(self, message: str, duration: float = 2.0, warning: bool = False) -> None - Show transient notification
│   │       ├── hide_notification(self) -> None - Hide the notification text
│   │       ├── show_feedback_circle(self, x: float, y: float, is_rotating: bool) -> None - Show feedback circle at position
│   │       ├── hide_feedback_circle(self) -> None - Hide any displayed feedback circle
│   │       ├── clear_feedback(self) -> None - Clear all visual feedback elements (guidance, notification, circle)
│   │       ├── _show_shortcut_guide(self, event: Optional[tk.Event] = None) -> None - (Private) Show shortcut guide on canvas
│   │       ├── _hide_shortcut_guide(self, event: Optional[tk.Event] = None) -> None - (Private) Hide the shortcut guide
│   │       ├── _exit_rotation_mode(self) -> None - (Private) Exit rotation mode and clean up visual elements
│   │       ├── _process_wheel_zoom(self, event: tk.Event) -> None - (Private) Process zoom for all visible layers
│   │       ├── __rotate_by_angle(self, angle_degrees: float) -> None - (Private) Rotate all visible layers by a specified angle
│   │       ├── __process_pending_rotation(self) -> None - (Private) Process pending rotation updates if any
│   │       ├── __cancel_all_timers(self) -> None - (Private) Cancel all pending hide/check timers
│   │       ├── __force_display_rotation_elements(self) -> None - (Private) Force display of rotation-related visual elements
│   │       ├── __schedule_ctrl_check_timer(self) -> None - (Private) Schedule timer to check Ctrl key state for rotation mode
│   │       └── __check_ctrl_key_state(self) -> None - (Private) Check if Ctrl key is still pressed to maintain rotation mode
│   ├── transform_manager.py
│   │   └── TransformationManager class
│   │       ├── __init__(self) -> None - Initialize the TransformationManager
│   │       ├── get_transform_data(self, layer_id: int, page_index: int) -> Tuple[float, float, float, float] - Get transformation data (rotation, x, y, scale)
│   │       ├── set_transform_data(self, layer_id: int, page_index: int, rotation: float, tx: float, ty: float, scale: float) -> None - Set transformation data
│   │       ├── update_transform_data(self, layer_id: int, page_index: int, rotation: Optional[float] = None, tx: Optional[float] = None, ty: Optional[float] = None, scale: Optional[float] = None) -> None - Update specific transformation parameters
│   │       ├── reset_transform(self, layer_id: int, page_index: int) -> None - Reset transformation data for a specific layer and page
│   │       ├── reset_all_transforms(self) -> None - Reset all transformation data to default values
│   │       ├── set_current_page_index(self, page_index: int) -> None - Set current page index
│   │       ├── get_current_page_index(self) -> int - Get current page index
│   │       ├── add_layer(self, layer_id: int, transform_data: Optional[List[Tuple[float, float, float, float]]] = None) -> None - Add a new display layer
│   │       ├── remove_layer(self, layer_id: int) -> None - Remove a display layer
│   │       └── get_all_transform_data(self) -> Dict[int, List[Tuple[float, float, float, float]]] - Get all transformation data
│   └── widgets_tracker.py
│       └── WidgetsTracker class
│           ├── register_widget(widget) - Register widget
│           ├── unregister_widget(widget) - Unregister widget
│           └── apply_theme_to_all(theme) - Apply theme to all widgets
├── models/
│   └── file_info.py
│       ├── FilePathInfo class - Hold file path information
│       └── FolderPathInfo class - Hold folder path information
├── themes/
│   ├── coloring_theme_interface.py
│   │   └── ColoringThemeIF class - Theme interface
│   ├── dark.json - Dark theme settings
│   ├── light.json - Light theme settings
│   └── pastel.json - Pastel theme settings
├── utils/
│   ├── baloon_message.py
│   │   └── BalloonMessage class - Display balloon message
│   ├── log_throttle.py
│   │   └── LogThrottle class - Limit log output
│   ├── shortcut_binding.py
│   │   ├── bind_shortcuts(root, patterns, handler) - Bind multiple shortcut patterns
│   │   └── unbind_shortcuts(root, patterns) - Unbind multiple shortcut patterns
│   └── utils.py - General utility functions
├── views/
│   ├── description.py
│   │   └── DescriptionTab class - Description tab
│   ├── file_extension_tab.py
│   │   └── FileExtensionTab class - File extension tab
│   ├── licenses.py
│   │   └── LicensesTab class - Licenses tab
│   └── pdf_ope_tab.py
│       └── PDFOperationApp class - PDF operation tab
│           ├── _setup_ui() - Setup the user interface
│           ├── _on_base_file_select() - Handle base file selection event
│           ├── _on_output_folder_select() - Handle output folder selection
│           ├── _setup_drag_and_drop() - Setup drag and drop functionality
│           ├── _load_and_display_pdf(file_path) - Load and display PDF file
│           ├── _display_page(page_index) - Display specified page of PDF
│           ├── _initialize_mouse_handler() - Initialize mouse event handler
│           ├── _rebind_mouse_wheel() - Rebind mouse wheel events
│           ├── _on_next_page() - Go to next page
│           ├── _on_prev_page() - Go to previous page
│           ├── _on_page_entry(event) - Handle page entry event
│           ├── _setup_mouse_events() - Set up mouse events for canvas
│           ├── _reset_transform() - Reset transformation for current page
│           ├── _go_to_first_page() - Go to first page of document
│           ├── _go_to_last_page() - Go to last page of document
│           ├── _on_drop(file_path) - Handle file drop event
│           ├── _show_drop_feedback(drop_data, is_valid) - Show drop feedback
│           ├── _create_page_control_frame(page_count) - Create page control frame
│           ├── _on_transform_update() - Callback when transform data updated
│           ├── update_image_transform(rotation, tx, ty, scale) - Update image transformation
│           ├── _on_insert_blank_page() - Insert blank page after current page
│           ├── apply_theme_color(theme_data) - Apply theme colors to widgets
│           ├── _config_widget(theme_settings) - Configure widget theme settings
│           └── _on_complete_edit() - Complete editing and export PDF
├── widgets/
│   ├── base_page_change_button.py
│   │   └── BasePageChangeButton class - Page change button
│   ├── base_path_entry.py
│   │   └── BasePathEntry class - Path input field
│   ├── base_path_select_button.py
│   │   └── BasePathSelectButton class - Path selection button
│   ├── base_tab_widgets.py
│   │   └── BaseTabWidgets class - Base class for tab widgets
│   ├── color_theme_change_button.py
│   │   └── ColorThemeChangeButton class - Theme change button
│   └── progress_window.py
│       └── ProgressWindow class - Progress display window
└── main.py - Application entry point
    └── CreateComparisonFileApp class - Main application
```

## Key Components

### Controllers

#### `transform_manager.py`

Manages transformation data for display layers (base file and comparison file), providing a centralized interface for rotation, scaling, translation, and flipping operations. This controller is used by the MouseEventHandler to maintain transformation state across page navigation.

```python
class TransformationManager:
    def __init__(self) -> None:
        # Initialize the TransformationManager with empty data.
    
    def get_transform_data(self, layer_id: int, page_index: int) -> Tuple[float, float, float, float, bool, bool]:
        # Get transformation data (rotation, x, y, scale, flip_x, flip_y) for a specific layer and page.
        # Default is (0.0, 0.0, 0.0, 1.0, False, False) if not found.
    
    def set_transform_data(self, layer_id: int, page_index: int, rotation: float, 
                           tx: float, ty: float, scale: float,
                           flip_x: bool = False, flip_y: bool = False) -> None:
        # Set transformation data for a specific layer and page including flip flags.
    
    def update_transform_data(self, layer_id: int, page_index: int, rotation: Optional[float] = None,
                             tx: Optional[float] = None, ty: Optional[float] = None,
                             scale: Optional[float] = None, flip_x: Optional[bool] = None,
                             flip_y: Optional[bool] = None) -> None:
        # Update specific transformation parameters for a layer and page including flip flags.
        # If a parameter is None, its current value is kept.
    
    def reset_transform(self, layer_id: int, page_index: int) -> None:
        # Reset transformation data to default values
        
    def reset_all_transforms(self) -> None:
        # Reset all transformation data for all layers and pages to default values
        
    def set_current_page_index(self, page_index: int) -> None:
        # Set current page index
        
    def get_current_page_index(self) -> int:
        # Get current page index
        
    def add_layer(self, layer_id: int, transform_data: Optional[List[Tuple[float, float, float, float, bool, bool]]] = None) -> None:
        # Add a new layer with optional transformation data including flip flags
        
    def remove_layer(self, layer_id: int) -> None:
        # Remove a layer and its transformation data
        
    def get_all_transform_data(self) -> Dict[int, List[Tuple[float, float, float, float, bool, bool]]]:
        # Get all transformation data for all layers including flip flags
```

#### `mouse_event_handler.py`

Provides comprehensive mouse event handling and transformation operations for PDF/TIFF display layers. Works with TransformationManager to manage rotation, scaling, and translation operations. Handles user interactions such as dragging, rotation mode (Ctrl+drag), and mouse wheel zooming, providing visual feedback during operations.

```python
class MouseEventHandler:
    def __init__(
            self,
            layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]],
            current_page_index: int,
            visible_layers: Dict[int, bool],
            on_transform_update: Callable[[], None],
        ) -> None:
        # Initialize with transformation data, page index, visibility, and update callback
    
    def on_mouse_down(self, event: tk.Event) -> None:
        # Handle mouse button press events
    
    def on_mouse_drag(self, event: tk.Event) -> None:
        # Handle mouse drag events (move operations)
    
    def on_mouse_up(self, event: tk.Event) -> None:
        # Handle mouse button release events
    
    def on_mouse_wheel(self, event: Any, single_layer_data: Optional[List[Any]] = None) -> None:
        # Handle mouse wheel events for zooming
    
    def __rotate_by_angle(self, angle: float) -> None:
        # Rotate all visible layers by the specified angle
    
    def on_rotate_right(self, event: Optional[tk.Event] = None) -> str:
        # Handle 90° clockwise rotation
    
    def on_rotate_left(self, event: Optional[tk.Event] = None) -> str:
        # Handle 90° counterclockwise rotation
    
    def on_flip_vertical(self, event: Optional[tk.Event] = None) -> str:
        # Handle vertical flip operation
    
    def on_flip_horizontal(self, event: Optional[tk.Event] = None) -> str:
        # Handle horizontal flip operation
    
    def on_reset_transform(self, event: Optional[tk.Event] = None) -> str:
        # Reset all transformations to default values
```

#### `drag_and_drop_file.py`

ファイルのドラッグ＆ドロップ機能を提供します。

```python
class DragAndDropHandler:
    def __init__(self, target_widget, on_drop_callback, on_feedback_callback=None):
        # ドラッグ＆ドロップ機能の初期化
    
    def on_drop(self, event):
        # ファイルがドロップされた時の処理
```

### Views

#### `pdf_ope_tab.py`

PDFファイルの操作タブを提供します。PDFの表示、ズーム、ページ移動などの機能を実装しています。マウスイベント処理は`MouseEventHandler`クラスを直接使用しています。

```python
class PDFOperationApp(ttk.Frame, ColoringThemeIF):
    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        # PDFビューアーの初期化
        # MouseEventHandlerインスタンスを作成
        self._initialize_mouse_handler()
    
    def _initialize_mouse_handler(self) -> None:
        # MouseEventHandlerインスタンスを作成
        self.mouse_handler = MouseEventHandler(self)
    
    def _display_page(self, page_index: int) -> None:
        # 指定されたページを表示
        # 回転、拡大縮小、移動などの変換を適用
    
    def _setup_mouse_events(self) -> None:
        # キャンバスにマウスイベントをバインド
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
    
    def _on_transform_update(self) -> None:
        # 変換（回転、拡大縮小、移動）が更新された時に呼び出される
        # 現在のページを再表示
```

### Widgets

#### `page_control_frame.py`

PDFページのナビゲーションコントロールを提供します。

```python
class PageControlFrame(ttk.Frame):
    def __init__(self, parent, color_key, base_pages, comp_pages, 
                 base_transform_data, comp_transform_data, 
                 visualized_image, page_amount_limit, 
                 on_prev_page, on_next_page, on_insert_blank, 
                 on_export, on_page_entry):
        # ページコントロールフレームの初期化
    
    def update_page_label(self, current_page_index: int, page_count: int) -> None:
        # ページラベルを更新
```

### Utils

#### `log_throttle.py`

ログメッセージの頻度を制限するためのユーティリティクラスを提供します。

```python
class LogThrottle:
    def __init__(self, min_interval: float = 1.0):
        # ログスロットリングの初期化
    
    def should_log(self, key: str, min_interval: float = None) -> bool:
        # 指定されたキーに対してログを出力すべきかどうかを判断
```

## データフロー

1. ユーザーがPDFファイルを選択または操作すると、対応するイベントが発生します。
2. コントローラー（`mouse_event_handler.py`など）がイベントを処理します。
3. モデル（`models/`ディレクトリ内）がデータ処理を行います。
4. ビュー（`views/`ディレクトリ内）が更新され、ユーザーに結果が表示されます。

## 主要な機能

1. **PDFの比較**: 2つのPDFファイルの差分を表示
2. **PDFの操作**: 回転、拡大縮小、移動などの操作
3. **ページナビゲーション**: ページ間の移動
4. **テーマ変更**: アプリケーションのカラーテーマを変更
5. **ファイル操作**: ファイルの拡張子変更、サイズ変更など

## 改善点と今後の課題

1. マウス操作の集約: マウス関連の操作を`controllers/mouse_event_handler.py`に集約
2. テーマ変更機能の強化
3. パフォーマンスの最適化
4. エラーハンドリングの改善
