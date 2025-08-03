"""Production configuration for Moodtape bot."""

from pathlib import Path
from typing import Dict, List, Set, Optional

from config.settings import settings

# Environment
IS_PRODUCTION = settings.ENVIRONMENT == "production"

# Webhook configuration
def get_webhook_config() -> Optional[Dict[str, str]]:
    """Get webhook configuration if enabled."""
    if not settings.WEBHOOK_URL:
        return None
    
    return {
        "url": settings.WEBHOOK_URL.rstrip("/"),
        "path": settings.WEBHOOK_PATH,
        "port": settings.WEBHOOK_PORT,
        "listen": settings.WEBHOOK_LISTEN,
        "secret_token": settings.WEBHOOK_SECRET_TOKEN
    }

# Database configuration
def get_database_config() -> Dict:
    """Get database configuration."""
    return {
        "url": settings.DATABASE_URL,
        "pool_settings": {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE
        }
    }

# Logging configuration
def get_logging_config() -> Dict:
    """Get logging configuration."""
    return {
        "level": settings.LOG_LEVEL,
        "format": settings.LOG_FORMAT,
        "enable_json": settings.ENABLE_JSON_LOGGING,
        "file": {
            "path": settings.LOG_FILE_PATH,
            "max_size": settings.LOG_FILE_MAX_SIZE,
            "backup_count": settings.LOG_FILE_BACKUP_COUNT
        }
    }

# Rate limiting configuration
def get_rate_limiting_config() -> Dict:
    """Get rate limiting configuration."""
    return {
        "enabled": settings.ENABLE_RATE_LIMITING,
        "redis_url": settings.RATE_LIMIT_REDIS_URL,
        "limits": {
            "openai": settings.OPENAI_RATE_LIMIT_RPM,
            "spotify": settings.SPOTIFY_RATE_LIMIT_RPM,
            "apple_music": settings.APPLE_MUSIC_RATE_LIMIT_RPM
        }
    }

# Caching configuration
def get_cache_config() -> Dict:
    """Get caching configuration."""
    return {
        "enabled": settings.ENABLE_CACHING,
        "ttl": settings.CACHE_TTL_SECONDS
    }

# Security configuration
def get_security_config() -> Dict:
    """Get security configuration."""
    return {
        "allowed_telegram_ips": settings.ALLOWED_TELEGRAM_IPS,
        "webhook_secret": settings.WEBHOOK_SECRET_TOKEN
    }

# Analytics configuration
def get_analytics_config() -> Dict:
    """Get analytics configuration."""
    return {
        "enabled": settings.ENABLE_ANALYTICS,
        "error_reporting": settings.ENABLE_ERROR_REPORTING,
        "personalization": settings.ENABLE_PERSONALIZATION
    }

# Monitoring configuration
def get_monitoring_config() -> Dict:
    """Get monitoring configuration."""
    return {
        "health_check": {
            "enabled": settings.ENABLE_HEALTH_CHECKS,
            "endpoint": settings.HEALTH_CHECK_ENDPOINT
        },
        "metrics": {
            "endpoint": settings.METRICS_ENDPOINT
        }
    }

# Performance configuration
def get_performance_config() -> Dict:
    """Get performance configuration."""
    return {
        "max_concurrent_requests": settings.MAX_CONCURRENT_REQUESTS,
        "request_timeout": settings.REQUEST_TIMEOUT_SECONDS,
        "memory_limit": settings.MEMORY_LIMIT_MB
    }

# Backup configuration
def get_backup_config() -> Dict:
    """Get backup configuration."""
    return {
        "enabled": settings.ENABLE_DATABASE_BACKUP,
        "interval_hours": settings.BACKUP_INTERVAL_HOURS,
        "retention_days": settings.BACKUP_RETENTION_DAYS,
        "s3_bucket": settings.BACKUP_S3_BUCKET
    }

# Recovery configuration
def get_recovery_config() -> Dict:
    """Get recovery configuration."""
    return {
        "enabled": settings.ENABLE_AUTO_RECOVERY,
        "max_retries": settings.MAX_RETRY_ATTEMPTS,
        "backoff_factor": settings.RETRY_BACKOFF_FACTOR
    }

# Premium features configuration
def get_premium_config() -> Dict:
    """Get premium features configuration."""
    return {
        "enabled": settings.ENABLE_PREMIUM_FEATURES,
        "user_ids": settings.PREMIUM_USER_IDS
    }

# Admin configuration
def get_admin_config() -> Dict:
    """Get admin configuration."""
    return {
        "user_ids": settings.ADMIN_USER_IDS
    }

# Debug configuration
def get_debug_config() -> Dict:
    """Get debug configuration."""
    return {
        "enabled": settings.ENABLE_DEBUG_LOGS,
        "profiling": settings.ENABLE_PROFILING
    } 