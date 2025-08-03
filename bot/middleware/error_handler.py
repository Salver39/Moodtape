"""Error handling middleware for Moodtape bot."""

import html
import json
import traceback
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    
    # Extract error details
    error_type = type(context.error).__name__
    error_message = str(context.error)
    error_traceback = "".join(traceback.format_tb(context.error.__traceback__))
    
    # Log error
    logger.error(
        f"Exception while handling an update:\n"
        f"Type: {error_type}\n"
        f"Message: {error_message}\n"
        f"Traceback:\n{error_traceback}"
    )
    
    # Get user info if available
    user_id = None
    user_language = "en"
    
    if isinstance(update, Update) and update.effective_user:
        user_id = update.effective_user.id
        user_language = user_sessions.get_session_data(user_id, "language", "en")
    
    # Send error message to user
    if user_id:
        try:
            error_text = get_text("error", user_language)
            if isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(error_text)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
    
    # Send detailed error report to admin chat
    admin_ids = getattr(settings, "ADMIN_USER_IDS", [])
    if admin_ids:
        try:
            for admin_id in admin_ids:
                error_report = (
                    f"❌ <b>Error Report</b>\n\n"
                    f"<b>Type:</b> {html.escape(error_type)}\n"
                    f"<b>Message:</b> {html.escape(error_message)}\n"
                    f"<b>User ID:</b> {user_id}\n"
                    f"<b>Language:</b> {user_language}\n\n"
                    f"<pre>{html.escape(error_traceback)}</pre>"
                )
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=error_report,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Failed to send error report to admin: {e}")
    
    # Return None to handle the error gracefully
    return None 