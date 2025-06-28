#!/usr/bin/env python3
"""
Telegram File Download Bot with Usage Limits and Referral System
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import os
from datetime import datetime, timedelta

from config import BOT_TOKEN, ADMIN_IDS, MAX_DAILY_DOWNLOADS, MAX_FILE_SIZE
from database import Database, User
from file_handler import FileHandler
from admin import AdminHandler
from referral import ReferralHandler
from utils import format_file_size, is_admin

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.file_handler = FileHandler()
        self.admin_handler = AdminHandler(self.db)
        self.referral_handler = ReferralHandler(self.db)
        
    async def initialize(self):
        """Initialize the bot components"""
        await self.file_handler.initialize()
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Register user in database
        self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        # Check if user was referred
        if context.args:
            referrer_id = context.args[0]
            try:
                referrer_id = int(referrer_id)
                if referrer_id != user.id:
                    self.referral_handler.process_referral(referrer_id, user.id)
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text="🎉 Someone used your referral link! You've received a bonus download for today."
                    )
            except ValueError:
                pass
        
        welcome_text = f"""
🤖 **Welcome to File Download Bot!**

Hi {user.first_name}! I can help you download files from the internet.

📋 **How to use:**
• Send me any file URL to download
• Maximum file size: {format_file_size(MAX_FILE_SIZE)}
• Daily limit: {MAX_DAILY_DOWNLOADS} files per day

🔗 **Need more downloads?**
• Use /referral to get your referral link
• Each friend who joins gives you +1 download for 24 hours

📊 **Commands:**
• /status - Check your usage
• /referral - Get your referral link
• /help - Show this message

Just send me a URL to get started! 🚀
        """
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await self.start_command(update, context)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show user's download status"""
        user = update.effective_user
        db_user = self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        today_downloads = self.db.get_today_downloads_count(user.id)
        bonus_downloads = self.db.get_bonus_downloads(user.id)
        total_limit = MAX_DAILY_DOWNLOADS + bonus_downloads
        
        status_text = f"""
📊 **Your Download Status**

👤 User: {user.first_name}
📅 Today's Downloads: {today_downloads}/{total_limit}
🎁 Bonus Downloads: {bonus_downloads}
📈 Total Downloads: {db_user.total_downloads}

⏰ Daily limit resets at midnight UTC
        """
        
        if bonus_downloads > 0:
            # Find the earliest bonus expiry
            bonus_expiry = self.db.get_earliest_bonus_expiry(user.id)
            if bonus_expiry:
                status_text += f"\n🕐 Bonus expires: {bonus_expiry.strftime('%Y-%m-%d %H:%M UTC')}"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command"""
        user = update.effective_user
        self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        referral_link = self.referral_handler.generate_referral_link(user.id)
        referral_count = self.db.get_referral_count(user.id)
        
        referral_text = f"""
🔗 **Your Referral Link**

Share this link with friends to earn bonus downloads:
`{referral_link}`

📊 **Referral Stats:**
• Friends referred: {referral_count}
• Bonus per referral: +1 download for 24 hours

