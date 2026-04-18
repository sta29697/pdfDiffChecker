"""Mixin for CreateComparisonFileApp: canvas drawing, image cache, and diff overlay.

Extracted to reduce the generated C file size for Nuitka compilation.
All methods access instance attributes through ``self`` (always a
``CreateComparisonFileApp`` at runtime) and must not be called before
``CreateComparisonFileApp.__init__`` completes.
"""
from __future__ import annotations

import math
import threading
from logging import getLogger
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from typing import Optional, List, Any

from PIL import Image, ImageTk
from PIL.Image import DecompressionBombError, Resampling, Transpose

from utils.preview_diff_emphasis import build_diff_highlight_overlay_rgba
from utils.transform_tuple import as_transform6
from controllers.pdf_export_handler import apply_color_processing_to_image
from configurations.message_manager import get_message_manager
from configurations import tool_settings
from controllers.color_theme_manager import ColorThemeManager

logger = getLogger(__name__)
message_manager = get_message_manager()

_MAIN_TAB_DEFAULT_DPI = 300
_DIFF_CACHE_MISSING = object()  # sentinel: key exists but value not yet computed


class WorkspaceRasterTooLarge(Exception):
    """Raised when a workspace page PNG hits Pillow's pixel ceiling or cannot be decoded."""

    pass


