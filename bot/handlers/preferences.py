"""User preferences and personalization statistics handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager
from moodtape_core.personalization import personalization_engine
from bot.middleware.rate_limiter import rate_limited

logger = get_logger(__name__)


@rate_limited(operation="general")
async def preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /preferences command to show user's learned preferences."""
    user = update.effective_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "en")
    
    try:
        # Analyze user preferences
        user_preferences = personalization_engine.analyzer.analyze_user_feedback(user.id)
        
        if user_preferences.total_feedback_count == 0:
            if user_language == "ru":
                no_data_text = (
                    "📊 Персональные предпочтения\n\n"
                    "❌ Пока нет данных для анализа.\n\n"
                    "Создайте несколько плейлистов и оцените их, чтобы система изучила ваши предпочтения!"
                )
            elif user_language == "es":
                no_data_text = (
                    "📊 Preferencias Personales\n\n"
                    "❌ Aún no hay datos para analizar.\n\n"
                    "¡Crea algunas listas y califícalas para que el sistema aprenda tus preferencias!"
                )
            else:
                no_data_text = (
                    "📊 Personal Preferences\n\n"
                    "❌ No data to analyze yet.\n\n"
                    "Create some playlists and rate them so the system can learn your preferences!"
                )
            
            await update.message.reply_text(no_data_text)
            return
        
        # Generate preferences report
        preferences_text = _generate_preferences_report(user_preferences, user_language)
        
        await update.message.reply_text(preferences_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing preferences for user {user.id}: {e}")
        await update.message.reply_text(get_text("error", user_language))


@rate_limited(operation="general")
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command to show user's usage statistics."""
    user = update.effective_user
    
    if not user:
        return
    
    user_language = user_sessions.get_session_data(user.id, "language", "en")
    
    try:
        # Get user's query history and feedback
        query_history = db_manager.get_user_query_history(user.id, limit=50)
        feedback_history = db_manager.get_user_feedback_history(user.id, limit=50)
        
        # Generate stats report
        stats_text = _generate_stats_report(query_history, feedback_history, user_language)
        
        await update.message.reply_text(stats_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing stats for user {user.id}: {e}")
        await update.message.reply_text(get_text("error", user_language))


def _generate_preferences_report(user_preferences, language: str) -> str:
    """Generate a human-readable preferences report."""
    
    if language == "ru":
        header = "📊 Ваши музыкальные предпочтения\n\n"
        confidence_text = f"🎯 Уверенность системы: {user_preferences.confidence_score:.0%}\n"
        feedback_text = f"📈 Всего отзывов: {user_preferences.total_feedback_count} (👍 {user_preferences.positive_feedback_count})\n\n"
        
        if user_preferences.confidence_score < 0.3:
            low_confidence = "⚠️ Низкая уверенность - нужно больше отзывов для лучшей персонализации\n\n"
        else:
            low_confidence = ""
        
        params_header = "🎵 Музыкальные параметры:\n"
        genres_header = "🎭 Предпочтения по жанрам:\n"
        tags_header = "🏷️ Предпочтения по настроению:\n"
    elif language == "es":
        header = "📊 Tus preferencias musicales\n\n"
        confidence_text = f"🎯 Confianza del sistema: {user_preferences.confidence_score:.0%}\n"
        feedback_text = f"📈 Total de comentarios: {user_preferences.total_feedback_count} (👍 {user_preferences.positive_feedback_count})\n\n"
        
        if user_preferences.confidence_score < 0.3:
            low_confidence = "⚠️ Baja confianza - se necesitan más comentarios para mejor personalización\n\n"
        else:
            low_confidence = ""
        
        params_header = "🎵 Parámetros musicales:\n"
        genres_header = "🎭 Preferencias de género:\n"
        tags_header = "🏷️ Preferencias de estado de ánimo:\n"
    else:  # English
        header = "📊 Your Music Preferences\n\n"
        confidence_text = f"🎯 System confidence: {user_preferences.confidence_score:.0%}\n"
        feedback_text = f"📈 Total feedback: {user_preferences.total_feedback_count} (👍 {user_preferences.positive_feedback_count})\n\n"
        
        if user_preferences.confidence_score < 0.3:
            low_confidence = "⚠️ Low confidence - more feedback needed for better personalization\n\n"
        else:
            low_confidence = ""
        
        params_header = "🎵 Musical parameters:\n"
        genres_header = "🎭 Genre preferences:\n"
        tags_header = "🏷️ Mood preferences:\n"
    
    # Musical parameters
    params_lines = []
    if abs(user_preferences.valence_bias) > 0.1:
        direction = "более позитивная" if user_preferences.valence_bias > 0 else "более меланхоличная"
        if language == "es":
            direction = "más positiva" if user_preferences.valence_bias > 0 else "más melancólica"
        elif language == "en":
            direction = "more positive" if user_preferences.valence_bias > 0 else "more melancholic"
        params_lines.append(f"• Музыка: {direction}" if language == "ru" else 
                           f"• Música: {direction}" if language == "es" else 
                           f"• Music: {direction}")
    
    if abs(user_preferences.energy_bias) > 0.1:
        direction = "более энергичная" if user_preferences.energy_bias > 0 else "более спокойная"
        if language == "es":
            direction = "más energética" if user_preferences.energy_bias > 0 else "más tranquila"
        elif language == "en":
            direction = "more energetic" if user_preferences.energy_bias > 0 else "calmer"
        params_lines.append(f"• Энергия: {direction}" if language == "ru" else 
                           f"• Energía: {direction}" if language == "es" else 
                           f"• Energy: {direction}")
    
    if abs(user_preferences.tempo_bias) > 10:
        direction = "быстрее" if user_preferences.tempo_bias > 0 else "медленнее"
        if language == "es":
            direction = "más rápido" if user_preferences.tempo_bias > 0 else "más lento"
        elif language == "en":
            direction = "faster" if user_preferences.tempo_bias > 0 else "slower"
        params_lines.append(f"• Темп: {direction}" if language == "ru" else 
                           f"• Tempo: {direction}" if language == "es" else 
                           f"• Tempo: {direction}")
    
    # Genre preferences
    genre_lines = []
    sorted_genres = sorted(user_preferences.genre_preferences.items(), 
                          key=lambda x: abs(x[1]), reverse=True)
    for genre, score in sorted_genres[:5]:
        if abs(score) > 0.2:
            emoji = "👍" if score > 0 else "👎"
            genre_lines.append(f"• {emoji} {genre.title()}")
    
    # Mood tag preferences
    tag_lines = []
    sorted_tags = sorted(user_preferences.mood_tag_preferences.items(), 
                        key=lambda x: abs(x[1]), reverse=True)
    for tag, score in sorted_tags[:5]:
        if abs(score) > 0.2:
            emoji = "👍" if score > 0 else "👎"
            tag_lines.append(f"• {emoji} {tag.title()}")
    
    # Assemble report
    report = header + confidence_text + feedback_text + low_confidence
    
    if params_lines:
        report += params_header + "\n".join(params_lines) + "\n\n"
    
    if genre_lines:
        report += genres_header + "\n".join(genre_lines) + "\n\n"
    
    if tag_lines:
        report += tags_header + "\n".join(tag_lines) + "\n\n"
    
    if not params_lines and not genre_lines and not tag_lines:
        if language == "ru":
            report += "📊 Пока недостаточно данных для детального анализа предпочтений."
        elif language == "es":
            report += "📊 Aún no hay suficientes datos para análisis detallado de preferencias."
        else:
            report += "📊 Not enough data yet for detailed preference analysis."
    
    return report


def _generate_stats_report(query_history, feedback_history, language: str) -> str:
    """Generate a usage statistics report."""
    
    # Calculate statistics
    total_queries = len(query_history)
    successful_queries = len([q for q in query_history if q['success']])
    total_feedback = len(feedback_history)
    positive_feedback = len([f for f in feedback_history if f['rating'] > 0])
    negative_feedback = len([f for f in feedback_history if f['rating'] < 0])
    comments = len([f for f in feedback_history if f.get('feedback_text')])
    
    success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
    positive_rate = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0
    
    # Get service usage
    service_usage = {}
    for query in query_history:
        service = query.get('service', 'unknown')
        service_usage[service] = service_usage.get(service, 0) + 1
    
    if language == "ru":
        header = "📈 Статистика использования\n\n"
        queries_text = f"🎵 Всего плейлистов: {total_queries}\n"
        success_text = f"✅ Успешно создано: {successful_queries} ({success_rate:.0f}%)\n"
        feedback_text = f"💬 Всего отзывов: {total_feedback}\n"
        positive_text = f"👍 Положительных: {positive_feedback} ({positive_rate:.0f}%)\n"
        negative_text = f"👎 Отрицательных: {negative_feedback}\n"
        comments_text = f"💬 Комментариев: {comments}\n\n"
        services_header = "🎧 Использование сервисов:\n"
    elif language == "es":
        header = "📈 Estadísticas de uso\n\n"
        queries_text = f"🎵 Total de listas: {total_queries}\n"
        success_text = f"✅ Creadas exitosamente: {successful_queries} ({success_rate:.0f}%)\n"
        feedback_text = f"💬 Total de comentarios: {total_feedback}\n"
        positive_text = f"👍 Positivos: {positive_feedback} ({positive_rate:.0f}%)\n"
        negative_text = f"👎 Negativos: {negative_feedback}\n"
        comments_text = f"💬 Comentarios de texto: {comments}\n\n"
        services_header = "🎧 Uso de servicios:\n"
    else:  # English
        header = "📈 Usage Statistics\n\n"
        queries_text = f"🎵 Total playlists: {total_queries}\n"
        success_text = f"✅ Successfully created: {successful_queries} ({success_rate:.0f}%)\n"
        feedback_text = f"💬 Total feedback: {total_feedback}\n"
        positive_text = f"👍 Positive: {positive_feedback} ({positive_rate:.0f}%)\n"
        negative_text = f"👎 Negative: {negative_feedback}\n"
        comments_text = f"💬 Text comments: {comments}\n\n"
        services_header = "🎧 Service usage:\n"
    
    # Service lines
    service_lines = []
    for service, count in service_usage.items():
        percentage = (count / total_queries * 100) if total_queries > 0 else 0
        service_name = "Spotify" if service == "spotify" else "Apple Music" if service == "apple_music" else service
        service_lines.append(f"• {service_name}: {count} ({percentage:.0f}%)")
    
    # Assemble report
    report = (header + queries_text + success_text + feedback_text + 
             positive_text + negative_text + comments_text)
    
    if service_lines:
        report += services_header + "\n".join(service_lines)
    
    return report 