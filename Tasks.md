# タスクリスト

## M3: メインタブ比較機能の再整備 (U001)

- 旧 `Tasks.md`（M2.1 の履歴）は `docs/tasks/M2_1_Tasks.md` へ退避した。
- このファイルは M3 以降の作業管理に使う。

### M3-001: `main.py` でメインタブを暫定再有効化する
- [✅] main tab が Notebook に表示されること。  
      **検証手順**: アプリを起動し、先頭に main tab が表示されることを確認する。  
- [✅] 開発中は他タブが一時的に無効化され、起動が軽くなること。  
      **検証手順**: 起動時に main tab 以外が生成されない構成になっていることを確認する。  

### M3-002: 共通パスブロックを main tab へ再利用する
- [✅] ベースPDF、比較PDF、出力フォルダの各入力が共通 path widget ベースで揃っていること。  
      **検証手順**: `BasePathEntry` ベースで 3 つの入力欄が表示され、値変更が反映されることを確認する。  
- [✅] ファイル/フォルダ選択ダイアログが前回フォルダを起点に開くこと。  
      **検証手順**: 一度選択後に再度ダイアログを開き、前回周辺フォルダが初期表示されることを確認する。  
- [✅] 比較ファイル入力を含めて設定保存・復元が機能すること。  
      **検証手順**: パスを設定して再起動し、各入力欄に前回値が復元されることを確認する。  
- [✅] ベースPDF/比較PDF のドラッグ&ドロップが利用できること。  
      **検証手順**: PDF を各入力欄へドロップし、対応するパスへ反映されることを確認する。  

### M3-003: main tab のテーマ適用を現行基盤へ揃える
- [✅] `apply_theme_color()` が main tab の主要 widget に反映されること。  
      **検証手順**: dark / light / pastel を切り替え、frame、label、button、canvas の配色が追従することを確認する。  
- [✅] path block の色味が既存タブと大きく乖離しないこと。  
      **検証手順**: `pdf_ope_tab` / `image_ope_tab` の path 入力系と比較し、main tab でも同系統の見た目になっていることを確認する。  

### M3-004: 比較表示・操作導線の最小実用構成を整える
- [✅] 解析ボタン、実行ボタン、保存ボタンの責務境界が整理されていること。  
      **検証手順**: `main_tab.py` 上で各ボタンの役割と今後の接続先が追える状態になっていることを確認する。  
- [✅] Canvas / page control / comparison view の再利用方針が `docs/milestone/M3_PLAN.md` と整合すること。  
      **検証手順**: 実装方針とドキュメントに齟齬がないことを確認する。  

---
更新日: 2026-03-15

      → M3 計画整理（2026-03-15）として、`views/main_tab.py`、`widgets/base_path_entry.py`、`controllers/drag_and_drop_file.py`、`utils/path_dialog_utils.py`、`main.py` を確認し、`docs/milestone/M3_PLAN.md` を新設した。方針は「main tab を一時再有効化」「他タブを一時停止して軽量起動」「共通 path block・D&D・設定保存の再利用」「現行テーマ基盤への追従」である。
      → M3 計画ファイル配置修正（2026-03-15）として、計画書の正しい保存先を `docs/milestone/M3_PLAN.md` に修正した。以後、M3 の実装方針・受け入れ基準・責務整理は同ファイルを正本とする。
      → M3-001 / M3-002 / M3-003 着手反映（2026-03-15）として、`main.py` を main tab 単独の軽量起動構成へ切り替え、`views/main_tab.py` に `WidgetsTracker` 登録、`apply_theme_color()` / `_config_widget()` の最小実装、ベースPDF・比較PDF・出力フォルダの `BasePathEntry` 整列、保存済みパス復元、比較ファイルを含むダイアログ初期フォルダ統一、D&D 接続を反映した。未完了は各解析処理・実行処理・比較表示部品の本接続である。
      → M3-004 最小接続反映（2026-03-16）として、`views/main_tab.py` に `PageControlFrame` と `MouseEventHandler` を最小接続し、比較ワークスペースのプレースホルダ描画、ページ表示状態、transform 値更新、マウスホイール/ドラッグ操作の受け口を追加した。あわせて解析ボタンは入力経路の存在確認、Process はワークスペース準備、Execute は最終比較パイプライン予約、Save は比較描画接続後の PDF 出力予約、という責務が canvas 上の表示と status 更新から追える状態に整理した。
      → M3-004 本接続反映（2026-03-16）として、`views/main_tab.py` に `Pdf2PngByPages` を用いた base/comparison PDF の実ページ変換、`tk.Canvas` への実 PNG 重ね描画、`PageControlFrame` / `MouseEventHandler` の実ページ状態連動、`PDFExportHandler` を使った Save 出力の実データ接続を追加した。これにより Analyze=PDF メタ情報確認、Process=PDF→PNG 変換と比較ワークスペース構築、Execute=変換済みページ再描画、Save=現在の transform を反映した PDF 出力、という責務で main tab の表示とボタン挙動が追える段階まで進んだ。
      ⇒ OK.