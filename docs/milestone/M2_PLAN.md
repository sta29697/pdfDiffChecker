# M2 Plan — ファイル拡張子・サイズ変換タブ (U006)

## 目的 / Goal
- `main.py` でコメントアウトされている「ファイル拡張子とサイズ」タブ（U006）を有効化する。
- `views/image_ope_tab.py`（`ImageOperationApp` クラス）を再設計し、以下の機能を提供する:
  1. **拡張子変換** — 画像形式間の変換（PNG, JPEG, BMP, GIF, TIFF, WebP 等）。
  2. **画像サイズ変換** — ユーザー指定の寸法へのリサイズ。
- αチャンネル喪失や画質劣化が発生する場合は、処理前にユーザーへ通知し「OK」確認を取る。
- コピー保護ファイルへの操作は「PDF操作」タブと同様に禁止し、通知＋ボタン無効化を行う。

## 前提
- タブ名のメッセージコードは既存: `U006`（"File Extension and Size" / "ファイル拡張子とサイズ"）。
- 既存ウィジェット用メッセージコード: `U012`（幅）, `U013`（高さ）, `U014`（変換）。
- テーマJSON に `width_size_set_label`, `height_size_set_label`, `convert_image_button` のエントリが存在。
- `DragAndDropHandler` は `controllers/drag_and_drop_file.py` から再利用可能。
- 入力ファイル・出力フォルダは「PDF操作」タブと共有する（`user_settings.json` 経由）。
- ドラッグ&ドロップで入力・出力欄への投入にも対応する。

## ライブラリ・ライセンス調査

### 現在使用中のライブラリ

| ライブラリ | バージョン | ライセンス | 商用利用 | コード開示義務 | 備考 |
|-----------|-----------|-----------|---------|--------------|------|
| **Pillow** | 12.0.0 | MIT-CMU (HPND) | ✅ 可 | ❌ 不要 | PIL のフォーク。著作権表示の保持のみ必要。コピーレフトなし。 |
| **pypdfium2** | 5.0.0 | BSD-3-Clause + Apache-2.0 | ✅ 可 | ❌ 不要 | PDFium (Google Chrome の PDF エンジン) の Python バインディング。 |
| **pypdf** | 6.1.3 | BSD-3-Clause | ✅ 可 | ❌ 不要 | Pure-Python PDF ライブラリ。メタデータ抽出に使用。 |
| **tkinterdnd2** | 0.4.3 | MIT | ✅ 可 | ❌ 不要 | Tkinter 用ドラッグ&ドロップ拡張。 |

### 結論
- **現在のすべての依存ライブラリは Permissive ライセンス**（MIT, BSD, Apache-2.0, HPND）である。
- GPL, AGPL, LGPL 等のコピーレフト（コード開示義務あり）ライセンスのライブラリは**一切使用していない**。
- M2 で追加の外部ライブラリは不要（Pillow 12.0.0 が PNG, JPEG, BMP, GIF, TIFF, WebP, ICO, TGA, PPM 等を標準サポート）。

### 拡張形式（将来検討）に関するライセンスリスク

| 形式 | 必要ライブラリ | ライセンス | リスク |
|------|--------------|-----------|--------|
| **AVIF** | `pillow-avif-plugin` / `pillow-heif` | libavif: BSD-2-Clause, ただしコーデック (dav1d: BSD-2, aom: BSD-2, rav1e: BSD-2) | ⚠ コーデック構成次第。現時点では安全だが、将来のバージョンで依存関係が変わる可能性あり。 |
| **HEIF/HEIC** | `pillow-heif` | BSD-3-Clause, ただし **libheif が LGPL-3.0** | ⚠ **LGPL-3.0**: 動的リンクなら商用利用可だが、静的リンクや改変時にソースコード開示義務が発生する可能性あり。**M2 では採用しない**。 |
| **JPEG XL** | `pillow-jxl-plugin` | BSD-3-Clause (libjxl) | ✅ 安全。ただし Pillow プラグインの成熟度が低い。 |

→ **M2 では Pillow 標準サポート形式のみを対象とし、追加ライブラリが必要な形式（AVIF, HEIF, JPEG XL）は対象外とする。**

## 対応拡張子

### Pillow 12.0.0 の機能確認結果（本プロジェクト環境）
```
webp: True, jpg: True, zlib: True, libtiff: True, jpg_2000: True
```

### M2 対応形式一覧

