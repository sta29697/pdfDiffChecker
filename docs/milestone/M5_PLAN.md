# M5 Plan — 文章類の整理（ドキュメント整備）

## 目的
- M5 のチェックリストは `docs/tasks/M5_Tasks.md` に置き、リポジトリ直下の `Tasks.md` は現在のマイルストーン（例: M6）用とする。完了済み M4 の詳細チェックリストは `docs/tasks/M4_Tasks.md` へ集約する。
- 新規参画者・将来の自分が、**現行コードと同じ前提**でアプリを理解・実行できるドキュメントに揃える。
- 全体のモジュール関係と処理の流れを **図（Mermaid）** で把握できるようにする。

## 現状整理
- `README.md` は機能・依存の列挙があるが、`main.py` の 5 タブ構成や配布ビルド（`build_nuitka.ps1`）との関係が十分に書かれていない部分がある。
- アプリ全体を俯瞰する単一の架構ドキュメント（クラス間・イベント連携の地図）が未整備。
- 説明タブ（`views/description.py`）は M4 でマイルストーンプランと整合させたが、利用者フィードバックによる追記の余地がある。

## スコープ
- 対象:
  - `README.md`
  - `docs/architecture.md`（新規）
  - （任意）`views/description.py`
  - 作業管理: `docs/tasks/M5_Tasks.md`、ルート `Tasks.md`（他マイルストーン用）、`docs/tasks/M4_Tasks.md`
- 非対象:
  - 機能仕様の変更（コードの挙動を変えるリファクタ）
  - ライセンス文面そのものの法務確定（M4-005 の判断は別途）

## 実装方針

### 1) README の更新
- 実行方法: `uv sync` と `uv run python main.py` を主路線とする。
- タブ: Main（比較）、PDF 操作、画像・拡張子/サイズ（U006）、説明、ライセンスの 5 つとコード上の対応を簡潔に記載する。
- 依存: 手書きの列挙と `pyproject.toml` の二重管理を避け、**正は `pyproject.toml`** と明記し README では概要のみにするか、主要パッケージに限定する。
- Windows 向けワンファイル EXE を配布する場合は、`build_nuitka.ps1` と GitHub Releases への誘導を短く書く（詳細はスクリプト内コメントに任せてよい）。

### 2) `docs/architecture.md`
- **Mermaid** を用いる（GitHub 上でレンダリングされやすい）。
- 推奨セクション例:
  - 起動シーケンス: `main()` → `initialize_application()` → `create_main_window()` → Notebook と各タブの生成。
  - レイヤ図: `configurations` / `controllers` / `views` / `widgets` / `utils` の依存の向き。
  - 横断関心: `EventBus` と `THEME_CHANGED`、`ColorThemeManager`、`UserSettingManager`、`MessageManager`。
  - 各タブのエントリクラス（`CreateComparisonFileApp`、`PDFOperationApp` 等）と `main.py` の関係。
- 全クラス・全関数の網羅は不要。読者が「どこを開けばよいか」分かる粒度を目標とする。

### 3) 説明タブの更新（任意）
- フィードバックが付いた項目だけを `views/description.py` に反映する。
- 変更時は `docs/tasks/M5_Tasks.md` の M5-003 を更新し、必要なら `architecture.md` の用語と揃える。

## タスク分解（`docs/tasks/M5_Tasks.md` と対応）

### M5-001: README の現行化
- [✅] 上記方針に沿って `README.md` を編集する。

### M5-002: アーキテクチャ文書
- [✅] `docs/architecture.md` を作成し、Mermaid 図を 2 本以上含める。

### M5-003: 説明タブ（任意）
- [-] フィードバックに応じて `views/description.py` を更新する。

## 検証手順
1. 新規クローン想定で `README.md` の手順のみを見て `uv sync` → `uv run python main.py` が再現できるか確認する。
2. `docs/architecture.md` を開き、図と本文が `main.py` のタブ追加順・主要 import と矛盾しないか確認する。
3. （M5-003 を実施した場合）説明タブの表示と README の用語が大きく矛盾していないか確認する。

## 受け入れ基準
- M4 の詳細チェックリストが `docs/tasks/M4_Tasks.md` にあり、M5 のチェックリストが `docs/tasks/M5_Tasks.md` にある（ルート `Tasks.md` は現行マイルストーン用）。
- README が現行コード・依存の「正」と整合している。
- `docs/architecture.md` が存在し、起動から UI 構築までの流れと主要コンポーネント関係が図で読める。
