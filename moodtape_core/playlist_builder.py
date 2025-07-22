"""Playlist builder that combines mood analysis with user preferences."""

import uuid
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from moodtape_core.gpt_parser import MoodParameters
from auth.spotify_auth import SpotifyClient
from auth.apple_auth import apple_music_client
from utils.database import db_manager
from utils.logger import get_logger

logger = get_logger(__name__)


class PlaylistBuilder:
    """Builds personalized playlists based on mood and user preferences."""
    
    def __init__(self, user_id: int, service: str = "spotify"):
        """
        Initialize playlist builder for user.
        
        Args:
            user_id: Telegram user ID
            service: Music service (spotify, apple_music)
        """
        self.user_id = user_id
        self.service = service
        self.spotify_client: Optional[SpotifyClient] = None
        
        # Initialize music service client
        if service == "spotify":
            self.spotify_client = SpotifyClient(user_id)
        elif service == "apple_music":
            # Apple Music doesn't require user-specific initialization
            # We'll use the global apple_music_client
            pass
    
    def is_service_available(self) -> bool:
        """Check if the music service is available and authenticated."""
        if self.service == "spotify":
            return self.spotify_client and self.spotify_client.is_authenticated()
        elif self.service == "apple_music":
            return apple_music_client.is_configured()
        return False
    
    async def build_mood_playlist(
        self,
        mood_params: MoodParameters,
        mood_description: str,
        playlist_length: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Build a personalized playlist based on mood parameters.
        
        Args:
            mood_params: Parsed mood parameters from GPT
            mood_description: Original user description
            playlist_length: Desired number of tracks
        
        Returns:
            Playlist info dict or None if failed
        """
        if not self.is_service_available():
            logger.error(f"Service {self.service} not available for user {self.user_id}")
            return None
        
        try:
            # Generate unique query ID
            query_id = str(uuid.uuid4())
            
            logger.info(f"Building playlist for user {self.user_id}, query {query_id}")
            
            # Get tracks from different sources
            if self.service == "spotify":
                # Spotify: user preferences + mood-based tracks
                user_tracks = self._get_user_preference_tracks()
                mood_tracks = self._get_mood_based_tracks(mood_params, playlist_length)
                
                # Combine and select best tracks
                final_tracks = self._combine_and_select_tracks(
                    user_tracks=user_tracks,
                    mood_tracks=mood_tracks,
                    target_length=playlist_length,
                    mood_params=mood_params
                )
            else:
                # Apple Music: only mood-based tracks (no user preferences)
                mood_tracks = self._get_mood_based_tracks(mood_params, playlist_length)
                final_tracks = mood_tracks[:playlist_length]
            
            if not final_tracks:
                logger.error(f"No tracks found for user {self.user_id}")
                # Log failed query
                db_manager.log_query(
                    query_id=query_id,
                    user_id=self.user_id,
                    mood_description=mood_description,
                    service=self.service,
                    mood_params=mood_params.__dict__,
                    success=False,
                    error_message="No suitable tracks found"
                )
                return None
            
            # Create playlist
            playlist_name = self._generate_playlist_name(mood_params, mood_description)
            playlist_description = self._generate_playlist_description(mood_params, mood_description)
            
            playlist_info = await self._create_playlist(
                name=playlist_name,
                description=playlist_description,
                tracks=final_tracks
            )
            
            if playlist_info:
                # Log successful query
                db_manager.log_query(
                    query_id=query_id,
                    user_id=self.user_id,
                    mood_description=mood_description,
                    service=self.service,
                    mood_params=mood_params.__dict__,
                    playlist_id=playlist_info['id'],
                    playlist_url=playlist_info['url'],
                    success=True
                )
                
                logger.info(f"Successfully created playlist for user {self.user_id}: {playlist_info['url']}")
                
                # Add query_id to result for feedback tracking
                playlist_info['query_id'] = query_id
                
                return playlist_info
            else:
                # Log failed query
                db_manager.log_query(
                    query_id=query_id,
                    user_id=self.user_id,
                    mood_description=mood_description,
                    service=self.service,
                    mood_params=mood_params.__dict__,
                    success=False,
                    error_message="Failed to create playlist"
                )
                return None
        
        except Exception as e:
            logger.error(f"Error building playlist for user {self.user_id}: {e}")
            return None
    
    def _get_user_preference_tracks(self) -> List[Dict[str, Any]]:
        """Get user's preferred tracks from their listening history."""
        if self.service == "spotify" and self.spotify_client:
            # Try to get liked tracks first
            liked_tracks = self.spotify_client.get_user_liked_tracks(limit=30)
            if liked_tracks:
                logger.info(f"Found {len(liked_tracks)} liked tracks for user {self.user_id}")
                return liked_tracks
            
            # Fallback to top tracks
            top_tracks = self.spotify_client.get_user_top_tracks(limit=30)
            logger.info(f"Found {len(top_tracks)} top tracks for user {self.user_id}")
            return top_tracks
        
        return []
    
    def _get_mood_based_tracks(self, mood_params: MoodParameters, limit: int) -> List[Dict[str, Any]]:
        """Get tracks that match the mood parameters."""
        if self.service == "spotify" and self.spotify_client:
            mood_tracks = self.spotify_client.search_tracks_by_mood(mood_params, limit=limit * 2)
            logger.info(f"Found {len(mood_tracks)} mood-based tracks for user {self.user_id}")
            return mood_tracks
        elif self.service == "apple_music":
            mood_tracks = apple_music_client.search_tracks_by_mood(mood_params, limit=limit * 2)
            logger.info(f"Found {len(mood_tracks)} Apple Music mood-based tracks for user {self.user_id}")
            return mood_tracks
        
        return []
    
    def _combine_and_select_tracks(
        self,
        user_tracks: List[Dict[str, Any]],
        mood_tracks: List[Dict[str, Any]],
        target_length: int,
        mood_params: MoodParameters
    ) -> List[Dict[str, Any]]:
        """
        Combine user preferences with mood-based tracks and select the best ones.
        
        Args:
            user_tracks: User's preferred tracks
            mood_tracks: Mood-matching tracks
            target_length: Target playlist length
            mood_params: Mood parameters for weighting
        
        Returns:
            List of selected tracks
        """
        # Remove duplicates by track ID
        seen_ids = set()
        all_tracks = []
        
        # Add user tracks first (they get priority)
        for track in user_tracks:
            if track['id'] not in seen_ids:
                track['source'] = 'user_preference'
                track['score'] = 1.0  # High score for user preferences
                all_tracks.append(track)
                seen_ids.add(track['id'])
        
        # Add mood tracks
        for track in mood_tracks:
            if track['id'] not in seen_ids:
                track['source'] = 'mood_based'
                track['score'] = 0.7  # Lower score than user preferences
                all_tracks.append(track)
                seen_ids.add(track['id'])
        
        # If we don't have enough tracks, return what we have
        if len(all_tracks) <= target_length:
            return all_tracks
        
        # Select tracks with a mix of user preferences and mood matching
        # Aim for 60% user preferences, 40% mood-based (if both are available)
        user_pref_tracks = [t for t in all_tracks if t['source'] == 'user_preference']
        mood_based_tracks = [t for t in all_tracks if t['source'] == 'mood_based']
        
        if user_pref_tracks and mood_based_tracks:
            # Mixed approach
            user_count = min(len(user_pref_tracks), int(target_length * 0.6))
            mood_count = target_length - user_count
            
            selected_tracks = user_pref_tracks[:user_count] + mood_based_tracks[:mood_count]
        elif user_pref_tracks:
            # Only user preferences available
            selected_tracks = user_pref_tracks[:target_length]
        else:
            # Only mood-based tracks available
            selected_tracks = mood_based_tracks[:target_length]
        
        logger.info(f"Selected {len(selected_tracks)} tracks: "
                   f"{len([t for t in selected_tracks if t['source'] == 'user_preference'])} user, "
                   f"{len([t for t in selected_tracks if t['source'] == 'mood_based'])} mood-based")
        
        return selected_tracks
    
    def _generate_playlist_name(self, mood_params: MoodParameters, mood_description: str) -> str:
        """Generate a creative playlist name based on mood."""
        # Use mood tags if available
        if mood_params.mood_tags:
            primary_mood = mood_params.mood_tags[0].title()
            return f"🎵 {primary_mood} Vibes"
        
        # Use genre if available
        if mood_params.genre_hints:
            primary_genre = mood_params.genre_hints[0].title()
            return f"🎵 {primary_genre} Mood"
        
        # Use time/activity context
        if mood_params.time_of_day:
            return f"🎵 {mood_params.time_of_day.title()} Mix"
        
        if mood_params.activity:
            return f"🎵 {mood_params.activity.title()} Playlist"
        
        # Fallback based on valence/energy
        if mood_params.valence > 0.7:
            return "🎵 Happy Vibes"
        elif mood_params.valence < 0.3:
            return "🎵 Melancholic Moments"
        elif mood_params.energy > 0.7:
            return "🎵 High Energy Mix"
        elif mood_params.energy < 0.3:
            return "🎵 Chill Playlist"
        else:
            return "🎵 Mood Mix"
    
    def _generate_playlist_description(self, mood_params: MoodParameters, mood_description: str) -> str:
        """Generate playlist description."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Include original mood description (truncated if too long)
        description_text = mood_description
        if len(description_text) > 100:
            description_text = description_text[:97] + "..."
        
        description = f'Generated by Moodtape on {timestamp}\n\n'
        description += f'Mood: "{description_text}"\n\n'
        
        # Add mood characteristics
        if mood_params.mood_tags:
            description += f"Tags: {', '.join(mood_params.mood_tags[:3])}\n"
        
        if mood_params.genre_hints:
            description += f"Genres: {', '.join(mood_params.genre_hints[:3])}\n"
        
        description += f"\nCreated with ❤️ by Moodtape"
        
        return description
    
    async def _create_playlist(
        self,
        name: str,
        description: str,
        tracks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Create the actual playlist in the music service."""
        if self.service == "spotify" and self.spotify_client:
            track_uris = [track['uri'] for track in tracks if track.get('uri')]
            
            if not track_uris:
                logger.error(f"No valid track URIs found for user {self.user_id}")
                return None
            
            return self.spotify_client.create_playlist(
                name=name,
                description=description,
                track_uris=track_uris,
                public=False  # Keep playlists private by default
            )
        elif self.service == "apple_music":
            # Apple Music: create a deep link playlist
            playlist_link = apple_music_client.create_playlist_link(tracks, name)
            
            if not playlist_link:
                logger.error(f"Failed to create Apple Music playlist link for user {self.user_id}")
                return None
            
            return {
                'id': f"apple_music_{int(time.time())}",  # Generate a unique ID
                'name': name,
                'url': playlist_link,
                'track_count': len(tracks),
                'service': 'apple_music'
            }
        
        return None


def create_user_playlist(
    user_id: int,
    service: str,
    mood_params: MoodParameters,
    mood_description: str,
    playlist_length: int = 20
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to create a playlist for a user.
    
    Args:
        user_id: Telegram user ID
        service: Music service (spotify, apple_music)
        mood_params: Parsed mood parameters
        mood_description: Original mood description
        playlist_length: Desired playlist length
    
    Returns:
        Playlist info dict or None if failed
    """
    builder = PlaylistBuilder(user_id, service)
    
    # Note: This would ideally be async, but keeping sync for simplicity
    # In production, you'd want to use asyncio.run() or similar
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            builder.build_mood_playlist(mood_params, mood_description, playlist_length)
        )
    finally:
        loop.close() 