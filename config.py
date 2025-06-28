"""
Configuration settings for the Telegram bot
"""

import os

# Try to load .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue without it
    pass

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("⚠️  BOT_TOKEN environment variable is required")
    print("Please add your Telegram bot token to continue.")
    print("Get your token from @BotFather on Telegram")
    exit(1)

# Admin user IDs (comma-separated string in environment variable)
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = []
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    except ValueError:
        print("Warning: Invalid ADMIN_IDS format. Should be comma-separated integers.")

# Download limits
MAX_DAILY_DOWNLOADS = int(os.getenv('MAX_DAILY_DOWNLOADS', '5'))
# Telegram Bot API has a 50MB limit for file uploads
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '52428800'))  # 50MB in bytes (Telegram limit)

# Database configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_database.db')

# Download settings
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', '300'))  # 5 minutes
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '8192'))  # 8KB chunks

# Referral settings
REFERRAL_BONUS_DURATION_HOURS = int(os.getenv('REFERRAL_BONUS_DURATION_HOURS', '24'))

# Bot info
BOT_USERNAME = os.getenv('BOT_USERNAME', 'your_bot_username')