class _MainTabMixin:
    """Mixin providing canvas drawing, image cache, histogram, and diff overlay methods."""

    # ------------------------------------------------------------------
    # Canvas footer / shortcut guide
    # ------------------------------------------------------------------

    def schedule_canvas_footer_reposition(self) -> None:
        """Defer footer guide layout until after Tk geometry has settled.

        Call after window maximize/restore, tab switches, or other late layout updates.
        """
        if not hasattr(self, "canvas"):
            return

        def _run() -> None:
            self._reposition_canvas_footer_guide()

        try:
            self.after_idle(_run)
        except Exception:
            try:
                _run()
            except Exception:
                pass

    def _reposition_canvas_footer_guide(self) -> None:
        """Reposition the footer guide overlay so it stays fixed in the viewport.

        The footer guide should remain at the bottom of the visible canvas area,
        even when the preview image is panned (uses canvas coordinates).
        """
        if not hasattr(self, "canvas"):
            return
        guide_frame = getattr(self, "_shortcut_guide_frame", None)
        guide_label = getattr(self, "_shortcut_guide_label", None)
        if guide_frame is None or guide_label is None:
            return

        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            cw = int(self.canvas.winfo_width())
        except Exception:
            cw = 1
        canvas_width = max(cw, 1)
        # Hug the canvas inner border; tiny insets avoid clipping the sunken relief.
        left_inset = 2
        right_inset = 2
        guide_width = max(canvas_width - left_inset - right_inset, 120)
        guide_label.configure(wraplength=max(guide_width - 12, 80))
        en_line2 = getattr(self, "_shortcut_guide_en_line2", None)
        if en_line2 is not None and en_line2.winfo_manager():
            en_line2.configure(wraplength=max(guide_width - 12, 80))
            spacer = getattr(self, "_shortcut_guide_en_spacer", None)
            l1_left = getattr(self, "_shortcut_guide_en_l1_left", None)
            if spacer is not None and l1_left is not None:
                try:
                    font = tkfont.Font(font=en_line2.cget("font"))
                    w2 = int(font.measure(en_line2.cget("text")))
                    fw = int(font.measure("\u3000"))
                    if fw <= 0:
                        fw = max(10, int(font.measure("0")))
                    target = w2 + fw
                    left_w = int(font.measure(l1_left.cget("text")))
                    spacer.configure(width=max(target - left_w, 0))
                except Exception:
                    pass
        try:
            guide_frame.update_idletasks()
        except Exception:
            pass
        guide_height = max(guide_frame.winfo_reqheight(), 28)
        # Pin to the canvas widget's bottom edge (viewport), not scroll coordinates.
        guide_frame.place(
            x=left_inset,
            rely=1.0,
            y=-2,
            anchor="sw",
            width=guide_width,
            height=guide_height,
        )
        try:
            guide_frame.lift()
        except Exception:
            pass

    @staticmethod
    def _u150_footer_message_uses_split_format(raw: str) -> bool:
        """Return True when U150 uses EN split layout (line1 left|||right, then newline line2)."""
        return "|||" in raw and "\n" in raw

    def _ensure_shortcut_guide_en_split_widgets(self, bg: str, fg: str) -> None:
        """Create EN two-row footer widgets (line1 left + spacer + right, then line2)."""
        if self._shortcut_guide_en_row1 is not None:
            return
        parent = self._shortcut_guide_frame
        self._shortcut_guide_en_row1 = tk.Frame(parent, bg=bg, highlightthickness=0, bd=0)
        self._shortcut_guide_en_l1_left = tk.Label(
            self._shortcut_guide_en_row1,
            anchor="w",
            justify="left",
            padx=0,
            pady=0,
            font=("Helvetica", 9),
            bg=bg,
            fg=fg,
        )
        self._shortcut_guide_en_spacer = tk.Frame(
            self._shortcut_guide_en_row1,
            height=1,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self._shortcut_guide_en_l1_right = tk.Label(
            self._shortcut_guide_en_row1,
            anchor="w",
            justify="left",
            padx=0,
            pady=0,
            font=("Helvetica", 9),
            bg=bg,
            fg=fg,
        )
        self._shortcut_guide_en_l1_left.pack(side=tk.LEFT)
        self._shortcut_guide_en_spacer.pack(side=tk.LEFT, fill=tk.Y)
        self._shortcut_guide_en_spacer.pack_propagate(False)
        self._shortcut_guide_en_l1_right.pack(side=tk.LEFT)
        self._shortcut_guide_en_line2 = tk.Label(
            parent,
            anchor="w",
            justify="left",
            padx=5,
            pady=0,
            font=("Helvetica", 9),
            bg=bg,
            fg=fg,
        )

    def _hide_shortcut_guide_en_split_widgets(self) -> None:
        """Remove EN split footer widgets from the pack manager."""
        for w in (self._shortcut_guide_en_row1, self._shortcut_guide_en_line2):
            if w is not None:
                try:
                    w.pack_forget()
                except Exception:
                    pass

    def _draw_canvas_footer_guide(self) -> None:
        """Draw the shortcut guide text inside the bottom area of the canvas."""
        if not hasattr(self, "canvas"):
            return

        mouse_handler = getattr(self, "mouse_handler", None)
        if mouse_handler is not None and hasattr(mouse_handler, "set_shortcut_help_visibility"):
            try:
                mouse_handler.set_shortcut_help_visibility(False)
            except Exception:
                pass

        try:
            self.canvas.delete("canvas_footer_overlay_bg")
            self.canvas.delete("canvas_footer_overlay_text")
        except Exception:
            pass

        current_theme = ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        guide_fg = str(frame_theme.get("fg", "#000000"))
        overlay_bg = str(self.canvas.cget("bg"))

        if getattr(self, "_shortcut_guide_frame", None) is None:
            self._shortcut_guide_frame = tk.Frame(
                self.canvas,
                relief=tk.FLAT,
                borderwidth=0,
                highlightthickness=0,
            )
        if getattr(self, "_shortcut_guide_label", None) is None:
            self._shortcut_guide_label = tk.Label(
                self._shortcut_guide_frame,
                anchor="w",
                justify="left",
                padx=5,
                pady=2,
                font=("Helvetica", 9),
            )

        self._shortcut_guide_frame.configure(bg=overlay_bg)
        raw_u150 = message_manager.get_ui_message("U150")
        if self._u150_footer_message_uses_split_format(raw_u150):
            line1, line2 = raw_u150.split("\n", 1)
            left, right = line1.split("|||", 1)
            self._ensure_shortcut_guide_en_split_widgets(overlay_bg, guide_fg)
            try:
                self._shortcut_guide_label.pack_forget()
            except Exception:
                pass
            self._shortcut_guide_en_l1_left.configure(
                text=left.strip(), bg=overlay_bg, fg=guide_fg
            )
            self._shortcut_guide_en_l1_right.configure(
                text=right.strip(), bg=overlay_bg, fg=guide_fg
            )
            self._shortcut_guide_en_line2.configure(
                text=line2, bg=overlay_bg, fg=guide_fg
            )
            self._shortcut_guide_en_row1.configure(bg=overlay_bg)
            self._shortcut_guide_en_spacer.configure(bg=overlay_bg)
            self._shortcut_guide_en_row1.pack(fill=tk.X, anchor="w", padx=5, pady=(2, 0))
            self._shortcut_guide_en_line2.pack(fill=tk.X, anchor="w", pady=(0, 2))
        else:
            self._hide_shortcut_guide_en_split_widgets()
            self._shortcut_guide_label.configure(
                text=raw_u150,
                bg=overlay_bg,
                fg=guide_fg,
                pady=2,
            )
            self._shortcut_guide_label.pack(fill="both", expand=True)
        self._reposition_canvas_footer_guide()
        try:
            self._shortcut_guide_frame.lift()
        except Exception:
            pass

    def _draw_reference_grid(
        self,
        bbox: Optional[tuple[int, int, int, int]] = None,
        *,
        raise_above_images: bool,
    ) -> None:
        """Draw a light guide-line grid on the preview canvas.

        Args:
            bbox: Optional target rectangle in canvas coordinates.
            raise_above_images: Whether the grid should be raised above image items.
        """
        if not hasattr(self, "canvas"):
            return

        # Main processing: rebuild the lightweight guide-line layer from scratch.
        self.canvas.delete("reference_grid")
        if not bool(self._show_reference_grid_var.get()):
            return

        canvas_width = max(self.canvas.winfo_width(), 720)
        canvas_height = max(self.canvas.winfo_height(), 420)

        if bbox is None:
            bbox = (0, 0, canvas_width, canvas_height)

        x1, y1, x2, y2 = [int(value) for value in bbox]
        grid_color = self._get_reference_grid_color()
        spacing = 24
        try:
            visible_x1 = int(self.canvas.canvasx(0))
            visible_y1 = int(self.canvas.canvasy(0))
            visible_x2 = int(self.canvas.canvasx(canvas_width))
            visible_y2 = int(self.canvas.canvasy(canvas_height))
        except Exception:
            visible_x1 = 0
            visible_y1 = 0
            visible_x2 = canvas_width
            visible_y2 = canvas_height

        x1 = min(x1, visible_x1)
        y1 = min(y1, visible_y1)
        x2 = max(x2, visible_x2)
        y2 = max(y2, visible_y2)
        if x2 - x1 < 24 or y2 - y1 < 24:
            return
        start_x = math.floor(x1 / spacing) * spacing
        start_y = math.floor(y1 / spacing) * spacing

        # Main processing: render the guide as a light intersection-dot grid for a visually finer result.
        for x in range(start_x, x2 + spacing, spacing):
            for y in range(start_y, y2 + spacing, spacing):
                self.canvas.create_line(
                    x,
                    y,
                    x + 1,
                    y,
                    fill=grid_color,
                    width=1,
                    capstyle=tk.ROUND,
                    tags=("reference_grid",),
                )

        if raise_above_images:
            try:
                self.canvas.tag_raise("reference_grid")
            except Exception:
                pass
        try:
            self.canvas.tag_raise("canvas_footer_overlay_bg")
            self.canvas.tag_raise("canvas_footer_overlay_text")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Histogram / analysis / color processing
    # ------------------------------------------------------------------

    def _normalize_histogram_counts(self, histogram_data: List[Any]) -> List[int]:
        """Normalize saved histogram payloads into a single 256-bin graph.

        Args:
            histogram_data: Raw histogram payload list collected by the converter.

        Returns:
            List[int]: Aggregated histogram counts.
        """
        aggregated = [0] * 766
        for page_histogram in histogram_data:
            if not isinstance(page_histogram, list):
                continue
            if len(page_histogram) >= 766 and len(page_histogram) < 768:
                for idx in range(766):
                    aggregated[idx] += int(page_histogram[idx])
                continue
            if len(page_histogram) >= 768:
                for idx in range(256):
                    aggregated[idx] += int(page_histogram[idx])
                    aggregated[idx] += int(page_histogram[idx + 256])
                    aggregated[idx] += int(page_histogram[idx + 512])
            elif len(page_histogram) >= 256:
                for idx in range(256):
                    aggregated[idx] += int(page_histogram[idx])
        return aggregated

    def _prepare_analysis_histogram(self, name_flag: str) -> List[int]:
        """Render analysis data for one side and return aggregated histogram counts.

        Args:
            name_flag: Either ``base`` or ``comp``.

        Returns:
            List[int]: Aggregated 256-bin histogram counts.
        """
        path_value = self.base_path.get() if name_flag == "base" else self.comparison_path.get()
        if not self._path_points_to_file(path_value):
            raise ValueError("PDF path is not valid for histogram analysis.")

        converter, file_info = self._get_or_create_converter(path_value, name_flag)
        file_info.file_histogram_data = []
        converter.process_with_progress_window(self.frame_main3, dpi=self._get_dpi_from_entry())
        return self._normalize_histogram_counts(file_info.file_histogram_data or [])

    def _refresh_graph_threshold_lines(self) -> None:
        """Refresh threshold markers in open graph windows."""
        graph_threshold_pairs = [
            (getattr(self, "_base_file_analyze_btn", None), int(self._base_threshold_value_var.get())),
            (getattr(self, "_comparison_file_analyze_btn", None), int(self._comparison_threshold_value_var.get())),
        ]
        for graph_button, threshold_value in graph_threshold_pairs:
            if graph_button is None:
                continue
            try:
                graph_button.set_threshold_value(threshold_value)
                graph_button.update_graph()
            except Exception:
                pass

    def _on_threshold_apply_click(self) -> None:
        """Apply threshold changes and refresh the lower preview when available.

        This handler validates the threshold inputs, persists them to settings,
        refreshes graph guides, and redraws the currently loaded lower preview page.
        """
        from utils.input_normalization import parse_strict_int

        try:
            base_threshold_value = parse_strict_int(self._base_threshold_entry.get())
            comparison_threshold_value = parse_strict_int(self._comparison_threshold_entry.get())
            self._base_threshold_value_var.set(base_threshold_value)
            self._comparison_threshold_value_var.set(comparison_threshold_value)
        except ValueError:
            self._show_status_feedback("閾値は整数で入力してください。", False)
            return

        if base_threshold_value < 0 or base_threshold_value > 765:
            self._show_status_feedback("閾値は 0 から 765 の範囲で入力してください。", False)
            return

        if comparison_threshold_value < 0 or comparison_threshold_value > 765:
            self._show_status_feedback("閾値は 0 から 765 の範囲で入力してください。", False)
            return

        self.settings.update_setting("separat_color_threshold", base_threshold_value)
        self.settings.update_setting("base_separat_color_threshold", base_threshold_value)
        self.settings.update_setting("comparison_separat_color_threshold", comparison_threshold_value)
        self.settings.save_settings()
        self._refresh_graph_threshold_lines()
        if self._has_loaded_workspace_pages():
            self._display_page(self.current_page_index)
            self._show_status_feedback(
                f"閾値変更結果を下の表示へ反映しました。元: {base_threshold_value} ／ 比較: {comparison_threshold_value}",
                True,
            )
            return
        if self._path_points_to_file(self.base_path.get()) or self._path_points_to_file(self.comparison_path.get()):
            self._refresh_workspace_state()
            if self._has_loaded_workspace_pages():
                self._show_status_feedback(
                    f"閾値変更結果を下の表示へ反映しました。元: {base_threshold_value} ／ 比較: {comparison_threshold_value}",
                    True,
                )
                return
        self._show_status_feedback(
            f"閾値を保存しました。プレビュー読込後に反映されます。元: {base_threshold_value} ／ 比較: {comparison_threshold_value}",
            True,
        )

    def _get_selected_layer_color(self, name_flag: str) -> Optional[str]:
        """Return the currently selected color for the requested side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Selected hex color string.
        """
        if name_flag == "base":
            button = getattr(self, "_base_image_color_change_btn", None)
            cached_color = self._base_selected_color_hex
        else:
            button = getattr(self, "_comparison_image_color_change_btn", None)
            cached_color = self._comparison_selected_color_hex

        if cached_color:
            return cached_color
        if button is None or not hasattr(button, "get_selected_color_hex"):
            return None
        try:
            return button.get_selected_color_hex()
        except Exception:
            return None

    def _diff_emphasis_palette_rgba(self, name_flag: str, alpha: int = 110) -> tuple[int, int, int, int]:
        """Map the layer palette color to an RGBA tuple for diff-emphasis overlay.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.
            alpha: Overlay alpha (0--255).

        Returns:
            ``(R, G, B, A)`` for semi-transparent highlights.
        """
        default_hex = "#3e77d2" if name_flag == "base" else "#c03755"
        raw = self._get_selected_layer_color(name_flag) or default_hex
        h = str(raw).strip().lstrip("#")
        if len(h) >= 6:
            try:
                return (
                    int(h[0:2], 16),
                    int(h[2:4], 16),
                    int(h[4:6], 16),
                    max(0, min(255, int(alpha))),
                )
            except ValueError:
                pass
        # Fallback parse for short or invalid hex
        return (62, 119, 210, max(0, min(255, int(alpha)))) if name_flag == "base" else (
            192,
            55,
            85,
            max(0, min(255, int(alpha))),
        )

    def _get_threshold_for_side(self, name_flag: str) -> int:
        """Return the current threshold value for one side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Threshold value in the range ``0`` to ``765``.
        """
        raw_value = self._base_threshold_value_var.get() if name_flag == "base" else self._comparison_threshold_value_var.get()
        try:
            return max(0, min(765, int(raw_value)))
        except Exception:
            return 700

    def _apply_color_processing_for_side(self, page_image: Image.Image, name_flag: str) -> Image.Image:
        """Apply the active color processing mode to one side image.

        Args:
            page_image: Source page image.
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Processed RGBA image.
        """
        return apply_color_processing_to_image(
            page_image,
            self._selected_color_processing_mode,
            self._get_selected_layer_color(name_flag),
            self._get_threshold_for_side(name_flag),
        )

    # ------------------------------------------------------------------
    # Background preview rendering
    # ------------------------------------------------------------------

    def _get_preview_render_lock(self, name_flag: str) -> threading.Lock:
        """Return the render lock used for one side preview generation.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            threading.Lock: Side-specific render lock.
        """
        return self._base_preview_render_lock if name_flag == "base" else self._comp_preview_render_lock

    def _render_preview_page_range(self, pdf_path: str, name_flag: str, dpi_value: int, start_page: int, end_page: int) -> None:
        """Render one page range for preview use without touching Tk widgets.

        Args:
            pdf_path: Source PDF path.
            name_flag: Either ``"base"`` or ``"comp"``.
            dpi_value: DPI used for preview rendering.
            start_page: Inclusive first page.
            end_page: Inclusive last page.
        """
        render_lock = self._get_preview_render_lock(name_flag)
        with render_lock:
            converter, _file_info = self._get_or_create_converter(pdf_path, name_flag)
            # Main processing: render only the requested page range for fast preview availability.
            converter.convert_to_grayscale_pngs(
                dpi=int(dpi_value),
                start_page=int(start_page),
                end_page=int(end_page),
            )

    def _start_background_preview_render(self, tasks: List[tuple[str, str, int, int]], dpi_value: int, generation: int) -> None:
        """Render remaining preview pages in a background worker.

        Args:
            tasks: Tuples of ``(pdf_path, name_flag, start_page, end_page)``.
            dpi_value: DPI used for rendering.
            generation: Snapshot of the current preview generation.
        """
        if not tasks:
            self._background_preview_render_thread = None
            return

        def _worker() -> None:
            """Background worker for incremental preview rendering."""
            # Main processing: render one page at a time so stale jobs can stop quickly.
            for pdf_path, name_flag, start_page, end_page in tasks:
                for page_num in range(start_page, end_page + 1):
                    if generation != self._preview_render_generation:
                        return
                    try:
                        self._render_preview_page_range(pdf_path, name_flag, dpi_value, page_num, page_num)
                    except Exception as exc:
                        logger.warning(f"Background preview render failed ({name_flag} page {page_num}): {exc}")

        worker_thread = threading.Thread(target=_worker, name="MainTabPreviewRender", daemon=True)
        self._background_preview_render_thread = worker_thread
        worker_thread.start()

    def _page_has_rendered_preview(self, page_index: int) -> bool:
        """Return whether at least one side already has a rendered image for the page.

        Args:
            page_index: Zero-based page index.

        Returns:
            bool: ``True`` when the page PNG exists for either side.
        """
        base_path = self._get_display_page_path(self.base_page_paths, page_index)
        comp_path = self._get_display_page_path(self.comp_page_paths, page_index)
        return bool((base_path is not None and base_path.exists()) or (comp_path is not None and comp_path.exists()))

    def _ensure_preview_page_available(self, page_index: int) -> None:
        """Synchronously render the requested page when background work is not done yet.

        Args:
            page_index: Zero-based page index.
        """
        if page_index < 0 or self._page_has_rendered_preview(page_index):
            return

        target_page_number = page_index + 1
        resolved_dpi = self._get_dpi_from_entry()

        # Main processing: render only the requested page as an on-demand fallback.
        if self._path_points_to_file(self.base_path.get()) and page_index < len(self.base_page_paths):
            base_path = self.base_page_paths[page_index]
            if not base_path.exists():
                self._render_preview_page_range(self.base_path.get(), "base", resolved_dpi, target_page_number, target_page_number)
        if self._path_points_to_file(self.comparison_path.get()) and page_index < len(self.comp_page_paths):
            comp_path = self.comp_page_paths[page_index]
            if not comp_path.exists():
                self._render_preview_page_range(self.comparison_path.get(), "comp", resolved_dpi, target_page_number, target_page_number)

    # ------------------------------------------------------------------
    # Image transform / cache / processing
    # ------------------------------------------------------------------

    def _apply_transform_to_image(
        self,
        pil_image: Image.Image,
        transform: tuple[float, ...],
        *,
        fast_resize: bool = False,
    ) -> Image.Image:
        """Apply mirror, rotation, and scale to a rendered page image.

        Args:
            pil_image: Source page image.
            transform: Transform tuple ``(rotation, tx, ty, scale[, flip_h, flip_v])``.
            fast_resize: Use bilinear instead of Lanczos for the scale step (LOD passes).

        Returns:
            Transformed PIL image.
        """
        rotation, _translate_x, _translate_y, scale, flip_h, flip_v = as_transform6(transform)
        dpi_normalization = float(_MAIN_TAB_DEFAULT_DPI) / float(max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI)))
        effective_scale = max(0.01, float(scale) * dpi_normalization)
        transformed_image = pil_image
        if flip_v:
            transformed_image = transformed_image.transpose(Transpose.FLIP_TOP_BOTTOM)
        if flip_h:
            transformed_image = transformed_image.transpose(Transpose.FLIP_LEFT_RIGHT)
        if rotation != 0:
            transformed_image = transformed_image.rotate(rotation, resample=Resampling.BICUBIC, expand=True)
        if abs(effective_scale - 1.0) > 1e-6:
            new_width = int(transformed_image.width * effective_scale)
            new_height = int(transformed_image.height * effective_scale)
            if new_width > 0 and new_height > 0:
                rs = Resampling.BILINEAR if fast_resize else Resampling.LANCZOS
                transformed_image = transformed_image.resize((new_width, new_height), rs)
        return transformed_image

    def _get_display_page_path(self, page_paths: List[Path], page_index: int) -> Optional[Path]:
        """Return the page PNG path for the requested index when available.

        Args:
            page_paths: Converted page list.
            page_index: Zero-based page index.

        Returns:
            Matching page path or ``None``.
        """
        if 0 <= page_index < len(page_paths):
            return page_paths[page_index]
        return None

    def _resolve_dpi_revert_target(self) -> int:
        """Return the DPI to restore after a workspace raster exceeds the pixel ceiling.

        Returns:
            Positive DPI present in settings or the main-tab default.
        """
        dpi_value = int(self._last_preview_ok_dpi)
        if dpi_value <= 0:
            return _MAIN_TAB_DEFAULT_DPI
        if dpi_value not in self._get_configured_dpi_choices():
            return _MAIN_TAB_DEFAULT_DPI
        return dpi_value

    def _notify_workspace_raster_pixel_limit(self, exc: Exception, page_path: Path) -> None:
        """Revert DPI, clear preview caches, and inform the user once per blocked episode.

        Args:
            exc: Underlying Pillow or IO error.
            page_path: Workspace PNG that triggered the failure.
        """
        target_dpi = self._resolve_dpi_revert_target()
        logger.debug("Workspace raster pixel limit triggered for: %s", page_path)
        self._preview_source_image_cache.clear()
        self._preview_processed_image_cache.clear()
        self._persist_selected_dpi(target_dpi, "manual")
        self._sync_dpi_combo_choices(preserve_current=False)
        self.settings.save_settings()
        self._workspace_preview_blocked = True

        if not self._workspace_raster_limit_dialog_shown:
            self._workspace_raster_limit_dialog_shown = True
            title = message_manager.get_ui_message("U179")
            body = message_manager.get_ui_message(
                "U180",
                f"{tool_settings.PIL_MAX_IMAGE_PIXELS:,}",
                str(target_dpi),
                str(exc),
            )
            try:
                messagebox.showerror(title, body, parent=self.winfo_toplevel())
            except Exception:
                pass
            logger.warning(
                message_manager.get_log_message("L347", str(target_dpi), str(exc))
            )

        self._show_status_feedback(message_manager.get_ui_message("U181"), False)

    def _render_workspace_raster_blocked_canvas(self) -> None:
        """Draw a short explanation when previews are suspended for oversized rasters."""
        if not hasattr(self, "canvas"):
            return
        for _tag in ("workspace", "reference_grid", "pdf_image", "base_image", "comp_image", "diff_emphasis"):
            try:
                self.canvas.delete(_tag)
            except Exception:
                pass
        self._base_canvas_image_id = None
        self._comp_canvas_image_id = None
        self._diff_emphasis_canvas_image_id = None
        self._preview_canvas_snap = None
        canvas_width = max(self.canvas.winfo_width(), 720)
        canvas_height = max(self.canvas.winfo_height(), 420)
        active_theme = ColorThemeManager.get_instance().get_current_theme()
        frame_theme = active_theme.get("Frame", {})
        canvas_bg = self._PREVIEW_CANVAS_BACKGROUND
        text_fg = frame_theme.get("fg", "#000000")
        accent_fg = active_theme.get("process_button", {}).get("fg", text_fg)
        border_fg = active_theme.get("canvas", {}).get("highlightbackground", "#6c6c6c")
        self.canvas.configure(bg=canvas_bg)
        self.canvas.create_rectangle(
            16,
            16,
            canvas_width - 16,
            canvas_height - 16,
            outline=border_fg,
            width=2,
            tags=("workspace",),
        )
        self.canvas.create_text(
            32,
            36,
            anchor="nw",
            text=message_manager.get_ui_message("U179"),
            fill=accent_fg,
            font=("", 12, "bold"),
            tags=("workspace",),
        )
        self.canvas.create_text(
            32,
            74,
            anchor="nw",
            text=message_manager.get_ui_message("U181"),
            fill=text_fg,
            width=max(canvas_width - 72, 320),
            font=("", 10),
            tags=("workspace",),
        )
        self._draw_canvas_footer_guide()
        try:
            self.canvas.tag_raise("overlay_shortcut_help")
        except Exception:
            pass

    @staticmethod
    def _get_preview_image_signature(page_path: Path) -> tuple[str, int, int]:
        """Return a stable signature for one rendered preview PNG.

        Args:
            page_path: Target PNG path.

        Returns:
            Tuple containing path string, modification time, and file size.
        """
        stat_result = page_path.stat()
        return (str(page_path), int(stat_result.st_mtime_ns), int(stat_result.st_size))

    def _get_cached_source_preview_image(self, page_path: Path) -> Image.Image:
        """Load one workspace PNG once and reuse it across redraws.

        Args:
            page_path: Target PNG path.

        Returns:
            Cached RGBA image copy.

        Raises:
            WorkspaceRasterTooLarge: When Pillow refuses the raster (pixel ceiling).
        """
        path_str, modified_time_ns, file_size = self._get_preview_image_signature(page_path)
        cache_key = (path_str, modified_time_ns, file_size, 0)

        # Main processing: reuse the immutable source image for repeated redraws (LRU).
        cached_image = self._preview_source_image_cache.get(cache_key)
        if cached_image is None:
            try:
                with Image.open(page_path) as loaded_image:
                    cached_image = loaded_image.convert("RGBA")
            except DecompressionBombError as exc:
                self._notify_workspace_raster_pixel_limit(exc, page_path)
                raise WorkspaceRasterTooLarge(str(page_path)) from exc
            max_size = int(getattr(self, "_PREVIEW_SOURCE_CACHE_MAX", 8))
            while len(self._preview_source_image_cache) >= max_size:
                self._preview_source_image_cache.popitem(last=False)
            self._preview_source_image_cache[cache_key] = cached_image
        else:
            self._preview_source_image_cache.move_to_end(cache_key)
        return cached_image.copy()

    def _get_cached_processed_preview_image(self, page_path: Path, name_flag: str) -> Image.Image:
        """Return a cached color-processed page image for preview redraws.

        Args:
            page_path: Target PNG path.
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Cached processed image copy.
        """
        path_str, modified_time_ns, file_size = self._get_preview_image_signature(page_path)
        selected_color = str(self._get_selected_layer_color(name_flag) or "")
        threshold_value = int(self._get_threshold_for_side(name_flag))
        cache_key = (
            name_flag,
            path_str,
            modified_time_ns,
            file_size,
            self._selected_color_processing_mode,
            selected_color,
            threshold_value,
        )

        # Main processing: cache the expensive color processing result separately (LRU).
        cached_image = self._preview_processed_image_cache.get(cache_key)
        if cached_image is None:
            source_image = self._get_cached_source_preview_image(page_path)
            cached_image = self._apply_color_processing_for_side(source_image, name_flag)
            max_size = int(getattr(self, "_PREVIEW_PROCESSED_CACHE_MAX", 8))
            while len(self._preview_processed_image_cache) >= max_size:
                self._preview_processed_image_cache.popitem(last=False)
            self._preview_processed_image_cache[cache_key] = cached_image
        else:
            self._preview_processed_image_cache.move_to_end(cache_key)
        return cached_image.copy()

    def _get_source_page_pixel_size(self, page_path: Path) -> tuple[int, int]:
        """Return width and height of the workspace PNG without copying pixel buffers.

        Args:
            page_path: Rendered page path.

        Returns:
            ``(width, height)`` in pixels.

        Raises:
            WorkspaceRasterTooLarge: When Pillow refuses the raster (pixel ceiling).
        """
        path_str, modified_time_ns, file_size = self._get_preview_image_signature(page_path)
        cache_key = (path_str, modified_time_ns, file_size, 0)
        cached_image = self._preview_source_image_cache.get(cache_key)
        if cached_image is not None:
            return cached_image.size
        try:
            with Image.open(page_path) as loaded_image:
                return loaded_image.size
        except DecompressionBombError as exc:
            self._notify_workspace_raster_pixel_limit(exc, page_path)
            raise WorkspaceRasterTooLarge(str(page_path)) from exc

    def _processed_preview_image_for_display(
        self,
        page_path: Path,
        name_flag: str,
        preview_max_source_side: Optional[int],
    ) -> Image.Image:
        """Return a color-processed page raster, optionally capped for LOD preview.

        Args:
            page_path: Workspace PNG path.
            name_flag: ``"base"`` or ``"comp"``.
            preview_max_source_side: If set and the source is larger, downsample before
                color processing (not cached with full-res keys).

        Returns:
            Processed RGBA image (copy).
        """
        if preview_max_source_side is None:
            return self._get_cached_processed_preview_image(page_path, name_flag)
        source = self._get_cached_source_preview_image(page_path)
        if max(source.size) > int(preview_max_source_side):
            lod = source.copy()
            cap = int(preview_max_source_side)
            lod.thumbnail((cap, cap), Resampling.BILINEAR)
            source = lod
        return self._apply_color_processing_for_side(source, name_flag)

    def _diff_emphasis_source_rgba_pair_for_page(
        self,
        page_index: int,
        base_path: Optional[Path],
        comp_path: Optional[Path],
    ) -> tuple[Optional[Image.Image], Optional[Image.Image]]:
        """Return base/comp RGBA rasters from workspace PNGs before color processing.

        Transforms match the live preview so diff logic can use raw raster values
        (needed for **指定色濃淡** and **二色化** ink comparison without preview LOD).

        Args:
            page_index: Index into ``base_transform_data`` / ``comp_transform_data``.
            base_path: Resolved workspace page path for the base side, if any.
            comp_path: Resolved workspace page path for the comparison side, if any.

        Returns:
            ``(base_rgba, comp_rgba)`` or ``(None, None)`` if either side is missing.
        """
        base_rgba: Optional[Image.Image] = None
        comp_rgba: Optional[Image.Image] = None
        if base_path is not None and base_path.exists():
            src = self._get_cached_source_preview_image(base_path).convert("RGBA")
            if page_index < len(self.base_transform_data):
                base_t = self._transform_tuple_for_preview_render(
                    page_index, self.base_transform_data[page_index], is_base_layer=True
                )
                base_rgba = self._apply_transform_to_image(src, base_t, fast_resize=False)
        if comp_path is not None and comp_path.exists():
            src = self._get_cached_source_preview_image(comp_path).convert("RGBA")
            if page_index < len(self.comp_transform_data):
                comp_t = self._transform_tuple_for_preview_render(
                    page_index, self.comp_transform_data[page_index], is_base_layer=False
                )
                comp_rgba = self._apply_transform_to_image(src, comp_t, fast_resize=False)
        if base_rgba is None or comp_rgba is None:
            return None, None
        return base_rgba, comp_rgba

    # ------------------------------------------------------------------
    # Diff overlay computation and display
    # ------------------------------------------------------------------

    def _compute_diff_emphasis_overlay_fullres(
        self,
        page_index: int,
        base_path: Path,
        comp_path: Path,
    ) -> Optional[tuple[Image.Image, int, int, tuple[int, int]]]:
        """Build diff-emphasis overlay from full-resolution rasters (no LOD cap).

        **二色化** uses source PNGs plus ink XOR only (no same-cell RGBA supplement) and
        slightly stronger dilation/alpha per M8 binarization tuning. **指定色濃淡** uses
        source PNGs when available with ink XOR and same-cell supplement (branch-era
        behavior).

        Args:
            page_index: Page index aligned with ``*_transform_data``.
            base_path: Existing workspace page path for the base side.
            comp_path: Existing workspace page path for the comparison side.

        Returns:
            ``(overlay_rgba, ox, oy, ref_wh)`` where ``ref_wh`` is the transformed
            processed-base ``(width, height)`` for scaling the overlay to LOD, or
            ``None`` if inputs are unusable.
        """
        if page_index >= len(self.base_transform_data) or page_index >= len(
            self.comp_transform_data
        ):
            return None
        base_t = self._transform_tuple_for_preview_render(
            page_index, self.base_transform_data[page_index], is_base_layer=True
        )
        comp_t = self._transform_tuple_for_preview_render(
            page_index, self.comp_transform_data[page_index], is_base_layer=False
        )
        base_proc = self._processed_preview_image_for_display(base_path, "base", None)
        base_full = self._apply_transform_to_image(base_proc, base_t, fast_resize=False)
        ref_wh = base_full.size

        comp_proc = self._processed_preview_image_for_display(comp_path, "comp", None)
        comp_full = self._apply_transform_to_image(comp_proc, comp_t, fast_resize=False)

        bi = base_full.convert("RGBA")
        ci = comp_full.convert("RGBA")

        _, btx, bty, _, _, _ = as_transform6(self.base_transform_data[page_index])
        _, ctx, cty, _, _, _ = as_transform6(self.comp_transform_data[page_index])

        sbi, sci = self._diff_emphasis_source_rgba_pair_for_page(
            page_index, base_path, comp_path
        )

        if self._selected_color_processing_mode == "二色化":
            if sbi is not None and sci is not None:
                bi, ci = sbi, sci
            ov, (ox, oy) = build_diff_highlight_overlay_rgba(
                bi,
                (int(btx), int(bty)),
                ci,
                (int(ctx), int(cty)),
                base_highlight_rgba=self._diff_emphasis_palette_rgba("base", alpha=130),
                comp_highlight_rgba=self._diff_emphasis_palette_rgba("comp", alpha=130),
                luma_threshold=248,
                alpha_threshold=18,
                ink_match_dilate_size=3,
                edge_suppress_px=2,
                open_size=3,
                dilate_size=5,
                ink_speckle_open_size=0,
                same_cell_pixel_diff=False,
                same_cell_sq_diff_threshold=200,
                same_cell_luma_delta_min=0,
                same_cell_supplement_open=0,
                same_cell_supplement_dilate=5,
            )
            return ov, ox, oy, ref_wh

        if sbi is not None and sci is not None:
            bi, ci = sbi, sci

        ov, (ox, oy) = build_diff_highlight_overlay_rgba(
            bi,
            (int(btx), int(bty)),
            ci,
            (int(ctx), int(cty)),
            base_highlight_rgba=self._diff_emphasis_palette_rgba("base"),
            comp_highlight_rgba=self._diff_emphasis_palette_rgba("comp"),
            luma_threshold=248,
            alpha_threshold=18,
            ink_match_dilate_size=3,
            edge_suppress_px=4,
            open_size=0,
            dilate_size=5,
            ink_speckle_open_size=0,
            same_cell_pixel_diff=True,
            same_cell_sq_diff_threshold=52,
            same_cell_luma_delta_min=5,
            same_cell_supplement_open=0,
            same_cell_supplement_dilate=5,
        )
        return ov, ox, oy, ref_wh

    # ------------------------------------------------------------------
    # Background diff overlay cache (decouples diff compute from scroll)
    # ------------------------------------------------------------------

    def _diff_overlay_cache_key(
        self, page_index: int, base_path: Path, comp_path: Path
    ) -> Optional[tuple]:
        """Return a cache key that captures everything affecting the diff pixel content.

        Includes scale and relative X/Y offsets so the cache is invalidated
        when either layer is moved or resized independently.
        """
        if page_index >= len(self.base_transform_data) or page_index >= len(
            self.comp_transform_data
        ):
            return None
        b_r, b_tx, b_ty, b_s, b_fh, b_fv = as_transform6(self.base_transform_data[page_index])
        c_r, c_tx, c_ty, c_s, c_fh, c_fv = as_transform6(self.comp_transform_data[page_index])
        base_c = self._diff_emphasis_palette_rgba("base", alpha=130)
        comp_c = self._diff_emphasis_palette_rgba("comp", alpha=130)
        return (
            page_index,
            str(base_path),
            str(comp_path),
            self._selected_color_processing_mode,
            base_c,
            comp_c,
            round(float(b_r), 2),
            int(b_fh),
            int(b_fv),
            round(float(b_s), 4),
            round(float(b_tx), 1),
            round(float(b_ty), 1),
            round(float(c_r), 2),
            int(c_fh),
            int(c_fv),
            round(float(c_s), 4),
            round(float(c_tx), 1),
            round(float(c_ty), 1),
        )

    def _compute_diff_overlay_at_origin(
        self, page_index: int, base_path: Path, comp_path: Path
    ) -> Optional[Image.Image]:
        """Compute diff overlay in base-image pixel space, applying scale and X/Y offset.

        The base image is placed at (0, 0) in "base pixel space".  The comp image
        is scaled by ``c_s / b_s`` and offset by ``((c_tx - b_tx)/b_s, (c_ty - b_ty)/b_s)``
        so that both are aligned as they appear on the canvas.

        The result is an RGBA image whose top-left corner in canvas coordinates is
        ``(b_tx + min(0, rel_x) * b_s * dpi_norm, b_ty + min(0, rel_y) * b_s * dpi_norm)``.
        The caller must use :meth:`_diff_overlay_canvas_origin` to find that position.

        Returns:
            RGBA :class:`PIL.Image.Image` overlay, or ``None`` on failure.
        """
        if page_index >= len(self.base_transform_data) or page_index >= len(
            self.comp_transform_data
        ):
            return None
        try:
            sbi_raw = self._get_cached_source_preview_image(base_path).convert("RGBA")
            sci_raw = self._get_cached_source_preview_image(comp_path).convert("RGBA")
        except Exception:
            return None

        r_base, b_tx, b_ty, b_s, fh_base, fv_base = as_transform6(self.base_transform_data[page_index])
        r_comp, c_tx, c_ty, c_s, fh_comp, fv_comp = as_transform6(self.comp_transform_data[page_index])

        def _apply_rot_flip(img: Image.Image, r: float, fh: int, fv: int) -> Image.Image:
            if fv:
                img = img.transpose(Transpose.FLIP_TOP_BOTTOM)
            if fh:
                img = img.transpose(Transpose.FLIP_LEFT_RIGHT)
            if abs(r) > 1e-6:
                img = img.rotate(float(r), resample=Resampling.BICUBIC, expand=True)
            return img

        sbi = _apply_rot_flip(sbi_raw, r_base, int(fh_base), int(fv_base))
        sci = _apply_rot_flip(sci_raw, r_comp, int(fh_comp), int(fv_comp))

        # Scale comp image to match base's scale (relative scale adjustment)
        rel_scale = float(c_s) / max(float(b_s), 1e-6)
        if abs(rel_scale - 1.0) > 0.001:
            new_cw = max(1, round(sci.width * rel_scale))
            new_ch = max(1, round(sci.height * rel_scale))
            sci = sci.resize((new_cw, new_ch), Resampling.LANCZOS)

        # Relative offset of comp image in base pixel space
        comp_rel_x = int(round((float(c_tx) - float(b_tx)) / max(float(b_s), 1e-6)))
        comp_rel_y = int(round((float(c_ty) - float(b_ty)) / max(float(b_s), 1e-6)))

        is_bin = self._selected_color_processing_mode == "二色化"
        base_c = self._diff_emphasis_palette_rgba("base", alpha=130)
        comp_c = self._diff_emphasis_palette_rgba("comp", alpha=130)

        # Scale morphology params by DPI so highlights stay visible after downscale to display.
        # At 300 DPI (baseline), factor=1. At 600 DPI, factor=2, etc.
        dpi_factor = max(1, round(
            int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI) / _MAIN_TAB_DEFAULT_DPI
        ))

        def _odd(n: int) -> int:
            """Round up to the nearest odd integer >= 3 (PIL MaxFilter requires odd size)."""
            n = max(3, int(n))
            return n if n % 2 == 1 else n + 1

        comp_pos = (comp_rel_x, comp_rel_y)
        try:
            if is_bin:
                ov, _ = build_diff_highlight_overlay_rgba(
                    sbi, (0, 0), sci, comp_pos,
                    base_highlight_rgba=base_c,
                    comp_highlight_rgba=comp_c,
                    luma_threshold=248, alpha_threshold=18,
                    ink_match_dilate_size=_odd(3 * dpi_factor),
                    edge_suppress_px=2 * dpi_factor,
                    open_size=_odd(3 * dpi_factor),
                    dilate_size=_odd(60 * dpi_factor),
                    ink_speckle_open_size=0,
                    same_cell_pixel_diff=False, same_cell_sq_diff_threshold=200,
                    same_cell_luma_delta_min=0,
                    same_cell_supplement_open=0,
                    same_cell_supplement_dilate=_odd(20 * dpi_factor),
                )
            else:
                ov, _ = build_diff_highlight_overlay_rgba(
                    sbi, (0, 0), sci, comp_pos,
                    base_highlight_rgba=base_c,
                    comp_highlight_rgba=comp_c,
                    luma_threshold=248, alpha_threshold=18,
                    ink_match_dilate_size=_odd(3 * dpi_factor),
                    edge_suppress_px=4 * dpi_factor,
                    open_size=_odd(3 * dpi_factor),
                    dilate_size=_odd(30 * dpi_factor),
                    ink_speckle_open_size=0,
                    same_cell_pixel_diff=True, same_cell_sq_diff_threshold=800,
                    same_cell_luma_delta_min=30,
                    same_cell_supplement_open=0,
                    same_cell_supplement_dilate=_odd(10 * dpi_factor),
                )
        except Exception:
            return None
        return ov

    def _schedule_diff_overlay_bg_compute(
        self, page_index: int, base_path: Path, comp_path: Path, key: tuple
    ) -> None:
        """Launch a daemon thread to compute the diff overlay for *key* if not already running."""
        with self._diff_overlay_cache_lock:
            if key in self._diff_src_overlay_cache:
                return
            if self._diff_overlay_bg_key == key:
                return
            self._diff_overlay_bg_key = key

        def _worker() -> None:
            ov = self._compute_diff_overlay_at_origin(page_index, base_path, comp_path)
            with self._diff_overlay_cache_lock:
                self._diff_src_overlay_cache[key] = ov
                if self._diff_overlay_bg_key == key:
                    self._diff_overlay_bg_key = None
            try:
                self.after(0, lambda: self._on_diff_overlay_ready(page_index))
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True, name="diff_overlay_bg")
        t.start()

    def _on_diff_overlay_ready(self, page_index: int) -> None:
        """Called on the main thread after background diff overlay computation finishes."""
        try:
            self.canvas.delete("diff_computing")
        except Exception:
            pass
        if self.current_page_index == page_index and self._has_loaded_workspace_pages():
            base_path = self._get_display_page_path(self.base_page_paths, page_index)
            comp_path = self._get_display_page_path(self.comp_page_paths, page_index)
            if base_path is not None and comp_path is not None:
                self._display_diff_overlay_from_cache(
                    page_index, base_path, comp_path, fast_resize=False
                )

    def _diff_overlay_canvas_origin(self, page_index: int) -> tuple[int, int]:
        """Return the canvas (x, y) where the diff overlay top-left should be placed.

        The overlay is in base-image pixel space; its top-left is at
        ``min(0, comp_rel_x)`` in that space.  Multiplying by the effective
        display scale gives the canvas offset to add to the base image position.

        Args:
            page_index: Current page index.

        Returns:
            ``(ox, oy)`` canvas coordinates (integers).
        """
        if page_index >= len(self.base_transform_data) or page_index >= len(
            self.comp_transform_data
        ):
            return (0, 0)
        _br, b_tx, b_ty, b_s, _bfh, _bfv = as_transform6(self.base_transform_data[page_index])
        _cr, c_tx, c_ty, c_s, _cfh, _cfv = as_transform6(self.comp_transform_data[page_index])
        dpi_norm = float(_MAIN_TAB_DEFAULT_DPI) / float(
            max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI))
        )
        effective_scale = max(0.01, float(b_s) * dpi_norm)
        b_s_safe = max(float(b_s), 1e-6)
        comp_rel_x = (float(c_tx) - float(b_tx)) / b_s_safe
        comp_rel_y = (float(c_ty) - float(b_ty)) / b_s_safe
        ox = int(float(b_tx) + min(0.0, comp_rel_x) * effective_scale)
        oy = int(float(b_ty) + min(0.0, comp_rel_y) * effective_scale)
        return (ox, oy)

    def _display_diff_overlay_from_cache(
        self,
        page_index: int,
        base_path: Path,
        comp_path: Path,
        *,
        fast_resize: bool,
    ) -> None:
        """Look up the diff overlay cache and draw it onto the canvas, or schedule bg compute."""
        if not bool(self._diff_emphasis_var.get()):
            return
        key = self._diff_overlay_cache_key(page_index, base_path, comp_path)
        if key is None:
            return

        with self._diff_overlay_cache_lock:
            cached = self._diff_src_overlay_cache.get(key, _DIFF_CACHE_MISSING)

        # Always clean up any stale computing indicator before deciding what to show
        try:
            self.canvas.delete("diff_computing")
        except Exception:
            pass

        if cached is _DIFF_CACHE_MISSING:
            self._schedule_diff_overlay_bg_compute(page_index, base_path, comp_path, key)
            try:
                cw = max(self.canvas.winfo_width(), 200)
                ch = max(self.canvas.winfo_height(), 120)
                self.canvas.create_text(
                    cw // 2, ch // 2,
                    text="差分計算中…",
                    fill="#FF8800",
                    font=("", 11, "bold"),
                    tags=("diff_computing",),
                )
            except Exception:
                pass
            return

        if cached is None:
            return  # Computation failed — skip silently

        # Determine canvas placement: overlay is in base-image pixel space
        ox, oy = self._diff_overlay_canvas_origin(page_index)

        r, _, _, s, _, _ = as_transform6(self.base_transform_data[page_index])
        dpi_norm = float(_MAIN_TAB_DEFAULT_DPI) / float(
            max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI))
        )
        effective_scale = max(0.01, float(s) * dpi_norm)

        ov_src_w, ov_src_h = cached.size
        tgt_w = max(1, int(ov_src_w * effective_scale))
        tgt_h = max(1, int(ov_src_h * effective_scale))

        rs = Resampling.BILINEAR if fast_resize else Resampling.LANCZOS
        try:
            display_ov = cached.resize((tgt_w, tgt_h), rs)
        except Exception:
            return

        try:
            self._diff_emphasis_photo_image = ImageTk.PhotoImage(display_ov)
            self._diff_emphasis_canvas_image_id = self.canvas.create_image(
                ox, oy,
                anchor="nw",
                image=self._diff_emphasis_photo_image,
                tags=("diff_emphasis", "pdf_image"),
            )
        except Exception as exc:
            logger.debug("Diff overlay display failed: %s", exc)

    # ------------------------------------------------------------------
    # Export diff overlay (full-resolution, no preview scale)
    # ------------------------------------------------------------------

    def _compute_diff_overlay_for_export_page(
        self,
        page_index: int,
        base_path: Path,
        comp_path: Path,
        export_base_transform: tuple,
        export_comp_transform: tuple,
    ) -> Optional[tuple[Image.Image, int, int]]:
        """Compute diff-emphasis overlay in full export resolution.

        The overlay is built in source-pixel space (scale=1.0).  Rotation is
        applied to match the export composite; flip flags are ignored here to
        match the existing ``PDFExportHandler`` behaviour (4-tuple transforms
        lose flip info).

        Args:
            page_index: Page index (used for palette colors only).
            base_path: Workspace PNG for the base side.
            comp_path: Workspace PNG for the comparison side.
            export_base_transform: Export transform for base (rotation, tx, ty, 1.0).
            export_comp_transform: Export transform for comp (rotation, tx, ty, 1.0).

        Returns:
            ``(overlay_rgba, rel_ox, rel_oy)`` where ``rel_ox/rel_oy`` are the
            top-left offsets of the overlay in base-pixel space
            (``min(0, comp_rel_x)``, ``min(0, comp_rel_y)``), or ``None`` on
            failure.
        """
        try:
            sbi = Image.open(base_path).convert("RGBA")
            sci = Image.open(comp_path).convert("RGBA")
        except Exception as exc:
            logger.error("Export overlay: failed to open source images: %s", exc)
            return None

        r_base, b_tx, b_ty, _b_s, _, _ = as_transform6(export_base_transform)
        r_comp, c_tx, c_ty, _c_s, _, _ = as_transform6(export_comp_transform)

        if abs(r_base) > 1e-6:
            sbi = sbi.rotate(float(r_base), resample=Resampling.BICUBIC, expand=True)
        if abs(r_comp) > 1e-6:
            sci = sci.rotate(float(r_comp), resample=Resampling.BICUBIC, expand=True)

        comp_rel_x = int(round(float(c_tx) - float(b_tx)))
        comp_rel_y = int(round(float(c_ty) - float(b_ty)))

        is_bin = self._selected_color_processing_mode == "二色化"
        base_c = self._diff_emphasis_palette_rgba("base", alpha=130)
        comp_c = self._diff_emphasis_palette_rgba("comp", alpha=130)

        dpi_factor = max(1, round(
            int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI) / _MAIN_TAB_DEFAULT_DPI
        ))

        def _odd(n: int) -> int:
            n = max(3, int(n))
            return n if n % 2 == 1 else n + 1

        logger.debug(
            "Export overlay page=%d mode=%s base=%s comp=%s comp_rel=(%d,%d) dpi_factor=%d",
            page_index, self._selected_color_processing_mode,
            base_path.name, comp_path.name, comp_rel_x, comp_rel_y, dpi_factor,
        )
        try:
            if is_bin:
                ov, _ = build_diff_highlight_overlay_rgba(
                    sbi, (0, 0), sci, (comp_rel_x, comp_rel_y),
                    base_highlight_rgba=base_c, comp_highlight_rgba=comp_c,
                    luma_threshold=248, alpha_threshold=18,
                    ink_match_dilate_size=_odd(3 * dpi_factor),
                    edge_suppress_px=2 * dpi_factor,
                    open_size=_odd(3 * dpi_factor),
                    dilate_size=_odd(60 * dpi_factor),
                    ink_speckle_open_size=0,
                    same_cell_pixel_diff=False, same_cell_sq_diff_threshold=200,
                    same_cell_luma_delta_min=0,
                    same_cell_supplement_open=0,
                    same_cell_supplement_dilate=_odd(20 * dpi_factor),
                )
            else:
                ov, _ = build_diff_highlight_overlay_rgba(
                    sbi, (0, 0), sci, (comp_rel_x, comp_rel_y),
                    base_highlight_rgba=base_c, comp_highlight_rgba=comp_c,
                    luma_threshold=248, alpha_threshold=18,
                    ink_match_dilate_size=_odd(3 * dpi_factor),
                    edge_suppress_px=4 * dpi_factor,
                    open_size=_odd(3 * dpi_factor),
                    dilate_size=_odd(30 * dpi_factor),
                    ink_speckle_open_size=0,
                    same_cell_pixel_diff=True, same_cell_sq_diff_threshold=800,
                    same_cell_luma_delta_min=30,
                    same_cell_supplement_open=0,
                    same_cell_supplement_dilate=_odd(10 * dpi_factor),
                )
        except Exception as exc:
            logger.error("Export overlay: build_diff_highlight_overlay_rgba failed: %s", exc)
            return None

        import numpy as _np
        non_zero = int((_np.array(ov)[:, :, 3] > 0).sum())
        logger.info("Export overlay page=%d: non-zero pixels=%d size=%s", page_index, non_zero, ov.size)
        rel_ox = min(0, comp_rel_x)
        rel_oy = min(0, comp_rel_y)
        return (ov, rel_ox, rel_oy)
