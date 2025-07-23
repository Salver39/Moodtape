"""Centralized error handling and fallback scenarios for production."""

import traceback
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager

logger = get_logger(__name__)

# Error recovery strategies
FALLBACK_STRATEGIES = {
    "openai_api_error": "retry_with_simpler_prompt",
    "spotify_api_error": "fallback_to_apple_music",
    "apple_music_api_error": "fallback_to_spotify",
    "database_error": "use_memory_session",
    "rate_limit_error": "queue_request",
    "network_timeout": "retry_with_backoff"
}

# Error messages for different contexts
ERROR_CONTEXTS = {
    "mood_parsing": {
        "ru": "❌ Не удалось обработать описание настроения. Попробуйте более простые слова.",
        "en": "❌ Failed to process mood description. Try using simpler words.",
        "es": "❌ Error al procesar la descripción del estado de ánimo. Intenta palabras más simples."
    },
    "playlist_creation": {
        "ru": "❌ Не удалось создать плейлист. Попробуйте другой музыкальный сервис или повторите позже.",
        "en": "❌ Failed to create playlist. Try another music service or retry later.",
        "es": "❌ Error al crear la lista de reproducción. Intenta otro servicio de música o inténtalo más tarde."
    },
    "service_auth": {
        "ru": "❌ Проблемы с авторизацией. Повторите процедуру авторизации через /start",
        "en": "❌ Authorization issues. Please re-authorize through /start",
        "es": "❌ Problemas de autorización. Vuelve a autorizar a través de /start"
    },
    "api_limit": {
        "ru": "⏱️ Достигнут лимит запросов. Попробуйте через несколько минут.",
        "en": "⏱️ Rate limit reached. Please try again in a few minutes.",
        "es": "⏱️ Límite de solicitudes alcanzado. Inténtalo en unos minutos."
    },
    "bot_conflict": {
        "ru": "🔄 Бот перезапускается для обновления. Попробуйте снова через несколько секунд.",
        "en": "🔄 Bot is restarting for updates. Please try again in a few seconds.",
        "es": "🔄 El bot se está reiniciando. Inténtalo de nuevo en unos segundos."
    },
    "general": {
        "ru": "❌ Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку.",
        "en": "❌ Technical error occurred. Please try later or contact support.",
        "es": "❌ Error técnico. Inténtalo más tarde o contacta soporte."
    }
}


