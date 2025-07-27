"""
Smart search strategies for Spotify track discovery based on mood parameters.
Replaces simple genre search with intelligent multi-strategy approach.
"""

import random
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

import spotipy
from spotipy.exceptions import SpotifyException

from moodtape_core.gpt_parser import MoodParameters
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Container for search results with metadata."""
    tracks: List[Dict[str, Any]]
    source: str  # Which search strategy found these tracks
    query: str   # The actual search query used
    success: bool = True
    error_message: Optional[str] = None


class SmartSearchStrategy:
    """Advanced search strategy for finding mood-matching tracks in Spotify."""
    
    def __init__(self, spotify_client):
        """
        Initialize smart search with Spotify client.
        
        Args:
            spotify_client: SpotifyClient instance with authenticated access
        """
        self.spotify_client = spotify_client
        
        # Safe client access with fallback
        if spotify_client:
            if hasattr(spotify_client, 'client') and spotify_client.client:
                self.client = spotify_client.client
            elif hasattr(spotify_client, 'sp') and spotify_client.sp:
                self.client = spotify_client.sp  # Alternative attribute name
            else:
                self.client = spotify_client  # Direct spotipy instance
        else:
            self.client = None
            
        self.logger = get_logger(__name__)
        
        # Initialize context mappings
        self._init_context_mappings()
        
    def _safe_get_nested(self, obj: Any, path: str, default: Any = None) -> Any:
        """
        Safely get nested attribute with fallback support.
        
        Args:
            obj: Object to get attribute from
            path: Dot-separated path (e.g., 'audio_features.valence')
            default: Default value if path not found
            
        Returns:
            Value at path or default
        """
        try:
            current = obj
            for attr in path.split('.'):
                if hasattr(current, attr):
                    current = getattr(current, attr)
                else:
                    return default
            return current
        except (AttributeError, TypeError):
            return default
    
    def _get_audio_features(self, mood_params: MoodParameters) -> Dict[str, Any]:
        """Get audio features with nested structure support."""
        # Try nested structure first
        if hasattr(mood_params, 'audio_features'):
            af = mood_params.audio_features
            return {
                'valence': getattr(af, 'valence', 0.5),
                'energy': getattr(af, 'energy', 0.5),
                'danceability': getattr(af, 'danceability', 0.5),
                'acousticness': getattr(af, 'acousticness', 0.5),
                'instrumentalness': getattr(af, 'instrumentalness', 0.5),
                'speechiness': getattr(af, 'speechiness', 0.1),
                'tempo': getattr(af, 'tempo', 120),
                'loudness': getattr(af, 'loudness', -8.0),
                'mode': getattr(af, 'mode', 1),
            }
        else:
            # Fallback to flat structure
            return {
                'valence': getattr(mood_params, 'valence', 0.5),
                'energy': getattr(mood_params, 'energy', 0.5),
                'danceability': getattr(mood_params, 'danceability', 0.5),
                'acousticness': getattr(mood_params, 'acousticness', 0.5),
                'instrumentalness': getattr(mood_params, 'instrumentalness', 0.5),
                'speechiness': getattr(mood_params, 'speechiness', 0.1),
                'tempo': getattr(mood_params, 'tempo', 120),
                'loudness': getattr(mood_params, 'loudness', -8.0),
                'mode': getattr(mood_params, 'mode', 1),
            }
    
    def _get_context_info(self, mood_params: MoodParameters) -> Dict[str, Any]:
        """Get context information with nested structure support."""
        # Try nested structure first
        if hasattr(mood_params, 'context'):
            ctx = mood_params.context
            return {
                'mood_tags': getattr(ctx, 'mood_tags', []),
                'activity': getattr(ctx, 'activity', None),
                'time_of_day': getattr(ctx, 'time_of_day', None),
                'weather': getattr(ctx, 'weather', None),
                'social': getattr(ctx, 'social', None),
                'emotional_intensity': getattr(ctx, 'emotional_intensity', 0.5),
            }
        else:
            # Fallback to flat structure
            return {
                'mood_tags': getattr(mood_params, 'mood_tags', []),
                'activity': getattr(mood_params, 'activity', None),
                'time_of_day': getattr(mood_params, 'time_of_day', None),
                'weather': getattr(mood_params, 'weather', None),
                'social': getattr(mood_params, 'social', None),
                'emotional_intensity': getattr(mood_params, 'emotional_intensity', 0.5),
            }
    
    def _get_preferences(self, mood_params: MoodParameters) -> Dict[str, Any]:
        """Get preferences with nested structure support."""
        # Try nested structure first
        if hasattr(mood_params, 'preferences'):
            prefs = mood_params.preferences
            # Handle nested genres structure
            if hasattr(prefs, 'genres'):
                genres = prefs.genres
                primary_genres = getattr(genres, 'primary', [])
                secondary_genres = getattr(genres, 'secondary', [])
                exclude_genres = getattr(genres, 'exclude', [])
            else:
                # Flat preferences structure
                primary_genres = getattr(prefs, 'primary_genres', [])
                secondary_genres = getattr(prefs, 'secondary_genres', [])
                exclude_genres = getattr(prefs, 'exclude_genres', [])
                
            return {
                'primary_genres': primary_genres,
                'secondary_genres': secondary_genres,
                'exclude_genres': exclude_genres,
                'popularity_range': getattr(prefs, 'popularity_range', [20, 80]),
                'decade_bias': getattr(prefs, 'decade_bias', None),
            }
        else:
            # Fallback to flat structure
            return {
                'primary_genres': getattr(mood_params, 'primary_genres', []),
                'secondary_genres': getattr(mood_params, 'secondary_genres', []),
                'exclude_genres': getattr(mood_params, 'exclude_genres', []),
                'popularity_range': getattr(mood_params, 'popularity_range', [20, 80]),
                'decade_bias': getattr(mood_params, 'decade_bias', None),
            }
    
    def _init_context_mappings(self):
        """Initialize context mappings for intelligent search."""
        # Context mappings for intelligent search
        self.activity_keywords = {
            "working": ["focus", "concentration", "productive", "study"],
            "exercising": ["workout", "gym", "running", "fitness", "motivation"],
            "relaxing": ["chill", "calm", "peaceful", "ambient", "relax"],
            "studying": ["focus", "concentration", "instrumental", "calm"],
            "commuting": ["upbeat", "energetic", "motivational"],
            "partying": ["party", "dance", "upbeat", "celebration"],
            "sleeping": ["ambient", "peaceful", "soft", "quiet"]
        }
        
        self.time_keywords = {
            "morning": ["sunrise", "fresh", "energetic", "wake up", "new day"],
            "afternoon": ["productive", "focused", "steady"],
            "evening": ["sunset", "winding down", "mellow", "golden hour"],
            "night": ["nocturnal", "intimate", "moody", "late night"],
            "late_night": ["deep", "atmospheric", "introspective"]
        }
        
        self.weather_keywords = {
            "sunny": ["bright", "cheerful", "summer", "warm"],
            "rainy": ["moody", "melancholic", "atmospheric", "cozy"],
            "cloudy": ["mellow", "contemplative", "soft"],
            "snowy": ["winter", "cozy", "peaceful", "serene"],
            "stormy": ["dramatic", "powerful", "intense"],
            "foggy": ["mysterious", "atmospheric", "ambient"]
        }
    
    def search_mood_tracks(
        self,
        mood_params: MoodParameters,
        total_limit: int = 200,
        market: str = 'US'
    ) -> List[Dict[str, Any]]:
        """
        Main method that combines all search strategies to find mood-matching tracks.
        
        Args:
            mood_params: Parsed mood parameters
            total_limit: Maximum total tracks to return across all strategies
            market: Spotify market code (e.g., 'US', 'GB', 'RU')
            
        Returns:
            List of deduplicated tracks from all search strategies
        """
        if not self.client:
            self.logger.error("No Spotify client available for smart search")
            return []
        
        # Get structured data with fallbacks
        audio_features = self._get_audio_features(mood_params)
        context_info = self._get_context_info(mood_params)
        preferences = self._get_preferences(mood_params)
        
        self.logger.info(f"Starting smart search for mood: valence={audio_features['valence']:.2f}, "
                        f"energy={audio_features['energy']:.2f}, tags={context_info['mood_tags']}, market={market}")
        
        all_results = []
        strategy_limits = {
            "genres": min(60, total_limit // 4),
            "recommendations": min(80, total_limit // 3),
            "playlists": min(40, total_limit // 5),
            "context": min(40, total_limit // 5)
        }
        
        # Strategy 1: Genre-based search with mood tags
        genre_results = self.search_by_genres(mood_params, strategy_limits["genres"], market)
        all_results.extend(genre_results.tracks)
        self.logger.info(f"Genre search found {len(genre_results.tracks)} tracks")
        
        # Strategy 2: Spotify Recommendations API
        recommendations_results = self.search_recommendations(mood_params, strategy_limits["recommendations"], market)
        all_results.extend(recommendations_results.tracks)
        self.logger.info(f"Recommendations API found {len(recommendations_results.tracks)} tracks")
        
        # Strategy 3: Featured playlists search
        playlists_results = self.search_featured_playlists(mood_params, strategy_limits["playlists"], market)
        all_results.extend(playlists_results.tracks)
        self.logger.info(f"Featured playlists found {len(playlists_results.tracks)} tracks")
        
        # Strategy 4: Context-based search
        context_results = self.search_by_context(mood_params, strategy_limits["context"], market)
        all_results.extend(context_results.tracks)
        self.logger.info(f"Context search found {len(context_results.tracks)} tracks")
        
        # Deduplicate tracks by ID
        deduplicated_tracks = self._deduplicate_tracks(all_results)
        
        # Shuffle for variety and limit to total_limit
        random.shuffle(deduplicated_tracks)
        final_tracks = deduplicated_tracks[:total_limit]
        
        self.logger.info(f"Smart search completed: {len(all_results)} total → "
                        f"{len(deduplicated_tracks)} unique → {len(final_tracks)} final tracks")
        
        return final_tracks
    
    def search_by_genres(self, mood_params: MoodParameters, limit: int = 60, market: str = 'US') -> SearchResult:
        """
        Strategy 1: Enhanced genre search combining genres with mood tags.
        
        Args:
            mood_params: Mood parameters with genre preferences and mood tags
            limit: Maximum tracks to return
            market: Spotify market code
            
        Returns:
            SearchResult with tracks found through genre + mood combination
        """
        tracks = []
        
        try:
            # Get structured data with fallbacks
            preferences = self._get_preferences(mood_params)
            context_info = self._get_context_info(mood_params)
            
            # Get genres from preferences
            primary_genres = preferences['primary_genres'] if preferences['primary_genres'] else []
            secondary_genres = preferences['secondary_genres'] if preferences['secondary_genres'] else []
            all_genres = (primary_genres + secondary_genres)[:4]  # Max 4 genres
            
            # Get mood tags from context
            mood_tags = context_info['mood_tags'][:3] if context_info['mood_tags'] else []
            
            if not all_genres:
                # Fallback to legacy genre_hints if available
                if hasattr(mood_params, 'genre_hints') and mood_params.genre_hints:
                    all_genres = mood_params.genre_hints[:4]
                else:
                    self.logger.warning("No genres available for genre-based search")
                    return SearchResult([], "genres", "no_genres", success=False, 
                                      error_message="No genres available")
            
            # Create smart search queries combining genres with mood tags
            search_queries = []
            
            # Primary strategy: genre + mood tag combinations
            for genre in all_genres[:2]:  # Use top 2 genres
                for mood_tag in mood_tags[:2]:  # Use top 2 mood tags
                    query = f"genre:{genre} {mood_tag}"
                    search_queries.append(query)
            
            # Secondary strategy: pure genre searches for broader results
            for genre in all_genres:
                search_queries.append(f"genre:{genre}")
            
            # Execute searches
            tracks_per_query = max(1, limit // len(search_queries)) if search_queries else limit
            
            for query in search_queries[:6]:  # Limit to 6 queries max
                try:
                    results = self.client.search(
                        q=query,
                        type='track',
                        limit=min(tracks_per_query, 20),  # Max 20 per query
                        market=market
                    )
                    
                    for track in results['tracks']['items']:
                        if len(tracks) >= limit:
                            break
                            
                        track_info = self._format_track_data(track, "genre_mood_search", query)
                        tracks.append(track_info)
                    
                    if len(tracks) >= limit:
                        break
                        
                except SpotifyException as e:
                    self.logger.warning(f"Error in genre search '{query}': {e}")
                    continue
            
            query_summary = f"genres: {', '.join(all_genres)}, tags: {', '.join(mood_tags)}"
            return SearchResult(tracks, "genres", query_summary)
            
        except Exception as e:
            self.logger.error(f"Error in search_by_genres: {e}")
            return SearchResult([], "genres", "error", success=False, error_message=str(e))
    
    def search_recommendations(self, mood_params: MoodParameters, limit: int = 80, market: str = 'US') -> SearchResult:
        """
        Strategy 2: Spotify Recommendations API with precise audio feature targeting.
        
        Args:
            mood_params: Mood parameters with audio features
            limit: Maximum tracks to return
            market: Spotify market code
            
        Returns:
            SearchResult with tracks from Spotify Recommendations API
        """
        tracks = []
        
        try:
            # Get structured data with fallbacks
            preferences = self._get_preferences(mood_params)
            audio_features = self._get_audio_features(mood_params)
            
            # Prepare seed genres (max 5 for Spotify API)
            seed_genres = []
            if preferences['primary_genres']:
                seed_genres.extend(preferences['primary_genres'][:2])
            if preferences['secondary_genres']:
                seed_genres.extend(preferences['secondary_genres'][:2])
            
            # Fallback to legacy genre_hints
            if not seed_genres and hasattr(mood_params, 'genre_hints'):
                seed_genres = mood_params.genre_hints[:3]
            
            if not seed_genres:
                seed_genres = ["pop"]  # Ultimate fallback
            
            seed_genres = seed_genres[:5]  # Spotify API limit
            
            # Prepare recommendation parameters with ranges for better diversity
            rec_params = {
                'seed_genres': seed_genres,
                'limit': min(limit, 100),  # Spotify API limit
                'market': market,
                
                # Target values (ideal)
                'target_valence': audio_features['valence'],
                'target_energy': audio_features['energy'],
                'target_danceability': audio_features['danceability'],
                'target_acousticness': audio_features['acousticness'],
                'target_tempo': audio_features['tempo'],
                
                # Min/Max ranges for controlled diversity (±20% from target)
                'min_valence': max(0.0, audio_features['valence'] - 0.2),
                'max_valence': min(1.0, audio_features['valence'] + 0.2),
                'min_energy': max(0.0, audio_features['energy'] - 0.2),
                'max_energy': min(1.0, audio_features['energy'] + 0.2),
                'min_danceability': max(0.0, audio_features['danceability'] - 0.2),
                'max_danceability': min(1.0, audio_features['danceability'] + 0.2),
                
                # Tempo range (±15 BPM)
                'min_tempo': max(50, audio_features['tempo'] - 15),
                'max_tempo': min(200, audio_features['tempo'] + 15),
            }
            
            # Add popularity constraint if specified
            if preferences['popularity_range']:
                min_pop, max_pop = preferences['popularity_range']
                rec_params['min_popularity'] = min_pop
                rec_params['max_popularity'] = max_pop
            
            self.logger.info(f"Spotify Recommendations with genres: {seed_genres}, "
                           f"valence: {audio_features['valence']:.2f}, energy: {audio_features['energy']:.2f}")
            
            # Get recommendations
            results = self.client.recommendations(**rec_params)
            
            for track in results['tracks']:
                track_info = self._format_track_data(track, "recommendations", f"genres: {', '.join(seed_genres)}")
                tracks.append(track_info)
            
            query_summary = f"recommendations: {', '.join(seed_genres)}"
            return SearchResult(tracks, "recommendations", query_summary)
            
        except SpotifyException as e:
            self.logger.error(f"Error in Spotify Recommendations API: {e}")
            return SearchResult([], "recommendations", "api_error", success=False, error_message=str(e))
        except Exception as e:
            self.logger.error(f"Error in search_recommendations: {e}")
            return SearchResult([], "recommendations", "error", success=False, error_message=str(e))
    
    def search_featured_playlists(self, mood_params: MoodParameters, limit: int = 40, market: str = 'US') -> SearchResult:
        """
        Strategy 3: Search featured playlists and extract tracks from mood-matching playlists.
        
        Args:
            mood_params: Mood parameters with mood tags
            limit: Maximum tracks to return
            market: Spotify market code
            
        Returns:
            SearchResult with tracks extracted from featured playlists
        """
        tracks = []
        
        try:
            # Get structured data with fallbacks
            context_info = self._get_context_info(mood_params)
            
            # Create playlist search queries from mood tags and context
            playlist_queries = []
            
            # Add mood tags as playlist search terms
            if context_info['mood_tags']:
                playlist_queries.extend(context_info['mood_tags'][:3])
            
            # Add activity-based playlist search
            if context_info['activity'] and context_info['activity'] in self.activity_keywords:
                playlist_queries.extend(self.activity_keywords[context_info['activity']][:2])
            
            # Add time-based playlist search
            if context_info['time_of_day'] and context_info['time_of_day'] in self.time_keywords:
                playlist_queries.extend(self.time_keywords[context_info['time_of_day']][:2])
            
            # Fallback queries if no specific tags
            if not playlist_queries:
                playlist_queries = ["chill", "mood", "vibes"]
            
            # Search for playlists using these terms
            playlists_found = []
            for query in playlist_queries[:5]:  # Limit to 5 queries
                try:
                    results = self.client.search(
                        q=query,
                        type='playlist',
                        limit=3,  # 3 playlists per query
                        market=market
                    )
                    
                    for playlist in results['playlists']['items']:
                        if playlist and playlist['tracks']['total'] > 10:  # Only consider substantial playlists
                            playlists_found.append({
                                'id': playlist['id'],
                                'name': playlist['name'],
                                'query': query
                            })
                    
                except SpotifyException as e:
                    self.logger.warning(f"Error searching playlists for '{query}': {e}")
                    continue
            
            # Extract tracks from found playlists
            tracks_per_playlist = max(1, limit // len(playlists_found)) if playlists_found else limit
            
            for playlist in playlists_found[:8]:  # Max 8 playlists
                try:
                    playlist_tracks = self.client.playlist_tracks(
                        playlist['id'],
                        limit=min(tracks_per_playlist, 15),  # Max 15 tracks per playlist
                        market=market
                    )
                    
                    for item in playlist_tracks['items']:
                        if len(tracks) >= limit:
                            break
                            
                        track = item['track']
                        if track and track['id']:  # Valid track
                            track_info = self._format_track_data(
                                track, "featured_playlist", 
                                f"playlist: {playlist['name'][:30]}"
                            )
                            tracks.append(track_info)
                    
                    if len(tracks) >= limit:
                        break
                        
                except SpotifyException as e:
                    self.logger.warning(f"Error extracting tracks from playlist {playlist['name']}: {e}")
                    continue
            
            query_summary = f"playlists: {', '.join(playlist_queries[:3])}"
            return SearchResult(tracks, "featured_playlists", query_summary)
            
        except Exception as e:
            self.logger.error(f"Error in search_featured_playlists: {e}")
            return SearchResult([], "featured_playlists", "error", success=False, error_message=str(e))
    
    def search_by_context(self, mood_params: MoodParameters, limit: int = 40, market: str = 'US') -> SearchResult:
        """
        Strategy 4: Context-aware search based on activity, time, weather, and social setting.
        
        Args:
            mood_params: Mood parameters with context information
            limit: Maximum tracks to return
            market: Spotify market code
            
        Returns:
            SearchResult with tracks found through context-aware search
        """
        tracks = []
        
        try:
            # Get structured data with fallbacks
            context_info = self._get_context_info(mood_params)
            
            # Build context-based search queries
            context_queries = []
            
            # Activity-based queries
            if context_info['activity'] and context_info['activity'] in self.activity_keywords:
                activity_terms = self.activity_keywords[context_info['activity']]
                for term in activity_terms[:2]:
                    context_queries.append(f"{term} music")
            
            # Time-based queries
            if context_info['time_of_day'] and context_info['time_of_day'] in self.time_keywords:
                time_terms = self.time_keywords[context_info['time_of_day']]
                for term in time_terms[:2]:
                    context_queries.append(f"{term} songs")
            
            # Weather-based queries
            if context_info['weather'] and context_info['weather'] in self.weather_keywords:
                weather_terms = self.weather_keywords[context_info['weather']]
                for term in weather_terms[:1]:
                    context_queries.append(f"{term} music")
            
            # Social setting queries
            if context_info['social']:
                social_map = {
                    "alone": ["solo", "introspective"],
                    "romantic": ["romantic", "love"],
                    "friends": ["hanging out", "social"],
                    "party": ["party", "celebration"],
                    "crowd": ["energetic", "upbeat"]
                }
                if context_info['social'] in social_map:
                    for term in social_map[context_info['social']][:1]:
                        context_queries.append(f"{term} playlist")
            
            # Emotional intensity context
            if context_info['emotional_intensity'] > 0.7:
                context_queries.append("intense music")
            elif context_info['emotional_intensity'] < 0.3:
                context_queries.append("subtle music")
            
            # Fallback if no context
            if not context_queries:
                context_queries = ["mood music", "atmospheric"]
            
            # Execute context searches
            tracks_per_query = max(1, limit // len(context_queries)) if context_queries else limit
            
            for query in context_queries[:6]:  # Limit to 6 queries
                try:
                    results = self.client.search(
                        q=query,
                        type='track',
                        limit=min(tracks_per_query, 15),  # Max 15 per query
                        market=market
                    )
                    
                    for track in results['tracks']['items']:
                        if len(tracks) >= limit:
                            break
                            
                        track_info = self._format_track_data(track, "context_search", query)
                        tracks.append(track_info)
                    
                    if len(tracks) >= limit:
                        break
                        
                except SpotifyException as e:
                    self.logger.warning(f"Error in context search '{query}': {e}")
                    continue
            
            query_summary = f"context: {', '.join(context_queries[:3])}"
            return SearchResult(tracks, "context", query_summary)
            
        except Exception as e:
            self.logger.error(f"Error in search_by_context: {e}")
            return SearchResult([], "context", "error", success=False, error_message=str(e))
    
    def _format_track_data(self, track: Dict[str, Any], discovery_method: str, query: str) -> Dict[str, Any]:
        """
        Format track data into standardized structure.
        
        Args:
            track: Spotify track object
            discovery_method: How this track was discovered
            query: The search query that found this track
            
        Returns:
            Formatted track dictionary
        """
        # Extract artist names
        artists = []
        for artist in track.get('artists', []):
            artists.append({
                'name': artist['name'],
                'id': artist['id']
            })
        
        return {
            'id': track['id'],
            'name': track['name'],
            'artists': artists,
            'uri': track['uri'],
            'popularity': track.get('popularity', 0),
            'duration_ms': track.get('duration_ms', 0),
            'explicit': track.get('explicit', False),
            'preview_url': track.get('preview_url'),
            'external_urls': track.get('external_urls', {}),
            
            # Discovery metadata
            'discovery_method': discovery_method,
            'search_query': query,
            'audio_features': None,  # Will be filled later if needed
            'genres': []  # Will be filled later if needed
        }
    
    def _deduplicate_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate tracks by ID, keeping the first occurrence.
        
        Args:
            tracks: List of track dictionaries
            
        Returns:
            Deduplicated list of tracks
        """
        seen_ids: Set[str] = set()
        deduplicated = []
        
        for track in tracks:
            track_id = track.get('id')
            if track_id and track_id not in seen_ids:
                seen_ids.add(track_id)
                deduplicated.append(track)
        
        return deduplicated
    
    def get_search_analytics(self, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate analytics about search results for debugging and optimization.
        
        Args:
            tracks: List of tracks from search
            
        Returns:
            Analytics dictionary with search method breakdown
        """
        analytics = {
            'total_tracks': len(tracks),
            'by_method': defaultdict(int),
            'by_query': defaultdict(int),
            'unique_artists': set(),
            'popularity_stats': {
                'min': 100, 'max': 0, 'avg': 0
            }
        }
        
        popularity_scores = []
        
        for track in tracks:
            # Count by discovery method
            method = track.get('discovery_method', 'unknown')
            analytics['by_method'][method] += 1
            
            # Count by query
            query = track.get('search_query', 'unknown')
            analytics['by_query'][query] += 1
            
            # Collect unique artists
            for artist in track.get('artists', []):
                analytics['unique_artists'].add(artist['name'])
            
            # Popularity stats
            popularity = track.get('popularity', 0)
            popularity_scores.append(popularity)
        
        # Calculate popularity statistics
        if popularity_scores:
            analytics['popularity_stats']['min'] = min(popularity_scores)
            analytics['popularity_stats']['max'] = max(popularity_scores)
            analytics['popularity_stats']['avg'] = sum(popularity_scores) / len(popularity_scores)
        
        analytics['unique_artists'] = len(analytics['unique_artists'])
        analytics['by_method'] = dict(analytics['by_method'])
        analytics['by_query'] = dict(analytics['by_query'])
        
        return analytics


def create_smart_search_strategy(spotify_client) -> SmartSearchStrategy:
    """
    Factory function to create a SmartSearchStrategy instance.
    
    Args:
        spotify_client: Authenticated SpotifyClient instance
        
    Returns:
        Configured SmartSearchStrategy
    """
    return SmartSearchStrategy(spotify_client) 