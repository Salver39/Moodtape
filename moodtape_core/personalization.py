"""Personalization engine for Moodtape bot based on user feedback."""

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

from moodtape_core.gpt_parser import MoodParameters
from utils.database import db_manager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserPreferences:
    """User's music preferences learned from feedback."""
    user_id: int
    valence_bias: float = 0.0  # Adjustment to valence (-0.5 to +0.5)
    energy_bias: float = 0.0   # Adjustment to energy (-0.5 to +0.5)
    danceability_bias: float = 0.0  # Adjustment to danceability (-0.5 to +0.5)
    acousticness_bias: float = 0.0  # Adjustment to acousticness (-0.5 to +0.5)
    tempo_bias: int = 0        # Adjustment to tempo (-50 to +50 BPM)
    
    # Genre preferences (positive = prefer, negative = avoid)
    genre_preferences: Dict[str, float] = None
    
    # Mood tag preferences
    mood_tag_preferences: Dict[str, float] = None
    
    # Confidence scores (how sure we are about these preferences)
    confidence_score: float = 0.0  # 0.0 to 1.0
    
    # Metadata
    total_feedback_count: int = 0
    positive_feedback_count: int = 0
    last_updated: int = 0
    
    def __post_init__(self):
        if self.genre_preferences is None:
            self.genre_preferences = {}
        if self.mood_tag_preferences is None:
            self.mood_tag_preferences = {}


