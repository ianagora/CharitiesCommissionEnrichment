"""File validation utilities for secure file uploads."""
import io
from typing import Tuple, Optional
import structlog

logger = structlog.get_logger()

# Magic bytes for allowed file types
# https://en.wikipedia.org/wiki/List_of_file_signatures
FILE_SIGNATURES = {
    # CSV - text file, no magic bytes, but we can check content
    "csv": {
        "extensions": [".csv"],
        "mime_types": ["text/csv", "text/plain", "application/csv"],
        "magic_bytes": None,  # Text file, validate differently
    },
    # Excel XLSX (ZIP-based Office Open XML)
    "xlsx": {
        "extensions": [".xlsx"],
        "mime_types": [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        ],
        "magic_bytes": b"PK\x03\x04",  # ZIP signature
    },
    # Excel XLS (OLE2 Compound Document)
    "xls": {
        "extensions": [".xls"],
        "mime_types": [
            "application/vnd.ms-excel",
            "application/x-msexcel",
        ],
        "magic_bytes": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  # OLE2 signature
    },
}

# Maximum file size in bytes (10MB default)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Dangerous content patterns to reject
DANGEROUS_PATTERNS = [
    b"<script",
    b"javascript:",
    b"vbscript:",
    b"onclick=",
    b"onerror=",
    b"onload=",
]


def validate_file_extension(filename: str, allowed_extensions: list[str]) -> Tuple[bool, str]:
    """
    Validate file extension against allowed list.
    
    Returns:
        (is_valid, error_message)
    """
    if not filename:
        return False, "Filename is required"
    
    # Get extension (lowercase)
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    
    if ext not in allowed_extensions:
        return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
    
    return True, ""


def validate_file_magic_bytes(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validate file content matches expected magic bytes for the extension.
    
    This prevents attacks where malicious files are renamed to allowed extensions.
    
    Returns:
        (is_valid, error_message)
    """
    if not content:
        return False, "File is empty"
    
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    
    # Find the file type config for this extension
    file_type = None
    for type_name, config in FILE_SIGNATURES.items():
        if ext in config["extensions"]:
            file_type = config
            break
    
    if not file_type:
        return False, f"Unknown file extension: {ext}"
    
    # CSV files don't have magic bytes - validate as text
    if file_type["magic_bytes"] is None:
        return validate_csv_content(content)
    
    # Check magic bytes
    expected_magic = file_type["magic_bytes"]
    if not content.startswith(expected_magic):
        logger.warning(
            "File magic bytes mismatch",
            filename=filename,
            expected=expected_magic.hex(),
            actual=content[:len(expected_magic)].hex() if len(content) >= len(expected_magic) else content.hex(),
        )
        return False, f"File content does not match expected format for {ext}"
    
    return True, ""


def validate_csv_content(content: bytes) -> Tuple[bool, str]:
    """
    Validate CSV content is safe text.
    
    Returns:
        (is_valid, error_message)
    """
    # Check for dangerous patterns
    content_lower = content.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in content_lower:
            logger.warning("Dangerous pattern found in CSV", pattern=pattern.decode())
            return False, "File contains potentially dangerous content"
    
    # Try to decode as UTF-8 or Latin-1 (common CSV encodings)
    try:
        # Try UTF-8 first
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            # Fall back to Latin-1
            text = content.decode("latin-1")
        except UnicodeDecodeError:
            return False, "File is not valid text (UTF-8 or Latin-1 encoding required)"
    
    # Check for null bytes (binary file disguised as CSV)
    if "\x00" in text:
        return False, "File contains binary content"
    
    # Check it looks like CSV (has commas or is small enough to be valid)
    if len(text) > 100 and "," not in text and "\t" not in text:
        return False, "File does not appear to be a valid CSV"
    
    return True, ""


def validate_file_size(content: bytes, max_size: int = MAX_FILE_SIZE) -> Tuple[bool, str]:
    """
    Validate file size.
    
    Returns:
        (is_valid, error_message)
    """
    if len(content) > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = len(content) / (1024 * 1024)
        return False, f"File size ({actual_mb:.1f}MB) exceeds maximum ({max_mb:.1f}MB)"
    
    return True, ""


async def validate_upload_file(
    content: bytes,
    filename: str,
    allowed_extensions: list[str],
    max_size_mb: int = 10,
) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive file upload validation.
    
    Validates:
    1. File extension is allowed
    2. File size is within limits
    3. File content matches expected format (magic bytes)
    4. No dangerous content patterns
    
    Returns:
        (is_valid, error_message or None if valid)
    """
    # Validate extension
    is_valid, error = validate_file_extension(filename, allowed_extensions)
    if not is_valid:
        return False, error
    
    # Validate size
    max_size = max_size_mb * 1024 * 1024
    is_valid, error = validate_file_size(content, max_size)
    if not is_valid:
        return False, error
    
    # Validate content/magic bytes
    is_valid, error = validate_file_magic_bytes(content, filename)
    if not is_valid:
        return False, error
    
    logger.info(
        "File validation passed",
        filename=filename,
        size_bytes=len(content),
    )
    
    return True, None
