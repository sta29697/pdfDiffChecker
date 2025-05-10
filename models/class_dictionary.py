from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class FilePathInfo:
    """Information about a file and its metadata.

    This class stores file path information and associated metadata for PDF and image files.
    The metadata dictionary can store various file-specific information such as:
    - Page count
    - File format
    - Creation date
    - Author
    - etc.

    Attributes:
        file_path (Path): Path to the file
        file_name (str): Name of the file without extension
        file_extension (str): File extension (e.g., 'pdf', 'png')
        file_page_count (int): Number of pages in the file
        file_meta_info (Dict[str, Any]): Dictionary containing file metadata
        file_histogram_data (Optional[List[Any]]): Histogram data for binary image processing
                                                  Used for determining threshold when separating
                                                  background and drawing in binary images
    """

    file_path: Path
    file_name: str = field(init=False)
    file_extension: str = field(init=False)
    file_page_count: int = field(default=0)
    file_meta_info: Dict[str, Any] = field(default_factory=dict)
    file_histogram_data: Optional[List[Any]] = field(default=None)

    def __post_init__(self) -> None:
        """Initialize derived attributes after instance creation.

        This method is automatically called after the dataclass is instantiated.
        It extracts the file name and extension from the file path.
        """
        self.file_name = self.file_path.stem
        self.file_extension = self.file_path.suffix.lower().lstrip(".")


@dataclass
class FolderPathInfo:
    """Information about a folder and its metadata.

    This class stores folder path information.

    Attributes:
        folder_path (Path): Path to the folder
    """

    folder_path: Path

    def __post_init__(self) -> None:
        """Initialize derived attributes after instance creation.

        This method is automatically called after the dataclass is instantiated.
        """


@dataclass
class CurrentAreaInfo:
    """Current area dimensions.

    This class stores the current area dimensions.

    Attributes:
        width (int): Width of the current area
        height (int): Height of the current area
    """

    width: int
    height: int


@dataclass
class WidgetPosition:
    """Widget grid position.

    This class stores the position of a widget in a grid.

    Attributes:
        col (int): Column index of the widget
        row (int): Row index of the widget
        col_span (int): Number of columns the widget spans (default: 1)
        row_span (int): Number of rows the widget spans (default: 1)
        padx (int): Horizontal padding (default: 0)
        pady (int): Vertical padding (default: 0)
        sticky (str): Sticky position (default: "nw")
    """

    col: int
    row: int
    col_span: int = 1
    row_span: int = 1
    padx: int = 0
    pady: int = 0
    sticky: str = "nw"


@dataclass
class EntryColor:
    """Entry widget color theme.

    This class stores the color theme for an entry widget.

    Attributes:
        fg (str): Foreground color
        bg (str): Background color
        col_hlfg (str): Highlight foreground color
        col_hlbg (str): Highlight background color
    """

    fg: str
    bg: str
    col_hlfg: str
    col_hlbg: str


@dataclass
class DialogButtonColor:
    """Dialog button color theme.

    This class stores the color theme for a dialog button.

    Attributes:
        col_acfg (str): Active foreground color
        col_acbg (str): Active background color
        col_inacfg (str): Inactive foreground color
        col_inacbg (str): Inactive background color
    """

    col_acfg: str
    col_acbg: str
    col_inacfg: str
    col_inacbg: str


@dataclass
class SubGraphWindowButtonColor:
    """Sub-graph window button color theme.

    This class stores the color theme for a sub-graph window button.

    Attributes:
        col_acfg (str): Active foreground color
        col_acbg (str): Active background color
        col_inacfg (str): Inactive foreground color
        col_inacbg (str): Inactive background color
    """

    col_acfg: str
    col_acbg: str
    col_inacfg: str
    col_inacbg: str


@dataclass
class ImageColorChangeButtonColor:
    """Image color change button color theme.

    This class stores the color theme for an image color change button.

    Attributes:
        col_acfg (str): Active foreground color
        col_acbg (str): Active background color
        col_inacfg (str): Inactive foreground color
        col_inacbg (str): Inactive background color
    """

    col_acfg: str
    col_acbg: str
    col_inacfg: str
    col_inacbg: str
