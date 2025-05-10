from __future__ import annotations

import tkinter as tk
from logging import getLogger
from typing import List, Optional, Callable

from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()


def update_page_label(
    page_var: tk.IntVar,
    current_file_page_amount: tk.IntVar,
    total_pages_label: tk.Label,
    current_index: int,
    max_pages: int,
) -> None:
    """Set the display text for current page and total pages.
    
    Args:
        page_var: Variable for current page number
        current_file_page_amount: Variable for total page amount
        total_pages_label: Label to display total pages
        current_index: Current page index (0-based)
        max_pages: Total number of pages
    """
    try:
        # current_index is 0-based, but we display as 1-based
        page_var.set(current_index + 1)
        current_file_page_amount.set(max_pages)
        total_pages_label.configure(text=f" / {max_pages}")
        
        logger.debug(message_manager.get_log_message("L209", current_index + 1, max_pages))
    except Exception as e:
        logger.error(message_manager.get_log_message("L195", str(e)))
        raise


def show_current_page(
    canvas: tk.Canvas,
    current_page_index: int,
    base_pages: List[str],
    comp_pages: List[str],
    base_visible: bool,
    comp_visible: bool,
    base_transform_data: List[tuple[float, float, float, float]],
    comp_transform_data: List[tuple[float, float, float, float]],
    update_page_label_func: Optional[Callable[[int, int], None]] = None,
) -> None:
    """Show the current page on the canvas.
    
    Args:
        canvas: Canvas to draw on
        current_page_index: Current page index
        base_pages: List of base file page paths
        comp_pages: List of comparison file page paths
        base_visible: Whether base file is visible
        comp_visible: Whether comparison file is visible
        base_transform_data: Transform data for base pages
        comp_transform_data: Transform data for comparison pages
        update_page_label_func: Optional callback to update page label
    """
    try:
        canvas.delete("all")
        
        # Calculate max pages
        max_pages = max(
            len(base_pages) if base_visible else 0,
            len(comp_pages) if comp_visible else 0,
        )
        
        if max_pages == 0:
            logger.warning(message_manager.get_log_message("L210"))
            return
            
        # Update page label if callback provided
        if update_page_label_func:
            update_page_label_func(current_page_index, max_pages)
            
        # Show base page if visible
        if base_visible and current_page_index < len(base_pages):
            # Base page display logic here
            logger.debug(message_manager.get_log_message("L196", current_page_index + 1))
            
        # Show comparison page if visible
        if comp_visible and current_page_index < len(comp_pages):
            # Comparison page display logic here
            logger.debug(message_manager.get_log_message("L197", current_page_index + 1))
            
    except Exception as e:
        logger.error(message_manager.get_log_message("L198", str(e)))
        raise
