"""Configuration settings for Moodtape bot using Pydantic."""

from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseSettings, Field, validator

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    """Application settings managed by Pydantic."""
    
    # Base paths (not from env)
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    
    # Critical settings
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    OPENAI_API_KEY: str = Field(..., description="OpenAI API Key")
    
    # OpenAI settings
    OPENAI_MODEL: str = Field("gpt-4o", description="OpenAI model to use")
    OPENAI_TEMPERATURE: float = Field(0.5, description="OpenAI temperature parameter")
    
    # Spotify settings
    SPOTIFY_CLIENT_ID: Optional[str] = Field(None, description="Spotify Client ID")
    SPOTIFY_CLIENT_SECRET: Optional[str] = Field(None, description="Spotify Client Secret")
    SPOTIFY_REDIRECT_URI: str = Field("http://localhost:8888/callback", description="Spotify OAuth redirect URI")
    
    # Apple Music settings
    APPLE_TEAM_ID: Optional[str] = Field(None, description="Apple Team ID")
    APPLE_KEY_ID: Optional[str] = Field(None, description="Apple Key ID")
    APPLE_PRIVATE_KEY_PATH: Optional[str] = Field(None, description="Path to Apple private key file")
    
    # Database settings
    DATABASE_URL: str = Field(default_factory=lambda: f"sqlite:///{DATA_DIR}/moodtape.db")
    TOKENS_DB_PATH: Path = Field(default_factory=lambda: DATA_DIR / "tokens.sqlite")
    FEEDBACK_DB_PATH: Path = Field(default_factory=lambda: DATA_DIR / "feedback.sqlite")
    QUERY_LOG_DB_PATH: Path = Field(default_factory=lambda: DATA_DIR / "query_log.sqlite")
    
    # Logging settings
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    LOG_FORMAT: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Playlist settings
    DEFAULT_PLAYLIST_LENGTH: int = Field(20, description="Default number of tracks in playlist")
    MAX_PLAYLIST_LENGTH: int = Field(50, description="Maximum number of tracks in playlist")
    
    # Rate limiting
    MAX_REQUESTS_PER_USER_PER_HOUR: int = Field(10, description="Maximum requests per user per hour")
    
    # Feature flags
    ENABLE_SPOTIFY: bool = Field(True, description="Enable Spotify integration")
    ENABLE_APPLE_MUSIC: bool = Field(True, description="Enable Apple Music integration")
    ENABLE_FEEDBACK: bool = Field(True, description="Enable feedback feature")
    
    # Development settings
    DEBUG: bool = Field(False, description="Enable debug mode")
    WEBHOOK_URL: Optional[str] = Field(None, description="Webhook URL for production")
    HEALTH_PORT: int = Field(8000, description="Health check server port")
    
    # Music services configuration
    MUSIC_SERVICES: Dict = Field(
        default_factory=lambda: {
            "spotify": {"name": "Spotify", "enabled": True, "icon": "🟢"},
            "apple_music": {"name": "Apple Music", "enabled": True, "icon": "🍎"}
        }
    )
    
    @validator("BOT_TOKEN", pre=True)
    def validate_bot_token(cls, v, values):
        """Support multiple possible environment variable names for bot token."""
        from os import environ
        if not v:
            for key in ["TELEGRAM_BOT_TOKEN", "Telegram_Token", "TELEGRAM_TOKEN", "BOT_TOKEN"]:
                if key in environ:
                    return environ[key]
        return v
    
    @validator("OPENAI_API_KEY", pre=True)
    def validate_openai_key(cls, v, values):
        """Support multiple possible environment variable names for OpenAI key."""
        from os import environ
        if not v:
            for key in ["OPENAI_API_KEY", "OPENAI_API_Key", "OPENAI_TOKEN", "GPT_API_KEY"]:
                if key in environ:
                    return environ[key]
        return v
    
    @validator("MUSIC_SERVICES", always=True)
    def update_music_services(cls, v, values):
        """Update music services based on credentials."""
        v["spotify"]["enabled"] = bool(
            values.get("ENABLE_SPOTIFY") and 
            values.get("SPOTIFY_CLIENT_ID") and 
            values.get("SPOTIFY_CLIENT_SECRET")
        )
        v["apple_music"]["enabled"] = bool(
            values.get("ENABLE_APPLE_MUSIC") and 
            values.get("APPLE_TEAM_ID") and 
            values.get("APPLE_KEY_ID") and 
            values.get("APPLE_PRIVATE_KEY_PATH")
        )
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = True
        env_prefix = ""

# Create settings instance
settings = Settings()

def validate_settings() -> bool:
    """Validate critical settings and log warnings."""
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    # Check music services
    available_services = [
        service["name"] 
        for service in settings.MUSIC_SERVICES.values() 
        if service["enabled"]
    ]
    
    if not available_services:
        logger.warning("⚠️  No music services configured. Bot will work but won't be able to create playlists.")
        logger.warning("📖 Check Docs/railway_setup.md for setup instructions")
    else:
        logger.info(f"🎵 Available music services: {', '.join(available_services)}")
    
    return True 