# M2 Plan — ファイル拡張子・サイズ変換タブ (U006)

## 目的 / Goal
- `main.py` でコメントアウトされている「ファイル拡張子とサイズ」タブ（U006）を有効化する。
- `views/image_ope_tab.py`（`ImageOperationApp` クラス）を再設計し、以下の機能を提供する:
  1. **拡張子変換** — 画像・PDF 形式間の変換（PNG, JPEG, BMP, GIF, TIFF, WebP, ICO, TGA, PDF, SVG）。
  2. **画像サイズ変換** — ユーザー指定の寸法・DPI・用紙サイズへのリサイズ。
- αチャンネル喪失や画質劣化が発生する場合は、処理前にユーザーへ通知し「OK」確認を取る。
- 変換後のメタ情報（EXIF, ICC プロファイル, DPI 等）を可能な限り引き継ぐ。
- コピー保護ファイルへの操作は「PDF操作」タブと同様に禁止し、ポップアップ警告＋ボタン無効化を行う。
- 同名ファイルが既に存在する場合は `(1)`, `(2)` 等のサフィックスを付与して上書きを防止する。

## 前提
- タブ名のメッセージコードは既存: `U006`（"File Extension and Size" / "ファイル拡張子とサイズ"）。
- 既存ウィジェット用メッセージコード: `U012`（幅）, `U013`（高さ）, `U014`（変換）。
- テーマJSON に `width_size_set_label`, `height_size_set_label`, `convert_image_button` のエントリが存在。
- `DragAndDropHandler` は `controllers/drag_and_drop_file.py` から再利用可能。
- 入力ファイル・出力フォルダは「PDF操作」タブと共有する（`user_settings.json` 経由）。
- ドラッグ&ドロップで入力・出力欄への投入にも対応する。  
  D&D 追加が「PDF操作」タブ側と競合する場合は、PDF操作タブ側にも D&D を追加し、共有可能な部分は共有する。

## ライブラリ・ライセンス調査

### 現在使用中のライブラリ

| ライブラリ | バージョン | ライセンス | 商用利用 | コード開示義務 | 備考 |
|-----------|-----------|-----------|---------|--------------|------|
| **Pillow** | 12.0.0 | MIT-CMU (HPND) | ✅ 可 | ❌ 不要 | PIL のフォーク。著作権表示の保持のみ必要。コピーレフトなし。 |
| **pypdfium2** | 5.0.0 | BSD-3-Clause + Apache-2.0 | ✅ 可 | ❌ 不要 | PDFium (Google Chrome の PDF エンジン) の Python バインディング。PDF→画像変換に使用。 |
| **pypdf** | 6.1.3 | BSD-3-Clause | ✅ 可 | ❌ 不要 | Pure-Python PDF ライブラリ。メタデータ抽出・暗号化チェックに使用。 |
| **tkinterdnd2** | 0.4.3 | MIT | ✅ 可 | ❌ 不要 | Tkinter 用ドラッグ&ドロップ拡張。 |

### M2 で追加検討したライブラリ

| ライブラリ | 用途 | ライセンス | 判定 | 理由 |
|-----------|------|-----------|------|------|
| **svglib** | SVG→ラスタ変換 | BSD-3-Clause | ✅ 採用可 | Permissive。ReportLab (BSD) に依存。 |
| **reportlab** | svglib の描画エンジン | BSD-3-Clause | ✅ 採用可 | svglib の必須依存。Permissive。 |
| **cairosvg** | SVG→PNG/PDF変換 | **LGPL-3.0** | ❌ **不採用** | コード開示義務リスクあり。 |

### 結論
- **現在のすべての依存ライブラリは Permissive ライセンス**（MIT, BSD, Apache-2.0, HPND）である。
- GPL, AGPL, LGPL 等のコピーレフト（コード開示義務あり）ライセンスのライブラリは**一切使用していない**。
- M2 で追加の外部ライブラリは原則不要（Pillow 12.0.0 が主要ラスタ形式を標準サポート）。
- **SVG 対応**: `svglib` + `reportlab`（両方 BSD-3-Clause）の導入を検討。  
  ただし SVG→ラスタ変換は複雑な SVG（グラデーション、フィルタ等）で品質が落ちる制限あり。  
  アイコン用途の単純な SVG であれば十分対応可能。対応不可の場合はユーザーに通知して断念。

