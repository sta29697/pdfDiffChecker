# タスクリスト

## M1: PDF Operations / Canvas 操作の整理
  
### M1-001: 現状実装監査と計画（docs/milestone/M1_PLAN.md）  
- [✅] `docs/milestone/M1_PLAN.md` を作成し、現状実装の監査結果と差分・懸念点を統合する。  
  
### M1-002: `Tasks.md` の世代交代（M0→M1）  
- [✅] 旧 `Tasks.md` を `docs/tasks/M0_Tasks.md` へ退避する。  
- [✅] 新しい `./Tasks.md` を作成し、M1用チェック項目を整理する。  
  
### M1-003: コピー保護PDFの操作禁止（表示のみ可）  
- [✅] コピー保護PDFの場合、Canvas表示は許可し、操作（ズーム/パン/回転/変換/挿入/削除/書き出し等）を禁止する。  
       ⇒ ズーム/パン/回転/移動のような表示の変更は許可するが、読み込み時に保存や挿入ができない注意書きを表示して、  
          OKしかない確認Windowを表示して、保存（完了）、挿入のボタンを無効にする。  
       ⇒ 現状、ズーム、パン、移動はできるが、注意書きのWindowの表示が一瞬で消えるため見ることはできない。  
          また、挿入、完了のボタンが押せるようになっている。  
          更に、回転操作をすると現在の仕様と異なる表示をする。  
       → コピー保護PDFの確認ダイアログが即消える問題を、ProgressWindowのgrab解放＋parent指定＋wait_windowで修正しました。  
       → 入力PDF切替時にCanvas上のタイトル/ガイド等のoverlayをクリアするように修正しました（ページ切替は維持）。  
       → テーマ更新等でボタンの state が上書きされるケースに備え、edit系ボタンの有効/無効状態を保持して再適用するように修正しました（state をテーマ適用から除外）。  
       ⇒ OK
       → パステルテーマ等で無効ボタンがクリック可能に見える問題を、set_edit_buttons_enabled で disabled 時に bg=#b0b0b0 / disabledforeground=#808080 のグレーアウト外観を明示設定し、enabled 時にテーマ色を復元するよう修正しました。
- [✅] 禁止操作が試みられた場合、Canvas中央に警告を表示する（赤枠・薄赤背景・白文字、言語対応）。  
       ⇒ For copy-protected PDFs, change the actions to “insert blank page” and disable the “Complete” button.  
  
### M1-004: ショートカットガイド（Ctrl+?）の見た目を仕様へ合わせる  
- [✅] `M049` のショートカットガイダンス表示を、背景=薄黄／枠=濃い黄／文字=緑 に変更する。  
       ⇒ It doesn't display.  
       → `controllers/mouse_event_handler.py` の `_show_shortcut_help()` を、背景=`#fff2a8`／枠=`#e6c200`／文字=`#008000` へ修正しました。  
       → ガイド表示位置をCanvas右上（可視領域の⇒上）＋paddingに固定し、ズーム/スクロールでもずれないように再配置するよう修正しました。 
       ⇒ Regarding the position of the shortcut guide, please adjust the padding to be similar in the upper right corner.  
       → ショートカットガイド表示位置をCanvas可視領域の右上（outer_pad=12）に変更し、_show_shortcut_help() と refresh_overlay_positions() の両方を修正しました。
       ⇒ OK.  
  
### M1-005: 変換通知（Ctrl+R/L/V/H/B）の見た目を仕様へ合わせる  
- [✅] Canvas上部中央に「赤字・赤枠・透明背景」の通知表示を追加し、`M044`〜`M048` を表示する。  
       ⇒ It never displayed even once, not even for an instant, with any shortcut.  
       → `controllers/mouse_event_handler.py` の `_show_notification()` を、赤字/赤枠/透明背景で 1秒以上表示し、連打時は前回タイマーを cancel するよう修正しました。  
       → ページ再描画時に通知が消える問題を、update_stateでoverlayをクリアしない方針へ変更し、可視領域上部中央へ固定表示するよう修正しました。  
       ⇒ OK
  
