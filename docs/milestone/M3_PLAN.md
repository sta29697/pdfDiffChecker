# M3 Plan — メインタブ比較機能の再有効化と共通UI再利用

## 目的
- `views/main_tab.py` を、現在のテーマ基盤と共通パスUIに追従した実用可能なメインタブとして再整備する。
- 既存タブで確立済みの `BasePathEntry` / ドラッグ&ドロップ / フォルダ記憶 / テーマ反映方式を再利用し、重複実装を避ける。
- 開発中は `main.py` を main tab 中心の軽量起動構成へ一時的に切り替え、起動待ち時間を抑えながら段階的に実装する。

## 現状整理
- `CreateComparisonFileApp` はベース/比較/出力のパス入力、解析ボタン、実行ボタン、Canvas を持ち、`apply_theme_color()` / `_config_widget()` の最小実装、設定復元、D&D 接続、軽量起動向けの main tab 有効化までは反映済みである。
- ファイルパス入力には既に `BasePathEntry` が使われている一方、`BasePathSelectButton` は旧来の `filedialog` 直呼び寄りで、`pdf_ope_tab.py` / `image_ope_tab.py` が利用している `ask_file_dialog()` / `ask_folder_dialog()`・共有設定・D&D 連携の流儀と完全には揃っていない。
- `main.py` では開発中の一時構成として main tab のみを有効化し、他タブは起動時間短縮のためコメントアウトしている。
- 既存の色反映は `ColorThemeManager`、`WidgetsTracker`、`EventBus` ベースで動いているため、M3 側でもこの経路に乗せる必要がある。

## スコープ
- 対象:
  - `views/main_tab.py`
  - `main.py`
  - 必要に応じた共通 widget / controller の軽微な補助修正
- 非対象:
  - U006 の DPI-only 仕様追加そのもの
  - PDF比較アルゴリズムの大規模刷新
  - 完全なリリース前最適化

## 実装方針

### 1) メインタブの起動経路を暫定復帰
- `main.py` で main tab を Notebook に再追加する。
- 開発期間中は他タブを一時的にコメントアウトし、`CreateComparisonFileApp(main_tab, settings_manager)` を優先して起動する。
- Notebook コンテナ背景更新も main tab を含む最小構成へ合わせる。

### 2) 共通パス入力ブロックの再利用統一
- ベースPDF、比較PDF、出力フォルダの3系統は `BasePathEntry` を継続利用する。
- ファイル選択は `ask_file_dialog()` / `ask_folder_dialog()` を使い、`resolve_initial_dir(...)` と保存済み設定値から初期フォルダを決める。
- ベース/出力だけでなく、比較ファイルにも `entry_setting_key` ベースの永続化を明示的に適用する。
- D&D は `DragAndDropHandler.register_drop_target(...)` を main tab の入力部品へ接続する。
- 既存タブの `_sync_shared_paths_from_settings()` 相当の同期処理を main tab に導入し、起動直後やタブ再表示時に設定値から復元する。

### 3) テーマ反映の現行方式へ追従
- `CreateComparisonFileApp.apply_theme_color()` を実装し、少なくとも frame / label / button / canvas の配色を現在テーマから更新する。
- `BasePathEntry`、`BasePathSelectButton`、`ColorThemeChangeButton` 等、個別にテーマ適用可能な子 widget は既存の `apply_theme_color()` を呼び出して反映する。
- Canvas 背景は `Notebook.tab_bg` と `Notebook.bg` のフォールバック方針を維持する。
- main tab でも `WidgetsTracker` / `EventBus` と競合しないよう、「最終見た目決定器を一箇所に寄せる」方針を採る。

### 4) 比較画面の既存部品への寄せ
- 現在 `frame_main3` に直接 `tk.Canvas` を置いているが、必要に応じて `comparison_and_adjustment_canvas.py`、`page_control_frame.py`、`mouse_event_handler.py` の既存責務へ寄せる。
- まずは「起動・テーマ反映・入力導線・設定保存」が成立する最小構成を優先し、その後に比較表示の責務整理へ進む。

