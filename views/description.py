from __future__ import annotations

from logging import getLogger
from typing import Dict, Any, Optional
import tkinter as tk
from tkinter import scrolledtext

from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager
from widgets.base_tab_widgets import BaseTabWidgets

logger = getLogger(__name__)

message_manager = get_message_manager()

# Application description text in Japanese
widget_description = """
アプリケーション説明
############ PDF比較タブ ################
PDFファイルを比較し、差分を確認するためのタブです。
以下の機能があります：
1. ベースPDFと比較PDFの選択
2. PDFの内容を単色グレースケール化と透明度を変更して表示と比較
3. DPI設定による画質調整
4. ページ移動と表示制御

############ PDF操作タブ ################
PDFファイルの操作を行うためのタブです。
以下の機能があります：
1. ドラッグアンドドロップしたPDFファイルをマウス操作で移動、回転させる。
　　移動：左クリックを保持したままドラッグ
　　回転：Ctrl＋左クリックで回転の中心を指定し、左クリックを離した場所で確定。
  　　　　その後、左クリックを別の場所で保持したままドラッグ
    移動、回転はエントリへの数値入力でも可能
2. PDFをページ毎に分割
3. 上記2の後に、PDFのページを入れ替えての結合

############# 画像形式変換・サイズ変更 ################
画像ファイルの形式変換とサイズ変更を行うためのタブです。
以下の機能があります：
1. 画像形式の変換（PNG, JPEG, TIFF等）
2. 画像サイズの変更
3. DPI設定の変更

############# 多言語化対応ガイドライン ################
このアプリケーションは日本語と英語の多言語対応を実装しています。
開発者向けのガイドラインは以下の通りです：

【メッセージコード命名規則】
- Lxxx: ログメッセージ用 (例: L001, L123)
- Mxxx: メッセージボックス・通知用 (例: M001, M222)
- Uxxx: UIラベル・省略表示用 (例: U001, U333)
- Exxx: エラーコード用 (例: E001, E444)

【ログメッセージのプレフィックス】
以下の機能領域ごとに必ずプレフィックスを付与します：
- [SYS]: システム全般
- [UI]: ユーザーインターフェース
- [WIDGET]: ウィジェット関連
- [THEME]: テーマ関連
- [FILE]: ファイル操作関連
- [PDF]: PDF操作関連
- [IMG]: 画像処理関連

【エラーメッセージ表記】
エラーメッセージは以下の形式で統一しています：
「[xxx] ...でエラーが発生しました: {0}」

【初期化フェーズの言語】
- message_manager初期化前: 英語固定
- 初期化後: ユーザー設定言語（デフォルト日本語）

【コメント・docstring】
- すべて英語で記述

【注意点】
- ハードコードされたメッセージは使用せず、必ずmessage_codes.jsonに定義する
- UI省略名はウィジェット幅に合わせて短縮表記を使用
- message_managerを使用する前に必ず初期化されていることを確認する
"""

# Dictionary of description texts by language code
description_texts = {
    "en": """
Application Description
################ PDF Comparison Tab ################
This tab is used to compare PDF files and check differences.
Features include:
1. Selection of base PDF and comparison PDF
2. Display and comparison by converting PDFs to monochrome grayscale with adjustable transparency
3. Image quality adjustment via DPI settings
4. Page navigation and display controls

################ PDF Operation Tab ################
This tab is for PDF file manipulation.
Features include:
1. Move and rotate PDF files using mouse operations after drag and drop
   Move: Hold left click and drag
   Rotate: Press Ctrl + left click to specify the center of rotation, then release the left click to confirm.
          Afterwards, hold left click at a different location and drag
   Moving and rotating can also be done by entering numeric values in the entry fields
2. Split PDF files by page
3. Combine PDF pages after operation 2, with the ability to rearrange pages

################ Image Format Conversion & Resize ################
This tab is for image file format conversion and size adjustment.
Features include:
1. Image format conversion (PNG, JPEG, TIFF, etc.)
2. Image size adjustment
3. DPI settings modification

################ Multilingual Support Guidelines ################
This application implements multilingual support for Japanese and English.
Development guidelines are as follows:

【Message Code Naming Convention】
- Lxxx: For log messages (e.g., L001, L123)
- Mxxx: For message boxes and notifications (e.g., M001, M222)
- Uxxx: For UI labels and abbreviated displays (e.g., U001, U333)
- Exxx: For error codes (e.g., E001, E444)

【Log Message Prefixes】
The following prefixes must be used for each functional area:
- [SYS]: General system
- [UI]: User interface
- [WIDGET]: Widget related
- [THEME]: Theme related
- [FILE]: File operation related
- [PDF]: PDF operation related
- [IMG]: Image processing related

【Error Message Format】
Error messages are standardized in the following format:
"[xxx] Error occurred in ...: {0}"

【Initialization Phase Language】
- Before message_manager initialization: Fixed to English
- After initialization: User-configured language (default: Japanese)

【Comments and Docstrings】
- All should be written in English

【Important Notes】
- Do not use hardcoded messages; always define them in message_codes.json
- Use abbreviated notation for UI labels to fit widget widths
- Always ensure message_manager is initialized before using it
""",
    "ja": widget_description
}


