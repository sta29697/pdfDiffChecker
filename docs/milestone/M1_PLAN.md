# M1 Plan (Draft)

## 目的 / Goal
- M1では、Canvas上の表示・操作（拡大縮小、移動、回転、ショートカット等）を安定動作させ、PDF Operationsタブで整備した機能をメイン側でも再利用できる状態にする。
- (New Feature) と明記された項目は未実装前提のため、本計画では「実装対象/仕様整理」として扱う。

## 前提
- 「PDF Operations」タブの各種機能は、将来的にメインタブでも共通利用する。
- メッセージは `./configurations/message_codes.json` と `message_manager.py` の言語モードに従う。

## 実装状況の確認（コード監査結果）

### 5. Canvas上でマウスホイールで拡大縮小
- **実装**: あり
- **関連**:
  - `controllers/mouse_event_handler.py`: `MouseEventHandler.on_mouse_wheel()`
  - `views/pdf_ope_tab.py`: `PDFOperationApp._on_mouse_wheel()` → `mouse_handler.on_mouse_wheel()`
  - `widgets/comparison_and_adjustment_canvas.py`: `PDFCompareCanvas.__bind_mouse_events()` → `mouse_handler.on_mouse_wheel()`
- **懸念/改善候補**:
  - `views/pdf_ope_tab.py` では `_on_mouse_wheel()` 内で `_rebind_mouse_wheel()` を毎回実行しており、イベント処理が過剰になる可能性がある（フリーズ要因の切り分け対象）。

### 6. Canvas上でマウスドラッグで表示画像を移動
- **実装**: あり
- **関連**:
  - `controllers/mouse_event_handler.py`: `MouseEventHandler.on_mouse_drag()` の「Standard image movement」
  - `views/pdf_ope_tab.py`: `<B1-Motion>` binding
  - `widgets/comparison_and_adjustment_canvas.py`: `<B1-Motion>` binding

### 7. Ctrl+クリックで回転中心設定、Ctrl維持でドラッグ回転、回転モード表示
- **実装**: 部分的にあり
- **関連**:
  - 回転中心設定/回転ドラッグ:
    - `controllers/mouse_event_handler.py`: `on_mouse_down()` / `on_mouse_drag()` / `on_mouse_up()`
  - 回転モード表示:
    - `controllers/mouse_event_handler.py`: `_show_feedback_circle()`（中心点の可視化）
    - `controllers/mouse_event_handler.py`: `_show_guidance_text()`（下部ガイダンス表示）
    - 使用メッセージコード: **M042**（"Rotation mode - drag to rotate"）
- **仕様差分（要確認）**:
  - ご提示仕様では「回転モード - ドラッグして回転」を **M044** と記載されているが、
    現在 `message_codes.json` では該当文言は **M042** に割り当てられている。
  - 併せて、M044 は現状「右に90°回転しました」になっており、Item 9 の仕様（Ctrl+R）と整合している。
  - **結論**: 実装側は M042 を使用しており、メッセージコード指定が仕様上ズレている可能性があるため、M1で仕様確定が必要。
- **既知不具合（ユーザー指摘）**:
  - 「他の操作をすると固まる」現象があるとのこと。
  - `views/pdf_ope_tab.py` の `_setup_mouse_events()` で `<Control-r>` を `_reset_transform()` に割り当てており、
    `MouseEventHandler` 側の Ctrl+R（右回転）と競合する可能性がある（フリーズ要因の切り分け対象）。
  - 回転中心の赤点やガイダンスが、ページ再描画（Canvas更新）で消える/ずれる可能性がある。
  - 画面座標（Y下向き）の扱いにより、ドラッグ方向と回転方向が一致しない可能性がある。

