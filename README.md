# pdfDiffChecker

A Tkinter-based application for comparing PDF files page by page, supporting advanced PDF/image operations, multi-language logging, and customizable color themes.

## Features
- Compare two PDF files visually, highlight differences
- GUI built with Tkinter (ttk)
- PDF rendering via pypdfium2
- Image processing with Pillow
- Multi-language support (Japanese/English) for UI and logs
- Color theme selection and instant theme switching
- Tabbed interface: PDF comparison, PDF operations, file extension/size tools, description, licenses
- User settings saved to JSON
- Logging with throttling and debug log output
- Temporary files managed in a dedicated directory
- Pytest-based testing ("tests" directory)
- ER diagrams in "docs" directory

## Requirements
- Python 3.12
- uv
- numpy
- pillow
- pdf2image
- tkinterdnd2
- matplotlib
- pypdfium2
- pypdf

## Usage
1. Install uv (if needed):
   ```sh
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

## Coding Guidelines
- Comments and documentation: English
- Variable and function names: English (snake_case)
- Class names: PascalCase
- Constants: UPPER_SNAKE_CASE

## License
See `licences.txt` for license details.

---
For more details, refer to the in-app description tab or documentation in the `docs` directory.
