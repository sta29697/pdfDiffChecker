# M2 Plan — File Extension & Size Conversion Tab (U006)

## Goal
- Activate the "File Extension and Size" tab (U006) which is currently commented out in `main.py`.
- Redesign `views/image_ope_tab.py` (class `ImageOperationApp`) to provide:
  1. **Extension conversion** — convert between image formats (PNG, JPEG, BMP, GIF, TIFF, WebP).
  2. **Image size conversion** — resize images to user-specified dimensions.
- Share input file / output folder paths with the "PDF Operations" tab.
- Support drag-and-drop into the input / output path entries.
- Enforce copy-protected file restrictions (same as PDF Operations tab).

## Prerequisites
- The tab name message code already exists: `U006` ("File Extension and Size" / "ファイル拡張子とサイズ").
- Existing widget message codes: `U012` (Width), `U013` (Height), `U014` (Convert).
- Theme JSON entries exist for `width_size_set_label`, `height_size_set_label`, `convert_image_button`.
- `DragAndDropHandler` is reusable from `controllers/drag_and_drop_file.py`.
- PIL/Pillow is already a project dependency.

## Current State Audit

### Tab Registration (`main.py`)
- **Line 930**: `image_ope_tab = tk.Frame(notebook)` — commented out.
- **Line 979**: `notebook.add(image_ope_tab, ...)` — commented out.
- `TabContainerBgUpdater` does not include `image_ope_tab` in its container list (line 968).
- The `ImageOperationApp` import and instantiation are absent from `main()`.

### View (`views/image_ope_tab.py`)
- **Layout**: 3 vertical frames (`frame_main0`, `frame_main1`, `frame_main2`).
  - `frame_main0`: Language combo + theme change button.
  - `frame_main1`: Base file path entry/button + output folder path entry/button + image color change button.
  - `frame_main2`: Canvas (preview) + size conversion controls (width/height entries + convert button).
- **Extension conversion**: `image_file_format_conversion()` and `standardization_image_file_extensions()` exist but are skeletal (only GIF→PNG path, no UI trigger).
- **Size conversion**: `_convert_image()` calls `ImageSizeConverter.resize_image()` — works but lacks degradation warnings.
- **Drag-and-drop**: Set up on canvas only; not on path entries.
- **Copy-protection handling**: Not implemented.
- **Issues**:
  - `_on_output_folder_select()` has size conversion widget creation inside its body (code after `return` — likely misindented; widgets are created during folder selection, not at init time).
  - `NullProgressCallback` and `ImageSizeConverter` are inline classes at module bottom — should be refactored.
  - No extension conversion UI (source/target format selectors, convert button).
  - No alpha/degradation warnings.
  - No preview update after extension conversion.

### Related Files
| File | Role |
|------|------|
| `views/image_ope_tab.py` | Tab view (main target) |
| `main.py` | Tab registration, Notebook setup |
| `controllers/drag_and_drop_file.py` | `DragAndDropHandler.register_drop_target()` |
| `controllers/file2png_by_page.py` | `BaseImageConverter` (used in extension conversion) |
| `controllers/image_operations.py` | `ImageOperations` class (move/rotate/zoom — not needed for M2) |
| `widgets/convert_image_button.py` | `ConvertImageButton` (BaseButton subclass) |
| `widgets/base_image_color_change_button.py` | Color picker button (may be removed/repurposed) |
| `widgets/base_path_entry.py` | Path entry with settings persistence |
| `widgets/base_path_select_button.py` | Path select button with dialog |
| `configurations/message_codes.json` | UI/log/error message codes |
| `themes/dark.json`, `light.json`, `pastel.json` | Theme color entries |

## Implementation Plan

### M2-001: Tab Activation in `main.py`
- Uncomment `image_ope_tab` frame creation and `notebook.add(...)`.
- Add `image_ope_tab` to `TabContainerBgUpdater` container list.
- Import `ImageOperationApp` from `views.image_ope_tab` and instantiate it inside the frame.
- Verify tab appears with correct theme colors.

