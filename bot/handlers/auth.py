"""Spotify and Apple Music authentication handlers."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager
from auth.spotify_auth import spotify_auth
from auth.apple_auth import apple_music_client
from config.settings import settings

logger = get_logger(__name__)


async def handle_spotify_auth_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Spotify authorization request.
    
    - Generate auth URL for user
    - Send instructions for authorization
    """
    query = update.callback_query
    user = query.from_user
    
    if not user:
        logger.warning("Received auth request without user information")
        return
    
    await query.answer()
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    try:
        # Check if Spotify is configured
        if not spotify_auth.is_configured():
            logger.error("Spotify OAuth not configured")
            await query.edit_message_text(
                get_text("error", user_language)
            )
            return
        
        # Generate authorization URL
        auth_url = spotify_auth.get_auth_url(user.id)
        
        # Create inline keyboard with auth URL
        keyboard = [[
            InlineKeyboardButton(
                get_text("spotify_button", user_language),
                url=auth_url
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Prepare instructions message
        if user_language == "ru":
            instructions = (
                "🔐 Авторизация Spotify\n\n"
                "Для создания персональных плейлистов мне нужен доступ к вашему Spotify аккаунту.\n\n"
                "👆 Нажмите кнопку выше для авторизации\n\n"
                "ℹ️ Я получу доступ только для:\n"
                "• Чтения ваших лайков и топ-треков\n"
                "• Создания плейлистов в вашем аккаунте\n\n"
                "После авторизации просто опишите ваше настроение!"
            )
        elif user_language == "es":
            instructions = (
                "🔐 Autorización de Spotify\n\n"
                "Para crear listas personalizadas necesito acceso a tu cuenta de Spotify.\n\n"
                "👆 Presiona el botón de arriba para autorizar\n\n"
                "ℹ️ Solo obtendré acceso para:\n"
                "• Leer tus me gusta y canciones top\n"
                "• Crear listas en tu cuenta\n\n"
                "¡Después de autorizar, simplemente describe tu estado de ánimo!"
            )
        else:  # English
            instructions = (
                "🔐 Spotify Authorization\n\n"
                "To create personalized playlists, I need access to your Spotify account.\n\n"
                "👆 Click the button above to authorize\n\n"
                "ℹ️ I'll only get access to:\n"
                "• Read your liked songs and top tracks\n"
                "• Create playlists in your account\n\n"
                "After authorization, just describe your mood!"
            )
        
        await query.edit_message_text(
            instructions,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        logger.info(f"Sent Spotify auth request to user {user.id}")
        
    except Exception as e:
        logger.error(f"Error handling Spotify auth request for user {user.id}: {e}")
        await query.edit_message_text(
            get_text("error", user_language)
        )


async def check_spotify_auth_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check Spotify authorization status and handle accordingly."""
    query = update.callback_query
    user = query.from_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    # Save selected service
    user_sessions.set_session_data(user.id, "music_service", "spotify")
    
    # Check if Spotify is enabled
    if not settings.MUSIC_SERVICES["spotify"]["enabled"]:
        await query.edit_message_text(
            get_text("spotify_not_available", user_language),
            parse_mode="HTML"
        )
        return
    
    # Check if user is already authorized
    if db_manager.is_token_valid(user.id, "spotify"):
        await query.edit_message_text(
            get_text("spotify_already_authorized", user_language),
            parse_mode="HTML"
        )
        return
    
    try:
        # Generate auth URL
        auth_url = spotify_auth.get_auth_url(user.id)
        
        # Create keyboard with auth link
        keyboard = [[
            InlineKeyboardButton(
                get_text("spotify_auth_button", user_language),
                url=auth_url
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send auth instructions
        await query.edit_message_text(
            get_text("spotify_auth_instructions", user_language),
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error generating Spotify auth URL for user {user.id}: {e}")
        await query.edit_message_text(
            get_text("error", user_language),
            parse_mode="HTML"
        )


async def check_apple_music_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check Apple Music availability and handle accordingly."""
    query = update.callback_query
    user = query.from_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    # Save selected service
    user_sessions.set_session_data(user.id, "music_service", "apple_music")
    
    # Check if Apple Music is enabled and configured
    if not settings.MUSIC_SERVICES["apple_music"]["enabled"]:
        await query.edit_message_text(
            get_text("apple_music_not_available", user_language),
            parse_mode="HTML"
        )
        return
    
    if not apple_music_client.is_configured():
        await query.edit_message_text(
            get_text("apple_music_not_configured", user_language),
            parse_mode="HTML"
        )
        return
    
    # Apple Music is ready to use
    await query.edit_message_text(
        get_text("apple_music_ready", user_language),
        parse_mode="HTML"
    )


async def handle_auth_callback(code: str, state: str) -> bool:
    """
    Handle OAuth callback from music service.
    
    This would typically be called by a web server handling the redirect.
    For now, it's a utility function that can be called manually.
    
    Args:
        code: Authorization code
        state: State parameter (user_id)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        user_id = int(state)
        
        # Handle Spotify callback
        token_info = spotify_auth.handle_callback(code, state)
        
        if token_info:
            logger.info(f"Successfully authorized user {user_id} for Spotify")
            
            # Set service in session (in case it wasn't set before)
            user_sessions.set_session_data(user_id, "music_service", "spotify")
            
            # Send success message to user with next steps
            await _send_auth_success_message(user_id)
            
            return True
        else:
            logger.error(f"Failed to authorize user {user_id} for Spotify")
            return False
    
    except Exception as e:
        logger.error(f"Error handling auth callback: {e}")
        return False


async def _send_auth_success_message(user_id: int) -> None:
    """Send authorization success message with next steps to user."""
    try:
        # Import here to avoid circular imports
        import asyncio
        from telegram.ext import Application
        from config.settings import TELEGRAM_BOT_TOKEN
        
        user_language = user_sessions.get_session_data(user_id, "language", "ru")
        
        if user_language == "ru":
            success_text = (
                "🎉 <b>Отлично! Spotify авторизация завершена!</b>\n\n"
                "Теперь я могу создавать персональные плейлисты на основе вашего настроения.\n\n"
                "📝 <b>Просто опишите ваше настроение:</b>\n"
                "• \"веселая музыка для утренней пробежки\"\n"
                "• \"спокойный вечер дома с книгой\"\n"
                "• \"грустное настроение под дождем\"\n\n"
                "🎵 Я создам идеальный плейлист для вашего состояния!"
            )
        elif user_language == "es":
            success_text = (
                "🎉 <b>¡Perfecto! ¡Autorización de Spotify completada!</b>\n\n"
                "Ahora puedo crear listas de reproducción personalizadas basadas en tu estado de ánimo.\n\n"
                "📝 <b>Simplemente describe tu estado de ánimo:</b>\n"
                "• \"música alegre para correr por la mañana\"\n"
                "• \"noche tranquila en casa con un libro\"\n"
                "• \"estado de ánimo triste bajo la lluvia\"\n\n"
                "🎵 ¡Crearé la lista perfecta para tu estado!"
            )
        else:  # English
            success_text = (
                "🎉 <b>Great! Spotify authorization completed!</b>\n\n"
                "Now I can create personalized playlists based on your mood.\n\n"
                "📝 <b>Just describe your mood:</b>\n"
                "• \"energetic workout\"\n"
                "• \"quiet evening at home\"\n"
                "• \"melancholy and rain\"\n\n"
                "🎵 I'll create the perfect playlist for your mood!"
            )
        
        # Create a temporary bot instance for sending message
        try:
            from telegram import Bot
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            
            async with bot:
                await bot.send_message(
                    chat_id=user_id,
                    text=success_text,
                    parse_mode="HTML"
                )
            
            logger.info(f"Sent authorization success notification to user {user_id}")
            
        except Exception as bot_error:
            logger.error(f"Error creating bot instance for message: {bot_error}")
            
    except Exception as e:
        logger.error(f"Error sending auth success message to user {user_id}: {e}")


# Command to manually check authorization status
async def auth_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /auth command to check service authorization status."""
    user = update.effective_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    # Check Spotify status
    spotify_status = "✅" if db_manager.is_token_valid(user.id, "spotify") else "❌"
    
    # Check Apple Music status
    apple_status = "✅" if apple_music_client.is_configured() else "❌"
    
    # Prepare status message
    if user_language == "ru":
        status_text = (
            "🔐 <b>Статус авторизации:</b>\n\n"
            f"Spotify: {spotify_status}\n"
            f"Apple Music: {apple_status}\n\n"
            "Используйте /start для настройки сервисов."
        )
    elif user_language == "es":
        status_text = (
            "🔐 <b>Estado de autorización:</b>\n\n"
            f"Spotify: {spotify_status}\n"
            f"Apple Music: {apple_status}\n\n"
            "Usa /start para configurar servicios."
        )
    else:  # English
        status_text = (
            "🔐 <b>Authorization Status:</b>\n\n"
            f"Spotify: {spotify_status}\n"
            f"Apple Music: {apple_status}\n\n"
            "Use /start to configure services."
        )
    
    await update.message.reply_text(status_text, parse_mode="HTML")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /logout command to revoke Spotify authorization."""
    user = update.effective_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    try:
        # Delete Spotify token from database
        db_manager.delete_user_token(user.id, "spotify")
        
        # Clear service selection from session
        user_sessions.set_session_data(user.id, "music_service", None)
        
        # Send confirmation message
        if user_language == "ru":
            message = (
                "✅ Вы успешно вышли из Spotify!\n\n"
                "Для создания новых плейлистов вам нужно будет заново авторизоваться.\n"
                "Используйте /start для авторизации."
            )
        elif user_language == "es":
            message = (
                "✅ ¡Has cerrado sesión de Spotify exitosamente!\n\n"
                "Necesitarás volver a autorizar para crear nuevas listas.\n"
                "Usa /start para autorizar."
            )
        else:
            message = (
                "✅ Successfully logged out from Spotify!\n\n"
                "You'll need to re-authorize to create new playlists.\n"
                "Use /start to authorize."
            )
        
        await update.message.reply_text(message)
        logger.info(f"User {user.id} logged out from Spotify")
        
    except Exception as e:
        logger.error(f"Error logging out user {user.id} from Spotify: {e}")
        await update.message.reply_text(get_text("error", user_language)) 