| 形式 | 拡張子 | 読込 | 書出 | αチャンネル | 可逆圧縮 | 色深度 | 備考 |
|------|--------|------|------|------------|---------|--------|------|
| **PNG** | `.png` | ✅ | ✅ | ✅ | ✅ | 8/16bit | 標準的な可逆形式。Web・印刷どちらにも対応。 |
| **JPEG** | `.jpg`, `.jpeg` | ✅ | ✅ | ❌ | ❌ (非可逆) | 8bit | 写真向け。αチャンネル非対応。 |
| **BMP** | `.bmp` | ✅ | ✅ | ❌ (※) | ✅ (無圧縮) | 8/24bit | Windows標準。αは保存不可（32bit BMPは限定的）。 |
| **GIF** | `.gif` | ✅ | ✅ | ✅ (1bit) | ✅ | 8bit (256色) | アニメーション対応（M2では静止画のみ）。パレット形式。 |
| **TIFF** | `.tif`, `.tiff` | ✅ | ✅ | ✅ | ✅ | 8/16/32bit | 印刷・DTP向け。多様な圧縮形式をサポート。 |
| **WebP** | `.webp` | ✅ | ✅ | ✅ | ✅/❌ | 8bit | Google開発。可逆/非可逆両対応。αチャンネル対応。 |
| **ICO** | `.ico` | ✅ | ✅ | ✅ | ✅ | 8/32bit | アイコン用。複数サイズ格納可能。M2では単一サイズ変換のみ。 |
| **TGA** | `.tga` | ✅ | ✅ | ✅ | ✅ | 8/24/32bit | ゲーム・映像向け。αチャンネル対応。 |

### 将来対応候補（M2 対象外）
- **AVIF** (`.avif`) — 高圧縮・高画質だが追加ライブラリ必要。
- **HEIF/HEIC** (`.heif`, `.heic`) — Apple 標準形式だが **libheif が LGPL-3.0** のためライセンスリスクあり。
- **JPEG XL** (`.jxl`) — 次世代形式だが Pillow プラグインが未成熟。
- **JPEG 2000** (`.jp2`) — Pillow が `openjpeg` 経由でサポート（本環境で利用可）。需要があれば追加検討。

## 実装状況の確認（コード監査結果）

### タブ登録 (`main.py`)
- **Line 930**: `image_ope_tab = tk.Frame(notebook)` — コメントアウト中。
- **Line 979**: `notebook.add(image_ope_tab, ...)` — コメントアウト中。
- `TabContainerBgUpdater` のコンテナリストに `image_ope_tab` が含まれていない（line 968）。
- `ImageOperationApp` の import と生成が `main()` 内に存在しない。

### ビュー (`views/image_ope_tab.py`)
- **レイアウト**: 3つの縦フレーム（`frame_main0`, `frame_main1`, `frame_main2`）。
  - `frame_main0`: 言語コンボ＋テーマ変更ボタン。
  - `frame_main1`: 入力ファイルパス Entry/Button ＋ 出力フォルダパス Entry/Button ＋ 画像色変更ボタン。
  - `frame_main2`: Canvas（プレビュー）＋ サイズ変換コントロール（幅/高さ Entry ＋ 変換ボタン）。
- **拡張子変換**: `image_file_format_conversion()` と `standardization_image_file_extensions()` が存在するが骨格のみ（GIF→PNGパスのみ、UIトリガーなし）。
- **サイズ変換**: `_convert_image()` が `ImageSizeConverter.resize_image()` を呼ぶが、劣化警告なし。
- **ドラッグ&ドロップ**: Canvas上のみ。パス入力欄には未対応。
- **コピー保護対応**: 未実装。
- **問題点**:
  - `_on_output_folder_select()` メソッド本体内にサイズ変換ウィジェット生成コードが混入（インデント不正により、フォルダ選択時に生成される状態）。
  - `NullProgressCallback` と `ImageSizeConverter` がモジュール末尾のインラインクラス → リファクタリング必要。
  - 拡張子変換UIなし（変換元/変換先フォーマット選択、変換ボタン）。
  - α喪失・劣化警告なし。
  - 拡張子変換後のプレビュー更新なし。

### 関連ファイル
| ファイル | 役割 |
|---------|------|
| `views/image_ope_tab.py` | タブビュー（主要対象） |
| `main.py` | タブ登録、Notebook セットアップ |
| `controllers/drag_and_drop_file.py` | `DragAndDropHandler.register_drop_target()` |
| `controllers/file2png_by_page.py` | `BaseImageConverter`（拡張子変換で使用） |
| `controllers/image_operations.py` | `ImageOperations` クラス（移動/回転/ズーム — M2では不要） |
| `widgets/convert_image_button.py` | `ConvertImageButton`（BaseButton サブクラス） |
| `widgets/base_image_color_change_button.py` | カラーピッカーボタン（M2では除去/用途変更の可能性） |
| `widgets/base_path_entry.py` | 設定永続化付きパス入力 Entry |
| `widgets/base_path_select_button.py` | ダイアログ付きパス選択ボタン |
| `configurations/message_codes.json` | UI/ログ/エラー メッセージコード |
| `themes/dark.json`, `light.json`, `pastel.json` | テーマカラーエントリ |