### 拡張形式（将来検討）に関するライセンスリスク

| 形式 | 必要ライブラリ | ライセンス | リスク |
|------|--------------|-----------|--------|
| **AVIF** | `pillow-avif-plugin` / `pillow-heif` | libavif: BSD-2-Clause, ただしコーデック (dav1d: BSD-2, aom: BSD-2, rav1e: BSD-2) | ⚠ コーデック構成次第。現時点では安全だが、将来のバージョンで依存関係が変わる可能性あり。 |
| **HEIF/HEIC** | `pillow-heif` | BSD-3-Clause, ただし **libheif が LGPL-3.0** | ⚠ **LGPL-3.0**: 動的リンクなら商用利用可だが、静的リンクや改変時にソースコード開示義務が発生する可能性あり。**M2 では採用しない**。 |
| **JPEG XL** | `pillow-jxl-plugin` | BSD-3-Clause (libjxl) | ✅ 安全。ただし Pillow プラグインの成熟度が低い。 |
| **EPS** | Pillow EpsImagePlugin | Pillow 内蔵 | ⚠ **Ghostscript 必須**（本環境未インストール）。外部依存が増えるため M2 では対象外。 |
| **EMF/WMF** | — | — | ❌ Pillow 非対応。サードパーティも成熟したライブラリなし。 |

→ **M2 では Pillow 標準サポート形式 + pypdfium2（PDF読込）+ svglib（SVG読込、要検証）を対象とし、追加ライブラリが必要な形式（AVIF, HEIF, JPEG XL, EPS）は対象外とする。**

## 対応拡張子

### 拡張子の正規化ルール
- **すべての拡張子は小文字に統一**する（`.PNG` → `.png`, `.JPG` → `.jpg` 等）。
- **TIFF**: `.tif`, `.tiff`, `.TIF`, `.TIFF` → すべて **`.tif`** に統一。
- **JPEG**: `.jpg`, `.jpeg`, `.JPG`, `.JPEG` → すべて **`.jpg`** に統一。
- 入力時は大文字・小文字を問わず受け付けるが、出力ファイルの拡張子は正規化後の小文字を使用。

### Pillow 12.0.0 の機能確認結果（本プロジェクト環境）
```
webp: True, jpg: True, zlib: True, libtiff: True, jpg_2000: True
PDF write: OK (Pillow), PDF read: pypdfium2 経由
SVG read: svglib 経由（要追加）, SVG write: 非対応
```

### M2 対応形式一覧

| 形式 | 正規化拡張子 | 読込 | 書出 | αチャンネル | 可逆圧縮 | 色深度 | 備考 |
|------|------------|------|------|------------|---------|--------|------|
| **PNG** | `.png` | ✅ Pillow | ✅ Pillow | ✅ | ✅ | 8/16bit | 標準的な可逆形式。Web・印刷どちらにも対応。 |
| **JPEG** | `.jpg` | ✅ Pillow | ✅ Pillow | ❌ | ❌ (非可逆) | 8bit | 写真向け。αチャンネル非対応。 |
| **BMP** | `.bmp` | ✅ Pillow | ✅ Pillow | ❌ (※) | ✅ (無圧縮) | 8/24bit | Windows 標準。αは保存不可（32bit BMPは限定的）。 |
| **GIF** | `.gif` | ✅ Pillow | ✅ Pillow | ✅ (1bit) | ✅ | 8bit (256色) | アニメーション対応（M2では静止画のみ）。パレット形式。 |
| **TIFF** | `.tif` | ✅ Pillow | ✅ Pillow | ✅ | ✅ | 8/16/32bit | 印刷・DTP向け。多様な圧縮形式をサポート。 |
| **WebP** | `.webp` | ✅ Pillow | ✅ Pillow | ✅ | ✅/❌ | 8bit | Google 開発。可逆/非可逆両対応。αチャンネル対応。 |
| **ICO** | `.ico` | ✅ Pillow | ✅ Pillow | ✅ | ✅ | 8/32bit | アイコン用。複数サイズ格納可能。M2では単一サイズ変換のみ。 |
| **TGA** | `.tga` | ✅ Pillow | ✅ Pillow | ✅ | ✅ | 8/24/32bit | ゲーム・映像向け。αチャンネル対応。 |
| **PDF** | `.pdf` | ✅ pypdfium2 | ✅ Pillow | ❌ | — | — | 読込は pypdfium2 でページをラスタライズ。書出は Pillow の PDF 保存。複数ページ PDF は1ページ目のみ対象。 |
| **SVG** | `.svg` | ⚠ svglib | ❌ | ✅ | — (ベクター) | — | svglib + reportlab で読込→ラスタ変換。複雑な SVG は品質低下の可能性あり。書出非対応。処理不可時はユーザーに通知。 |

