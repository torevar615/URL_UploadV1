#!/usr/bin/env python3
"""
Telegram File Download Bot with Usage Limits and Referral System - Windows Compatible Version
"""

import asyncio
import os
import sys
import logging
from typing import Optional
import signal
import platform

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Local imports
from database import Database
from file_handler import FileHandler
from admin import AdminHandler
from referral import ReferralHandler
from utils import is_admin, extract_urls_from_text, format_file_size, sanitize_filename
from config import BOT_TOKEN, MAX_DAILY_DOWNLOADS, ADMIN_IDS

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.file_handler = FileHandler()
        self.admin_handler = AdminHandler(self.db)
        self.referral_handler = ReferralHandler(self.db)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        if not user:
            return

        # Check for referral code
        referral_code = None
        if context.args:
            referral_code = context.args[0]

        # Get or create user
        db_user = self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        # Process referral if present
        if referral_code and referral_code.startswith('ref_'):
            try:
                referrer_id = int(referral_code[4:])
                if self.referral_handler.process_referral(referrer_id, user.id):
                    await update.message.reply_text(
                        f"🎉 Welcome {user.first_name}!\n\n"
                        f"You've been referred by someone awesome! "
                        f"Both of you get bonus downloads. 🚀"
                    )
                else:
                    await update.message.reply_text(f"👋 Welcome back, {user.first_name}!")
            except ValueError:
                await update.message.reply_text(f"👋 Welcome, {user.first_name}!")
        else:
            await update.message.reply_text(f"👋 Welcome, {user.first_name}!")

        # Show usage info
        downloads_today = self.db.get_today_downloads_count(user.id)
        bonus_downloads = self.db.get_bonus_downloads(user.id)
        remaining = MAX_DAILY_DOWNLOADS + bonus_downloads - downloads_today
        
        await update.message.reply_text(
            f"📁 **File Download Bot**\n\n"
            f"Send me any file URL and I'll download it for you!\n\n"
            f"📊 **Your Status:**\n"
            f"• Downloads today: {downloads_today}\n"
            f"• Bonus downloads: {bonus_downloads}\n"
            f"• Remaining today: {remaining}\n\n"
            f"💡 Use /referral to get more downloads\n"
            f"📋 Use /help for more commands",
            parse_mode=ParseMode.MARKDOWN
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🤖 **Bot Commands:**\n\n"
            "📁 **File Downloads:**\n"
            "• Send any file URL to download\n"
            "• Supports files up to 2GB\n"
            "• Daily limit: 5 files + bonuses\n\n"
            "📊 **Commands:**\n"
            "• /start - Welcome message\n"
            "• /help - Show this help\n"
            "• /status - Check your download status\n"
            "• /referral - Get referral link for bonuses\n\n"
            "🔗 **Supported Sites:**\n"
            "• Direct download links\n"
            "• Cloud storage services\n"
            "• File hosting sites\n\n"
            "⚡ **Features:**\n"
            "• File renaming\n"
            "• Progress tracking\n"
            "• Large file support (up to 2GB)"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show user's download status"""
        user = update.effective_user
        if not user:
            return

        db_user = self.db.get_or_create_user(user.id, user.username, user.first_name)
        downloads_today = self.db.get_today_downloads_count(user.id)
        bonus_downloads = self.db.get_bonus_downloads(user.id)
        remaining = MAX_DAILY_DOWNLOADS + bonus_downloads - downloads_today
        
        # Get referral stats
        referral_stats = self.referral_handler.get_referral_stats(user.id)
        
        status_text = (
            f"📊 **Your Download Status**\n\n"
            f"👤 **User:** {user.first_name}\n"
            f"📁 **Today's Downloads:** {downloads_today}/{MAX_DAILY_DOWNLOADS}\n"
            f"🎁 **Bonus Downloads:** {bonus_downloads}\n"
            f"⚡ **Remaining Today:** {remaining}\n"
            f"📈 **Total Downloads:** {db_user.total_downloads}\n\n"
            f"🔗 **Referral Stats:**\n"
            f"• Successful referrals: {referral_stats['total_referrals']}\n"
            f"• Active bonuses: {referral_stats['active_bonuses']}\n\n"
            f"💡 Use /referral to get more downloads!"
        )
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command"""
        await self.referral_handler.show_referral_info(update, context)

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user = update.effective_user
        if not user or not is_admin(user.id):
            await update.message.reply_text("❌ You don't have admin access.")
            return
        
        await self.admin_handler.show_admin_panel(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages (file URLs)"""
        user = update.effective_user
        message_text = update.message.text.strip()
        
        if not user or not message_text:
            return

        # Check if user is waiting to rename a file
        if context.user_data.get('awaiting_rename'):
            # User is providing a new filename
            url = context.user_data.pop('rename_url', None)
            context.user_data.pop('awaiting_rename', None)
            
            if not url:
                await update.message.reply_text("❌ Error: No file URL found. Please try again.")
                return
                
            # Use the message text as the custom filename
            custom_filename = sanitize_filename(message_text)
            
            # Get or create user
            db_user = self.db.get_or_create_user(user.id, user.username, user.first_name)
            
            # Check download limits
            downloads_today = self.db.get_today_downloads_count(user.id)
            bonus_downloads = self.db.get_bonus_downloads(user.id)
            daily_limit = MAX_DAILY_DOWNLOADS + bonus_downloads
            
            if downloads_today >= daily_limit:
                await update.message.reply_text(
                    f"❌ **Daily limit reached!**\n\n"
                    f"You've used all {daily_limit} downloads today.\n"
                    f"• Get more with /referral\n"
                    f"• Or try again tomorrow",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text("⏳ Processing your request...")
            
            # Download and send file with custom name
            success = await self.file_handler.download_and_send_file_with_custom_name(
                url=url,
                chat_id=update.effective_chat.id,
                context=context,
                user_id=user.id,
                custom_filename=custom_filename
            )
            
            if success:
                # Record the download
                self.db.record_download(user.id, url, custom_filename)
                
                # Update processing message
                remaining = MAX_DAILY_DOWNLOADS + self.db.get_bonus_downloads(user.id) - self.db.get_today_downloads_count(user.id)
                await processing_msg.edit_text(
                    f"✅ **File sent successfully!**\n\n"
                    f"📝 **Filename:** {custom_filename}\n"
                    f"Downloads remaining today: {remaining}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await processing_msg.edit_text("❌ **Download failed.** Please check the URL and try again.")
            
            return

        # Extract URLs from message
        urls = extract_urls_from_text(message_text)
        if not urls:
            await update.message.reply_text(
                "❌ **No valid URL found.**\n\n"
                "Please send a direct download URL.\n"
                "Use /help for more information."
            )
            return

        url = urls[0]  # Use the first URL found
        
        # Get or create user
        db_user = self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        # Check download limits
        downloads_today = self.db.get_today_downloads_count(user.id)
        bonus_downloads = self.db.get_bonus_downloads(user.id)
        daily_limit = MAX_DAILY_DOWNLOADS + bonus_downloads
        
        if downloads_today >= daily_limit:
            await update.message.reply_text(
                f"❌ **Daily limit reached!**\n\n"
                f"You've used all {daily_limit} downloads today.\n"
                f"• Get more with /referral\n"
                f"• Or try again tomorrow",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Show processing message
        processing_msg = await update.message.reply_text("⏳ Processing your request...")
        
        try:
            # Try to get file info first for rename option
            filename, file_size = await self.file_handler.get_file_info(url)
            
            if filename and file_size:
                # Create a hash of the URL to avoid callback data length issues
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
                
                # Store the URL in user data with the hash as key
                if 'url_cache' not in context.user_data:
                    context.user_data['url_cache'] = {}
                context.user_data['url_cache'][url_hash] = url
                
                # Show file info with download/rename options
                keyboard = [
                    [InlineKeyboardButton("📥 Download Now", callback_data=f"download:{url_hash}")],
                    [InlineKeyboardButton("✏️ Rename & Download", callback_data=f"rename:{url_hash}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_msg.edit_text(
                    f"📄 **File Found**\n\n"
                    f"📝 **Name:** {filename}\n"
                    f"📏 **Size:** {format_file_size(file_size)}\n\n"
                    f"Choose an option:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                return
            else:
                # If file info not available, proceed with direct download
                success = await self.file_handler.download_and_send_file(
                    url=url,
                    chat_id=update.effective_chat.id,
                    context=context,
                    user_id=user.id
                )
            
            if success:
                # Record the download
                self.db.record_download(user.id, url)
                
                # Update processing message
                remaining = MAX_DAILY_DOWNLOADS + self.db.get_bonus_downloads(user.id) - self.db.get_today_downloads_count(user.id)
                await processing_msg.edit_text(
                    f"✅ **File sent successfully!**\n\n"
                    f"Downloads remaining today: {remaining}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await processing_msg.edit_text("❌ **Download failed.** Please check the URL and try again.")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await processing_msg.edit_text("❌ **An error occurred.** Please try again later.")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()

        try:
            # Handle file download callbacks
            if query.data.startswith('download:'):
                url_hash = query.data[9:]  # Remove 'download:' prefix
                user = query.from_user
                
                # Retrieve URL from cache
                url = context.user_data.get('url_cache', {}).get(url_hash)
                if not url:
                    await query.edit_message_text("❌ URL not found. Please try again.")
                    return
                
                # Update message to show downloading
                await query.edit_message_text(
                    "⏳ Downloading file...",
                    reply_markup=None
                )
                
                # Download and send file
                success = await self.file_handler.download_and_send_file(
                    url=url,
                    chat_id=query.message.chat_id,
                    context=context,
                    user_id=user.id
                )
                
                if success:
                    await query.edit_message_text("✅ File downloaded successfully!")
                else:
                    await query.edit_message_text("❌ Failed to download file.")
                
                return
            
            # Handle file rename callbacks
            elif query.data.startswith('rename:'):
                url_hash = query.data[7:]  # Remove 'rename:' prefix
                
                # Retrieve URL from cache
                url = context.user_data.get('url_cache', {}).get(url_hash)
                if not url:
                    await query.edit_message_text("❌ URL not found. Please try again.")
                    return
                
                # Store URL for later use
                context.user_data['rename_url'] = url
                context.user_data['awaiting_rename'] = True
                
                await query.edit_message_text(
                    "✏️ **Rename File**\n\nPlease send the new filename:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=None
                )
                
                return
            
            # Handle admin panel callbacks
            if not is_admin(query.from_user.id):
                await query.edit_message_text("❌ You don't have admin access.")
                return
            
            await self.admin_handler.handle_callback(update, context)
            
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await query.edit_message_text("❌ An error occurred. Please try again.")
            return

async def run_bot():
    """Async function to run the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set your bot token in the environment variables.")
        return

    logger.info("Starting Telegram bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Create bot instance
    bot = TelegramBot()

    # Initialize file handler
    await bot.file_handler.initialize()
    logger.info("Bot initialized successfully")

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("referral", bot.referral_command))
    application.add_handler(CommandHandler("admin", bot.admin_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))

    try:
        # Initialize and start the application
        await application.initialize()
        await application.start()
        
        # Start polling
        logger.info("Starting bot polling...")
        await application.updater.start_polling()
        
        # Keep running until interrupted
        import signal
        stop_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            logger.info("Received stop signal")
            stop_event.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        await stop_event.wait()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        logger.info("Shutting down...")
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except:
            pass
        logger.info("Bot stopped.")

def main():
    """Main function to run the bot"""
    # Set Windows event loop policy
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        # Run the async bot function
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        
        # Try with nest_asyncio for environments with existing event loops
        try:
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(run_bot())
        except ImportError:
            logger.error("nest_asyncio not available. Install it with: pip install nest-asyncio")
        except Exception as e2:
            logger.error(f"Alternative startup failed: {e2}")

if __name__ == '__main__':
    main()