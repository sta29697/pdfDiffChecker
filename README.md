# pdfDiffChecker

Tkinter / ttk desktop app to compare two PDFs side by side, with extra tabs for PDF utilities, image and file-extension/size workflows, in-app help, and license documents. UI strings and logs support **Japanese and English**; **dark / light / pastel** themes are built from JSON under `themes/`.

## Features

- **Main** — Compare two PDFs, page navigation, canvas overlays, export-oriented actions (see `views/main_tab.py`).
- **PDF operation** — PDF-focused tools (`views/pdf_ope_tab.py`).
- **Image / file extension & size (U006)** — Image and conversion-style tools (`views/image_ope_tab.py`).
- **Description** — Operational notes and links (`views/description.py`).
- **Licenses** — Reads `licences_tree.txt` and `licences.txt` from the workspace (`views/licenses.py`).
- PDF rendering via **pypdfium2**; raster work with **Pillow**; charts where used via **matplotlib**.
- User settings persist as JSON (development: under the repo; **frozen / .exe**: under `%LocalAppData%\pdfDiffChecker\` — see `configurations/tool_settings.py`).
- Throttled logging and optional `logs/debug.log` in development layout.
- Tests under `tests/` (pytest). Additional diagrams under `docs/` (drawio, architecture markdown).

## Requirements

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for environments and runs  
- Runtime Python packages are declared in **`pyproject.toml`** (e.g. numpy, pillow, pypdfium2, pypdf, pdf2image, matplotlib, tkinterdnd2, reportlab, svglib, typing-extensions). Prefer that file as the source of truth rather than duplicating full lists here.

System packages may be needed for some PDF/raster paths (e.g. Poppler for `pdf2image` on some setups); adjust per your OS.

## Usage (development)

1. Install uv (Windows PowerShell example):

   ```powershell
   irm https://astral.sh/uv/install.ps1 | iex
   ```

2. Install dependencies:

   ```sh
   uv sync
   ```

3. Run the application:

   ```sh
   uv run python main.py
   ```

## Windows onefile executable (optional)

The repository includes **`build_nuitka.ps1`**, which builds **`pdfDiffChecker.exe`** (Nuitka standalone/onefile) under `build/nuitka/`. The `build/` directory is gitignored; distribute binaries via **GitHub Releases** (or similar), not by committing large `.exe` files to git.

Example:

```powershell
.\build_nuitka.ps1 -OneFile
```

## Documentation

- **Milestone / task plans**: `docs/milestone/`, `docs/tasks/`
- **Architecture overview (Mermaid)**: `docs/architecture.md`
- **License text**: `licences.txt`, `licences_tree.txt`

## Coding guidelines

- Comments and docstrings in code: **English** (project convention).
- Names: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.

## License

See `licences.txt` for third-party and project license notes.