### 5) ボタン画像の遊び心対応
- 実行ボタンは既存の `BaseButtonImageChangeToggleButton` を活かしつつ、画像差し替えや hover/toggle の演出余地を残す。
- 画像資産変更が必要な場合も、まずは現在の部品で差し替え可能な形を保ち、ロジックと見た目変更を分離する。

## タスク分解

### M3-001: 起動経路の再有効化
- [ ] `main.py` で main tab を一時有効化する
- [ ] 他タブを一時コメントアウトして軽量起動にする
- [ ] 起動直後にクラッシュしないことを確認する

### M3-002: 共通パスブロックの再利用
- [ ] main tab のベース/比較/出力パスで共通 widget の責務を整理する
- [ ] ファイル/フォルダ選択ダイアログの初期フォルダと設定保存を統一する
- [ ] D&D と設定復元を main tab に接続する

### M3-003: テーマ適用の実装
- [ ] `apply_theme_color()` と `_config_widget()` の責務を定義する
- [ ] main tab の主要 widget が dark / light / pastel に追従する
- [ ] Canvas と path block の配色が他タブと乖離しないようにする

### M3-004: 比較表示・操作導線の整理
- [ ] 既存 Canvas 実装と共通部品の再利用方針を確定する
- [ ] ページ操作・解析・保存の責務の仮置き境界を整理する
- [ ] 最小実用フローを明文化する

## 受け入れ基準
- main tab がアプリ起動時に表示される。
- ベースPDF、比較PDF、出力フォルダの選択値が保存・復元される。
- ベースPDF/比較PDFの入力導線で D&D が利用できる。
- main tab の主要UIが dark / light / pastel の各テーマで視認可能な配色になる。
- 他タブを無効化した軽量構成で、main tab の反復開発が可能になる。

## 実装メモ
- `CreateComparisonFileApp` の `settings` 引数には `main.py` の `settings_manager = usm()` を渡す。
- `BasePathEntry` は `entry_setting_key` を通じて自動保存するため、main tab 側は `path_var` と業務用 `StringVar` の同期漏れに注意する。
- 既存タブで使われている `resolve_initial_dir(...)`、`ask_file_dialog()`、`ask_folder_dialog()` の組み合わせを優先し、`filedialog` 直呼びは増やさない。
- テーマ反映は、個別 widget への場当たり的な色上書きを増やすよりも、main tab 全体の最終反映点を整理して集約する。

## 進捗メモ
- 2026-03-16: M3-004 の第一段として、`views/main_tab.py` に `PageControlFrame` と `MouseEventHandler` を直接最小接続した。
- 2026-03-16: この段階では `comparison_and_adjustment_canvas.py` への全面移行は行わず、既存の main tab 入力導線・設定保存・テーマ反映を維持したまま、`frame_main3` 上の `tk.Canvas` に対してページ操作枠と transform 操作の責務だけを先行接続している。
- 2026-03-16: ボタン責務は暫定的に、解析=`base/comparison` の入力経路確認、Process=比較ワークスペース準備、Execute=最終比較処理の予約、Save=比較描画接続後の PDF 出力、として canvas/status 表示から追跡可能にした。
- 2026-03-16: 次段では、実 PDF ページ変換結果を main tab の canvas 描画へ流し込み、プレースホルダ描画を実表示へ置き換える。その際に `comparison_and_adjustment_canvas.py` を再利用するか、main tab 側で現在の最小接続を維持したまま描画責務のみ寄せるかを再評価する。
- 2026-03-16: M3-004 の本接続として、`views/main_tab.py` に `Pdf2PngByPages` ベースの PDF→PNG 変換経路を追加し、base / comparison の各ページを main tab の `tk.Canvas` へ重ね描画するよう更新した。
- 2026-03-16: `PageControlFrame` と `MouseEventHandler` はプレースホルダ状態ではなく、変換済みページ一覧・page index・transform 情報と直接連動するよう切り替え、Process 後にページ送りと transform 再描画が実ページで追える構成にした。
- 2026-03-16: ボタン責務も本接続後の挙動へ更新し、Analyze=PDF メタ情報確認、Process=PDF→PNG 変換と比較ワークスペース構築、Execute=変換済みページ再描画、Save=`PDFExportHandler` による現 transform 反映 PDF 出力、という整理に改めた。
