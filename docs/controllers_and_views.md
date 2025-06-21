# コントローラーとビューの関係

## 概要

このドキュメントでは、PDF Diff Checkerアプリケーションにおけるコントローラーとビューの関係について詳細に説明します。特に、マウスイベント処理の集約方法と、各コンポーネントの責任範囲について解説します。

## マウスイベント処理の集約

### マウスイベント処理の基本構造

`controllers/mouse_event_handler.py`に定義されている`MouseEventHandler`クラスは、アプリケーション全体のマウスイベント処理のコアロジックを提供する低レベルのコントローラーです。このクラスは`TransformationManager`と連携して、PDFやTIFFファイルの表示レイヤーの変換データを管理します。

```python
class MouseEventHandler:
    def __init__(self, transform_manager: TransformationManager, 
                 visible_layers: Dict[int, bool], 
                 msg_mgr: MessageManager, canvas_ref: tk.Canvas):
        # 初期化
    
    def on_mouse_down(self, event: tk.Event) -> None:
        # マウスボタン押下イベントを処理
        
    def on_mouse_drag(self, event: tk.Event) -> None:
        # マウスドラッグイベントを処理
        
    def on_mouse_up(self, event: tk.Event) -> None:
        # マウスボタン解放イベントを処理
        
    def __force_display_rotation_elements(self) -> None:
        # 回転モード中の視覚要素を強制的に表示
        
    # その他のマウスイベントメソッド
```

### `MouseEventHandler` クラス

`controllers/mouse_event_handler.py`に定義されている`MouseEventHandler`クラスは、マウスイベント処理の中核となるクラスです。このクラスはPDFビューアーを含む様々なコンポーネントで直接使用されます。

```python
class MouseEventHandler:
    def __init__(
            self,
            layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]],
            current_page_index: int,
            visible_layers: Dict[int, bool],
            on_transform_update: Callable[[], None],
            # transform_manager: TransformationManager, # この引数は実際には __init__ に直接渡されません
            # msg_mgr: MessageManager, # MessageManagerはグローバルインスタンスを使用
            # canvas_ref: tk.Canvas # canvas_refは attach_to_canvas で設定
        ) -> None:
        # 変換データ、ページインデックス、表示レイヤー、更新コールバックを初期化
        self.__layer_transform_data = layer_transform_data
        self.__current_page_index = current_page_index
        self.__visible_layers = visible_layers
        self.__on_transform_update = on_transform_update
        # MessageManagerはモジュールレベルで取得
        self.__msg_mgr = get_message_manager()
        # Canvas参照は attach_to_canvas で設定
        self.__canvas_ref: Optional[tk.Canvas] = None
        # その他の初期化...

    def attach_to_canvas(self, canvas: tk.Canvas) -> None:
        # キャンバスへの参照を設定し、イベントバインドに必要な準備を行う
        self.__canvas_ref = canvas
        
    def update_state(self, current_page_index: int, visible_layers: Dict[int, bool]) -> None:
        # 状態を更新（ページ変更時など）
        
    def on_mouse_wheel(self, event: tk.Event) -> None:
        # マウスホイールイベントを処理（ズーム）
        
    def on_mouse_down(self, event: tk.Event) -> str:
        # マウスボタン押下イベントを処理
        
    def on_mouse_drag(self, event: tk.Event) -> None:
        # マウス移動イベントを処理（ドラッグ中）
        
    def on_mouse_up(self, event: tk.Event) -> None:
        # マウスボタン解放イベントを処理
```

`MouseEventHandler`クラスは以下の機能を提供します：

1. **変換データの管理**
   - 回転、移動、拡大縮小などの変換データを管理
   - 複数のレイヤーと複数のページに対応

2. **マウスイベント処理**
   - ドラッグによる移動
   - Ctrl+ドラッグによる回転
   - マウスホイールによるズーム

3. **視覚的フィードバック**
   - 回転中心点の表示
   - ガイダンステキストの表示
   - 通知メッセージの表示
   - ショートカットヘルプの表示

4. **回転モード管理**
   - Ctrlキー状態の監視
   - 回転モードの開始と終了
   - 回転角度の平滑化処理

5. **変換操作の委譲**
   - TransformationManagerを使用して変換データを管理
   - 複数のレイヤーと複数のページに対する変換操作を委譲

### `TransformationManager` クラス

`controllers/transform_manager.py`に定義されている`TransformationManager`クラスは、表示レイヤーの変換データを管理する専用のクラスです。このクラスは、MouseEventHandlerから使用され、PDFやTIFFファイルの表示に関する変換データ（回転、移動、拡大縮小、水平・垂直反転）を一元管理します。

