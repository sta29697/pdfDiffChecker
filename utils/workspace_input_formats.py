"""Input file patterns shared by Main and PDF Operation tabs (dialogs and validation).

These must stay aligned so packaged builds accept the same sources as development.
"""

from __future__ import annotations

from typing import Final, FrozenSet, List, Tuple

# Lower-case suffixes including the dot (matches BasePathEntry / Path.suffix.lower()).
MAIN_PDF_OPE_INPUT_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".webp",
        ".ico",
        ".tga",
        ".svg",
    }
)

_MAIN_SUPPORTED_GLOB: Final[str] = (
    "*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.ico *.tga *.svg"
)


def main_pdf_ope_askopen_filetypes() -> List[Tuple[str, str]]:
    """File type tuples for ``askopenfilename`` on Main and PDF Operation tabs.

    Returns:
        Ordered filter list with an explicit all-supported pattern and ``*.*``.
    """
    return [
        ("All supported", _MAIN_SUPPORTED_GLOB),
        ("PDF files", "*.pdf"),
        (
            "Image files",
            "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.ico *.tga",
        ),
        ("SVG files", "*.svg"),
        ("All files", "*.*"),
    ]


def main_pdf_ope_drop_suffixes() -> List[str]:
    """Suffixes (with dot) accepted by drag-and-drop on those tabs."""
    return sorted(MAIN_PDF_OPE_INPUT_EXTENSIONS)
