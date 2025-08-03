"""Main entry point for Moodtape Telegram bot."""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs
from aiohttp import web
import logging
logging.getLogger("aiohttp.server").setLevel(logging.DEBUG)
import redis

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config.settings import settings, validate_settings
from utils.logger import get_logger
from auth.spotify_auth import spotify_callback_handler

logger = get_logger(__name__)

# Попытка получить распределённый lock в Redis
redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    sys.exit("ERROR: REDIS_URL не задан")

client = redis.Redis.from_url(redis_url)
# Устанавливаем ключ с NX и TTL 60 секунд
acquired = client.set("moodtape_polling_lock", "1", nx=True, ex=60)
if not acquired:
    sys.exit(0)  # другой экземпляр уже держит lock

# Import handlers
from bot.handlers.start import start_command, service_selection_callback, help_command
from bot.handlers.mood import mood_message_handler
from bot.handlers.auth import auth_status_command, handle_auth_callback, logout_command
from bot.handlers.feedback import handle_feedback_callback
from bot.handlers.preferences import preferences_command, stats_command
from bot.handlers.admin import (
    admin_rate_limit_stats,
    admin_blocked_users,
    admin_user_status,
    admin_violations_history,
    admin_cleanup_old_data,
    handle_admin_callback
)

# Import middleware
from bot.middleware.error_handler import telegram_error_handler
from bot.middleware.rate_limiter import rate_limiter

# Global application instance
_application = None
_shutdown_event = asyncio.Event()

async def healthcheck(request):
    """Handle health check requests."""
    try:
        return web.Response(text="OK")
    except Exception:
        logger.exception("Healthcheck crashed")
        return web.Response(status=500, text="Healthcheck error")

async def start_health_server():
    """Start a minimal HTTP server for health checks."""
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/auth/spotify/callback", spotify_callback_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🏥 Health check server started on port {port}")

def get_application():
    """Get the global application instance."""
    return _application

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    _shutdown_event.set()
    
    # Clean shutdown sequence
    if _application:
        try:
            # Stop the application gracefully
            asyncio.create_task(_application.stop())
            asyncio.create_task(_application.shutdown())
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
    
    # Release Redis lock
    try:
        client.delete("moodtape_polling_lock")
        logger.info("✅ Released Redis lock")
    except Exception as e:
        logger.error(f"❌ Failed to release Redis lock: {e}")
    
    logger.info("👋 Goodbye!")
    sys.exit(0)

def main() -> None:
    """Start the bot."""
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Validate required environment variables
    try:
        validate_settings()
        logger.info("✅ All required environment variables are configured")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("Please set the required environment variables and restart the bot")
        return
    
    # Create application with better error handling
    global _application
    try:
        _application = Application.builder().token(settings.BOT_TOKEN).build()
        logger.info("✅ Telegram application created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create Telegram application: {e}")
        return
    
    # Wait a bit for any old instances to fully terminate
    logger.info("⏳ Waiting for any old bot instances to terminate...")
    time.sleep(5)
    
    # Add handlers
    
    # Command handlers
    _application.add_handler(CommandHandler("start", start_command))
    _application.add_handler(CommandHandler("help", help_command))
    _application.add_handler(CommandHandler("auth", auth_status_command))
    _application.add_handler(CommandHandler("preferences", preferences_command))
    _application.add_handler(CommandHandler("stats", stats_command))
    _application.add_handler(CommandHandler("logout", logout_command))
    
    # Admin commands
    _application.add_handler(CommandHandler("admin_stats", admin_rate_limit_stats))
    _application.add_handler(CommandHandler("admin_blocked", admin_blocked_users))
    _application.add_handler(CommandHandler("admin_user", admin_user_status))
    _application.add_handler(CommandHandler("admin_violations", admin_violations_history))
    _application.add_handler(CommandHandler("admin_cleanup", admin_cleanup_old_data))
    
    # Callback query handlers
    _application.add_handler(CallbackQueryHandler(
        service_selection_callback, 
        pattern=r"^service:"
    ))
    _application.add_handler(CallbackQueryHandler(
        handle_feedback_callback,
        pattern=r"^feedback:"
    ))
    _application.add_handler(CallbackQueryHandler(
        handle_admin_callback,
        pattern=r"^admin_"
    ))
    
    # Message handlers (for mood descriptions)
    _application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        mood_message_handler
    ))
    
    # Error handler
    _application.add_error_handler(telegram_error_handler)
    
    # Setup periodic cleanup for rate limiter
    async def cleanup_rate_limiter(context):
        """Periodic cleanup of rate limiter data."""
        rate_limiter.cleanup_old_data()
        rate_limiter.cleanup_old_violations()
    
    # Add cleanup job (every 6 hours)
    job_queue = _application.job_queue
    if job_queue:
        job_queue.run_repeating(cleanup_rate_limiter, interval=21600, first=60)  # 6 hours
        logger.info("Rate limiter cleanup job scheduled")
    
    logger.info("🚀 Moodtape bot starting...")
    
    # Choose between webhook and polling mode
    if settings.WEBHOOK_URL:
        logger.info("🌐 Starting in WEBHOOK mode for production")
        try:
            from config.production import get_webhook_config
            webhook_config = get_webhook_config()
            
            if webhook_config:
                # Запускаем webhook сервер
                _application.run_webhook(
                    listen=webhook_config["listen"],
                    port=webhook_config["port"],
                    url_path=webhook_config["path"],
                    webhook_url=webhook_config["url"] + webhook_config["path"],
                    secret_token=webhook_config.get("secret_token"),
                    drop_pending_updates=True
                )
                logger.info("🎵 Bot started successfully in webhook mode!")
            else:
                logger.error("❌ Failed to get webhook configuration")
                return
        except Exception as e:
            logger.error(f"❌ Failed to start webhook mode: {e}")
            return
    else:
        logger.info("🔄 Starting in POLLING mode for development")
        
        # Start health check server
        loop = asyncio.get_event_loop()
        loop.create_task(start_health_server())
        
        # Start polling with conservative settings
        try:
            _application.run_polling(
                poll_interval=3.0,
                timeout=15,
                drop_pending_updates=True,
                stop_signals=None,
                close_loop=False
            )
            logger.info("🎵 Bot started successfully!")
        except Exception as e:
            error_str = str(e).lower()
            if "conflict" in error_str and "getUpdates" in error_str:
                logger.error("🚨 Multiple bot instances detected!")
                logger.error(f"💡 Error: {e}")
            else:
                logger.error(f"❌ Unexpected error: {e}")
            raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user (Ctrl+C)")
    except SystemExit:
        logger.info("👋 Bot stopped by system signal")
    except Exception as e:
        error_str = str(e).lower()
        if "conflict" in error_str and "getUpdates" in error_str:
            logger.error("🚨 CRITICAL: Multiple bot instances detected!")
            logger.error("🔧 SOLUTION: Check your deployment platform for running instances")
            logger.error("   - Render.com: Check dashboard for multiple deploys")
            logger.error("   - Docker: Check for running containers")
            logger.error("   - Local: Check for other terminal sessions")
        else:
            logger.error(f"💥 Fatal error: {e}")
        
        # Clean shutdown
        if _application:
            try:
                asyncio.run(_application.stop())
                asyncio.run(_application.shutdown())
            except:
                pass
        
        # Release Redis lock on error
        try:
            client.delete("moodtape_polling_lock")
            logger.info("✅ Released Redis lock")
        except Exception as e:
            logger.error(f"❌ Failed to release Redis lock: {e}")
        
        sys.exit(1) 