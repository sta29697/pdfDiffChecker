# Release checklist (Windows / Nuitka / GitHub Releases)

Use this list for each tagged release so steps stay reproducible. Adjust version strings everywhere in one pass.

## 1. Version and metadata

- [ ] `pyproject.toml`: project version.
- [ ] `main.py`: user-visible or build-stamped version if applicable.
- [ ] `build_nuitka.ps1`: `--file-version` and `--product-version` (four-part Windows style, e.g. `1.0.8.0`).

## 2. Dependencies

- [ ] If dependencies changed: run `uv lock` (or project-standard sync) and commit `uv.lock` with a clear message (e.g. `chore: sync uv.lock`).

## 3. Build the Windows executable

- [ ] From the repo root, run the Nuitka script (example):

  `powershell -ExecutionPolicy Bypass -File .\build_nuitka.ps1`

- [ ] On first failure (e.g. file in use / AV): retry once; exclude build output paths from real-time scanning if needed.

## 4. Verify the artifact locally

- [ ] Confirm `build\nuitka\pdfDiffChecker.exe` exists and has a recent timestamp (do not rely on `git status` alone for the binary).
- [ ] Optional smoke test: run the exe and launch the main window.

## 5. Git tag and push

- [ ] Commit all release-related changes on the intended branch (usually `main`).
- [ ] Create an annotated tag matching the release (e.g. `v1.0.8`) and push the tag:

  `git push origin v1.0.8`

## 6. GitHub Release with asset

- [ ] Create the release and attach the exe in one step, for example:

  `gh release create v1.0.8 --title "v1.0.8" --notes-file path\to\notes.md build\nuitka\pdfDiffChecker.exe`

- [ ] Confirm assets on GitHub:

  `gh release view v1.0.8 --json assets`

  Expect at least `pdfDiffChecker.exe` in `assets`.

## 7. Housekeeping

- [ ] If the repo tracks the exe under `.gitignore` exceptions, decide whether to commit the binary or distribute only via Releases; keep policy consistent with `.gitignore`.
- [ ] Do not commit real user paths in `configurations/user_settings.json`; use placeholders for examples.
