# ショートカットおよびガイダンス表示メソッド

このドキュメントは、PDFDiffCheckerアプリケーション内でショートカットガイド、操作ガイダンス、および通知を表示する役割を担うメソッドの概要を説明します。これらのメソッドは主に `controllers/mouse_event_handler.py` に配置されています。

## `controllers/mouse_event_handler.py` 内のメソッド

### 1. `show_guidance_text(self, text: str, duration: float = 2.0, is_rotation: bool = False, tag: Optional[str] = None) -> None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_mouse_down`, `on_mouse_drag`, `on_rotate_right`, `on_rotate_left`, `on_flip_vertical`, `on_flip_horizontal`, `__show_shortcut_guide`
* **目的:** キャンバス上に操作ガイダンステキスト（例：「Ctrl+ドラッグで回転」）を表示します。`duration` で指定された時間が経過すると消えるか、`duration` が0の場合や `tag` が指定された場合は永続的に表示されます。回転モード専用のスタイル (`is_rotation=True`) もサポートします。
* **引数:**
  * `text: str`: 表示するテキスト。
  * `duration: float`: テキストが消えるまでの秒数。0の場合、明示的に非表示にするか、同じタグを持つテキストで置き換えられるまで永続します。
  * `is_rotation: bool`: `True` の場合、回転モードガイダンス特有のスタイルを適用します。
  * `tag: Optional[str]`: テキスト要素を識別・管理するためのオプショナルなタグ。同じタグを持つテキストは互いに置き換えられます。
* **戻り値:** `None`
* **関連UI要素:** キャンバステキストアイテム、テキストの背景矩形。
* **評価と提案:**
  * `tag` 引数は、特定のガイダンスメッセージ（例: `ROTATION_GUIDANCE_TAG`）を管理するのに役立ちます。
  * 永続表示のための `duration=0` の動作は、`persistent: bool` のような、より明示的な引数名にすると分かりやすくなる可能性があります。

### 2. `hide_guidance_text(self, event: Optional[tk.Event] = None) -> None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_mouse_up`, `__exit_rotation_mode`, タイマーコールバック（期間満了時）。
* **目的:** 現在表示されているガイダンステキストを非表示にします。`show_guidance_text` で `tag` が使用された場合、特別に対象としない限り、タグ付けされた要素を非表示にしない可能性があります（現在の実装は `self.__guidance_text_id` に基づいて非表示にします）。
* **引数:** `event: Optional[tk.Event]` (通常は使用されません)。
* **戻り値:** `None`
* **評価と提案:** `show_guidance_text` と対になる標準的なメソッドです。複数のタグ付きガイダンスが共存できる場合、タグ付きガイダンス要素が正しく管理されるようにする必要があります。

### 3. `show_notification(self, message: str, duration: float = 2.0, warning: bool = False) -> None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_rotate_right`, `on_rotate_left`, `on_flip_vertical`, `on_flip_horizontal`, `reset_transformations`, `toggle_shortcut_guide`
* **目的:** 短時間表示される通知メッセージ（例：「右に90°回転しました」）をキャンバス上に表示します。警告スタイルもサポートします。
* **引数:**
  * `message: str`: 通知メッセージ。
  * `duration: float`: 通知が消えるまでの秒数。
  * `warning: bool`: `True` の場合、警告スタイル（例：異なる背景色）で通知を表示します。
* **戻り値:** `None`
* **関連UI要素:** キャンバステキストアイテム、テキストの背景矩形。
* **評価と提案:** `show_guidance_text` と似ていますが、こちらは一時的なフィードバックが主目的です。区別は明確です。

### 4. `hide_notification(self) -> None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** タイマーコールバック（期間満了時）。
* **目的:** 現在表示されている通知メッセージを非表示にします。
* **引数:** なし。
* **注意:** tkinterの`after`メソッドは文字列型のタイマーIDを返し、`after_cancel`メソッドも文字列型の引数を期待します。内部でタイマーIDを管理する際は、この型の一貫性に注意が必要です。
* **戻り値:** `None`
* **評価と提案:** `show_notification` と対になる標準的なメソッドです。

### 5. `__show_shortcut_guide(self, event: Optional[tk.Event] = None) -> None:` (プライベート)

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `toggle_shortcut_guide`, `on_mouse_down` (回転モード開始時に条件付きで)。
* **目的:** キーボードショートカットの一覧をキャンバス上に表示します。内容は `message_manager.get_message('M049')` を使用して取得します。
* **引数:** `event: Optional[tk.Event]` (通常は使用されません)。
* **戻り値:** `None`
* **関連UI要素:** キャンバステキストアイテム（ガイド用）、背景矩形。
* **評価と提案:** ショートカットヘルプ表示のコアロジックです。プライベートであるため、直接の使用は `toggle_shortcut_guide` によって制御されます。

