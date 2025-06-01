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
│   ├── mouse_event_handler.py
│   │   └── MouseEventHandler class
│   │       ├── update_state(current_page_index, visible_layers) - Update state
│   │       ├── add_layer(layer_id, init_transform_data) - Add a new layer
│   │       ├── remove_layer(layer_id) - Remove a layer
│   │       ├── attach_to_canvas(canvas_widget) - Attach to a canvas for visual feedback
│   │       ├── on_key_press(event) - Handle key press events
│   │       ├── on_mouse_down(event) - Handle mouse button press
│   │       ├── on_mouse_drag(event) - Handle mouse drag
│   │       ├── on_mouse_up(event) - Handle mouse button release
│   │       ├── __force_display_rotation_elements() - Force display of rotation-related visual elements
│   │       ├── __schedule_ctrl_check_timer() - Schedule timer to check Ctrl key state
│   │       ├── __check_ctrl_key_state() - Check if Ctrl key is still pressed
│   │       ├── __exit_rotation_mode() - Exit rotation mode and clean up visual elements
│   │       ├── on_mouse_move(event) - Handle mouse movement events
│   │       ├── clear_feedback() - Clear all visual feedback elements
│   │       ├── hide_feedback_circle() - Hide any displayed feedback circle
│   │       ├── hide_guidance_text() - Hide any displayed guidance text
│   │       ├── on_mouse_wheel(event, single_layer_data) - Handle mouse wheel for zooming
│   │       ├── _process_wheel_zoom(event, transform_data, page_index, callback_function) - Process zoom for single layer
│   │       ├── _process_wheel_zoom_multi_layer(event) - Process zoom for multiple layers
│   │       ├── __rotate_by_angle(angle) - Rotate all visible layers by angle
│   │       ├── on_rotate_right(event) - Handle right rotation (90°)
│   │       ├── on_rotate_left(event) - Handle left rotation (90°)
│   │       ├── on_flip_vertical(event) - Handle vertical flip
│   │       ├── on_flip_horizontal(event) - Handle horizontal flip
│   │       ├── on_reset_transform(event) - Reset transformations
│   │       ├── show_feedback_circle(x, y, is_rotating) - Show feedback circle at position
│   │       ├── show_guidance_text(message, is_rotation) - Show guidance text on canvas
│   │       ├── show_notification(message, duration) - Show transient notification
│   │       └── hide_notification() - Hide the notification text
│   ├── transform_manager.py
│   │   └── TransformationManager class
│   │       ├── get_transform_data(layer_id, page_index) - Get transformation data
│   │       ├── set_transform_data(layer_id, page_index, rotation, tx, ty, scale) - Set transformation data
│   │       ├── update_transform_data(layer_id, page_index, rotation, tx, ty, scale) - Update transformation data
│   │       ├── reset_transform(layer_id, page_index) - Reset transformation data
│   │       ├── reset_all_transforms() - Reset all transformation data
│   │       ├── set_current_page_index(page_index) - Set current page index
│   │       ├── get_current_page_index() - Get current page index
│   │       ├── add_layer(layer_id, transform_data) - Add a new layer
│   │       ├── remove_layer(layer_id) - Remove a layer
│   │       └── get_all_transform_data() - Get all transformation data
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

Manages transformation data for PDF layers, providing a centralized interface for rotation, scaling, and translation operations.

```python
class TransformationManager:
    def __init__(self, layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]], 
                 current_page_index: int, on_transform_update: Callable[[], None]):
        # Initialize transformation data, current page index, and update callback
    
    def get_transform_data(self, layer_id: int, page_index: int) -> Tuple[float, float, float, float]:
        # Get transformation data (rotation, tx, ty, scale) for a specific layer and page
    
    def update_transform_data(self, layer_id: int, page_index: int, rotation: Optional[float] = None,
                             tx: Optional[float] = None, ty: Optional[float] = None,
                             scale: Optional[float] = None, scale_x: Optional[float] = None,
                             update_callback: bool = True) -> None:
        # Update transformation data for a specific layer and page
    
    def reset_transform(self, layer_id: int, page_index: int) -> None:
        # Reset transformation data to default values
```

#### `mouse_event_handler.py`

Provides comprehensive mouse event handling and transformation operations for PDF layers. Uses TransformationManager to manage transformation data.

```python
class MouseEventHandler:
    def __init__(self, layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]], 
                 current_page_index: int, visible_layers: Dict[int, bool], 
                 on_transform_update: Callable[[], None]):
        # Initialize transformation manager, visible layers, and feedback elements
    
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