```python
class TransformationManager:
    def __init__(self) -> None:
        # TransformationManagerを空のデータで初期化します。
        
    def get_transform_data(self, layer_id: int, page_index: int) -> Tuple[float, float, float, float, bool, bool]:
        # 特定のレイヤーとページの変換データ（回転、X座標、Y座標、スケール、水平反転、垂直反転）を取得
        
    def set_transform_data(self, layer_id: int, page_index: int, rotation: float, 
                           tx: float, ty: float, scale: float,
                           flip_x: bool = False, flip_y: bool = False) -> None:
        # 特定のレイヤーとページの変換データ（反転フラグを含む）を設定
        
    def update_transform_data(self, layer_id: int, page_index: int, rotation: Optional[float] = None, 
                              tx: Optional[float] = None, ty: Optional[float] = None, 
                              scale: Optional[float] = None, flip_x: Optional[bool] = None,
                              flip_y: Optional[bool] = None) -> None:
        # 特定のレイヤーとページの変換データ（反転フラグを含む）を更新
```

`TransformationManager`クラスは以下の機能を提供します：

1. **高レベルのイベント処理**
   - エラーハンドリングの追加
   - ログ出力の最適化（スロットリング）
   - 一貫したインターフェースの提供

2. **ページインデックス管理**
   - 現在表示中のページインデックスを管理
   - ページ切り替え時の状態保持

3. **レイヤー管理**
   - レイヤーの追加と削除
   - 各レイヤーの変換データの初期化と更新

4. **画像変換操作**
   - 回転、移動、拡大縮小の管理
   - 水平・垂直反転フラグの管理

### ビューからのイベント委譲

各ビュークラスは、マウスイベントを直接`MouseEventHandler`に委譲します：

```python
# views/pdf_ope_tab.py の例 (簡略化・概念)
def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
    # 他の初期化コード...
    
    # TransformationManagerインスタンスを作成 (引数なしで初期化)
    self.transform_manager = TransformationManager()
    
    # MouseEventHandlerインスタンスを作成
    self._initialize_mouse_handler() 
    
    # マウスイベントのセットアップ
    self._setup_mouse_events()

def _initialize_mouse_handler(self) -> None:
    # MouseEventHandlerインスタンスを作成
    # 実際の引数はMouseEventHandlerの__init__定義に合わせる
    self.mouse_handler = MouseEventHandler(
        layer_transform_data=self.transform_manager.get_all_transform_data(), # 初期データを提供
        current_page_index=self.transform_manager.get_current_page_index(),
        visible_layers=self.visible_layers, # ビューが管理する表示状態
        on_transform_update=self._on_transform_update # ビューの更新用コールバック
    )
    # MouseEventHandlerにCanvasをアタッチ
    if hasattr(self, 'canvas'): # canvasウィジェットが存在する場合
        self.mouse_handler.attach_to_canvas(self.canvas)
    
def _setup_mouse_events(self) -> None:
    # キャンバスにマウスイベントをバインド
    self.canvas.bind("<ButtonPress-1>", self.mouse_handler.on_mouse_down)
    self.canvas.bind("<B1-Motion>", self.mouse_handler.on_mouse_drag)
    self.canvas.bind("<ButtonRelease-1>", self.mouse_handler.on_mouse_up)
    self.canvas.bind("<MouseWheel>", self.mouse_handler.on_mouse_wheel)
    self.canvas.bind("<Configure>", self.mouse_handler.on_canvas_resize)

def _on_transform_update(self) -> None:
    # 変換データが更新された時のコールバック
    # 現在のページを再表示
    self._display_page(self.transform_manager.get_current_page_index())
```

## コンポーネント間の相互作用

### 1. イベントフロー

1. ユーザーがマウスイベント（ホイール、クリック、ドラッグなど）を実行
2. tkinterがイベントをビュークラスのイベントハンドラに渡す
3. ビュークラスが`MouseEventHandler`にイベントを直接委譲
4. `MouseEventHandler`がイベントを処理し、`TransformationManager`を通じて変換データを更新
5. `TransformationManager`のコールバック関数が呼び出され、ビューが更新される

### 2. データの流れ

```text
[ユーザーイベント] → [ビュークラス] → [MouseEventHandler] → [TransformationManager] → [変換データ更新] → [コールバック] → [ビュー更新]
```

### 3. 責任分担

- **MouseEventHandler**: マウスイベント処理と視覚的フィードバックの提供
- **TransformationManager**: 変換データの管理と更新
- **ビュークラス**: UI表示と更新、ユーザー入力の受け取り
- **コールバック関数**: ビューとコントローラー間の通信

## 実装例

### PDFビューアーでのズーム操作

1. ユーザーがマウスホイールを回転
2. tkinterがイベントを`MouseEventHandler.on_mouse_wheel`に直接渡す
3. `MouseEventHandler`がズーム係数を計算し、マウス位置を中心にズーム処理を行う
4. `MouseEventHandler`が`TransformationManager`を通じて変換データを更新
5. `TransformationManager`の`on_transform_update`コールバックが呼び出される
6. PDFページが新しいスケールで再描画される

### 比較モードでのズーム操作

1. ユーザーがマウスホイールを回転
2. イベントが`MouseEventHandler.on_mouse_wheel`に直接渡される
3. `MouseEventHandler`が全ての表示レイヤーに対して処理を行う
4. `TransformationManager`を通じて各レイヤーの変換データが更新される
5. `on_transform_update`コールバックが呼び出される
6. 全てのレイヤーが新しいスケールで再描画される

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
