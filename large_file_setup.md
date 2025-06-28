# 2GB File Support Setup Guide

Your Telegram bot now supports **files up to 2GB** using MTProto API! Here's how to enable it:

## Quick Setup (5 minutes)

### Step 1: Get API Credentials
1. Go to https://my.telegram.org/apps
2. Log in with your Telegram account
3. Create a new application:
   - **App title**: "Telegram File Bot"
   - **Short name**: "filebot" (or any name)
   - **Platform**: Select any (Desktop recommended)
4. Copy the **API ID** and **API Hash** values

### Step 2: Configure Environment
1. Open your `.env` file (or create one from `.env.example`)
2. Add these lines:
```
TELEGRAM_API_ID=YOUR_API_ID_HERE
TELEGRAM_API_HASH=YOUR_API_HASH_HERE
```

### Step 3: Restart Bot
Restart your bot and it will now support 2GB files automatically!

## How It Works

### File Size Handling
- **Small files (under 50MB)**: Sent via regular Bot API (fast)
- **Large files (50MB - 2GB)**: Sent via MTProto API (slower but no limits)

### User Experience
- Files are handled seamlessly - users don't need to do anything different
- Large files show upload progress
- Download and send process is fully automated

### Fallback Mode
If MTProto credentials are not configured:
- Bot works normally for files under 50MB
- For larger files, bot offers file splitting option
- Users get clear instructions for both scenarios

## Advanced Configuration

### Custom File Size Limits
Edit `config.py` to change the maximum file size:
```python
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB default
```

### MTProto Session Storage
Sessions are stored in the temp directory and cleaned up automatically.

## Troubleshooting

### "API credentials required" message
- Make sure `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are set correctly
- Restart the bot after adding credentials

### Large file upload fails
- Check internet connection stability
- Large files take longer to upload
- Verify the file isn't corrupted

### Bot API vs MTProto
- Bot API: Faster, 50MB limit, simpler
- MTProto: Slower, 2GB limit, requires credentials

## Security Notes

- Keep API credentials secure and private
- Never share your API ID and API Hash
- These credentials are for your bot only
- Sessions are temporary and automatically cleaned

Your bot now matches the capabilities of premium file download bots!