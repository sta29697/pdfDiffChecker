from __future__ import annotations
from logging import getLogger
from PIL import Image


logger = getLogger(__name__)


class ImageFileExtensionConverter:
    def __init__(self, before_file_path: str, output_dir_path: str) -> None:
        self._before_file_path = before_file_path
        self._output_dir_path = output_dir_path

    # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
    ### jpg -> ___ ##########################################################
    """
    Pillow reads JPEG, JFIF, and Adobe JPEG files containing L, RGB, or CMYK data.
    It writes standard and progressive JFIF files.
    Using the draft() method, you can speed things up by converting RGB images to L,
    and resize images to 1/2, 1/4 or 1/8 of their original size while loading them.
    By default Pillow doesn’t allow loading of truncated JPEG files, set ImageFile.
    LOAD_TRUNCATED_IMAGES to override this.
    Opening
        The open() method may set the following info properties if available:
    """

    def jpg2png(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "png")

    def jpg2gif(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "gif")

    def jpg2tiff(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "tiff")

    def jpg2bmp(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "bmp")

    def jpg2pdf(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "pdf")

    ### png -> ___ ##########################################################
    """
    Pillow identifies, reads, and writes PNG files containing 1, L, LA, I, P, RGB or
    RGBA data. Interlaced files are supported as of v1.1.7.
    As of Pillow 6.0, EXIF data can be read from PNG images. However, unlike other
    image formats, EXIF data is not guaranteed to be present in info until load()
    has been called.
    By default Pillow doesn’t allow loading of truncated PNG files, set
    ImageFile.LOAD_TRUNCATED_IMAGES to override this.
    Opening
        The open() function sets the following info properties, when appropriate:
    """

    def png2jpg(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGBA":
                f = f.convert("RGB")
            f.save(self._output_dir_path, "jpg")

    ### gif -> ___ ##########################################################
    """
    Pillow reads GIF87a and GIF89a versions of the GIF file format. The library writes
    files in GIF87a by default, unless GIF89a features are used or GIF89a is already
    in use. Files are written with LZW encoding.
    GIF files are initially read as grayscale (L) or palette mode (P) images. Seeking
    to later frames in a P image will change the image to RGB (or RGBA if the first
    frame had transparency).
    P mode images are changed to RGB because each frame of a GIF may contain its own
    individual palette of up to 256 colors. When a new frame is placed onto a previous
    frame, those colors may combine to exceed the P mode limit of 256 colors. Instead,
    the image is converted to RGB handle this.
    Opening
        The open() method sets the following info properties:
    """

    def gif2png(self) -> None:
        with Image.open(self._before_file_path) as f:
            f.save(self._output_dir_path, "png")

    ### tiff -> ___ ##########################################################
    """
    Pillow reads and writes TIFF files. It can read both striped and tiled images,
    pixel and plane interleaved multi-band images. If you have libtiff and its headers
    installed, Pillow can read and write many kinds of compressed TIFF files. If not,
    Pillow will only read and write uncompressed files.
    Note
        Beginning in version 5.0.0, Pillow requires libtiff to read or write compressed
        files. Prior to that release, Pillow had buggy support for reading Packbits,
        LZW and JPEG compressed TIFFs without using libtiff.
    Opening
        The open() method sets the following info properties:
    compression
        Compression mode.
    """

    def tiff2png(self) -> None:
        with Image.open(self._before_file_path) as f:
            f.save(self._output_dir_path, "png")

    ### bmp -> ___ ##########################################################
    """
    Pillow reads and writes Windows and OS/2 BMP files containing 1, L, P, or RGB data.
    16-colour images are read as P images. Support for reading 8-bit run-length encoding
    was added in Pillow 9.1.0. Support for reading 4-bit run-length encoding was added
    in Pillow 9.3.0.
    Opening
        The open() method sets the following info properties:
    compression
        Set to 1 if the file is a 256-color run-length encoded image. Set to 2 if the file
        is a 16-color run-length encoded image.
    """

    def bmp2png(self) -> None:
        with Image.open(self._before_file_path) as f:
            if f.mode == "RGB":
                f = f.convert("RGBA")
            f.save(self._output_dir_path, "png")
