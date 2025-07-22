"""Feedback handlers for playlist ratings."""

from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager
from bot.middleware.rate_limiter import rate_limited

logger = get_logger(__name__)


@rate_limited(operation="feedback")
async def handle_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle feedback callback (thumbs up/down/comment).
    
    Callback data format: "feedback:up|down|comment:query_id"
    """
    query = update.callback_query
    user = query.from_user
    
    if not user:
        logger.warning("Received feedback callback without user information")
        return
    
    await query.answer()
    
    try:
        # Parse callback data
        _, feedback_type, query_id = query.data.split(":", 2)
        
        user_language = user_sessions.get_session_data(user.id, "language", "en")
        
        if feedback_type == "comment":
            # Handle comment request
            await _handle_comment_request(update, context, query_id, user_language)
        else:
            # Handle thumbs up/down
            await _handle_rating_feedback(update, context, feedback_type, query_id, user_language)
        
    except ValueError as e:
        logger.error(f"Invalid feedback callback data: {query.data}")
        await query.edit_message_text(
            get_text("error", user_sessions.get_session_data(user.id, "language", "en"))
        )
    except Exception as e:
        logger.error(f"Error handling feedback callback: {e}")
        await query.edit_message_text(
            get_text("error", user_sessions.get_session_data(user.id, "language", "en"))
        )


async def _handle_rating_feedback(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    rating_str: str, 
    query_id: str, 
    user_language: str
) -> None:
    """Handle thumbs up/down feedback."""
    query = update.callback_query
    user = query.from_user
    
    # Convert rating to number
    rating = 1 if rating_str == "up" else -1
    
    # Get mood parameters from session for context
    mood_params = user_sessions.get_session_data(user.id, "last_mood_params")
    mood_params_dict = mood_params.__dict__ if mood_params else None
    
    # Save feedback to database
    db_manager.save_feedback(
        user_id=user.id,
        rating=rating,
        query_id=query_id,
        mood_params=mood_params_dict
    )
    
    logger.info(f"User {user.id} gave feedback: {rating_str} for query {query_id}")
    
    # Send thank you message
    thanks_text = get_text("feedback_thanks", user_language)
    
    # Add emoji based on rating
    if rating > 0:
        thanks_text = f"👍 {thanks_text}"
    else:
        thanks_text = f"👎 {thanks_text}"
    
    # Edit message to show feedback was received
    await query.edit_message_text(
        query.message.text + f"\n\n{thanks_text}",
        parse_mode="HTML"
    )


async def _handle_comment_request(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    query_id: str, 
    user_language: str
) -> None:
    """Handle comment request."""
    query = update.callback_query
    user = query.from_user
    
    # Set user session to expect a comment
    user_sessions.set_session_data(user.id, "expecting_comment", query_id)
    
    # Send comment prompt
    comment_prompt = get_text("comment_prompt", user_language)
    
    # Edit message to show comment was requested
    await query.edit_message_text(
        query.message.text + f"\n\n💬 Комментарий запрошен..." if user_language == "ru"
        else query.message.text + f"\n\n💬 Comentario solicitado..." if user_language == "es"
        else query.message.text + f"\n\n💬 Comment requested...",
        parse_mode="HTML"
    )
    
    # Send prompt message
    await context.bot.send_message(
        chat_id=user.id,
        text=comment_prompt
    )


async def handle_comment_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text comment message from user.
    
    This should be called from the main message handler when user is in comment state.
    """
    user = update.effective_user
    message = update.message
    
    if not user or not message or not message.text:
        return
    
    # Check if user is expecting a comment
    query_id = user_sessions.get_session_data(user.id, "expecting_comment")
    if not query_id:
        return  # User is not in comment state
    
    user_language = user_sessions.get_session_data(user.id, "language", "en")
    comment_text = message.text.strip()
    
    # Validate comment length
    if len(comment_text) < 3:
        await message.reply_text("Комментарий слишком короткий" if user_language == "ru"
                                else "Comentario muy corto" if user_language == "es"
                                else "Comment too short")
        return
    
    if len(comment_text) > 500:
        await message.reply_text("Комментарий слишком длинный" if user_language == "ru"
                                else "Comentario muy largo" if user_language == "es"
                                else "Comment too long")
        return
    
    # Get mood parameters from session for context
    mood_params = user_sessions.get_session_data(user.id, "last_mood_params")
    mood_params_dict = mood_params.__dict__ if mood_params else None
    
    # Save comment as feedback
    db_manager.save_feedback(
        user_id=user.id,
        rating=0,  # Neutral rating for comments
        query_id=query_id,
        feedback_text=comment_text,
        mood_params=mood_params_dict
    )
    
    # Clear comment state
    user_sessions.set_session_data(user.id, "expecting_comment", None)
    
    logger.info(f"User {user.id} left comment for query {query_id}: {comment_text[:50]}...")
    
    # Send thank you message
    thanks_text = get_text("comment_received", user_language)
    await message.reply_text(f"💬 {thanks_text}")


# Helper function to check if user is in comment state
def is_expecting_comment(user_id: int) -> bool:
    """Check if user is expecting to leave a comment."""
    return user_sessions.get_session_data(user_id, "expecting_comment") is not None 