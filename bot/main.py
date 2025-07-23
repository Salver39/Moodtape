"""Main entry point for Moodtape Telegram bot."""

import asyncio
import os
import signal
import sys
from pathlib import Path
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config.settings import TELEGRAM_BOT_TOKEN, DEBUG, WEBHOOK_URL, validate_required_env_vars
from utils.logger import get_logger

# Import handlers
from bot.handlers.start import start_command, service_selection_callback, help_command
from bot.handlers.mood import mood_message_handler
from bot.handlers.auth import auth_status_command, handle_auth_callback
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

logger = get_logger(__name__)

# Global application instance
_application = None
_shutdown_event = asyncio.Event()

def get_application():
    """Get the global application instance."""
    return _application

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    _shutdown_event.set()
    
    # Give some time for cleanup before force exit
    if _application:
        try:
            # Stop the application gracefully
            asyncio.create_task(_application.stop())
            asyncio.create_task(_application.shutdown())
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
    
    logger.info("👋 Goodbye!")
    sys.exit(0)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks and OAuth callbacks."""
    
    def do_GET(self):
        """Handle GET requests for health check and OAuth callbacks."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        if path == "/health" or path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "moodtape-bot"}')
            
        elif path == "/auth/spotify/callback":
            self._handle_spotify_callback(query_params)
            
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')
    
    def _handle_spotify_callback(self, query_params):
        """Handle Spotify OAuth callback."""
        try:
            # Extract code and state from callback
            code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            error = query_params.get('error', [None])[0]
            
            if error:
                logger.error(f"Spotify OAuth error: {error}")
                self._send_callback_page(
                    "❌ Authorization Failed",
                    f"Error: {error}",
                    False
                )
                return
            
            if not code or not state:
                logger.error("Missing code or state in Spotify callback")
                self._send_callback_page(
                    "❌ Authorization Failed",
                    "Missing authorization code or state parameter.",
                    False
                )
                return
            
            # Process the callback asynchronously
            success = asyncio.run(self._process_spotify_callback(code, state))
            
            if success:
                self._send_callback_page(
                    "✅ Authorization Successful!",
                    "You can now return to Telegram and start creating playlists!",
                    True
                )
            else:
                self._send_callback_page(
                    "❌ Authorization Failed",
                    "Failed to process authorization. Please try again.",
                    False
                )
                
        except Exception as e:
            logger.error(f"Error handling Spotify callback: {e}")
            self._send_callback_page(
                "❌ Authorization Failed", 
                "An unexpected error occurred.",
                False
            )
    
    async def _process_spotify_callback(self, code: str, state: str) -> bool:
        """Process Spotify callback asynchronously."""
        try:
            return await handle_auth_callback(code, state)
        except Exception as e:
            logger.error(f"Error processing Spotify callback: {e}")
            return False
    
    def _send_callback_page(self, title: str, message: str, success: bool):
        """Send HTML response page for OAuth callback."""
        status_color = "#4CAF50" if success else "#f44336"
        icon = "✅" if success else "❌"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Moodtape - Spotify Authorization</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{
                    background: white;
                    border-radius: 20px;
                    padding: 40px;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    max-width: 400px;
                    width: 100%;
                }}
                .icon {{
                    font-size: 60px;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: {status_color};
                    margin-bottom: 20px;
                    font-size: 24px;
                }}
                p {{
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                    font-size: 16px;
                }}
                .telegram-button {{
                    background: #0088cc;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 25px;
                    text-decoration: none;
                    display: inline-block;
                    font-weight: bold;
                    font-size: 16px;
                    transition: background 0.3s;
                }}
                .telegram-button:hover {{
                    background: #006ba1;
                }}
                .footer {{
                    margin-top: 30px;
                    color: #999;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">{icon}</div>
                <h1>{title}</h1>
                <p>{message}</p>
                <a href="https://t.me/Mood_TAape_Music_bot" class="telegram-button">
                    🤖 Return to Telegram Bot
                </a>
                <div class="footer">
                    Moodtape - Music that matches your mood
                </div>
            </div>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass

def start_health_server():
    """Start a simple health check server for Render.com"""
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        logger.info(f"🏥 Health check server started on port 10000")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start health server: {e}")


def main() -> None:
    """Start the bot."""
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
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
    
    # Create application with better error handling
    global _application
    try:
        _application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        logger.info("✅ Telegram application created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create Telegram application: {e}")
        return
    
    # Add handlers
    
    # Command handlers
    _application.add_handler(CommandHandler("start", start_command))
    _application.add_handler(CommandHandler("help", help_command))
    _application.add_handler(CommandHandler("auth", auth_status_command))
    _application.add_handler(CommandHandler("preferences", preferences_command))
    _application.add_handler(CommandHandler("stats", stats_command))
    
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
    
    # RENDER.COM MULTIPLE INSTANCE FIX:
    # Zero-downtime deployments on Render can cause multiple bot instances
    # We use aggressive polling settings and better error handling
    
    try:
        logger.info("🔄 Starting bot with polling (multiple instance protection)")
        _application.run_polling(
            poll_interval=2.0,          # Увеличил интервал для снижения нагрузки
            timeout=20,                 # Уменьшил timeout для быстрого обнаружения конфликтов
            drop_pending_updates=True,  # Агрессивная очистка старых updates
            stop_signals=None,          # Отключаем стандартные сигналы, используем свои
            close_loop=False            # Не закрываем loop автоматически
        )
    except Exception as e:
        error_str = str(e).lower()
        if "conflict" in error_str and ("getUpdates" in error_str or "terminated" in error_str):
            logger.error("🚨 MULTIPLE BOT INSTANCES DETECTED!")
            logger.error("💡 This is likely due to Render.com zero-downtime deployment")
            logger.error("⏳ Waiting for old instance to terminate...")
            
            # Wait for old instance to die, then retry
            import time
            time.sleep(10)
            
            try:
                logger.info("🔄 Retrying bot startup after conflict resolution...")
                _application.run_polling(
                    poll_interval=3.0,
                    timeout=15,
                    drop_pending_updates=True,
                    stop_signals=None,
                    close_loop=False
                )
            except Exception as retry_error:
                logger.error(f"❌ Failed to start bot after retry: {retry_error}")
                raise
        else:
            logger.error(f"❌ Unexpected error starting bot: {e}")
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
        
        sys.exit(1) 