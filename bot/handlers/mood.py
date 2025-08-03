"""Mood description handler for Moodtape bot."""

from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from config.settings import settings
from moodtape_core.gpt_parser import parse_mood
from moodtape_core.playlist_builder import PlaylistBuilder
from bot.middleware.rate_limiter import rate_limited

logger = get_logger(__name__)


@rate_limited(operation="playlist_creation")
async def mood_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mood description message."""
    user = update.effective_user
    message = update.message
    
    if not user or not message:
        return
    
    try:
        # Get user language and service
        user_language = user_sessions.get_session_data(user.id, "language", "ru")
        music_service = user_sessions.get_session_data(user.id, "music_service")
        
        if not music_service:
            await message.reply_text(
                get_text("no_service_selected", user_language),
                parse_mode="HTML"
            )
            return
        
        # Parse mood and create playlist
        mood_description = message.text
        playlist_builder = PlaylistBuilder(user.id, music_service)
        
        if not playlist_builder.is_service_available():
            await message.reply_text(
                get_text("service_not_available", user_language),
                parse_mode="HTML"
            )
            return
        
        # Send "processing" message
        processing_message = await message.reply_text(
            get_text("processing_mood", user_language),
            parse_mode="HTML"
        )
        
        # Parse mood description
        mood_params = await parse_mood(mood_description)
        
        if not mood_params:
            await processing_message.edit_text(
                get_text("mood_parse_error", user_language),
                parse_mode="HTML"
            )
            return
        
        # Build playlist
        playlist_info = await playlist_builder.build_mood_playlist(
            mood_params=mood_params,
            mood_description=mood_description,
            playlist_length=settings.DEFAULT_PLAYLIST_LENGTH
        )
        
        if not playlist_info:
            await processing_message.edit_text(
                get_text("playlist_creation_error", user_language),
                parse_mode="HTML"
            )
            return
        
        # Send success message with playlist link
        success_text = get_text(
            "playlist_created",
            user_language,
            url=playlist_info["url"],
            name=playlist_info["name"]
        )
        
        await processing_message.edit_text(
            success_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error handling mood message for user {user.id}: {e}")
        await message.reply_text(
            get_text("error", user_language),
            parse_mode="HTML"
        ) 