class UserPreferenceAnalyzer:
    """Analyzes user feedback to determine preferences."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def analyze_user_feedback(self, user_id: int, limit: int = 10) -> UserPreferences:
        """
        Analyze user's recent feedback to determine preferences.
        
        Args:
            user_id: Telegram user ID
            limit: Number of recent feedback entries to analyze
        
        Returns:
            UserPreferences object with learned preferences
        """
        # Get user's feedback history
        feedback_history = db_manager.get_user_feedback_history(user_id, limit)
        
        if not feedback_history:
            logger.info(f"No feedback history found for user {user_id}")
            return UserPreferences(user_id=user_id)
        
        logger.info(f"Analyzing {len(feedback_history)} feedback entries for user {user_id}")
        
        # Separate positive and negative feedback
        positive_feedback = [f for f in feedback_history if f['rating'] > 0]
        negative_feedback = [f for f in feedback_history if f['rating'] < 0]
        
        preferences = UserPreferences(user_id=user_id)
        preferences.total_feedback_count = len(feedback_history)
        preferences.positive_feedback_count = len(positive_feedback)
        
        # If not enough feedback, return default preferences
        if len(feedback_history) < 3:
            preferences.confidence_score = 0.1
            return preferences
        
        # Analyze parameter preferences
        self._analyze_parameter_preferences(preferences, positive_feedback, negative_feedback)
        
        # Analyze genre preferences
        self._analyze_genre_preferences(preferences, positive_feedback, negative_feedback)
        
        # Analyze mood tag preferences
        self._analyze_mood_tag_preferences(preferences, positive_feedback, negative_feedback)
        
        # Calculate confidence score
        preferences.confidence_score = self._calculate_confidence_score(preferences, len(feedback_history))
        
        logger.info(f"Generated preferences for user {user_id} with confidence {preferences.confidence_score:.2f}")
        
        return preferences
    
    def _analyze_parameter_preferences(
        self, 
        preferences: UserPreferences, 
        positive_feedback: List[Dict], 
        negative_feedback: List[Dict]
    ) -> None:
        """Analyze musical parameter preferences from feedback."""
        
        # Extract mood parameters from feedback
        positive_params = []
        negative_params = []
        
        for feedback in positive_feedback:
            if feedback.get('mood_params'):
                positive_params.append(feedback['mood_params'])
        
        for feedback in negative_feedback:
            if feedback.get('mood_params'):
                negative_params.append(feedback['mood_params'])
        
        if not positive_params and not negative_params:
            return
        
        # Calculate parameter biases based on differences between positive and negative
        
        # Valence bias
        if positive_params and negative_params:
            positive_valence = [p.get('valence', 0.5) for p in positive_params]
            negative_valence = [p.get('valence', 0.5) for p in negative_params]
            
            avg_positive_valence = statistics.mean(positive_valence)
            avg_negative_valence = statistics.mean(negative_valence)
            
            # If user likes higher valence, bias positive; if likes lower valence, bias negative
            valence_diff = avg_positive_valence - avg_negative_valence
            preferences.valence_bias = max(-0.5, min(0.5, valence_diff * 0.5))
        
        # Energy bias
        if positive_params and negative_params:
            positive_energy = [p.get('energy', 0.5) for p in positive_params]
            negative_energy = [p.get('energy', 0.5) for p in negative_params]
            
            avg_positive_energy = statistics.mean(positive_energy)
            avg_negative_energy = statistics.mean(negative_energy)
            
            energy_diff = avg_positive_energy - avg_negative_energy
            preferences.energy_bias = max(-0.5, min(0.5, energy_diff * 0.5))
        
        # Danceability bias
        if positive_params and negative_params:
            positive_dance = [p.get('danceability', 0.5) for p in positive_params]
            negative_dance = [p.get('danceability', 0.5) for p in negative_params]
            
            avg_positive_dance = statistics.mean(positive_dance)
            avg_negative_dance = statistics.mean(negative_dance)
            
            dance_diff = avg_positive_dance - avg_negative_dance
            preferences.danceability_bias = max(-0.5, min(0.5, dance_diff * 0.5))
        
        # Acousticness bias
        if positive_params and negative_params:
            positive_acoustic = [p.get('acousticness', 0.5) for p in positive_params]
            negative_acoustic = [p.get('acousticness', 0.5) for p in negative_params]
            
            avg_positive_acoustic = statistics.mean(positive_acoustic)
            avg_negative_acoustic = statistics.mean(negative_acoustic)
            
            acoustic_diff = avg_positive_acoustic - avg_negative_acoustic
            preferences.acousticness_bias = max(-0.5, min(0.5, acoustic_diff * 0.5))
        
        # Tempo bias
        if positive_params and negative_params:
            positive_tempo = [p.get('tempo', 120) for p in positive_params]
            negative_tempo = [p.get('tempo', 120) for p in negative_params]
            
            avg_positive_tempo = statistics.mean(positive_tempo)
            avg_negative_tempo = statistics.mean(negative_tempo)
            
            tempo_diff = avg_positive_tempo - avg_negative_tempo
            preferences.tempo_bias = max(-50, min(50, int(tempo_diff * 0.5)))
        
        logger.debug(f"Parameter biases: valence={preferences.valence_bias:.2f}, "
                    f"energy={preferences.energy_bias:.2f}, dance={preferences.danceability_bias:.2f}")
    
    def _analyze_genre_preferences(
        self, 
        preferences: UserPreferences, 
        positive_feedback: List[Dict], 
        negative_feedback: List[Dict]
    ) -> None:
        """Analyze genre preferences from feedback."""
        
        genre_scores = defaultdict(float)
        
        # Positive feedback genres get +1
        for feedback in positive_feedback:
            mood_params = feedback.get('mood_params', {})
            genre_hints = mood_params.get('genre_hints', [])
            for genre in genre_hints:
                genre_scores[genre.lower()] += 1.0
        
        # Negative feedback genres get -1
        for feedback in negative_feedback:
            mood_params = feedback.get('mood_params', {})
            genre_hints = mood_params.get('genre_hints', [])
            for genre in genre_hints:
                genre_scores[genre.lower()] -= 1.0
        
        # Normalize scores based on total feedback count
        total_feedback = len(positive_feedback) + len(negative_feedback)
        if total_feedback > 0:
            for genre in genre_scores:
                genre_scores[genre] = genre_scores[genre] / total_feedback
        
        preferences.genre_preferences = dict(genre_scores)
        
        logger.debug(f"Genre preferences: {dict(list(genre_scores.items())[:5])}")  # Log top 5
    
    def _analyze_mood_tag_preferences(
        self, 
        preferences: UserPreferences, 
        positive_feedback: List[Dict], 
        negative_feedback: List[Dict]
    ) -> None:
        """Analyze mood tag preferences from feedback."""
        
        tag_scores = defaultdict(float)
        
        # Positive feedback tags get +1
        for feedback in positive_feedback:
            mood_params = feedback.get('mood_params', {})
            mood_tags = mood_params.get('mood_tags', [])
            for tag in mood_tags:
                tag_scores[tag.lower()] += 1.0
        
        # Negative feedback tags get -1
        for feedback in negative_feedback:
            mood_params = feedback.get('mood_params', {})
            mood_tags = mood_params.get('mood_tags', [])
            for tag in mood_tags:
                tag_scores[tag.lower()] -= 1.0
        
        # Normalize scores
        total_feedback = len(positive_feedback) + len(negative_feedback)
        if total_feedback > 0:
            for tag in tag_scores:
                tag_scores[tag] = tag_scores[tag] / total_feedback
        
        preferences.mood_tag_preferences = dict(tag_scores)
        
        logger.debug(f"Mood tag preferences: {dict(list(tag_scores.items())[:5])}")  # Log top 5
    
    def _calculate_confidence_score(self, preferences: UserPreferences, feedback_count: int) -> float:
        """Calculate confidence score for preferences."""
        
        # Base confidence on feedback count
        base_confidence = min(1.0, feedback_count / 10.0)  # Max confidence at 10+ feedback
        
        # Reduce confidence if positive/negative feedback is very imbalanced
        if preferences.total_feedback_count > 0:
            positive_ratio = preferences.positive_feedback_count / preferences.total_feedback_count
            # Ideal ratio is around 0.7 (mostly positive but some negative for learning)
            balance_penalty = abs(positive_ratio - 0.7) * 0.5
            base_confidence *= (1.0 - balance_penalty)
        
        return max(0.1, min(1.0, base_confidence))


class PersonalizationEngine:
    """Main personalization engine that adjusts mood parameters based on user feedback."""
    
    def __init__(self):
        self.analyzer = UserPreferenceAnalyzer()
        self.logger = get_logger(__name__)
    
    def personalize_mood_parameters(
        self, 
        user_id: int, 
        original_params: MoodParameters
    ) -> Tuple[MoodParameters, UserPreferences]:
        """
        Personalize mood parameters based on user's feedback history.
        
        Args:
            user_id: Telegram user ID
            original_params: Original mood parameters from GPT
        
        Returns:
            Tuple of (personalized_params, user_preferences)
        """
        
        # Analyze user preferences
        user_preferences = self.analyzer.analyze_user_feedback(user_id)
        
        # If confidence is too low, return original parameters
        if user_preferences.confidence_score < 0.3:
            logger.info(f"Low confidence ({user_preferences.confidence_score:.2f}) for user {user_id}, using original parameters")
            return original_params, user_preferences
        
        # Create personalized parameters
        personalized_params = MoodParameters(
            # Audio features
            valence=self._adjust_parameter(
                original_params.valence, 
                user_preferences.valence_bias, 
                user_preferences.confidence_score
            ),
            energy=self._adjust_parameter(
                original_params.energy, 
                user_preferences.energy_bias, 
                user_preferences.confidence_score
            ),
            danceability=self._adjust_parameter(
                original_params.danceability, 
                user_preferences.danceability_bias, 
                user_preferences.confidence_score
            ),
            acousticness=self._adjust_parameter(
                original_params.acousticness, 
                user_preferences.acousticness_bias, 
                user_preferences.confidence_score
            ),
            instrumentalness=original_params.instrumentalness,  # Keep original for now
            speechiness=original_params.speechiness,  # Keep original
            tempo=self._adjust_tempo(
                original_params.tempo, 
                user_preferences.tempo_bias, 
                user_preferences.confidence_score
            ),
            loudness=original_params.loudness,  # Keep original
            mode=original_params.mode,  # Keep original
            
            # Context information (keep original)
            mood_tags=self._adjust_mood_tags(
                original_params.mood_tags, 
                user_preferences.mood_tag_preferences, 
                user_preferences.confidence_score
            ),
            activity=original_params.activity,
            time_of_day=original_params.time_of_day,
            weather=original_params.weather,
            social=original_params.social,
            emotional_intensity=original_params.emotional_intensity,
            
            # Preferences (adjusted)
            primary_genres=self._adjust_primary_genres(
                original_params.primary_genres, 
                user_preferences.genre_preferences, 
                user_preferences.confidence_score
            ),
            secondary_genres=self._adjust_secondary_genres(
                original_params.secondary_genres, 
                user_preferences.genre_preferences, 
                user_preferences.confidence_score
            ),
            exclude_genres=original_params.exclude_genres,  # Keep original
            popularity_range=original_params.popularity_range,  # Keep original
            decade_bias=original_params.decade_bias  # Keep original
        )
        
        logger.info(f"Personalized parameters for user {user_id}: "
                   f"valence {original_params.valence:.2f} -> {personalized_params.valence:.2f}, "
                   f"energy {original_params.energy:.2f} -> {personalized_params.energy:.2f}")
        
        return personalized_params, user_preferences
    
    def _adjust_parameter(self, original: float, bias: float, confidence: float) -> float:
        """Adjust a 0.0-1.0 parameter with bias and confidence."""
        adjustment = bias * confidence
        adjusted = original + adjustment
        return max(0.0, min(1.0, adjusted))
    
    def _adjust_tempo(self, original: int, bias: int, confidence: float) -> int:
        """Adjust tempo with bias and confidence."""
        adjustment = int(bias * confidence)
        adjusted = original + adjustment
        return max(50, min(200, adjusted))
    
    def _adjust_primary_genres(
        self, 
        original_genres: List[str], 
        genre_preferences: Dict[str, float], 
        confidence: float
    ) -> List[str]:
        """Adjust primary genre list based on preferences."""
        if not genre_preferences or confidence < 0.5:
            return original_genres
        
        # Start with original genres
        adjusted_genres = original_genres.copy()
        
        # Remove genres with strong negative preference
        adjusted_genres = [
            genre for genre in adjusted_genres 
            if genre_preferences.get(genre.lower(), 0) > -0.5
        ]
        
        # Add preferred genres if not already present
        preferred_genres = [
            genre for genre, score in genre_preferences.items() 
            if score > 0.5 and genre not in [g.lower() for g in adjusted_genres]
        ]
        
        # Add top preferred genres
        adjusted_genres.extend(preferred_genres[:2])
        
        return adjusted_genres[:2]  # Limit to 2 primary genres
    
    def _adjust_secondary_genres(
        self, 
        original_genres: List[str], 
        genre_preferences: Dict[str, float], 
        confidence: float
    ) -> List[str]:
        """Adjust secondary genre list based on preferences."""
        if not genre_preferences or confidence < 0.5:
            return original_genres
        
        # Start with original genres
        adjusted_genres = original_genres.copy()
        
        # Remove genres with strong negative preference
        adjusted_genres = [
            genre for genre in adjusted_genres 
            if genre_preferences.get(genre.lower(), 0) > -0.3  # Less strict than primary
        ]
        
        # Add moderately preferred genres if not already present
        moderate_genres = [
            genre for genre, score in genre_preferences.items() 
            if 0.2 < score <= 0.5 and genre not in [g.lower() for g in adjusted_genres]
        ]
        
        # Add moderate preference genres
        adjusted_genres.extend(moderate_genres[:3])
        
        return adjusted_genres[:3]  # Limit to 3 secondary genres
    
    def _adjust_mood_tags(
        self, 
        original_tags: List[str], 
        tag_preferences: Dict[str, float], 
        confidence: float
    ) -> List[str]:
        """Adjust mood tags based on preferences."""
        if not tag_preferences or confidence < 0.5:
            return original_tags
        
        # Start with original tags
        adjusted_tags = original_tags.copy()
        
        # Remove tags with strong negative preference
        adjusted_tags = [
            tag for tag in adjusted_tags 
            if tag_preferences.get(tag.lower(), 0) > -0.5
        ]
        
        # Add preferred tags if not already present
        preferred_tags = [
            tag for tag, score in tag_preferences.items() 
            if score > 0.5 and tag not in [t.lower() for t in adjusted_tags]
        ]
        
        # Add top 2 preferred tags
        adjusted_tags.extend(preferred_tags[:2])
        
        return adjusted_tags[:5]  # Limit to 5 tags


# Global personalization engine instance
personalization_engine = PersonalizationEngine() 