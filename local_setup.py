#!/usr/bin/env python3
"""
Local setup script for Telegram File Download Bot
This script helps set up the bot for local development
"""

import os
import subprocess
import sys

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot", "aiohttp"])
        print("✅ Packages installed successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to install packages")
        return False
    return True

def setup_env_file():
    """Create .env file template"""
    env_template = """# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_user_id
BOT_USERNAME=your_bot_username

# Optional Configuration
MAX_DAILY_DOWNLOADS=5
MAX_FILE_SIZE=2147483648
DATABASE_PATH=bot_database.db
DOWNLOAD_TIMEOUT=300
REFERRAL_BONUS_DURATION_HOURS=24
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_template)
        print("✅ Created .env file template")
        print("📝 Please edit .env file and add your bot token and admin ID")
    else:
        print("ℹ️  .env file already exists")

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def create_directories():
    """Create necessary directories"""
    dirs = ['logs', 'temp']
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✅ Created {dir_name} directory")

def main():
    """Main setup function"""
    print("🤖 Telegram File Download Bot - Local Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install requirements
    if not install_requirements():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Setup environment file
    setup_env_file()
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Get a bot token from @BotFather on Telegram")
    print("2. Find your Telegram user ID (message @userinfobot)")
    print("3. Edit the .env file with your details")
    print("4. Run: python main.py")
    print("\n📖 See README.md for detailed instructions")

if __name__ == "__main__":
    main()