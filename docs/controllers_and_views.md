# コントローラーとビューの関係

## 概要

このドキュメントでは、PDF Diff Checkerアプリケーションにおけるコントローラーとビューの関係について詳細に説明します。特に、マウスイベント処理の集約方法と、各コンポーネントの責任範囲について解説します。

## マウスイベント処理の集約

### `MouseEventHandler` クラス

`controllers/mouse_event_handler.py`に定義されている`MouseEventHandler`クラスは、アプリケーション全体のマウスイベント処理のコアロジックを提供する低レベルのコントローラーです。

```python
class MouseEventHandler:
    def __init__(self, layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]], 
                 current_page_index: int, visible_layers: Dict[int, bool], 
                 on_transform_update: Callable[[], None]):
        # 初期化
    
    def on_mouse_down(self, event: tk.Event) -> None:
        # マウスボタン押下イベントを処理
        
    def on_mouse_drag(self, event: tk.Event) -> None:
        # マウスドラッグイベントを処理
        
    def on_mouse_up(self, event: tk.Event) -> None:
        # マウスボタン解放イベントを処理
        
    # その他のマウスイベントメソッド
```

### `PDFMouseHandler` クラス

`controllers/pdf_mouse_handler.py`に定義されている`PDFMouseHandler`クラスは、PDFビューアー向けに最適化された高レベルのラッパーです。このクラスは`MouseEventHandler`を内部で使用し、PDFビューアー特有の処理を行います。

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
        # マウスホイールイベントを処理し、MouseEventHandlerに委譲
        
    def on_mouse_down(self, event: Any) -> None:
        # マウスボタン押下イベントを処理し、MouseEventHandlerに委譲
        
    def on_mouse_move(self, event: Any) -> None:
        # マウス移動イベントを処理し、MouseEventHandlerのon_mouse_dragに委譲
        
    def on_mouse_up(self, event: Any) -> None:
        # マウスボタン解放イベントを処理し、MouseEventHandlerに委譲
```

`MouseEventHandler`クラスは以下の機能を提供します：

1. **変換データの管理**
   - 回転、移動、拡大縮小などの変換データを管理
   - 複数のレイヤーと複数のページに対応

2. **マウスイベント処理**
   - ドラッグによる移動
   - Ctrl+ドラッグによる回転
   - マウスホイールによるズーム

`PDFMouseHandler`クラスは以下の機能を提供します：

1. **高レベルのイベント処理**
   - エラーハンドリングの追加
   - ログ出力の最適化（スロットリング）
   - 一貫したインターフェースの提供

2. **PDFビューアー特有の機能**
   - PDFページのズーム処理
   - PDFページの回転処理
   - PDFページの移動処理

### ビューからのイベント委譲

各ビュークラスは、マウスイベントを`PDFMouseHandler`に委譲し、`PDFMouseHandler`が`MouseEventHandler`に委譲します：

```python
# views/pdf_ope_tab.py の例
def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
    # 他の初期化コード...
    
    # PDFMouseHandlerインスタンスを作成
    self.pdf_mouse_handler = PDFMouseHandler(self)
    
    # マウスイベントのセットアップ
    self._setup_mouse_events()

def _setup_mouse_events(self) -> None:
    # PDFMouseHandlerを使用してマウスイベントをセットアップ
    self.pdf_mouse_handler.setup_mouse_events()

def _on_transform_update(self) -> None:
    # 変換データが更新された時のコールバック
    # 現在のページを再表示
    self._display_page(self.current_page_index)
