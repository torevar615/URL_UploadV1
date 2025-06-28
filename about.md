# Telegram File Download Bot

## Overview

This is a Telegram bot that allows users to download files from URLs with built-in usage limits, a referral system, and admin management capabilities. The bot is designed to manage user downloads, track usage statistics, and provide administrative controls for monitoring and managing the system.

## System Architecture

The application follows a modular Python architecture with the following key design principles:

1. **Separation of Concerns**: Each major functionality is separated into dedicated modules
2. **Database Abstraction**: SQLite database with a custom ORM-like interface for data management
3. **Asynchronous Operations**: Uses async/await pattern for handling Telegram API calls and file downloads
4. **Environment-based Configuration**: All sensitive data and settings are managed through environment variables

## Key Components

### Core Application (`main.py`)
- **Purpose**: Entry point and main bot logic
- **Responsibilities**: Command handling, user interaction, bot lifecycle management
- **Architecture**: Uses python-telegram-bot library with async handlers

### Database Layer (`database.py`)
- **Technology**: SQLite with custom Python wrapper
- **Models**: User, Download, Referral dataclasses
- **Features**: User management, download tracking, referral system data
- **Design**: Direct SQL queries with connection pooling

### File Handling (`file_handler.py`)
- **Purpose**: Manages file downloads and processing
- **Technology**: aiohttp for HTTP requests
- **Features**: File size validation, download progress tracking, temporary file management
- **Architecture**: Async file operations with configurable timeouts and chunk sizes

### Admin Panel (`admin.py`)
- **Purpose**: Administrative interface for bot management
- **Features**: User statistics, download monitoring, system cleanup
- **Access Control**: Admin-only functionality based on user ID whitelist

### Referral System (`referral.py`)
- **Purpose**: User referral and bonus system
- **Features**: Referral link generation, bonus tracking, referral processing
- **Architecture**: Deep linking with Telegram start parameters

### Configuration (`config.py`)
- **Purpose**: Centralized configuration management
- **Method**: Environment variable-based configuration
- **Settings**: Bot tokens, admin IDs, download limits, database paths

### Utilities (`utils.py`)
- **Purpose**: Common helper functions
- **Features**: File size formatting, filename extraction, admin validation
- **Design**: Pure functions with no external dependencies

## Data Flow

1. **User Interaction**: User sends URL to bot
2. **Validation**: Bot checks user limits and file constraints
3. **Download Process**: File is downloaded to temporary storage
4. **Upload**: File is sent back to user via Telegram
5. **Tracking**: Download is logged in database
6. **Cleanup**: Temporary files are removed

## External Dependencies

### Core Libraries
- **python-telegram-bot**: Telegram Bot API wrapper
- **aiohttp**: Async HTTP client for file downloads
- **sqlite3**: Database operations (built-in Python)

### System Dependencies
- Python 3.11 runtime environment
- File system access for temporary storage
- Network access for Telegram API and file downloads

## Deployment Strategy

### Environment Setup
- **Platform**: Replit with Nix package manager
- **Runtime**: Python 3.11 module
- **Dependencies**: Automatically installed via workflow

### Configuration Requirements
- `BOT_TOKEN`: Telegram bot token (required)
- `ADMIN_IDS`: Comma-separated admin user IDs
- `MAX_DAILY_DOWNLOADS`: Daily download limit per user (default: 5)
- `MAX_FILE_SIZE`: Maximum file size in bytes (default: 2GB)
- `DATABASE_PATH`: SQLite database file path
- `BOT_USERNAME`: Bot username for referral links

### Workflow
- Parallel execution model
- Automatic dependency installation
- Single command startup via `python main.py`

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

- **June 27, 2025**: Fixed import issues and Google Drive cleanup
  - Completely removed all Google Drive integration references from codebase
  - Fixed python-telegram-bot package import conflicts (removed conflicting `telegram` package)
  - Created comprehensive telegram package __init__.py with all required imports
  - Fixed MTProto client startup and error handling for better reliability
  - Resolved "Client has not been started yet" and "is_premium" attribute errors
  - Enhanced Windows event loop compatibility with threading fallback and nest_asyncio support

- **June 27, 2025**: Implemented MTProto API for 2GB file support
  - Added Pyrogram-based MTProto client for native Telegram file handling
  - Created hybrid file handler: Bot API for small files, MTProto for large files
  - Supports files up to 2GB with progress tracking and automatic method selection
  - Includes file splitting fallback for when MTProto credentials aren't configured
  - Added comprehensive setup guide and environment configuration examples

- **June 27, 2025**: Fixed Windows compatibility issue with event loop
  - Created `main_windows.py` for Windows users 
  - Added proper event loop policy for Windows systems
  - Updated documentation with platform-specific instructions

## Changelog

- June 27, 2025: Initial setup and Windows compatibility fix