## 変換時の警告マトリクス

| 変換元 → 変換先 | PNG | JPEG | BMP | GIF | TIFF | WebP | ICO | TGA |
|----------------|-----|------|-----|-----|------|------|-----|-----|
| **PNG**        | —   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | ✓    | ✓   | ✓   |
| **JPEG**       | ✓   | —    | ✓   | ⚠C  | ✓    | ✓    | ✓   | ✓   |
| **BMP**        | ✓   | ⚠Q   | —   | ⚠C  | ✓    | ✓    | ✓   | ✓   |
| **GIF**        | ✓   | ⚠Q   | ✓   | —   | ✓    | ✓    | ✓   | ✓   |
| **TIFF**       | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| —    | ✓    | ✓   | ✓   |
| **WebP**       | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | —    | ✓   | ✓   |
| **ICO**        | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | ✓    | —   | ✓   |
| **TGA**        | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | ✓    | ✓   | —   |

- **⚠α** = αチャンネル喪失警告（RGBA画像の場合のみ。RGB画像なら警告不要）
- **⚠Q** = 画質劣化警告（可逆→非可逆変換）
- **⚠C** = 色深度削減警告（256色パレットへの変換）
- **✓** = 安全な変換（警告不要）

## 実装計画

### M2-001: `main.py` でのタブ有効化
- `image_ope_tab` フレーム作成と `notebook.add(...)` のコメントアウトを解除。
- `TabContainerBgUpdater` のコンテナリストに `image_ope_tab` を追加。
- `views.image_ope_tab` から `ImageOperationApp` を import し、フレーム内で生成。
- タブが正しいテーマカラーで表示されることを検証。