### 将来対応候補（M2 対象外）
- **AVIF** (`.avif`) — 高圧縮・高画質だが追加ライブラリ必要。
- **HEIF/HEIC** (`.heif`, `.heic`) — Apple 標準形式だが **libheif が LGPL-3.0** のためライセンスリスクあり。
- **JPEG XL** (`.jxl`) — 次世代形式だが Pillow プラグインが未成熟。
- **JPEG 2000** (`.jp2`) — Pillow が `openjpeg` 経由でサポート（本環境で利用可）。需要があれば追加検討。
- **EPS** (`.eps`) — Pillow プラグインあるが Ghostscript 必須（本環境未インストール）。

## メタ情報の保持・変換ルール

### 基本方針
- 変換時に**引き継げるメタ情報は可能な限り保持**する。
- 変換先形式が対応していないメタ情報は破棄される（ユーザーへの通知は不要）。

### メタ情報の対応表

| メタ情報 | PNG | JPEG | BMP | GIF | TIFF | WebP | ICO | TGA | PDF |
|----------|-----|------|-----|-----|------|------|-----|-----|-----|
| **EXIF** | ✅ (pnginfo) | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **ICC プロファイル** | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **DPI (解像度)** | ✅ (pHYs) | ✅ (JFIF) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **コメント** | ✅ (tEXt) | ✅ (COM) | ❌ | ✅ (comment) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **作成日時** | ✅ (tEXt) | ✅ (EXIF) | ❌ | ❌ | ✅ | ✅ (EXIF) | ❌ | ❌ | ❌ |

### 実装方法
1. 入力ファイル読込時に `Image.info` / `Image.getexif()` からメタ情報を取得。
2. ICC プロファイルは `img.info.get("icc_profile")` で取得し、保存時に `icc_profile=` パラメータで引き継ぐ。
3. EXIF データは `img.getexif()` で取得し、保存時に `exif=` パラメータで引き継ぐ。
4. DPI は `img.info.get("dpi")` で取得し、保存時に `dpi=` パラメータで引き継ぐ。
5. 変換先形式が未対応のメタ情報は自動的にスキップ（エラーにはしない）。

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
  - メタ情報の引き継ぎ未実装。

### 関連ファイル
| ファイル | 役割 |
|---------|------|
| `views/image_ope_tab.py` | タブビュー（主要対象） |
| `main.py` | タブ登録、Notebook セットアップ |
| `controllers/drag_and_drop_file.py` | `DragAndDropHandler.register_drop_target()` |
| `controllers/file2png_by_page.py` | `BaseImageConverter`（PDF→画像変換で使用） |
| `controllers/image_operations.py` | `ImageOperations` クラス（移動/回転/ズーム — M2では不要） |
| `widgets/convert_image_button.py` | `ConvertImageButton`（BaseButton サブクラス） |
| `widgets/base_image_color_change_button.py` | カラーピッカーボタン（M2では除去/用途変更の可能性） |
| `widgets/base_path_entry.py` | 設定永続化付きパス入力 Entry |
| `widgets/base_path_select_button.py` | ダイアログ付きパス選択ボタン |
| `configurations/message_codes.json` | UI/ログ/エラー メッセージコード |
| `themes/dark.json`, `light.json`, `pastel.json` | テーマカラーエントリ |

## 変換時の警告マトリクス

