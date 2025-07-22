"""Administrative commands for rate limiter management."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager
from bot.middleware.rate_limiter import rate_limiter

logger = get_logger(__name__)

# Admin user IDs - add your Telegram user ID here
ADMIN_USER_IDS = {223842907}  # Replace with actual admin user IDs


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in ADMIN_USER_IDS


async def admin_rate_limit_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show rate limiter statistics."""
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    try:
        # Get rate limiter stats
        rl_stats = rate_limiter.get_rate_limiter_stats()
        
        # Get database violation stats
        db_stats = db_manager.get_rate_limit_stats(hours_back=24)
        
        # Format response
        message = f"""📊 **Rate Limiter Statistics**

**Current Status:**
• Tracked users: {rl_stats['total_users_tracked']}
• Blocked users: {rl_stats['blocked_users_count']}
• Whitelisted: {rl_stats['whitelisted_users_count']}
• Blacklisted: {rl_stats['blacklisted_users_count']}
• Premium users: {rl_stats['premium_users_count']}

**Active Users (Last 24h):**
• Last minute: {rl_stats['active_users']['last_minute']}
• Last hour: {rl_stats['active_users']['last_hour']}
• Last day: {rl_stats['active_users']['last_day']}

**Violations (Last 24h):**
• Total violations: {db_stats['total_violations']}
• In-memory violations: {rl_stats['total_violations_tracked']}

**Top Operations:**"""
        
        for op in db_stats['operations'][:3]:
            message += f"\n• {op['operation']}: {op['count']} violations"
        
        message += "\n\n**Top Violators:**"
        for user in db_stats['top_violators'][:5]:
            message += f"\n• User {user['user_id']}: {user['count']} violations"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        await update.message.reply_text("❌ Error getting statistics.")


async def admin_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show currently blocked users."""
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    try:
        blocked = rate_limiter.get_blocked_users()
        
        if not blocked:
            await update.message.reply_text("✅ No users are currently blocked.")
            return
        
        message = "🚫 **Currently Blocked Users:**\n\n"
        
        for user_info in blocked[:10]:  # Limit to 10 users
            user_id = user_info['user_id']
            remaining = user_info['seconds_remaining']
            
            if remaining > 0:
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                message += f"• User {user_id}: {time_str} remaining\n"
            else:
                message += f"• User {user_id}: Expired (will be removed)\n"
        
        if len(blocked) > 10:
            message += f"\n... and {len(blocked) - 10} more users"
        
        # Add unblock buttons for first 5 users
        if blocked:
            keyboard = []
            for user_info in blocked[:5]:
                user_id = user_info['user_id']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Unblock {user_id}",
                        callback_data=f"admin_unblock:{user_id}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting blocked users: {e}")
        await update.message.reply_text("❌ Error getting blocked users.")


async def admin_user_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get status for specific user."""
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /admin_user_status <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Get comprehensive user status
        status = rate_limiter.get_user_status(target_user_id)
        
        message = f"""👤 **User {target_user_id} Status:**

**Access Level:**
• Whitelisted: {'✅' if status['is_whitelisted'] else '❌'}
• Blacklisted: {'✅' if status['is_blacklisted'] else '❌'}
• Premium: {'✅' if status['is_premium'] else '❌'}
• Blocked: {'✅' if status['is_blocked'] else '❌'}

"""
        
        if status['is_blocked']:
            message += f"**Block Details:**\n"
            message += f"• Until: {status['blocked_until']}\n"
            message += f"• Remaining: {status['seconds_remaining']}s\n\n"
        
        if status['request_history']:
            hist = status['request_history']
            message += f"""**Request History:**
• Last minute: {hist['minute_requests']} requests
• Last hour: {hist['hour_requests']} requests  
• Last day: {hist['day_requests']} requests
• Total violations: {hist['total_violations']}
• Last warning: {hist['last_warning_time'] or 'Never'}
"""
        else:
            message += "**Request History:** No activity tracked\n"
        
        # Add action buttons
        keyboard = []
        
        if status['is_blocked']:
            keyboard.append([
                InlineKeyboardButton("🔓 Unblock", callback_data=f"admin_unblock:{target_user_id}")
            ])
        
        if not status['is_whitelisted']:
            keyboard.append([
                InlineKeyboardButton("⚪ Add to Whitelist", callback_data=f"admin_whitelist_add:{target_user_id}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("❌ Remove from Whitelist", callback_data=f"admin_whitelist_remove:{target_user_id}")
            ])
        
        if not status['is_blacklisted']:
            keyboard.append([
                InlineKeyboardButton("⚫ Add to Blacklist", callback_data=f"admin_blacklist_add:{target_user_id}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("❌ Remove from Blacklist", callback_data=f"admin_blacklist_remove:{target_user_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error getting user status: {e}")
        await update.message.reply_text("❌ Error getting user status.")


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin callback buttons."""
    query = update.callback_query
    user = query.from_user
    
    if not user or not is_admin(user.id):
        await query.answer("❌ Access denied.")
        return
    
    await query.answer()
    
    try:
        action, target_user_id = query.data.split(":", 1)
        target_user_id = int(target_user_id)
        
        if action == "admin_unblock":
            success = rate_limiter.unblock_user(target_user_id)
            if success:
                await query.edit_message_text(f"✅ User {target_user_id} has been unblocked.")
            else:
                await query.edit_message_text(f"❌ User {target_user_id} was not blocked.")
        
        elif action == "admin_whitelist_add":
            rate_limiter.add_to_whitelist(target_user_id)
            await query.edit_message_text(f"✅ User {target_user_id} added to whitelist.")
        
        elif action == "admin_whitelist_remove":
            rate_limiter.remove_from_whitelist(target_user_id)
            await query.edit_message_text(f"✅ User {target_user_id} removed from whitelist.")
        
        elif action == "admin_blacklist_add":
            rate_limiter.add_to_blacklist(target_user_id)
            await query.edit_message_text(f"✅ User {target_user_id} added to blacklist.")
        
        elif action == "admin_blacklist_remove":
            rate_limiter.remove_from_blacklist(target_user_id)
            await query.edit_message_text(f"✅ User {target_user_id} removed from blacklist.")
        
    except ValueError:
        await query.edit_message_text("❌ Invalid data format.")
    except Exception as e:
        logger.error(f"Error handling admin callback: {e}")
        await query.edit_message_text("❌ Error processing request.")


async def admin_violations_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent rate limit violations."""
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    try:
        # Get recent violations
        violations = db_manager.get_rate_limit_violations(hours_back=24, limit=20)
        
        if not violations:
            await update.message.reply_text("✅ No violations in the last 24 hours.")
            return
        
        message = "⚠️ **Recent Rate Limit Violations (24h):**\n\n"
        
        for v in violations:
            message += f"• User {v['user_id']}: {v['operation']} ({v['violation_type']})\n"
            message += f"  {v['timestamp']} - {v['cooldown_seconds']}s cooldown\n\n"
        
        if len(message) > 4000:  # Telegram message limit
            message = message[:4000] + "\n... (truncated)"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error getting violations history: {e}")
        await update.message.reply_text("❌ Error getting violations history.")


async def admin_cleanup_old_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up old rate limit data."""
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    try:
        # Clean up violations older than 30 days
        deleted_count = db_manager.cleanup_old_rate_limit_violations(days_to_keep=30)
        
        await update.message.reply_text(
            f"🧹 Cleaned up {deleted_count} old rate limit violations (>30 days)."
        )
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        await update.message.reply_text("❌ Error cleaning up data.") 