### M2-002: `image_ope_tab.py` のレイアウト再設計
- `ImageOperationApp.__init__()` のレイアウトを再構成:
  - **frame_main0**（上部）: 言語コンボ＋テーマ変更ボタン（現状維持）。
  - **frame_main1**（ファイルパス）: 入力ファイルパス＋出力フォルダパス＋選択ボタン。
    - `entry_setting_key` を PDF操作タブと共有（`base_file_path`, `output_folder_path`）。
    - `BaseImageColorChangeButton` を除去（拡張子/サイズ変換には不要）。
    - パス入力欄へのドラッグ&ドロップを登録。
    - 入力受付拡張子: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`, `.ico`, `.tga`。
  - **frame_main2**（拡張子変換セクション）:
    - 変換元形式ラベル（入力ファイルから自動検出）。
    - 変換先形式 Combobox: PNG, JPEG, BMP, GIF, TIFF, WebP, ICO, TGA。
    - 「拡張子変換」ボタン。
    - 警告情報ラベル（α喪失・劣化通知用）。
  - **frame_main3**（サイズ変換セクション）:
    - 幅 / 高さ Entry（既存 `U012`, `U013`）。
    - アスペクト比固定チェックボックス。
    - 「サイズ変換」ボタン（既存 `U014`）。
    - 警告情報ラベル（拡大時劣化通知用）。
  - **frame_main4**（プレビュー / ステータス）:
    - Canvas で画像プレビュー（既存流用）。
    - ステータスバーラベル（既存流用）。

### M2-003: 拡張子変換ロジック
- `_convert_extension()` を実装:
  1. PIL で入力ファイルを読み込み。
  2. 変換元形式とαチャンネルの有無を検出。
  3. 変換先形式がαチャンネル非対応（JPEG, BMP 等）の場合:
     - 確認ダイアログ表示: 「αチャンネルが失われます。続行しますか？」
     - キャンセル → 中断。OK → RGBA→RGB（白背景合成）。
  4. 可逆→非可逆変換（PNG→JPEG 等）の場合:
     - 確認ダイアログ表示: 「画像品質が劣化する可能性があります。続行しますか？」
  5. 256色パレット変換（→GIF）の場合:
     - 確認ダイアログ表示: 「色深度が256色に削減されます。続行しますか？」
  6. 出力フォルダに新拡張子で保存。
  7. プレビュー Canvas を更新。
  8. ステータスバーに成功/失敗を表示。

### M2-004: サイズ変換ロジック
- `_convert_image()` / `ImageSizeConverter` をリファクタリング:
  1. PIL で入力ファイルを読み込み。
  2. 幅/高さ > 0 のバリデーション（既存）。
  3. 全角→半角正規化を追加（M1-008 のパターンを再利用）。
  4. 拡大（ターゲットサイズ > ソースサイズ）の場合:
     - 確認ダイアログ表示: 「拡大により画像品質が劣化する可能性があります。続行しますか？」
  5. アスペクト比固定: 有効時、幅変更→高さ自動計算、高さ変更→幅自動計算。
  6. 出力フォルダに `_resized` サフィックス付きで保存。
  7. プレビュー Canvas を更新。
- リサンプリング: 縮小時 `Image.Resampling.LANCZOS`、拡大時 `Image.Resampling.BICUBIC`。

### M2-005: コピー保護ファイル対応
- PDF ファイルが入力として選択された場合、`Encrypted` フラグをチェック。
- コピー保護 PDF から抽出された画像ファイルが検出された場合、変換ボタンを無効化。
- PDF操作タブと同じ警告スタイル（赤枠・薄赤背景・白文字）を表示。
- `MouseEventHandler` の `_show_blocked_warning()` パターンを再利用。

### M2-006: 入出力パスの共有
- PDF操作タブと同じ `entry_setting_key` 値を使用:
  - 入力: `base_file_path`
  - 出力: `output_folder_path`
- `BasePathEntry` は `user_settings.json` 経由でこれらのキーに永続化済み。
- 一方のタブでパスを設定すると、もう一方のタブでも次回フォーカス時に反映される。

### M2-007: ドラッグ&ドロップ対応
- ドラッグ&ドロップを登録するウィジェット:
  - 入力パス Entry: 画像ファイル（`.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`, `.ico`, `.tga`）および PDF ファイル（`.pdf`）を受付。
  - 出力パス Entry: フォルダパスを受付。
  - Canvas: 画像ファイルを受付（プレビュー表示）。
- `controllers/drag_and_drop_file.py` の `DragAndDropHandler.register_drop_target()` を使用。

### M2-008: 新規メッセージコード
- UI メッセージ（実装時に正確なコード番号を決定）:
  - `U075`: "変換元形式:" / "Source format:"
  - `U076`: "変換先形式:" / "Target format:"
  - `U077`: "拡張子変換" / "Convert Extension"
  - `U078`: "αチャンネルが失われます。続行しますか？" / "Alpha channel will be lost. Proceed?"
  - `U079`: "画像品質が劣化する可能性があります。続行しますか？" / "Image quality may degrade. Proceed?"
  - `U080`: "色深度が256色に削減されます。続行しますか？" / "Color depth will be reduced to 256 colors. Proceed?"
  - `U081`: "アスペクト比を固定" / "Lock aspect ratio"
  - `U082`: "拡大により画像品質が劣化する可能性があります。続行しますか？" / "Image quality may degrade due to upscaling. Proceed?"
  - `U083`: "拡張子変換が完了しました。" / "Extension conversion completed."
  - `U084`: "サイズ変換が完了しました。" / "Size conversion completed."

### M2-009: テーマカラーエントリ追加
- `dark.json`, `light.json`, `pastel.json` に新規ウィジェット用エントリを追加:
  - `ext_convert_button`（拡張子変換ボタン）
  - `size_convert_button`（`convert_image_button` を再利用可能）
  - `aspect_ratio_checkbox`
  - `warning_info_label`
- 既存エントリ（`width_size_set_label`, `height_size_set_label`, `convert_image_button`）の適切な使用を確認。

### M2-010: コード整理
- `_on_output_folder_select()` 内のインデント不正修正（サイズ変換ウィジェット生成コードを `__init__()` へ移動）。
- `ImageSizeConverter` を `controllers/image_operations.py` または専用モジュールへ移動。
- `NullProgressCallback` の除去（不要であれば）。
- `BaseImageColorChangeButton` の使用を除去または用途変更（M2 では不要）。

## 検証チェックリスト（Tasks.md 用）
- [ ] タブが Notebook に表示され選択可能。
- [ ] すべての新規ウィジェットにテーマカラーが正しく適用される。
- [ ] 入力ファイルパスと出力フォルダパスが PDF操作タブと共有される。
- [ ] 入力/出力パス Entry および Canvas へのドラッグ&ドロップが動作する。
- [ ] 拡張子変換: αチャンネルを持つ PNG → JPEG でα喪失警告が表示される。
- [ ] 拡張子変換: PNG → JPEG で有効な JPEG ファイルが生成される。
- [ ] 拡張子変換: JPEG → PNG で有効な PNG ファイルが生成される。
- [ ] サイズ変換: 縮小で正しいサイズが生成される。
- [ ] サイズ変換: 拡大で劣化警告が表示される。
- [ ] アスペクト比固定が正しく動作する。
- [ ] コピー保護ファイル: 変換ボタンが無効化され警告が表示される。
- [ ] すべてのメッセージコードが日本語/英語で正しく表示される。

---
更新日: 2026-02-16
