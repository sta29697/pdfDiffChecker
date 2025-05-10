from typing import Any, Dict

def get_theme_color(
    theme: Dict[str, Any],
    color_key: str,
    fallback_key: str,
    color_type: str,
    hardcoded_default: str
) -> str:
    """
    Get theme color with priority: color_key -> fallback_key -> hardcoded_default.
    """
    if isinstance(theme, dict):
        if color_key in theme and color_type in theme[color_key]:
            return str(theme[color_key][color_type])
        if fallback_key in theme and color_type in theme[fallback_key]:
            return str(theme[fallback_key][color_type])
    return hardcoded_default