- **対策（実装済み）**:
  - 回転角の計算を「画面座標（Y下向き）→数学座標（Y上向き）」へ補正し、角度アンラップで最小回転方向へ追従するよう変更。
  - 最小刻みを 0.1° とし、微小な逆回転ジッタを抑制。
  - 再描画後に回転中心の赤点を再生成し、Ctrl解放まで維持するようにした。
  → Ctrl押下中の再クリックで回転中心（赤点）が更新されないようにし、最初のクリック位置に固定してCtrl解放まで維持するよう修正。
  → 回転中心を画像座標系（原画像中心からのオフセット）で管理し、ズーム/回転/パン後も画像上の同一点に追従するよう修正。
  → ピボット補正付きtranslation調整を実装し、赤点を中心として画像が回転するよう修正。
  → 回転角度の量子化を floor→round に変更し、0.1°未満の変化を無視するヒステリシスでジッタを解消。
  → ガイダンス表示を赤字・赤枠・透明背景に変更。
  → ±20°振動の根本原因: ドラッグ中に毎フレーム回転中心Canvas座標を再計算し座標変換誤差がフィードバックループ化。修正: ドラッグ中は回転中心Canvas座標を固定。
  → 増分累積方式を廃止し絶対角度差分方式に変更（浮動小数点誤差の累積を排除）。
  → 回転更新を~30fpsにレートリミットしイベントキュー滞留を防止。

### 8. M049 のショートカットガイダンスを Ctrl+? で表示/非表示
- **実装**: あり（ただし見た目が仕様と不一致）
- **関連**:
  - `controllers/mouse_event_handler.py`: `<Control-question>` で `_toggle_shortcut_help()`
  - 表示文言: `message_codes.json` の **M049**
- **仕様差分（要修正）**:
  - 仕様: 背景=薄い黄色、枠=少し濃い黄色、文字=緑
  - 現状: 背景=黒(stipple)、枠=白、文字=黄

- **対策（実装済み）**:
  - 背景=#fff2a8／枠=#e6c200／文字=#008000 へ修正。
  - 表示位置を Canvas の可視領域左上＋padding に固定し、ズーム/スクロールで位置が崩れないようにした。
  → 表示位置をCanvas可視領域の右上（outer_pad=12）に変更。
  - 入力PDF切替時は Canvas overlay（タイトル/ガイド等）をクリアし、ページ切替時は維持（Batch編集のため）。

### 9. ショートカット動作（Ctrl+R/L/V/H/B）と通知表示
- **動作（回転/反転/リセット）**: 実装あり
  - `controllers/mouse_event_handler.py`:
    - Ctrl+R: `_on_rotate_right()` → **M044**
    - Ctrl+L: `_on_rotate_left()` → **M045**
    - Ctrl+V: `_on_flip_vertical()` → **M046**
    - Ctrl+H: `_on_flip_horizontal()` → **M047**
    - Ctrl+B: `_on_reset_transform()` → **M048**
- **通知表示（見た目）**: 仕様と不一致
  - 仕様: Canvas上部中央に「赤字・赤枠・透明背景」の通知
  - 現状: `_show_notification()` が「黄色文字のみ」で枠/背景なし

- **対策（実装済み）**:
  - 通知を「赤字・赤枠・透明背景」で 1秒以上表示し、連打時は前回タイマーを cancel するようにした。
  - Canvas再描画で通知が消えないよう、state更新時にoverlayをクリアしない方針へ変更し、可視領域上部中央に固定表示するようにした。

### 10. 「空白ページ挿入」ボタンで次ページに空白を挿入
- **実装**: あり（ただし実装箇所が複数系統）
- **関連**:
  - `views/pdf_ope_tab.py`: `_on_insert_blank_page()`（A4固定サイズ 595x842, white）
  - `widgets/comparison_and_adjustment_canvas.py`: `__insert_blank_page()`（1000x1400, alpha=0）
- **注意点**:
  - PDF Operations と Compare Canvas で「空白ページサイズ/背景」が異なるため、
    M1で共通仕様（ページサイズ、背景色、DPI/メタ情報連携）を決めて統一するのが望ましい。

### 11. （新機能）「表示ページ削除」ボタン追加（U063）
- **実装**: 未実装
- **補足**:
  - `message_codes.json` に U063 は現時点で存在しない（追加が必要）。

