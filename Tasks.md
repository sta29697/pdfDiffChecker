# タスクリスト
 
 ## Integration  
 - **2026-01-29 検証結果（ユーザー）**:  
   - **①** Dark Modeで起動後、入力ファイル選択時に進捗バーが表示される画面  
   - **②** Light Modeへ切替後の画面  
   - **③** Dark Modeへ戻した後の画面  
   - **④** Pastel Modeへ切替後の画面  
   - **M0-004-02-3**: ①と③の比較で、起動直後はタブ内背景がすぐ黒にならない。起動時の背景反映タイミング不整合が疑われる。  
   - **M0-004-02-3**: ②/④でタブ・背景・一部ボタンがテーマと一致しない。LightはWindows標準配色で判別しづらいため、デバッグのため一時的にCanvas白とは異なる背景色を使ってほしい。  
   - **AC-M0-006-01**: PCF選択後に表示できるため暫定で[✅]。  
   - **AC-M0-006-02**: 右サイドバー表示、ページ遷移、ページラベル整合は確認できたが、配色がNoteのテーマと一致しないため未マーク。  
   - **M0-004-02-4**: クラッシュは解消し、画像は白背景で安定表示できる。テーマ切替後も白のまま。  
 - **履歴（AI）**:  
   - `Tasks.md` は合計112行で、line 90 の空の `→` が存在することを確認した。  
   - line 90 の `→` 直後に、`process_with_progress_window()` と `ProgressWindow.show()` による進捗ウィンドウ表示の対策を2行形式で追記した。  

## M0（共通: メインウィンドウ / 全タブ）

### M0-001: Windows 11 のタスクバーアイコンが Tkinter アイコンのまま
- **修正内容（予定）**: Windows 11 でタスクバー/Alt+Tab のアイコンにアプリのアイコンが反映されるようにする。  
- **Note**: Windows 11 では、起動直後はアイコン未反映だが、ファイル選択/ドラッグ&ドロップ等の操作後に
   タスクバー側だけアプリアイコンへ切り替わるケースがある（再現条件を M0-001 で調査）。  
 - **Note**: `ProgressWindow`（`tk.Toplevel`）の左上アイコンが Tkinter のまま残るため、
   メインウィンドウと同じアプリアイコン（`iconbitmap`/`iconphoto`/`AppUserModelID` 等）を適用する必要がある可能性がある。  
   → M0-001-03/04対応として、`widgets/progress_window.py` の `ProgressWindow.__init__` でアプリアイコン（`images/LOGO_128.ico`）を `get_resource_path()` で解決し、  
     `self.iconbitmap()` で `tk.Toplevel` 側へ明示的に適用した。  
   → さらに AC-M0-001-04 対策として、`main.py` で `main_window.iconbitmap()` に加えて `main_window.iconphoto()`（`images/LOGOm.png`）も適用し、  
     複数サイズのアイコンを渡してWindows側の縮小表示でも透過が崩れにくいようにした（参照は `main_window._icon_photos` に保持）。  
   → また、`widgets/progress_window.py` でも `self.iconphoto()`（`images/LOGOm.png`）を適用し、  
     参照を `self._icon_photo` に保持して透過表示の経路を揃えた。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-001-01: `uv run main.py` で起動し、タスクバーのアイコンがアプリのアイコンになっていること。  
   - [✅] AC-M0-001-02: Alt+Tab 切替時のサムネイル/アイコンがアプリのアイコンになっていること。  
   - [✅] AC-M0-001-03: `ProgressWindow` の左上アイコンがアプリのアイコンになっていること。  
   - [✅] AC-M0-001-04: 全部のこのアプリのアイコンの背景が透明になっていること。  
        ⇒ The outer border is transparent, but the inner white background area is not transparent.  
           .\images\LOGOm.png has a transparent background.
        → `iconphoto()`（`images/LOGOm.png`）をメイン/`ProgressWindow`へ適用し、複数サイズ指定＋参照保持で透過が崩れにくいようにした。
        ⇒ The taskbar, Alt+Tab, ProgressWindow, and all app windows still have a white square background.  
        → `iconbitmap()` が参照していた `images/LOGO_128.ico` がアルファ無し（不透明）だったため、`images/LOGOm.png` から透過付きICO（`temp/LOGOm.ico`）を起動時に生成し、  
           `main.py` / `ProgressWindow` の `iconbitmap()` がこのICOを優先して使うように変更して、タスクバー/Alt+Tabでも透過が反映される経路へ切り替えた。  
        → さらに、`iconbitmap()` を適用する前に `iconphoto()` で透過付きPNGを設定することで、  
           Windows 10 でもタスクバー/Alt+Tab に透過付きアイコンが表示されるようにした。  
        ⇒ The taskbar seems to be a Windows issue, but Tkinter icons are displayed.
           The remaining icons are application icons, but the blue squares appear to have white interiors. What do you think?
        → `images/LOGO_128.ico` を削除してもアイコン適用が崩れないよう、`iconbitmap()` の参照先を `temp/LOGOm.ico` に統一し、
           `widgets/progress_window.py` 側の `images/LOGO_128.ico` フォールバックも撤廃した。  
        → 併せて `temp/LOGOm.ico` は起動のたびに作り直さず、`images/LOGOm.png` 更新時のみ再生成するようにし、
           終了時の `cleanup()` でも `LOGOm.ico` を削除しないようにしてキャッシュを維持した。  
        → これにより、`images/LOGO_128.ico` 削除後もアイコン適用が正常に機能し、キャッシュにより `temp/LOGOm.ico` の再生成が抑制される。  
        → さらに、グラフ表示用のサブウィンドウ（`tk.Toplevel`）でも同じ `iconbitmap/iconphoto` を明示的に適用し、
           `ProgressWindow` 以外のウィンドウでも Tk 既定アイコンへ戻らないよう統一した。  
        → ユーザー提供のマルチサイズICO（`images/icon_multi.ico`）と各サイズPNG（`images/icon_*x*.png`）を優先して使用するようにし、
          これらが配置されていない場合に限り、`images/LOGOm.png`（フォールバック）を使用するようにした。  
          これにより、縮小補間によるアイコンのブレを抑制し、よりスムーズなアイコン表示が可能になった。  
        ⇒ OK

