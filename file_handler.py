"""
File download and handling functionality
"""

import os
import logging
import aiohttp
import asyncio
from urllib.parse import urlparse, unquote
from pathlib import Path
import tempfile
from typing import Optional, Tuple
from telegram import InputFile
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import MAX_FILE_SIZE, DOWNLOAD_TIMEOUT, CHUNK_SIZE
from utils import format_file_size, get_filename_from_url, sanitize_filename
from mtproto_client import HybridFileHandler

logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self):
        self.session = None
        self.temp_dir = tempfile.mkdtemp(prefix='telegram_bot_')
        self.hybrid_handler = HybridFileHandler()
        self.chunk_size = 45 * 1024 * 1024  # 45MB chunks
        logger.info(f"Temporary directory created: {self.temp_dir}")
        
    async def initialize(self):
        """Initialize the file handler and MTProto if available"""
        await self.hybrid_handler.initialize()
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
        return self.session
    
    async def get_file_info(self, url: str) -> Tuple[Optional[str], Optional[int]]:
        """Get file information without downloading"""
        try:
            session = await self.get_session()
            async with session.head(url, allow_redirects=True) as response:
                if response.status == 200:
                    content_length = response.headers.get('content-length')
                    file_size = int(content_length) if content_length else None
                    
                    # Get filename from Content-Disposition or URL
                    content_disposition = response.headers.get('content-disposition', '')
                    filename = None
                    
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"\'')
                    else:
                        filename = get_filename_from_url(str(response.url))
                    
                    return filename, file_size
                else:
                    logger.warning(f"HEAD request failed with status {response.status} for URL: {url}")
                    return None, None
                    
        except Exception as e:
            logger.error(f"Error getting file info for {url}: {e}")
            return None, None
    
    async def download_file(self, url: str, max_size: int = MAX_FILE_SIZE, allow_large_files: bool = True, progress_callback=None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        Download file from URL
        Returns: (file_path, filename, file_size) or (None, None, None) on failure
        """
        try:
            # Get file info first
            filename, file_size = await self.get_file_info(url)
            
            # Check against our configured maximum size (2GB for large file support)
            MAX_LARGE_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
            if file_size and file_size > MAX_LARGE_FILE_SIZE:
                raise ValueError(f"File size ({format_file_size(file_size)}) exceeds maximum limit ({format_file_size(MAX_LARGE_FILE_SIZE)})")
            
            # Set default filename if not found
            if not filename:
                filename = get_filename_from_url(url)
            
            filename = sanitize_filename(filename)
            
            # Create temporary file path
            temp_file_path = os.path.join(self.temp_dir, filename)
            
            # Ensure unique filename
            counter = 1
            original_path = temp_file_path
            while os.path.exists(temp_file_path):
                name, ext = os.path.splitext(original_path)
                temp_file_path = f"{name}_{counter}{ext}"
                counter += 1
            
            session = await self.get_session()
            downloaded_size = 0
            last_progress_update = 0
            
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}: Failed to download file")
                
                # Check content length again from actual response
                content_length = response.headers.get('content-length')
                total_size = None
                if content_length:
                    total_size = int(content_length)
                    if total_size > max_size:
                        raise ValueError(f"File size ({format_file_size(total_size)}) exceeds maximum limit ({format_file_size(max_size)})")
                
                # Download file in chunks
                with open(temp_file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        downloaded_size += len(chunk)
                        
                        # Check size limit during download
                        if downloaded_size > max_size:
                            file.close()
                            os.remove(temp_file_path)
                            raise ValueError(f"File size exceeds maximum limit ({format_file_size(max_size)})")
                        
                        file.write(chunk)
                        
                        # Update progress callback if provided
                        if progress_callback and total_size and (downloaded_size - last_progress_update) > (1024 * 1024):  # Update every 1MB
                            progress_percent = (downloaded_size / total_size) * 100
                            await progress_callback(downloaded_size, total_size, progress_percent)
                            last_progress_update = downloaded_size
            
            logger.info(f"Downloaded file: {filename} ({format_file_size(downloaded_size)})")
            return temp_file_path, filename, downloaded_size
            
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {e}")
            raise e
    
    async def send_file_to_telegram(self, file_path: str, filename: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send file to Telegram chat"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Telegram Bot API file size limits
            TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB for Bot API
            
            # Check if file exceeds Telegram's limit
            if file_size > TELEGRAM_MAX_FILE_SIZE:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **File too large for Telegram**\n\n"
                         f"📁 File: {filename}\n"
                         f"📏 Size: {format_file_size(file_size)}\n"
                         f"📋 Telegram limit: {format_file_size(TELEGRAM_MAX_FILE_SIZE)}\n\n"
                         f"💡 **Solutions:**\n"
                         f"• Try a file smaller than 50MB\n"
                         f"• Use a file compression tool\n"
                         f"• Split large files into smaller parts",
                    parse_mode='Markdown'
                )
                logger.warning(f"File too large for Telegram: {filename} ({format_file_size(file_size)})")
                return False
            
            # Send file with appropriate timeout based on size
            if file_size > 10 * 1024 * 1024:  # 10MB
                logger.info(f"Sending large file ({format_file_size(file_size)}): {filename}")
            
            with open(file_path, 'rb') as file:
                # Set timeout based on file size
                if file_size > 10 * 1024 * 1024:  # Files larger than 10MB
                    timeout_seconds = min(300, max(60, file_size // (1024 * 1024) * 10))  # 10 seconds per MB, max 5 minutes
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(file, filename=filename),
                        caption=f"📁 **{filename}**\n📏 Size: {format_file_size(file_size)}",
                        parse_mode='Markdown',
                        read_timeout=timeout_seconds,
                        write_timeout=timeout_seconds,
                        connect_timeout=60
                    )
                else:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(file, filename=filename),
                        caption=f"📁 **{filename}**\n📏 Size: {format_file_size(file_size)}",
                        parse_mode='Markdown'
                    )
            
            logger.info(f"Successfully sent file to chat {chat_id}: {filename}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending file {filename}: {e}")
            if "Request Entity Too Large" in str(e) or "File too large" in str(e):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **File too large for Telegram**\n\n"
                         f"📁 File: {filename}\n"
                         f"📏 Size: {format_file_size(file_size)}\n"
                         f"📋 Telegram limit: 2GB for bots\n\n"
                         f"Please try a smaller file.",
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **Failed to send file**\n\n"
                         f"Error: {str(e)}\n"
                         f"Please try again later.",
                    parse_mode='Markdown'
                )
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending file {filename}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Unexpected error**\n\n"
                     f"Error: {str(e)}\n"
                     f"Please try again later.",
                parse_mode='Markdown'
            )
            return False
    
    async def handle_large_file(self, file_path: str, filename: str, file_size: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Handle large files that exceed Telegram's 50MB limit"""
        try:
            TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
            
            if file_size <= TELEGRAM_MAX_FILE_SIZE:
                return False  # Not a large file, handle normally
            
            # This should not be reached if MTProto is working properly
            # Only used as fallback when MTProto credentials are missing
            logger.warning(f"Large file fallback triggered for {filename}")
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📁 **Large File**: {filename}\n"
                     f"📏 **Size**: {format_file_size(file_size)}\n\n"
                     f"⚠️ **MTProto API not configured**\n"
                     f"For 2GB support, add TELEGRAM_API_ID and TELEGRAM_API_HASH\n\n"
                     f"🔄 **Splitting into parts...**",
                parse_mode='Markdown'
            )
            
            # Automatically split the file as fallback
            return await self.split_and_send_file(file_path, filename, file_size, chat_id, context)
            
        except Exception as e:
            logger.error(f"Error handling large file: {e}")
            return False
    
    async def split_file(self, file_path: str, filename: str) -> list:
        """Split file into chunks and return list of chunk paths"""
        try:
            chunks = []
            chunk_num = 1
            
            with open(file_path, 'rb') as infile:
                while True:
                    chunk_data = infile.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    # Create chunk filename
                    name, ext = os.path.splitext(filename)
                    chunk_filename = f"{name}.part{chunk_num:03d}{ext}"
                    chunk_path = os.path.join(self.temp_dir, chunk_filename)
                    
                    # Write chunk
                    with open(chunk_path, 'wb') as chunk_file:
                        chunk_file.write(chunk_data)
                    
                    chunks.append((chunk_path, chunk_filename))
                    chunk_num += 1
            
            logger.info(f"Split {filename} into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error splitting file: {e}")
            return []
    
    def generate_reassembly_instructions(self, filename: str, num_chunks: int) -> str:
        """Generate instructions for reassembling file chunks"""
        name, ext = os.path.splitext(filename)
        
        instructions = f"""
📋 **File Reassembly Instructions**

Your file "{filename}" has been split into {num_chunks} parts.

**Windows:**
```
copy /b "{name}.part001{ext}"+"{name}.part002{ext}"+... "{filename}"
```

**Linux/Mac:**
```
cat "{name}.part001{ext}" "{name}.part002{ext}" ... > "{filename}"
```

**Alternative:** Use file joining software like HJSplit, 7-Zip, or WinRAR.
        """
        
        return instructions.strip()

    async def split_and_send_file(self, file_path: str, filename: str, file_size: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Split large file and send parts"""
        try:
            # Split the file
            chunks = await self.split_file(file_path, filename)
            
            if not chunks:
                return False
            
            # Send introduction message
            intro_text = f"""
📦 **Splitting Large File**

📁 File: {filename}
📏 Size: {format_file_size(file_size)}
🔢 Parts: {len(chunks)}

Sending parts now...
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=intro_text,
                parse_mode='Markdown'
            )
            
            # Send each chunk
            for i, (chunk_path, chunk_filename) in enumerate(chunks, 1):
                try:
                    chunk_size = os.path.getsize(chunk_path)
                    
                    with open(chunk_path, 'rb') as chunk_file:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=InputFile(chunk_file, filename=chunk_filename),
                            caption=f"📦 Part {i}/{len(chunks)} - {chunk_filename}\n📏 {format_file_size(chunk_size)}",
                            parse_mode='Markdown'
                        )
                    
                    logger.info(f"Sent chunk {i}/{len(chunks)}: {chunk_filename}")
                    
                except Exception as e:
                    logger.error(f"Error sending chunk {i}: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Failed to send part {i}/{len(chunks)}"
                    )
                finally:
                    # Clean up chunk file
                    try:
                        os.remove(chunk_path)
                    except:
                        pass
            
            # Send reassembly instructions
            instructions = self.generate_reassembly_instructions(filename, len(chunks))
            await context.bot.send_message(
                chat_id=chat_id,
                text=instructions,
                parse_mode='Markdown'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error splitting and sending file: {e}")
            return False

    async def download_and_send_file(self, url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Download file from URL and send to Telegram"""
        temp_file_path = None
        
        try:
            # Download file
            temp_file_path, filename, file_size = await self.download_file(url, allow_large_files=True)
            
            if not temp_file_path or not filename or file_size is None:
                return False
            
            # Use hybrid handler for optimal file delivery
            success = await self.hybrid_handler.send_file(chat_id, temp_file_path, filename, context)
            
            if success:
                # Record download in database
                from database import Database
                db = Database()
                db.record_download(user_id, url, filename, file_size)
            
            return success
            
        except ValueError as e:
            # Handle file size or download errors
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Download Error**\n\n{str(e)}",
                parse_mode='Markdown'
            )
            return False
            
        except Exception as e:
            logger.error(f"Error in download_and_send_file: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Download Failed**\n\n"
                     f"Could not download file from URL.\n"
                     f"Please check the URL and try again.\n\n"
                     f"Error: {str(e)}",
                parse_mode='Markdown'
            )
            return False
            
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.debug(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")

    async def download_and_send_file_with_custom_name(self, url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int, custom_filename: str) -> bool:
        """Download file from URL and send to Telegram with custom filename"""
        temp_file_path = None
        
        try:
            # Download file
            temp_file_path, original_filename, file_size = await self.download_file(url, allow_large_files=True)
            
            if not temp_file_path or not original_filename or file_size is None:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **Download Failed**\n\n"
                         f"Could not download file from URL.\n"
                         f"Please check the URL and try again.",
                    parse_mode='Markdown'
                )
                return False
            
            # Use the custom filename provided by user
            from utils import sanitize_filename
            filename = sanitize_filename(custom_filename)
            
            # Use hybrid handler for optimal file delivery
            success = await self.hybrid_handler.send_file(chat_id, temp_file_path, filename, context)
            
            if success:
                # Record download in database with custom filename
                from database import Database
                Database().record_download(user_id, url, filename, file_size)
                logger.info(f"Successfully sent file {filename} (renamed from {original_filename}) to user {user_id}")
                return True
            else:
                logger.error(f"Failed to send file {filename} to user {user_id}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **Upload Failed**\n\n"
                         f"Could not upload file to Telegram.\n"
                         f"The file might be too large or corrupted.",
                    parse_mode='Markdown'
                )
                return False
                
        except Exception as e:
            logger.error(f"Error in download_and_send_file_with_custom_name: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Download Failed**\n\n"
                     f"Could not download file from URL.\n"
                     f"Please check the URL and try again.\n\n"
                     f"Error: {str(e)}",
                parse_mode='Markdown'
            )
            return False
            
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.debug(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.session and not self.session.closed:
            await self.session.close()
        
        # Clean up hybrid handler
        await self.hybrid_handler.cleanup()
        
        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary directory: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # Create new event loop if none exists for cleanup
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.cleanup())
                else:
                    loop.run_until_complete(self.cleanup())
            except:
                pass
