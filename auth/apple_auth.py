"""Apple Music API integration for Moodtape bot."""

import json
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

import applemusicpy
from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

class AppleMusicClient:
    """Apple Music API client for Moodtape bot."""
    
    def __init__(self):
        """Initialize Apple Music client."""
        self.client = None
        self.logger = get_logger(__name__)
        self.initialized = False
        
        # Try to initialize client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize Apple Music client with developer token."""
        try:
            if settings.APPLE_MUSIC_KEY_ID and settings.APPLE_MUSIC_TEAM_ID and settings.APPLE_MUSIC_KEY_FILE:
                key_file = Path(settings.APPLE_MUSIC_KEY_FILE)
                if key_file.exists():
                    with open(key_file, 'r') as f:
                        private_key = f.read()
                    
                    self.client = applemusicpy.AppleMusic(
                        secret_key=private_key,
                        key_id=settings.APPLE_MUSIC_KEY_ID,
                        team_id=settings.APPLE_MUSIC_TEAM_ID
                    )
                    self.initialized = True
                    self.logger.info("✅ Apple Music client initialized successfully")
                else:
                    self.logger.error(f"❌ Apple Music key file not found: {key_file}")
            else:
                self.logger.warning("⚠️ Apple Music credentials not configured")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Apple Music client: {e}")
    
    def is_configured(self) -> bool:
        """Check if Apple Music client is properly configured."""
        return self.initialized and self.client is not None
    
    def search_tracks(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Search for tracks in Apple Music.
        
        Args:
            query: Search query string
            limit: Maximum number of tracks to return
        
        Returns:
            List of track dictionaries
        """
        if not self.is_configured():
            return []
        
        if limit is None:
            limit = settings.DEFAULT_PLAYLIST_LENGTH
            
        try:
            results = self.client.search(query, types=['songs'], limit=limit)
            if 'songs' in results and 'data' in results['songs']:
                return results['songs']['data']
            return []
        except Exception as e:
            self.logger.error(f"Error searching Apple Music tracks: {e}")
            return []
    
    def create_playlist(self, name: str, description: str = "", tracks: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new playlist in Apple Music.
        Note: This is a stub - Apple Music API doesn't support playlist creation.
        
        Args:
            name: Playlist name
            description: Playlist description
            tracks: List of track IDs
        
        Returns:
            Playlist info dictionary or None
        """
        self.logger.warning("⚠️ Apple Music API does not support playlist creation")
        return None
    
    def get_track_details(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a track.
        
        Args:
            track_id: Apple Music track ID
        
        Returns:
            Track details dictionary or None
        """
        if not self.is_configured():
            return None
        
        try:
            return self.client.song(track_id)
        except Exception as e:
            self.logger.error(f"Error getting Apple Music track details: {e}")
            return None
    
    def get_recommendations(self, seed_tracks: List[str] = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get track recommendations based on seed tracks.
        Note: This is a stub - Apple Music API doesn't support recommendations.
        
        Args:
            seed_tracks: List of track IDs to base recommendations on
            limit: Maximum number of recommendations
        
        Returns:
            List of recommended track dictionaries
        """
        self.logger.warning("⚠️ Apple Music API does not support recommendations")
        return []

# Global client instance
apple_music_client = AppleMusicClient() 