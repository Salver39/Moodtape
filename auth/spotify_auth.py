"""Spotify OAuth authorization and API integration for Moodtape bot."""

import time
import uuid
import asyncio
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

from config.settings import (
    SPOTIPY_CLIENT_ID, 
    SPOTIPY_CLIENT_SECRET, 
    SPOTIPY_REDIRECT_URI,
    DEFAULT_PLAYLIST_LENGTH
)
from utils.database import db_manager
from utils.logger import get_logger
from moodtape_core.gpt_parser import MoodParameters

logger = get_logger(__name__)

# Spotify OAuth scopes needed for Moodtape
SPOTIFY_SCOPES = [
    "user-read-private",          # Read user profile
    "user-library-read",          # Read liked songs
    "user-top-read",             # Read top tracks/artists
    "playlist-modify-public",     # Create public playlists
    "playlist-modify-private",    # Create private playlists
]

class SpotifyAuth:
    """Handles Spotify OAuth authorization."""
    
    def __init__(self):
        """Initialize Spotify OAuth manager."""
        self.oauth = None
        
        if all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET]):
            try:
                self.oauth = SpotifyOAuth(
                    client_id=SPOTIPY_CLIENT_ID,
                    client_secret=SPOTIPY_CLIENT_SECRET,
                    redirect_uri=SPOTIPY_REDIRECT_URI,
                    scope=" ".join(SPOTIFY_SCOPES),
                    show_dialog=True  # Always show auth dialog
                )
                logger.info("Spotify OAuth initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Spotify OAuth: {e}")
                self.oauth = None
        else:
            logger.warning("Spotify credentials not configured")
    
    def is_configured(self) -> bool:
        """Check if Spotify OAuth is properly configured."""
        return self.oauth is not None
    
    def get_auth_url(self, user_id: int) -> str:
        """
        Get Spotify authorization URL for user.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            Authorization URL
        """
        if not self.oauth:
            raise ValueError("Spotify OAuth not configured")
        
        # Use user_id as state for security
        auth_url = self.oauth.get_authorize_url(state=str(user_id))
        logger.info(f"Generated auth URL for user {user_id}")
        return auth_url
    
    def handle_callback(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Handle OAuth callback and exchange code for token.
        
        Args:
            code: Authorization code from Spotify
            state: State parameter (should be user_id)
        
        Returns:
            Token info dict or None if failed
        """
        if not self.oauth:
            logger.error("Spotify OAuth not configured")
            return None
        
        try:
            # Exchange code for token
            token_info = self.oauth.get_access_token(code)
            
            if token_info:
                user_id = int(state)
                
                # Save token to database
                db_manager.save_user_token(
                    user_id=user_id,
                    service="spotify",
                    access_token=token_info["access_token"],
                    refresh_token=token_info.get("refresh_token"),
                    expires_at=int(time.time()) + token_info.get("expires_in", 3600),
                    scope=token_info.get("scope")
                )
                
                logger.info(f"Successfully saved Spotify token for user {user_id}")
                return token_info
            
        except Exception as e:
            logger.error(f"Error handling Spotify callback: {e}")
        
        return None
    
    def refresh_token(self, user_id: int) -> Optional[str]:
        """
        Refresh expired access token.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            New access token or None if failed
        """
        if not self.oauth:
            logger.error("Spotify OAuth not configured")
            return None
        
        token_data = db_manager.get_user_token(user_id, "spotify")
        
        if not token_data or not token_data.get("refresh_token"):
            logger.warning(f"No refresh token found for user {user_id}")
            return None
        
        try:
            # Create temporary token info for refresh
            token_info = {
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_at": token_data["expires_at"]
            }
            
            # Refresh token
            new_token_info = self.oauth.refresh_access_token(token_data["refresh_token"])
            
            if new_token_info:
                # Save updated token
                db_manager.save_user_token(
                    user_id=user_id,
                    service="spotify",
                    access_token=new_token_info["access_token"],
                    refresh_token=new_token_info.get("refresh_token", token_data["refresh_token"]),
                    expires_at=int(time.time()) + new_token_info.get("expires_in", 3600),
                    scope=new_token_info.get("scope")
                )
                
                logger.info(f"Successfully refreshed Spotify token for user {user_id}")
                return new_token_info["access_token"]
        
        except Exception as e:
            logger.error(f"Error refreshing Spotify token for user {user_id}: {e}")
        
        return None


class SpotifyClient:
    """Spotify API client for playlist generation."""
    
    def __init__(self, user_id: int):
        """
        Initialize Spotify client for specific user.
        
        Args:
            user_id: Telegram user ID
        """
        self.user_id = user_id
        self.spotify_auth = SpotifyAuth()
        self.client: Optional[spotipy.Spotify] = None
        
        # Initialize client
        self._init_client()
    
    def _init_client(self) -> bool:
        """
        Initialize Spotify client with user's token.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get user token
            token_data = db_manager.get_user_token(self.user_id, "spotify")
            
            if not token_data:
                logger.warning(f"No Spotify token found for user {self.user_id}")
                return False
            
            # Check if token is expired and refresh if needed
            if not db_manager.is_token_valid(self.user_id, "spotify"):
                logger.info(f"Token expired for user {self.user_id}, attempting refresh")
                new_token = self.spotify_auth.refresh_token(self.user_id)
                if not new_token:
                    logger.error(f"Failed to refresh token for user {self.user_id}")
                    return False
                
                # Get updated token data
                token_data = db_manager.get_user_token(self.user_id, "spotify")
            
            # Create Spotify client
            self.client = spotipy.Spotify(auth=token_data["access_token"])
            
            # Test the connection
            user_info = self.client.current_user()
            logger.info(f"Successfully connected to Spotify for user {self.user_id}, "
                       f"Spotify user: {user_info.get('display_name', user_info['id'])}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error initializing Spotify client for user {self.user_id}: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with Spotify."""
        return self.client is not None
    
    def get_user_liked_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get user's liked tracks.
        
        Args:
            limit: Maximum number of tracks to fetch
        
        Returns:
            List of track objects
        """
        if not self.client:
            return []
        
        try:
            results = self.client.current_user_saved_tracks(limit=limit)
            tracks = []
            
            for item in results['items']:
                track = item['track']
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'uri': track['uri'],
                    'audio_features': None  # Will be fetched separately if needed
                })
            
            logger.info(f"Retrieved {len(tracks)} liked tracks for user {self.user_id}")
            return tracks
        
        except SpotifyException as e:
            logger.error(f"Error fetching liked tracks for user {self.user_id}: {e}")
            return []
    
    def get_user_top_tracks(self, time_range: str = "medium_term", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get user's top tracks.
        
        Args:
            time_range: short_term, medium_term, or long_term
            limit: Maximum number of tracks to fetch
        
        Returns:
            List of track objects
        """
        if not self.client:
            return []
        
        try:
            results = self.client.current_user_top_tracks(
                time_range=time_range,
                limit=limit
            )
            
            tracks = []
            for track in results['items']:
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'uri': track['uri'],
                    'audio_features': None
                })
            
            logger.info(f"Retrieved {len(tracks)} top tracks for user {self.user_id}")
            return tracks
        
        except SpotifyException as e:
            logger.error(f"Error fetching top tracks for user {self.user_id}: {e}")
            return []
    
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
        if not self.client:
            return []
        
        try:
            # Build search query based on mood
            search_terms = []
            
            # Add genre hints
            if mood_params.genre_hints:
                search_terms.extend([f"genre:{genre}" for genre in mood_params.genre_hints[:2]])
            
            # Add mood tags as general search terms
            if mood_params.mood_tags:
                search_terms.extend(mood_params.mood_tags[:2])
            
            # Add time/activity context
            if mood_params.time_of_day:
                search_terms.append(mood_params.time_of_day)
            
            if mood_params.activity:
                search_terms.append(mood_params.activity)
            
            # If no specific terms, use generic search
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
            logger.info(f"Searching Spotify with query: {search_query}")
            
            results = self.client.search(
                q=search_query,
                type='track',
                limit=min(limit * 2, 50)  # Get more results to filter later
            )
            
            tracks = []
            for track in results['tracks']['items']:
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'uri': track['uri'],
                    'audio_features': None
                })
            
            logger.info(f"Found {len(tracks)} tracks matching mood search")
            return tracks[:limit]
        
        except SpotifyException as e:
            logger.error(f"Error searching tracks for user {self.user_id}: {e}")
            return []
    
    def create_playlist(
        self, 
        name: str, 
        description: str,
        track_uris: List[str],
        public: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new playlist with specified tracks.
        
        Args:
            name: Playlist name
            description: Playlist description
            track_uris: List of track URIs to add
            public: Whether playlist should be public
        
        Returns:
            Playlist info dict or None if failed
        """
        if not self.client or not track_uris:
            return None
        
        try:
            # Get current user info
            user_info = self.client.current_user()
            
            # Debug logging
            logger.info(f"Creating playlist for user {self.user_id}: name='{name}', description='{description[:100]}...', public={public}, tracks={len(track_uris)}")
            
            # Create playlist
            playlist = self.client.user_playlist_create(
                user=user_info['id'],
                name=name,
                public=public,
                description=description
            )
            
            # Add tracks to playlist (Spotify API limits to 100 tracks per request)
            chunk_size = 100
            for i in range(0, len(track_uris), chunk_size):
                chunk = track_uris[i:i + chunk_size]
                self.client.playlist_add_items(playlist['id'], chunk)
            
            logger.info(f"Created playlist '{name}' with {len(track_uris)} tracks for user {self.user_id}")
            
            return {
                'id': playlist['id'],
                'name': playlist['name'],
                'url': playlist['external_urls']['spotify'],
                'uri': playlist['uri'],
                'track_count': len(track_uris)
            }
        
        except SpotifyException as e:
            logger.error(f"Error creating playlist for user {self.user_id}: {e}")
            return None


# Global Spotify auth instance
spotify_auth = SpotifyAuth() 