| 変換元＼変換先 | .png | .jpg | .bmp | .gif | .tif | .webp | .ico | .tga | .pdf |
|---------------|------|------|------|------|------|-------|------|------|------|
| **.png**      | —    | ⚠α+Q | ⚠α   | ⚠α+C | ✓    | ✓     | ✓    | ✓    | ⚠α   |
| **.jpg**      | ✓    | —    | ✓    | ⚠C   | ✓    | ✓     | ✓    | ✓    | ✓    |
| **.bmp**      | ✓    | ⚠Q   | —    | ⚠C   | ✓    | ✓     | ✓    | ✓    | ✓    |
| **.gif**      | ✓    | ⚠Q   | ✓    | —    | ✓    | ✓     | ✓    | ✓    | ✓    |
| **.tif**      | ✓    | ⚠α+Q | ⚠α   | ⚠α+C | —    | ✓     | ✓    | ✓    | ⚠α   |
| **.webp**     | ✓    | ⚠α+Q | ⚠α   | ⚠α+C | ✓    | —     | ✓    | ✓    | ⚠α   |
| **.ico**      | ✓    | ⚠α+Q | ⚠α   | ⚠α+C | ✓    | ✓     | —    | ✓    | ⚠α   |
| **.tga**      | ✓    | ⚠α+Q | ⚠α   | ⚠α+C | ✓    | ✓     | ✓    | —    | ⚠α   |
| **.pdf**      | ✓    | ✓    | ✓    | ⚠C   | ✓    | ✓     | ✓    | ✓    | —    |
| **.svg**      | ✓    | ✓    | ✓    | ⚠C   | ✓    | ✓     | ✓    | ✓    | ✓    |

- **⚠α** = αチャンネル喪失警告（RGBA画像の場合のみ。RGB画像なら警告不要）
- **⚠Q** = 画質劣化警告（可逆→非可逆変換）
- **⚠C** = 色深度削減警告（256色パレットへの変換）
- **✓** = 安全な変換（警告不要）
- **.svg** は書出非対応のため変換先列なし（読込→他形式への変換のみ）

## UIレイアウト設計

### 基本方針
- **プレビューは設けない**。スペースを十分に確保し、変換内容が一目で分かるモダンなレイアウトとする。
- **拡張子変換**と**サイズ変換**は明確に独立したブロックに分離する。
- 各ブロックに個別の実行ボタンを配置する。
- コピー保護ファイルの場合はポップアップ警告後に実行ボタンを無効化する。

### 全体構成
```
┌──────────────────────────────────────────────────────────┐
│ frame_main0: 言語コンボ ＋ テーマ変更ボタン                │
├──────────────────────────────────────────────────────────┤
│ frame_main1: 入力ファイルパス [Entry] [選択ボタン]         │
│              出力フォルダパス [Entry] [選択ボタン]         │
├──────────────────────────────────────────────────────────┤
│ frame_ext: 【拡張子変換ブロック】                          │
│                                                          │
│   入力ファイル名.拡張子  ⇒  出力ファイル名.[▼ 拡張子選択] │
│   ─────────────────────────────────────────              │
│   メタ情報表示:                                           │
│     形式: PNG | モード: RGBA | サイズ: 1920x1080          │
│     DPI: 72 | ICC: sRGB | EXIF: あり                     │
│   ─────────────────────────────────────────              │
│   [⚠ 警告ラベル（α喪失・品質劣化等、該当時のみ表示）]      │
│                                                          │
│                              [🔄 拡張子変換 実行ボタン]   │
├──────────────────────────────────────────────────────────┤
│ frame_size: 【サイズ変換ブロック】                         │
│                                                          │
│   入力ファイル名.拡張子  ⇒  出力ファイル名.拡張子          │
│   現在: 1920px × 1080px   □ px × □ px                    │
│   ─────────────────────────────────────────              │
│   DPI:     [▼ 72 / 96 / 150 / 300 / 600 ]               │
│   用紙:    [▼ A4 / A3 / B5 / Letter / はがき / カスタム ] │
│   □ アスペクト比を固定                                    │
│   ─────────────────────────────────────────              │
│   [⚠ 警告ラベル（拡大劣化等、該当時のみ表示）]             │
│                                                          │
│                              [📐 サイズ変換 実行ボタン]   │
├──────────────────────────────────────────────────────────┤
│ frame_status: ステータスバー                               │
└──────────────────────────────────────────────────────────┘
```

