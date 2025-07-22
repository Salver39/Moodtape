"""Database utilities for Moodtape bot."""

import sqlite3
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

from config.settings import DATA_DIR, TOKENS_DB_PATH, FEEDBACK_DB_PATH, QUERY_LOG_DB_PATH
from utils.logger import get_logger

logger = get_logger(__name__)


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


# Global database manager instance
db_manager = DatabaseManager() 