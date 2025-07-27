"""Playlist builder that combines mood analysis with user preferences."""

import uuid
import time
import asyncio
import random
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

from moodtape_core.gpt_parser import MoodParameters
from moodtape_core.improved_scoring import (
    ImprovedTrackScorer, SmartTrackFilter, SpotifyTrackEnricher, MoodPlaylistBuilder,
    default_scorer, default_filter, default_enricher
)
from moodtape_core.smart_search import SmartSearchStrategy, create_smart_search_strategy
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
            logger.info(f"Mood params: valence={mood_params.valence:.2f}, energy={mood_params.energy:.2f}")
            logger.info(f"Mood tags: {mood_params.mood_tags}")
            logger.info(f"Primary genres: {getattr(mood_params, 'primary_genres', [])}")
            logger.info(f"Secondary genres: {getattr(mood_params, 'secondary_genres', [])}")
            logger.info(f"Legacy genre_hints: {getattr(mood_params, 'genre_hints', [])}")
            
            # Get tracks from different sources
            if self.service == "spotify":
                logger.info("Getting user preference tracks...")
                # Spotify: user preferences + mood-based tracks
                user_tracks = self._get_user_preference_tracks()
                logger.info(f"Found {len(user_tracks)} user preference tracks")
                
                logger.info("Getting mood-based tracks...")
                mood_tracks = self._get_mood_based_tracks(mood_params, playlist_length)
                logger.info(f"Found {len(mood_tracks)} mood-based tracks")
                
                # Combine and select best tracks
                logger.info("Combining and selecting tracks...")
                final_tracks = self._combine_and_select_tracks(
                    user_tracks=user_tracks,
                    mood_tracks=mood_tracks,
                    target_length=playlist_length,
                    mood_params=mood_params
                )
                logger.info(f"Selected {len(final_tracks)} final tracks")
            else:
                # Apple Music: only mood-based tracks (no user preferences)
                mood_tracks = self._get_mood_based_tracks(mood_params, playlist_length)
                final_tracks = mood_tracks[:playlist_length]
            
            if not final_tracks:
                logger.error(f"No tracks found for user {self.user_id} - this is the main problem!")
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
            logger.info("Generating playlist name and description...")
            playlist_name = self._generate_playlist_name(mood_params, mood_description)
            playlist_description = self._generate_playlist_description(mood_params, mood_description)
            logger.info(f"Playlist name: '{playlist_name}'")
            
            logger.info("Creating playlist in Spotify...")
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
            all_user_tracks = []
            
            # Get a mix of liked tracks and top tracks for better variety
            # Try to get liked tracks first (recent additions)
            liked_tracks = self.spotify_client.get_user_liked_tracks(limit=20)
            if liked_tracks:
                all_user_tracks.extend(liked_tracks)
                logger.info(f"Found {len(liked_tracks)} liked tracks for user {self.user_id}")
            
            # Add top tracks from different time periods for variety
            for time_range in ["short_term", "medium_term", "long_term"]:
                top_tracks = self.spotify_client.get_user_top_tracks(time_range=time_range, limit=10)
                all_user_tracks.extend(top_tracks)
                logger.info(f"Found {len(top_tracks)} {time_range} top tracks for user {self.user_id}")
            
            # Remove duplicates while preserving order
            seen_ids = set()
            unique_tracks = []
            for track in all_user_tracks:
                if track['id'] not in seen_ids:
                    unique_tracks.append(track)
                    seen_ids.add(track['id'])
            
            # Shuffle to avoid only recent tracks and limit to reasonable number
            random.shuffle(unique_tracks)
            final_tracks = unique_tracks[:30]  # Keep max 30 for balance
            
            logger.info(f"Final user track selection: {len(final_tracks)} tracks (from {len(all_user_tracks)} total)")
            return final_tracks
        
        return []
    
    def _get_mood_based_tracks(self, mood_params: MoodParameters, limit: int) -> List[Dict[str, Any]]:
        """Get tracks that match the mood parameters with intelligent filtering."""
        if self.service == "spotify" and self.spotify_client:
            logger.info(f"Starting intelligent mood-based track search for user {self.user_id}")
            
            # Get user's known tracks to exclude them from discovery
            user_liked_ids = set()
            try:
                liked_tracks = self.spotify_client.get_user_liked_tracks(limit=50)
                user_liked_ids = {track['id'] for track in liked_tracks}
                logger.info(f"Excluding {len(user_liked_ids)} user's liked tracks from discovery")
            except Exception as e:
                logger.warning(f"Could not get user's liked tracks for filtering: {e}")
            
            # Get a larger pool of mood-based tracks for intelligent filtering
            search_limit = limit * 5  # Get 5x more tracks for better filtering
            logger.info(f"Searching for {search_limit} candidate tracks to filter from")
            
            try:
                candidate_tracks = self.spotify_client.search_tracks_by_mood(mood_params, limit=search_limit)
                logger.info(f"Retrieved {len(candidate_tracks)} candidate tracks from Spotify")
            except Exception as e:
                logger.error(f"Error in search_tracks_by_mood: {e}")
                return []
            
            if not candidate_tracks:
                logger.warning("No candidate tracks found from Spotify search")
                return []
            
            # Filter out tracks user already knows
            discovery_candidates = []
            for track in candidate_tracks:
                if track['id'] not in user_liked_ids:
                    discovery_candidates.append(track)
            
            logger.info(f"Filtered to {len(discovery_candidates)} new discovery candidates")
            
            if not discovery_candidates:
                logger.warning("No new discovery tracks found after filtering known tracks")
                return candidate_tracks[:limit * 2]  # Fallback to original tracks
            
            # Enrich candidates with audio features for intelligent filtering
            try:
                enriched_candidates = self._enrich_tracks_with_audio_features(discovery_candidates)
                logger.info(f"Enriched {len(enriched_candidates)} tracks with audio features")
            except Exception as e:
                logger.warning(f"Failed to enrich tracks with audio features: {e}")
                enriched_candidates = discovery_candidates
            
            # Apply intelligent filtering using SmartTrackFilter
            try:
                smart_filter = SmartTrackFilter(default_scorer)
                filtered_tracks = smart_filter.filter_and_rank_tracks(
                    tracks=enriched_candidates,
                    mood_params=mood_params,
                    target_count=limit * 2,  # Get 2x more than needed for final selection
                    min_score_threshold=0.20  # Higher threshold for mood-only tracks
                )
                
                final_discovery_tracks = [track for track, score in filtered_tracks]
                
                logger.info(f"Smart filtering selected {len(final_discovery_tracks)} high-quality mood tracks")
                
                # Log top scoring tracks for debugging
                if filtered_tracks:
                    logger.info("Top mood-based tracks:")
                    for i, (track, score) in enumerate(filtered_tracks[:3]):
                        artists = ', '.join([a.get('name', 'Unknown') for a in track.get('artists', [])])
                        logger.info(f"  {i+1}. '{track.get('name', 'Unknown')}' by {artists} (score: {score:.3f})")
                
                return final_discovery_tracks
                
            except Exception as e:
                logger.error(f"Error in smart filtering: {e}")
                # Fallback to simple filtering
                logger.info("Falling back to simple track selection")
                return discovery_candidates[:limit * 2]
    
    def _get_mood_based_tracks_with_smart_search(self, mood_params: MoodParameters, limit: int) -> List[Dict[str, Any]]:
        """
        Alternative method using SmartSearchStrategy for enhanced mood-based track discovery.
        
        Args:
            mood_params: Mood parameters for intelligent search
            limit: Target number of tracks
            
        Returns:
            List of tracks found through smart search strategies
        """
        if self.service == "spotify" and self.spotify_client:
            try:
                logger.info(f"Using SmartSearchStrategy for enhanced mood-based discovery")
                
                # Create smart search strategy
                smart_search = create_smart_search_strategy(self.spotify_client)
                
                # Use smart search to find tracks (gets ~200 candidates)
                candidate_tracks = smart_search.search_mood_tracks(mood_params, total_limit=limit * 10)
                
                if not candidate_tracks:
                    logger.warning("SmartSearchStrategy returned no tracks")
                    return []
                
                # Get analytics about search results
                analytics = smart_search.get_search_analytics(candidate_tracks)
                logger.info(f"Smart search analytics: {analytics['total_tracks']} tracks from "
                           f"{len(analytics['by_method'])} methods, {analytics['unique_artists']} unique artists")
                
                # Filter out tracks user already knows
                user_liked_ids = set()
                try:
                    liked_tracks = self.spotify_client.get_user_liked_tracks(limit=50)
                    user_liked_ids = {track['id'] for track in liked_tracks}
                    logger.info(f"Excluding {len(user_liked_ids)} user's known tracks from smart search results")
                except Exception as e:
                    logger.warning(f"Could not get user's liked tracks for filtering: {e}")
                
                # Filter out known tracks
                discovery_candidates = []
                for track in candidate_tracks:
                    if track['id'] not in user_liked_ids:
                        discovery_candidates.append(track)
                
                logger.info(f"Smart search found {len(candidate_tracks)} candidates, "
                           f"{len(discovery_candidates)} are new discoveries")
                
                # Apply smart scoring and filtering
                try:
                    # Enrich with audio features
                    enricher = SpotifyTrackEnricher(self.spotify_client)
                    enriched_candidates = enricher.enrich_tracks_with_audio_features(discovery_candidates)
                    
                    # Apply intelligent filtering
                    smart_filter = SmartTrackFilter(default_scorer)
                    filtered_tracks = smart_filter.filter_and_rank_tracks(
                        tracks=enriched_candidates,
                        mood_params=mood_params,
                        target_count=limit * 2,
                        min_score_threshold=0.15  # Lower threshold for smart search results
                    )
                    
                    final_tracks = [track for track, score in filtered_tracks]
                    
                    # Log search method breakdown
                    method_breakdown = defaultdict(int)
                    for track in final_tracks:
                        method = track.get('discovery_method', 'unknown')
                        method_breakdown[method] += 1
                    
                    logger.info(f"Smart search final selection: {len(final_tracks)} tracks")
                    logger.info(f"Discovery methods: {dict(method_breakdown)}")
                    
                    return final_tracks[:limit * 2]  # Return 2x for final selection
                    
                except Exception as e:
                    logger.error(f"Error in smart search filtering: {e}")
                    # Return raw smart search results as fallback
                    return discovery_candidates[:limit * 2]
                
            except Exception as e:
                logger.error(f"Error in smart search strategy: {e}")
                # Fallback to original method
                logger.info("Falling back to original search method")
                return self._get_mood_based_tracks(mood_params, limit)
        
        elif self.service == "apple_music":
            try:
                mood_tracks = apple_music_client.search_tracks_by_mood(mood_params, limit=limit * 2)
                logger.info(f"Found {len(mood_tracks)} Apple Music mood-based tracks for user {self.user_id}")
                return mood_tracks
            except Exception as e:
                logger.error(f"Error getting Apple Music tracks: {e}")
                return []
        
        else:
            logger.warning(f"Smart search not available for service={self.service}, spotify_client={self.spotify_client}")
            return []
    
    def _combine_and_select_tracks(
        self,
        user_tracks: List[Dict[str, Any]],
        mood_tracks: List[Dict[str, Any]],
        target_length: int,
        mood_params: MoodParameters
    ) -> List[Dict[str, Any]]:
        """
        Combine user preferences with mood-based tracks and select the best ones using improved scoring.
        
        Args:
            user_tracks: User's preferred tracks
            mood_tracks: Mood-matching tracks
            target_length: Target playlist length
            mood_params: Mood parameters for weighting
        
        Returns:
            List of selected tracks
        """
        logger.info(f"Starting intelligent track combination: {len(user_tracks)} user tracks, {len(mood_tracks)} mood tracks")
        
        # Remove duplicates by track ID
        seen_ids = set()
        all_tracks = []
        
        # Add user tracks with source metadata
        for track in user_tracks:
            if track['id'] not in seen_ids:
                track['source'] = 'user_preference'
                all_tracks.append(track)
                seen_ids.add(track['id'])
        
        # Add mood tracks with source metadata
        for track in mood_tracks:
            if track['id'] not in seen_ids:
                track['source'] = 'mood_based'
                all_tracks.append(track)
                seen_ids.add(track['id'])
        
        logger.info(f"Combined tracks: {len(all_tracks)} unique tracks total")
        
        if len(all_tracks) <= target_length:
            logger.info(f"Not enough tracks ({len(all_tracks)} <= {target_length}), returning all available")
            return all_tracks
        
        # Fetch audio features for all tracks for improved scoring
        if self.service == "spotify" and self.spotify_client:
            logger.info("Fetching audio features for intelligent scoring...")
            all_tracks = self._enrich_tracks_with_audio_features(all_tracks)
        
        # Use improved scoring algorithm to rank all tracks
        logger.info("Applying improved mood scoring algorithm...")
        scored_tracks = []
        scorer = ImprovedTrackScorer()
        
        for track in all_tracks:
            # Calculate mood compatibility score
            mood_score = scorer.calculate_mood_score(mood_params, track)
            
            # Apply source bonus: user preferences get a boost
            if track['source'] == 'user_preference':
                # User tracks get 20% bonus to their mood score
                final_score = mood_score * 1.2
            else:
                final_score = mood_score
            
            track['mood_score'] = mood_score
            track['final_score'] = final_score
            scored_tracks.append((track, final_score))
        
        logger.info(f"Scored {len(scored_tracks)} tracks")
        
        # Use smart filter for final selection with diversity
        smart_filter = SmartTrackFilter(scorer)
        
        # Filter and rank tracks
        filtered_tracks = smart_filter.filter_and_rank_tracks(
            tracks=[track for track, _ in scored_tracks],
            mood_params=mood_params,
            target_count=target_length * 2,  # Get more candidates
            min_score_threshold=0.12  # Lower threshold for more options
        )
        
        logger.info(f"Smart filter returned {len(filtered_tracks)} candidate tracks")
        
        # Apply diversity and select final tracks
        if len(filtered_tracks) > target_length:
            diversified_tracks = smart_filter.diversify_tracks(
                filtered_tracks, 
                diversity_factor=0.3
            )
            final_tracks = [track for track, _ in diversified_tracks[:target_length]]
        else:
            final_tracks = [track for track, _ in filtered_tracks]
        
        # Log selection analytics
        user_count = len([t for t in final_tracks if t['source'] == 'user_preference'])
        mood_count = len([t for t in final_tracks if t['source'] == 'mood_based'])
        
        if final_tracks:
            avg_mood_score = sum(t.get('mood_score', 0) for t in final_tracks) / len(final_tracks)
            avg_final_score = sum(t.get('final_score', 0) for t in final_tracks) / len(final_tracks)
            top_score = final_tracks[0].get('final_score', 0) if final_tracks else 0
            
            logger.info(f"Final selection analytics:")
            logger.info(f"  • {len(final_tracks)} tracks selected ({user_count} user, {mood_count} discovery)")
            logger.info(f"  • Average mood score: {avg_mood_score:.3f}")
            logger.info(f"  • Average final score: {avg_final_score:.3f}")
            logger.info(f"  • Top track score: {top_score:.3f}")
        
        # Log top tracks for debugging
        logger.info(f"Top tracks in final selection:")
        for i, track in enumerate(final_tracks[:5]):
            mood_score = track.get('mood_score', 0)
            final_score = track.get('final_score', 0)
            source = track.get('source', 'unknown')
            artists = ', '.join([a.get('name', 'Unknown') for a in track.get('artists', [])])
            logger.info(f"  {i+1}. '{track.get('name', 'Unknown')}' by {artists}")
            logger.info(f"     Score: {final_score:.3f} (mood: {mood_score:.3f}, source: {source})")
        
        return final_tracks
    
    def _enrich_tracks_with_audio_features(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich track data with audio features needed for scoring.
        
        Args:
            tracks: List of track dictionaries
            
        Returns:
            List of tracks enriched with audio features
        """
        if not tracks or self.service != "spotify" or not self.spotify_client:
            return tracks
        
        # Use the new SpotifyTrackEnricher class
        enricher = SpotifyTrackEnricher(self.spotify_client)
        return enricher.enrich_tracks_with_audio_features(tracks)
    
    def _generate_playlist_name(self, mood_params: MoodParameters, mood_description: str) -> str:
        """Generate a creative playlist name based on mood."""
        # Use mood tags if available
        if mood_params.mood_tags:
            primary_mood = mood_params.mood_tags[0].title()
            name = f"{primary_mood} Vibes"
        # Use genre if available
        elif mood_params.genre_hints:
            primary_genre = mood_params.genre_hints[0].title()
            name = f"{primary_genre} Mood"
        # Use time/activity context
        elif mood_params.time_of_day:
            name = f"{mood_params.time_of_day.title()} Mix"
        elif mood_params.activity:
            name = f"{mood_params.activity.title()} Playlist"
        # Fallback based on valence/energy
        elif mood_params.valence > 0.7:
            name = "Happy Vibes"
        elif mood_params.valence < 0.3:
            name = "Melancholic Moments"
        elif mood_params.energy > 0.7:
            name = "High Energy Mix"
        elif mood_params.energy < 0.3:
            name = "Chill Playlist"
        else:
            name = "Mood Mix"
        
        # Sanitize name for Spotify API (max 100 chars, no special chars)
        name = name.replace('"', "'").replace('\n', ' ').replace('\r', '').replace('\t', ' ')
        
        # Remove any potentially problematic characters
        name = re.sub(r'[^\w\s\-\'\(\)]+', '', name)
        name = ' '.join(name.split())  # Remove extra whitespace
        
        # Ensure minimum and maximum length
        if len(name) < 1:
            name = "Mood Playlist"
        elif len(name) > 100:
            name = name[:97] + "..."
        
        return name
    
    def _generate_playlist_description(self, mood_params: MoodParameters, mood_description: str) -> str:
        """Generate playlist description."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Include original mood description (truncated if too long)
        description_text = mood_description
        if len(description_text) > 100:
            description_text = description_text[:97] + "..."
        
        # No line breaks - they break Spotify API JSON
        description = f'Generated by Moodtape on {timestamp}. '
        description += f"Mood: '{description_text}'. "
        
        # Add mood characteristics
        if mood_params.mood_tags:
            description += f"Tags: {', '.join(mood_params.mood_tags[:3])}. "
        
        if mood_params.genre_hints:
            description += f"Genres: {', '.join(mood_params.genre_hints[:3])}. "
        
        description += f"Created with love by Moodtape"
        
        # Ensure no line breaks and max length for Spotify API
        description = description.replace('\n', ' ').replace('\r', ' ')
        if len(description) > 300:
            description = description[:297] + "..."
        
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
            
            logger.info(f"Preparing to create Spotify playlist with {len(track_uris)} track URIs")
            
            if not track_uris:
                logger.error(f"No valid track URIs found for user {self.user_id}")
                logger.error(f"Track sample: {tracks[:3] if tracks else 'No tracks'}")
                return None
            
            logger.info(f"Calling Spotify API to create playlist...")
            try:
                result = self.spotify_client.create_playlist(
                    name=name,
                    description=description,
                    track_uris=track_uris,
                    public=False  # Keep playlists private by default
                )
                
                if result:
                    logger.info(f"Successfully created Spotify playlist: {result.get('url', 'No URL')}")
                else:
                    logger.error(f"Spotify API returned None/False when creating playlist")
                
                return result
                
            except Exception as e:
                logger.error(f"Exception when creating Spotify playlist: {e}")
                return None
                
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
        
        logger.error(f"Unknown service '{self.service}' or client not available")
        return None
    
    async def _build_playlist_with_improved_scoring(
        self,
        mood_params: MoodParameters,
        mood_description: str,
        playlist_length: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Alternative method using the new MoodPlaylistBuilder for improved scoring.
        
        Args:
            mood_params: Parsed mood parameters from GPT
            mood_description: Original user description
            playlist_length: Desired number of tracks
        
        Returns:
            Playlist info dict or None if failed
        """
        if not self.is_service_available() or self.service != "spotify":
            logger.error(f"Improved scoring only available for Spotify service")
            return None
        
        try:
            # Generate unique query ID
            query_id = str(uuid.uuid4())
            
            logger.info(f"Building playlist with improved scoring for user {self.user_id}, query {query_id}")
            
            # Get candidate tracks from both sources
            user_tracks = self._get_user_preference_tracks()
            mood_tracks = self._get_mood_based_tracks(mood_params, playlist_length)
            
            # Combine all candidate tracks
            all_candidates = []
            
            # Add user tracks with source metadata
            for track in user_tracks:
                track['source'] = 'user_preference'
                all_candidates.append(track)
            
            # Add mood tracks with source metadata
            for track in mood_tracks:
                track['source'] = 'mood_based'
                all_candidates.append(track)
            
            if not all_candidates:
                logger.error(f"No candidate tracks found for user {self.user_id}")
                return None
            
            logger.info(f"Using improved scoring algorithm with {len(all_candidates)} candidates")
            
            # Use the new MoodPlaylistBuilder for intelligent playlist creation
            mood_builder = MoodPlaylistBuilder(
                spotify_client=self.spotify_client,
                scorer=ImprovedTrackScorer()
            )
            
            final_tracks = mood_builder.build_intelligent_playlist(
                candidate_tracks=all_candidates,
                mood_params=mood_params,
                target_length=playlist_length,
                user_track_bonus=1.2,  # 20% bonus for user preference tracks
                min_score_threshold=0.15
            )
            
            if not final_tracks:
                logger.error(f"No tracks selected by improved scoring algorithm")
                return None
            
            # Generate playlist metadata
            playlist_name = self._generate_playlist_name(mood_params, mood_description)
            playlist_description = self._generate_playlist_description(mood_params, mood_description)
            
            # Create the actual playlist
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
                
                playlist_info['query_id'] = query_id
                playlist_info['scoring_method'] = 'improved_algorithm'
                
                logger.info(f"Successfully created improved playlist for user {self.user_id}: {playlist_info['url']}")
                return playlist_info
            
        except Exception as e:
            logger.error(f"Error in improved scoring playlist builder: {e}")
            
        return None


async def create_user_playlist(
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
    
    # Now properly async - no event loop conflicts
    return await builder.build_mood_playlist(mood_params, mood_description, playlist_length) 