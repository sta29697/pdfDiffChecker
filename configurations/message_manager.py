"""
Message manager for internationalization.

This module provides the MessageManager class, which is responsible for
managing message codes and internationalization throughout the application.
"""

import json
import os
from logging import getLogger
from typing import Dict, Any, Optional

logger = getLogger(__name__)

# Hardcoded messages for initialization errors
# These are needed before the message system is fully initialized
INIT_MESSAGES = {
    "load_success": {
        "en": "Loaded {} message categories",
        "ja": "{}個のメッセージカテゴリを読み込みました",
    },
    "load_error": {
        "en": "Failed to load message codes: {}",
        "ja": "メッセージコードの読み込みに失敗しました: {}",
    },
    "instance_exists": {
        "en": "MessageManager instance already exists. Use get_instance() instead.",
        "ja": "MessageManagerインスタンスは既に存在します。get_instance()を使用してください。",
    },
    "unknown_prefix": {
        "en": "Unknown code prefix: {}",
        "ja": "不明なコードプレフィックス: {}",
    },
    "unknown_code": {
        "en": "Unknown code: {}",
        "ja": "不明なコード: {}",
    },
    "error_formatting": {
        "en": "Error formatting message {}: {}",
        "ja": "メッセージのフォーマットエラー {}: {}",
    },
    "language_already_set": {
        "en": "[SYS] Language is already set to {}. Skipping.",
        "ja": "[SYS] 言語は既に {} に設定されています。スキップします",
    },
    "language_set": {
        "en": "[SYS] Language set to {}",
        "ja": "[SYS] 言語を {} に設定しました",
    },
}