### M2-002: Layout Redesign of `image_ope_tab.py`
- Reorganize `ImageOperationApp.__init__()` layout:
  - **frame_main0** (top): Language combo + theme change button (keep as-is).
  - **frame_main1** (file paths): Input file path + output folder path + select buttons.
    - Share `entry_setting_key` values with PDF Operations tab (`base_file_path`, `output_folder_path`) so that `user_settings.json` persists the same paths.
    - Remove `BaseImageColorChangeButton` (not needed for extension/size conversion).
    - Register drag-and-drop on path entry widgets (input: image files; output: folders).
    - Accepted input extensions: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`.
  - **frame_main2** (extension conversion section):
    - Source format label (auto-detected from input file).
    - Target format Combobox: PNG, JPEG, BMP, GIF, TIFF, WebP.
    - "Convert Extension" button.
    - Info label for alpha/degradation warnings.
  - **frame_main3** (size conversion section):
    - Width / Height entries (existing `U012`, `U013`).
    - Aspect ratio lock checkbox.
    - "Convert Size" button (existing `U014`).
    - Info label for degradation warnings.
  - **frame_main4** (preview / status):
    - Canvas for image preview (keep existing).
    - Status bar label (keep existing).

### M2-003: Extension Conversion Logic
- Implement `_convert_extension()`:
  1. Read input file via PIL.
  2. Detect source format and alpha channel presence.
  3. If target format does not support alpha (e.g., JPEG, BMP):
     - Show confirmation dialog: "Alpha channel will be lost. Proceed?" (new message code).
     - If user cancels, abort.
     - If user confirms, convert RGBA → RGB with white background.
  4. If converting from lossless to lossy (e.g., PNG → JPEG):
     - Show confirmation dialog: "Image quality may degrade. Proceed?" (new message code).
  5. Save to output folder with new extension.
  6. Update preview canvas.
  7. Show success/failure in status bar.
- Supported format matrix:

| Source → Target | PNG | JPEG | BMP | GIF | TIFF | WebP |
|-----------------|-----|------|-----|-----|------|------|
| PNG             | —   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | ✓    |
| JPEG            | ✓   | —    | ✓   | ⚠C  | ✓    | ✓    |
| BMP             | ✓   | ⚠Q   | —   | ⚠C  | ✓    | ✓    |
| GIF             | ✓   | ⚠Q   | ✓   | —   | ✓    | ✓    |
| TIFF            | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| —    | ✓    |
| WebP            | ✓   | ⚠α+Q | ⚠α  | ⚠α+C| ✓    | —    |

  - ⚠α = alpha loss warning
  - ⚠Q = quality degradation warning (lossless → lossy)
  - ⚠C = color depth reduction warning (256 colors)
  - ✓ = safe conversion

### M2-004: Size Conversion Logic
- Refactor `_convert_image()` / `ImageSizeConverter`:
  1. Read input file via PIL.
  2. Validate width/height > 0 (existing).
  3. Add full-width → half-width normalization (reuse pattern from M1-008).
  4. If target size is **larger** than source (upscaling):
     - Show confirmation dialog: "Image quality may degrade due to upscaling. Proceed?" (new message code).
  5. Aspect ratio lock: when enabled, changing width auto-calculates height and vice versa.
  6. Save to output folder with `_resized` suffix.
  7. Update preview canvas.
- Resampling: use `Image.Resampling.LANCZOS` for downscaling, `Image.Resampling.BICUBIC` for upscaling.

### M2-005: Copy-Protected File Handling
- When a PDF file is selected as input (for conversion to image), check `Encrypted` flag.
- When an image file extracted from a copy-protected PDF is detected, disable conversion buttons.
- Display the same warning style as PDF Operations tab (red border, light red background, white text).
- Reuse the `_show_blocked_warning()` pattern from `MouseEventHandler`.

### M2-006: Shared Input/Output Paths
- Use the same `entry_setting_key` values as PDF Operations tab:
  - Input: `base_file_path`
  - Output: `output_folder_path`
- `BasePathEntry` already persists to `user_settings.json` via these keys.
- When the user sets a path in one tab, it should be reflected in the other tab on next focus.

### M2-007: Drag-and-Drop Support
- Register drag-and-drop on:
  - Input path entry: accept image files (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`) and PDF files (`.pdf`).
  - Output path entry: accept folder paths.
  - Canvas: accept image files (preview).
- Use `DragAndDropHandler.register_drop_target()` from `controllers/drag_and_drop_file.py`.

### M2-008: New Message Codes
- UI messages (candidates — exact codes TBD during implementation):
  - `U075`: "Source format:" / "変換元形式:"
  - `U076`: "Target format:" / "変換先形式:"
  - `U077`: "Convert Extension" / "拡張子変換"
  - `U078`: "Alpha channel will be lost. Proceed?" / "アルファチャンネルが失われます。続行しますか？"
  - `U079`: "Image quality may degrade. Proceed?" / "画像品質が劣化する可能性があります。続行しますか？"
  - `U080`: "Color depth will be reduced to 256 colors. Proceed?" / "色深度が256色に削減されます。続行しますか？"
  - `U081`: "Lock aspect ratio" / "アスペクト比を固定"
  - `U082`: "Image quality may degrade due to upscaling. Proceed?" / "拡大により画像品質が劣化する可能性があります。続行しますか？"
  - `U083`: "Extension conversion completed." / "拡張子変換が完了しました。"
  - `U084`: "Size conversion completed." / "サイズ変換が完了しました。"

### M2-009: Theme Color Entries
- Add theme entries to `dark.json`, `light.json`, `pastel.json` for new widgets:
  - `ext_convert_button` (extension conversion button)
  - `size_convert_button` (may reuse `convert_image_button`)
  - `aspect_ratio_checkbox`
  - `warning_info_label`
- Ensure all existing entries (`width_size_set_label`, `height_size_set_label`, `convert_image_button`) are used correctly.

### M2-010: Code Cleanup
- Fix the misindented code in `_on_output_folder_select()` (size conversion widgets created inside method body).
- Move `ImageSizeConverter` to `controllers/image_operations.py` or a new dedicated module.
- Remove `NullProgressCallback` if no longer needed.
- Remove or repurpose `BaseImageColorChangeButton` usage if not needed for M2.

## Verification Checklist (for Tasks.md)
- [ ] Tab is visible and selectable in the Notebook.
- [ ] Theme colors apply correctly to all new widgets.
- [ ] Input file path and output folder path are shared with PDF Operations tab.
- [ ] Drag-and-drop works on input/output path entries and canvas.
- [ ] Extension conversion: PNG → JPEG shows alpha warning.
- [ ] Extension conversion: PNG → JPEG produces valid JPEG file.
- [ ] Extension conversion: JPEG → PNG produces valid PNG file.
- [ ] Size conversion: downscale produces correct size.
- [ ] Size conversion: upscale shows degradation warning.
- [ ] Aspect ratio lock works correctly.
- [ ] Copy-protected file: conversion buttons are disabled, warning is shown.
- [ ] All message codes display correctly in Japanese and English.

---
Updated: 2026-02-16
