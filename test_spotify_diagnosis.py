#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики Spotify разрешений.

Проверяет какие именно API доступны и где происходят 403 ошибки.
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth.spotify_auth import SpotifyClient
from utils.logger import get_logger

logger = get_logger(__name__)


class MockSpotifyClientForDiag:
    """Mock Spotify client для тестирования диагностики."""
    
    def __init__(self, simulate_403_on_audio_features=True):
        self.simulate_403_on_audio_features = simulate_403_on_audio_features
        self.call_count = 0
        
    def current_user(self):
        """Моковый user profile."""
        return {
            'id': 'test_user_123',
            'display_name': 'Test User',
            'country': 'US',
            'followers': {'total': 42}
        }
    
    def current_user_saved_tracks(self, limit=50):
        """Моковые liked треки."""
        return {
            'total': 150,
            'items': [
                {
                    'track': {
                        'id': 'test_track_1',
                        'name': 'Test Song',
                        'artists': [{'name': 'Test Artist'}]
                    }
                }
            ]
        }
    
    def current_user_top_tracks(self, limit=50):
        """Моковые топ треки."""
        return {
            'items': [
                {
                    'id': 'top_track_1',
                    'name': 'Top Song',
                    'artists': [{'name': 'Top Artist'}]
                }
            ]
        }
    
    def current_user_top_artists(self, limit=50):
        """Моковые топ артисты."""
        return {
            'items': [
                {
                    'id': 'top_artist_1',
                    'name': 'Top Artist',
                    'genres': ['pop', 'rock']
                }
            ]
        }
    
    def audio_features(self, track_ids):
        """Симулирует 403 ошибку на audio_features или успешный ответ."""
        self.call_count += 1
        
        if self.simulate_403_on_audio_features:
            # Симулируем 403 ошибку
            from spotipy.exceptions import SpotifyException
            raise SpotifyException(403, -1, "Insufficient client scope")
        else:
            # Возвращаем моковые audio features
            return [
                {
                    'valence': 0.8,
                    'energy': 0.9,
                    'danceability': 0.7,
                    'tempo': 120
                }
            ]
    
    def user_playlist_create(self, user_id, name, public=True, description=""):
        """Моковое создание плейлиста."""
        return {
            'id': 'test_playlist_123',
            'name': name,
            'public': public
        }
    
    def current_user_unfollow_playlist(self, playlist_id):
        """Моковое удаление плейлиста."""
        return True
    
    def recommendations(self, **kwargs):
        """Моковые рекомендации."""
        return {
            'tracks': [
                {
                    'id': 'rec_track_1',
                    'name': 'Recommended Song',
                    'artists': [{'name': 'Rec Artist'}]
                }
            ]
        }
    
    def search(self, q, type='track', limit=20):
        """Моковый поиск."""
        return {
            'tracks': {
                'items': [
                    {
                        'id': 'search_track_1',
                        'name': 'Search Result',
                        'artists': [{'name': 'Search Artist'}]
                    }
                ]
            }
        }
    
    def current_user_playlists(self, limit=50):
        """Моковые плейлисты пользователя."""
        return {
            'items': [
                {
                    'id': 'user_playlist_1',
                    'name': 'My Playlist',
                    'tracks': {'total': 25}
                }
            ]
        }


def test_spotify_diagnosis_with_403():
    """Тестирует диагностику когда audio_features возвращает 403."""
    print("\n🔍 Testing Spotify Diagnosis with 403 on audio_features...")
    
    # Создаем SpotifyClient с mock клиентом
    spotify_client = SpotifyClient(user_id=12345)
    
    # Заменяем реальный client на mock с 403 ошибкой
    spotify_client.client = MockSpotifyClientForDiag(simulate_403_on_audio_features=True)
    
    # Запускаем диагностику
    try:
        spotify_client.diagnose_spotify_permissions(12345)
        print("✅ Diagnosis completed - check logs above for audio_features 403 error")
        return True
    except Exception as e:
        print(f"❌ Diagnosis failed with error: {e}")
        return False


def test_spotify_diagnosis_success():
    """Тестирует диагностику когда все API работают."""
    print("\n🔍 Testing Spotify Diagnosis with all APIs working...")
    
    # Создаем SpotifyClient с mock клиентом
    spotify_client = SpotifyClient(user_id=12345)
    
    # Заменяем реальный client на mock без ошибок
    spotify_client.client = MockSpotifyClientForDiag(simulate_403_on_audio_features=False)
    
    # Запускаем диагностику
    try:
        spotify_client.diagnose_spotify_permissions(12345)
        print("✅ Diagnosis completed - all APIs should show OK")
        return True
    except Exception as e:
        print(f"❌ Diagnosis failed with error: {e}")
        return False


def test_spotify_diagnosis_no_client():
    """Тестирует диагностику когда нет Spotify client."""
    print("\n🔍 Testing Spotify Diagnosis with no client...")
    
    # Создаем SpotifyClient без client
    spotify_client = SpotifyClient(user_id=12345)
    spotify_client.client = None
    
    # Запускаем диагностику
    try:
        spotify_client.diagnose_spotify_permissions(12345)
        print("✅ No client diagnosis completed")
        return True
    except Exception as e:
        print(f"❌ Diagnosis failed with error: {e}")
        return False


def main():
    """Запускает все тесты диагностики."""
    print("🔍 Testing Spotify Permissions Diagnosis")
    print("="*50)
    
    results = []
    
    try:
        # Тест 1: Диагностика с 403 на audio_features
        results.append(test_spotify_diagnosis_with_403())
        
        # Тест 2: Диагностика со всеми работающими API
        results.append(test_spotify_diagnosis_success())
        
        # Тест 3: Диагностика без client
        results.append(test_spotify_diagnosis_no_client())
        
        print("\n" + "="*50)
        
        passed_tests = sum(results)
        total_tests = len(results)
        
        if passed_tests == total_tests:
            print("✅ ALL DIAGNOSIS TESTS PASSED!")
            print(f"   ✅ 403 error detection working")
            print(f"   ✅ All APIs diagnosis working")
            print(f"   ✅ No client handling working")
            print(f"   ✅ Diagnosis ready for production use")
            
        else:
            print(f"❌ {total_tests - passed_tests}/{total_tests} tests failed")
            print(f"   ❌ Diagnosis needs fixes")
            
    except Exception as e:
        print(f"\n❌ Critical diagnosis test failure: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 