class DescriptionApp(tk.Frame, ColoringThemeIF):
    """Application description tab.

    This class provides a scrollable text widget that displays application
    description and usage instructions in Japanese.

    Attributes:
        root (Optional[tk.Widget]): Parent widget
        base_widgets (BaseTabWidgets): Base tab widget container
        description_text (scrolledtext.ScrolledText): Scrollable text widget for description
    """

    def __init__(self, master: Optional[tk.Widget] = None) -> None:
        """Initialize the description tab.

        Args:
            master (Optional[tk.Widget], optional): Parent widget. Defaults to None.
        """
        super().__init__(master)
        self.root = master
        self.base_widgets = BaseTabWidgets()

        # Create main frame
        frame = tk.Frame(self)
        frame.pack(expand=True, fill="both")

        # Create and configure description text widget
        self.description_text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("Meiryo UI", 10)
        )
        
        # Get current language and set appropriate text
        current_lang = message_manager._language
        description = description_texts.get(current_lang, widget_description)
        
        self.description_text.insert("1.0", description)
        self.description_text.config(state="disabled")
        self.description_text.pack(expand=True, fill="both")
        # Display description tab
        # Log description tab display event
        logger.debug(message_manager.get_log_message("L146"))

    def bind_window_events(self, master: tk.Tk | tk.Toplevel) -> None:
        """Bind window events to the master window.
        When running in tab mode, do not bind window events.

        Args:
            master (tk.Tk | tk.Toplevel): Master window
        """
        # When running in tab mode, do not bind window events
        # Window events are centrally managed in the main window
        if not hasattr(self, "is_tab") or not self.is_tab:
            try:
                master.bind(
                    "<Configure>", lambda event: self.base_widgets.get_window_info(event)
                )
                master.protocol(
                    "WM_DELETE_WINDOW", lambda: self.base_widgets.exit_window(master)
                )
                # Events bound log
                # Log window events bound
                logger.debug(message_manager.get_log_message("L147"))
            except Exception as e:
                # Error binding window events
                logger.error(message_manager.get_log_message("L148", str(e)))
                raise

    def apply_theme_color(self, theme: Dict[str, Dict[str, str]]) -> None:
        """Apply color theme to all widgets.

        This method applies the specified color theme to this widget and all its children.
        It uses widget class names to match theme configurations.

        Args:
            theme (Dict[str, Dict[str, str]]): Theme configuration dictionary

        Raises:
            Exception: If theme application fails
        """
        try:
            # Apply theme to self
            widget_class = self.winfo_class()
            if widget_class in theme:
                config = theme[widget_class]
                self.configure(**config)
                # Theme applied to widget
                logger.debug(message_manager.get_log_message("L149", widget_class))

            # Apply theme to child widgets
            for child in self.winfo_children():
                child_class = child.winfo_class()
                if child_class in theme:
                    child_config = theme[child_class]
                    child.configure(**child_config)
                    # Theme applied to child widget
                    logger.debug(message_manager.get_log_message("L150", child_class))

        except Exception as e:
            # Error applying theme
            logger.error(message_manager.get_log_message("L151", str(e)))
            raise

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings."""
        self.configure(**theme_settings)  # type: ignore
        
    def refresh_language(self) -> None:
        """Update UI text elements with the current language.
        
        This method should be called when the application language is changed
        to update all text elements in this tab.
        """
        # Get current language
        current_lang = message_manager._language
        
        # Update description text
        description = description_texts.get(current_lang, widget_description)
        
        # Enable text widget for update
        self.description_text.config(state="normal")
        
        # Clear current content
        self.description_text.delete("1.0", tk.END)
        
        # Insert new content
        self.description_text.insert("1.0", description)
        
        # Disable editing
        self.description_text.config(state="disabled")
        
        # Log language change with appropriate message code
        logger.debug(message_manager.get_log_message("L228", current_lang))
