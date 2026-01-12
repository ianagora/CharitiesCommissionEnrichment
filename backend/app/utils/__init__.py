"""Utility modules for the application."""
from app.utils.file_validation import (
    validate_file_extension,
    validate_file_magic_bytes,
    validate_file_size,
    validate_upload_file,
)
from app.utils.security import (
    escape_html,
    sanitize_string,
    sanitize_dict,
    sanitize_list,
    sanitize_for_json_response,
    strip_dangerous_html_tags,
    XSSProtection,
)

__all__ = [
    # File validation
    "validate_file_extension",
    "validate_file_magic_bytes",
    "validate_file_size",
    "validate_upload_file",
    # Security
    "escape_html",
    "sanitize_string",
    "sanitize_dict",
    "sanitize_list",
    "sanitize_for_json_response",
    "strip_dangerous_html_tags",
    "XSSProtection",
]