```

## コンポーネント間の相互作用

### 1. イベントフロー

1. ユーザーがマウスイベント（ホイール、クリック、ドラッグなど）を実行
2. tkinterがイベントをビュークラスのイベントハンドラに渡す
3. ビュークラスが`PDFMouseHandler`にイベントを委譲
4. `PDFMouseHandler`が`MouseEventHandler`にイベントを委譲
5. `MouseEventHandler`がイベントを処理し、必要に応じて変換データを更新
6. コールバック関数が呼び出され、ビューが更新される

### 2. データの流れ

```
[ユーザーイベント] → [ビュークラス] → [PDFMouseHandler] → [MouseEventHandler] → [変換データ更新] → [コールバック] → [ビュー更新]
```

### 3. 責任分担

- **MouseEventHandler**: 低レベルのイベント処理とデータ変換のコアロジック
- **PDFMouseHandler**: PDFビューアー特有の高レベルイベント処理、エラーハンドリング、ログ出力の最適化
- **ビュークラス**: UI表示と更新、ユーザー入力の受け取り
- **コールバック関数**: ビューとコントローラー間の通信

## 実装例

### PDFビューアーでのズーム操作

1. ユーザーがマウスホイールを回転
2. tkinterがイベントを`PDFMouseHandler.on_mouse_wheel`に直接渡す
3. `PDFMouseHandler`がズーム係数を計算し、エラーハンドリングを行う
4. `MouseEventHandler`の適切なメソッドにイベントが委譲される
5. 変換データが更新される
6. `_on_transform_update`コールバックが呼び出される
7. PDFページが新しいスケールで再描画される

### 比較モードでのズーム操作

1. ユーザーがマウスホイールを回転
2. イベントが`MouseEventHandler.on_mouse_wheel`に直接渡される
3. `MouseEventHandler._process_wheel_zoom_multi_layer`が全ての表示レイヤーのスケール値を更新
4. `__on_transform_update`コールバックが呼び出される
5. 全てのレイヤーが新しいスケールで再描画される

## 設計上の利点

1. **コードの再利用**: マウスイベント処理ロジックが集約され、重複が排除される
2. **一貫性**: 全てのビューで同じマウス操作体験が提供される
3. **保守性**: マウス操作の変更が1か所で行える
4. **拡張性**: 新しいマウス操作を追加する際に、既存のビューを変更する必要がない

## マウス操作の詳細仕様

### 回転機能

1. **回転モードの開始**
   - Ctrlキーを押しながらマウスをクリックすると回転モードが開始される
   - 回転中心点として赤い小さな点（半径3ピクセル）が表示される
   - 初期状態では、クリックした位置が回転中心点になる

2. **回転操作**
   - Ctrlキーを押しながらマウスをドラッグすると、画像が回転中心点を中心に回転する
   - 回転角度はマウスの移動方向と距離に基づいて計算される
   - 回転中は常に回転中心点（赤い点）が表示され続ける
   - 回転中は「回転中」というガイダンステキスト（M042）が画面上部に半透明の赤枠赤字で表示される

3. **回転の完了**
   - マウスボタンを離すと回転操作が完了する
   - 回転角度を示す通知が表示される（例：「45°回転しました」）
   - Ctrlキーを押し続けている間は回転モードが維持され、回転中心点も表示されたままになる
   - Ctrlキーを離すと回転モードが終了し、回転中心点も消える

4. **回転中心の移動**
   - 回転中心の赤点を移動するには一度Ctrl＋クリックを両方離して、再度別の場所でCtrl＋クリックする

### ショートカットヘルプ

1. **表示条件**
   - 回転機能の中心の赤点を表示している間中表示される
   - 赤点を表示し終えてから再表示するまで非表示になる

2. **表示形式**
   - 表示位置：画面右上
   - 表示色：半透明の赤色
   - 表示内容：メッセージID 'M049'

### キーボードショートカット

以下のショートカットキーが実装されており、使用時に0.5秒間メッセージが表示される：

1. **Ctrl+R**: 右に90°回転（M044）
2. **Ctrl+L**: 左に90°回転（M045）
3. **Ctrl+V**: 垂直に反転（M046）
4. **Ctrl+H**: 水平に反転（M047）
5. **Ctrl+B**: 元の状態にリセット（M048）

## 今後の改善点

1. **ドラッグ操作の統合**: 現在のドラッグ操作も同様に集約する
2. **キーボードイベントの集約**: キーボードショートカットなども同様の方法で集約する
3. **イベントバスの導入**: より疎結合なイベント処理のためのイベントバスパターンの検討
