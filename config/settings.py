"""Configuration settings for Moodtape bot."""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# OpenAI GPT-4o
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка критических переменных в runtime, а не при импорте
def validate_required_env_vars():
    """Проверяет наличие обязательных переменных окружения"""
    missing_vars = []
    
    if not TELEGRAM_BOT_TOKEN:
        missing_vars.append("TELEGRAM_BOT_TOKEN")
    
    if not OPENAI_API_KEY:
        missing_vars.append("OPENAI_API_KEY")
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Проверяем музыкальные сервисы (не критично для запуска)
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    available_services = []
    if ENABLE_SPOTIFY:
        available_services.append("Spotify")
    if ENABLE_APPLE_MUSIC:
        available_services.append("Apple Music")
    
    if not available_services:
        logger.warning("⚠️  No music services configured. Bot will work but won't be able to create playlists.")
        logger.warning("📖 Check Docs/railway_setup.md for setup instructions")
    else:
        logger.info(f"🎵 Available music services: {', '.join(available_services)}")
    
    return True

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.5"))

# Spotify API
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")

# Apple Music API
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_PRIVATE_KEY_PATH = os.getenv("APPLE_PRIVATE_KEY_PATH")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/moodtape.db")

# Database file paths
TOKENS_DB_PATH = DATA_DIR / "tokens.sqlite"
FEEDBACK_DB_PATH = DATA_DIR / "feedback.sqlite"
QUERY_LOG_DB_PATH = DATA_DIR / "query_log.sqlite"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Playlist settings
DEFAULT_PLAYLIST_LENGTH = int(os.getenv("DEFAULT_PLAYLIST_LENGTH", "20"))
MAX_PLAYLIST_LENGTH = int(os.getenv("MAX_PLAYLIST_LENGTH", "50"))

# Rate limiting
MAX_REQUESTS_PER_USER_PER_HOUR = int(os.getenv("MAX_REQUESTS_PER_USER_PER_HOUR", "10"))

# Features flags
ENABLE_SPOTIFY = os.getenv("ENABLE_SPOTIFY", "true").lower() == "true"
ENABLE_APPLE_MUSIC = os.getenv("ENABLE_APPLE_MUSIC", "true").lower() == "true"
ENABLE_FEEDBACK = os.getenv("ENABLE_FEEDBACK", "true").lower() == "true"

# Development settings
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # For production deployment

# Music service configurations
MUSIC_SERVICES = {
    "spotify": {
        "name": "Spotify",
        "enabled": ENABLE_SPOTIFY,
        "icon": "🟢"
    },
    "apple_music": {
        "name": "Apple Music", 
        "enabled": ENABLE_APPLE_MUSIC,
        "icon": "🍎"
    }
}

# Conditionally enable services based on credentials
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    ENABLE_SPOTIFY = ENABLE_SPOTIFY and True
else:
    ENABLE_SPOTIFY = False
    print("Warning: Spotify credentials not configured, Spotify will be disabled")

if APPLE_TEAM_ID and APPLE_KEY_ID and APPLE_PRIVATE_KEY_PATH:
    ENABLE_APPLE_MUSIC = ENABLE_APPLE_MUSIC and True
else:
    ENABLE_APPLE_MUSIC = False
    print("Warning: Apple Music credentials not configured, Apple Music will be disabled")

# Update music services with actual availability
MUSIC_SERVICES["spotify"]["enabled"] = ENABLE_SPOTIFY
MUSIC_SERVICES["apple_music"]["enabled"] = ENABLE_APPLE_MUSIC

# Note: Service validation moved to runtime in validate_required_env_vars()
# This allows bot to start without music services for initial setup 