### 12. （新機能）右側ボタンエリアに座標/角度/移動距離の表示・入力UI追加（U064-U069）
- **実装**: 実装済み
- **補足**:
  - `message_codes.json` に U064-U069 追加（Transform/X:/Y:/Angle:/Scale:/Apply）。U061-U063はM1-007用に予約。
 → `PageControlFrame` に変換情報セクション（セパレータ＋ヘッダ＋X/Y/Angle/Scale Entry）を追加。
 → `_display_page()` 末尾で `update_transform_info()` を呼び出しリアルタイム反映。Enterで入力値を適用。

### 13. フッターとしてメタ情報（DPI、サイズ等）を小さく表示
- **実装**: 未実装（ただしメタ情報抽出は一部あり）
- **関連**:
  - `controllers/file2png_by_page.py`: `_extract_metadata()` で `file_info.file_meta_info` に
    Title/Author/.../NumberOfPages/Encrypted 等を格納。
- **提案（M1での表示候補）**:
  - DPI: 変換時に指定した dpi（例: `Pdf2PngByPages.convert_to_grayscale_pngs(dpi=...)` の値）
  - サイズ: 画像ピクセル（`pil_image.width x pil_image.height`）
  - 用紙推定: A3/A4 など（可能なら画像比率とDPIから概算）
  - 情報が無い場合: "-" を表示

## 要求 3: コピー保護PDF（New Feature）での操作禁止（実装対象）

### 要件
- コピー保護フラグ付きPDFは Canvas で表示できる。
- ただし「操作」は禁止し、操作が試みられたら Canvas 中央に警告を表示する。
  - 枠: 赤
  - 背景: 薄い赤
  - 文字: 白
  - 文言: "Operation not possible due to copy-protected file"（言語モードでローカライズ）
- ページナビゲーションのみ許可（表示目的のため）。

### 現状
- `file_meta_info` には `Encrypted` が格納される。
- コピー保護の概念（フラグ）と、それに基づく操作禁止は未実装。

→ コピー保護PDFでは「空白ページ挿入」「完成」ボタンを無効化し、テーマ更新等で state が上書きされないよう state をテーマ適用から除外＋状態再適用を実装。

### M1 実装案
- `controllers/file2png_by_page.py` の `_extract_metadata()` でコピー保護判定用のメタ（例: `CopyProtected`）を追加。
  - 暫定案: `reader.is_encrypted` をベースにフラグ化（今後、権限ビット等へ拡張）。
- Canvas操作（ホイール、ドラッグ、Ctrl系変換、空白挿入、完了/書き出し等）を実行する前にフラグを確認し、禁止時は
  - 操作を実行せず
  - Canvas中央に警告を表示
- 警告表示用に `message_codes.json` の `message_codes` に新規コードを追加（例: **M055**）。

## 要求 4: （新機能）Batch All Pages
- **実装**: 未実装
- **メッセージ**:
  - U061: mixed orientations warning（OK/Cancel）
  - U062: mixed sizes warning（OK/Cancel）
- **補足**:
  - `message_codes.json` に U061/U062 は現時点で存在しないため追加が必要。

### 14. ショートカットガイド（ヘルプオーバーレイ）の表示制御改善
- **実装**: 未実装
- **現状**: Ctrl+? でショートカットガイドを表示/非表示できるが、ページ切替や再描画のたびにガイドが再表示されてしまう。
- **原因**: `_display_page()` → `refresh_overlay_positions()` 等の再描画パスで、ガイドの表示状態フラグが正しく保持されない。
- **対策案**:
  - 表示/非表示状態を明示的なフラグ（例: `__shortcut_help_visible`）で管理し、`refresh_overlay_positions()` ではフラグがTrueの場合のみ再描画する。
  - 将来的に他のタブでも同じショートカットガイド機構を使うため、表示制御ロジックを汎用化しておく。
- **検証**: ページ切替・ズーム・回転操作後にガイドの表示状態が意図通り維持されるか手動確認。

## 追加メモ（M1での修正候補）
- `views/pdf_ope_tab.py` のキーバインド競合（`bind_all('<Control-r>', _reset_transform)` 等）は、
  `MouseEventHandler` のショートカットと矛盾するため整理が必要。
- ショートカット表示（M049）や通知表示（M044〜M048）の見た目は、仕様に合わせて Canvas overlay の描画方式へ統一する。

---
更新日: 2026-02-07
