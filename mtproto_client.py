"""
MTProto API client for handling large files up to 2GB
Uses Pyrogram library for native Telegram MTProto implementation
"""

import os
import logging
import asyncio
from typing import Optional, Tuple
import tempfile
from pathlib import Path

try:
    from pyrogram import Client, filters
    from pyrogram.types import Message
    from pyrogram.errors import FloodWait, FilePartMissing
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False

from config import BOT_TOKEN, ADMIN_IDS
from utils import format_file_size, sanitize_filename, get_filename_from_url
from database import Database

logger = logging.getLogger(__name__)

class MTProtoFileHandler:
    """
    MTProto client for handling large file uploads up to 2GB
    This bypasses the Bot API 50MB limitation
    """
    
    def __init__(self):
        self.app = None
        self.db = Database()
        self.temp_dir = tempfile.mkdtemp(prefix='mtproto_bot_')
        
        if not PYROGRAM_AVAILABLE:
            logger.warning("Pyrogram not installed. Large file support (2GB) disabled.")
            logger.info("Install with: pip install pyrogram")
            return
            
        self._init_client()
    
    def _init_client(self):
        """Initialize MTProto client"""
        try:
            # Extract bot credentials from BOT_TOKEN
            if not BOT_TOKEN:
                logger.error("BOT_TOKEN required for MTProto client")
                return
                
            # For MTProto, we need API credentials
            # These would normally come from https://my.telegram.org
            api_id = os.getenv('TELEGRAM_API_ID')
            api_hash = os.getenv('TELEGRAM_API_HASH')
            
            if not api_id or not api_hash:
                logger.warning("TELEGRAM_API_ID and TELEGRAM_API_HASH required for 2GB file support")
                logger.info("Get these from https://my.telegram.org/apps")
                return
            
            # Create Pyrogram client
            self.app = Client(
                "large_file_bot",
                api_id=int(api_id),
                api_hash=api_hash,
                bot_token=BOT_TOKEN,
                workdir=self.temp_dir
            )
            
            logger.info("MTProto client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MTProto client: {e}")
    
    async def start_client(self):
        """Start the MTProto client"""
        if self.app and PYROGRAM_AVAILABLE:
            try:
                await self.app.start()
                logger.info("MTProto client started")
                return True
            except Exception as e:
                logger.error(f"Failed to start MTProto client: {e}")
                return False
        return False
    
    async def stop_client(self):
        """Stop the MTProto client"""
        if self.app and PYROGRAM_AVAILABLE:
            try:
                await self.app.stop()
                logger.info("MTProto client stopped")
            except Exception as e:
                logger.error(f"Error stopping MTProto client: {e}")
    
    async def send_large_document(self, chat_id: int, file_path: str, filename: str, progress_callback=None) -> bool:
        """
        Send large document using MTProto (up to 2GB)
        
        Args:
            chat_id: Telegram chat ID
            file_path: Path to the file
            filename: Original filename
            progress_callback: Optional callback for upload progress
            
        Returns:
            bool: Success status
        """
        if not self.app or not PYROGRAM_AVAILABLE:
            logger.error("MTProto client not available")
            return False
        
        # Ensure client is started
        if not self.app.is_connected:
            try:
                await self.app.start()
                logger.info("MTProto client started for file upload")
            except Exception as e:
                logger.error(f"Failed to start MTProto client: {e}")
                return False
            
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading large file via MTProto: {filename} ({format_file_size(file_size)})")
            
            # Ensure we have a valid chat - try to get chat info first
            try:
                chat = await self.app.get_chat(chat_id)
                logger.info(f"Chat verified: {chat.title if hasattr(chat, 'title') else chat_id}")
            except Exception as e:
                logger.warning(f"Could not verify chat {chat_id}: {e}")
                # Continue anyway - might still work
            
            # Send document with progress tracking
            # Note: Progress callback temporarily disabled to avoid TypeError
            message = await self.app.send_document(
                chat_id=chat_id,
                document=file_path,
                file_name=filename,
                caption=f"📁 **{filename}**\n📏 Size: {format_file_size(file_size)}\n🚀 Uploaded via MTProto"
            )
            
            if message:
                logger.info(f"Successfully sent large file: {filename}")
                return True
            else:
                logger.error(f"Failed to send large file: {filename}")
                return False
                
        except FloodWait as e:
            logger.warning(f"Rate limited, waiting {e.value} seconds")
            await asyncio.sleep(e.value)
            return await self.send_large_document(chat_id, file_path, filename, progress_callback)
            
        except FilePartMissing as e:
            logger.error(f"File part missing: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Error sending large document: {e}")
            return False
    
    async def progress_callback(self, current: int, total: int, chat_id: int, message_id: int):
        """Progress callback for large file uploads"""
        try:
            percent = (current / total) * 100
            
            # Update progress every 10%
            if percent % 10 < 1:
                progress_text = f"⬆️ Uploading: {percent:.1f}% ({format_file_size(current)}/{format_file_size(total)})"
                
                await self.app.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=progress_text
                )
                
        except Exception as e:
            logger.debug(f"Progress update error: {e}")
    
    def is_available(self) -> bool:
        """Check if MTProto client is available and configured"""
        return (PYROGRAM_AVAILABLE and 
                self.app is not None and 
                os.getenv('TELEGRAM_API_ID') and 
                os.getenv('TELEGRAM_API_HASH'))