### M0-002: Light Mode で赤枠のタブ文字が白くて読めない
 - **修正内容（予定）**: `./themes` 配下の定義に沿って、Light Mode 時の `ttk.Notebook` タブ文字色（foreground）を可読な色へ適用する。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-002-01: Light Mode に切り替え後、赤枠のタブ名が背景に対して十分に読める色で表示されること。  
   - [✅] AC-M0-002-02: Dark Mode に戻した際、タブ名が背景に対して十分に読める色で表示されること。  

### M0-003: Light/Dark の差分が背景と Canvas 付近しか変わらない
 - **修正内容（予定）**: テーマ適用対象（`ttk.Style`/各Widget/Canvas含む）の網羅性を確認し、Light/Dark で必要な配色差分が反映されるようにする。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-003-01: Light Mode と Dark Mode の切替で、タブ/入力欄/ラベル等の主要UI配色がテーマ定義通りに切り替わること。  
   - [✅] AC-M0-003-02: 切替後に一部のWidgetだけ旧テーマの色が残らないこと。  

### M0-004: user_setting.json の設定変更が反映されない（Light Modeでも黒しか変わらない）
 - **修正内容（予定）**: `./configurations/user_setting_manager.py` の読込/保存/適用フローを整理し、ユーザー設定変更がUIへ反映されるようにする。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-004-01: UI上で設定変更後、`./configurations/user_setting.json` に保存されること。  
    	⇒	The language settings and output folder path were applied, but the color theme was not applied.  
    		To begin with, even though Dark Mode was set, it opened using the Light Mode button.  
    	→	（日本語）`main.py` 起動時に `theme_color` を無視して `dark` を強制していた処理を撤廃し、`user_settings.json` の `theme_color` がそのままUI/ボタン表示へ反映されるように修正する。  
      		⇒ I confirmed that the changes are reflected in `./configurations/user_setting.json`.  
  - [✅] AC-M0-004-02: 再起動後、保存された設定が自動で読み込まれUIへ反映されること。 
    	⇒	Only the language settings have been applied. The color theme remains in light mode, and I believe the default settings have not been properly applied.  
			The output folder path is reflected in ./configurations/user_settings.json, but it is not reflected in the UI.  
			→	（M0-004-02-1）  
				（日本語）`views/pdf_ope_tab.py` の背景/Canvas/ボタン等でテーマ(JSON)とキー名が不一致（`Canvas` vs `canvas`、`bg` vs `background`）のため反映漏れが発生していた。キーの統一と起動時テーマ適用順序の修正により、各モードで配色を揃え、Canvas背景を白にし、テーマ変更ボタンのサイズも復元する。さらにパス表示は起動時にクリアしつつ、ダイアログ初期フォルダのみ最後の入力値のフォルダを使用する。  
      ⇒ I've uploaded images for each mode this time.  
         [✅]1. Regarding the image labeled “1” in Dark Mode, when compared to the image labeled “2” in Dark Mode, the colors differ even though they're both Dark Mode.  
            Could it be that the colors hard-coded instead of loading from the JSON file aren't being applied?  

         [✅]2. The color mode change button is smaller than before the fix. Please restore it to its previous size.  
              ⇒ The spacing has improved, but the button size hasn't changed.  
			→	（M0-004-02-2）  
				（日本語）ボタン枠の `width/height` 調整ではなく、PNG画像をPILで指定高さ（最大48px）へリサイズしてから `ImageTk.PhotoImage` で表示する方式に変更し、実際の見た目サイズを拡大する。初期レイアウト時に誤って縮小しないよう、画像高さ未満にならないガードも追加する。  
			⇒ Only in dark mode, the area outside the theme switch button is black. Also, I believe this applies to all buttons,  
                 but the top and bottom edges of the button images are cut off.  
			→	（M0-004-02-2）  
				（日本語）テーマ変更ボタンのPNG画像（透明部分）がOS側で黒く見えるため、PILで `Window.bg`（親背景色）へアルファ合成してから `ImageTk.PhotoImage` に渡すよう修正する。併せて `tk.Button` の `width/height`（文字単位）指定を撤去し、`padx/pady` を0にして画像上下の欠けを防ぐ。  
              ⇒ OK  
         [✅]3. When viewing the remaining two images (Light Mode and Pastel Mode) together, the background color of the entire area outlined in red appears inconsistent.   

			⇒ Only some background colors change based on the color mode.   
			   This includes tabs, areas around tabs, Canvas borders, and the progress bar background color.  
			   Dark mode is easier to see, so please check it.  
			→	（M0-004-02-3）  
				（日本語）`ttk` がOSテーマに負けて配色が固定化される箇所が残っていたため、`clam` テーマを優先し、`TNotebook`/`TCombobox`/`Primary.Horizontal.TProgressbar` をテーマJSONに追従するよう `ttk.Style` を拡張する。Canvas枠はOSのborderでは色変更できないため、`highlightthickness` と `highlightbackground/highlightcolor` を使ってテーマ化する。  
			→	（M0-004-02-3）  
				（日本語）テーマ切替時に `ttk` のstate別配色や枠線/矢印色がOS側に負けて更新されない問題があったため、`main.py` の `ttk.Style` に `TCombobox` の `arrowcolor/bordercolor/focuscolor` と state別 `style.map` を追加し、`TNotebook` も `bordercolor` をテーマ追従させる。さらに「選択」ボタン（`BasePathSelectButton`）はテーマJSONにキーが無い場合があるため、`process_button` をフォールバックとして適用し、テーマ切替で確実に再着色されるようにする。  
			⇒ Only the tabs, pull-down menus, and outer borders turned black regardless of theme. For pull-down buttons,  
			   the ▼ is barely visible against the black background unless pressed. The “Select” button for displaying dialogs also doesn't change color  
			   with the theme. The pull-down background color is the same. The Canvas border is now almost invisible.  
			→	（M0-004-02-3）  
				（日本語）テーマ切替時に `ttk` のstate別配色や枠線/矢印色がOS側に負けて更新されない問題があったため、`main.py` の `ttk.Style` に `TCombobox` の `arrowcolor/bordercolor/focuscolor` と state別 `style.map` を追加し、`TNotebook` も `bordercolor` をテーマ追従させる。さらに「選択」ボタン（`BasePathSelectButton`）はテーマJSONにキーが無い場合があるため、`process_button` をフォールバックとして適用し、テーマ切替で確実に再着色されるようにする。  
      ⇒ From upload images 2 and 4, the tabs outlined in yellow-green (combobox) and the outer edges of the tabs outlined in blue  
          in image 2 are only colored during initialization and are not recolored when switching color modes.  
          Additionally, the red-outlined “Select” button is not recolored either.  
			→	（M0-004-02-3）  
				（日本語）上記の「初期化時のみ着色され、テーマ切替で再着色されない」問題に対して、`TNotebook.Tab` の state（`selected/active/!selected`）別配色を `ttk.Style.map` で明示し、未選択タブ/外枠がOS側配色へ戻るのを抑止する。さらにタブ内UI生成後に `apply_color_theme_all_widgets()` を再実行して、起動直後・切替直後の適用順序による取り逃しを防ぐ。  
      ⇒ The background color within the tabs does not turn black immediately after launch. I suspect the timing for changing the background color at launch is incorrect.  
         Additionally, the tabs, background, and some buttons do not match the color theme.  
         Furthermore, since Light Mode uses the standard Windows system colors, it is difficult to distinguish.  
         Please temporarily use a color different from Canvas white to facilitate debugging.  

			→ 	（日本語）Light/Pastelでタブ選択が判別しづらい問題に対し、未選択タブ背景を `Notebook.bg`、選択タブ背景を `tab_bg` に分離し、外枠（root背景）もテーマ切替に追従するよう修正した。  
      ⇒ OK
         [✅]4. The background color of the Canvas is black in all images. This area should display images with a white background and transparent color.   
            Please investigate and fix this.  
            *Note: Colors for each mode are loaded from ./themes/**.json. Although not currently used, the original colors for each mode are preserved  
             in ./configurations/color_theme.py for reference.  
			⇒ All background colors are now white, but the selected image isn't displayed.  
			→	(M0-004-02-4)  
			（日本語）PDF→PNG変換で `bitmap.to_pil(colour=...)` を使うと環境によって全面透明になり得るため、通常レンダリング（`to_pil()`）に統一し、保存前に白背景へ合成して必ずページ内容が可視化されるよう修正する。  
      ⇒ Selected images still do not appear in the Canvas.  
	    →	(M0-004-02-4)  
	     	（日本語）PDF選択後に `PDFOperationApp._create_page_control_frame` 未実装でクラッシュしていたため、同メソッドを実装して `PageControlFrame` を生成・配置する。併せてページ表示のラベル更新（`update_page_label`）は0-basedで統一し、PDF読み込み後にCanvas描画処理まで到達できるようにする。  
      ⇒ The progress window during PDF selection appears complete in Upload Image 1 but is not displayed.  
          An error appears in the log, so that might be the cause.  
          The Main tab's ./views/main_tab.py showed some images, so please use that as a reference.  

        <<<error log>>>  
        2026-01-26 17:48:57 [ERROR] views.pdf_ope_tab (342): [PDF] PDFの読み込み中にエラーが発生しました: 'PDFOperationApp' object has no attribute '_create_page_control_frame'  
        2026-01-26 17:48:57 [ERROR] views.pdf_ope_tab (345): Traceback (most recent call last):  
          File "C:\Users\haya-\Lab\PrivateProject\01_DiffChecker\pdfDiffChecker\views\pdf_ope_tab.py", line 325, in _load_and_display_pdf  
          File "C:\Users\haya-\Lab\PrivateProject\01_DiffChecker\pdfDiffChecker\views\pdf_ope_tab.py", line 342, in _load_and_display_pdf  
            self._create_page_control_frame(self.page_count)  
      → 	(M0-004-02-4)  
      	（日本語）PDF選択時の変換処理を `process_with_progress_window()` 経由にし、`ProgressWindow.show()`（`deiconify()/update()`）で進捗ウィンドウを確実に表示する。終了時は  `after` で `hide/destroy`、例外時はウィンドウ上にエラーを表示して原因特定しやすくする。  
      	（日本語）PDF選択後に `PDFOperationApp._create_page_control_frame` 未実装でクラッシュしていたため、同メソッドを実装して `PageControlFrame` を生成・配置する。併せてページ表示のラベル更新（`update_page_label`）は0-basedで統一し、PDF読み込み後にCanvas描画処理まで到達できるようにする。  
      ⇒ （M0-004-02-4）  
         The crash has been fixed. Images now consistently display on a white background and remain white even when the color theme is changed.  

         [✅]5. Specification change. Previously, the path saved in the input/output box was displayed at startup; please clear it as before. Instead,  
            set the first path opened in the dialog box to the folder containing the last path entered in the input/output box.  
            (For the input box as well, since a different file is likely to be selected, set it to the folder level.)  
   - [✅] AC-M0-004-03: 設定変更直後（再起動不要の範囲）は即時反映されること。  
 
 ### M0-005: 言語ドロップダウン変更時にピンク枠の領域が残留する
 - **修正内容（予定）**: 言語変更のガイダンス表示（ピンク枠）の表示/非表示の条件とライフサイクルを見直し、元の言語へ戻した場合に表示が消えるようにする。  
   → （日本語）`widgets/language_select_combobox.py` で言語変更時のガイダンス（`notification_tag` を持つ `tk.Label`）を、現在テーマ（`ColorThemeManager.get_current_theme()`）に応じた背景色＋ピンク系の枠線で表示するようにして、各テーマで視認できるようにした。  
   → （日本語）また、初期言語へ戻した場合はガイダンスを非表示にする（既存ラベルは都度破棄する）挙動へ変更し、ピンク枠の表示残留を防ぐようにした。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-005-01: 言語ドロップダウンを変更するとピンク枠の表示が出ること。  
   - [✅] AC-M0-005-02: 元の言語へ戻すとピンク枠の表示が消えること。  

 
 ## M0（PDF Operation タブ）
 
 ### M0-006: 選択したPDFが表示されているか不明
 - **修正内容（予定）**: `./views/pdf_ope_tab.py` と `image_editor_view.py` 周辺を調査し、  
   表示対象（ページ番号/読み込み状態/レンダリング結果）がユーザーに明確に分かるようにする。  
 - **検証（ユーザー）**:  
   - [✅] AC-M0-006-01: PDF選択後、クラッシュせずに処理が完了し、Canvasに少なくとも1ページ目が表示されることが視覚的に分かること（空白/黒一色にならない）。  
   - [✅] AC-M0-006-02: 前/次のページ操作（ページ番号入力を含む）で表示内容が更新され、ページラベル等から現在ページが分かること。  
                      ⇒ The right sidebar is displayed, and page transitions and page label alignment were confirmed. However,  
                         the colors do not match the color themes listed in the Notes, so it remains unmarked for now.  
   - [✅] AC-M0-006-03: 読み込み失敗/変換失敗/画像ファイル欠損時に、エラーがログへ出力され、ユーザーが原因に当たりを付けられる情報が残ること（黒画面のまま黙る状態にならない）。

 - **Note**: Dark/Light の切替に加え、Light への切替時に一定確率（10%）で `pastel` に切り替わり、ボタン画像も `pastel_mode.png` へ変わる仕様がある。現状この切替が発生しないため、M0-004 で挙動と反映経路（テーマ名/画像更新）を確認する.

### M0-007: 見た目改善（Visual Improvements）
- **修正内容（予定）**: 添付画像の赤/青/緑/ピンク/黄/紫の指摘に基づき、全モード（Dark/Light/Pastel）で視認性と立体感（陰影/境界線）を改善する。  
- **対応方針（予定）**: まずテーマ定義（`./themes/*.json`）で色コントラストを整理し、次に `ttk.Style`（Notebook/Combobox）と `tk` ウィジェット（Entry/Button）の枠線/陰影/フォントを調整する。  

- **要望（ユーザー）**:  
  - **A（赤）**: Dark以外でタブとウィンドウ枠の境界が不明瞭。各タブの下にタブ枠と同色の境界線を追加し、選択タブが分かるようにする。  
    - Darkのみ: 選択タブ背景をメイン黒背景に合わせ、タブ外枠は上記の境界線と同色にする。  
  - **B（青）**: Combobox とボタンに陰影（shading）を付けて分かりやすくする。  
  - **C（緑）**: Combobox の▼と表示領域は、白一色にせず線や色差で判別しやすくする。  
  - **D（ピンク）**: 表示/入力兼用のページ番号欄（右サイドバー）に、ファイルパス入力欄と同等の陰影を付ける。  
  - **E（黄）**: Darkのクールな差分は良いが、Light/Pastelでは背景と同化して見えない箇所があるため、わずかに色をずらして区別できるようにする。  
  - **F（紫）**: パステル紫で縁取られた文字がLightと区別できないため、別の色を使う。  
  - **G（全体）**: Pastelが淡すぎるため、モード切替ボタンのように全体をもう少しカラフルにする。  
  - **H**: Canvas横の「←」「→」ボタンの矢印を太くして見やすくする。  

 - **検証（ユーザー）**:  
  - [✅] AC-M0-007-01: Light/Pastelで、選択中タブが「下線/境界線」等により明確に判別できること。  
          → （日本語）Light/Pastelでタブ境界が背景と同化していたため、`Frame.highlightbackground` が背景色と同一の場合は `Notebook.bg` から少し暗い色を派生して `bordercolor/lightcolor/darkcolor` に適用し、  
             さらに未選択タブ背景を `Notebook.bg` から僅かに暗くして state別 `style.map` で選択タブ（`tab_bg`）とのコントラストを確保するよう修正した（`WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()`）。  
  - [✅] AC-M0-007-02: Darkで、選択中タブ背景がメイン黒背景と一致し、タブ外枠が境界線色で揃うこと。  
          → （日本語）Darkで選択タブ背景がメイン黒背景と一致しない問題に対し、選択タブ背景を `Window.bg` に合わせ、未選択タブは `tab_bg` のままにしつつ、`bordercolor` を境界線色として維持するよう state別 `style.map` を修正した（`WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()`）。  
          ⇒ 未対応。また、全モードで選択中のタブの左側と上側の線の太さが異なるので、他の境界線と太さを合わせてください。  
          → （日本語）Darkでタブ枠に白いハイライトが出る問題に対し、`TNotebook.Tab` の `relief` を `solid` に統一し、
             state別 `style.map` で `bordercolor/lightcolor/darkcolor/focuscolor` を境界線色へ固定して白枠を抑止するよう修正した。  
             また、Light/Pastelで選択タブの左/上の線が細く見える問題に対し、`borderwidth` を明示し、state別に同一値を適用して線幅の見え方を揃えるよう修正した。  
          ⇒ OK  
  - [✅] AC-M0-007-03: Comboboxで、▼と表示領域が白一色にならず判別でき、陰影が付いて立体感があること。  
          → （日本語）`ttk.Combobox` のドロップダウン（Listbox）は `option_add` が生成済みウィジェットへ反映されないため、  
             テーマ切替時に Tcl の `winfo` で Popdown 内 Listbox を走査して `configure` で色を再適用する `refresh_combobox_popdown_listboxes()` を追加し、  
             `WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()` から呼び出すことで、既存ドロップダウンもテーマへ追従するよう修正した。  
             さらに、`ttk.Combobox` の `arrowcolor` をテーマJSONから取得し、`style.map` で state 別に適用することで、  
             選択時/非選択時/フォーカス時等の状態別に色を変化させるよう修正した。  
          ⇒ OK  
  - [✅] AC-M0-007-04: 右サイドバーのページ番号欄が入力欄として認識できる陰影（枠/ハイライト）になること。  
          → （日本語）ページ番号欄（`PageControlFrame.current_page_label`）に、既存の入力欄（`output_folder_path_entry` 等）の Entry テーマ（`bg/fg/highlight/insert`）を適用し、  
             `relief='sunken'`, `bd=1`, `highlightthickness=1` を指定して枠/陰影が常時見えるように修正した（テーマ切替時も再適用）。  
          ⇒ OK  
  - [✅] AC-M0-007-05: Light/Pastelで背景と同化していた境界・枠線が判別できること。  
          ⇒ AC-M0-007-01/02と共に対応完了  
  - [✅] AC-M0-007-06: Pastelで紫系の文字がLightと区別できること。  
          → （日本語）Pastelで紫系の文字がLightと同化していたため、`themes/pastel.json` の入力欄/Combobox/ボタン等の文字色（`fg`/`insertbackground`/`selectforeground`）を、より濃い紫（`#7b4fae`）へ寄せて差別化した。  
          ⇒ OK  
  - [✅] AC-M0-007-07: Pastel全体が「淡すぎる」印象を改善し、カラフルに感じられること。  
          → （日本語）Pastel全体が白っぽく見えるため、`Window.bg`/`Frame.bg`/`Notebook.bg`/`Notebook.tab_bg` を淡い紫寄りの背景色（`#f5effa`/`#fdf6ff`）へ調整し、アクセント色（`highlightcolor`/Progressbar枠等）も `#ff7a8c` へ寄せて彩度を上げた。  
          ⇒ While referencing Dark Mode, please make the color scheme more vivid.
          → （日本語）黄枠（ページ番号欄）をDark参照で周囲から差別化するため、`themes/light.json` / `themes/pastel.json` に `page_number_entry` を追加し、`PageControlFrame` が `page_number_entry` を優先して参照するよう修正した。併せて `total_pages_label` の背景/文字色も調整し、Lightでは僅かな色差、Pastelではよりビビッドな配色になるようにした。  
          → （日本語）PastelでLightと同化して見える箇所（紫/黄緑の指摘領域）について、`base_file_path_label` / `comparison_file_path_label` 等の背景/文字色をアクセント寄りに調整し、Lightとの差別化を強めた。  
          ⇒ Please change the background color of unselected tabs in the red-outlined area of the Dark Mode screen.  
             They blend in with the line color and are indistinguishable.  
             Regarding the Pastel Mode color scheme, it's improved significantly, but please look at the button for changing the color theme.  
             Various pastel colors are being used. Please use a variety of pastel colors to the extent that it doesn't feel jarring.
          → （日本語）Darkの未選択タブが境界線色（`bordercolor`）と同化して判別しづらかったため、`WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()` のDark分岐で、未選択タブ背景（`unselected_tab_bg`）とホバー時背景（`active_tab_bg`）を `tab_bg` から僅かに明るい色へ補正して見分けられるようにした。  
          → （日本語）Pastelが紫寄り一色に見えないよう、`themes/pastel.json` でベース背景/入力欄背景をニュートラル寄り（薄い白青）へ寄せつつ、ラベル・主要ボタン・ページ番号周りに青/ピンク/ミント/黄/ラベンダーのパステル色を控えめに配分して「多色パステル」感を出した（違和感が出ない範囲で彩度差を抑制）。  
          → （日本語）Pastelモードのボタンをよりパステル色寄りに調整するため、`themes/pastel.json` のボタン背景色（`button_bg`）を薄いピンク（`#ffd7d7`）へ変更し、ボタン文字色（`button_fg`）を濃い青（`#3498db`）へ変更した。  
          ⇒ ・In Dark Mode, unselected tabs no longer blend into the border, improving visibility.  
             ・Regarding Pastel Mode: Since the overall background color is white, it looks identical to Light Mode.  
               Please change the background color to one that doesn't clash with other colors in the interface.  
          → （日本語）PastelがLightと同化して見えるため、`themes/pastel.json` の `Window.bg`/`SubWindow.bg`/`Notebook.bg`/`Frame.bg` を薄いラベンダー寄り（`#ede6ff`/`#f6f2ff`）へ調整し、アクセント色（`highlightcolor`/Progressbar枠等）も `#ff7a8c` へ寄せて彩度を上げた。  
          → （日本語）Pastel背景色の差別化対応として、`themes/pastel.json` の `Window.bg`/`SubWindow.bg`/`Notebook.bg`/`Frame.bg` を薄いラベンダー寄り（`#ede6ff`/`#f6f2ff`）へ調整し、アクセント色（`highlightcolor`/Progressbar枠等）も `#ff7a8c` へ寄せて彩度を上げた。  
          ⇒ Below are the requested fixes:  
            ・The color of the selected tab is white, so please change it to a light lavender color. (Red box area)  
            ・The border around the combobox has disappeared, and the background of the unselected part of the pull-down menu has turned white,  
              so please add color. (Blue box area)  
            ・This applies to all theme colors, but the “Select” button lacks shading.  
              Please add shading so it's clearly recognizable as a button. (Yellow-green box area)  

          → （日本語）Pastelで選択中タブ背景が白く見えるため、`themes/pastel.json` の `Notebook.tab_bg` を薄いラベンダー（`#e8dcff`）へ調整し、選択タブ背景が白化しないようにした。  
          → （日本語）PastelでCombobox枠が消え、プルダウン未選択部が白化する問題に対し、`themes/pastel.json` の `primary_combobox` に `bordercolor`/`arrowbackground`/`list_bg`/`list_fg`/`list_selectbackground`/`list_selectforeground` を追加し、`WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()` で `primary_combobox.bordercolor` を優先して枠色を適用するよう修正した。  
          → （日本語）全テーマで「選択」ボタンがフラットで判別しづらいため、`BasePathSelectButton` で `relief='raised'` と `bd=2` を強制し、テーマ再適用時も陰影が維持されるようにした。  

          → （日本語）Pastelで選択中タブ背景が白く見えるため、`themes/pastel.json` の `Notebook.tab_bg` を薄いラベンダー（`#e8dcff`）へ調整し、選択タブ背景が白化しないようにした。  
          → （日本語）PastelでCombobox枠が消え、プルダウン未選択部が白化する問題に対し、`themes/pastel.json` の `primary_combobox` に `bordercolor`/`arrowbackground`/`list_bg`/`list_fg`/`list_selectbackground`/`list_selectforeground` を追加し、`WidgetsTracker._apply_ttk_global_styles()` / `NotebookStyleUpdater.handle_theme_changed()` で `primary_combobox.bordercolor` を優先して枠色を適用するよう修正した。  
          → （日本語）全テーマで「選択」ボタンがフラットで判別しづらいため、`BasePathSelectButton` で `relief='raised'` と `bd=2` を強制し、テーマ再適用時も陰影が維持されるようにした。  
          ⇒ Each mode's screen has been uploaded.  
             It's almost completely finished, but please make the following two corrections:  
             ・The color of the selected tab in Pastel Mode differs from the other modes, and the color below the tab differs from the background color.  
               Please change it to a pale lavender, matching the color below the tab.  
             ・The transition probability to Pastel Mode is currently set to 10%, I believe. Please change it to 30%.  

          → （日本語）Pastelモードの選択中タブ背景がタブ下（タブ内容領域）の背景色と一致せず違和感が出るため、`themes/pastel.json` の `Notebook.tab_bg` をタブ内容側の背景（`Frame.bg`）と揃う淡いラベンダー（`#f6f2ff`）へ変更し、選択タブとタブ下の色が一致するようにした。  
          → （日本語）Dark→（Light/Pastel）切替時のPastel遷移確率が10%だったため、`controllers/color_theme_manager.py` の `random.random() < 0.1` を `random.random() < 0.3` へ変更し、Pastelへ切り替わる確率を30%へ調整した。  
          ⇒ OK

  - [✅] AC-M0-007-08: 「←」「→」が太く/見やすくなること.  
          → （日本語）ページ送りボタン（`BasePageChangeButton`）で `BaseTabWidgets.base_font` から `weight='bold'` のフォントを派生し、  
             デフォルトで適用することで「←」「→」を太字化した（必要なら `font` 引数で上書き可能）。  
          ⇒ OK