### 拡張子変換ブロック詳細
- **変換表現行**:  
  `sample_image.png` ⇒ `sample_image.` [▼ jpg ▾]  
  - 入力ファイル名はパスから自動取得して表示（読み取り専用）。
  - 出力ファイル名は入力ファイル名のベース部分を引き継ぎ、拡張子部分のみドロップダウンで選択。
  - ドロップダウン選択肢: `png`, `jpg`, `bmp`, `gif`, `tif`, `webp`, `ico`, `tga`, `pdf`  
    （入力形式と同一の拡張子は選択肢から除外）。
- **メタ情報表示**（変換表現行の下）:  
  - 入力ファイルのメタ情報を自動検出して表示（拡張子変換に関連する項目のみ）。
  - 表示項目: 形式、カラーモード（RGB/RGBA/P/L 等）、画像サイズ(px)、DPI、ICC プロファイル名、EXIF 有無。
- **警告ラベル**: 選択中の変換先に応じて動的に表示/非表示が切り替わる。

### サイズ変換ブロック詳細
- **変換表現行**:  
  `sample_image.png` ⇒ `sample_image.png`  
  `1920px × 1080px`　→　`[□] px × [□] px`  
  - 入力ファイルの現在サイズを左に表示。右に変換先サイズの入力欄。
- **DPI ドロップダウン**: `72`, `96`, `150`, `300`, `600`（カスタム入力可）。
- **用紙サイズ ドロップダウン**:  
  選択時に幅/高さを自動入力する。選択肢:
  - A4 (210×297mm), A3 (297×420mm), A5 (148×210mm)
  - B5 (176×250mm), B4 (250×353mm)
  - Letter (216×279mm), Legal (216×356mm)
  - はがき (100×148mm)
  - カスタム（手入力）
  - ※ mm→px 変換は選択中の DPI 値を使用。
- **アスペクト比固定チェックボックス**: 有効時、幅/高さの一方を変更すると他方を自動計算。

## 重複ファイル名の処理ルール
- 出力先に同名ファイル（変更後の拡張子を含む）が既に存在する場合:
  - `filename(1).ext`, `filename(2).ext`, ... の順でサフィックスを付与。
  - 空き番号を自動検索して使用する。
- 例: `photo.jpg` → PNG 変換で `photo.png` が既存 → `photo(1).png` として保存。

## 実装計画

### M2-001: `main.py` でのタブ有効化
- `image_ope_tab` フレーム作成と `notebook.add(...)` のコメントアウトを解除。
- `TabContainerBgUpdater` のコンテナリストに `image_ope_tab` を追加。
- `views.image_ope_tab` から `ImageOperationApp` を import し、フレーム内で生成。
- タブが正しいテーマカラーで表示されることを検証。

### M2-002: UIレイアウト再設計（`image_ope_tab.py`）
- `ImageOperationApp.__init__()` のレイアウトを「UIレイアウト設計」セクションに従い再構成。
- **プレビュー Canvas を削除**し、スペースを変換ブロックに活用。
- **frame_main0**: 言語コンボ＋テーマ変更ボタン（現状維持）。
- **frame_main1**: 入力ファイルパス＋出力フォルダパス＋選択ボタン。
  - `entry_setting_key` を PDF操作タブと共有（`base_file_path`, `output_folder_path`）。
  - `BaseImageColorChangeButton` を除去（拡張子/サイズ変換には不要）。
- **frame_ext**: 拡張子変換ブロック（変換表現＋メタ情報＋警告＋実行ボタン）。
- **frame_size**: サイズ変換ブロック（変換表現＋DPI/用紙＋アスペクト比＋警告＋実行ボタン）。
- **frame_status**: ステータスバー。

### M2-003: 拡張子変換ロジック
- `_convert_extension()` を実装:
  1. PIL / pypdfium2 / svglib で入力ファイルを読み込み。
  2. 変換元形式とαチャンネルの有無を検出。
  3. 変換先形式に応じた警告を表示:
     - αチャンネル非対応（`.jpg`, `.bmp` 等）→ 確認ダイアログ。
     - 可逆→非可逆変換 → 確認ダイアログ。
     - 256色パレット変換（→ `.gif`）→ 確認ダイアログ。
  4. メタ情報（EXIF, ICC, DPI）を可能な限り引き継いで保存。
  5. 出力フォルダに正規化拡張子で保存。同名ファイル存在時は `(1)` サフィックス付与。
  6. ステータスバーに成功/失敗を表示。
