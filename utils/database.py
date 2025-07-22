"""Database utilities for Moodtape bot."""

import sqlite3
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

from config.settings import DATA_DIR
from utils.logger import get_logger

logger = get_logger(__name__)

# Database paths
TOKENS_DB_PATH = DATA_DIR / "tokens.sqlite"
FEEDBACK_DB_PATH = DATA_DIR / "feedback.sqlite" 
QUERY_LOG_DB_PATH = DATA_DIR / "query_log.sqlite"
RATE_LIMIT_DB_PATH = DATA_DIR / "rate_limits.sqlite"


class DatabaseManager:
    """Manages SQLite databases for Moodtape bot."""
    
    def __init__(self):
        """Initialize database connections and create tables."""
        self.init_databases()
    
    def init_databases(self):
        """Initialize all required databases and tables."""
        self._init_tokens_db()
        self._init_feedback_db()
        self._init_query_log_db()
        self._init_rate_limit_db()
    
    def _init_tokens_db(self):
        """Initialize tokens database."""
        with sqlite3.connect(TOKENS_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_tokens (
                    user_id INTEGER PRIMARY KEY,
                    service TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at INTEGER,
                    scope TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.commit()
        logger.info("Tokens database initialized")
    
    def _init_feedback_db(self):
        """Initialize feedback database."""
        with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query_id TEXT,
                    rating INTEGER,  -- 1 for thumbs up, -1 for thumbs down
                    feedback_text TEXT,
                    mood_params TEXT,  -- JSON of mood parameters
                    created_at INTEGER NOT NULL
                )
            """)
            conn.commit()
        logger.info("Feedback database initialized")
    
    def _init_query_log_db(self):
        """Initialize query log database."""
        with sqlite3.connect(QUERY_LOG_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    mood_description TEXT NOT NULL,
                    mood_params TEXT,  -- JSON of parsed mood parameters
                    service TEXT NOT NULL,
                    playlist_id TEXT,
                    playlist_url TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.commit()
        logger.info("Query log database initialized")

    def _init_rate_limit_db(self):
        """Initialize rate limit violations database."""
        with sqlite3.connect(RATE_LIMIT_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    cooldown_seconds INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.commit()
        logger.info("Rate limit violations database initialized")
    
    # Token management methods
    def save_user_token(
        self, 
        user_id: int, 
        service: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[int] = None,
        scope: Optional[str] = None
    ) -> None:
        """Save or update user token."""
        current_time = int(time.time())
        
        with sqlite3.connect(TOKENS_DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_tokens 
                (user_id, service, access_token, refresh_token, expires_at, scope, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, service, access_token, refresh_token, expires_at, scope, current_time, current_time))
            conn.commit()
        
        logger.info(f"Saved token for user {user_id}, service {service}")
    
    def get_user_token(self, user_id: int, service: str) -> Optional[Dict[str, Any]]:
        """Get user token for specific service."""
        with sqlite3.connect(TOKENS_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM user_tokens WHERE user_id = ? AND service = ?
            """, (user_id, service))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def delete_user_token(self, user_id: int, service: str) -> None:
        """Delete user token for specific service."""
        with sqlite3.connect(TOKENS_DB_PATH) as conn:
            conn.execute("""
                DELETE FROM user_tokens WHERE user_id = ? AND service = ?
            """, (user_id, service))
            conn.commit()
        
        logger.info(f"Deleted token for user {user_id}, service {service}")
    
    def is_token_valid(self, user_id: int, service: str) -> bool:
        """Check if user token is valid and not expired."""
        token_data = self.get_user_token(user_id, service)
        if not token_data:
            return False
        
        # Check if token is expired
        if token_data.get('expires_at'):
            current_time = int(time.time())
            if current_time >= token_data['expires_at']:
                logger.info(f"Token expired for user {user_id}, service {service}")
                return False
        
        return True
    
    # Feedback methods
    def save_feedback(
        self,
        user_id: int,
        rating: int,
        query_id: Optional[str] = None,
        feedback_text: Optional[str] = None,
        mood_params: Optional[Dict] = None
    ) -> None:
        """Save user feedback."""
        mood_params_json = json.dumps(mood_params) if mood_params else None
        current_time = int(time.time())
        
        with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO user_feedback 
                (user_id, query_id, rating, feedback_text, mood_params, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, query_id, rating, feedback_text, mood_params_json, current_time))
            conn.commit()
        
        logger.info(f"Saved feedback for user {user_id}: rating={rating}")
    
    def get_user_feedback_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's recent feedback history."""
        with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM user_feedback 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            feedback_list = []
            for row in rows:
                feedback = dict(row)
                if feedback.get('mood_params'):
                    try:
                        feedback['mood_params'] = json.loads(feedback['mood_params'])
                    except json.JSONDecodeError:
                        feedback['mood_params'] = None
                feedback_list.append(feedback)
            
            return feedback_list
    
    # Query log methods
    def log_query(
        self,
        query_id: str,
        user_id: int,
        mood_description: str,
        service: str,
        mood_params: Optional[Dict] = None,
        playlist_id: Optional[str] = None,
        playlist_url: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """Log a user query."""
        mood_params_json = json.dumps(mood_params) if mood_params else None
        current_time = int(time.time())
        
        with sqlite3.connect(QUERY_LOG_DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO query_log 
                (id, user_id, mood_description, mood_params, service, playlist_id, 
                 playlist_url, success, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (query_id, user_id, mood_description, mood_params_json, service,
                  playlist_id, playlist_url, success, error_message, current_time))
            conn.commit()
        
        logger.info(f"Logged query {query_id} for user {user_id}")
    
    def get_user_query_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's recent query history."""
        with sqlite3.connect(QUERY_LOG_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM query_log 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            query_list = []
            for row in rows:
                query = dict(row)
                if query.get('mood_params'):
                    try:
                        query['mood_params'] = json.loads(query['mood_params'])
                    except json.JSONDecodeError:
                        query['mood_params'] = None
                query_list.append(query)
            
            return query_list
    
    def log_rate_limit_violation(
        self,
        user_id: int,
        operation: str,
        violation_type: str,
        cooldown_seconds: int
    ) -> None:
        """
        Log a rate limit violation.
        
        Args:
            user_id: ID of the user who violated rate limit
            operation: Type of operation (e.g., 'playlist_creation')
            violation_type: Type of violation (e.g., 'per_minute', 'per_hour')
            cooldown_seconds: Cooldown period applied
        """
        current_time = int(time.time())
        with sqlite3.connect(RATE_LIMIT_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO rate_limit_violations 
                (user_id, operation, violation_type, cooldown_seconds, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, operation, violation_type, cooldown_seconds, current_time))
            conn.commit()
        logger.warning(
            f"Rate limit violation logged: user={user_id}, operation={operation}, "
            f"violation={violation_type}, cooldown={cooldown_seconds}s"
        )
    
    def get_rate_limit_violations(
        self,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get rate limit violations with optional filtering.
        
        Args:
            user_id: Filter by specific user (optional)
            operation: Filter by operation type (optional)
            hours_back: How many hours back to look
            limit: Maximum number of results
            
        Returns:
            List of violation records
        """
        cutoff_time = int(time.time()) - (hours_back * 3600)
        
        query = """
            SELECT id, user_id, operation, violation_type, cooldown_seconds, created_at
            FROM rate_limit_violations 
            WHERE created_at >= ?
        """
        params = [cutoff_time]
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
            
        if operation:
            query += " AND operation = ?"
            params.append(operation)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(RATE_LIMIT_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            violations = []
            for row in cursor.fetchall():
                violations.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'operation': row['operation'],
                    'violation_type': row['violation_type'],
                    'cooldown_seconds': row['cooldown_seconds'],
                    'created_at': row['created_at'],
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(row['created_at']))
                })
            
            return violations
    
    def get_rate_limit_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get rate limit violation statistics.
        
        Args:
            hours_back: How many hours back to analyze
            
        Returns:
            Dictionary with statistics
        """
        cutoff_time = int(time.time()) - (hours_back * 3600)
        
        with sqlite3.connect(RATE_LIMIT_DB_PATH) as conn:
            # Total violations
            total_violations = conn.execute(
                "SELECT COUNT(*) FROM rate_limit_violations WHERE created_at >= ?",
                (cutoff_time,)
            ).fetchone()[0]
            
            # Violations by operation
            operation_stats = conn.execute("""
                SELECT operation, COUNT(*) as count
                FROM rate_limit_violations 
                WHERE created_at >= ?
                GROUP BY operation
                ORDER BY count DESC
            """, (cutoff_time,)).fetchall()
            
            # Violations by user (top violators)
            user_stats = conn.execute("""
                SELECT user_id, COUNT(*) as count
                FROM rate_limit_violations 
                WHERE created_at >= ?
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff_time,)).fetchall()
            
            # Violations by type
            type_stats = conn.execute("""
                SELECT violation_type, COUNT(*) as count
                FROM rate_limit_violations 
                WHERE created_at >= ?
                GROUP BY violation_type
                ORDER BY count DESC
            """, (cutoff_time,)).fetchall()
            
            return {
                'total_violations': total_violations,
                'hours_analyzed': hours_back,
                'operations': [{'operation': row[0], 'count': row[1]} for row in operation_stats],
                'top_violators': [{'user_id': row[0], 'count': row[1]} for row in user_stats],
                'violation_types': [{'type': row[0], 'count': row[1]} for row in type_stats]
            }
    
    def cleanup_old_rate_limit_violations(self, days_to_keep: int = 30) -> int:
        """
        Clean up old rate limit violations.
        
        Args:
            days_to_keep: How many days of data to keep
            
        Returns:
            Number of records deleted
        """
        cutoff_time = int(time.time()) - (days_to_keep * 24 * 3600)
        
        with sqlite3.connect(RATE_LIMIT_DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM rate_limit_violations WHERE created_at < ?",
                (cutoff_time,)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            
        logger.info(f"Cleaned up {deleted_count} old rate limit violations (older than {days_to_keep} days)")
        return deleted_count


# Global database manager instance
db_manager = DatabaseManager() 