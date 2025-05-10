from configurations import tool_settings


def apply_eme() -> None:
    if cfg.theme_mode == "dark":
        # Dark Theme
        cfg.base_bg_color = "#1d1d29"
        cfg.primary_bg_color = "#27283a"
        cfg.primary_font_color = "#43c0cd"
        cfg.secondary_font_color = "#db57c4"
        cfg.blue_font_color = "#3e77d2"
        cfg.red_font_color = "#c03755"
        cfg.btn_inactive_bg_color = "#22a9e9"
        cfg.btn_inactive_font_color = "#27283a"
        cfg.btn_active_bg_color = "#0fd2d6"
        cfg.btn_active_font_color = "#574ed6"
    elif cfg.theme_mode == "light":
        # Light Theme
        cfg.base_bg_color = "#f0f0f0"
        cfg.primary_bg_color = "#ffffff"
        cfg.primary_font_color = "#000000"
        cfg.secondary_font_color = "#000000"
        cfg.blue_font_color = "#3e77d2"
        cfg.red_font_color = "#c03755"
        cfg.btn_inactive_bg_color = "#22a9e9"
        cfg.btn_inactive_font_color = "#ffffff"
        cfg.btn_active_bg_color = "#0fd2d6"
        cfg.btn_active_font_color = "#574ed6"
    elif cfg.theme_mode == "pastel":
        # Pastel Theme
        cfg.base_bg_color = "#f2f0e6"
        cfg.primary_bg_color = "#fffbf5"
        cfg.primary_font_color = "#6b6b6b"
        cfg.secondary_font_color = "#a88fb9"
        cfg.blue_font_color = "#a5c9ea"
        cfg.red_font_color = "#f8a5a5"
        cfg.btn_inactive_bg_color = "#c9e6d0"
        cfg.btn_inactive_font_color = "#ffffff"
        cfg.btn_active_bg_color = "#f7d6c1"
        cfg.btn_active_font_color = "#9375b7"
    else:
        # Dark Theme
        cfg.base_bg_color = "#1d1d29"
        cfg.primary_bg_color = "#27283a"
        cfg.primary_font_color = "#43c0cd"
        cfg.secondary_font_color = "#db57c4"
        cfg.blue_font_color = "#3e77d2"
        cfg.red_font_color = "#c03755"
        cfg.btn_inactive_bg_color = "#22a9e9"
        cfg.btn_inactive_font_color = "#27283a"
        cfg.btn_active_bg_color = "#0fd2d6"
        cfg.btn_active_font_color = "#574ed6"
