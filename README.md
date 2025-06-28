# Telegram File Download Bot

A Telegram bot that downloads files from URLs with usage limits, referral system, and admin management tools.

## Features

- **File Downloads**: Download files up to 50MB from any URL (Telegram's limit)
- **Usage Limits**: 5 downloads per day per user (configurable)
- **Referral System**: Users can get bonus downloads by referring friends
- **Admin Panel**: Complete management interface with statistics
- **Database**: SQLite database for user and download tracking

## Local Setup

### Prerequisites

- Python 3.11 or higher
- A Telegram bot token from @BotFather

### Installation

1. Clone or download this project
2. Install required packages:
   ```bash
   pip install python-telegram-bot aiohttp
   ```

3. Get a Telegram bot token:
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow the instructions
   - Copy the token you receive

4. Set up environment variables:

   **Option 1: Create a .env file**
   ```bash
   BOT_TOKEN=your_bot_token_here
   ADMIN_IDS=your_telegram_user_id
   BOT_USERNAME=your_bot_username
   ```

   **Option 2: Set environment variables directly**
   ```bash
   # Windows
  # Telegram Bot Configuration - Copy to .env and fill in your details

# Required: Get from @BotFather on Telegram
BOT_TOKEN=

# Required: Your Telegram user ID (get from @userinfobot)
ADMIN_IDS=

# Required: Your bot's username (without @)
BOT_USERNAME=@metaurlupbot

# Optional: Customize bot behavior
MAX_DAILY_DOWNLOADS=5
MAX_FILE_SIZE=2147483648
DATABASE_PATH=bot_database.db
DOWNLOAD_TIMEOUT=300
REFERRAL_BONUS_DURATION_HOURS=24
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

   # Linux/Mac
   export BOT_TOKEN=your_bot_token_here
   export ADMIN_IDS=your_telegram_user_id
   export BOT_USERNAME=your_bot_username
   ```

5. Run the bot:
   
   **For Windows users (recommended):**
   ```bash
   python main_windows.py
or
   **python main_windows_fixed.py**
   ```
   
   **For other platforms:**
   ```bash
   python main.py
   ```
   
   **Or use the local runner:**
   ```bash
   python run_local.py
   ```

### Configuration Options

You can customize the bot by setting these environment variables:

- `BOT_TOKEN`: Your Telegram bot token (required)
- `ADMIN_IDS`: Comma-separated list of admin user IDs
- `BOT_USERNAME`: Your bot's username (for referral links)
- `MAX_DAILY_DOWNLOADS`: Daily download limit per user (default: 5)
- `MAX_FILE_SIZE`: Maximum file size in bytes (default: 2GB)
- `DATABASE_PATH`: Path to SQLite database file (default: bot_database.db)

### Finding Your Telegram User ID

To find your Telegram user ID for admin access:
1. Message @userinfobot on Telegram
2. It will reply with your user ID
3. Add this ID to the `ADMIN_IDS` environment variable

## Usage

### User Commands

- `/start` - Start the bot and see welcome message
- `/help` - Show help information
- `/status` - Check download usage and limits
- `/referral` - Get your referral link for bonus downloads

### Admin Commands

- `/admin` - Access admin panel with statistics and management tools

### Downloading Files

Simply send any URL to the bot and it will download and send the file back to you.

## File Limits

- Maximum file size: 2GB (Telegram Bot MTProto)
- Daily limit: 5 files per user
- Supported: All file types
- Note: Files are sent as documents in Telegram

## Referral System

- Share your referral link with friends
- When someone joins using your link, you get +1 download for 24 hours
- No limit on the number of referrals

## Admin Features

- View user statistics and growth
- Monitor download activity
- See top users by download count
- System cleanup and maintenance
- Detailed analytics and trends

## Troubleshooting

### Bot won't start
- Check that BOT_TOKEN is set correctly
- Verify the token is valid by testing with @BotFather

### Downloads failing
- Ensure the URL is accessible
- Check file size doesn't exceed 2GB
- Verify internet connection

### Database issues
- The bot creates `bot_database.db` automatically
- Make sure the directory is writable
- Delete the database file to reset all data

## Security Notes

- Keep your bot token secret
- Only share admin access with trusted users
- The bot logs user activity for debugging
- Files are temporarily stored and then deleted

## Support

For issues or questions, check the logs in the console where you're running the bot.
