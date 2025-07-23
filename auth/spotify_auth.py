"""Spotify OAuth authorization and API integration for Moodtape bot."""

import time
import uuid
import asyncio
import random
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
                    show_dialog=False  # ИСПРАВЛЕНО: Не заставляем пользователя повторно авторизовываться
                )
                logger.info("Spotify OAuth initialized successfully - persistent auth enabled")
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
            logger.info(f"Refreshing Spotify token for user {user_id}")
            
            # Используем refresh_token напрямую
            new_token_info = self.oauth.refresh_access_token(token_data["refresh_token"])
            
            if new_token_info and new_token_info.get("access_token"):
                # Рассчитываем новое время истечения
                expires_in = new_token_info.get("expires_in", 3600)
                new_expires_at = int(time.time()) + expires_in
                
                # Сохраняем обновленный токен, сохраняя старый refresh_token если новый не предоставлен
                new_refresh_token = new_token_info.get("refresh_token", token_data["refresh_token"])
                
                db_manager.save_user_token(
                    user_id=user_id,
                    service="spotify",
                    access_token=new_token_info["access_token"],
                    refresh_token=new_refresh_token,
                    expires_at=new_expires_at,
                    scope=new_token_info.get("scope", token_data.get("scope"))
                )
                
                logger.info(f"Successfully refreshed Spotify token for user {user_id}, new expiry: {new_expires_at}")
                return new_token_info["access_token"]
            else:
                logger.error(f"Invalid response from token refresh for user {user_id}: {new_token_info}")
                return None
        
        except Exception as e:
            logger.error(f"Error refreshing Spotify token for user {user_id}: {e}")
            # При ошибке refresh token может быть недействительным, но не удаляем токен - пользователь должен заново авторизоваться
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
        self._cached_token = None  # Кэш токена в памяти
        self._token_expires_at = None  # Время истечения кэшированного токена
        
        # Initialize client
        self._init_client()
    
    def _init_client(self) -> bool:
        """
        Initialize Spotify client with user's token.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Проверяем кэшированный токен
            current_time = int(time.time())
            if (self._cached_token and self._token_expires_at and 
                current_time < (self._token_expires_at - 300)):  # 5 минут буфер
                logger.info(f"Using cached token for user {self.user_id}")
                self.client = spotipy.Spotify(auth=self._cached_token)
                return True
            
            # Получаем токен из базы данных
            token_data = db_manager.get_user_token(self.user_id, "spotify")
            
            if not token_data:
                logger.warning(f"No Spotify token found for user {self.user_id}")
                return False
            
            access_token = token_data["access_token"]
            expires_at = token_data.get("expires_at", 0)
            
            # Проверяем, истек ли токен (с буфером 5 минут)
            if expires_at and current_time >= (expires_at - 300):
                logger.info(f"Token for user {self.user_id} expires soon (at {expires_at}, now {current_time}), refreshing...")
                
                # Пытаемся обновить токен
                new_token = self.spotify_auth.refresh_token(self.user_id)
                if new_token:
                    # Получаем обновленные данные токена
                    token_data = db_manager.get_user_token(self.user_id, "spotify")
                    access_token = token_data["access_token"]
                    expires_at = token_data.get("expires_at", 0)
                    logger.info(f"Token refreshed successfully for user {self.user_id}")
                else:
                    logger.error(f"Failed to refresh token for user {self.user_id}, user will need to re-authorize")
                    return False
            
            # Создаем Spotify client с валидным токеном
            self.client = spotipy.Spotify(auth=access_token)
            
            # Кэшируем токен в памяти
            self._cached_token = access_token
            self._token_expires_at = expires_at
            
            # Проверяем соединение
            try:
                # user_info = self.client.current_user()  # Removed to avoid 403 error
                logger.info(f"Successfully connected to Spotify for user {self.user_id}, token expires: {expires_at}")
                return True
            except Exception as test_error:
                logger.error(f"Token validation failed for user {self.user_id}: {test_error}")
                # Очищаем кэш и пытаемся обновить токен
                self._cached_token = None
                self._token_expires_at = None
                
                # Последняя попытка - обновить токен
                new_token = self.spotify_auth.refresh_token(self.user_id)
                if new_token:
                    return self._init_client()  # Рекурсивный вызов после обновления
                else:
                    logger.error(f"Final token refresh failed for user {self.user_id}")
                    return False
        
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
        Search for tracks that match mood parameters using multiple discovery strategies.
        
        Args:
            mood_params: Parsed mood parameters
            limit: Number of tracks to find
        
        Returns:
            List of track objects
        """
        if not self.client:
            return []
        
        all_tracks = []
        
        try:
            # Strategy 1: Genre-based search with audio features
            # Use new MoodParameters structure (primary + secondary genres)
            available_genres = []
            if hasattr(mood_params, 'primary_genres') and mood_params.primary_genres:
                available_genres.extend(mood_params.primary_genres)
            if hasattr(mood_params, 'secondary_genres') and mood_params.secondary_genres:
                available_genres.extend(mood_params.secondary_genres)
            
            # Fallback to legacy genre_hints if new structure not available
            if not available_genres and hasattr(mood_params, 'genre_hints') and mood_params.genre_hints:
                available_genres = mood_params.genre_hints
            
            if available_genres:
                for genre in available_genres[:3]:  # Use top 3 genres
                    search_query = f"genre:{genre}"
                    logger.info(f"Discovery search 1 - Genre: {search_query}")
                    
                    results = self.client.search(q=search_query, type='track', limit=20)
                    for track in results['tracks']['items'][:10]:  # Take first 10
                        all_tracks.append({
                            'id': track['id'],
                            'name': track['name'],
                            'artists': [artist['name'] for artist in track['artists']],
                            'uri': track['uri'],
                            'audio_features': None,
                            'discovery_method': f'genre_{genre}'
                        })
                        
                logger.info(f"Genre search found {len([t for t in all_tracks if t.get('discovery_method', '').startswith('genre_')])} tracks from genres: {available_genres[:3]}")
            else:
                logger.warning(f"No genres available for mood search for user {self.user_id}")
            
            # Strategy 2: Mood descriptors search (for discovery)
            mood_descriptors = []
            if mood_params.valence > 0.7:
                mood_descriptors.extend(["uplifting", "optimistic", "bright"])
            elif mood_params.valence < 0.3:
                mood_descriptors.extend(["melancholy", "introspective", "contemplative"])
            else:
                mood_descriptors.extend(["balanced", "thoughtful", "mellow"])
            
            if mood_params.energy > 0.7:
                mood_descriptors.extend(["dynamic", "vibrant", "driving"])
            elif mood_params.energy < 0.3:
                mood_descriptors.extend(["ambient", "peaceful", "gentle"])
            
            # Search with mood descriptors
            for descriptor in mood_descriptors[:2]:
                logger.info(f"Discovery search 2 - Mood: {descriptor}")
                results = self.client.search(q=descriptor, type='track', limit=15)
                for track in results['tracks']['items'][:8]:  # Take 8 from each
                    all_tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [artist['name'] for artist in track['artists']],
                        'uri': track['uri'],
                        'audio_features': None,
                        'discovery_method': f'mood_{descriptor}'
                    })
            
            # Strategy 3: Activity/context based search
            if mood_params.activity or mood_params.time_of_day:
                context_terms = []
                if mood_params.activity:
                    context_terms.append(mood_params.activity)
                if mood_params.time_of_day:
                    context_terms.append(mood_params.time_of_day)
                
                search_query = " ".join(context_terms[:2])
                logger.info(f"Discovery search 3 - Context: {search_query}")
                
                results = self.client.search(q=search_query, type='track', limit=15)
                for track in results['tracks']['items'][:10]:
                    all_tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [artist['name'] for artist in track['artists']],
                        'uri': track['uri'],
                        'audio_features': None,
                        'discovery_method': f'context_{search_query.replace(" ", "_")}'
                    })
            
            # Strategy 4: Random discovery from similar genres
            discovery_genres = ["indie rock", "alternative", "dream pop", "folk rock", "indie folk", "electronic", "chillwave"]
            selected_genre = random.choice(discovery_genres)
            logger.info(f"Discovery search 4 - Random genre: {selected_genre}")
            
            results = self.client.search(q=f"genre:\"{selected_genre}\"", type='track', limit=20)
            for track in results['tracks']['items'][:12]:
                all_tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'uri': track['uri'],
                    'audio_features': None,
                    'discovery_method': f'random_{selected_genre.replace(" ", "_")}'
                })
            
            # Remove duplicates and shuffle for variety
            seen_ids = set()
            unique_tracks = []
            for track in all_tracks:
                if track['id'] not in seen_ids:
                    unique_tracks.append(track)
                    seen_ids.add(track['id'])
            
            random.shuffle(unique_tracks)
            final_tracks = unique_tracks[:limit]
            
            logger.info(f"Found {len(final_tracks)} tracks matching mood search (from {len(all_tracks)} total, {len(unique_tracks)} unique)")
            
            # Log discovery methods
            method_counts = {}
            for track in final_tracks:
                method = track.get('discovery_method', 'unknown')
                method_counts[method] = method_counts.get(method, 0) + 1
            logger.info(f"Discovery methods: {method_counts}")
            
            return final_tracks
        
        except SpotifyException as e:
            logger.error(f"Error searching tracks by mood for user {self.user_id}: {e}")
            return []
    
    def create_playlist(
        self, 
        name: str, 
        description: str,
        track_uris: List[str],
        public: bool = True
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
            # user_info = self.client.current_user()  # Removed to avoid 403 error
            
            # Sanitize inputs for Spotify API
            clean_name = name.replace('\n', ' ').replace('\r', ' ').strip()
            clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
            
            # Additional safety: remove any quotes that might break JSON
            clean_name = clean_name.replace('"', "'").replace('\t', ' ')
            clean_description = clean_description.replace('"', "'").replace('\t', ' ')
            
            # Debug logging with exact parameters
            logger.info(f"Creating playlist for user {self.user_id}:")
            # logger.info(f"  user_id: removed for 403 fix")
            logger.info(f"  name: '{clean_name}' (len={len(clean_name)})")
            logger.info(f"  description: '{clean_description[:150]}...' (len={len(clean_description)})")
            logger.info(f"  public: {public}")
            logger.info(f"  tracks_count: {len(track_uris)}")
            
            # Create playlist with cleaned parameters
            try:
                playlist = self.client.user_playlist_create(
                    user="me",
                    name=clean_name,
                    public=public,
                    description=clean_description
                )
            except Exception as desc_error:
                logger.warning(f"Failed to create playlist with description for user {self.user_id}: {desc_error}")
                logger.info(f"Trying to create playlist without description...")
                
                # Fallback: create playlist without description
                playlist = self.client.user_playlist_create(
                    user="me",
                    name=clean_name,
                    public=public
                )
            
            # Add tracks to playlist (Spotify API limits to 100 tracks per request)
            chunk_size = 100
            added_tracks_count = 0
            
            logger.info(f"Adding {len(track_uris)} tracks to playlist '{clean_name}'...")
            
            for i in range(0, len(track_uris), chunk_size):
                chunk = track_uris[i:i + chunk_size]
                try:
                    result = self.client.playlist_add_items(playlist['id'], chunk)
                    added_tracks_count += len(chunk)
                    logger.info(f"Added chunk {i//chunk_size + 1}: {len(chunk)} tracks (total: {added_tracks_count})")
                except Exception as chunk_error:
                    logger.error(f"Failed to add chunk {i//chunk_size + 1} with {len(chunk)} tracks: {chunk_error}")
            
            logger.info(f"Created playlist '{clean_name}' with {added_tracks_count}/{len(track_uris)} tracks for user {self.user_id}")
            
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