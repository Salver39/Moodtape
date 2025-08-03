"""Spotify OAuth authorization and API integration for Moodtape bot."""

import time
import uuid
import asyncio
import random
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

from config.settings import settings
from utils.database import db_manager
from utils.logger import get_logger
from moodtape_core.gpt_parser import MoodParameters

logger = get_logger(__name__)

# Spotify OAuth scopes needed for Moodtape
SPOTIFY_SCOPES = [
    "user-read-private",          # Read user profile
    "user-library-read",          # Access saved tracks
    "user-top-read",             # Access top tracks/artists
    "playlist-modify-public",     # Create public playlists
    "playlist-modify-private"     # Create private playlists
]

class SpotifyAuth:
    """Handles Spotify OAuth authorization."""
    
    def __init__(self):
        """Initialize Spotify auth manager."""
        self.logger = get_logger(__name__)
        self._auth_manager = None
        self._initialize_auth()
    
    def _initialize_auth(self) -> None:
        """Initialize OAuth manager."""
        try:
            self._auth_manager = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope=SPOTIFY_SCOPES,
                show_dialog=False  # Don't force re-auth
            )
            self.logger.info("✅ Spotify OAuth manager initialized")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Spotify OAuth: {e}")
    
    def get_auth_url(self, user_id: int) -> Optional[str]:
        """
        Get authorization URL for user.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            Authorization URL or None if failed
        """
        try:
            if not self._auth_manager:
                self._initialize_auth()
            
            if not self._auth_manager:
                self.logger.error("❌ OAuth manager not initialized")
                return None
            
            auth_url = self._auth_manager.get_authorize_url()
            self.logger.info(f"Generated auth URL for user {user_id}")
            return auth_url
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get auth URL: {e}")
            return None
    
    def get_token(self, auth_code: str) -> Optional[Dict[str, Any]]:
        """
        Get access token from authorization code.
        
        Args:
            auth_code: Authorization code from callback
        
        Returns:
            Token info dictionary or None if failed
        """
        try:
            if not self._auth_manager:
                self._initialize_auth()
            
            if not self._auth_manager:
                self.logger.error("❌ OAuth manager not initialized")
                return None
            
            token_info = self._auth_manager.get_access_token(auth_code)
            if not token_info:
                self.logger.error("❌ Failed to get token info")
                return None
            
            self.logger.info("✅ Successfully got access token")
            return token_info
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get token: {e}")
            return None
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token
        
        Returns:
            New token info dictionary or None if failed
        """
        try:
            if not self._auth_manager:
                self._initialize_auth()
            
            if not self._auth_manager:
                self.logger.error("❌ OAuth manager not initialized")
                return None
            
            token_info = self._auth_manager.refresh_access_token(refresh_token)
            if not token_info:
                self.logger.error("❌ Failed to refresh token")
                return None
            
            self.logger.info("✅ Successfully refreshed token")
            return token_info
            
        except Exception as e:
            self.logger.error(f"❌ Failed to refresh token: {e}")
            return None

# Global clients for singleton pattern
_user_spotify: Optional[spotipy.Spotify] = None
_public_spotify: Optional[spotipy.Spotify] = None

def get_user_spotify() -> Optional[spotipy.Spotify]:
    """
    Get Spotify client for user operations (OAuth flow).
    Uses singleton pattern to avoid multiple instances.
    
    Returns:
        Spotify client with user authorization or None if not available
    """
    global _user_spotify
    
    if _user_spotify is None:
        try:
            auth_manager = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope=SPOTIFY_SCOPES,
                show_dialog=False  # Don't force re-auth
            )
            _user_spotify = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            logger.error(f"Failed to initialize user Spotify client: {e}")
            return None
    
    return _user_spotify

def get_public_spotify() -> Optional[spotipy.Spotify]:
    """
    Get Spotify client for public operations (Client Credentials flow).
    Uses singleton pattern to avoid multiple instances.
    
    Returns:
        Spotify client for public operations or None if not available
    """
    global _public_spotify
    
    if _public_spotify is None:
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET
            )
            _public_spotify = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            logger.error(f"Failed to initialize public Spotify client: {e}")
            return None
    
    return _public_spotify

class SpotifyClient:
    """Spotify API client for Moodtape bot."""
    
    def __init__(self, user_id: int):
        """
        Initialize Spotify client for user.
        
        Args:
            user_id: Telegram user ID
        """
        self.user_id = user_id
        self.logger = get_logger(__name__)
    
    def search_tracks_by_mood(self, mood_params: MoodParameters, limit: int = None) -> List[Dict[str, Any]]:
        """
        Search for tracks that match mood parameters.
        Uses public client for search operations.
        """
        if limit is None:
            limit = settings.DEFAULT_PLAYLIST_LENGTH
            
        spotify = get_public_spotify()
        if not spotify:
            return []
        
        try:
            # Build search query from mood parameters
            query_parts = []
            
            # Add genre hints to query
            if hasattr(mood_params, 'genre_hints') and mood_params.genre_hints:
                query_parts.extend(mood_params.genre_hints[:2])  # Top 2 genres
            
            # Add mood tags to query
            if hasattr(mood_params, 'mood_tags') and mood_params.mood_tags:
                query_parts.extend(mood_params.mood_tags[:2])  # Top 2 mood tags
            
            # Add activity if available
            if hasattr(mood_params, 'activity') and mood_params.activity:
                query_parts.append(mood_params.activity)
            
            # Ensure we have a valid query
            if not query_parts:
                query_parts = ["instrumental"]  # Fallback query
            
            # Combine query parts
            search_query = " ".join(query_parts)
            
            # Search with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    results = spotify.search(
                        q=search_query,
                        type='track',
                        limit=limit,
                        market='US'  # Ensure tracks are playable
                    )
                    
                    if results and 'tracks' in results:
                        tracks = results['tracks']['items']
                        if tracks:
                            return tracks
                    
                    # If no results, try with just the first query part
                    if attempt == 0 and len(query_parts) > 1:
                        search_query = query_parts[0]
                    elif attempt == 1:
                        # On second retry, try a more generic query
                        search_query = "popular"
                    
                except Exception as e:
                    self.logger.error(f"Search attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                    continue
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error searching tracks by mood: {e}")
            return []
    
    def get_user_top_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get user's top tracks.
        Uses OAuth client for user data access.
        """
        spotify = get_user_spotify()
        if not spotify:
            return []
        
        try:
            results = spotify.current_user_top_tracks(
                limit=limit,
                offset=0,
                time_range='medium_term'  # Last 6 months
            )
            return results.get('items', [])
        except Exception as e:
            self.logger.error(f"Error getting user top tracks: {e}")
            return []
    
    def get_user_saved_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get user's saved/liked tracks.
        Uses OAuth client for user data access.
        """
        spotify = get_user_spotify()
        if not spotify:
            return []
        
        try:
            results = spotify.current_user_saved_tracks(limit=limit)
            return [item['track'] for item in results.get('items', [])]
        except Exception as e:
            self.logger.error(f"Error getting user saved tracks: {e}")
            return []
    
    def create_playlist(self, name: str, description: str = "", public: bool = True) -> Optional[Dict[str, Any]]:
        """
        Create a new playlist for user.
        Uses OAuth client for playlist creation.
        """
        spotify = get_user_spotify()
        if not spotify:
            return None
        
        try:
            # Get user ID first
            user_data = spotify.current_user()
            if not user_data or 'id' not in user_data:
                self.logger.error("Could not get Spotify user ID")
                return None
            
            spotify_user_id = user_data['id']
            
            # Create playlist
            playlist = spotify.user_playlist_create(
                user=spotify_user_id,
                name=name,
                public=public,
                description=description
            )
            
            if playlist and 'id' in playlist:
                return {
                    'id': playlist['id'],
                    'url': playlist['external_urls']['spotify'],
                    'name': playlist['name']
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating playlist: {e}")
            return None
    
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """
        Add tracks to an existing playlist.
        Uses OAuth client for playlist modification.
        """
        spotify = get_user_spotify()
        if not spotify or not track_uris:
            return False
        
        try:
            # Add tracks in batches (Spotify allows max 100 per request)
            batch_size = 100
            for i in range(0, len(track_uris), batch_size):
                batch = track_uris[i:i + batch_size]
                spotify.playlist_add_items(playlist_id, batch)
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding tracks to playlist: {e}")
            return False
    
    def get_audio_features(self, track_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
        """
        Get audio features for tracks.
        Uses public client for audio features access.
        """
        spotify = get_public_spotify()
        if not spotify or not track_ids:
            return []
        
        try:
            return spotify.audio_features(track_ids)
        except Exception as e:
            self.logger.error(f"Error getting audio features: {e}")
            return []
    
    def get_recommendations(
        self,
        seed_tracks: List[str] = None,
        seed_artists: List[str] = None,
        seed_genres: List[str] = None,
        limit: int = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Get track recommendations.
        Uses public client for recommendations.
        """
        if limit is None:
            limit = settings.DEFAULT_PLAYLIST_LENGTH
            
        spotify = get_public_spotify()
        if not spotify:
            return []
        
        try:
            results = spotify.recommendations(
                seed_tracks=seed_tracks,
                seed_artists=seed_artists,
                seed_genres=seed_genres,
                limit=limit,
                **kwargs
            )
            return results.get('tracks', [])
        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")
            return []
    
    def diagnose_spotify_permissions(self, user_id: int) -> None:
        """
        Diagnose Spotify API permissions for troubleshooting.
        Tests both OAuth and public endpoints.
        """
        # Test public client
        public_spotify = get_public_spotify()
        if not public_spotify:
            self.logger.error("❌ Public Spotify client initialization failed")
            return
        
        # Test OAuth client
        user_spotify = get_user_spotify()
        if not user_spotify:
            self.logger.error("❌ User Spotify client initialization failed")
            return
        
        try:
            # Test public endpoints
            try:
                public_spotify.audio_features(['spotify:track:2takcwOaAZWiXQijPHIx7B'])
                self.logger.info("✅ Public API: audio_features endpoint working")
            except Exception as e:
                self.logger.error(f"❌ Public API: audio_features failed: {e}")
            
            try:
                public_spotify.search(q='test', type='track', limit=1)
                self.logger.info("✅ Public API: search endpoint working")
            except Exception as e:
                self.logger.error(f"❌ Public API: search failed: {e}")
            
            # Test OAuth endpoints
            try:
                user_spotify.current_user()
                self.logger.info("✅ OAuth API: current_user endpoint working")
            except Exception as e:
                self.logger.error(f"❌ OAuth API: current_user failed: {e}")
            
            try:
                user_spotify.current_user_saved_tracks(limit=1)
                self.logger.info("✅ OAuth API: saved_tracks endpoint working")
            except Exception as e:
                self.logger.error(f"❌ OAuth API: saved_tracks failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error during Spotify permissions diagnosis: {e}")

# Global instances
spotify_auth = SpotifyAuth() 