"""
Utility functions for the Telegram bot
"""

import re
import os
import logging
from urllib.parse import urlparse, unquote
from pathlib import Path
from typing import Optional

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size)} {size_names[i]}"
    else:
        return f"{size:.1f} {size_names[i]}"

def get_filename_from_url(url: str) -> str:
    """Extract filename from URL"""
    try:
        parsed_url = urlparse(url)
        path = unquote(parsed_url.path)
        
        # Get filename from path
        filename = os.path.basename(path)
        
        # If no filename found, create a default one
        if not filename or '.' not in filename:
            # Try to get from URL parameters
            if parsed_url.query:
                for param in parsed_url.query.split('&'):
                    if 'filename=' in param:
                        filename = param.split('filename=')[1]
                        break
            
            # Still no filename? Create default
            if not filename or '.' not in filename:
                filename = f"download_{hash(url) % 10000}.bin"
        
        return sanitize_filename(filename)
        
    except Exception as e:
        logger.warning(f"Error extracting filename from URL {url}: {e}")
        return f"download_{hash(url) % 10000}.bin"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_length = 255 - len(ext)
        filename = name[:max_name_length] + ext
    
    # Ensure filename is not empty
    if not filename.strip():
        filename = "download.bin"
    
    return filename.strip()

def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

def is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def extract_urls_from_text(text: str) -> list:
    """Extract URLs from text"""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return url_pattern.findall(text)

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_datetime(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        from datetime import datetime
        dt = datetime.fromisoformat(dt)
    
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower()

def is_supported_file_type(filename: str) -> bool:
    """Check if file type is supported for download"""
    # Add any file type restrictions here if needed
    # For now, allow all file types
    return True

def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Create a text progress bar"""
    if total == 0:
        return "█" * length
    
    progress = current / total
    filled_length = int(length * progress)
    bar = "█" * filled_length + "░" * (length - filled_length)
    percentage = progress * 100
    
    return f"{bar} {percentage:.1f}%"

def validate_file_size(size: int, max_size: int) -> bool:
    """Validate if file size is within limits"""
    return 0 < size <= max_size

def get_mime_type_from_extension(filename: str) -> str:
    """Get MIME type from file extension"""
    ext = get_file_extension(filename)
    
    mime_types = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.zip': 'application/zip',
        '.rar': 'application/vnd.rar',
        '.7z': 'application/x-7z-compressed',
        '.txt': 'text/plain',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac'
    }
    
    return mime_types.get(ext, 'application/octet-stream')

def log_user_action(user_id: int, action: str, details: str = ""):
    """Log user actions for debugging"""
    logger.info(f"User {user_id} - {action}" + (f" - {details}" if details else ""))

def safe_int(value, default: int = 0) -> int:
    """Safely convert value to integer"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
