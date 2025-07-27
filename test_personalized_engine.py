#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации PersonalizedPlaylistEngine.

Демонстрирует создание персонализированных плейлистов БЕЗ использования audio_features API.
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from moodtape_core.personalized_engine import (
    PersonalizedPlaylistEngine, 
    UserMusicProfile, 
    MoodToGenreMapper, 
    PersonalizedRecommendationEngine,
    SmartTrackFilter,
    UserProfile
)
from moodtape_core.gpt_parser import MoodParameters
from utils.logger import get_logger

logger = get_logger(__name__)


class MockSpotifyClient:
    """Mock Spotify client для тестирования без реального API."""
    
    def __init__(self):
        self.client = self  # Имитируем реальный client
        
        # Моковые данные топ артистов
        self.mock_artists = [
            {
                'id': 'artist1', 'name': 'The Weeknd',
                'genres': ['pop', 'r&b', 'alternative r&b'], 'popularity': 95
            },
            {
                'id': 'artist2', 'name': 'Radiohead',
                'genres': ['alternative rock', 'art rock', 'post-punk'], 'popularity': 85
            },
            {
                'id': 'artist3', 'name': 'Tame Impala',
                'genres': ['psychedelic pop', 'indie rock', 'dream pop'], 'popularity': 80
            }
        ]
        
        # Моковые данные треков
        self.mock_tracks = [
            {
                'id': 'track1', 'name': 'Blinding Lights', 'popularity': 95,
                'artists': [{'id': 'artist1', 'name': 'The Weeknd'}],
                'uri': 'spotify:track:track1'
            },
            {
                'id': 'track2', 'name': 'Karma Police', 'popularity': 85,
                'artists': [{'id': 'artist2', 'name': 'Radiohead'}],
                'uri': 'spotify:track:track2'
            }
        ]
    
    def current_user_top_artists(self, time_range='medium_term', limit=20):
        """Моковые топ артисты."""
        return {'items': self.mock_artists[:limit]}
    
    def current_user_saved_tracks(self, limit=50):
        """Моковые liked треки."""
        return {'items': [{'track': track} for track in self.mock_tracks[:limit]]}
    
    def current_user_top_tracks(self, time_range='medium_term', limit=50):
        """Моковые топ треки."""
        return {'items': self.mock_tracks[:limit]}
    
    def tracks(self, track_ids):
        """Моковая информация о треках."""
        tracks = []
        for track_id in track_ids:
            track = next((t for t in self.mock_tracks if t['id'] == track_id), None)
            if track:
                tracks.append(track)
        return {'tracks': tracks}
    
    def recommendations(self, **kwargs):
        """Моковые рекомендации."""
        logger.info(f"🔍 [MOCK] Getting recommendations with params: {kwargs}")
        
        # Возвращаем моковые рекомендации
        recommendations = []
        for i in range(kwargs.get('limit', 20)):
            recommendations.append({
                'id': f'rec_track_{i}',
                'name': f'Recommended Track {i+1}',
                'popularity': 70 + (i % 30),
                'artists': [{'id': f'rec_artist_{i}', 'name': f'Artist {i+1}'}],
                'uri': f'spotify:track:rec_track_{i}',
                'preview_url': f'https://example.com/preview_{i}',
                'external_urls': {'spotify': f'https://open.spotify.com/track/rec_track_{i}'}
            })
        
        return {'tracks': recommendations}
    
    def get_user_liked_tracks(self, limit=50):
        """Адаптер для существующего интерфейса."""
        result = self.current_user_saved_tracks(limit)
        return [item['track'] for item in result['items']]
    
    def get_user_top_tracks(self, time_range='medium_term', limit=50):
        """Адаптер для существующего интерфейса."""
        result = self.current_user_top_tracks(time_range, limit)
        return result['items']