### 6. `__hide_shortcut_guide(self, event: Optional[tk.Event] = None) -> None:` (プライベート)

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `toggle_shortcut_guide`, `__exit_rotation_mode`。
* **目的:** 表示されているショートカットガイドを非表示にします。
* **引数:** `event: Optional[tk.Event]` (通常は使用されません)。
* **戻り値:** `None`
* **評価と提案:** `__show_shortcut_guide` と対になる標準的なメソッドです。

### 7. `toggle_shortcut_guide(self, event: Optional[tk.Event] = None) -> str:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_key_press` (Ctrl+? ショートカットを処理)。
* **目的:** ショートカットガイドの表示・非表示を切り替えます。また、ガイドがユーザーの直接的な操作によって表示/非表示にされたかを追跡します (`self.__user_toggled_shortcut_guide`)。
* **引数:** `event: Optional[tk.Event]` (通常はキープレスイベント)。
* **戻り値:** `"break"` (Tkinterでのさらなるイベント伝播を防ぐため)。
* **評価と提案:** ショートカットガイドの表示を制御するための主要な公開APIです。

### 8. `on_flip_horizontal(self, event: tk.Event | None = None) -> str | None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_key_press` (Ctrl+H ショートカットを処理)。
* **目的:** 現在表示されているレイヤーの画像を水平方向に反転します。`image_operations.py`の`flip_horizontal`メソッドを使用してPILの`transpose`メソッドで画像自体を反転させます。
* **引数:** `event: Optional[tk.Event]` (通常はキープレスイベント)。
* **戻り値:** `"break"` (イベント伝播を防ぐ場合) または `None`。
* **評価と提案:** 当初は座標の反転による実装でしたが、PILの`transpose`メソッドを使用した正確な画像反転処理に改善されました。

### 9. `on_flip_vertical(self, event: tk.Event | None = None) -> str | None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_key_press` (Ctrl+V ショートカットを処理)。
* **目的:** 現在表示されているレイヤーの画像を垂直方向に反転します。`image_operations.py`の`flip_vertical`メソッドを使用してPILの`transpose`メソッドで画像自体を反転させます。
* **引数:** `event: Optional[tk.Event]` (通常はキープレスイベント)。
* **戻り値:** `"break"` (イベント伝播を防ぐ場合) または `None`。
* **評価と提案:** 当初は座標の反転による実装でしたが、PILの`transpose`メソッドを使用した正確な画像反転処理に改善されました。

### 10. `__exit_rotation_mode(self) -> None:` (プライベート - 関連メソッド)

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** `on_mouse_down`, `on_mouse_up`, `on_key_release`。
* **目的:** 回転モードを終了する際にUIと状態をクリーンアップします。これには、回転特有のガイダンス（`self.__canvas_ref.delete(self.ROTATION_GUIDANCE_TAG)`経由）、回転中心の点、およびユーザーによって切り替えられていなければショートカットガイド（`__hide_shortcut_guide`経由）の非表示が含まれます。
* **引数:** なし。
* **戻り値:** `None`
* **評価と提案:** 回転モードのクリーンアップを中央集権化しており、これは良い習慣です。ユーザーがショートカットガイドを明示的に開いたかどうかを正しく考慮してから閉じるかどうかを決定します。

## 命名と重複に関する概要

* 命名規則（例：`show_...`/`hide_...`、プライベートメソッドの先頭アンダースコア）は概ね一貫しており、一般的なPythonの慣行に従っています。
* `show_guidance_text` と `show_notification` は同様の機能（キャンバスへのテキスト表示）を持ちますが、意味的な目的（ガイダンスか通知か）とスタイルオプションによって区別されており、これは分離を正当化します。
* ショートカットガイドの表示管理は、`toggle_shortcut_guide` とその基盤となるプライベートメソッド（`__show_shortcut_guide`, `__hide_shortcut_guide`）を通じて行われており、明確で一般的なパターンです。

### 8. `on_canvas_resize(self, event: Optional[tk.Event] = None) -> None:`

* **定義場所:** `controllers/mouse_event_handler.py`
* **主な呼び出し元:** キャンバスの `<Configure>` イベントバインディング
* **目的:** キャンバスのサイズが変更されたときに呼び出され、ショートカットガイドが表示されている場合は再描画して適切な位置に配置します。
* **引数:** `event: Optional[tk.Event]` - リサイズイベント情報（オプション）
* **戻り値:** `None`
* **関連UI要素:** ショートカットガイドのキャンバスアイテム
* **評価と提案:** キャンバスのリサイズに応じてUIを適切に調整するための重要なメソッドです。ウィンドウサイズ変更時のユーザーエクスペリエンスを向上させます。

これらの主要なガイダンスおよびショートカット表示メソッドに関して、不必要な重複や紛らわしい命名に関する当面の懸念は確認されませんでした。システムは論理的に構成されているように見えます。
