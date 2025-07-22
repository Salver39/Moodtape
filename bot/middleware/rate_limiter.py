"""Rate limiting middleware for production bot."""

import time
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass
from telegram import Update
from telegram.ext import ContextTypes

from utils.i18n import get_text, user_sessions
from utils.logger import get_logger
from utils.database import db_manager

logger = get_logger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    cooldown_seconds: int = 60  # Cooldown after exceeding limits


@dataclass
class UserRequestHistory:
    """Track user request history."""
    user_id: int
    minute_requests: List[float]  # Timestamps
    hour_requests: List[float]
    day_requests: List[float]
    last_warning_time: float = 0
    total_violations: int = 0


class RateLimiter:
    """Rate limiter for bot requests."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.user_histories: Dict[int, UserRequestHistory] = {}
        self.blocked_users: Dict[int, float] = {}  # user_id -> unblock_time
        
        # Access control lists
        self.whitelist: set = set()  # Users exempt from rate limiting
        self.blacklist: set = set()  # Users with stricter limits
        
        # Rate limits for different operations
        self.limits = {
            "playlist_creation": RateLimit(
                requests_per_minute=3,
                requests_per_hour=15,
                requests_per_day=50,
                cooldown_seconds=300  # 5 minutes
            ),
            "mood_parsing": RateLimit(
                requests_per_minute=5,
                requests_per_hour=30,
                requests_per_day=100,
                cooldown_seconds=60  # 1 minute
            ),
            "feedback": RateLimit(
                requests_per_minute=10,
                requests_per_hour=50,
                requests_per_day=200,
                cooldown_seconds=30  # 30 seconds
            ),
            "general": RateLimit(
                requests_per_minute=10,
                requests_per_hour=60,
                requests_per_day=300,
                cooldown_seconds=60  # 1 minute
            )
        }
        
        # Blacklist users get stricter limits (half of normal)
        self.blacklist_limits = {
            "playlist_creation": RateLimit(
                requests_per_minute=1,
                requests_per_hour=7,
                requests_per_day=25,
                cooldown_seconds=600  # 10 minutes
            ),
            "mood_parsing": RateLimit(
                requests_per_minute=2,
                requests_per_hour=15,
                requests_per_day=50,
                cooldown_seconds=120  # 2 minutes
            ),
            "feedback": RateLimit(
                requests_per_minute=5,
                requests_per_hour=25,
                requests_per_day=100,
                cooldown_seconds=60  # 1 minute
            ),
            "general": RateLimit(
                requests_per_minute=5,
                requests_per_hour=30,
                requests_per_day=150,
                cooldown_seconds=120  # 2 minutes
            )
        }
        
        # Premium users (can have higher limits)
        self.premium_users: set = set()
        self.premium_multiplier = 3
    
    async def check_rate_limit(
        self, 
        user_id: int, 
        operation: str = "general",
        update: Optional[Update] = None,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limits.
        
        Args:
            user_id: Telegram user ID
            operation: Type of operation being performed
            update: Telegram update object (optional)
            context: Bot context (optional)
        
        Returns:
            Tuple of (allowed, error_message)
        """
        current_time = time.time()
        
        # Check if user is temporarily blocked
        if user_id in self.blocked_users:
            unblock_time = self.blocked_users[user_id]
            if current_time < unblock_time:
                remaining_time = int(unblock_time - current_time)
                user_language = "ru"
                if update and update.effective_user:
                    user_language = user_sessions.get_session_data(user_id, "language", "ru")
                
                error_message = self._get_blocked_message(remaining_time, user_language)
                return False, error_message
            else:
                # Remove expired block
                del self.blocked_users[user_id]
        
        # Check if user is whitelisted
        if user_id in self.whitelist:
            return True, None
        
        # Check if user is blacklisted
        if user_id in self.blacklist:
            limit_config = self.blacklist_limits.get(operation, self.blacklist_limits["general"])
        else:
            limit_config = self.limits.get(operation, self.limits["general"])
        
        # Get or create user history
        if user_id not in self.user_histories:
            self.user_histories[user_id] = UserRequestHistory(
                user_id=user_id,
                minute_requests=[],
                hour_requests=[],
                day_requests=[]
            )
        
        user_history = self.user_histories[user_id]
        
        # Apply premium multiplier if user is premium
        if user_id in self.premium_users:
            limit_config = RateLimit(
                requests_per_minute=limit_config.requests_per_minute * self.premium_multiplier,
                requests_per_hour=limit_config.requests_per_hour * self.premium_multiplier,
                requests_per_day=limit_config.requests_per_day * self.premium_multiplier,
                cooldown_seconds=limit_config.cooldown_seconds // 2
            )
        
        # Clean old requests
        self._clean_old_requests(user_history, current_time)
        
        # Check limits
        violation_type = self._check_limits(user_history, limit_config)
        
        if violation_type:
            # Rate limit exceeded
            user_language = "ru"
            if update and update.effective_user:
                user_language = user_sessions.get_session_data(user_id, "language", "ru")
            
            # Apply cooldown
            self._apply_cooldown(user_id, limit_config.cooldown_seconds, user_history)
            
            # Log violation
            self.logger.warning(f"Rate limit violation for user {user_id}: {violation_type} for {operation}")
            
            # Send warning
            error_message = self._get_rate_limit_message(
                violation_type, 
                limit_config.cooldown_seconds, 
                user_language
            )
            
            # Log to database
            try:
                db_manager.log_rate_limit_violation(
                    user_id=user_id,
                    operation=operation,
                    violation_type=violation_type,
                    cooldown_seconds=limit_config.cooldown_seconds
                )
            except Exception as e:
                self.logger.error(f"Failed to log rate limit violation: {e}")
            
            return False, error_message
        
        # Add current request to history
        user_history.minute_requests.append(current_time)
        user_history.hour_requests.append(current_time)
        user_history.day_requests.append(current_time)
        
        return True, None
    
    # Administrative methods
    
    def add_to_whitelist(self, user_id: int) -> None:
        """Add user to whitelist (exempt from rate limiting)."""
        self.whitelist.add(user_id)
        # Remove from blacklist if present
        self.blacklist.discard(user_id)
        self.logger.info(f"Added user {user_id} to whitelist")
    
    def remove_from_whitelist(self, user_id: int) -> None:
        """Remove user from whitelist."""
        self.whitelist.discard(user_id)
        self.logger.info(f"Removed user {user_id} from whitelist")
    
    def add_to_blacklist(self, user_id: int) -> None:
        """Add user to blacklist (stricter rate limits)."""
        self.blacklist.add(user_id)
        # Remove from whitelist if present
        self.whitelist.discard(user_id)
        self.logger.info(f"Added user {user_id} to blacklist")
    
    def remove_from_blacklist(self, user_id: int) -> None:
        """Remove user from blacklist."""
        self.blacklist.discard(user_id)
        self.logger.info(f"Removed user {user_id} from blacklist")
    
    def add_premium_user(self, user_id: int) -> None:
        """Add user to premium list (higher limits)."""
        self.premium_users.add(user_id)
        self.logger.info(f"Added user {user_id} to premium users")
    
    def remove_premium_user(self, user_id: int) -> None:
        """Remove user from premium list."""
        self.premium_users.discard(user_id)
        self.logger.info(f"Removed user {user_id} from premium users")
    
    def unblock_user(self, user_id: int) -> bool:
        """
        Manually unblock a user.
        
        Returns:
            True if user was blocked and is now unblocked, False if user wasn't blocked
        """
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
            self.logger.info(f"Manually unblocked user {user_id}")
            return True
        return False
    
    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive status for a user.
        
        Returns:
            Dictionary with user's rate limit status
        """
        current_time = time.time()
        
        status = {
            'user_id': user_id,
            'is_whitelisted': user_id in self.whitelist,
            'is_blacklisted': user_id in self.blacklist,
            'is_premium': user_id in self.premium_users,
            'is_blocked': user_id in self.blocked_users,
            'blocked_until': None,
            'request_history': None,
            'total_violations': 0
        }
        
        if user_id in self.blocked_users:
            unblock_time = self.blocked_users[user_id]
            status['blocked_until'] = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(unblock_time))
            status['seconds_remaining'] = max(0, int(unblock_time - current_time))
        
        if user_id in self.user_histories:
            history = self.user_histories[user_id]
            status['request_history'] = {
                'minute_requests': len(history.minute_requests),
                'hour_requests': len(history.hour_requests),
                'day_requests': len(history.day_requests),
                'total_violations': history.total_violations,
                'last_warning_time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(history.last_warning_time)) if history.last_warning_time else None
            }
            status['total_violations'] = history.total_violations
        
        return status
    
    def get_blocked_users(self) -> List[Dict[str, Any]]:
        """Get list of currently blocked users."""
        current_time = time.time()
        blocked = []
        
        for user_id, unblock_time in self.blocked_users.items():
            blocked.append({
                'user_id': user_id,
                'blocked_until': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(unblock_time)),
                'seconds_remaining': max(0, int(unblock_time - current_time))
            })
        
        return sorted(blocked, key=lambda x: x['seconds_remaining'])
    
    def get_rate_limiter_stats(self) -> Dict[str, Any]:
        """Get overall rate limiter statistics."""
        current_time = time.time()
        
        # Count active histories
        active_minute = 0
        active_hour = 0
        active_day = 0
        total_violations = 0
        
        for history in self.user_histories.values():
            # Clean old requests for accurate counting
            history.minute_requests = [t for t in history.minute_requests if current_time - t < 60]
            history.hour_requests = [t for t in history.hour_requests if current_time - t < 3600]
            history.day_requests = [t for t in history.day_requests if current_time - t < 86400]
            
            if history.minute_requests:
                active_minute += 1
            if history.hour_requests:
                active_hour += 1
            if history.day_requests:
                active_day += 1
            
            total_violations += history.total_violations
        
        return {
            'total_users_tracked': len(self.user_histories),
            'blocked_users_count': len(self.blocked_users),
            'whitelisted_users_count': len(self.whitelist),
            'blacklisted_users_count': len(self.blacklist),
            'premium_users_count': len(self.premium_users),
            'active_users': {
                'last_minute': active_minute,
                'last_hour': active_hour,
                'last_day': active_day
            },
            'total_violations_tracked': total_violations
        }
    
    def cleanup_old_violations(self) -> None:
        """Clean up old rate limit violations from database."""
        try:
            deleted_count = db_manager.cleanup_old_rate_limit_violations(days_to_keep=30)
            self.logger.info(f"Rate limiter cleanup: removed {deleted_count} old violations")
        except Exception as e:
            self.logger.error(f"Error during rate limiter cleanup: {e}")
    
    def _clean_old_requests(self, user_history: UserRequestHistory, current_time: float) -> None:
        """Remove old requests from history."""
        # Remove requests older than 1 minute
        user_history.minute_requests = [
            req_time for req_time in user_history.minute_requests 
            if current_time - req_time < 60
        ]
        
        # Remove requests older than 1 hour
        user_history.hour_requests = [
            req_time for req_time in user_history.hour_requests 
            if current_time - req_time < 3600
        ]
        
        # Remove requests older than 1 day
        user_history.day_requests = [
            req_time for req_time in user_history.day_requests 
            if current_time - req_time < 86400
        ]
    
    def _check_limits(self, user_history: UserRequestHistory, limit_config: RateLimit) -> Optional[str]:
        """Check if any limits are exceeded."""
        
        if len(user_history.minute_requests) >= limit_config.requests_per_minute:
            return "per_minute"
        
        if len(user_history.hour_requests) >= limit_config.requests_per_hour:
            return "per_hour"
        
        if len(user_history.day_requests) >= limit_config.requests_per_day:
            return "per_day"
        
        return None
    
    def _apply_cooldown(self, user_id: int, cooldown_seconds: int, user_history: UserRequestHistory) -> None:
        """Apply cooldown to user."""
        current_time = time.time()
        unblock_time = current_time + cooldown_seconds
        
        self.blocked_users[user_id] = unblock_time
        user_history.total_violations += 1
        
        # Increase cooldown for repeat offenders
        if user_history.total_violations > 3:
            additional_cooldown = min(user_history.total_violations * 60, 1800)  # Max 30 minutes
            self.blocked_users[user_id] += additional_cooldown
    
    def _get_rate_limit_message(
        self, 
        violation_type: str, 
        cooldown_seconds: int, 
        language: str
    ) -> str:
        """Get rate limit error message."""
        
        cooldown_minutes = cooldown_seconds // 60
        cooldown_text = f"{cooldown_minutes} мин" if language == "ru" else f"{cooldown_minutes} min"
        
        if violation_type == "per_minute":
            if language == "ru":
                return f"⏱️ Слишком много запросов в минуту. Подождите {cooldown_text}."
            elif language == "es":
                return f"⏱️ Demasiadas solicitudes por minuto. Espera {cooldown_text}."
            else:
                return f"⏱️ Too many requests per minute. Wait {cooldown_text}."
        
        elif violation_type == "per_hour":
            if language == "ru":
                return f"⏱️ Превышен лимит запросов в час. Подождите {cooldown_text}."
            elif language == "es":
                return f"⏱️ Límite de solicitudes por hora excedido. Espera {cooldown_text}."
            else:
                return f"⏱️ Hourly request limit exceeded. Wait {cooldown_text}."
        
        elif violation_type == "per_day":
            if language == "ru":
                return f"⏱️ Превышен дневной лимит запросов. Попробуйте завтра."
            elif language == "es":
                return f"⏱️ Límite diario de solicitudes excedido. Intenta mañana."
            else:
                return f"⏱️ Daily request limit exceeded. Try tomorrow."
        
        else:
            if language == "ru":
                return f"⏱️ Превышен лимит запросов. Подождите {cooldown_text}."
            elif language == "es":
                return f"⏱️ Límite de solicitudes excedido. Espera {cooldown_text}."
            else:
                return f"⏱️ Request limit exceeded. Wait {cooldown_text}."
    
    def _get_blocked_message(self, remaining_seconds: int, language: str) -> str:
        """Get message for blocked user."""
        
        if remaining_seconds > 60:
            remaining_time = f"{remaining_seconds // 60} мин" if language == "ru" else f"{remaining_seconds // 60} min"
        else:
            remaining_time = f"{remaining_seconds} сек" if language == "ru" else f"{remaining_seconds} sec"
        
        if language == "ru":
            return f"🚫 Вы временно заблокированы за превышение лимитов. Осталось: {remaining_time}"
        elif language == "es":
            return f"🚫 Estás temporalmente bloqueado por exceder límites. Restante: {remaining_time}"
        else:
            return f"🚫 You are temporarily blocked for exceeding limits. Remaining: {remaining_time}"
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """Get user's current request statistics."""
        if user_id not in self.user_histories:
            return {
                "minute_requests": 0,
                "hour_requests": 0,
                "day_requests": 0,
                "total_violations": 0,
                "is_blocked": False,
                "is_premium": False
            }
        
        current_time = time.time()
        user_history = self.user_histories[user_id]
        self._clean_old_requests(user_history, current_time)
        
        return {
            "minute_requests": len(user_history.minute_requests),
            "hour_requests": len(user_history.hour_requests),
            "day_requests": len(user_history.day_requests),
            "total_violations": user_history.total_violations,
            "is_blocked": user_id in self.blocked_users,
            "is_premium": user_id in self.premium_users
        }
    
    def reset_user_limits(self, user_id: int) -> None:
        """Reset user's rate limits (admin function)."""
        if user_id in self.user_histories:
            del self.user_histories[user_id]
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
        self.logger.info(f"Reset rate limits for user {user_id}")
    
    def cleanup_old_data(self) -> None:
        """Clean up old data to prevent memory leaks."""
        current_time = time.time()
        
        # Remove old user histories (inactive for more than 7 days)
        inactive_users = []
        for user_id, history in self.user_histories.items():
            if (not history.day_requests or 
                current_time - max(history.day_requests) > 86400 * 7):
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self.user_histories[user_id]
        
        # Remove expired blocks
        expired_blocks = []
        for user_id, unblock_time in self.blocked_users.items():
            if current_time >= unblock_time:
                expired_blocks.append(user_id)
        
        for user_id in expired_blocks:
            del self.blocked_users[user_id]
        
        if inactive_users or expired_blocks:
            self.logger.info(f"Cleaned up {len(inactive_users)} inactive users and {len(expired_blocks)} expired blocks")


# Global rate limiter instance
rate_limiter = RateLimiter()


# Decorator for rate-limited functions
def rate_limited(operation: str = "general"):
    """Decorator to apply rate limiting to bot handlers."""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)
            
            user_id = update.effective_user.id
            allowed, error_message = await rate_limiter.check_rate_limit(
                user_id=user_id,
                operation=operation,
                update=update,
                context=context
            )
            
            if not allowed:
                # Send rate limit message
                if error_message:
                    if update.message:
                        await update.message.reply_text(error_message)
                    elif update.callback_query:
                        await update.callback_query.answer(error_message, show_alert=True)
                return
            
            # Call original function
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator 