#!/usr/bin/env python3
"""
Telegram File Download Bot with Usage Limits and Referral System - Windows Compatible Version
"""

import logging
import asyncio
import platform
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
        
        # Check if message contains a URL
        if not (message_text.startswith('http://') or message_text.startswith('https://')):
            await update.message.reply_text(
                "❌ Please send a valid URL starting with http:// or https://\n\n"
                "Example: https://example.com/file.pdf"
            )
            return
        
        # Check user's daily limit (skip for admins)
        if not is_admin(user.id):
            today_downloads = self.db.get_today_downloads_count(user.id)
            bonus_downloads = self.db.get_bonus_downloads(user.id)
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
            # Download and send file
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
        
        if not is_admin(query.from_user.id):
            await query.edit_message_text("❌ You don't have admin access.")
            return
        
        await self.admin_handler.handle_callback(update, context)

def main():
    """Main function to run the bot"""
    # Fix for Windows event loop issues
    import asyncio as async_module
    if platform.system() == 'Windows':
        async_module.set_event_loop_policy(async_module.WindowsProactorEventLoopPolicy())
    
    # Check if bot token is provided
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Initialize bot
    bot = TelegramBot()
    
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
    try:
        # Check if we're in an environment with an existing event loop
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # If we get here, there's already a running loop
            logger.warning("Detected running event loop. Using application.initialize() and polling manually.")
            
            # For environments with existing event loops (like Jupyter)
            import threading
            
            def run_bot_in_thread():
                # Create new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(application.initialize())
                    application.run_polling(drop_pending_updates=True)
                except Exception as e:
                    logger.error(f"Error in bot thread: {e}")
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_bot_in_thread, daemon=True)
            thread.start()
            
            # Keep main thread alive
            try:
                thread.join()
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                
        except RuntimeError:
            # No running event loop, we can run normally
            application.run_polling(drop_pending_updates=True)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        
        # Additional error handling for Windows event loop issues
        if "event loop is already running" in str(e).lower():
            logger.info("Attempting alternative startup method...")
            try:
                # Try using nest_asyncio if available
                import nest_asyncio
                nest_asyncio.apply()
                application.run_polling(drop_pending_updates=True)
            except ImportError:
                logger.error("nest_asyncio not available. Please install it: pip install nest-asyncio")
            except Exception as e2:
                logger.error(f"Alternative startup failed: {e2}")

if __name__ == '__main__':
    main()