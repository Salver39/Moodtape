"""Internationalization (i18n) module for Moodtape bot."""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {"ru", "en", "es"}
DEFAULT_LANGUAGE = "en"

# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ru": {
        "welcome": "🎵 Добро пожаловать в Moodtape!\n\nЯ создаю персональные плейлисты на основе вашего настроения. Просто опишите, что вы чувствуете, и я подберу музыку под ваше состояние.\n\nВыберите музыкальный сервис:",
        "choose_service": "Выберите музыкальный сервис:",
        "spotify_button": "🟢 Spotify",
        "apple_music_button": "🍎 Apple Music",
        "service_selected": "Отлично! Вы выбрали {service}.\n\nТеперь опишите ваше настроение или ситуацию. Например:\n• \"осень, одиночество и тёплый чай\"\n• \"веселая вечеринка с друзьями\"\n• \"спокойный вечер дома\"",
        "describe_mood": "Опишите ваше настроение:",
        "processing": "🎵 Анализирую ваше настроение и подбираю музыку...",
        "error": "❌ Произошла ошибка. Попробуйте еще раз.",
        "playlist_ready": "🎉 Ваш плейлист готов! {link}\n\nОцените результат:",
        "feedback_thanks": "Спасибо за обратную связь! Это поможет мне лучше понимать ваши предпочтения.",
        "thumbs_up": "👍",
        "thumbs_down": "👎",
        "comment_prompt": "💬 Напишите комментарий о плейлисте:\n\nЧто вам понравилось или не понравилось? Какие треки были удачными?",
        "comment_received": "Спасибо за комментарий! Это поможет улучшить будущие рекомендации.",
        "personalization_applied": "🎯 Персонализация применена (уверенность: {confidence:.0%})",
        "language_changed": "Язык изменен на русский 🇷🇺",
    },
    "en": {
        "welcome": "🎵 Welcome to Moodtape!\n\nI create personalized playlists based on your mood. Just describe how you feel, and I'll find music that matches your vibe.\n\nChoose your music service:",
        "choose_service": "Choose your music service:",
        "spotify_button": "🟢 Spotify",
        "apple_music_button": "🍎 Apple Music",
        "service_selected": "Great! You've chosen {service}.\n\nNow describe your mood or situation. For example:\n• \"autumn, solitude and warm tea\"\n• \"fun party with friends\"\n• \"quiet evening at home\"",
        "describe_mood": "Describe your mood:",
        "processing": "🎵 Analyzing your mood and selecting music...",
        "error": "❌ An error occurred. Please try again.",
        "playlist_ready": "🎉 Your playlist is ready! {link}\n\nRate the result:",
        "feedback_thanks": "Thanks for your feedback! This helps me better understand your preferences.",
        "thumbs_up": "👍",
        "thumbs_down": "👎",
        "comment_prompt": "💬 Write a comment about the playlist:\n\nWhat did you like or dislike? Which tracks were good?",
        "comment_received": "Thanks for your comment! This will help improve future recommendations.",
        "personalization_applied": "🎯 Personalization applied (confidence: {confidence:.0%})",
        "language_changed": "Language changed to English 🇺🇸",
    },
    "es": {
        "welcome": "🎵 ¡Bienvenido a Moodtape!\n\nCreo listas de reproducción personalizadas basadas en tu estado de ánimo. Solo describe cómo te sientes y encontraré música que coincida con tu vibra.\n\nElige tu servicio de música:",
        "choose_service": "Elige tu servicio de música:",
        "spotify_button": "🟢 Spotify",
        "apple_music_button": "🍎 Apple Music",
        "service_selected": "¡Genial! Has elegido {service}.\n\nAhora describe tu estado de ánimo o situación. Por ejemplo:\n• \"otoño, soledad y té caliente\"\n• \"fiesta divertida con amigos\"\n• \"tarde tranquila en casa\"",
        "describe_mood": "Describe tu estado de ánimo:",
        "processing": "🎵 Analizando tu estado de ánimo y seleccionando música...",
        "error": "❌ Ocurrió un error. Inténtalo de nuevo.",
        "playlist_ready": "🎉 ¡Tu lista de reproducción está lista! {link}\n\nCalifica el resultado:",
        "feedback_thanks": "¡Gracias por tu comentario! Esto me ayuda a entender mejor tus preferencias.",
        "thumbs_up": "👍",
        "thumbs_down": "👎",
        "comment_prompt": "💬 Escribe un comentario sobre la lista:\n\n¿Qué te gustó o no te gustó? ¿Qué canciones fueron buenas?",
        "comment_received": "¡Gracias por tu comentario! Esto ayudará a mejorar las recomendaciones futuras.",
        "personalization_applied": "🎯 Personalización aplicada (confianza: {confidence:.0%})",
        "language_changed": "Idioma cambiado a español 🇪🇸",
    }
}


def get_user_language(language_code: str = None) -> str:
    """
    Determine user language based on Telegram language_code.
    
    Args:
        language_code: Telegram user language code (e.g., 'ru', 'en-US', 'es-ES')
    
    Returns:
        Supported language code ('ru', 'en', 'es')
    """
    if not language_code:
        return DEFAULT_LANGUAGE
    
    # Extract main language code (e.g., 'en' from 'en-US')
    main_lang = language_code.lower().split('-')[0]
    
    if main_lang in SUPPORTED_LANGUAGES:
        return main_lang
    
    # Fallback for similar languages
    if main_lang in ['uk', 'be', 'kk']:  # Ukrainian, Belarusian, Kazakh -> Russian
        return 'ru'
    elif main_lang in ['pt', 'it', 'fr', 'ca']:  # Portuguese, Italian, French, Catalan -> Spanish
        return 'es'
    
    return DEFAULT_LANGUAGE


def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Get translated text for given key and language.
    
    Args:
        key: Translation key
        language: Language code
        **kwargs: Format arguments for string formatting
    
    Returns:
        Translated and formatted text
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    try:
        text = TRANSLATIONS[language].get(key, TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))
        return text.format(**kwargs) if kwargs else text
    except Exception as e:
        logger.error(f"Translation error for key '{key}' in language '{language}': {e}")
        return key


class UserSession:
    """Simple in-memory user session storage."""
    
    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}
    
    def get_session(self, user_id: int) -> Dict[str, Any]:
        """Get user session data."""
        return self._sessions.get(user_id, {})
    
    def set_session_data(self, user_id: int, key: str, value: Any) -> None:
        """Set session data for user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        self._sessions[user_id][key] = value
    
    def get_session_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get specific session data for user."""
        return self._sessions.get(user_id, {}).get(key, default)
    
    def clear_session(self, user_id: int) -> None:
        """Clear user session."""
        self._sessions.pop(user_id, None)


# Global session instance
user_sessions = UserSession() 