class MessageManager:
    """Message manager for internationalization.

    This class is responsible for managing message codes and internationalization
    throughout the application. It follows the singleton pattern to ensure
    only one instance is used.

    Attributes:
        _instance (Optional[MessageManager]): Singleton instance
        _messages (Dict[str, Dict[str, Dict[str, str]]]): Message codes and translations
        _language (str): Current language code (e.g., "en", "ja")
    """

    _instance: Optional["MessageManager"] = None
    _messages: Dict[str, Dict[str, Dict[str, str]]] = {}
    _language: str = "ja"  # Default to Japanese

    @classmethod
    def get_instance(cls) -> "MessageManager":
        """Get the singleton instance of MessageManager.

        Returns:
            MessageManager: Singleton instance
        """
        if cls._instance is None:
            cls._instance = MessageManager()
        return cls._instance

    def __init__(self) -> None:
        """Initialize the MessageManager.

        Loads message codes from the JSON file and sets the default language.
        """
        if MessageManager._instance is not None:
            logger.warning(INIT_MESSAGES["instance_exists"][self._language])
        else:
            MessageManager._instance = self
            self._load_messages()

    def _load_messages(self) -> None:
        """Load message codes from the JSON file.

        This method loads message codes from the message_codes.json file
        and stores them in memory to minimize file access.
        """
        try:
            message_file = os.path.join("configurations", "message_codes.json")
            with open(message_file, "r", encoding="utf-8") as f:
                self._messages = json.load(f)
            logger.info(
                INIT_MESSAGES["load_success"][self._language].format(
                    len(self._messages)
                )
            )
        except Exception as e:
            logger.error(INIT_MESSAGES["load_error"][self._language].format(e))
            # Initialize with empty dictionaries to avoid errors
            self._messages = {
                "error_codes": {},
                "log_codes": {},
                "message_codes": {},
                "ui_codes": {},
            }

    def set_language(self, language_code: str) -> None:
        """Set the current language.

        Args:
            language_code (str): Language code (e.g., "en", "ja")
        """
        # Skip processing if language is already set to requested language
        if self._language == language_code:
            # Only debug log for repeated language setting attempts - use L003 message code if available
            if "L003" in self._messages.get("log_codes", {}):
                logger.debug(self.get_log_message("L003", language_code))
            else:
                logger.debug(INIT_MESSAGES["language_already_set"][self._language].format(language_code))
            return
            
        # Log current and requested language for actual changes
        # Support both ISO codes (ja, en) and friendly names (japanese, english)
        normalized_code = language_code.lower()
        if normalized_code in ["en", "ja", "english", "japanese"]:
            # Map friendly names to ISO codes
            if normalized_code == "japanese":
                self._language = "ja"
            elif normalized_code == "english":
                self._language = "en"
            else:
                self._language = normalized_code
                
            # Use direct logging to avoid potential infinite recursion
            if "L003" in self._messages.get("log_codes", {}):
                logger.info(self.get_log_message("L003", self._language))
            else:
                logger.info(INIT_MESSAGES["language_set"][self._language].format(self._language))
            # Additional check to prevent redundant theme reloads with language changes
            # Only notify about language change, not reload themes on redundant calls
        else:
            # Log warning for unsupported language
            logger.warning(self.get_log_message("L004", language_code))

    def get_message(self, code: str, *args: Any) -> str:
        """Get a message by its code.

        Args:
            code (str): Message code (e.g., "E001", "L001", "M001", "U001")
            *args: Arguments to format into the message

        Returns:
            str: Formatted message in the current language
        """
        try:
            # Determine category based on code prefix
            if code.startswith("E"):
                category = "error_codes"
            elif code.startswith("L"):
                category = "log_codes"
            elif code.startswith("M"):
                category = "message_codes"
            elif code.startswith("U"):
                category = "ui_codes"
            else:
                # Use hardcoded message to avoid potential infinite recursion
                error_msg = INIT_MESSAGES["unknown_prefix"][self._language].format(code)
                logger.warning(error_msg)
                return error_msg

            # Get message from the appropriate category
            if category in self._messages and code in self._messages[category]:
                message_template = self._messages[category][code].get(
                    self._language, self._messages[category][code].get("en", code)
                )
                # Only format when arguments are provided
                if args:
                    return message_template.format(*args)
                return message_template
            else:
                # Use hardcoded message to avoid potential infinite recursion
                error_msg = INIT_MESSAGES["unknown_code"][self._language].format(code)
                logger.warning(error_msg)
                return error_msg
        except Exception as e:
            # Use hardcoded message to avoid potential infinite recursion
            error_msg = INIT_MESSAGES["error_formatting"][self._language].format(
                code, e
            )
            logger.error(error_msg)
            return error_msg

    def get_error_message(self, code: str, *args: Any) -> str:
        """Get an error message by its code.

        Args:
            code (str): Error code (e.g., "E001")
            *args: Arguments to format into the message

        Returns:
            str: Formatted error message in the current language
        """
        return self.get_message(code, *args)

    def get_log_message(self, code: str, *args: Any) -> str:
        """Get a log message by its code.

        Args:
            code (str): Log code (e.g., "L001")
            *args: Arguments to format into the message

        Returns:
            str: Formatted log message in the current language
        """
        return self.get_message(code, *args)

    def get_ui_message(self, code: str, *args: Any) -> str:
        """Get a UI message by its code.

        Args:
            code (str): UI code (e.g., "U001")
            *args: Arguments to format into the message

        Returns:
            str: Formatted UI message in the current language
        """
        return self.get_message(code, *args)

    def get_user_message(self, code: str, *args: Any) -> str:
        """Get a user-facing message by its code.

        Args:
            code (str): Message code (e.g., "M001")
            *args: Arguments to format into the message

        Returns:
            str: Formatted user message in the current language
        """
        return self.get_message(code, *args)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        This method is primarily used for testing purposes.
        """
        cls._instance = None


# For backward compatibility
ErrorManager = MessageManager


def get_message_manager() -> MessageManager:
    """Get the singleton instance of MessageManager.

    Returns:
        MessageManager: The singleton instance
    """
    return MessageManager.get_instance()
