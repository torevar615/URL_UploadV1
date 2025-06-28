#!/usr/bin/env python3
"""
Local runner for Telegram File Download Bot
This script sets up environment variables and runs the bot locally
"""

import os
import sys

def setup_environment():
    """Set up environment variables for local development"""
    
    # Check if .env file exists and read it
    if os.path.exists('.env'):
        print("Loading configuration from .env file...")
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # Check required environment variables
    required_vars = ['BOT_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Please create a .env file with your configuration.")
        print("   You can copy .env.example as a template.")
        return False
    
    # Set default values for optional variables
    defaults = {
        'MAX_DAILY_DOWNLOADS': '5',
        'MAX_FILE_SIZE': '2147483648',  # 2GB
        'DATABASE_PATH': 'bot_database.db',
        'DOWNLOAD_TIMEOUT': '300',
        'REFERRAL_BONUS_DURATION_HOURS': '24',
        'ADMIN_IDS': '',
        'BOT_USERNAME': 'your_bot_username'
    }
    
    for key, default_value in defaults.items():
        if not os.environ.get(key):
            os.environ[key] = default_value
    
    return True

def main():
    """Main function to run the bot locally"""
    print("🤖 Starting Telegram File Download Bot locally...")
    print("=" * 50)
    
    # Setup environment
    if not setup_environment():
        sys.exit(1)
    
    # Display configuration
    print("✅ Configuration loaded:")
    print(f"   BOT_TOKEN: {'*' * 20}{os.environ['BOT_TOKEN'][-10:]}")
    print(f"   ADMIN_IDS: {os.environ.get('ADMIN_IDS', 'Not set')}")
    print(f"   BOT_USERNAME: {os.environ.get('BOT_USERNAME')}")
    print(f"   MAX_DAILY_DOWNLOADS: {os.environ.get('MAX_DAILY_DOWNLOADS')}")
    print(f"   MAX_FILE_SIZE: {int(os.environ.get('MAX_FILE_SIZE', 0)) // 1024 // 1024 // 1024}GB")
    print()
    
    # Import and run the bot
    try:
        import platform
        if platform.system() == 'Windows':
            import asyncio
            # Fix for Windows event loop issues
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        from main import main as bot_main
        print("🚀 Bot starting...")
        bot_main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()