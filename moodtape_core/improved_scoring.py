"""
Improved track scoring algorithm for precise mood matching in Moodtape bot.
Implements Gaussian similarity functions and intelligent genre/popularity bonuses.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import statistics

from moodtape_core.gpt_parser import MoodParameters
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrackFeatures:
    """Normalized track features for scoring."""
    valence: float
    energy: float
    danceability: float
    acousticness: float
    instrumentalness: float
    speechiness: float
    tempo: float  # Normalized to 0-1 scale
    loudness: float  # Normalized to 0-1 scale
    popularity: int  # 0-100
    genres: List[str]
    

@dataclass
class ScoringWeights:
    """Weights for different audio features in mood matching."""
    valence: float = 0.25       # Most important - emotional positivity
    energy: float = 0.20        # Energy level matching
    danceability: float = 0.15  # Rhythmic compatibility
    tempo: float = 0.10         # BPM matching
    acousticness: float = 0.10  # Acoustic vs electronic preference
    loudness: float = 0.08      # Volume preference
    instrumentalness: float = 0.07  # Vocal vs instrumental
    speechiness: float = 0.05   # Least important - spoken vs sung
    
    def __post_init__(self):
        """Ensure weights sum to 1.0."""
        total = sum([
            self.valence, self.energy, self.danceability, self.tempo,
            self.acousticness, self.loudness, self.instrumentalness, self.speechiness
        ])
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Scoring weights sum to {total:.3f}, not 1.0. Normalizing...")
            self.valence /= total
            self.energy /= total
            self.danceability /= total
            self.tempo /= total
            self.acousticness /= total
            self.loudness /= total
            self.instrumentalness /= total
            self.speechiness /= total


class ImprovedTrackScorer:
    """Advanced track scoring algorithm using Gaussian similarity functions."""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        Initialize scorer with custom weights.
        
        Args:
            weights: Custom scoring weights, uses default if None
        """
        self.weights = weights or ScoringWeights()
        self.logger = get_logger(__name__)
    
    def gaussian_similarity(self, target: float, actual: float, sigma: float = 0.15) -> float:
        """
        Calculate Gaussian similarity between target and actual values.
        
        Args:
            target: Target value (0.0-1.0)
            actual: Actual track value (0.0-1.0)
            sigma: Standard deviation for Gaussian curve (smaller = stricter)
        
        Returns:
            Similarity score (0.0-1.0), where 1.0 = perfect match
        """
        if target is None or actual is None:
            return 0.5  # Neutral score for missing data
        
        # Gaussian function: e^(-(x-μ)²/(2σ²))
        difference = abs(target - actual)
        similarity = math.exp(-(difference ** 2) / (2 * sigma ** 2))
        
        return similarity
    
    def tempo_similarity(self, target_tempo: int, actual_tempo: float, sigma: float = 0.2) -> float:
        """
        Calculate tempo similarity with special handling for BPM.
        
        Args:
            target_tempo: Target BPM (50-200)
            actual_tempo: Actual track BPM
            sigma: Standard deviation for tempo matching
        
        Returns:
            Similarity score (0.0-1.0)
        """
        if target_tempo is None or actual_tempo is None:
            return 0.5
        
        # Normalize both to 0-1 scale (50 BPM = 0, 200 BPM = 1)
        target_norm = (target_tempo - 50) / 150
        actual_norm = (actual_tempo - 50) / 150
        
        # Clamp to valid range
        target_norm = max(0, min(1, target_norm))
        actual_norm = max(0, min(1, actual_norm))
        
        return self.gaussian_similarity(target_norm, actual_norm, sigma)
    
    def loudness_similarity(self, target_loudness: float, actual_loudness: float, sigma: float = 0.2) -> float:
        """
        Calculate loudness similarity with dB to 0-1 normalization.
        
        Args:
            target_loudness: Target loudness in dB (-30 to 0)
            actual_loudness: Actual track loudness in dB
            sigma: Standard deviation for loudness matching
        
        Returns:
            Similarity score (0.0-1.0)
        """
        if target_loudness is None or actual_loudness is None:
            return 0.5
        
        # Normalize both to 0-1 scale (-30 dB = 0, 0 dB = 1)
        target_norm = (target_loudness + 30) / 30
        actual_norm = (actual_loudness + 30) / 30
        
        # Clamp to valid range
        target_norm = max(0, min(1, target_norm))
        actual_norm = max(0, min(1, actual_norm))
        
        return self.gaussian_similarity(target_norm, actual_norm, sigma)
    
    def calculate_audio_features_score(self, mood_params: MoodParameters, track_features: TrackFeatures) -> float:
        """
        Calculate core audio features similarity score.
        
        Args:
            mood_params: Target mood parameters
            track_features: Track's audio features
        
        Returns:
            Weighted audio features score (0.0-1.0)
        """
        # Calculate individual feature similarities using correct MoodParameters structure
        valence_sim = self.gaussian_similarity(mood_params.valence, track_features.valence, sigma=0.12)
        energy_sim = self.gaussian_similarity(mood_params.energy, track_features.energy, sigma=0.15)
        danceability_sim = self.gaussian_similarity(mood_params.danceability, track_features.danceability, sigma=0.18)
        acousticness_sim = self.gaussian_similarity(mood_params.acousticness, track_features.acousticness, sigma=0.20)
        instrumentalness_sim = self.gaussian_similarity(mood_params.instrumentalness, track_features.instrumentalness, sigma=0.25)
        speechiness_sim = self.gaussian_similarity(mood_params.speechiness, track_features.speechiness, sigma=0.30)
        
        # Special handling for tempo and loudness
        tempo_sim = self.tempo_similarity(mood_params.tempo, track_features.tempo)
        loudness_sim = self.loudness_similarity(mood_params.loudness, track_features.loudness)
        
        # Calculate weighted score
        weighted_score = (
            valence_sim * self.weights.valence +
            energy_sim * self.weights.energy +
            danceability_sim * self.weights.danceability +
            tempo_sim * self.weights.tempo +
            acousticness_sim * self.weights.acousticness +
            loudness_sim * self.weights.loudness +
            instrumentalness_sim * self.weights.instrumentalness +
            speechiness_sim * self.weights.speechiness
        )
        
        return weighted_score
    
    def calculate_genre_bonus(self, mood_params: MoodParameters, track_genres: List[str]) -> float:
        """
        Calculate bonus/penalty based on genre matching.
        
        Args:
            mood_params: Target mood parameters with genre preferences
            track_genres: Track's genres
        
        Returns:
            Genre bonus/penalty (-0.3 to +0.3)
        """
        if not track_genres:
            return 0.0
        
        bonus = 0.0
        track_genres_lower = [g.lower() for g in track_genres]
        
        # Primary genres bonus (highest priority) - use correct MoodParameters structure
        primary_genres = mood_params.primary_genres if mood_params.primary_genres else []
        for genre in primary_genres:
            if genre.lower() in track_genres_lower:
                bonus += 0.15  # Strong bonus for primary genre match
        
        # Secondary genres bonus
        secondary_genres = mood_params.secondary_genres if mood_params.secondary_genres else []
        for genre in secondary_genres:
            if genre.lower() in track_genres_lower:
                bonus += 0.08  # Moderate bonus for secondary genre match
        
        # Legacy genre_hints support
        if hasattr(mood_params, 'genre_hints') and mood_params.genre_hints:
            for genre in mood_params.genre_hints[:3]:  # Top 3 genre hints
                if genre.lower() in track_genres_lower:
                    bonus += 0.10
        
        # Exclude genres penalty
        exclude_genres = mood_params.exclude_genres if mood_params.exclude_genres else []
        for genre in exclude_genres:
            if genre.lower() in track_genres_lower:
                bonus -= 0.25  # Strong penalty for excluded genres
        
        # Cap bonus/penalty
        return max(-0.3, min(0.3, bonus))
    
    def calculate_popularity_bonus(self, mood_params: MoodParameters, track_popularity: int) -> float:
        """
        Calculate bonus based on popularity preferences.
        
        Args:
            mood_params: Target mood parameters with popularity range
            track_popularity: Track's popularity (0-100)
        
        Returns:
            Popularity bonus/penalty (-0.1 to +0.1)
        """
        if track_popularity is None:
            return 0.0
        
        # Use correct MoodParameters structure
        popularity_range = mood_params.popularity_range if mood_params.popularity_range else [20, 80]
        min_pop, max_pop = popularity_range[0], popularity_range[1]
        
        if min_pop <= track_popularity <= max_pop:
            # Within preferred range - give bonus
            center = (min_pop + max_pop) / 2
            distance_from_center = abs(track_popularity - center) / ((max_pop - min_pop) / 2)
            bonus = 0.1 * (1 - distance_from_center)  # Closer to center = higher bonus
            return bonus
        else:
            # Outside preferred range - give penalty
            if track_popularity < min_pop:
                penalty = -0.05 * (min_pop - track_popularity) / min_pop
            else:  # track_popularity > max_pop
                penalty = -0.05 * (track_popularity - max_pop) / (100 - max_pop)
            return max(-0.1, penalty)
    
    def calculate_mood_score(self, mood_params: MoodParameters, track_data: Dict[str, Any]) -> float:
        """
        Calculate comprehensive mood matching score for a track.
        
        Args:
            mood_params: Target mood parameters
            track_data: Track data from Spotify API
        
        Returns:
            Total mood score (0.0-1.0+), higher = better match
        """
        try:
            # Extract audio features
            audio_features = track_data.get('audio_features', {})
            if not audio_features:
                self.logger.warning(f"No audio features for track {track_data.get('id', 'unknown')}")
                return 0.1  # Very low score for tracks without features
            
            # Create TrackFeatures object
            track_features = TrackFeatures(
                valence=audio_features.get('valence', 0.5),
                energy=audio_features.get('energy', 0.5),
                danceability=audio_features.get('danceability', 0.5),
                acousticness=audio_features.get('acousticness', 0.5),
                instrumentalness=audio_features.get('instrumentalness', 0.5),
                speechiness=audio_features.get('speechiness', 0.05),
                tempo=audio_features.get('tempo', 120),
                loudness=audio_features.get('loudness', -5.0),
                popularity=track_data.get('popularity', 50),
                genres=track_data.get('genres', [])
            )
            
            # Calculate base audio features score (0.0-1.0)
            base_score = self.calculate_audio_features_score(mood_params, track_features)
            
            # Calculate bonuses/penalties
            genre_bonus = self.calculate_genre_bonus(mood_params, track_features.genres)
            popularity_bonus = self.calculate_popularity_bonus(mood_params, track_features.popularity)
            
            # Combine scores
            total_score = base_score + genre_bonus + popularity_bonus
            
            # Ensure minimum score for playable content
            final_score = max(0.0, total_score)
            
            self.logger.debug(f"Track {track_data.get('name', 'Unknown')}: "
                            f"base={base_score:.3f}, genre={genre_bonus:+.3f}, "
                            f"pop={popularity_bonus:+.3f}, final={final_score:.3f}")
            
            return final_score
            
        except Exception as e:
            self.logger.error(f"Error calculating mood score for track {track_data.get('id', 'unknown')}: {e}")
            return 0.1  # Low score for problematic tracks


