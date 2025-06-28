"""
Admin panel functionality for the Telegram bot
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timedelta
from typing import List

from database import Database, User
from utils import format_file_size, is_admin

logger = logging.getLogger(__name__)

class AdminHandler:
    def __init__(self, db: Database):
        self.db = db
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin panel"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        # Get basic stats
        stats = self.db.get_user_stats()
        
        admin_text = f"""
🔧 **Admin Panel**

📊 **Statistics:**
• Total Users: {stats['total_users']:,}
• Active Today: {stats['active_today']:,}
• Total Downloads: {stats['total_downloads']:,}
• Downloads Today: {stats['downloads_today']:,}

📅 **Server Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👥 User Stats", callback_data="admin_users"),
                InlineKeyboardButton("📈 Top Users", callback_data="admin_top_users")
            ],
            [
                InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_detailed"),
                InlineKeyboardButton("🧹 Cleanup", callback_data="admin_cleanup")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                admin_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                admin_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    async def show_user_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed user statistics"""
        query = update.callback_query
        
        stats = self.db.get_user_stats()
        
        # Get additional stats
        with self.db.get_connection() as conn:
            # Users registered today
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE date(created_at) = date('now')
            ''')
            new_users_today = cursor.fetchone()['count']
            
            # Users registered this week
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE created_at >= date('now', '-7 days')
            ''')
            new_users_week = cursor.fetchone()['count']
            
            # Average downloads per user
            cursor = conn.execute('''
                SELECT AVG(total_downloads) as avg_downloads FROM users 
                WHERE total_downloads > 0
            ''')
            avg_downloads = cursor.fetchone()['avg_downloads'] or 0
        
        user_stats_text = f"""
👥 **Detailed User Statistics**

📊 **User Growth:**
• Total Users: {stats['total_users']:,}
• New Today: {new_users_today:,}
• New This Week: {new_users_week:,}
• Active Today: {stats['active_today']:,}

📈 **Download Activity:**
• Total Downloads: {stats['total_downloads']:,}
• Downloads Today: {stats['downloads_today']:,}
• Avg Downloads/User: {avg_downloads:.1f}

🔗 **Referral System:**
• Total Referrals: {self._get_total_referrals():,}
• Active Bonuses: {self._get_active_bonuses():,}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_refresh")]
        ]
        
        await query.edit_message_text(
            user_stats_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_top_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top users by download count"""
        query = update.callback_query
        
        top_users = self.db.get_top_users(10)
        
        if not top_users:
            top_users_text = "📊 **Top Users**\n\nNo users found."
        else:
            top_users_text = "📊 **Top Users by Downloads**\n\n"
            
            for i, user in enumerate(top_users, 1):
                username = f"@{user.username}" if user.username else "No username"
                name = user.first_name or "No name"
                last_active = user.last_active.strftime('%Y-%m-%d')
                
                top_users_text += f"{i}. **{name}** ({username})\n"
                top_users_text += f"   📥 {user.total_downloads:,} downloads\n"
                top_users_text += f"   📅 Last active: {last_active}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_refresh")]
        ]
        
        await query.edit_message_text(
            top_users_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_detailed_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed system statistics"""
        query = update.callback_query
        
        with self.db.get_connection() as conn:
            # File size statistics
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_files,
                    COALESCE(AVG(file_size), 0) as avg_size,
                    COALESCE(SUM(file_size), 0) as total_size,
                    COALESCE(MAX(file_size), 0) as max_size
                FROM downloads 
                WHERE file_size > 0
            ''')
            file_stats = cursor.fetchone()
            
            # Download trends (last 7 days)
            cursor = conn.execute('''
                SELECT 
                    date(created_at) as download_date,
                    COUNT(*) as count
                FROM downloads 
                WHERE created_at >= date('now', '-7 days')
                GROUP BY date(created_at)
                ORDER BY download_date DESC
            ''')
            daily_downloads = cursor.fetchall()
            
            # Most popular file extensions
            cursor = conn.execute('''
                SELECT 
                    CASE 
                        WHEN filename LIKE '%.%' THEN 
                            LOWER(SUBSTR(filename, LENGTH(filename) - INSTR(REVERSE(filename), '.') + 2))
                        ELSE 'no_extension'
                    END as extension,
                    COUNT(*) as count
                FROM downloads 
                WHERE filename != ''
                GROUP BY extension
                ORDER BY count DESC
                LIMIT 5
            ''')
            extensions = cursor.fetchall()
        
        detailed_text = f"""
📈 **Detailed System Statistics**

💾 **File Statistics:**
• Total Files: {file_stats['total_files']:,}
• Total Size: {format_file_size(file_stats['total_size'])}
• Average Size: {format_file_size(file_stats['avg_size'])}
• Largest File: {format_file_size(file_stats['max_size'])}

📅 **Download Trends (Last 7 Days):**
"""
        
        for day in daily_downloads:
            date_str = datetime.strptime(day['download_date'], '%Y-%m-%d').strftime('%m-%d')
            detailed_text += f"• {date_str}: {day['count']:,} downloads\n"
        
        if extensions:
            detailed_text += "\n🗂️ **Popular File Types:**\n"
            for ext in extensions:
                extension = ext['extension'] if ext['extension'] != 'no_extension' else 'No extension'
                detailed_text += f"• {extension}: {ext['count']:,}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_refresh")]
        ]
        
        await query.edit_message_text(
            detailed_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def perform_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Perform system cleanup"""
        query = update.callback_query
        
        # Clean up expired referral bonuses
        self.db.cleanup_expired_bonuses()
        
        cleanup_text = f"""
🧹 **System Cleanup Completed**

✅ **Tasks Performed:**
• Cleaned up expired referral bonuses
• Database maintenance completed

📅 **Cleanup Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

The system is now optimized for better performance.
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_refresh")]
        ]
        
        await query.edit_message_text(
            cleanup_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_broadcast_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show broadcast message panel"""
        query = update.callback_query
        
        broadcast_text = """
📢 **Broadcast Message**

Send a message to all users who have used the bot.

⚠️ **Warning:** This will send a message to ALL users in the database. Use responsibly.

📝 Reply to this message with the text you want to broadcast.

**Example:**
🎉 New feature available! Now supporting files up to 2GB with improved MTProto integration!
        """
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_refresh")]
        ]
        
        # Store that admin is in broadcast mode
        context.user_data['awaiting_broadcast'] = True
        
        await query.edit_message_text(
            broadcast_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
        """Handle the actual broadcast message"""
        if not is_admin(update.effective_user.id):
            return
        
        # Get all user IDs
        user_ids = self.db.get_all_user_ids()
        
        if not user_ids:
            await update.message.reply_text("❌ No users found in the database.")
            return
        
        # Send progress message
        progress_msg = await update.message.reply_text(
            f"📢 Starting broadcast to {len(user_ids):,} users...\n⏳ Progress: 0/{len(user_ids)}"
        )
        
        successful = 0
        failed = 0
        
        # Broadcast to all users
        for i, user_id in enumerate(user_ids):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 **Admin Broadcast**\n\n{message_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                successful += 1
            except Exception as e:
                failed += 1
                print(f"Failed to send to {user_id}: {e}")
            
            # Update progress every 10 users or at the end
            if (i + 1) % 10 == 0 or i == len(user_ids) - 1:
                try:
                    await progress_msg.edit_text(
                        f"📢 Broadcasting progress...\n"
                        f"✅ Sent: {successful:,}\n"
                        f"❌ Failed: {failed:,}\n"
                        f"⏳ Progress: {i + 1}/{len(user_ids):,}"
                    )
                except:
                    pass  # Ignore edit failures
        
        # Final summary
        summary_text = f"""
📢 **Broadcast Complete!**

✅ **Successfully sent:** {successful:,}
❌ **Failed:** {failed:,}
📊 **Total users:** {len(user_ids):,}
📅 **Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """
        
        await update.message.reply_text(summary_text, parse_mode=ParseMode.MARKDOWN)
        
        # Clear broadcast mode
        context.user_data.pop('awaiting_broadcast', None)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        data = query.data
        
        if data == "admin_refresh":
            await self.show_admin_panel(update, context)
        elif data == "admin_users":
            await self.show_user_stats(update, context)
        elif data == "admin_top_users":
            await self.show_top_users(update, context)
        elif data == "admin_detailed":
            await self.show_detailed_stats(update, context)
        elif data == "admin_cleanup":
            await self.perform_cleanup(update, context)
        elif data == "admin_broadcast":
            await self.show_broadcast_panel(update, context)
    
    def _get_total_referrals(self) -> int:
        """Get total number of referrals"""
        with self.db.get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) as count FROM referrals')
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def _get_active_bonuses(self) -> int:
        """Get number of active referral bonuses"""
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM referrals 
                WHERE bonus_expires_at > datetime('now')
            ''')
            result = cursor.fetchone()
            return result['count'] if result else 0