- **PDF 読込**: pypdfium2 でページをラスタライズ → PIL Image に変換。
- **PDF 書出**: `img.save(path, format="PDF")` で保存。
- **SVG 読込**: svglib で読込 → reportlab で描画 → PIL Image に変換。  
  変換不可時はエラーメッセージを表示して処理中断。
- **出力単位文言の統一（M2-003追加仕様）**:
  - 単一出力（1ファイル保存）の場合は `file` 文言を使用する。
  - 複数ページ/複数フレームで専用ディレクトリ出力する場合は `folder` 文言を使用する。
  - ステータスバー・警告ラベル・確認ダイアログで同一語彙を使用する。

### M2.1（追加仕様）
- M2 の追加仕様は `docs/milestone/M2_1_PLAN.md` を正とする。
- 対象は U006（ファイル拡張子・サイズタブ）であり、特に以下を定義する。
  1. PDF入力時のラスタライズDPI指定（軽量化目的のDPI低減を含む）
  2. 用紙サイズ（物理サイズ）を基準とした出力制御
  3. M2-003における file/folder 文言統一の厳格適用

### M2-004: サイズ変換ロジック
- `_convert_image()` / `ImageSizeConverter` をリファクタリング:
  1. PIL で入力ファイルを読み込み。
  2. 幅/高さ > 0 のバリデーション（既存）。
  3. 全角→半角正規化を追加（M1-008 のパターンを再利用）。
  4. DPI ドロップダウン＋用紙サイズドロップダウンから自動計算:  
     `px = mm × dpi / 25.4`
  5. 拡大（ターゲットサイズ > ソースサイズ）の場合:
     - 確認ダイアログ表示: 「拡大により画像品質が劣化する可能性があります。続行しますか？」
  6. アスペクト比固定: 有効時、幅変更→高さ自動計算、高さ変更→幅自動計算。
  7. メタ情報を引き継ぎつつ出力フォルダに `_resized` サフィックス付きで保存。  
     同名ファイル存在時は `(1)` サフィックス付与。
- リサンプリング: 縮小時 `Image.Resampling.LANCZOS`、拡大時 `Image.Resampling.BICUBIC`。

### M2-005: コピー保護ファイル対応
- PDF ファイルが入力として選択された場合、`pypdf.PdfReader` で `Encrypted` フラグをチェック。
- コピー保護検出時:
  1. ポップアップウィンドウで警告メッセージを表示し、ユーザーに「OK」クリックを求める。
  2. 拡張子変換・サイズ変換の両実行ボタンを `state=DISABLED` に設定。
  3. PDF操作タブと同じ警告スタイル（赤枠・薄赤背景・白文字）を表示。
- 別の非保護ファイルが選択されたらボタンを再有効化。

### M2-006: 入出力パスの共有
- PDF操作タブと同じ `entry_setting_key` 値を使用:
  - 入力: `base_file_path`
  - 出力: `output_folder_path`
- `BasePathEntry` は `user_settings.json` 経由でこれらのキーに永続化済み。
- 一方のタブでパスを設定すると、もう一方のタブでも次回フォーカス時に反映される。

### M2-007: ドラッグ&ドロップ対応
- ドラッグ&ドロップを登録するウィジェット:
  - 入力パス Entry: 画像ファイル（`.png`, `.jpg`, `.bmp`, `.gif`, `.tif`, `.webp`, `.ico`, `.tga`, `.svg`）および PDF ファイル（`.pdf`）を受付。
  - 出力パス Entry: フォルダパスを受付。
- `controllers/drag_and_drop_file.py` の `DragAndDropHandler.register_drop_target()` を使用。
- **PDF操作タブとの共有**: D&D 追加が PDF操作タブ側と競合する場合は、PDF操作タブにも D&D を追加する。  
  `DragAndDropFileConverter` クラスの `setup_drag_and_drop_for_pdf_tab()` を拡張または新メソッドを追加して共有化。

