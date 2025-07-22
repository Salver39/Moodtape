"""Apple Music API integration for Moodtape bot."""

import time
import jwt as PyJWT
import requests
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from config.settings import (
    APPLE_TEAM_ID, 
    APPLE_KEY_ID, 
    APPLE_PRIVATE_KEY_PATH,
    DEFAULT_PLAYLIST_LENGTH
)
from utils.logger import get_logger
from moodtape_core.gpt_parser import MoodParameters

logger = get_logger(__name__)

# Apple Music API endpoints
APPLE_MUSIC_BASE_URL = "https://api.music.apple.com/v1"
APPLE_MUSIC_SEARCH_URL = f"{APPLE_MUSIC_BASE_URL}/catalog/{{storefront}}/search"


class AppleMusicAuth:
    """Handles Apple Music Developer Token generation."""
    
    def __init__(self):
        """Initialize Apple Music auth manager."""
        self.team_id = APPLE_TEAM_ID
        self.key_id = APPLE_KEY_ID
        self.private_key_path = APPLE_PRIVATE_KEY_PATH
        self.private_key = None
        self.cached_token = None
        self.token_expires_at = None
        
        # Load private key if configured
        if all([self.team_id, self.key_id, self.private_key_path]):
            try:
                self._load_private_key()
                logger.info("Apple Music auth initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Apple Music auth: {e}")
        else:
            logger.warning("Apple Music credentials not configured")
    
    def _load_private_key(self) -> None:
        """Load Apple Music private key from file."""
        try:
            key_path = Path(self.private_key_path)
            if not key_path.exists():
                raise FileNotFoundError(f"Apple Music private key file not found: {self.private_key_path}")
            
            with open(key_path, 'r') as f:
                self.private_key = f.read()
            
            logger.info("Apple Music private key loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Apple Music private key: {e}")
            self.private_key = None
    
    def is_configured(self) -> bool:
        """Check if Apple Music auth is properly configured."""
        return all([self.team_id, self.key_id, self.private_key])
    
    def generate_developer_token(self) -> Optional[str]:
        """
        Generate Apple Music Developer Token using JWT.
        
        Returns:
            Developer token string or None if failed
        """
        if not self.is_configured():
            logger.error("Apple Music auth not properly configured")
            return None
        
        # Check if we have a valid cached token
        if (self.cached_token and self.token_expires_at and 
            datetime.now() < self.token_expires_at - timedelta(minutes=5)):
            return self.cached_token
        
        try:
            # JWT payload
            now = datetime.now()
            expires_at = now + timedelta(hours=12)  # Apple Music tokens last up to 12 hours
            
            payload = {
                'iss': self.team_id,
                'iat': int(now.timestamp()),
                'exp': int(expires_at.timestamp())
            }
            
            # JWT headers
            headers = {
                'alg': 'ES256',
                'kid': self.key_id
            }
            
            # Generate JWT token
            token = PyJWT.encode(
                payload=payload,
                key=self.private_key,
                algorithm='ES256',
                headers=headers
            )
            
            # Cache the token
            self.cached_token = token
            self.token_expires_at = expires_at
            
            logger.info("Successfully generated Apple Music developer token")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate Apple Music developer token: {e}")
            return None