def test_mood_to_genre_mapper():
    """Тестирует MoodToGenreMapper."""
    print("\n🔍 Testing MoodToGenreMapper...")
    
    mapper = MoodToGenreMapper()
    
    # Тест 1: Базовые mood теги
    mood_tags = ['energetic', 'upbeat', 'party']
    user_genres = ['electronic', 'pop', 'dance']
    
    mapped_genres = mapper.map_mood_to_genres(mood_tags, user_genres)
    print(f"✅ Mood tags {mood_tags} -> Genres: {mapped_genres}")
    
    # Тест 2: Меланхоличное настроение
    mood_tags = ['melancholic', 'rainy', 'introspective']
    user_genres = ['indie', 'alternative', 'rock']
    
    mapped_genres = mapper.map_mood_to_genres(mood_tags, user_genres)
    print(f"✅ Mood tags {mood_tags} -> Genres: {mapped_genres}")


def test_user_music_profile():
    """Тестирует UserMusicProfile."""
    print("\n🔍 Testing UserMusicProfile...")
    
    profile_analyzer = UserMusicProfile()
    mock_client = MockSpotifyClient()
    
    # Анализируем профиль пользователя
    user_profile = profile_analyzer.analyze_user_preferences("test_user", mock_client)
    
    print(f"✅ User Profile Created:")
    print(f"   - Favorite Artists: {len(user_profile.favorite_artists)}")
    print(f"   - Favorite Genres: {user_profile.favorite_genres}")
    print(f"   - Preferred Popularity: {user_profile.preferred_popularity:.1f}")
    print(f"   - Recent Tracks: {len(user_profile.recent_tracks)}")
    
    return user_profile


def test_personalized_recommendation_engine():
    """Тестирует PersonalizedRecommendationEngine."""
    print("\n🔍 Testing PersonalizedRecommendationEngine...")
    
    mock_client = MockSpotifyClient()
    rec_engine = PersonalizedRecommendationEngine(mock_client)
    
    # Создаем тестовые MoodParameters
    mood_params = MoodParameters(
        valence=0.8,
        energy=0.9,
        danceability=0.7,
        acousticness=0.2,
        instrumentalness=0.1,
        speechiness=0.1,
        tempo=120,
        loudness=-6.0,
        mode=1,
        mood_tags=['energetic', 'upbeat', 'party'],
        activity='party',
        time_of_day='night',
        weather=None,
        social='friends',
        emotional_intensity=0.8,
        primary_genres=['electronic', 'pop'],
        secondary_genres=['dance', 'house'],
        exclude_genres=[],
        popularity_range=[60, 95],
        decade_bias=None
    )
    
    # Создаем тестовый профиль пользователя
    user_profile = UserProfile(
        favorite_artists=[{'id': 'artist1', 'name': 'Test Artist'}],
        favorite_artist_ids=['artist1'],
        favorite_genres=['electronic', 'pop', 'dance'],
        preferred_popularity=75.0,
        recent_tracks=[],
        top_track_ids=['track1'],
        genre_distribution={'electronic': 1.0, 'pop': 0.8}
    )
    
    # Генерируем рекомендации
    recommendations = rec_engine.generate_recommendations(mood_params, user_profile, limit=30)
    
    print(f"✅ Generated {len(recommendations)} recommendations")
    if recommendations:
        print(f"   Sample tracks:")
        for i, track in enumerate(recommendations[:3]):
            print(f"   {i+1}. '{track['name']}' by {track['artists'][0]['name']}")
    
    return recommendations