### M2-008: メタ情報保持の実装
- 新規ユーティリティ関数群を作成（`utils/image_meta_utils.py` 等）:
  - `extract_metadata(img: Image.Image) -> dict` — EXIF, ICC, DPI, コメント等を抽出。
  - `apply_metadata(img: Image.Image, metadata: dict, target_format: str) -> dict` — 保存時パラメータを構築。
  - `format_metadata_display(metadata: dict) -> str` — UI表示用にフォーマット。
- 拡張子変換・サイズ変換の両方で利用する。

### M2-009: 新規メッセージコード
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
  - `U085`: "DPI:" / "DPI:"
  - `U086`: "用紙サイズ:" / "Paper size:"
  - `U087`: "コピー保護されたファイルです。変換できません。" / "This file is copy-protected. Conversion is not allowed."
  - `U088`: "SVGの変換に失敗しました。複雑なSVGには対応していません。" / "SVG conversion failed. Complex SVG files are not supported."
  - `U089`: "同名ファイルが存在するため、サフィックスを付与しました: {0}" / "A file with the same name exists. Suffix added: {0}"

### M2-010: テーマカラーエントリ追加
- `dark.json`, `light.json`, `pastel.json` に新規ウィジェット用エントリを追加:
  - `ext_convert_button`（拡張子変換実行ボタン）
  - `size_convert_button`（サイズ変換実行ボタン、`convert_image_button` を再利用可能）
  - `aspect_ratio_checkbox`
  - `warning_info_label`
  - `meta_info_label`（メタ情報表示ラベル）
  - `conversion_arrow_label`（⇒ 矢印表示ラベル）
- 既存エントリ（`width_size_set_label`, `height_size_set_label`, `convert_image_button`）の適切な使用を確認。

### M2-011: コード整理
- `_on_output_folder_select()` 内のインデント不正修正（サイズ変換ウィジェット生成コードを `__init__()` へ移動）。
- `ImageSizeConverter` を `controllers/image_operations.py` または専用モジュールへ移動。
- `NullProgressCallback` の除去（不要であれば）。
- `BaseImageColorChangeButton` の使用を除去（M2 では不要）。
- 拡張子の正規化処理を共通ユーティリティに集約（大文字→小文字、`.tiff`→`.tif`、`.jpeg`→`.jpg`）。

## 検証チェックリスト（Tasks.md 用）
- [ ] タブが Notebook に表示され選択可能。
- [ ] すべての新規ウィジェットにテーマカラーが正しく適用される。
- [ ] 入力ファイルパスと出力フォルダパスが PDF操作タブと共有される。
- [ ] 入力/出力パス Entry へのドラッグ&ドロップが動作する。
- [ ] 拡張子変換ブロック: 入力ファイルのメタ情報が正しく表示される。
- [ ] 拡張子変換: αチャンネルを持つ `.png` → `.jpg` でα喪失警告が表示される。
- [ ] 拡張子変換: `.png` → `.jpg` で有効な JPEG ファイルが生成される。
- [ ] 拡張子変換: `.jpg` → `.png` で有効な PNG ファイルが生成される。
- [ ] 拡張子変換: `.pdf` → `.png` で有効な PNG ファイルが生成される（pypdfium2 経由）。
- [ ] 拡張子変換: EXIF, ICC, DPI が変換先で引き継がれる（対応形式の場合）。
- [ ] 拡張子変換: 同名ファイル存在時に `(1)` サフィックスが付与される。
- [ ] 拡張子の正規化: `.TIFF` → `.tif`, `.JPEG` → `.jpg` に統一される。
- [ ] サイズ変換ブロック: DPI ドロップダウンが正しく動作する。
- [ ] サイズ変換ブロック: 用紙サイズ選択で幅/高さが自動入力される。
- [ ] サイズ変換: 縮小で正しいサイズが生成される。
- [ ] サイズ変換: 拡大で劣化警告が表示される。
- [ ] アスペクト比固定が正しく動作する。
- [ ] コピー保護ファイル: ポップアップ警告表示＋変換ボタンが無効化される。
- [ ] SVG 読込: 単純なアイコン SVG が正しくラスタ変換される（svglib 導入時）。
- [ ] すべてのメッセージコードが日本語/英語で正しく表示される。

---
更新日: 2026-02-16