class HybridFileHandler:
    """
    Hybrid file handler that uses Bot API for small files and MTProto for large files
    """
    
    def __init__(self):
        self.mtproto = MTProtoFileHandler()
        self.bot_api_limit = 50 * 1024 * 1024  # 50MB
        
    async def initialize(self):
        """Initialize the hybrid handler"""
        if self.mtproto.is_available():
            await self.mtproto.start_client()
            logger.info("Hybrid handler: MTProto available for 2GB files")
        else:
            logger.info("Hybrid handler: Bot API only (50MB limit)")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.mtproto:
            await self.mtproto.stop_client()
    
    async def send_file(self, chat_id: int, file_path: str, filename: str, context=None) -> bool:
        """
        Send file using the best available method
        
        Args:
            chat_id: Telegram chat ID
            file_path: Path to the file
            filename: Original filename
            context: Bot API context (if using Bot API)
            
        Returns:
            bool: Success status
        """
        try:
            file_size = os.path.getsize(file_path)
            
            # Choose method based on file size and availability
            if file_size <= self.bot_api_limit:
                # Use Bot API for small files
                logger.info(f"Using Bot API for file: {filename} ({format_file_size(file_size)})")
                return await self._send_via_bot_api(chat_id, file_path, filename, context)
            
            elif self.mtproto.is_available():
                # Use MTProto for large files
                logger.info(f"Using MTProto for large file: {filename} ({format_file_size(file_size)})")
                
                # Send progress message first
                if context:
                    progress_msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⬆️ Uploading large file: {filename}\n📏 Size: {format_file_size(file_size)}\n🚀 Using MTProto for 2GB support"
                    )
                    
                    # Create progress callback
                    async def progress(current, total):
                        await self.mtproto.progress_callback(current, total, chat_id, progress_msg.message_id)
                    
                    success = await self.mtproto.send_large_document(chat_id, file_path, filename, progress)
                    
                    # Delete progress message after upload
                    try:
                        await context.bot.delete_message(chat_id, progress_msg.message_id)
                    except:
                        pass
                    
                    return success
                else:
                    return await self.mtproto.send_large_document(chat_id, file_path, filename)
            
            else:
                # MTProto not available, suggest file splitting
                if context:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ **File too large**: {filename}\n"
                             f"📏 Size: {format_file_size(file_size)}\n"
                             f"📋 Limit: {format_file_size(self.bot_api_limit)}\n\n"
                             f"💡 **To enable 2GB support:**\n"
                             f"1. Get API credentials from https://my.telegram.org/apps\n"
                             f"2. Set TELEGRAM_API_ID and TELEGRAM_API_HASH\n"
                             f"3. Install: pip install pyrogram",
                        parse_mode='Markdown'
                    )
                return False
                
        except Exception as e:
            logger.error(f"Error in hybrid file handler: {e}")
            return False
    
    async def _send_via_bot_api(self, chat_id: int, file_path: str, filename: str, context) -> bool:
        """Send file via Bot API"""
        try:
            if not context:
                return False
                
            from telegram import InputFile
            
            with open(file_path, 'rb') as file:
                file_size = os.path.getsize(file_path)
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(file, filename=filename),
                    caption=f"📁 **{filename}**\n📏 Size: {format_file_size(file_size)}",
                    parse_mode='Markdown'
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Bot API send failed: {e}")
            return False