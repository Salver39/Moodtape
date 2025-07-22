"""Production configuration for Moodtape bot."""

import os
from pathlib import Path
from typing import Optional

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
IS_STAGING = ENVIRONMENT == "staging"
IS_DEVELOPMENT = ENVIRONMENT == "development"

# Webhook configuration for production
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., "https://your-domain.com"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Parse DATABASE_URL for various database types
    if DATABASE_URL.startswith("postgresql://"):
        # PostgreSQL configuration
        DB_TYPE = "postgresql"
        DB_URL = DATABASE_URL
    elif DATABASE_URL.startswith("mysql://"):
        # MySQL configuration  
        DB_TYPE = "mysql"
        DB_URL = DATABASE_URL
    else:
        # Default to SQLite
        DB_TYPE = "sqlite"
        DB_URL = DATABASE_URL
else:
    # Default SQLite configuration
    DB_TYPE = "sqlite"
    if IS_PRODUCTION:
        # Production SQLite path
        DB_URL = "sqlite:///data/moodtape_production.db"
    elif IS_STAGING:
        # Staging SQLite path
        DB_URL = "sqlite:///data/moodtape_staging.db"
    else:
        # Development SQLite path
        DB_URL = "sqlite:///data/moodtape.db"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")
LOG_FORMAT = os.getenv("LOG_FORMAT", "production" if IS_PRODUCTION else "development")

# Enable JSON logging in production
ENABLE_JSON_LOGGING = IS_PRODUCTION and os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true"

# Log file configuration
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "data/moodtape.log")
LOG_FILE_MAX_SIZE = int(os.getenv("LOG_FILE_MAX_SIZE", "10485760"))  # 10MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))

# Rate limiting configuration
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL")  # Optional Redis for distributed rate limiting

# API rate limits (can be overridden via environment)
OPENAI_RATE_LIMIT_RPM = int(os.getenv("OPENAI_RATE_LIMIT_RPM", "50"))
SPOTIFY_RATE_LIMIT_RPM = int(os.getenv("SPOTIFY_RATE_LIMIT_RPM", "100"))
APPLE_MUSIC_RATE_LIMIT_RPM = int(os.getenv("APPLE_MUSIC_RATE_LIMIT_RPM", "100"))

# Performance configuration
ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true" if IS_PRODUCTION else "false").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour

# Security configuration
ALLOWED_TELEGRAM_IPS = os.getenv("ALLOWED_TELEGRAM_IPS", "").split(",") if os.getenv("ALLOWED_TELEGRAM_IPS") else []
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")  # For webhook verification

# Feature flags
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "true" if IS_PRODUCTION else "false").lower() == "true"
ENABLE_ERROR_REPORTING = os.getenv("ENABLE_ERROR_REPORTING", "true" if IS_PRODUCTION else "false").lower() == "true"
ENABLE_PERSONALIZATION = os.getenv("ENABLE_PERSONALIZATION", "true").lower() == "true"

# Monitoring configuration
HEALTH_CHECK_ENDPOINT = os.getenv("HEALTH_CHECK_ENDPOINT", "/health")
METRICS_ENDPOINT = os.getenv("METRICS_ENDPOINT", "/metrics")
ENABLE_HEALTH_CHECKS = os.getenv("ENABLE_HEALTH_CHECKS", "true" if IS_PRODUCTION else "false").lower() == "true"

# Resource limits
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MEMORY_LIMIT_MB = int(os.getenv("MEMORY_LIMIT_MB", "512"))

# Backup configuration
ENABLE_DATABASE_BACKUP = os.getenv("ENABLE_DATABASE_BACKUP", "true" if IS_PRODUCTION else "false").lower() == "true"
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
BACKUP_S3_BUCKET = os.getenv("BACKUP_S3_BUCKET")  # Optional S3 backup

# Error recovery configuration
ENABLE_AUTO_RECOVERY = os.getenv("ENABLE_AUTO_RECOVERY", "true" if IS_PRODUCTION else "false").lower() == "true"
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

# Premium features configuration
ENABLE_PREMIUM_FEATURES = os.getenv("ENABLE_PREMIUM_FEATURES", "false").lower() == "true"
PREMIUM_USER_IDS = set(map(int, os.getenv("PREMIUM_USER_IDS", "").split(","))) if os.getenv("PREMIUM_USER_IDS") else set()