class AppleMusicClient:
    """Apple Music API client for music search and playlist operations."""
    
    def __init__(self):
        """Initialize Apple Music client."""
        self.auth = AppleMusicAuth()
        self.storefront = "us"  # Default to US storefront
    
    def is_configured(self) -> bool:
        """Check if Apple Music client is properly configured."""
        return self.auth.is_configured()
    
    def _get_headers(self) -> Optional[Dict[str, str]]:
        """Get request headers with authorization token."""
        token = self.auth.generate_developer_token()
        if not token:
            return None
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def search_tracks_by_mood(
        self, 
        mood_params: MoodParameters, 
        limit: int = DEFAULT_PLAYLIST_LENGTH
    ) -> List[Dict[str, Any]]:
        """
        Search for tracks that match mood parameters.
        
        Args:
            mood_params: Parsed mood parameters
            limit: Number of tracks to find
        
        Returns:
            List of track objects
        """
        if not self.is_configured():
            logger.error("Apple Music client not configured")
            return []
        
        headers = self._get_headers()
        if not headers:
            logger.error("Failed to get Apple Music authorization headers")
            return []
        
        try:
            # Build search query based on mood
            search_terms = []
            
            # Add genre hints
            if mood_params.genre_hints:
                search_terms.extend(mood_params.genre_hints[:2])
            
            # Add mood tags as general search terms
            if mood_params.mood_tags:
                search_terms.extend(mood_params.mood_tags[:2])
            
            # Add time/activity context
            if mood_params.time_of_day:
                search_terms.append(mood_params.time_of_day)
            
            if mood_params.activity:
                search_terms.append(mood_params.activity)
            
            # If no specific terms, use generic search based on valence/energy
            if not search_terms:
                if mood_params.valence > 0.7:
                    search_terms.append("happy")
                elif mood_params.valence < 0.3:
                    search_terms.append("sad")
                
                if mood_params.energy > 0.7:
                    search_terms.append("energetic")
                elif mood_params.energy < 0.3:
                    search_terms.append("calm")
            
            # Perform search
            search_query = " ".join(search_terms[:3])  # Limit to avoid too complex queries
            logger.info(f"Searching Apple Music with query: {search_query}")
            
            # Search parameters
            params = {
                'term': search_query,
                'types': 'songs',
                'limit': min(limit * 2, 50)  # Get more results to filter later
            }
            
            # Make API request
            search_url = APPLE_MUSIC_SEARCH_URL.format(storefront=self.storefront)
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            tracks = []
            songs = data.get('results', {}).get('songs', {}).get('data', [])
            
            for song in songs:
                attributes = song.get('attributes', {})
                tracks.append({
                    'id': song['id'],
                    'name': attributes.get('name', 'Unknown'),
                    'artists': [attributes.get('artistName', 'Unknown Artist')],
                    'album': attributes.get('albumName', 'Unknown Album'),
                    'duration_ms': attributes.get('durationInMillis', 0),
                    'preview_url': attributes.get('previews', [{}])[0].get('url') if attributes.get('previews') else None,
                    'apple_music_url': attributes.get('url'),
                    'source': 'apple_music'
                })
            
            logger.info(f"Found {len(tracks)} tracks matching mood search on Apple Music")
            return tracks[:limit]
            
        except requests.RequestException as e:
            logger.error(f"Apple Music API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching Apple Music tracks: {e}")
            return []
    
    def search_by_genre(self, genre: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search tracks by specific genre.
        
        Args:
            genre: Genre name to search
            limit: Number of tracks to return
        
        Returns:
            List of track objects
        """
        if not self.is_configured():
            return []
        
        headers = self._get_headers()
        if not headers:
            return []
        
        try:
            params = {
                'term': genre,
                'types': 'songs',
                'limit': limit
            }
            
            search_url = APPLE_MUSIC_SEARCH_URL.format(storefront=self.storefront)
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            tracks = []
            songs = data.get('results', {}).get('songs', {}).get('data', [])
            
            for song in songs:
                attributes = song.get('attributes', {})
                tracks.append({
                    'id': song['id'],
                    'name': attributes.get('name', 'Unknown'),
                    'artists': [attributes.get('artistName', 'Unknown Artist')],
                    'album': attributes.get('albumName', 'Unknown Album'),
                    'apple_music_url': attributes.get('url'),
                    'source': 'apple_music'
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"Error searching Apple Music by genre {genre}: {e}")
            return []
    
    def get_track_info(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific track.
        
        Args:
            track_id: Apple Music track ID
        
        Returns:
            Track info dict or None if not found
        """
        if not self.is_configured():
            return None
        
        headers = self._get_headers()
        if not headers:
            return None
        
        try:
            url = f"{APPLE_MUSIC_BASE_URL}/catalog/{self.storefront}/songs/{track_id}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            songs = data.get('data', [])
            
            if songs:
                song = songs[0]
                attributes = song.get('attributes', {})
                return {
                    'id': song['id'],
                    'name': attributes.get('name'),
                    'artists': [attributes.get('artistName')],
                    'album': attributes.get('albumName'),
                    'duration_ms': attributes.get('durationInMillis'),
                    'apple_music_url': attributes.get('url'),
                    'source': 'apple_music'
                }
            
        except Exception as e:
            logger.error(f"Error getting Apple Music track info for {track_id}: {e}")
        
        return None
    
    def create_playlist_link(
        self, 
        tracks: List[Dict[str, Any]], 
        name: str = "Moodtape Playlist"
    ) -> Optional[str]:
        """
        Create a shareable Apple Music playlist link.
        
        Note: Apple Music API doesn't support creating user playlists directly.
        This creates a deep link that opens Apple Music with the tracks.
        
        Args:
            tracks: List of track objects
            name: Playlist name
        
        Returns:
            Apple Music deep link or None if failed
        """
        if not tracks:
            return None
        
        try:
            # Get track IDs for Apple Music
            track_ids = [track['id'] for track in tracks if track.get('id')]
            
            if not track_ids:
                logger.error("No valid Apple Music track IDs found")
                return None
            
            # Create a deep link to Apple Music
            # This will open Apple Music app with the first track and suggest similar music
            first_track_id = track_ids[0]
            apple_music_link = f"https://music.apple.com/album/id{first_track_id}"
            
            logger.info(f"Created Apple Music link for {len(track_ids)} tracks")
            return apple_music_link
            
        except Exception as e:
            logger.error(f"Error creating Apple Music playlist link: {e}")
            return None


# Global Apple Music client instance
apple_music_client = AppleMusicClient() 