class ErrorHandler:
    """Centralized error handler with recovery strategies."""
    
    def __init__(self):
        self.error_count = {}  # Track error frequency per user
        self.logger = get_logger(__name__)
    
    async def handle_error(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        error_type: str = "general",
        original_error: Optional[Exception] = None,
        recovery_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Handle errors with automatic recovery strategies.
        
        Args:
            update: Telegram update object
            context: Bot context
            error_type: Type of error for specific handling
            original_error: Original exception if available
            recovery_data: Data needed for recovery attempts
        
        Returns:
            bool: True if error was handled successfully, False otherwise
        """
        user_id = None
        user_language = "ru"
        
        if update and update.effective_user:
            user_id = update.effective_user.id
            user_language = user_sessions.get_session_data(user_id, "language", "ru")
        
        # Log the error
        error_msg = f"Error type: {error_type}"
        if original_error:
            error_msg += f", Exception: {str(original_error)}"
        if user_id:
            error_msg += f", User: {user_id}"
        
        self.logger.error(error_msg)
        if original_error:
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Track error frequency
        if user_id:
            self._track_user_error(user_id, error_type)
        
        # Try recovery strategy
        recovery_success = await self._attempt_recovery(
            update, context, error_type, recovery_data
        )
        
        if recovery_success:
            self.logger.info(f"Successfully recovered from {error_type} error")
            return True
        
        # Send user-friendly error message
        await self._send_error_message(update, context, error_type, user_language)
        
        # Log error to database for monitoring
        if user_id:
            try:
                db_manager.log_error(
                    user_id=user_id,
                    error_type=error_type,
                    error_message=str(original_error) if original_error else "Unknown error",
                    recovery_attempted=recovery_success
                )
            except Exception as e:
                self.logger.error(f"Failed to log error to database: {e}")
        
        return False
    
    def _track_user_error(self, user_id: int, error_type: str) -> None:
        """Track error frequency per user."""
        if user_id not in self.error_count:
            self.error_count[user_id] = {}
        
        if error_type not in self.error_count[user_id]:
            self.error_count[user_id][error_type] = 0
        
        self.error_count[user_id][error_type] += 1
        
        # Alert if user has too many errors
        if self.error_count[user_id][error_type] > 5:
            self.logger.warning(f"User {user_id} has {self.error_count[user_id][error_type]} {error_type} errors")
    
    async def _attempt_recovery(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        error_type: str, 
        recovery_data: Optional[Dict[str, Any]]
    ) -> bool:
        """Attempt to recover from the error."""
        
        strategy = FALLBACK_STRATEGIES.get(error_type)
        if not strategy or not recovery_data:
            return False
        
        try:
            if strategy == "retry_with_simpler_prompt":
                return await self._retry_simple_mood_parsing(update, context, recovery_data)
            
            elif strategy == "fallback_to_apple_music":
                return await self._fallback_to_service(update, context, "apple_music")
            
            elif strategy == "fallback_to_spotify":
                return await self._fallback_to_service(update, context, "spotify")
            
            elif strategy == "use_memory_session":
                return await self._use_memory_fallback(update, context, recovery_data)
            
            elif strategy == "retry_with_backoff":
                return await self._retry_with_backoff(update, context, recovery_data)
            
        except Exception as e:
            self.logger.error(f"Recovery strategy {strategy} failed: {e}")
        
        return False
    
    async def _retry_simple_mood_parsing(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        recovery_data: Dict[str, Any]
    ) -> bool:
        """Retry mood parsing with simpler prompt."""
        if not update or not update.effective_user:
            return False
        
        try:
            # Import here to avoid circular imports
            from moodtape_core.gpt_parser import parse_mood_description
            
            user_language = user_sessions.get_session_data(update.effective_user.id, "language", "ru")
            
            # Create a simpler mood description
            original_mood = recovery_data.get("mood_description", "")
            simple_mood = self._simplify_mood_description(original_mood, user_language)
            
            # Try parsing with simplified description
            simplified_params = await parse_mood_description(
                description=simple_mood,
                user_language=user_language,
                user_id=update.effective_user.id,
                use_personalization=False  # Disable personalization for recovery
            )
            
            if simplified_params:
                # Store simplified params for playlist creation
                user_sessions.set_session_data(
                    update.effective_user.id, 
                    "last_mood_params", 
                    simplified_params
                )
                return True
        
        except Exception as e:
            self.logger.error(f"Simple mood parsing recovery failed: {e}")
        
        return False
    
    async def _fallback_to_service(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        service: str
    ) -> bool:
        """Fallback to alternative music service."""
        if not update or not update.effective_user:
            return False
        
        try:
            # Check if alternative service is available
            from config.settings import MUSIC_SERVICES
            
            if not MUSIC_SERVICES.get(service, {}).get("enabled"):
                return False
            
            # Switch user to alternative service
            user_sessions.set_session_data(update.effective_user.id, "music_service", service)
            
            user_language = user_sessions.get_session_data(update.effective_user.id, "language", "ru")
            service_name = MUSIC_SERVICES[service]["name"]
            
            fallback_message = {
                "ru": f"🔄 Переключаемся на {service_name}...",
                "en": f"🔄 Switching to {service_name}...",
                "es": f"🔄 Cambiando a {service_name}..."
            }
            
            if update.message:
                await update.message.reply_text(fallback_message[user_language])
            elif update.callback_query:
                await update.callback_query.answer(fallback_message[user_language])
            
            return True
        
        except Exception as e:
            self.logger.error(f"Service fallback to {service} failed: {e}")
        
        return False
    
    async def _use_memory_fallback(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        recovery_data: Dict[str, Any]
    ) -> bool:
        """Use in-memory session instead of database."""
        try:
            # This is already implemented in user_sessions
            # Just log that we're using memory fallback
            self.logger.info("Using memory session fallback for database error")
            return True
        except Exception as e:
            self.logger.error(f"Memory fallback failed: {e}")
        
        return False
    
    async def _retry_with_backoff(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        recovery_data: Dict[str, Any]
    ) -> bool:
        """Retry operation with exponential backoff."""
        import asyncio
        
        retry_function = recovery_data.get("retry_function")
        retry_args = recovery_data.get("retry_args", [])
        retry_kwargs = recovery_data.get("retry_kwargs", {})
        max_retries = recovery_data.get("max_retries", 3)
        
        if not retry_function:
            return False
        
        for attempt in range(max_retries):
            try:
                # Exponential backoff: 1s, 2s, 4s
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)
                
                result = await retry_function(*retry_args, **retry_kwargs)
                if result:
                    self.logger.info(f"Retry succeeded on attempt {attempt + 1}")
                    return True
            
            except Exception as e:
                self.logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                continue
        
        return False
    
    def _simplify_mood_description(self, description: str, language: str) -> str:
        """Simplify mood description for better parsing."""
        # Extract key mood words
        mood_keywords = {
            "ru": ["грустный", "веселый", "спокойный", "энергичный", "романтичный", "мечтательный"],
            "en": ["sad", "happy", "calm", "energetic", "romantic", "dreamy"],
            "es": ["triste", "feliz", "tranquilo", "energético", "romántico", "soñador"]
        }
        
        keywords = mood_keywords.get(language, mood_keywords["ru"])
        description_lower = description.lower()
        
        # Find matching keywords
        found_keywords = [word for word in keywords if word in description_lower]
        
        if found_keywords:
            return " ".join(found_keywords[:2])  # Use top 2 matching keywords
        
        # Fallback to basic emotional states
        if language == "ru":
            return "нейтральное настроение"
        elif language == "es":
            return "estado de ánimo neutral"
        else:
            return "neutral mood"
    
    async def _send_error_message(
        self, 
        update: Optional[Update], 
        context: ContextTypes.DEFAULT_TYPE, 
        error_type: str, 
        language: str
    ) -> None:
        """Send user-friendly error message."""
        
        error_messages = ERROR_CONTEXTS.get(error_type, ERROR_CONTEXTS["general"])
        message = error_messages.get(language, error_messages["ru"])
        
        try:
            if update and update.message:
                await update.message.reply_text(message)
            elif update and update.callback_query:
                await update.callback_query.answer(message, show_alert=True)
            elif context and context.bot:
                # Fallback: try to get user from context
                if hasattr(context, 'user_data') and 'user_id' in context.user_data:
                    await context.bot.send_message(
                        chat_id=context.user_data['user_id'],
                        text=message
                    )
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")


# Global error handler instance
error_handler = ErrorHandler()


# Telegram bot error handler function
async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors for the Telegram bot."""
    
    if context.error:
        error_type = "general"
        
        # Classify error type - FIX: проверяем что error не None
        error_str = str(context.error).lower() if context.error else ""
        
        if "openai" in error_str or "gpt" in error_str:
            error_type = "mood_parsing"
        elif "spotify" in error_str:
            error_type = "spotify_api_error"  
        elif "apple" in error_str:
            error_type = "apple_music_api_error"
        elif "database" in error_str or "sqlite" in error_str:
            error_type = "database_error"
        elif "rate limit" in error_str or "too many requests" in error_str:
            error_type = "api_limit"
        elif "timeout" in error_str or "network" in error_str:
            error_type = "network_timeout"
        elif "conflict" in error_str and "getUpdates" in error_str:
            error_type = "bot_conflict"  # Новый тип ошибки для конфликтов ботов
        
        # Handle the error
        await error_handler.handle_error(
            update=update if isinstance(update, Update) else None,
            context=context,
            error_type=error_type,
            original_error=context.error
        )
    else:
        # Если нет ошибки в контексте, логируем как общую ошибку
        logger.warning("telegram_error_handler called without context.error")
        await error_handler.handle_error(
            update=update if isinstance(update, Update) else None,
            context=context,
            error_type="general",
            original_error=None
        ) 