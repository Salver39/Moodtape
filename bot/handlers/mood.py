"""Mood description handler for Moodtape bot."""

from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager
from moodtape_core.gpt_parser import parse_mood_description, get_mood_summary
from moodtape_core.playlist_builder import create_user_playlist
from config.settings import DEFAULT_PLAYLIST_LENGTH
from bot.handlers.feedback import handle_comment_message, is_expecting_comment
from bot.middleware.rate_limiter import rate_limited

logger = get_logger(__name__)


@rate_limited(operation="playlist_creation")
async def mood_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle user's mood description text messages.
    
    - Check if user has selected a music service
    - Parse mood description using GPT-4o
    - Show parsed mood summary
    - Prepare for playlist generation (M4-M5)
    """
    user = update.effective_user
    message = update.message
    
    if not user or not message or not message.text:
        logger.warning("Received invalid message")
        return
    
    # Check if user is expecting to leave a comment
    if is_expecting_comment(user.id):
        await handle_comment_message(update, context)
        return
    
    # Get user session data
    user_language = user_sessions.get_session_data(user.id, "language", "en")
    music_service = user_sessions.get_session_data(user.id, "music_service")
    
    # Check if user has selected a music service
    if not music_service:
        logger.info(f"User {user.id} sent mood description without selecting service")
        
        # Send message asking to start with /start
        await message.reply_text(
            get_text("welcome", user_language),
            parse_mode="HTML"
        )
        return
    
    mood_description = message.text.strip()
    
    # Validate mood description length
    if len(mood_description) < 3:
        logger.info(f"User {user.id} sent too short mood description")
        await message.reply_text(
            get_text("describe_mood", user_language)
        )
        return
    
    if len(mood_description) > 500:
        logger.info(f"User {user.id} sent too long mood description")
        await message.reply_text(
            get_text("error", user_language)
        )
        return
    
    logger.info(f"Processing mood description from user {user.id}: {mood_description[:100]}...")
    
    # Send "processing" message
    processing_message = await message.reply_text(
        get_text("processing", user_language)
    )
    
    try:
        # Parse mood using GPT-4o with personalization
        mood_params = await parse_mood_description(
            description=mood_description,
            user_language=user_language,
            user_id=user.id,
            use_personalization=True
        )
        
        if mood_params is None:
            # GPT parsing failed
            logger.error(f"Failed to parse mood for user {user.id}")
            await processing_message.edit_text(
                get_text("error", user_language)
            )
            return
        
        # Save mood parameters to session
        user_sessions.set_session_data(user.id, "last_mood_params", mood_params)
        user_sessions.set_session_data(user.id, "last_mood_description", mood_description)
        
        # Generate mood summary
        mood_summary = await get_mood_summary(mood_params, user_language)
        
        # Prepare response message
        if user_language == "ru":
            response_text = f"🎵 Понял ваше настроение!\n\n{mood_summary}\n\n⏳ Создаю плейлист..."
        elif user_language == "es":
            response_text = f"🎵 ¡Entendí tu estado de ánimo!\n\n{mood_summary}\n\n⏳ Creando lista de reproducción..."
        else:  # English
            response_text = f"🎵 Got your mood!\n\n{mood_summary}\n\n⏳ Creating playlist..."
        
        await processing_message.edit_text(response_text)
        
        # Check if user is authorized for the selected service
        # Note: Apple Music doesn't require user tokens, only Spotify does
        if music_service == "spotify" and not db_manager.is_token_valid(user.id, music_service):
            if user_language == "ru":
                auth_needed_text = "❌ Необходима авторизация в Spotify.\n\nИспользуйте /start для авторизации."
            elif user_language == "es":
                auth_needed_text = "❌ Se necesita autorización de Spotify.\n\nUsa /start para autorizar."
            else:
                auth_needed_text = "❌ Spotify authorization required.\n\nUse /start to authorize."
            
            await context.bot.send_message(
                chat_id=user.id,
                text=auth_needed_text
            )
            return
        
        # Create the actual playlist
        playlist_info = create_user_playlist(
            user_id=user.id,
            service=music_service,
            mood_params=mood_params,
            mood_description=mood_description,
            playlist_length=DEFAULT_PLAYLIST_LENGTH
        )
        
        if playlist_info:
            # Success! Send playlist link
            playlist_url = playlist_info['url']
            track_count = playlist_info.get('track_count', 0)
            query_id = playlist_info.get('query_id')
            
            if user_language == "ru":
                success_text = f"🎉 Ваш плейлист готов!\n\n🎵 {playlist_info['name']}\n{track_count} треков\n\n{playlist_url}\n\nОцените результат:"
            elif user_language == "es":
                success_text = f"🎉 ¡Tu lista está lista!\n\n🎵 {playlist_info['name']}\n{track_count} canciones\n\n{playlist_url}\n\nCalifica el resultado:"
            else:
                success_text = f"🎉 Your playlist is ready!\n\n🎵 {playlist_info['name']}\n{track_count} tracks\n\n{playlist_url}\n\nRate the result:"
            
            # Add feedback buttons
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            feedback_keyboard = [
                [
                    InlineKeyboardButton(
                        get_text("thumbs_up", user_language),
                        callback_data=f"feedback:up:{query_id}"
                    ),
                    InlineKeyboardButton(
                        get_text("thumbs_down", user_language),
                        callback_data=f"feedback:down:{query_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💬 Комментарий" if user_language == "ru" 
                        else "💬 Comentario" if user_language == "es" 
                        else "💬 Comment",
                        callback_data=f"feedback:comment:{query_id}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(feedback_keyboard)
            
            await context.bot.send_message(
                chat_id=user.id,
                text=success_text,
                reply_markup=reply_markup
            )
        else:
            # Failed to create playlist
            if user_language == "ru":
                error_text = "❌ Не удалось создать плейлист. Попробуйте описать настроение по-другому или проверьте авторизацию."
            elif user_language == "es":
                error_text = "❌ No se pudo crear la lista. Intenta describir tu estado de ánimo de otra manera o verifica la autorización."
            else:
                error_text = "❌ Failed to create playlist. Try describing your mood differently or check your authorization."
            
            await context.bot.send_message(
                chat_id=user.id,
                text=error_text
            )
        
        logger.info(f"Successfully processed mood for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error processing mood for user {user.id}: {e}")
        await processing_message.edit_text(
            get_text("error", user_language)
        ) 