"""Security utilities for the application."""
import html
import re
from typing import Any, Dict, List, Union
import structlog

logger = structlog.get_logger()


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    This converts:
    - & to &amp;
    - < to &lt;
    - > to &gt;
    - " to &quot;
    - ' to &#x27;
    
    Args:
        text: The text to escape
        
    Returns:
        HTML-escaped text
    """
    if not text:
        return text
    return html.escape(str(text), quote=True)


def sanitize_string(text: str, max_length: int = 10000) -> str:
    """
    Sanitize a string for safe output.
    
    - Removes null bytes
    - Removes control characters (except newlines and tabs)
    - Truncates to max_length
    - Escapes HTML
    
    Args:
        text: The text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return text
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]
    
    return escape_html(text)


def sanitize_dict(data: Dict[str, Any], max_string_length: int = 10000) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        max_string_length: Maximum length for string values
        
    Returns:
        Sanitized dictionary
    """
    if not data:
        return data
    
    sanitized = {}
    for key, value in data.items():
        # Sanitize the key too
        safe_key = sanitize_string(str(key), max_length=255) if isinstance(key, str) else key
        
        if isinstance(value, str):
            sanitized[safe_key] = sanitize_string(value, max_string_length)
        elif isinstance(value, dict):
            sanitized[safe_key] = sanitize_dict(value, max_string_length)
        elif isinstance(value, list):
            sanitized[safe_key] = sanitize_list(value, max_string_length)
        else:
            sanitized[safe_key] = value
    
    return sanitized


def sanitize_list(data: List[Any], max_string_length: int = 10000) -> List[Any]:
    """
    Recursively sanitize all string values in a list.
    
    Args:
        data: List to sanitize
        max_string_length: Maximum length for string values
        
    Returns:
        Sanitized list
    """
    if not data:
        return data
    
    sanitized = []
    for item in data:
        if isinstance(item, str):
            sanitized.append(sanitize_string(item, max_string_length))
        elif isinstance(item, dict):
            sanitized.append(sanitize_dict(item, max_string_length))
        elif isinstance(item, list):
            sanitized.append(sanitize_list(item, max_string_length))
        else:
            sanitized.append(item)
    
    return sanitized


def sanitize_for_json_response(data: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
    """
    Sanitize data for safe JSON response output.
    
    This is the main entry point for sanitizing API responses.
    
    Args:
        data: Data to sanitize (dict, list, or string)
        
    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        return sanitize_string(data)
    elif isinstance(data, dict):
        return sanitize_dict(data)
    elif isinstance(data, list):
        return sanitize_list(data)
    else:
        return data


def strip_dangerous_html_tags(text: str) -> str:
    """
    Remove potentially dangerous HTML tags while preserving safe content.
    
    This is a more permissive sanitization that allows basic formatting
    but removes script tags, event handlers, etc.
    
    Args:
        text: Text that may contain HTML
        
    Returns:
        Text with dangerous elements removed
    """
    if not text:
        return text
    
    # Remove script tags and content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove style tags and content
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove event handlers (onclick, onerror, etc.)
    text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+on\w+\s*=\s*[^\s>]+', '', text, flags=re.IGNORECASE)
    
    # Remove javascript: and vbscript: URLs
    text = re.sub(r'(href|src|action)\s*=\s*["\']?\s*javascript:[^"\'>\s]*', r'\1=""', text, flags=re.IGNORECASE)
    text = re.sub(r'(href|src|action)\s*=\s*["\']?\s*vbscript:[^"\'>\s]*', r'\1=""', text, flags=re.IGNORECASE)
    
    # Remove data: URLs in src attributes (can be used for XSS)
    text = re.sub(r'src\s*=\s*["\']?\s*data:[^"\'>\s]*', 'src=""', text, flags=re.IGNORECASE)
    
    return text


class XSSProtection:
    """
    Context manager and decorator for XSS protection.
    
    Usage as decorator:
        @XSSProtection.sanitize_response
        async def my_endpoint():
            return {"user_input": potentially_dangerous_string}
    """
    
    @staticmethod
    def sanitize_response(func):
        """Decorator to sanitize function response."""
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            return sanitize_for_json_response(result)
        return wrapper