class SmartTrackFilter:
    """Intelligent track filtering and ranking system."""
    
    def __init__(self, scorer: Optional[ImprovedTrackScorer] = None):
        """
        Initialize filter with custom scorer.
        
        Args:
            scorer: Custom track scorer, creates default if None
        """
        self.scorer = scorer or ImprovedTrackScorer()
        self.logger = get_logger(__name__)
    
    def filter_and_rank_tracks(
        self,
        tracks: List[Dict[str, Any]],
        mood_params: MoodParameters,
        target_count: int = 20,
        min_score_threshold: float = 0.15
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Filter and rank tracks by mood compatibility.
        
        Args:
            tracks: List of track data from Spotify API
            mood_params: Target mood parameters
            target_count: Desired number of tracks to return
            min_score_threshold: Minimum score to include track
        
        Returns:
            List of (track_data, score) tuples, sorted by score descending
        """
        if not tracks:
            self.logger.warning("No tracks provided for filtering")
            return []
        
        self.logger.info(f"Filtering {len(tracks)} tracks with mood parameters")
        
        # Score all tracks
        scored_tracks = []
        for track in tracks:
            score = self.scorer.calculate_mood_score(mood_params, track)
            
            # Apply minimum score threshold
            if score >= min_score_threshold:
                scored_tracks.append((track, score))
        
        # Sort by score descending
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        
        # Log filtering results
        filtered_count = len(scored_tracks)
        self.logger.info(f"Filtered to {filtered_count} tracks above threshold {min_score_threshold}")
        
        if scored_tracks:
            top_score = scored_tracks[0][1]
            avg_score = statistics.mean([score for _, score in scored_tracks])
            self.logger.info(f"Score range: {top_score:.3f} (top) to {avg_score:.3f} (avg)")
        
        # Return top tracks up to target count
        result = scored_tracks[:target_count]
        
        self.logger.info(f"Returning top {len(result)} tracks for playlist")
        return result
    
    def diversify_tracks(
        self,
        scored_tracks: List[Tuple[Dict[str, Any], float]],
        diversity_factor: float = 0.3
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Apply diversity to avoid too similar tracks in sequence.
        
        Args:
            scored_tracks: List of (track, score) tuples
            diversity_factor: How much to prioritize diversity (0.0-1.0)
        
        Returns:
            Reordered list with diversity applied
        """
        if len(scored_tracks) <= 2 or diversity_factor <= 0:
            return scored_tracks
        
        # Implement simple diversity by artist and genre spreading
        result = []
        remaining = scored_tracks.copy()
        used_artists = set()
        used_genres = set()
        
        while remaining:
            best_idx = 0
            best_score = -1
            
            for i, (track, score) in enumerate(remaining):
                # Base score
                adjusted_score = score
                
                # Diversity bonuses
                artist_name = track.get('artists', [{}])[0].get('name', '')
                track_genres = track.get('genres', [])
                
                # Bonus for new artist
                if artist_name and artist_name not in used_artists:
                    adjusted_score += diversity_factor * 0.1
                
                # Bonus for new genres
                new_genres = [g for g in track_genres if g not in used_genres]
                if new_genres:
                    adjusted_score += diversity_factor * 0.05 * len(new_genres)
                
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_idx = i
            
            # Add best track to result
            track, original_score = remaining.pop(best_idx)
            result.append((track, original_score))
            
            # Update used sets
            artist_name = track.get('artists', [{}])[0].get('name', '')
            if artist_name:
                used_artists.add(artist_name)
            used_genres.update(track.get('genres', []))
        
        self.logger.info(f"Applied diversity reordering to {len(result)} tracks")
        return result


class SpotifyTrackEnricher:
    """Enriches track data with audio features from Spotify API."""
    
    def __init__(self, spotify_client=None):
        """
        Initialize track enricher.
        
        Args:
            spotify_client: SpotifyClient instance for API calls
        """
        self.spotify_client = spotify_client
        self.logger = get_logger(__name__)
    
    def enrich_tracks_with_audio_features(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich track data with audio features from Spotify API.
        
        Args:
            tracks: List of track dictionaries
            
        Returns:
            List of tracks enriched with audio features
        """
        if not tracks or not self.spotify_client:
            self.logger.warning("No tracks provided or Spotify client not available for enrichment")
            return tracks
        
        try:
            # Get track IDs
            track_ids = [track['id'] for track in tracks if track.get('id')]
            
            if not track_ids:
                self.logger.warning("No track IDs found for audio features enrichment")
                return tracks
            
            self.logger.info(f"Enriching {len(track_ids)} tracks with audio features...")
            
            # Get audio features in batches (Spotify allows max 100 per request)
            batch_size = 100
            all_audio_features = {}
            
            for i in range(0, len(track_ids), batch_size):
                batch_ids = track_ids[i:i + batch_size]
                try:
                    features_batch = self.spotify_client.get_audio_features(batch_ids)
                    
                    if features_batch:
                        for track_id, features in zip(batch_ids, features_batch):
                            if features:  # Some tracks might not have audio features
                                all_audio_features[track_id] = features
                except Exception as e:
                    self.logger.error(f"Error fetching audio features batch {i//batch_size + 1}: {e}")
            
            self.logger.info(f"Retrieved audio features for {len(all_audio_features)} tracks")
            
            # Enrich tracks with audio features
            enriched_tracks = []
            for track in tracks:
                track_id = track.get('id')
                enriched_track = track.copy()  # Create a copy to avoid modifying original
                
                if track_id and track_id in all_audio_features:
                    enriched_track['audio_features'] = all_audio_features[track_id]
                    
                    # Also extract artist genres from track data if available
                    if 'artists' in track and track['artists']:
                        # Try to get genres from artist data (if already available)
                        genres = []
                        for artist in track['artists']:
                            if isinstance(artist, dict) and 'genres' in artist:
                                genres.extend(artist['genres'])
                        if genres:
                            enriched_track['genres'] = list(set(genres))  # Remove duplicates
                
                enriched_tracks.append(enriched_track)
            
            return enriched_tracks
            
        except Exception as e:
            self.logger.error(f"Error enriching tracks with audio features: {e}")
            return tracks  # Return original tracks if enrichment fails
    
    def enrich_single_track(self, track: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single track with audio features.
        
        Args:
            track: Track dictionary
            
        Returns:
            Track enriched with audio features
        """
        return self.enrich_tracks_with_audio_features([track])[0]


class MoodPlaylistBuilder:
    """Integration class that combines mood scoring with playlist building."""
    
    def __init__(self, spotify_client=None, scorer: Optional[ImprovedTrackScorer] = None):
        """
        Initialize mood playlist builder.
        
        Args:
            spotify_client: SpotifyClient instance
            scorer: Custom track scorer, uses default if None
        """
        self.spotify_client = spotify_client
        self.scorer = scorer or ImprovedTrackScorer()
        self.smart_filter = SmartTrackFilter(self.scorer)
        self.enricher = SpotifyTrackEnricher(spotify_client)
        self.logger = get_logger(__name__)
    
    def build_intelligent_playlist(
        self,
        candidate_tracks: List[Dict[str, Any]],
        mood_params: MoodParameters,
        target_length: int = 20,
        user_track_bonus: float = 1.2,
        min_score_threshold: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Build an intelligent playlist using improved scoring algorithm.
        
        Args:
            candidate_tracks: List of candidate tracks
            mood_params: Target mood parameters
            target_length: Desired playlist length
            user_track_bonus: Bonus multiplier for user preference tracks
            min_score_threshold: Minimum score threshold for inclusion
            
        Returns:
            List of selected tracks with scores
        """
        if not candidate_tracks:
            self.logger.warning("No candidate tracks provided")
            return []
        
        self.logger.info(f"Building intelligent playlist from {len(candidate_tracks)} candidates")
        
        # Step 1: Enrich tracks with audio features
        enriched_tracks = self.enricher.enrich_tracks_with_audio_features(candidate_tracks)
        
        # Step 2: Score all tracks
        scored_tracks = []
        for track in enriched_tracks:
            # Calculate mood compatibility score
            mood_score = self.scorer.calculate_mood_score(mood_params, track)
            
            # Apply source bonus if it's a user preference track
            if track.get('source') == 'user_preference':
                final_score = mood_score * user_track_bonus
            else:
                final_score = mood_score
            
            track['mood_score'] = mood_score
            track['final_score'] = final_score
            scored_tracks.append((track, final_score))
        
        # Step 3: Filter and rank using smart filter
        filtered_tracks = self.smart_filter.filter_and_rank_tracks(
            tracks=[track for track, _ in scored_tracks],
            mood_params=mood_params,
            target_count=target_length * 2,  # Get more candidates for diversity
            min_score_threshold=min_score_threshold
        )
        
        # Step 4: Apply diversity if we have enough tracks
        if len(filtered_tracks) > target_length:
            diversified_tracks = self.smart_filter.diversify_tracks(
                filtered_tracks,
                diversity_factor=0.3
            )
            final_tracks = [track for track, _ in diversified_tracks[:target_length]]
        else:
            final_tracks = [track for track, _ in filtered_tracks]
        
        # Log analytics
        if final_tracks:
            user_count = len([t for t in final_tracks if t.get('source') == 'user_preference'])
            discovery_count = len(final_tracks) - user_count
            avg_mood_score = sum(t.get('mood_score', 0) for t in final_tracks) / len(final_tracks)
            avg_final_score = sum(t.get('final_score', 0) for t in final_tracks) / len(final_tracks)
            
            self.logger.info(f"Intelligent playlist built:")
            self.logger.info(f"  • {len(final_tracks)} tracks selected ({user_count} user, {discovery_count} discovery)")
            self.logger.info(f"  • Average mood score: {avg_mood_score:.3f}")
            self.logger.info(f"  • Average final score: {avg_final_score:.3f}")
        
        return final_tracks


# Create default instances for easy importing
default_scorer = ImprovedTrackScorer()
default_filter = SmartTrackFilter(default_scorer)
default_enricher = SpotifyTrackEnricher() 