from __future__ import annotations

from logging import getLogger
from typing import Dict, Any, Optional, List
import tkinter as tk
from tkinter import messagebox

from configurations import tool_settings
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager
from widgets.base_tab_widgets import BaseTabWidgets

logger = getLogger(__name__)

message_manager = get_message_manager()

_MIN_BODY_WRAP_LENGTH = 320
_BODY_WRAP_HORIZONTAL_PADDING = 80

DESCRIPTION_TEXTS: Dict[str, Dict[str, Any]] = {
    "ja": {
        "title": "アプリケーション説明",
        "sections": [
            {
                "heading": "Main タブ",
                "items": [
                    {
                        "title": "1. 右上の共通操作",
                        "body": "右上の言語設定プルダウンでは日本語 / 英語を選べます。ただし表示反映にはアプリ再起動が必要です。右隣のイメージボタンではカラーモードを切り替えられ、こちらは切替後すぐに画面へ反映されます。"
                    },
                    {
                        "title": "2. ベースファイルパス",
                        "body": "差分確認の基準にする PDF を指定します。直接入力もできますが、通常は右側の「選択」ボタンを使うと安全です。ここで指定した PDF は左側レイヤーの元データになります。"
                    },
                    {
                        "title": "3. 比較ファイルパス",
                        "body": "ベースの上に重ねて確認する比較用 PDF を指定します。ベースと比較の両方がそろってから解析を行うと、重ね表示や保存に必要な情報がそろいます。"
                    },
                    {
                        "title": "4. 出力フォルダパス",
                        "body": "保存結果の出力先です。比較結果 PDF を保存するときに使うため、作業前に決めておくと流れが止まりません。他タブと共有される保存先でもあります。"
                    },
                    {
                        "title": "5. まず押す解析ボタン",
                        "body": "「ベースファイル解析」と「比較ファイル解析」は、指定した PDF を読み込み、プレビューとページ情報を使える状態にするための開始ボタンです。ファイルを指定しただけでは比較表示は完成しないため、まずこの2つを使います。"
                    },
                    {
                        "title": "6. 閾値入力欄と適用ボタン",
                        "body": "「閾値 元」「比較」は色処理結果をどこまで強調するかの調整値です。右の「適用」ボタンを押すと下の表示へ反映されます。線が出過ぎる、逆に薄くなる場合はここを調整してください。"
                    },
                    {
                        "title": "7. 色選択ボタンと画像ボタン",
                        "body": "ベースファイルパス右の青系ボタン、比較ファイルパス右の赤系ボタンは、各レイヤーの表示色を決めるためのボタンです。中央の画像ボタン2つは比較開始方法の切替用で、左は自動寄せ、右は手動寄せの入口として使います。"
                    },
                    {
                        "title": "8. 色処理・DPI設定・表示切替",
                        "body": "「色処理」コンボボックスでは指定色濃淡などの表示方式を選びます。「DPI設定」はプレビュー解像度の基準です。ベースファイル表示、比較ファイル表示、基準罫線を表示のチェックで、必要なレイヤーだけを見ながら確認できます。両方表示中は「差分を強調表示（半透明）」で、色処理後の画像同士の違いを半透明の色で重ねて強調できます。"
                    },
                    {
                        "title": "9. カスタム回転ガイドと中央Canvas",
                        "body": "「カスタム回転ガイド」ボタンは、回転中心指定や操作の考え方を確認したいときに使います。下の大きなCanvasは差分確認の中心画面で、マウスホイールで拡大縮小、ドラッグで移動、Ctrl系ショートカットで回転や反転ができます。"
                    },
                    {
                        "title": "10. 右側のページ操作パネル",
                        "body": "右側の矢印で前後ページへ移動し、数値欄で直接ページ番号を指定できます。「空白ページ挿入」「ページ削除」「保存」でページ構成や出力を行います。一括編集チェックをONにすると、現在ページのX、Y、角度、倍率の値を他ページにもまとめて反映できます。"
                    },
                    {
                        "title": "11. 下部の状態表示",
                        "body": "Canvas下にはピクセルサイズ、ピクセル密度、用紙サイズなどの情報が表示されます。表示内容が思ったものと違うときは、この欄を見て現在の状態を確認してください。"
                    }
                ]
            },
            {
                "heading": "PDF操作 タブ",
                "items": [
                    {
                        "title": "1. 右上の共通操作",
                        "body": "Main タブと同じく、右上の言語設定プルダウンは再起動後に反映されます。右隣のイメージボタンはカラーモード切替で、こちらはその場で見た目が変わります。"
                    },
                    {
                        "title": "2. ベースファイルパス",
                        "body": "編集したい PDF を指定します。このタブは1つの PDF をページ単位で見た目調整するためのタブなので、比較ファイルは使いません。PDF を選ぶとページ画像がCanvasへ表示されます。"
                    },
                    {
                        "title": "3. 出力フォルダパス",
                        "body": "編集後 PDF の保存先です。保存時に必須なので、作業前に決めておくとスムーズです。他タブと共通の保存先としても使われます。"
                    },
                    {
                        "title": "4. 中央プレビュー",
                        "body": "表示中ページを見ながら位置や角度を調整する作業画面です。ドラッグで移動し、マウスホイールで拡大縮小し、ショートカットや右側の変形情報欄で回転や倍率調整を行います。"
                    },
                    {
                        "title": "5. ページ移動とページ番号欄",
                        "body": "右側上部の左矢印 / 右矢印で前後ページへ移動します。中央の数値欄は現在ページ番号で、数値を入れて Enter を押すとそのページへ直接移動できます。下の「/ 総ページ数」は全体のページ数確認用です。"
                    },
                    {
                        "title": "6. 空白ページ挿入・ページ削除",
                        "body": "「空白ページ挿入」は現在ページの直後に白紙ページを追加します。「ページ削除」は表示中ページを削除しますが、最後の1ページだけを残した状態では削除できません。"
                    },
                    {
                        "title": "7. 保存ボタン",
                        "body": "現在の表示状態を反映した PDF を保存します。位置、角度、倍率、ページ追加 / 削除の結果が保存対象です。保存先は上の出力フォルダパスが使われます。"
                    },
                    {
                        "title": "8. 一括編集チェック",
                        "body": "ON のときは、現在ページに対して行った変形値を他ページにもまとめて反映します。全ページを同じ位置に寄せたい、同じ倍率にそろえたいときに使います。"
                    },
                    {
                        "title": "9. 変形情報欄",
                        "body": "「X」は左右移動量、「Y」は上下移動量、「角度」は回転角、「倍率」は拡大率です。数値を入力して Enter を押すと現在ページへ反映されます。ドラッグやホイールで変えた値の確認欄としても使えます。"
                    },
                    {
                        "title": "10. 下部メタ情報・保存サイズ・Canvasガイド",
                        "body": "Canvas下の1行に、保存に用いる「保存サイズ」（U172）とピクセルサイズ・推定DPI・用紙サイズの目安がまとめて表示されます。Canvas手前の下端にはMainタブと同じショートカット／操作ガイド（U150）が重なり表示され、右側操作列の下には「カスタム回転ガイド」ボタンで詳しい回転操作の説明を開けます。"
                    }
                ]
            },
            {
                "heading": "ファイル拡張子とサイズ タブ",
                "items": [
                    {
                        "title": "1. 右上の共通操作",
                        "body": "右上の言語設定プルダウンは再起動後に反映されます。右隣のイメージボタンではカラーモードをその場で切り替えられます。"
                    },
                    {
                        "title": "2. 入力ファイルパス",
                        "body": "変換したい画像や PDF / SVG を指定します。ドラッグ＆ドロップにも対応しています。入力した形式によって、拡張子変換とサイズ変換で使える機能や注意表示が変わります。"
                    },
                    {
                        "title": "3. 出力フォルダパス",
                        "body": "変換結果の保存先です。拡張子変換でもサイズ変換でも、このフォルダに結果が出力されます。同名ファイルがある場合は自動で別名保存されます。"
                    },
                    {
                        "title": "4. 拡張子変換ブロック上段",
                        "body": "左に入力ファイル名、中央に矢印、右に出力ファイル名と拡張子コンボボックスが表示されます。ここで変換先形式を選び、「拡張子変換」ボタンを押すのが基本操作です。"
                    },
                    {
                        "title": "5. 拡張子変換ブロック下段",
                        "body": "メタ情報表示には形式、モード、サイズ、実効ラスタライズDPI、DPI参照元、色プロファイル、EXIF などが出ます。PDF入力時は「PDFラスタライズDPI」欄が有効になり、画像化時の解像度を調整できます。警告文が表示された場合は内容を確認してから変換してください。"
                    },
                    {
                        "title": "6. サイズ変換ブロック上段",
                        "body": "左に元ファイル名、中央に矢印、右にサイズ変換後の出力名が表示されます。その下の現在サイズ表示は、今のピクセルサイズ確認用です。"
                    },
                    {
                        "title": "7. サイズ変換ブロック入力欄",
                        "body": "「幅」「高さ」で出力ピクセル数を指定します。「出力DPI」は保存時の解像度指定、「用紙サイズ」はA4などの定型サイズ入力補助です。「縦横比を固定」をONにすると、片方を変えたときにもう片方も自動調整されます。"
                    },
                    {
                        "title": "8. サイズ変換ブロック下段",
                        "body": "補足メッセージ欄にはDPIや入力形式に関する注意が表示されます。警告文が出た場合は内容を確認してから右下の「サイズ変換」ボタンを押してください。"
                    },
                    {
                        "title": "9. PDF / 複数ページ入力時の注意",
                        "body": "PDFや複数ページ入力では、先頭ページの代表値だけを表示する項目があります。全ページに同じ値をそのまま適用すると誤解を招く場合は、入力欄が無効化されたり注意文が表示されたりします。"
                    },
                    {
                        "title": "10. 最下部の状態表示",
                        "body": "最下部のステータス欄には、変換成功、警告、失敗理由などが表示されます。ボタンを押したのに結果が分からないときは、まずここを確認してください。"
                    }
                ]
            },
            {
                "heading": "説明 タブ",
                "items": [
                    {
                        "title": "1. 説明本文エリア",
                        "body": "このタブは各タブの使い方を順番に読むための場所です。上から順に読むと、どの欄を先に触ればよいかが分かるように並べています。"
                    },
                    {
                        "title": "2. スクロールバー",
                        "body": "右端のスクロールバー、またはマウスホイールで上下移動できます。説明量が多いときは、見たいタブの見出しまでスクロールして読んでください。"
                    },
                    {
                        "title": "3. 一時保存フォルダパスを表示",
                        "body": "下部左のボタンは、一時保存先フォルダを確認したいときに使います。製品版では Windows 標準の一時保存先フォルダを表示します。"
                    },
                    {
                        "title": "4. ログファイルパスを表示",
                        "body": "下部右のボタンは、ログ保存先を確認したいときに使います。不具合調査や動作確認時に、どのログファイルを見ればよいかを確認するためのボタンです。"
                    }
                ]
            },
            {
                "heading": "配布形態（製品ビルド）",
                "items": [
                    {
                        "title": "1. フォルダ一式と単一 exe",
                        "body": "既定の Nuitka ビルド（build_nuitka.ps1、--standalone）は build\\\\nuitka\\\\main.dist フォルダ内の pdfDiffChecker.exe と同梱の DLL 等がすべて必要です。exe ファイルだけを配布しても起動しません。単一の exe だけで渡したい場合は同スクリプトに -OneFile を付けてビルドし（Nuitka の --onefile）、出力フォルダに生成された pdfDiffChecker.exe 1 本を配布してください。初回起動時に一時フォルダへ展開するため、起動がやや遅くなることがあります。"
                    }
                ]
            },
        ],
    },
    "en": {
        "title": "Application Description",
        "sections": [
            {
                "heading": "Main Tab",
                "items": [
                    {"title": "1. Shared controls at the top right", "body": "The language drop-down lets you choose Japanese or English, but the UI text is applied after restarting the app. The image button next to it changes the color theme immediately."},
                    {"title": "2. Base file path", "body": "Select the reference PDF used as the source side of the comparison. You can type the path directly, but the Select button is the safer normal workflow."},
                    {"title": "3. Comparison file path", "body": "Select the PDF that will be overlaid against the base PDF for difference checking. Both files should be prepared before running analysis."},
                    {"title": "4. Output folder path", "body": "Choose the destination folder used when saving comparison results. This folder is also shared with other tabs."},
                    {"title": "5. Analysis buttons", "body": "Use the base and comparison analysis buttons first. They load the selected PDFs and prepare the preview and page information used by later steps."},
                    {"title": "6. Threshold fields and Apply button", "body": "These fields control how strongly each side is emphasized by the current color-processing mode. Press Apply after changing the numbers."},
                    {"title": "7. Color buttons and image buttons", "body": "The color buttons next to the base and comparison paths define the visible color of each layer. The two large image buttons are the entry points for automatic alignment and manual alignment workflows."},
                    {"title": "8. Color mode, DPI, and layer toggles", "body": "Choose the processing mode, set the preview DPI, and turn the base layer, comparison layer, and reference grid on or off as needed. When both layers are visible, use Highlight differences (semi-transparent) to tint regions where the processed pixels differ."},
                    {"title": "9. Rotation guide and preview canvas", "body": "The custom rotation guide explains the rotation workflow. The large canvas below is the main inspection area, where you can zoom, pan, rotate, and inspect the overlaid result."},
                    {"title": "10. Right-side page controls", "body": "Move between pages, insert blank pages, delete pages, save, and enter X/Y, angle, and scale values. Batch Edit applies the current transform settings to other pages as well."},
                    {"title": "11. Footer status information", "body": "The footer below the canvas shows pixel size, DPI, and paper-size information for the current page so you can confirm the current state quickly."}
                ]
            },
            {
                "heading": "PDF Operation Tab",
                "items": [
                    {"title": "1. Shared controls at the top right", "body": "The language choice is applied after restarting the app, while the theme image button updates the look immediately."},
                    {"title": "2. Base file path", "body": "Load the PDF that you want to edit page by page. This tab works with one PDF only and does not use a comparison file."},
                    {"title": "3. Output folder path", "body": "Choose where the edited PDF should be saved before exporting."},
                    {"title": "4. Central preview", "body": "Preview the current page and adjust its visual position, rotation, and scale by dragging, scrolling, shortcuts, or the transform fields."},
                    {"title": "5. Page navigation", "body": "Use the arrow buttons, direct page number entry, and the total-page indicator to move through the document."},
                    {"title": "6. Insert blank page and delete page", "body": "Insert adds a blank page after the current page. Delete removes the current page, except when only one page remains."},
                    {"title": "7. Save button", "body": "Save exports the edited PDF using the current page layout and the selected output folder."},
                    {"title": "8. Batch Edit check box", "body": "When enabled, transform changes on the current page are propagated to other pages."},
                    {"title": "9. Transform fields", "body": "X, Y, angle, and scale fields are direct numeric controls for the current page. Press Enter to apply the values."},
                    {"title": "10. Footer, saved size, and canvas guide", "body": "One line under the canvas combines the Saved size export hint (U172) with pixel size, estimated DPI, and paper-size hints. The same shortcut and canvas guide strip as the Main tab (U150) appears along the bottom of the canvas, and the Custom Rotation Guide button below the right-hand controls opens detailed rotation instructions."}
                ]
            },
            {
                "heading": "File Extension and Size Tab",
                "items": [
                    {"title": "1. Shared controls at the top right", "body": "The language setting is reflected after restarting the app, while the theme image button updates the color mode immediately."},
                    {"title": "2. Input file path", "body": "Select the source image, PDF, or SVG file to convert. Drag and drop is also supported."},
                    {"title": "3. Output folder path", "body": "Set the destination folder for every conversion result. Existing names are avoided automatically by saving to a different name when needed."},
                    {"title": "4. Extension conversion block: top row", "body": "The upper block shows the input name on the left, the conversion arrow in the middle, and the output name plus extension selector on the right. Use this area to choose the target format."},
                    {"title": "5. Extension conversion block: details", "body": "The metadata area shows format, mode, size, effective raster DPI, DPI source, ICC, and EXIF details. When the input is a PDF, the PDF Raster DPI field becomes important because it controls rasterization quality."},
                    {"title": "6. Size conversion block: top row", "body": "This block shows the current file name, the output name, and the current pixel size before resizing."},
                    {"title": "7. Size conversion block: input fields", "body": "Width and height define the output size in pixels. Output DPI controls saved resolution metadata, paper size helps fill common dimensions, and Lock aspect ratio keeps width and height synchronized."},
                    {"title": "8. Size conversion block: messages and action", "body": "Read the hint and warning messages before pressing the Size Conversion button, especially for PDF inputs or unusual resize settings."},
                    {"title": "9. Multi-page guidance", "body": "Representative values and edit restrictions are shown when the input contains multiple pages or frames, so always follow the on-screen guidance in those cases."},
                    {"title": "10. Bottom status area", "body": "The bottom status line reports success, warnings, and failure reasons after each conversion."}
                ]
            },
            {
                "heading": "Description Tab",
                "items": [
                    {"title": "1. Description body area", "body": "This tab explains how to use each screen in a practical order so users can read from top to bottom and follow the workflow."},
                    {"title": "2. Scroll bar", "body": "Use the vertical scroll bar or the mouse wheel to move through the full explanation."},
                    {"title": "3. Show temp folder path", "body": "This button shows the active temporary-working folder. In the packaged app, it points to the standard Windows temporary app folder."},
                    {"title": "4. Show log file path", "body": "This button shows the current log file path used for troubleshooting and runtime checks."}
                ]
            },
            {
                "heading": "Distribution (packaged build)",
                "items": [
                    {
                        "title": "1. Folder bundle vs single executable",
                        "body": "The default Nuitka build from build_nuitka.ps1 uses --standalone: you must ship the entire build\\\\nuitka\\\\main.dist folder (pdfDiffChecker.exe plus bundled DLLs and data). The exe alone is not sufficient. To ship a single file, rebuild with -OneFile (adds --onefile) and distribute only the generated pdfDiffChecker.exe in the output folder. One-file apps extract on first launch, which can make startup slightly slower."
                    }
                ]
            },
        ],
    },
}


