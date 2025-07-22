"""Main entry point for Moodtape Telegram bot."""

import asyncio
import os
from pathlib import Path
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config.settings import TELEGRAM_BOT_TOKEN, DEBUG, WEBHOOK_URL, validate_required_env_vars
from utils.logger import get_logger

# Import handlers
from bot.handlers.start import start_command, service_selection_callback, help_command
from bot.handlers.mood import mood_message_handler
from bot.handlers.auth import auth_status_command
from bot.handlers.feedback import handle_feedback_callback
from bot.handlers.preferences import preferences_command, stats_command

# Import middleware
from bot.middleware.error_handler import telegram_error_handler
from bot.middleware.rate_limiter import rate_limiter

logger = get_logger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""
    
    def do_GET(self):
        """Handle GET requests for health check."""
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "moodtape-bot"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass

def start_health_server():
    """Start simple HTTP server for health checks."""
    port = int(os.getenv("PORT", 8000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🏥 Health check server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start health server: {e}")

def main() -> None:
    """Start the bot."""
    # Validate required environment variables
    try:
        validate_required_env_vars()
        logger.info("✅ All required environment variables are configured")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("Please set the required environment variables and restart the bot")
        return
    
    # Start health check server in background thread for Render compatibility
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("auth", auth_status_command))
    application.add_handler(CommandHandler("preferences", preferences_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(
        service_selection_callback, 
        pattern=r"^service:"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_feedback_callback,
        pattern=r"^feedback:"
    ))
    
    # Message handlers (for mood descriptions)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        mood_message_handler
    ))
    
    # Error handler
    application.add_error_handler(telegram_error_handler)
    
    # Setup periodic cleanup for rate limiter
    async def cleanup_rate_limiter(context):
        """Periodic cleanup of rate limiter data."""
        rate_limiter.cleanup_old_data()
    
    # Add cleanup job (every 6 hours)
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(cleanup_rate_limiter, interval=21600, first=60)  # 6 hours
        logger.info("Rate limiter cleanup job scheduled")
    
    logger.info("Moodtape bot starting...")
    
    if WEBHOOK_URL and not DEBUG:
        # Production mode with webhook
        logger.info(f"Starting bot with webhook: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=8000,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook"
        )
    else:
        # Development mode with polling
        logger.info("Starting bot with polling (development mode)")
        application.run_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=True
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 