💡 **How it works:**
1. Share your link with friends
2. When they join using your link, you both benefit
3. You get +1 download for the next 24 hours
4. No limit on referrals!
        """
        
        await update.message.reply_text(referral_text, parse_mode=ParseMode.MARKDOWN)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user = update.effective_user
        
        if not is_admin(user.id):
            await update.message.reply_text("❌ You don't have admin access.")
            return
        
        await self.admin_handler.show_admin_panel(update, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages (file URLs)"""
        user = update.effective_user
        message_text = update.message.text.strip()
        
        # Register user
        self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        # Check if admin is in broadcast mode
        if is_admin(user.id) and context.user_data.get('awaiting_broadcast'):
            await self.admin_handler.handle_broadcast_message(update, context, message_text)
            return
        
        # Check if user is in rename mode
        if context.user_data.get('awaiting_rename'):
            url = context.user_data.get('rename_url')
            if url:
                # Clean the user data
                context.user_data.pop('awaiting_rename', None)
                context.user_data.pop('rename_url', None)
                
                # Use the new filename provided by user
                new_filename = message_text.strip()
                
                # Send processing message
                processing_msg = await update.message.reply_text("⏳ Downloading with new filename...")
                
                try:
                    # Download file with custom filename
                    success = await self.file_handler.download_and_send_file_with_custom_name(
                        url=url,
                        chat_id=update.effective_chat.id,
                        context=context,
                        user_id=user.id,
                        custom_filename=new_filename
                    )
                    
                    if success:
                        # Get remaining downloads
                        today_downloads = self.db.get_today_downloads_count(user.id)
                        from config import MAX_DAILY_DOWNLOADS
                        remaining = max(0, MAX_DAILY_DOWNLOADS - today_downloads)
                        
                        await processing_msg.edit_text(
                            f"✅ **File Downloaded Successfully!**\n\n"
                            f"📝 **Filename:** {new_filename}\n"
                            f"Downloads remaining today: {remaining}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await processing_msg.edit_text("❌ Failed to download file with new filename.")
                        
                except Exception as e:
                    logger.error(f"Error processing renamed download: {e}")
                    await processing_msg.edit_text(f"❌ Error: {str(e)}")
                
                return
            else:
                # Reset if no URL found
                context.user_data.pop('awaiting_rename', None)
                context.user_data.pop('rename_url', None)
        
        # Check if message contains a URL
        if not (message_text.startswith('http://') or message_text.startswith('https://')):
            # If user is admin and just sent broadcast message, don't show URL error
            if is_admin(user.id):
                await update.message.reply_text(
                    "❌ Please send a valid URL starting with http:// or https://\n\n"
                    "Example: https://example.com/file.pdf\n\n"
                    "Or use /admin to access admin panel for broadcasting."
                )
            else:
                await update.message.reply_text(
                    "❌ Please send a valid URL starting with http:// or https://\n\n"
                    "Example: https://example.com/file.pdf"
                )
            return
        
        # Check user's daily limit (skip for admins)
        if not is_admin(user.id):
            today_downloads = self.db.get_today_downloads_count(user.id)
            bonus_downloads = self.db.get_bonus_downloads(user.id)
            from config import MAX_DAILY_DOWNLOADS
            total_limit = MAX_DAILY_DOWNLOADS + bonus_downloads
            
            if today_downloads >= total_limit:
                await update.message.reply_text(
                    f"❌ **Daily limit reached!**\n\n"
                    f"You've used {today_downloads}/{total_limit} downloads today.\n"
                    f"• Limit resets at midnight UTC\n"
                    f"• Get more downloads with /referral",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        # Send processing message
        processing_msg = await update.message.reply_text("⏳ Processing your request...")
        
        try:
            # Get file info first to show preview with rename option
            filename, file_size = await self.file_handler.get_file_info(message_text)
            
            if filename and file_size:
                # Create a hash of the URL to avoid callback data length issues
                import hashlib
                url_hash = hashlib.md5(message_text.encode()).hexdigest()[:16]
                
                # Store the URL in user data with the hash as key
                if 'url_cache' not in context.user_data:
                    context.user_data['url_cache'] = {}
                context.user_data['url_cache'][url_hash] = message_text
                
                # Update processing message with file info and rename option
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
                    url=message_text,
                    chat_id=update.effective_chat.id,
                    context=context,
                    user_id=user.id
                )
            
            if success:
                # Record the download
                self.db.record_download(user.id, message_text)
                
                # Update processing message
                remaining = MAX_DAILY_DOWNLOADS + self.db.get_bonus_downloads(user.id) - self.db.get_today_downloads_count(user.id)
                await processing_msg.edit_text(
                    f"✅ **File sent successfully!**\n\n"
                    f"Downloads remaining today: {remaining}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await processing_msg.edit_text("❌ Failed to download file. Please check the URL and try again.")
                
        except Exception as e:
            logger.error(f"Error processing download: {e}")
            await processing_msg.edit_text(f"❌ Error: {str(e)}")
    
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

async def main():
    """Main function to run the bot"""
    # Check if bot token is provided
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Initialize bot
    bot = TelegramBot()
    await bot.initialize()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("referral", bot.referral_command))
    application.add_handler(CommandHandler("admin", bot.admin_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    logger.info("Starting Telegram bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        # Keep the bot running
        import signal
        stop = asyncio.Event()
        
        def signal_handler(signum, frame):
            logger.info("Received stop signal")
            stop.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        await stop.wait()
    finally:
        logger.info("Shutting down...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def run_bot():
    """Run the bot with proper event loop handling"""
    import platform
    if platform.system() == 'Windows':
        # Fix for Windows event loop issues
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        # Try to get the running loop
        asyncio.get_running_loop()
        logger.info("Event loop already running, using nest_asyncio")
        
        # Install nest_asyncio if needed
        try:
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(main())
        except ImportError:
            logger.error("nest_asyncio not available. Please install it: pip install nest-asyncio")
            
    except RuntimeError:
        # No event loop running, create one
        logger.info("No event loop running, creating new one")
        asyncio.run(main())

if __name__ == '__main__':
    run_bot()