class DescriptionApp(tk.Frame, ColoringThemeIF):
    """Application description tab.

    This class provides a scrollable text widget that displays application
    description and usage instructions in Japanese.

    Attributes:
        root (Optional[tk.Widget]): Parent widget
        base_widgets (BaseTabWidgets): Base tab widget container
        _section_frames (List[tk.LabelFrame]): Framed sections for tab descriptions
    """

    def __init__(self, master: Optional[tk.Widget] = None) -> None:
        """Initialize the description tab.

        Args:
            master (Optional[tk.Widget], optional): Parent widget. Defaults to None.
        """
        super().__init__(master)
        WidgetsTracker().add_widgets(self)
        self.root = master
        self.base_widgets = BaseTabWidgets()
        self._temp_path_button: Optional[tk.Button] = None
        self._log_path_button: Optional[tk.Button] = None
        self._user_settings_path_button: Optional[tk.Button] = None
        self._section_frames: List[tk.LabelFrame] = []
        self._section_title_labels: List[tk.Label] = []
        self._section_body_labels: List[tk.Label] = []
        self._scroll_bind_targets: List[tk.Widget] = []

        # Main processing: split the tab into a scrollable description area and a bottom path-action area.
        self._content_frame = tk.Frame(self)
        self._content_frame.pack(expand=True, fill="both")

        self._scroll_canvas = tk.Canvas(self._content_frame, highlightthickness=0, borderwidth=0)
        self._scrollbar = tk.Scrollbar(self._content_frame, orient="vertical", command=self._scroll_canvas.yview)
        self._sections_container = tk.Frame(self._scroll_canvas)

        self._sections_container.bind("<Configure>", self._on_sections_container_configure)
        self._scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scroll_canvas.create_window((0, 0), window=self._sections_container, anchor="nw", tags=("sections_window",))
        self._bind_scroll_target(self._scroll_canvas)
        self._bind_scroll_target(self._sections_container)
        self._bind_scroll_target(self._scrollbar)

        self._scroll_canvas.pack(side="left", expand=True, fill="both")
        self._scrollbar.pack(side="right", fill="y")

        self._button_frame = tk.Frame(self)
        self._button_frame.pack(fill="x", side="bottom", padx=8, pady=(4, 8))

        self._temp_path_button = tk.Button(
            self._button_frame,
            text="",
            command=self._show_temp_path,
        )
        self._temp_path_button.pack(side="left", padx=(0, 8))

        self._log_path_button = tk.Button(
            self._button_frame,
            text="",
            command=self._show_log_path,
        )
        self._log_path_button.pack(side="left", padx=(0, 8))

        self._user_settings_path_button = tk.Button(
            self._button_frame,
            text="",
            command=self._show_user_settings_path,
        )
        self._user_settings_path_button.pack(side="left")

        self._render_sections()
        self.refresh_language()
        self.apply_theme_color(ColorThemeManager.get_current_theme())  # type: ignore[arg-type]
        # Display description tab
        # Log description tab display event
        logger.debug(message_manager.get_log_message("L146"))

    def _show_temp_path(self) -> None:
        """Show the absolute runtime temporary-folder path."""
        # Main processing: expose the active runtime temporary root for troubleshooting.
        messagebox.showinfo(
            title=message_manager.get_ui_message("U165"),
            message=str(tool_settings.RUNTIME_STORAGE_ROOT.resolve()),
            parent=self.winfo_toplevel(),
        )

    def _show_log_path(self) -> None:
        """Show the absolute runtime log-file path."""
        # Main processing: expose the current log file location for troubleshooting.
        messagebox.showinfo(
            title=message_manager.get_ui_message("U166"),
            message=str(tool_settings.LOG_FILE_PATH.resolve()),
            parent=self.winfo_toplevel(),
        )

    def _show_user_settings_path(self) -> None:
        """Show the absolute path to the persisted ``user_settings.json`` file."""
        messagebox.showinfo(
            title=message_manager.get_ui_message("U174"),
            message=str(tool_settings.USER_SETTINGS_FILE.resolve()),
            parent=self.winfo_toplevel(),
        )

    def _get_current_language_texts(self) -> Dict[str, str]:
        """Return localized description-tab texts for the current language.

        Returns:
            Dict[str, str]: Localized text map.
        """
        current_lang = str(getattr(message_manager, "_language", "ja") or "ja")
        return DESCRIPTION_TEXTS.get(current_lang, DESCRIPTION_TEXTS["ja"])

    def _on_sections_container_configure(self, event: tk.Event) -> None:
        """Update the canvas scrollregion after the inner section frame changes.

        Args:
            event: Tk configure event.
        """
        _ = event
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_scroll_canvas_configure(self, event: tk.Event) -> None:
        """Stretch the inner section frame to the current canvas width.

        Args:
            event: Tk configure event.
        """
        self._scroll_canvas.itemconfigure("sections_window", width=event.width)
        self._update_body_wrap_lengths(int(event.width))

    def _bind_scroll_target(self, widget: tk.Widget) -> None:
        """Bind vertical-wheel scrolling events to the specified widget.

        Args:
            widget: Widget that should forward wheel events to the canvas.
        """
        widget.bind("<MouseWheel>", self._on_mousewheel_scroll, add="+")
        widget.bind("<Button-4>", self._on_mousewheel_scroll, add="+")
        widget.bind("<Button-5>", self._on_mousewheel_scroll, add="+")
        self._scroll_bind_targets.append(widget)

    def _on_mousewheel_scroll(self, event: tk.Event) -> str:
        """Scroll the description canvas vertically for wheel input.

        Args:
            event: Mouse-wheel event.

        Returns:
            str: Tkinter break signal to stop duplicate handlers.
        """
        try:
            delta = int(getattr(event, "delta", 0) or 0)
        except (TypeError, ValueError):
            delta = 0

        try:
            event_num = int(getattr(event, "num", 0) or 0)
        except (TypeError, ValueError):
            event_num = 0

        if delta > 0 or event_num == 4:
            self._scroll_canvas.yview_scroll(-1, "units")
        elif delta < 0 or event_num == 5:
            self._scroll_canvas.yview_scroll(1, "units")
        return "break"

    def _update_body_wrap_lengths(self, canvas_width: int) -> None:
        """Update body-label wrap lengths to fit the visible canvas width.

        Args:
            canvas_width: Current visible canvas width in pixels.
        """
        wrap_length = max(_MIN_BODY_WRAP_LENGTH, canvas_width - _BODY_WRAP_HORIZONTAL_PADDING)
        for body_label in self._section_body_labels:
            body_label.configure(wraplength=wrap_length)

    def _clear_section_widgets(self) -> None:
        """Destroy all rendered description sections before rebuilding them."""
        for child in self._sections_container.winfo_children():
            child.destroy()
        self._section_frames = []
        self._section_title_labels = []
        self._section_body_labels = []

    def _render_sections(self) -> None:
        """Render the framed description sections for the current language."""
        texts = self._get_current_language_texts()
        sections = list(texts.get("sections", []))
        self._clear_section_widgets()

        for section_index, section in enumerate(sections):
            section_frame = tk.LabelFrame(
                self._sections_container,
                text=str(section.get("heading", "")),
                padx=10,
                pady=8,
                bd=1,
                relief=tk.GROOVE,
            )
            section_frame.pack(fill="x", expand=True, padx=10, pady=(10 if section_index == 0 else 0, 10))
            self._section_frames.append(section_frame)
            self._bind_scroll_target(section_frame)

            for item in list(section.get("items", [])):
                title_label = tk.Label(
                    section_frame,
                    text=str(item.get("title", "")),
                    anchor="w",
                    justify="left",
                    font=("Meiryo UI", 10, "bold"),
                )
                title_label.pack(fill="x", anchor="w", pady=(4, 0))
                self._section_title_labels.append(title_label)
                self._bind_scroll_target(title_label)

                body_label = tk.Label(
                    section_frame,
                    text=str(item.get("body", "")),
                    anchor="w",
                    justify="left",
                    wraplength=_MIN_BODY_WRAP_LENGTH,
                    font=("Meiryo UI", 10),
                )
                body_label.pack(fill="x", anchor="w", padx=(12, 0), pady=(0, 6))
                self._section_body_labels.append(body_label)
                self._bind_scroll_target(body_label)

        self.after_idle(lambda: self._update_body_wrap_lengths(self._scroll_canvas.winfo_width()))

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
            frame_theme = dict(theme.get("Frame", {})) if isinstance(theme, dict) else {}
            window_theme = dict(theme.get("Window", {})) if isinstance(theme, dict) else {}
            text_theme = dict(theme.get("text_box", {})) if isinstance(theme, dict) else {}
            button_theme = dict(theme.get("process_button", theme.get("Button", {}))) if isinstance(theme, dict) else {}

            frame_bg = frame_theme.get("bg", window_theme.get("bg", "#ffffff"))
            frame_fg = frame_theme.get("fg", "#000000")
            text_bg = text_theme.get("bg", frame_bg)
            text_fg = text_theme.get("fg", frame_fg)

            self.configure(bg=frame_bg)
            self._content_frame.configure(bg=frame_bg)
            self._button_frame.configure(bg=frame_bg)
            self._sections_container.configure(bg=frame_bg)
            self._scroll_canvas.configure(
                bg=frame_bg,
                highlightbackground=frame_bg,
                highlightcolor=frame_bg,
            )
            try:
                self._scrollbar.configure(
                    bg=button_theme.get("bg", frame_bg),
                    activebackground=button_theme.get("activebackground", frame_bg),
                    troughcolor=frame_bg,
                    highlightbackground=frame_bg,
                )
            except Exception:
                pass

            for section_frame in self._section_frames:
                section_frame.configure(
                    bg=text_bg,
                    fg=text_fg,
                    highlightbackground=button_theme.get("activebackground", frame_bg),
                    highlightcolor=button_theme.get("activebackground", frame_bg),
                )

            for title_label in self._section_title_labels:
                title_label.configure(bg=text_bg, fg=text_fg)

            for body_label in self._section_body_labels:
                body_label.configure(bg=text_bg, fg=text_fg)

            for button in [
                self._temp_path_button,
                self._log_path_button,
                self._user_settings_path_button,
            ]:
                if button is None:
                    continue
                button.configure(
                    bg=button_theme.get("bg", frame_bg),
                    fg=button_theme.get("fg", frame_fg),
                    activebackground=button_theme.get("activebackground", frame_bg),
                    activeforeground=button_theme.get("activeforeground", frame_fg),
                    highlightbackground=button_theme.get("activebackground", frame_bg),
                    highlightcolor=button_theme.get("activebackground", frame_bg),
                )

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
        self._render_sections()
        if self._temp_path_button is not None:
            self._temp_path_button.configure(text=message_manager.get_ui_message("U163"))
        if self._log_path_button is not None:
            self._log_path_button.configure(text=message_manager.get_ui_message("U164"))
        if self._user_settings_path_button is not None:
            self._user_settings_path_button.configure(text=message_manager.get_ui_message("U173"))

        # Log language change with appropriate message code
        logger.debug(message_manager.get_log_message("L228", getattr(message_manager, "_language", "ja")))