# Admin configuration
ADMIN_USER_IDS = set(map(int, os.getenv("ADMIN_USER_IDS", "").split(","))) if os.getenv("ADMIN_USER_IDS") else set()
ENABLE_ADMIN_COMMANDS = len(ADMIN_USER_IDS) > 0

# Debugging and development
ENABLE_DEBUG_LOGS = os.getenv("ENABLE_DEBUG_LOGS", "false" if IS_PRODUCTION else "true").lower() == "true"
ENABLE_PROFILING = os.getenv("ENABLE_PROFILING", "false").lower() == "true"


def validate_production_config() -> list[str]:
    """Validate production configuration and return list of issues."""
    issues = []
    
    if IS_PRODUCTION:
        # Critical production checks
        if not WEBHOOK_URL:
            issues.append("WEBHOOK_URL is required in production")
        
        if not WEBHOOK_SECRET_TOKEN:
            issues.append("WEBHOOK_SECRET_TOKEN is recommended in production")
        
        if LOG_LEVEL == "DEBUG":
            issues.append("DEBUG log level is not recommended in production")
        
        if not ENABLE_RATE_LIMITING:
            issues.append("Rate limiting should be enabled in production")
        
        # Performance warnings
        if MAX_CONCURRENT_REQUESTS > 200:
            issues.append(f"MAX_CONCURRENT_REQUESTS ({MAX_CONCURRENT_REQUESTS}) might be too high")
        
        if REQUEST_TIMEOUT_SECONDS > 60:
            issues.append(f"REQUEST_TIMEOUT_SECONDS ({REQUEST_TIMEOUT_SECONDS}) might be too high")
    
    return issues


def get_database_config() -> dict:
    """Get database configuration based on environment."""
    config = {
        "type": DB_TYPE,
        "url": DB_URL,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20" if IS_PRODUCTION else "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "30" if IS_PRODUCTION else "10")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),  # 1 hour
        "echo": not IS_PRODUCTION,  # Disable SQL echo in production
    }
    
    return config


def get_logging_config() -> dict:
    """Get logging configuration based on environment."""
    config = {
        "level": LOG_LEVEL,
        "format": LOG_FORMAT,
        "file_path": LOG_FILE_PATH,
        "file_max_size": LOG_FILE_MAX_SIZE,
        "file_backup_count": LOG_FILE_BACKUP_COUNT,
        "enable_json": ENABLE_JSON_LOGGING,
        "enable_console": not IS_PRODUCTION or ENABLE_DEBUG_LOGS,
    }
    
    return config


def get_webhook_config() -> Optional[dict]:
    """Get webhook configuration if enabled."""
    if not WEBHOOK_URL:
        return None
    
    config = {
        "url": WEBHOOK_URL,
        "path": WEBHOOK_PATH,
        "port": WEBHOOK_PORT,
        "listen": WEBHOOK_LISTEN,
        "secret_token": WEBHOOK_SECRET_TOKEN,
        "allowed_ips": ALLOWED_TELEGRAM_IPS,
    }
    
    return config


def is_admin_user(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in ADMIN_USER_IDS


def is_premium_user(user_id: int) -> bool:
    """Check if user has premium features."""
    return user_id in PREMIUM_USER_IDS


def print_startup_info():
    """Print startup information for debugging."""
    print(f"🚀 Moodtape Bot Starting")
    print(f"📊 Environment: {ENVIRONMENT}")
    print(f"🌐 Webhook: {'Enabled' if WEBHOOK_URL else 'Disabled'}")
    print(f"💾 Database: {DB_TYPE.upper()}")
    print(f"📝 Log Level: {LOG_LEVEL}")
    print(f"⚡ Rate Limiting: {'Enabled' if ENABLE_RATE_LIMITING else 'Disabled'}")
    print(f"🎯 Personalization: {'Enabled' if ENABLE_PERSONALIZATION else 'Disabled'}")
    print(f"👑 Premium Users: {len(PREMIUM_USER_IDS)}")
    print(f"🔧 Admin Users: {len(ADMIN_USER_IDS)}")
    
    # Validate configuration
    if IS_PRODUCTION:
        issues = validate_production_config()
        if issues:
            print("\n⚠️  Production Configuration Issues:")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print("\n✅ Production configuration validated successfully")


if __name__ == "__main__":
    print_startup_info() 