### M1-006: Ctrl+回転操作（中心点設定/回転ドラッグ）の安定化  
- [✕] Ctrl+クリックで回転中心設定、Ctrl+ドラッグで回転が安定して動作すること。  
       ⇒ Even though I held down the Ctrl button, the red dot moved to the initial point where I first placed the mouse cursor to drag.  
       ⇒ Also, even though I was just slowly moving the mouse downward to drag, it repeatedly rotated in tiny clockwise and counterclockwise angles.  
       → `controllers/mouse_event_handler.py` で回転中心のCanvas座標変換、中心点=赤点固定、角度差の正規化と丸め撤廃、Ctrl解放で回転モード終了を実装しました。  
       → Ctrl+ドラッグ回転の再描画後も回転中心の赤点を再生成し、Ctrl解放まで消えないよう修正しました。  
       → 画面座標（Y下向き）の補正＋角度アンラップにより回転方向をドラッグ方向へ一致させ、最小刻みを0.1°にしました。  
       → Ctrl押下中の再クリックで回転中心（赤点）が移動する挙動を廃止し、最初のクリック位置に固定してCtrl解放まで維持するよう修正しました（ホイールズーム後もoverlay再配置）。  
       → 回転中心（赤点）を画像座標系（原画像中心からのオフセット）で管理し、_canvas_to_image_offset / _image_offset_to_canvas ヘルパーで座標変換することで、ズーム/回転/パン後も画像上の同一点に追従するよう修正しました。  
       → 回転時にピボット補正付きtranslation調整を実装し、赤点を中心として画像が回転するよう修正しました（_compute_rotated_dims で回転後画像サイズを算出し、新tx/tyを逆算）。  
       → 回転角度の量子化を floor→round に変更し、0.1°未満の変化を無視するヒステリシスを追加してジッタ（CW/CCW行き来）を解消しました。  
       → ガイダンス表示（M042等）を黒地stipple背景から赤字・赤枠(outline=#ff0000)・透明背景(fill="")に変更しました。  
       → pdf_ope_tab.py の _display_page で原画像サイズを mouse_handler.set_original_image_size() に渡し、回転ピボット計算に使用するよう修正しました。
       ⇒ NG.  
          When moving the mouse, it repeatedly rotates clockwise ⇔ counterclockwise by approximately ±20° during movement. Additionally,  
          it continues rotating for about 1 second even after releasing the Ctrl button to turn off rotation mode.  
          Moving the mouse slowly only reduces the rotation angle but has the same effect. Can this be fixed?  
          If not, we'll consider a different operation method.  
       → ±20°振動の根本原因を特定: ドラッグ中に毎フレーム回転中心Canvas座標を再計算(`_rotation_center_canvas_pos`)していたため、座標変換の微小誤差がフィードバックループを形成し角度が発散していました。  
       → 修正1: ドラッグ中は回転中心のCanvas座標を更新せず、初期クリック位置に固定（赤点位置も固定）。ドラッグ終了後に画像座標から再計算。  
       → 修正2: 増分累積方式（delta蓄積）を廃止し、ドラッグ開始角度と現在角度の**絶対差分方式**に変更。浮動小数点誤差の累積を根本排除。  
       → 修正3: 回転更新を~30fps（33ms間隔）にレートリミットし、イベントキュー滞留を防止。Ctrl解放後の残留回転を大幅に短縮。  
       ⇒ Much smoother. However, vibrations may still occur at certain angles. Mouse release doesn't stop rotation as quickly as Ctrl release.  
       → 修正4: ±180°境界でatan2がジャンプする問題に対し、1フレームあたり120°超の角度変化を棄却するアンチジャンプフィルタを追加。  
       → 修正5: ヒステリシスを0.05°→0.2°に増加し、マウス位置ジッタによる微小振動を吸収。  
       → マウス解放時の遅延はTkinterイベントキュー特性（ButtonRelease前の滞留Motionイベント処理）に起因。レートリミットにより最大33ms程度に抑制済み。  
       ⇒ Indeed,  
          ・ Jumping near specific angles no longer occurs.  
          ・ Slow dragging has become even smoother and more stable.  
          ・ Rotation stops faster upon mouse release than before.  
          ・ High-speed drag angle jumps still occur. I understand an anti-jump filter has been added for angles exceeding 120° per frame,  
             but what exactly constitutes “per frame”? Could you clarify the time duration, assuming standard display specs in frames per second?  
             I suspect further fine-tuning here will be key.  
       → B案採用: 絶対角度差分方式を廃止し、増分累積方式（delta蓄積）に戻しました。回転中心Canvas座標の固定・30fpsレートリミット・0.2°ヒステリシスは維持。  
       → 増分方式では各フレーム間のdeltaが常に小さいため、±180°境界問題が構造的に発生せず、アンチジャンプフィルタを削除。>360°回転にも自然に対応。  
       → レートリミットでスキップされた期間のdeltaは次処理フレームにまとめて反映（回転中心固定のため安定）。  
       ⇒ I uploaded one image.  
         ・ I slowly rotated it as indicated by the blue arrow.  
         ・ When I paused the mouse at the red arrow location, the image jumped multiple times.  
        　　At this point, after releasing both Ctrl and the mouse, it felt like it jumped for about one second.  
         ・ My guess is that mouse movements crossing the four quadrants separated by the yellow-green lines cause the jumping.  
       → 残留イベント即時破棄(M1-006): Ctrl解放後もキューに残るMotionイベントが回転を継続させていた問題を修正。  
         (1) `_is_ctrl_physically_pressed()` を追加: Windows API `GetAsyncKeyState(VK_CONTROL)` でCtrlキーのリアルタイムハードウェア状態を取得。キュー内のMotionイベント処理時にCtrlが既に離されていれば即座に回転モードを終了し残りを破棄。非Windowsではフォールバックで `True` を返しKeyReleaseイベントに依存。  
         (2) `_on_ctrl_key_release()` で `self.__dragging = False` を設定: KeyRelease以降のキュー内Motionイベントが `on_mouse_drag` 冒頭の `if not self.__dragging: return` で即スキップされるようにした。  
         (3) `on_mouse_drag()` 回転ブランチ冒頭に `_is_ctrl_physically_pressed()` チェックを追加: イベントの `state` にCtrlフラグがあっても実キーが離されていれば `_on_ctrl_key_release()` を呼び出して即終了。  
- [✅] 回転モード表示のメッセージコード（M042 vs 仕様）を確定し、コードと `message_codes.json` の整合を取る。  
       ⇒ OK.

### M1-007: 表示ページ削除ボタンの追加（M1_PLAN.mdのNo.11）
- [✅] 「空白ページ挿入」のボタンの下に「表示ページ削除」ボタンを追加する。  
      ボタンが押されたら、表示中のページを削除する。削除前に「削除してよろしいですか？」の確認ダイアログを表示する。  
       → UIメッセージコード U061（ページ削除）、U062（確認ダイアログ）、U063（最後の1ページ削除不可）を `message_codes.json` に追加。  
       → 3テーマJSON（dark/light/pastel）に `delete_page_button` エントリを追加。  
       → `PageControlFrame.__init__` に `on_delete_page` コールバックパラメータを追加し、`BaseButton` で削除ボタンを row=5 に配置。export を row=6、transform セクションを row=7〜12 にシフト。  
       → `set_edit_buttons_enabled()` に `delete_page_btn` の有効/無効制御を追加（コピー保護PDF対応）。  
       → `pdf_ope_tab.py` に `_on_delete_page()` を実装: 残1ページ時は削除拒否（U063）、`messagebox.askyesno` で確認後に `base_transform_data`・`base_page_paths` から該当ページを除去、`page_count` 更新、UI再構築。  
       ⇒ Images 1 and 2 are of the screen after a blank page was inserted as page two.  
          Image 3 is the image after the inserted blank page was deleted.  
          Image 4 is the first image of page two, and the part framed in red is different from the image of page two in the other images.  
          Images 1 through 3 have the same image for the last two pages, so I think you forgot to change the path of the read file name when adding or deleting pages.
       → パス管理バグ修正: `_on_insert_blank_page()` で空白ページのファイル名に `uuid` を使用し既存ファイルの上書きを防止。さらに新規パスを `base_page_paths` の正しい位置に `insert()` するよう修正。これにより挿入・削除後もページインデックスとファイルパスの対応が維持される。  
       ⇒ OK.  
### M1-008: 座標/角度/移動距離の表示・入力UIの追加（M1_PLAN.mdのNo.12）
- [✅] Canvas右のボタンエリアに座標/角度/移動距離の表示・入力UIを追加する。  
      座標はCanvas上の表示位置、角度は回転角度、移動距離はCanvas上の移動距離を表示する。  
      入力UIは、それぞれの値を直接入力することができる。  
       → `PageControlFrame` に変換情報セクションを追加（セパレータ＋ヘッダ＋X/Y/Angle/Scaleの4つのラベル付きEntry）。  
       → UIメッセージコード U064-U069 を `message_codes.json` に追加（Transform/X:/Y:/Angle:/Scale:/Apply）。U061-U063はM1-007用に予約。  
       → `_display_page()` 末尾で `update_transform_info()` を呼び出し、ページ切替・回転・移動・ズーム時にリアルタイム反映。  
       → Entryにフォーカス中は外部からの値上書きをスキップし、ユーザー入力を保護。  
       → EnterキーでEntryの値を読み取り→バリデーション→ `base_transform_data` に反映→ `_on_transform_update()` で再描画。  
       ⇒ For the block added this time, please add validation to convert full-width characters to half-width.  
          For the block added this time, since it's the same for all color themes, please adjust it to match the theme color.
       → 全角→半角変換: `_normalize_fullwidth()` を追加。`unicodedata.normalize("NFKC")` で全角数字・記号を半角化し、カタカナ長音符（ー）もマイナスに変換。`_on_transform_entry_submit` で適用。  
       → テーマカラー対応: `apply_theme_color()` にセパレータ・ヘッダ・サブフレーム・ラベル・Entryのテーマ更新処理を追加。ウィジェット参照をインスタンス変数に保存。  
       → 「完了」ボタンを「保存」に変更（U037: "Complete"→"Save" / "完了"→"保存"）。  
       → 重複ログ修正: `color_theme_change_button.py` の `_update_button_theme` 内の L121 ログ出力を削除（`_on_click` で既に出力済み）。  
       ⇒ The text color in the “Transformation Information” section added to the right-side operation menu  
          in Canvas is a uniform color that does not match the theme color. Please make this match the theme color as well.  
       → テーマカラー未追従修正: `apply_theme_color()` で `__swfg`/`__swbg` を `component_theme` から更新するように修正。これによりセパレータ・ヘッダ・ラベルの色がテーマ変更に追従する。  
       → 重複ログ修正: `apply_theme_color()` 内の `total_pages_label`/`prev_page_btn`/`next_page_btn`/`insert_blank_btn` への明示的 `apply_theme_color` 呼び出しを削除（`WidgetsTracker` が自動呼び出し済みのため重複していた）。  
       ⇒ ・ The color of the fixed text in the “Conversion Information” block (highlighted in red) is the same across all themes.  
             Please change this text color to match the theme color as well.  
          ・ Also, please insert a half-width space between X and :, and between Y and :.  
          ・ Regarding the logs, duplicates still exist as shown below. Please resolve them.  
       → ラベル色修正: `"page_control"` キーが各テーマJSONに存在しないため `__swfg` がデフォルト固定だった。`Frame.fg` をフォールバックに使用するよう `__init__` と `apply_theme_color()` を修正。dark=`#43c0cd`、light=`#000000`、pastel=`#6b6b6b` に追従。  
       → U065/U066 修正: `message_codes.json` の "X:" → "X :"、"Y:" → "Y :" に半角スペースを挿入。  
       → 重複ログ修正: `base_label.py` の `_config_widget()` 内 L049 ログ出力を削除。`apply_theme_color()` の L087 ログのみ残し、1ウィジェット1行に削減。  
       ⇒ - We confirmed that the text color of the "Change Information" block has changed for each color theme, and that X: and Y: have been changed.  
          - There are duplicates in the log.  
          - The following error log has been saved, so please investigate and take action. Since no other similar errors have been reported,  
            this may be an error that only occurs when building operation blocks next to the Canvas.
       → `__color_key` エラー修正: `BasePageChangeButton` と `InsertBlankPageButton` が `super().__init__()` の後に `self.__color_key` を設定していたが、`BaseButton.__init__` 内で `WidgetsTracker` に登録→即テーマ適用→MROにより子クラスの `apply_theme_color` が呼ばれ、未設定の `_子クラス__color_key` を参照して AttributeError が発生していた。子クラスの冗長な `__color_key`・`apply_theme_color`・`_config_widget`・`WidgetsTracker` 登録を削除し、`BaseButton` に委任。  
       → ログ重複修正: `base_path_select_button.py` の L083 ログが `color_key` なしで出力されていたため、2つのインスタンスが同一メッセージを出力。L083 メッセージに `{0}` パラメータを追加し、呼び出し側で `color_key` を渡すよう修正。  
       ⇒ OK.

### M1-009: フッターに小さく表示するメタ情報（M1_PLAN.mdのNo.13）
- [✅] フッターに小さくメタ情報（DPI、サイズ等）を表示する。  
      情報が無い場合は"-"を表示する。  
       → `pdf_ope_tab.py` の `frame_main2` に `_footer_meta_label`（font=8pt, anchor=w）を row=1 に配置。初期値は "-"。  
       → `_update_footer_meta()` メソッドを追加: PIL Image から `width`/`height`（px）と `info["dpi"]` を取得し、`"595 x 842 px  |  96 DPI"` 形式で表示。情報欠落時は "-" を表示。  
       → `_display_page()` 末尾で `_update_footer_meta(pil_image)` を呼び出し、ページ切替時にリアルタイム更新。  
       → `apply_theme_color()` にフッターラベルの bg/fg テーマ適用処理を追加。  
       → DPI表示修正: PNG ファイルは DPI メタデータを埋め込まないため `pil_image.info["dpi"]` が常に None だった。`tool_settings.setted_dpi`（変換時の DPI 設定値）から取得するよう修正。  
       → 用紙サイズ推定: `_estimate_paper_size()` を追加。ピクセル寸法と DPI から物理サイズ（mm）を算出し、A0〜A5・B3〜B5・Letter・Legal と±5mm 許容で照合。一致時はフッターに `"510 x 361 px  |  96 DPI  |  A4"` のように表示。  
       ⇒ Is it correct that the paper size isn't displayed because there's no DPI information for the paper?  
          A title would be nice. Something like "Pixel size: 〇px x 〇px | Pixel density: 〇dpi | Paper size: 〇".  
          I assume the title changes depending on the language settings.  
          The third file was printed from PDF to PDF at 300dpi, but is it possible that the meta information isn't being accessed properly?  
          I also had it read a company's product introduction PDF and a research paper PDF, but it couldn't read the dpi for all of them.  
       → DPI取得バグ修正: `getattr(tool_settings, 'setted_dpi', None)` は `tool_settings` がモジュールのため常に `None` を返していた。`UserSettingManager.get_setting("setted_dpi")` で設定値を取得し、`_load_and_display_pdf()` で `self._conversion_dpi` に保存。さらに変換時に `dpi=self._conversion_dpi` を `process_with_progress_window()` に渡すよう修正。  
       → i18nタイトル追加: UIメッセージコード U072（ピクセルサイズ:）、U073（ピクセル密度:）、U074（用紙サイズ:）を追加。フッター表示を `"ピクセルサイズ: 595 x 842 px  |  ピクセル密度: 96dpi  |  用紙サイズ: A4"` 形式に変更。言語設定に応じてラベルが英語/日本語で切り替わる。  
       ⇒ As you can see in the red frames in both images, the zoom ratio has not been taken into account, so if you zoom in and out with the mouse wheel,  
          the "paper size" will change even if the document is the same. Please correct the calculation formula so that the correct paper size is fixed regardless  
          of zooming in and out in Canvas.   
          Also, in the case of multi-page images, this may be different for each page, so please make sure the accurate "paper size" for each page is displayed.  
       → ズーム不変修正: `_display_page()` で PNG 読込直後（変形前）に `self._original_page_width` / `self._original_page_height` を保存。`_update_footer_meta()` は変形後の `pil_image` サイズではなく保存済み原寸値を使用するよう変更。これによりズーム・回転に依らず用紙サイズが一定になる。マルチページでもページ切替時に各ページの原寸が再取得されるため正確に表示。  
       ⇒ OK.  

### M1-010: 一括編集チェックボタンの追加（M1_PLAN.mdの要求4に対応）
- [✅] Canvas右のボタンエリアに「一括編集」チェックボタンを追加する。  
      入力ファイルが縦横ページ混合やサイズが異なっている場合は、一括編集チェックボックスを無効にして禁止する。
      同じ縦横、同じサイズの入力ファイルが指定されている場合は、一括編集チェックボックスを有効にして許可する。
      チェックボックスがONの場合、１つのページの操作を全ページに反映させる。
      チェックボックスがOFFの場合は、表示中のページの操作を個別に行う。
       → UIメッセージコード U070（一括編集）、U071（サイズ不一致時の無効メッセージ）を `message_codes.json` に追加。  
       → `PageControlFrame` に `tk.Checkbutton`（`batch_edit_var: BooleanVar`）を row=7 に配置。transform セクションを row=8〜13 にシフト。テーマ適用処理を `apply_theme_color()` に追加。  
       → `set_batch_edit_enabled()` メソッドを追加: 無効時はチェックボックスを DISABLED にし `batch_edit_var` を False にリセット。  
       → `pdf_ope_tab.py` に `_check_batch_edit_eligibility()` を追加: 全ページの PNG 画像サイズを比較し、全ページ同一サイズなら有効、異なれば無効にする。PDF読み込み・ページ挿入・ページ削除後に呼び出し。  
       → `_on_transform_update()` を拡張: `batch_edit_var` が True の場合、現在ページの transform データを全ページにコピーしてから再描画。マウス操作（ズーム/パン/回転）・Entry入力の両方で一括反映。  
       → 空白ページサイズ修正: `_on_insert_blank_page()` で挿入する空白ページのサイズを、現在表示中のページの画像サイズ（width×height）に合わせるよう変更。A4縦表示中ならA4縦、A3横表示中ならA3横の空白ページが挿入される。現ページ画像が読めない場合はフォールバックとして 595×842（A4縦相当）を使用。  
       → U071 は将来のツールチップ表示等に使用可能な予備コードとして保持。  
       ⇒ OK.  

### M1-011: ショートカットガイド（ヘルプオーバーレイ）の表示制御改善
- [✅] ページ切替や再描画のたびにショートカットガイドが再表示される問題を修正する。  
      `_display_page()` → `refresh_overlay_positions()` 等の再描画パスで、ガイドの表示状態フラグが保持されない。  
      表示/非表示状態を明示的なフラグ（例: `__shortcut_help_visible`）で管理し、`refresh_overlay_positions()` ではフラグがTrueの場合のみ再描画する。  
      将来的に他のタブでも同じショートカットガイド機構を使うため、表示制御ロジックを汎用化しておく。  
      検証: ページ切替・ズーム・回転操作後にガイドの表示状態が意図通り維持されるか手動確認。  
       → 重複バインド除去: `attach_to_canvas()` から Ctrl+?/Ctrl+Shift+H 等のショートカットヘルプ用バインドを削除。`pdf_ope_tab._bind_global_shortcuts()` の `bind_all` のみでイベント処理し、キャンバスフォーカス有無で二重発火する問題を解消。  
       → フラグ―アイテム整合検証: `refresh_overlay_positions()` でヘルプ再配置前に `find_withtag("overlay_shortcut_help")` でキャンバスアイテムの存在を検証。外部削除（`canvas.delete("all")`等）でアイテムが消えた場合、`__shortcut_help_visible` フラグを False にリセットし「非表示なのに再表示される」状態を防止。  
       → 汎用API追加: `shortcut_help_visible` プロパティ（読取専用）と `set_shortcut_help_visibility(visible)` メソッドを `MouseEventHandler` に追加。外部タブからプログラム的にヘルプ表示を制御でき、将来の他タブ対応が容易になる。  
       ⇒ The shortcut guide flickers when rotating or zooming.  
       → フリッカー修正: `refresh_overlay_positions()` 内でヘルプテキストを一時的に (0,0) へ移動し `update_idletasks()` で強制再描画していた処理を削除。現在位置のまま `bbox()` でサイズを取得し、直接目標位置へ `coords()` するよう変更。また `_display_page()` 内の `refresh_overlay_positions()` 二重呼び出し（画像描画直後＋状態更新後）を1回（状態更新後のみ）に統合し、不要な再配置を排除。  
       → 重複バインド除去を撤回: `attach_to_canvas()` のキャンバスレベルバインドを復元。Tkinter では `bind` コールバックが `"break"` を返すと `bind_all` への伝播が止まるため二重発火は起きない。キャンバスバインドと `bind_all` の両方を維持し、フォーカス状態に依存せず確実にショートカットが動作するようにした。  
       ⇒ OK.  

---  
更新日: 2026-02-15
