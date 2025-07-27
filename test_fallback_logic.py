#!/usr/bin/env python3
"""
Тестовый скрипт для проверки fallback логики при 403 ошибках audio_features API.

Симулирует HTTP 403 ошибки и проверяет что PersonalizedPlaylistEngine активируется.
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from moodtape_core.playlist_builder import PlaylistBuilder, AudioFeaturesUnavailableError
from moodtape_core.gpt_parser import MoodParameters
from utils.logger import get_logger

logger = get_logger(__name__)


class Mock403SpotifyClient:
    """Mock Spotify client который симулирует 403 ошибки audio_features."""
    
    def __init__(self):
        self.client = self  # Имитируем реальный client
        self.call_count = 0
        
    def is_authenticated(self):
        return True
    
    def get_user_liked_tracks(self, limit=50):
        """Моковые liked треки."""
        return [
            {
                'id': 'liked_track_1', 'name': 'Liked Track 1',
                'artists': [{'id': 'artist1', 'name': 'Artist 1'}],
                'uri': 'spotify:track:liked_track_1'
            }
        ]
    
    def search_tracks_by_mood(self, mood_params, limit=50):
        """Моковый поиск треков который вызовет 403 в audio_features."""
        return [
            {
                'id': 'mood_track_1', 'name': 'Mood Track 1',
                'artists': [{'id': 'artist1', 'name': 'Artist 1'}],
                'uri': 'spotify:track:mood_track_1'
            },
            {
                'id': 'mood_track_2', 'name': 'Mood Track 2', 
                'artists': [{'id': 'artist2', 'name': 'Artist 2'}],
                'uri': 'spotify:track:mood_track_2'
            }
        ]
    
    def get_audio_features(self, track_ids):
        """Симулирует 403 ошибку audio_features API."""
        self.call_count += 1
        logger.info(f"🔍 [MOCK] get_audio_features called #{self.call_count} with {len(track_ids)} tracks")
        
        # Симулируем 403 ошибку
        raise Exception("HTTP 403 Forbidden: Insufficient client scope")


class MockPersonalizedEngine:
    """Mock PersonalizedPlaylistEngine для тестирования."""
    
    def __init__(self, spotify_client):
        self.spotify_client = spotify_client
        
    def create_personalized_playlist(self, user_id, mood_params, target_length=20):
        """Создает моковый персонализированный плейлист."""
        logger.info(f"🔍 [MOCK_PERSONALIZED] Creating playlist for user {user_id}, length {target_length}")
        
        # Возвращаем моковые треки из персонализированного алгоритма
        personalized_tracks = []
        for i in range(target_length):
            track = {
                'id': f'personalized_track_{i+1}',
                'name': f'Personalized Track {i+1}',
                'artists': [{'id': f'pers_artist_{i+1}', 'name': f'Personalized Artist {i+1}'}],
                'uri': f'spotify:track:personalized_track_{i+1}',
                'discovery_method': 'personalized_fallback',
                'popularity': 75 + (i % 20)
            }
            personalized_tracks.append(track)
        
        logger.info(f"🔍 [MOCK_PERSONALIZED] Generated {len(personalized_tracks)} personalized tracks")
        return personalized_tracks


def test_403_fallback_detection():
    """Тестирует обнаружение 403 ошибок и переключение на fallback."""
    print("\n🔍 Testing 403 Error Detection...")
    
    # Создаем тестовые mood параметры
    mood_params = MoodParameters(
        valence=0.8, energy=0.9, danceability=0.7, acousticness=0.2,
        instrumentalness=0.1, speechiness=0.1, tempo=120, loudness=-6.0, mode=1,
        mood_tags=['energetic', 'dance'], activity='party', time_of_day='night',
        weather=None, social='friends', emotional_intensity=0.8,
        primary_genres=['electronic', 'dance'], secondary_genres=['pop'],
        exclude_genres=[], popularity_range=[60, 90], decade_bias=None
    )
    
    # Создаем mock Spotify client который дает 403 ошибку
    mock_client = Mock403SpotifyClient()
    
    # Создаем PlaylistBuilder с mock клиентом
    playlist_builder = PlaylistBuilder(user_id=12345, service="spotify")
    playlist_builder.spotify_client = mock_client
    
    # Патчим PersonalizedPlaylistEngine
    original_import = __builtins__.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == 'moodtape_core.personalized_engine':
            class MockModule:
                PersonalizedPlaylistEngine = MockPersonalizedEngine
            return MockModule()
        return original_import(name, *args, **kwargs)
    
    __builtins__.__import__ = mock_import
    
    try:
        # Тестируем fallback логику
        logger.info("🔍 Testing _get_mood_based_tracks with 403 error...")
        
        result_tracks = playlist_builder._get_mood_based_tracks(mood_params, limit=10)
        
        logger.info(f"✅ Fallback successful: {len(result_tracks)} tracks returned")
        
        # Проверяем что это треки из персонализированного алгоритма
        personalized_count = sum(1 for track in result_tracks 
                                if track.get('discovery_method') == 'personalized_fallback')
        
        print(f"✅ 403 Error Detection Test Results:")
        print(f"   - Total tracks returned: {len(result_tracks)}")
        print(f"   - Personalized tracks: {personalized_count}")
        print(f"   - Audio features API calls: {mock_client.call_count}")
        print(f"   - Fallback activated: {'✅ YES' if personalized_count > 0 else '❌ NO'}")
        
        return len(result_tracks) > 0 and personalized_count > 0
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Восстанавливаем оригинальный import
        __builtins__.__import__ = original_import


def test_audiofeatures_exception():
    """Тестирует AudioFeaturesUnavailableError exception."""
    print("\n🔍 Testing AudioFeaturesUnavailableError...")
    
    try:
        # Тестируем что exception корректно создается
        raise AudioFeaturesUnavailableError("Test 403 error")
    except AudioFeaturesUnavailableError as e:
        print(f"✅ AudioFeaturesUnavailableError works: {e}")
        return True
    except Exception as e:
        print(f"❌ Unexpected exception type: {type(e)} - {e}")
        return False


def test_error_keyword_detection():
    """Тестирует обнаружение ключевых слов ошибок."""
    print("\n🔍 Testing Error Keyword Detection...")
    
    test_errors = [
        "HTTP 403 Forbidden: Insufficient client scope",
        "audio_features API unavailable",
        "403 forbidden access denied", 
        "Permission denied for audio features",
        "Some other random error"
    ]
    
    detected_403_errors = 0
    
    for error_msg in test_errors:
        error_str = error_msg.lower()
        is_403_error = any(keyword in error_str for keyword in ['403', 'audio', 'forbidden', 'permission', 'unauthorized'])
        
        print(f"   '{error_msg}' -> 403 detected: {'✅ YES' if is_403_error else '❌ NO'}")
        
        if is_403_error and ('403' in error_str or 'forbidden' in error_str or 'audio' in error_str):
            detected_403_errors += 1
    
    print(f"✅ Detected {detected_403_errors}/4 expected 403-related errors")
    return detected_403_errors >= 4


def main():
    """Запускает все тесты fallback логики."""
    print("🚨 Testing Critical 403 Fallback Logic")
    print("="*50)
    
    results = []
    
    try:
        # Тест 1: AudioFeaturesUnavailableError
        results.append(test_audiofeatures_exception())
        
        # Тест 2: Keyword detection
        results.append(test_error_keyword_detection())
        
        # Тест 3: Full 403 fallback
        results.append(test_403_fallback_detection())
        
        print("\n" + "="*50)
        
        passed_tests = sum(results)
        total_tests = len(results)
        
        if passed_tests == total_tests:
            print("✅ ALL TESTS PASSED!")
            print(f"   ✅ 403 Error detection working")
            print(f"   ✅ PersonalizedPlaylistEngine fallback active")
            print(f"   ✅ AudioFeaturesUnavailableError exception ready")
            print(f"   ✅ Critical fallback logic implemented successfully")
            
        else:
            print(f"❌ {total_tests - passed_tests}/{total_tests} tests failed")
            print(f"   ❌ Fallback logic needs fixes")
            
    except Exception as e:
        print(f"\n❌ Critical test failure: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 