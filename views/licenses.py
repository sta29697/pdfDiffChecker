from __future__ import annotations
from logging import getLogger
import webbrowser
from typing import Dict, Optional, Any
import tkinter as tk
from tkinter import scrolledtext


from controllers.color_theme_manager import ColorThemeManager
from widgets.base_tab_widgets import BaseTabWidgets
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()


license_header = """
Additional License Information:

This application uses various open-source libraries and components.
The main licenses are shown below.
"""

MIT_licenses = """
=======MIT License=======
The MIT License (MIT)

Copyright (c) 2004 Holger Krekel and others

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

GPL2_licenses = """
=======GPL v2 License=======
Copyright (c) 2024

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.
"""


class LicensesApp(tk.Frame, ColoringThemeIF):
    def callback(self, url: str) -> None:
        """Open the specified URL in a web browser.

        Args:
            url (str): URL to open
        """
        webbrowser.open_new(url)

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the licenses view.

        Args:
            master (Optional[tk.Misc]): Parent widget
            **kwargs: Additional keyword arguments
        """
        super().__init__(master, **kwargs)
        self.root = master
        self.base_widgets = BaseTabWidgets()
        
        self.frame = tk.Frame(self)
        self.frame.pack(expand=True, fill="both")

        # Configure the ScrolledText widget
        self.licenses_text = scrolledtext.ScrolledText(self.frame)
        self.licenses_text.pack(expand=True, fill="both")

        # Change the state to normal before inserting text
        self.licenses_text.config(state="normal")

        # Insert header text
        self.licenses_text.insert(tk.END, license_header)
        
        # Insert licenses - these remain the same in both languages
        self.licenses_text.insert(tk.END, MIT_licenses)
        self.licenses_text.insert(tk.END, GPL2_licenses)

        # Insert URL and configure tag
        self.licenses_text.insert(tk.END, "\nhttp://www.gnu.org/licenses/")
        self.licenses_text.tag_add("gnu_link", "end-1l", "end")
        self.licenses_text.tag_config("gnu_link", foreground="blue", underline=True)

        # Configure tag events
        self.licenses_text.tag_bind(
            "gnu_link",
            "<Button-1>",
            lambda e: self.callback("http://www.gnu.org/licenses/"),
        )
        self.licenses_text.tag_bind(
            "gnu_link", "<Enter>", lambda e: self.licenses_text.config(cursor="hand2")
        )  # Change cursor to pointer on mouse over
        self.licenses_text.tag_bind(
            "gnu_link", "<Leave>", lambda e: self.licenses_text.config(cursor="")
        )  # Restore cursor when mouse leaves

        # Set the text to disabled again to prevent editing
        self.licenses_text.config(state="disabled")

        # Apply color theme to the window (ignore type check for Mypy)
        self.apply_theme_color(ColorThemeManager.get_current_theme())  # type: ignore
        
        # Don't directly bind window events in tab mode
        # Main window should handle these events centrally
        # This prevents conflicts between tab-level and application-level control

    def bind_window_events(self, master: tk.Tk | tk.Toplevel) -> None:
        """Bind window events and close event to exit window.
        When running in tab mode, do not bind window events.
        
        Args:
            master: The Tk or Toplevel window to bind events to
        """
        # This method is intentionally empty
        # All window events are now centrally managed by WindowEventManager in main.py
        # DO NOT set any protocol handlers or bindings here to avoid conflicts
        # with the central event handling system in the main window
        # 
        # Previous implementation incorrectly overwrote the WM_DELETE_WINDOW protocol
        # which caused window control buttons to malfunction
        pass

    def apply_theme_color(self, theme: Dict[str, Dict[str, str]]) -> None:
        """Apply theme safely, filtering unsupported options per widget."""
        widget_class = self.winfo_class()
        # Apply to self
        config = theme.get(widget_class)
        if config:
            valid_opts = set(self.keys())
            filtered = {k: v for k, v in config.items() if k in valid_opts}
            try:
                if filtered:
                    self._config_widget(filtered)
                    logger.debug(message_manager.get_log_message("L143", widget_class))
            except Exception as e:
                logger.error(message_manager.get_log_message("L145", str(e)))
        # Apply to children
        for child in self.winfo_children():
            child_class = child.winfo_class()
            config = theme.get(child_class)
            if not config:
                continue
            # Filter only supported options
            valid_opts = set(child.keys())
            filtered = {k: v for k, v in config.items() if k in valid_opts}
            if not filtered:
                continue
            try:
                child.configure(**filtered)
                logger.debug(message_manager.get_log_message("L144", child_class))
            except Exception as e:
                logger.error(message_manager.get_log_message("L145", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings."""
        self.configure(**theme_settings)  # type: ignore
        
    def refresh_language(self) -> None:
        """Update UI text elements with the current language.
        
        This method should be called when the application language is changed
        to update all text elements in this tab.
        """
        # Process for language update
        
        # Update text content with current language
        self.licenses_text.config(state="normal")
        
        # Clear existing content
        self.licenses_text.delete("1.0", tk.END)
        
        # Insert new content with appropriate language
        self.licenses_text.insert(tk.END, license_header)
        self.licenses_text.insert(tk.END, MIT_licenses)
        self.licenses_text.insert(tk.END, GPL2_licenses)
        
        # Insert URL and configure tag
        self.licenses_text.insert(tk.END, "\nhttp://www.gnu.org/licenses/")
        self.licenses_text.tag_add("gnu_link", "end-1l", "end")
        self.licenses_text.tag_config("gnu_link", foreground="blue", underline=True)
        
        # Configure tag events
        self.licenses_text.tag_bind(
            "gnu_link",
            "<Button-1>",
            lambda e: self.callback("http://www.gnu.org/licenses/"),
        )
        self.licenses_text.tag_bind(
            "gnu_link", "<Enter>", lambda e: self.licenses_text.config(cursor="hand2")
        )  # Change cursor to pointer on mouse over
        self.licenses_text.tag_bind(
            "gnu_link", "<Leave>", lambda e: self.licenses_text.config(cursor="")
        )  # Restore cursor when mouse leaves
        
        # Disable text widget again to prevent editing
        self.licenses_text.config(state="disabled")
        
        # Log language change with appropriate message code
        logger.debug(message_manager.get_log_message("L228", message_manager._language))


