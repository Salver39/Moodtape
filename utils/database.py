"""Database utilities for Moodtape bot."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Ensure data directory exists
data_dir = Path(settings.DATA_DIR)
data_dir.mkdir(parents=True, exist_ok=True)
logger.info(f"✅ Data directory is accessible: {data_dir}")

# Database paths
TOKENS_DB = data_dir / "tokens.db"
FEEDBACK_DB = data_dir / "feedback.db"
QUERY_LOG_DB = data_dir / "query_log.db"
RATE_LIMIT_DB = data_dir / "rate_limit.db"

class DatabaseManager:
    """Manages database operations for Moodtape bot."""
    
    def __init__(self):
        """Initialize database connections and tables."""
        self.logger = get_logger(__name__)
        
        # Initialize databases
        self._init_tokens_db()
        self._init_feedback_db()
        self._init_query_log_db()
        self._init_rate_limit_db()
    
    def _init_tokens_db(self):
        """Initialize tokens database."""
        try:
            with sqlite3.connect(TOKENS_DB) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tokens (
                        user_id INTEGER PRIMARY KEY,
                        service TEXT NOT NULL,
                        access_token TEXT,
                        refresh_token TEXT,
                        expires_at INTEGER,
                        created_at INTEGER,
                        updated_at INTEGER
                    )
                """)
                conn.commit()
            self.logger.info("Tokens database initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize tokens database: {e}")
    
    def _init_feedback_db(self):
        """Initialize feedback database."""
        try:
            with sqlite3.connect(FEEDBACK_DB) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        query_id TEXT NOT NULL,
                        rating INTEGER,
                        comment TEXT,
                        created_at INTEGER
                    )
                """)
                conn.commit()
            self.logger.info("Feedback database initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize feedback database: {e}")
    
    def _init_query_log_db(self):
        """Initialize query log database."""
        try:
            with sqlite3.connect(QUERY_LOG_DB) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        query_id TEXT NOT NULL,
                        mood_description TEXT,
                        mood_params TEXT,
                        playlist_info TEXT,
                        created_at INTEGER
                    )
                """)
                conn.commit()
            self.logger.info("Query log database initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize query log database: {e}")
    
    def _init_rate_limit_db(self):
        """Initialize rate limit violations database."""
        try:
            with sqlite3.connect(RATE_LIMIT_DB) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rate_limit_violations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        operation TEXT NOT NULL,
                        violation_count INTEGER DEFAULT 1,
                        first_violation_at INTEGER,
                        last_violation_at INTEGER
                    )
                """)
                conn.commit()
            self.logger.info("Rate limit violations database initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize rate limit database: {e}")
    
    def save_user_token(
        self,
        user_id: int,
        service: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[int] = None
    ) -> bool:
        """
        Save or update user's service token.
        
        Args:
            user_id: Telegram user ID
            service: Service name (e.g., 'spotify')
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_at: Token expiration timestamp (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            now = int(datetime.now().timestamp())
            
            with sqlite3.connect(TOKENS_DB) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tokens (
                        user_id, service, access_token, refresh_token,
                        expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, service, access_token, refresh_token,
                    expires_at, now, now
                ))
                conn.commit()
            
            self.logger.info(f"Saved {service} token for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save user token: {e}")
            return False
    
    def get_user_token(self, user_id: int, service: str) -> Optional[Dict[str, Any]]:
        """
        Get user's service token.
        
        Args:
            user_id: Telegram user ID
            service: Service name
        
        Returns:
            Token info dictionary or None if not found
        """
        try:
            with sqlite3.connect(TOKENS_DB) as conn:
                cursor = conn.execute("""
                    SELECT access_token, refresh_token, expires_at, updated_at
                    FROM tokens
                    WHERE user_id = ? AND service = ?
                """, (user_id, service))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'access_token': row[0],
                        'refresh_token': row[1],
                        'expires_at': row[2],
                        'updated_at': row[3]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user token: {e}")
            return None
    
    def delete_user_token(self, user_id: int, service: str) -> bool:
        """
        Delete user's service token.
        
        Args:
            user_id: Telegram user ID
            service: Service name
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(TOKENS_DB) as conn:
                conn.execute("""
                    DELETE FROM tokens
                    WHERE user_id = ? AND service = ?
                """, (user_id, service))
                conn.commit()
            
            self.logger.info(f"Deleted {service} token for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete user token: {e}")
            return False
    
    def is_token_valid(self, user_id: int, service: str) -> bool:
        """
        Check if user's service token is valid and not expired.
        
        Args:
            user_id: Telegram user ID
            service: Service name
        
        Returns:
            True if token is valid, False otherwise
        """
        token_info = self.get_user_token(user_id, service)
        if not token_info or not token_info.get('access_token'):
            return False
        
        # Check expiration if available
        expires_at = token_info.get('expires_at')
        if expires_at:
            now = int(datetime.now().timestamp())
            if now >= expires_at:
                return False
        
        return True
    
    def save_feedback(
        self,
        user_id: int,
        query_id: str,
        rating: Optional[int] = None,
        comment: Optional[str] = None
    ) -> bool:
        """
        Save user feedback for a playlist.
        
        Args:
            user_id: Telegram user ID
            query_id: Unique query identifier
            rating: Numeric rating (optional)
            comment: Text comment (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            now = int(datetime.now().timestamp())
            
            with sqlite3.connect(FEEDBACK_DB) as conn:
                conn.execute("""
                    INSERT INTO feedback (
                        user_id, query_id, rating, comment, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (user_id, query_id, rating, comment, now))
                conn.commit()
            
            self.logger.info(f"Saved feedback for query {query_id} from user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save feedback: {e}")
            return False
    
    def log_query(
        self,
        user_id: int,
        query_id: str,
        mood_description: str,
        mood_params: Dict[str, Any],
        playlist_info: Dict[str, Any]
    ) -> bool:
        """
        Log a mood query and its results.
        
        Args:
            user_id: Telegram user ID
            query_id: Unique query identifier
            mood_description: Original mood description
            mood_params: Parsed mood parameters
            playlist_info: Generated playlist info
        
        Returns:
            True if successful, False otherwise
        """
        try:
            now = int(datetime.now().timestamp())
            
            with sqlite3.connect(QUERY_LOG_DB) as conn:
                conn.execute("""
                    INSERT INTO query_log (
                        user_id, query_id, mood_description,
                        mood_params, playlist_info, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id, query_id, mood_description,
                    json.dumps(mood_params), json.dumps(playlist_info), now
                ))
                conn.commit()
            
            self.logger.info(f"Logged query {query_id} for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log query: {e}")
            return False
    
    def get_user_queries(
        self,
        user_id: int,
        limit: int = 10,
        with_feedback: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user's recent queries with optional feedback.
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of queries to return
            with_feedback: Include feedback data if True
        
        Returns:
            List of query dictionaries
        """
        try:
            with sqlite3.connect(QUERY_LOG_DB) as conn:
                conn.row_factory = sqlite3.Row
                
                if with_feedback:
                    cursor = conn.execute("""
                        SELECT q.*, f.rating, f.comment
                        FROM query_log q
                        LEFT JOIN feedback f ON q.query_id = f.query_id
                        WHERE q.user_id = ?
                        ORDER BY q.created_at DESC
                        LIMIT ?
                    """, (user_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT *
                        FROM query_log
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (user_id, limit))
                
                queries = []
                for row in cursor:
                    query = dict(row)
                    # Parse JSON fields
                    query['mood_params'] = json.loads(query['mood_params'])
                    query['playlist_info'] = json.loads(query['playlist_info'])
                    queries.append(query)
                
                return queries
                
        except Exception as e:
            self.logger.error(f"Failed to get user queries: {e}")
            return []
    
    def log_rate_limit_violation(self, user_id: int, operation: str) -> None:
        """
        Log a rate limit violation.
        
        Args:
            user_id: Telegram user ID
            operation: Operation type that was rate limited
        """
        try:
            now = int(datetime.now().timestamp())
            
            with sqlite3.connect(RATE_LIMIT_DB) as conn:
                # Check if user already has violations
                cursor = conn.execute("""
                    SELECT violation_count, first_violation_at
                    FROM rate_limit_violations
                    WHERE user_id = ? AND operation = ?
                """, (user_id, operation))
                
                row = cursor.fetchone()
                if row:
                    # Update existing record
                    conn.execute("""
                        UPDATE rate_limit_violations
                        SET violation_count = violation_count + 1,
                            last_violation_at = ?
                        WHERE user_id = ? AND operation = ?
                    """, (now, user_id, operation))
                else:
                    # Create new record
                    conn.execute("""
                        INSERT INTO rate_limit_violations (
                            user_id, operation, violation_count,
                            first_violation_at, last_violation_at
                        ) VALUES (?, ?, 1, ?, ?)
                    """, (user_id, operation, now, now))
                
                conn.commit()
            
            self.logger.warning(f"Rate limit violation logged for user {user_id} ({operation})")
            
        except Exception as e:
            self.logger.error(f"Failed to log rate limit violation: {e}")
    
    def get_rate_limit_violations(
        self,
        user_id: int,
        operation: str,
        window_seconds: int = 3600
    ) -> int:
        """
        Get number of rate limit violations within time window.
        
        Args:
            user_id: Telegram user ID
            operation: Operation type to check
            window_seconds: Time window in seconds
        
        Returns:
            Number of violations
        """
        try:
            now = int(datetime.now().timestamp())
            window_start = now - window_seconds
            
            with sqlite3.connect(RATE_LIMIT_DB) as conn:
                cursor = conn.execute("""
                    SELECT violation_count
                    FROM rate_limit_violations
                    WHERE user_id = ?
                    AND operation = ?
                    AND last_violation_at >= ?
                """, (user_id, operation, window_start))
                
                row = cursor.fetchone()
                return row[0] if row else 0
                
        except Exception as e:
            self.logger.error(f"Failed to get rate limit violations: {e}")
            return 0

    def cleanup_old_rate_limit_violations(self, days_to_keep: int = 30) -> int:
        """
        Clean up old rate limit violations.
        
        Args:
            days_to_keep: Number of days to keep violations for (default: 30)
        
        Returns:
            Number of deleted records
        """
        try:
            now = int(datetime.now().timestamp())
            cutoff_time = now - (days_to_keep * 86400)  # 86400 seconds in a day
            
            with sqlite3.connect(RATE_LIMIT_DB) as conn:
                cursor = conn.execute("""
                    DELETE FROM rate_limit_violations
                    WHERE last_violation_at < ?
                """, (cutoff_time,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleaned up {deleted_count} old rate limit violations")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to clean up rate limit violations: {e}")
            return 0

# Global database manager instance
db_manager = DatabaseManager() 