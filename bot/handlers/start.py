"""Start command handler for Moodtape bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.i18n import get_user_language, get_text, user_sessions
from utils.logger import get_logger
from config.settings import MUSIC_SERVICES
from bot.handlers.auth import check_spotify_auth_status, check_apple_music_availability
from bot.middleware.rate_limiter import rate_limited  # Включено обратно с улучшенной обработкой ошибок

logger = get_logger(__name__)


@rate_limited(operation="general")  # Включено обратно с улучшенной обработкой ошибок
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    
    - Determine user language from Telegram language_code
    - Save language to user session
    - Show welcome message with music service selection
    """
    user = update.effective_user
    
    if not user:
        logger.warning("Received /start command without user information")
        return
    
    # Log user start
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    logger.info(f"User {user.id} ({user.username or 'N/A'}) started bot with language: {user_language}")
    
    try:
        # First, get the user's language preference from session or detect from Telegram
        if not user_language or user_language not in {"ru", "en", "es"}:
            # Auto-detect from Telegram user language
            user_language = get_user_language(user.language_code or "ru")
            user_sessions.set_session_data(user.id, "language", user_language)
        
        # Show welcome message with service selection
        welcome_text = get_text("welcome", user_language)
        
        keyboard = [
            [InlineKeyboardButton(
                get_text("spotify_button", user_language),
                callback_data="service:spotify"
            )],
            [InlineKeyboardButton(
                get_text("apple_music_button", user_language),
                callback_data="service:apple_music"
            )],
            [InlineKeyboardButton(
                get_text("language_settings", user_language),
                callback_data="show_language_menu"
            )]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user.id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in start handler for user {user.id}: {e}")
        await context.bot.send_message(
            chat_id=user.id,
            text=get_text("error", user_language)
        )


async def service_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle music service selection callback.
    
    - Save selected service to user session
    - Show confirmation and next steps
    """
    query = update.callback_query
    user = query.from_user
    
    if not user:
        logger.warning("Received callback without user information")
        return
    
    # Acknowledge the callback
    await query.answer()
    
    # Extract service from callback data
    try:
        _, service_key = query.data.split(":", 1)
    except ValueError:
        logger.error(f"Invalid callback data format: {query.data}")
        return
    
    # Validate service
    if service_key not in MUSIC_SERVICES or not MUSIC_SERVICES[service_key]["enabled"]:
        logger.error(f"Invalid or disabled service selected: {service_key}")
        return
    
    logger.info(f"User {user.id} selected music service: {service_key}")
    
    # Handle service-specific authorization
    if service_key == "spotify":
        await check_spotify_auth_status(update, context)
    elif service_key == "apple_music":
        await check_apple_music_availability(update, context)
    else:
        # For any other services, use the old flow
        user_language = user_sessions.get_session_data(user.id, "language", "ru")
        user_sessions.set_session_data(user.id, "music_service", service_key)
        
        service_name = MUSIC_SERVICES[service_key]["name"]
        confirmation_text = get_text(
            "service_selected", 
            user_language, 
            service=service_name
        )
        
        await query.edit_message_text(
            confirmation_text,
            parse_mode="HTML"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    user = update.effective_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "ru")
    
    if user_language == "ru":
        help_text = (
            "🎵 <b>Moodtape - Музыка по настроению</b>\n\n"
            "<b>Основные команды:</b>\n"
            "• /start - Начать работу с ботом\n"
            "• /help - Показать это сообщение\n"
            "• /auth - Проверить статус авторизации\n"
            "• /preferences - Показать изученные предпочтения\n"
            "• /stats - Статистика использования\n\n"
            "<b>Как использовать:</b>\n"
            "1. Выберите музыкальный сервис (Spotify или Apple Music)\n"
            "2. Опишите своё настроение любыми словами\n"
            "3. Получите персональный плейлист\n"
            "4. Оцените результат 👍👎 или оставьте комментарий 💬\n\n"
            "<b>Персонализация:</b>\n"
            "Бот изучает ваши предпочтения на основе оценок и автоматически улучшает рекомендации!"
        )
    elif user_language == "es":
        help_text = (
            "🎵 <b>Moodtape - Música por estado de ánimo</b>\n\n"
            "<b>Comandos principales:</b>\n"
            "• /start - Empezar a usar el bot\n"
            "• /help - Mostrar este mensaje\n"
            "• /auth - Verificar estado de autorización\n"
            "• /preferences - Mostrar preferencias aprendidas\n"
            "• /stats - Estadísticas de uso\n\n"
            "<b>Cómo usar:</b>\n"
            "1. Elige servicio de música (Spotify o Apple Music)\n"
            "2. Describe tu estado de ánimo con cualquier palabra\n"
            "3. Recibe una lista personalizada\n"
            "4. Califica el resultado 👍👎 o deja un comentario 💬\n\n"
            "<b>Personalización:</b>\n"
            "¡El bot aprende tus preferencias basándose en calificaciones y mejora automáticamente las recomendaciones!"
        )
    else:  # English
        help_text = (
            "🎵 <b>Moodtape - Music by Mood</b>\n\n"
            "<b>Main commands:</b>\n"
            "• /start - Start using the bot\n"
            "• /help - Show this message\n"
            "• /auth - Check authorization status\n"
            "• /preferences - Show learned preferences\n"
            "• /stats - Usage statistics\n\n"
            "<b>How to use:</b>\n"
            "1. Choose music service (Spotify or Apple Music)\n"
            "2. Describe your mood with any words\n"
            "3. Get a personalized playlist\n"
            "4. Rate the result 👍👎 or leave a comment 💬\n\n"
            "<b>Personalization:</b>\n"
            "The bot learns your preferences based on ratings and automatically improves recommendations!"
        )
    
    await update.message.reply_text(help_text, parse_mode="HTML") 