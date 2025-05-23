# PDF Diff Checker - File Structure and Architecture

## Project Overview

PDF Diff Checkerは、2つのPDFファイル間の差分を表示するアプリケーションです。このドキュメントでは、アプリケーションのファイル構造と各コンポーネントの役割について説明します。

## Directory Structure

```
pdfDiffChecker/
├── configurations/     # 設定ファイルとメッセージコード
├── controllers/        # イベント処理とコントローラー
├── docs/               # ドキュメントとER図
├── images/             # アプリケーションで使用される画像
├── logs/               # ログファイル
├── models/             # データモデルとビジネスロジック
├── tests/              # テストコード
├── themes/             # カラーテーマ
├── utils/              # ユーティリティ関数
├── views/              # UIビュー
├── widgets/            # 再利用可能なUIコンポーネント
└── main.py             # アプリケーションのエントリーポイント
```

## Key Components

### Controllers

#### `mouse_event_handler.py`

マウスイベント（ドラッグ、ズーム、クリックなど）を処理する低レベルのコアロジックを提供します。

```python
class MouseEventHandler:
    def __init__(self, layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]], 
                 current_page_index: int, visible_layers: Dict[int, bool], 
                 on_transform_update: Callable[[], None]):
        # レイヤー変換データ、現在のページインデックス、表示レイヤー、更新コールバックを初期化
    
    def on_mouse_down(self, event: tk.Event) -> None:
        # マウスボタン押下イベントを処理
    
    def on_mouse_drag(self, event: tk.Event) -> None:
        # マウスドラッグイベントを処理（移動操作）
    
    def on_mouse_up(self, event: tk.Event) -> None:
        # マウスボタン解放イベントを処理
    
    def update_state(self, current_page_index: int, visible_layers: Dict[int, bool]) -> None:
        # 状態を更新（現在のページインデックスと表示レイヤー）
    
    def attach_to_canvas(self, canvas_widget: tk.Canvas) -> None:
        # キャンバスにアタッチしてビジュアルフィードバックを提供
```

#### `pdf_mouse_handler.py`

PDFビューアー向けに最適化された高レベルのマウスイベント処理を提供します。`MouseEventHandler`クラスを内部で使用し、エラーハンドリングとログ出力の最適化を行います。

```python
class PDFMouseHandler:
    def __init__(self, parent: Any) -> None:
        # 親ウィジェットへの参照を保持
        self.parent = parent
        self.mouse_handler: Optional[MouseEventHandler] = None
        # ログスロットリング用のインスタンスを初期化
    
    def initialize_mouse_handler(self) -> None:
        # MouseEventHandlerインスタンスを初期化
    
    def setup_mouse_events(self) -> None:
        # マウスイベントのバインディングをセットアップ
    
    def on_mouse_wheel(self, event: Any) -> None:
        # マウスホイールイベントを処理し、ズーム機能を提供
        # エラーハンドリングとログ出力の最適化を行う
    
    def on_mouse_down(self, event: Any) -> None:
        # マウスボタン押下イベントを処理し、MouseEventHandlerに委譲
    
    def on_mouse_move(self, event: Any) -> None:
        # マウス移動イベントを処理し、MouseEventHandlerのon_mouse_dragに委譲
    
    def on_mouse_up(self, event: Any) -> None:
        # マウスボタン解放イベントを処理し、MouseEventHandlerに委譲
    
    def on_zoom_in(self, event: Any = None) -> None:
        # ズームイン操作を処理
    
    def on_zoom_out(self, event: Any = None) -> None:
        # ズームアウト操作を処理
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

PDFファイルの操作タブを提供します。PDFの表示、ズーム、ページ移動などの機能を実装しています。マウスイベント処理は`PDFMouseHandler`クラスに委譲しています。

```python
class PDFOperationApp(ttk.Frame, ColoringThemeIF):
    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        # PDFビューアーの初期化
        # PDFMouseHandlerインスタンスを作成
        self.pdf_mouse_handler = PDFMouseHandler(self)
    
    def _display_page(self, page_index: int) -> None:
        # 指定されたページを表示
        # 回転、拡大縮小、移動などの変換を適用
    
    def _setup_mouse_events(self) -> None:
        # PDFMouseHandlerを使用してマウスイベントをセットアップ
        self.pdf_mouse_handler.setup_mouse_events()
    
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
