# M8 タスク一覧

- 目的・背景は `docs/milestone/M8_PLAN.md` を参照。

## M8-A: ドキュメントとリリース手順

- [x] `docs/dev/RELEASE_CHECKLIST.md` に「`gh release create` では exe を**必ず**パスで渡す／アップロードする」旨を明記し、コピペ用例を追加する。
- [x] `.gitignore` の `build/` 例外を読みやすく整理し、意図（`nuitka` 配下は原則無視、exe のみ追跡可）が伝わるようにする。
- [x] （任意）`gh release create ... build\nuitka\pdfDiffChecker.exe` をラップするスクリプトを `scripts/` に追加する。

## M8-B: コンボボックスと矢印キー

- [x] `KeyboardNavigationShell` から **Down キーでの `ttk::combobox::Post` 自動実行**を削除する。
- [x] **readonly コンボ**は **Enter / KP_Enter** のみで Post する（既存ハンドラを維持・整理）。
- [x] ポップダウンが**閉じている**ときは、コンボ上の **Up/Down を空間フォーカス**の対象に含める。ポップダウンが**開いている**ときは従来どおりリストが矢印を処理する。

## M8-C: 差分強調オーバーレイ

- [x] `build_diff_highlight_overlay_rgba` に、両レイヤーインクが重なる画素での **RGBA ピクセル差分ベースの補助マスク**を追加する（パラメータ化）。
- [x] `views/main_tab.py` から適切な閾値で呼び出す（必要なら後から UI 設定に繋げられる形にする）。

## M8-D: 検証

- [ ] 上記 `M8_PLAN.md` の検証手順を満たすこと。