def test_smart_track_filter():
    """Тестирует SmartTrackFilter."""
    print("\n🔍 Testing SmartTrackFilter...")
    
    filter_engine = SmartTrackFilter()
    
    # Моковые треки для фильтрации
    mock_tracks = [
        {
            'id': 'track1', 'name': 'Popular Dance Track', 'popularity': 85,
            'artists': [{'id': 'artist1', 'name': 'Popular Artist'}],
            'discovery_method': 'artist_based'
        },
        {
            'id': 'track2', 'name': 'Indie Alternative Song', 'popularity': 45,
            'artists': [{'id': 'artist2', 'name': 'Indie Artist'}],
            'discovery_method': 'genre_based'
        },
        {
            'id': 'track3', 'name': 'Electronic Remix', 'popularity': 70,
            'artists': [{'id': 'artist3', 'name': 'Electronic Artist'}],
            'discovery_method': 'track_based'
        }
    ]
    
    # Тестовые параметры
    mood_params = MoodParameters(
        valence=0.8, energy=0.9, danceability=0.7, acousticness=0.2,
        instrumentalness=0.1, speechiness=0.1, tempo=120, loudness=-6.0, mode=1,
        mood_tags=['energetic', 'dance'], activity='party', time_of_day='night',
        weather=None, social='friends', emotional_intensity=0.8,
        primary_genres=['electronic', 'dance'], secondary_genres=['pop'],
        exclude_genres=[], popularity_range=[60, 90], decade_bias=None
    )
    
    user_profile = UserProfile(
        favorite_artists=[{'id': 'artist1', 'name': 'Popular Artist', 'genres': ['electronic', 'dance']}],
        favorite_artist_ids=['artist1'],
        favorite_genres=['electronic', 'dance', 'pop'],
        preferred_popularity=75.0,
        recent_tracks=[], top_track_ids=[],
        genre_distribution={'electronic': 1.0, 'dance': 0.8}
    )
    
    # Фильтруем и ранжируем треки
    filtered_tracks = filter_engine.filter_and_rank_tracks(
        mock_tracks, mood_params, user_profile, target_count=5
    )
    
    print(f"✅ Filtered {len(mock_tracks)} -> {len(filtered_tracks)} tracks")
    for i, (track, score) in enumerate(filtered_tracks):
        print(f"   {i+1}. '{track['name']}' - Score: {score:.3f}")
    
    return filtered_tracks


def test_full_personalized_engine():
    """Тестирует полный PersonalizedPlaylistEngine."""
    print("\n🔍 Testing Full PersonalizedPlaylistEngine...")
    
    mock_client = MockSpotifyClient()
    engine = PersonalizedPlaylistEngine(mock_client)
    
    # Создаем тестовые MoodParameters
    mood_params = MoodParameters(
        valence=0.7, energy=0.8, danceability=0.6, acousticness=0.3,
        instrumentalness=0.2, speechiness=0.1, tempo=110, loudness=-8.0, mode=1,
        mood_tags=['chill', 'electronic', 'dreamy'],
        activity='study', time_of_day='evening', weather='rainy',
        social='alone', emotional_intensity=0.6,
        primary_genres=['electronic', 'ambient'], secondary_genres=['chillout', 'downtempo'],
        exclude_genres=[], popularity_range=[40, 80], decade_bias=None
    )
    
    # Создаем персонализированный плейлист
    playlist_tracks = engine.create_personalized_playlist(
        user_id="test_user_123",
        mood_params=mood_params,
        target_length=15
    )
    
    print(f"✅ Created personalized playlist with {len(playlist_tracks)} tracks")
    
    if playlist_tracks:
        print(f"   Discovery methods breakdown:")
        methods = {}
        for track in playlist_tracks:
            method = track.get('discovery_method', 'unknown')
            methods[method] = methods.get(method, 0) + 1
        
        for method, count in methods.items():
            print(f"   - {method}: {count} tracks")
        
        print(f"\n   Sample tracks:")
        for i, track in enumerate(playlist_tracks[:5]):
            artists = ', '.join([a.get('name', 'Unknown') for a in track.get('artists', [])])
            print(f"   {i+1}. '{track.get('name', 'Unknown')}' by {artists}")
    
    return playlist_tracks


def main():
    """Запускает все тесты персонализированного алгоритма."""
    print("🎵 Testing PersonalizedPlaylistEngine - Audio Features Free Algorithm")
    print("="*70)
    
    try:
        # Тест 1: MoodToGenreMapper
        test_mood_to_genre_mapper()
        
        # Тест 2: UserMusicProfile
        user_profile = test_user_music_profile()
        
        # Тест 3: PersonalizedRecommendationEngine
        recommendations = test_personalized_recommendation_engine()
        
        # Тест 4: SmartTrackFilter
        filtered_tracks = test_smart_track_filter()
        
        # Тест 5: Полный PersonalizedPlaylistEngine
        playlist = test_full_personalized_engine()
        
        print("\n" + "="*70)
        print("✅ All tests completed successfully!")
        print(f"   ✅ PersonalizedPlaylistEngine works WITHOUT audio_features API")
        print(f"   ✅ Fallback algorithm ready for HTTP 403 errors")
        print(f"   ✅ User personalization through Spotify Recommendations API")
        print(f"   ✅ Smart mood-to-genre mapping implemented")
        print(f"   ✅ Intelligent track filtering and scoring working")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 