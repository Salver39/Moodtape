"""
Персонализированный алгоритм создания плейлистов без audio_features API.

Решает проблему HTTP 403 ошибок при запросе audio_features через:
- Анализ пользовательских данных (топ артисты, жанры, liked треки)
- Умный mapping mood тегов к жанрам
- Spotify Recommendations API
- Персонализированную фильтрацию и scoring
"""

import random
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict, Counter

from utils.logger import get_logger
from moodtape_core.gpt_parser import MoodParameters

logger = get_logger(__name__)


@dataclass
class UserProfile:
    """Профиль музыкальных предпочтений пользователя."""
    favorite_artists: List[Dict[str, Any]]
    favorite_artist_ids: List[str]
    favorite_genres: List[str]
    preferred_popularity: float
    recent_tracks: List[Dict[str, Any]]
    top_track_ids: List[str]
    genre_distribution: Dict[str, float]
    
    def __str__(self):
        return (f"UserProfile(artists={len(self.favorite_artists)}, "
                f"genres={len(self.favorite_genres)}, "
                f"popularity={self.preferred_popularity:.0f})")


class UserMusicProfile:
    """Анализирует музыкальные предпочтения пользователя."""
    
    def __init__(self):
        self.genre_cache = {}
    
    def analyze_user_preferences(self, user_id: str, spotify_client) -> UserProfile:
        """
        Анализирует музыкальные предпочтения пользователя через доступные API.
        
        Args:
            user_id: ID пользователя
            spotify_client: Авторизованный Spotify клиент
            
        Returns:
            UserProfile с анализом предпочтений пользователя
        """
        logger.info(f"🔍 [USER_ANALYSIS] Analyzing music preferences for user {user_id}")
        
        try:
            # 1. Получаем топ артистов пользователя
            top_artists = self._get_user_top_artists(spotify_client)
            logger.info(f"🔍 [USER_ANALYSIS] Found {len(top_artists)} top artists")
            
            # 2. Извлекаем любимые жанры из артистов
            favorite_genres = self._extract_genres_from_artists(top_artists)
            logger.info(f"🔍 [USER_ANALYSIS] Extracted {len(favorite_genres)} favorite genres: {favorite_genres[:5]}")
            
            # 3. Анализируем предпочитаемый уровень популярности
            preferred_popularity = self._analyze_popularity_preference(spotify_client)
            logger.info(f"🔍 [USER_ANALYSIS] Preferred popularity level: {preferred_popularity:.1f}")
            
            # 4. Получаем недавние треки для актуальных предпочтений
            recent_tracks = self._get_recent_tracks(spotify_client)
            logger.info(f"🔍 [USER_ANALYSIS] Found {len(recent_tracks)} recent tracks")
            
            # 5. Создаем профиль пользователя
            user_profile = UserProfile(
                favorite_artists=top_artists,
                favorite_artist_ids=[artist['id'] for artist in top_artists],
                favorite_genres=favorite_genres,
                preferred_popularity=preferred_popularity,
                recent_tracks=recent_tracks,
                top_track_ids=[track['id'] for track in recent_tracks[:10]],
                genre_distribution=self._calculate_genre_distribution(favorite_genres)
            )
            
            logger.info(f"🔍 [USER_ANALYSIS] User profile created: {user_profile}")
            return user_profile
            
        except Exception as e:
            logger.error(f"❌ [USER_ANALYSIS] Error analyzing user preferences: {e}")
            # Возвращаем базовый профиль для fallback
            return self._create_fallback_profile()
    
    def _get_user_top_artists(self, spotify_client) -> List[Dict[str, Any]]:
        """Получает топ артистов пользователя из разных периодов."""
        all_artists = []
        
        try:
            # Проверяем есть ли у клиента spotipy instance
            if hasattr(spotify_client, 'client') and spotify_client.client:
                sp = spotify_client.client
            else:
                logger.warning("🔍 [USER_ANALYSIS] No spotify client available")
                return []
            
            # Получаем топ артистов за разные периоды
            for time_range in ["short_term", "medium_term", "long_term"]:
                try:
                    result = sp.current_user_top_artists(time_range=time_range, limit=20)
                    artists = result.get('items', [])
                    
                    for artist in artists:
                        all_artists.append({
                            'id': artist['id'],
                            'name': artist['name'],
                            'genres': artist.get('genres', []),
                            'popularity': artist.get('popularity', 50),
                            'time_range': time_range
                        })
                    
                    logger.info(f"🔍 [USER_ANALYSIS] Got {len(artists)} artists from {time_range}")
                    
                except Exception as e:
                    logger.warning(f"🔍 [USER_ANALYSIS] Error getting {time_range} artists: {e}")
                    continue
            
            # Дедупликация по ID артиста
            seen_ids = set()
            unique_artists = []
            for artist in all_artists:
                if artist['id'] not in seen_ids:
                    unique_artists.append(artist)
                    seen_ids.add(artist['id'])
            
            return unique_artists[:50]  # Максимум 50 топ артистов
            
        except Exception as e:
            logger.error(f"❌ [USER_ANALYSIS] Error fetching top artists: {e}")
            return []
    
    def _extract_genres_from_artists(self, artists: List[Dict[str, Any]]) -> List[str]:
        """Извлекает и ранжирует жанры из списка артистов."""
        genre_counts = Counter()
        
        for artist in artists:
            genres = artist.get('genres', [])
            popularity = artist.get('popularity', 50)
            
            # Учитываем популярность артиста при подсчете жанров
            weight = popularity / 100.0 + 0.5  # Вес от 0.5 до 1.5
            
            for genre in genres:
                genre_counts[genre] += weight
        
        # Возвращаем топ жанры, отсортированные по весу
        top_genres = [genre for genre, count in genre_counts.most_common(25)]
        
        logger.info(f"🔍 [USER_ANALYSIS] Genre distribution: {dict(genre_counts.most_common(10))}")
        return top_genres
    
    def _analyze_popularity_preference(self, spotify_client) -> float:
        """Анализирует предпочитаемый уровень популярности из liked треков."""
        try:
            liked_tracks = spotify_client.get_user_liked_tracks(limit=50)
            top_tracks = spotify_client.get_user_top_tracks(limit=30)
            
            all_tracks = liked_tracks + top_tracks
            
            if not all_tracks:
                logger.warning("🔍 [USER_ANALYSIS] No tracks for popularity analysis, using default")
                return 60.0  # Средняя популярность по умолчанию
            
            # Получаем popularity для треков через Spotify API
            popularities = []
            
            if hasattr(spotify_client, 'client') and spotify_client.client:
                sp = spotify_client.client
                
                # Группируем треки для batch запроса
                track_ids = [track['id'] for track in all_tracks if track.get('id')]
                
                # Batch запрос треков (до 50 за раз)
                for i in range(0, len(track_ids), 50):
                    batch_ids = track_ids[i:i+50]
                    try:
                        tracks_info = sp.tracks(batch_ids)
                        for track in tracks_info.get('tracks', []):
                            if track and 'popularity' in track:
                                popularities.append(track['popularity'])
                    except Exception as e:
                        logger.warning(f"🔍 [USER_ANALYSIS] Error getting track popularity: {e}")
                        continue
            
            if popularities:
                avg_popularity = sum(popularities) / len(popularities)
                logger.info(f"🔍 [USER_ANALYSIS] Analyzed {len(popularities)} tracks, avg popularity: {avg_popularity:.1f}")
                return avg_popularity
            else:
                return 60.0  # Fallback значение
                
        except Exception as e:
            logger.error(f"❌ [USER_ANALYSIS] Error analyzing popularity preference: {e}")
            return 60.0
    
    def _get_recent_tracks(self, spotify_client) -> List[Dict[str, Any]]:
        """Получает недавние треки пользователя для актуальных предпочтений."""
        try:
            # Комбинируем топ треки за короткий период и liked треки
            recent_top = spotify_client.get_user_top_tracks(time_range="short_term", limit=20)
            recent_liked = spotify_client.get_user_liked_tracks(limit=30)
            
            # Объединяем и дедуплицируем
            all_recent = recent_top + recent_liked
            seen_ids = set()
            unique_recent = []
            
            for track in all_recent:
                if track['id'] not in seen_ids:
                    unique_recent.append(track)
                    seen_ids.add(track['id'])
            
            return unique_recent[:30]  # Максимум 30 недавних треков
            
        except Exception as e:
            logger.error(f"❌ [USER_ANALYSIS] Error getting recent tracks: {e}")
            return []
    
    def _calculate_genre_distribution(self, genres: List[str]) -> Dict[str, float]:
        """Рассчитывает распределение жанров для взвешивания."""
        total = len(genres)
        if total == 0:
            return {}
        
        distribution = {}
        for i, genre in enumerate(genres):
            # Убывающий вес для жанров (первые важнее)
            weight = (total - i) / total
            distribution[genre] = weight
        
        return distribution
    
    def _create_fallback_profile(self) -> UserProfile:
        """Создает базовый профиль для случаев ошибки."""
        logger.warning("🔍 [USER_ANALYSIS] Creating fallback user profile")
        
        return UserProfile(
            favorite_artists=[],
            favorite_artist_ids=[],
            favorite_genres=["pop", "rock", "electronic", "indie", "alternative"],
            preferred_popularity=60.0,
            recent_tracks=[],
            top_track_ids=[],
            genre_distribution={"pop": 1.0, "rock": 0.8, "electronic": 0.6}
        )


class MoodToGenreMapper:
    """Маппинг mood тегов к соответствующим жанрам."""
    
    def __init__(self):
        self.mood_mappings = {
            # Эмоциональные состояния
            'melancholic': ['indie', 'alternative', 'ambient', 'shoegaze', 'slowcore', 'sad', 'emo'],
            'nostalgic': ['indie', 'folk', 'alternative rock', 'classic rock', 'vintage'],
            'euphoric': ['electronic', 'trance', 'house', 'techno', 'progressive house'],
            'romantic': ['r&b', 'soul', 'neo soul', 'jazz', 'bossa nova', 'indie pop'],
            'angry': ['metal', 'punk', 'hardcore', 'aggressive', 'hard rock', 'nu metal'],
            'peaceful': ['ambient', 'chillout', 'new age', 'meditation', 'classical'],
            'mysterious': ['dark ambient', 'trip hop', 'experimental', 'post-rock', 'darkwave'],
            
            # Энергетические состояния
            'energetic': ['pop', 'electronic', 'dance', 'punk', 'rock', 'edm', 'house'],
            'upbeat': ['pop', 'indie pop', 'electronic', 'dance pop', 'funk', 'disco'],
            'chill': ['chillout', 'ambient', 'downtempo', 'lo-fi', 'chillwave', 'trip hop'],
            'relaxing': ['ambient', 'chillout', 'acoustic', 'folk', 'jazz', 'classical'],
            'intense': ['metal', 'hard rock', 'electronic', 'drum and bass', 'dubstep'],
            'mellow': ['indie', 'folk', 'acoustic', 'singer-songwriter', 'soft rock'],
            
            # Активности и контекст
            'thoughtful': ['folk', 'singer-songwriter', 'indie folk', 'classical', 'post-rock'],
            'introspective': ['indie rock', 'alternative', 'post-punk', 'art rock', 'experimental'],
            'celebratory': ['pop', 'funk', 'disco', 'electronic', 'dance', 'party'],
            'motivational': ['rock', 'electronic', 'pop', 'hip hop', 'workout'],
            'dreamy': ['dream pop', 'shoegaze', 'ambient', 'indie', 'ethereal'],
            'dark': ['dark ambient', 'post-punk', 'gothic', 'industrial', 'black metal'],
            
            # Погода и время
            'rainy': ['ambient', 'post-rock', 'dream pop', 'indie', 'melancholic'],
            'sunny': ['pop', 'reggae', 'indie pop', 'surf rock', 'tropical house'],
            'winter': ['folk', 'ambient', 'post-rock', 'indie', 'classical'],
            'summer': ['pop', 'reggae', 'tropical house', 'indie pop', 'surf'],
            'morning': ['folk', 'acoustic', 'indie', 'coffee shop', 'ambient'],
            'night': ['electronic', 'ambient', 'chill', 'r&b', 'jazz'],
            
            # Социальный контекст
            'party': ['electronic', 'dance', 'house', 'pop', 'hip hop', 'disco'],
            'study': ['ambient', 'classical', 'lo-fi', 'post-rock', 'minimal'],
            'workout': ['electronic', 'rock', 'metal', 'hip hop', 'fitness'],
            'driving': ['rock', 'electronic', 'pop', 'alternative', 'classic rock'],
            'focus': ['ambient', 'minimal', 'classical', 'post-rock', 'concentration']
        }
    
    def map_mood_to_genres(self, mood_tags: List[str], user_genres: List[str]) -> List[str]:
        """
        Маппит mood теги к жанрам с учетом предпочтений пользователя.
        
        Args:
            mood_tags: Теги настроения из MoodParameters
            user_genres: Любимые жанры пользователя
            
        Returns:
            Список жанров, соответствующих настроению
        """
        logger.info(f"🔍 [MOOD_MAPPING] Mapping mood tags {mood_tags} to genres")
        
        # Собираем все жанры из mood тегов
        mood_genres = set()
        for tag in mood_tags:
            tag_lower = tag.lower().strip()
            if tag_lower in self.mood_mappings:
                mood_genres.update(self.mood_mappings[tag_lower])
                logger.info(f"🔍 [MOOD_MAPPING] Tag '{tag_lower}' mapped to: {self.mood_mappings[tag_lower]}")
        
        # Если нет точного совпадения, ищем частичные совпадения
        if not mood_genres:
            for tag in mood_tags:
                tag_lower = tag.lower().strip()
                for mood_key, genres in self.mood_mappings.items():
                    if tag_lower in mood_key or mood_key in tag_lower:
                        mood_genres.update(genres)
                        logger.info(f"🔍 [MOOD_MAPPING] Partial match '{tag_lower}' -> '{mood_key}': {genres}")
        
        # Если пользователь имеет предпочтения, находим пересечения
        if user_genres:
            # Прямые совпадения имеют высший приоритет
            direct_matches = [genre for genre in mood_genres if genre in user_genres]
            
            # Частичные совпадения (например, "electronic" и "electronic dance")
            partial_matches = []
            for mood_genre in mood_genres:
                for user_genre in user_genres:
                    if (mood_genre in user_genre or user_genre in mood_genre) and mood_genre not in direct_matches:
                        partial_matches.append(mood_genre)
            
            # Комбинируем результаты
            final_genres = direct_matches + partial_matches + list(mood_genres)
            
            logger.info(f"🔍 [MOOD_MAPPING] Direct matches: {direct_matches}")
            logger.info(f"🔍 [MOOD_MAPPING] Partial matches: {partial_matches}")
        else:
            final_genres = list(mood_genres)
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_genres = []
        for genre in final_genres:
            if genre not in seen:
                unique_genres.append(genre)
                seen.add(genre)
        
        # Ограничиваем количество жанров для Spotify API (максимум 5)
        result = unique_genres[:5]
        
        logger.info(f"🔍 [MOOD_MAPPING] Final mapped genres: {result}")
        return result


class PersonalizedRecommendationEngine:
    """Генерирует персонализированные рекомендации через Spotify Recommendations API."""
    
    def __init__(self, spotify_client):
        self.spotify_client = spotify_client
        self.mood_mapper = MoodToGenreMapper()
    
    def generate_recommendations(
        self, 
        mood_params: MoodParameters, 
        user_profile: UserProfile, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Генерирует персонализированные рекомендации без audio_features.
        
        Args:
            mood_params: Параметры настроения
            user_profile: Профиль пользователя
            limit: Максимальное количество треков
            
        Returns:
            Список рекомендованных треков
        """
        logger.info(f"🔍 [RECOMMENDATIONS] Generating {limit} personalized recommendations")
        
        if not hasattr(self.spotify_client, 'client') or not self.spotify_client.client:
            logger.error("❌ [RECOMMENDATIONS] No Spotify client available")
            return []
        
        sp = self.spotify_client.client
        all_recommendations = []
        
        try:
            # 1. Адаптируем mood под пользователя
            adapted_params = self._adapt_mood_to_user(mood_params, user_profile)
            logger.info(f"🔍 [RECOMMENDATIONS] Adapted mood genres: {adapted_params['mood_genres']}")
            
            # 2. Стратегия 1: На основе топ артистов пользователя
            if user_profile.favorite_artist_ids:
                artist_recs = self._get_artist_based_recommendations(
                    sp, adapted_params, user_profile, limit=40
                )
                all_recommendations.extend(artist_recs)
                logger.info(f"🔍 [RECOMMENDATIONS] Artist-based: {len(artist_recs)} tracks")
            
            # 3. Стратегия 2: На основе любимых треков
            if user_profile.top_track_ids:
                track_recs = self._get_track_based_recommendations(
                    sp, adapted_params, user_profile, limit=30
                )
                all_recommendations.extend(track_recs)
                logger.info(f"🔍 [RECOMMENDATIONS] Track-based: {len(track_recs)} tracks")
            
            # 4. Стратегия 3: Чисто жанровые рекомендации под mood
            genre_recs = self._get_genre_based_recommendations(
                sp, adapted_params, user_profile, limit=30
            )
            all_recommendations.extend(genre_recs)
            logger.info(f"🔍 [RECOMMENDATIONS] Genre-based: {len(genre_recs)} tracks")
            
            # 5. Стратегия 4: Популярные треки в жанрах (fallback)
            if len(all_recommendations) < limit // 2:
                popular_recs = self._get_popular_recommendations(
                    sp, adapted_params, user_profile, limit=30
                )
                all_recommendations.extend(popular_recs)
                logger.info(f"🔍 [RECOMMENDATIONS] Popular fallback: {len(popular_recs)} tracks")
            
            # 6. Объединение и дедупликация
            final_recs = self._combine_and_deduplicate(all_recommendations)
            
            logger.info(f"🔍 [RECOMMENDATIONS] Total generated: {len(final_recs)} unique tracks")
            return final_recs[:limit]
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error generating recommendations: {e}")
            return []
    
    def _adapt_mood_to_user(self, mood_params: MoodParameters, user_profile: UserProfile) -> Dict[str, Any]:
        """Адаптирует mood параметры под предпочтения пользователя."""
        
        # Маппим mood теги к жанрам с учетом пользователя
        mood_genres = self.mood_mapper.map_mood_to_genres(
            mood_params.mood_tags, 
            user_profile.favorite_genres
        )
        
        # Если мало жанров от mood, добавляем пользовательские
        if len(mood_genres) < 3 and user_profile.favorite_genres:
            for genre in user_profile.favorite_genres[:3]:
                if genre not in mood_genres:
                    mood_genres.append(genre)
        
        # Адаптируем popularity под пользователя
        target_popularity = user_profile.preferred_popularity
        
        # Если есть popularity_range в mood_params, учитываем его
        if hasattr(mood_params, 'popularity_range') and mood_params.popularity_range:
            min_pop, max_pop = mood_params.popularity_range
            # Находим пересечение предпочтений пользователя и mood
            target_popularity = max(min_pop, min(max_pop, target_popularity))
        
        return {
            'mood_genres': mood_genres,
            'target_popularity': target_popularity,
            'popularity_range': [max(0, target_popularity - 25), min(100, target_popularity + 25)]
        }
    
    def _get_artist_based_recommendations(
        self, 
        sp, 
        adapted_params: Dict[str, Any], 
        user_profile: UserProfile, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Рекомендации на основе топ артистов пользователя."""
        try:
            # Берем топ 2-3 артиста как seeds
            seed_artists = user_profile.favorite_artist_ids[:3]
            seed_genres = adapted_params['mood_genres'][:2]  # Оставляем место для артистов
            
            recommendations = sp.recommendations(
                seed_artists=seed_artists,
                seed_genres=seed_genres,
                limit=limit,
                target_popularity=int(adapted_params['target_popularity']),
                market='US'
            )
            
            tracks = []
            for track in recommendations.get('tracks', []):
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in track['artists']],
                    'uri': track['uri'],
                    'popularity': track.get('popularity', 50),
                    'discovery_method': 'artist_based',
                    'preview_url': track.get('preview_url'),
                    'external_urls': track.get('external_urls', {})
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error in artist-based recommendations: {e}")
            return []
    
    def _get_track_based_recommendations(
        self, 
        sp, 
        adapted_params: Dict[str, Any], 
        user_profile: UserProfile, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Рекомендации на основе любимых треков пользователя."""
        try:
            # Берем топ 2-3 трека как seeds
            seed_tracks = user_profile.top_track_ids[:3]
            seed_genres = adapted_params['mood_genres'][:2]
            
            recommendations = sp.recommendations(
                seed_tracks=seed_tracks,
                seed_genres=seed_genres,
                limit=limit,
                target_popularity=int(adapted_params['target_popularity']),
                market='US'
            )
            
            tracks = []
            for track in recommendations.get('tracks', []):
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in track['artists']],
                    'uri': track['uri'],
                    'popularity': track.get('popularity', 50),
                    'discovery_method': 'track_based',
                    'preview_url': track.get('preview_url'),
                    'external_urls': track.get('external_urls', {})
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error in track-based recommendations: {e}")
            return []
    
    def _get_genre_based_recommendations(
        self, 
        sp, 
        adapted_params: Dict[str, Any], 
        user_profile: UserProfile, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Рекомендации на основе жанров mood."""
        try:
            # Используем только жанры как seeds
            seed_genres = adapted_params['mood_genres'][:5]
            
            if not seed_genres:
                logger.warning("🔍 [RECOMMENDATIONS] No genres for genre-based recommendations")
                return []
            
            recommendations = sp.recommendations(
                seed_genres=seed_genres,
                limit=limit,
                target_popularity=int(adapted_params['target_popularity']),
                market='US'
            )
            
            tracks = []
            for track in recommendations.get('tracks', []):
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in track['artists']],
                    'uri': track['uri'],
                    'popularity': track.get('popularity', 50),
                    'discovery_method': 'genre_based',
                    'preview_url': track.get('preview_url'),
                    'external_urls': track.get('external_urls', {})
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error in genre-based recommendations: {e}")
            return []
    
    def _get_popular_recommendations(
        self, 
        sp, 
        adapted_params: Dict[str, Any], 
        user_profile: UserProfile, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback рекомендации популярных треков в жанрах."""
        try:
            # Используем только жанры, но с высокой популярностью
            seed_genres = adapted_params['mood_genres'][:5]
            
            if not seed_genres:
                # Если нет mood жанров, используем пользовательские
                seed_genres = user_profile.favorite_genres[:3]
            
            if not seed_genres:
                logger.warning("🔍 [RECOMMENDATIONS] No genres for popular recommendations")
                return []
            
            recommendations = sp.recommendations(
                seed_genres=seed_genres,
                limit=limit,
                min_popularity=60,  # Только популярные треки
                market='US'
            )
            
            tracks = []
            for track in recommendations.get('tracks', []):
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in track['artists']],
                    'uri': track['uri'],
                    'popularity': track.get('popularity', 50),
                    'discovery_method': 'popular_fallback',
                    'preview_url': track.get('preview_url'),
                    'external_urls': track.get('external_urls', {})
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error in popular recommendations: {e}")
            return []
    
    def _combine_and_deduplicate(self, track_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Объединяет и дедуплицирует треки из разных источников."""
        seen_ids = set()
        combined_tracks = []
        
        # Плоский список всех треков
        all_tracks = []
        for track_list in track_lists:
            all_tracks.extend(track_list)
        
        # Дедупликация
        for track in all_tracks:
            if track['id'] not in seen_ids:
                combined_tracks.append(track)
                seen_ids.add(track['id'])
        
        logger.info(f"🔍 [RECOMMENDATIONS] Combined {len(all_tracks)} -> {len(combined_tracks)} unique tracks")
        return combined_tracks


class SmartTrackFilter:
    """Умная фильтрация и ранжирование треков без audio_features."""
    
    def filter_and_rank_tracks(
        self, 
        tracks: List[Dict[str, Any]], 
        mood_params: MoodParameters, 
        user_profile: UserProfile, 
        target_count: int = 20
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Фильтрует и ранжирует треки по персонализированному score.
        
        Args:
            tracks: Список треков для фильтрации
            mood_params: Параметры настроения
            user_profile: Профиль пользователя
            target_count: Целевое количество треков
            
        Returns:
            Список (трек, score) отсортированный по убыванию score
        """
        logger.info(f"🔍 [TRACK_FILTER] Filtering {len(tracks)} tracks for user profile")
        
        scored_tracks = []
        for track in tracks:
            score = self._calculate_personalized_score(track, mood_params, user_profile)
            
            # Минимальный порог для включения в результат
            if score > 0.3:
                scored_tracks.append((track, score))
        
        logger.info(f"🔍 [TRACK_FILTER] {len(scored_tracks)} tracks passed minimum score threshold")
        
        # Сортировка по score
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        
        # Применение разнообразия (max 2-3 трека от артиста)
        diversified = self._apply_artist_diversity(scored_tracks, max_per_artist=2)
        
        logger.info(f"🔍 [TRACK_FILTER] Final result: {len(diversified)} diversified tracks")
        
        # Логирование топ треков для диагностики
        if diversified:
            logger.info(f"🔍 [TRACK_FILTER] Top 5 tracks:")
            for i, (track, score) in enumerate(diversified[:5]):
                artists = ', '.join([a.get('name', 'Unknown') for a in track.get('artists', [])])
                logger.info(f"🔍 [TRACK_FILTER]   {i+1}. '{track.get('name', 'Unknown')}' by {artists} (score: {score:.3f})")
        
        return diversified[:target_count]
    
    def _calculate_personalized_score(
        self, 
        track: Dict[str, Any], 
        mood_params: MoodParameters, 
        user_profile: UserProfile
    ) -> float:
        """Рассчитывает персонализированный score трека без audio_features."""
        score = 0.5  # Базовый score
        
        try:
            # 1. Бонус за знакомых артистов (важный фактор персонализации)
            artist_ids = [a.get('id', '') for a in track.get('artists', [])]
            artist_bonus = 0
            for artist_id in artist_ids:
                if artist_id in user_profile.favorite_artist_ids:
                    # Больший бонус для топовых артистов
                    artist_index = user_profile.favorite_artist_ids.index(artist_id)
                    artist_bonus += 0.3 * (1.0 - artist_index / len(user_profile.favorite_artist_ids))
            
            score += min(0.4, artist_bonus)  # Максимум 0.4 за артистов
            
            # 2. Бонус за соответствие popularity preferences
            track_popularity = track.get('popularity', 50)
            user_popularity = user_profile.preferred_popularity
            pop_diff = abs(track_popularity - user_popularity)
            
            if pop_diff <= 10:
                score += 0.2
            elif pop_diff <= 20:
                score += 0.1
            elif pop_diff <= 30:
                score += 0.05
            
            # 3. Бонус за жанровое соответствие
            track_genres = self._get_track_genres(track, user_profile)
            user_genres_set = set(user_profile.favorite_genres)
            
            genre_matches = len(set(track_genres) & user_genres_set)
            score += genre_matches * 0.08  # До 0.4 за жанры
            
            # 4. Бонус за discovery method (некоторые методы лучше)
            discovery_method = track.get('discovery_method', 'unknown')
            method_bonuses = {
                'artist_based': 0.1,
                'track_based': 0.12,
                'genre_based': 0.08,
                'popular_fallback': 0.05
            }
            score += method_bonuses.get(discovery_method, 0)
            
            # 5. Штраф за слишком низкую или высокую популярность
            if track_popularity < 10:
                score -= 0.1  # Слишком неизвестные
            elif track_popularity > 90:
                score -= 0.05  # Слишком мейнстрим для некоторых пользователей
            
            # 6. Бонус за название и мета-информацию (простая эвристика)
            track_name = track.get('name', '').lower()
            mood_keywords = [tag.lower() for tag in mood_params.mood_tags]
            
            name_match_bonus = 0
            for keyword in mood_keywords:
                if keyword in track_name:
                    name_match_bonus += 0.02
            
            score += min(0.1, name_match_bonus)
            
            # Ограничиваем score диапазоном [0, 1]
            final_score = max(0.0, min(1.0, score))
            
            return final_score
            
        except Exception as e:
            logger.warning(f"🔍 [TRACK_FILTER] Error calculating score for track {track.get('id', 'unknown')}: {e}")
            return 0.3  # Fallback score
    
    def _get_track_genres(self, track: Dict[str, Any], user_profile: UserProfile) -> List[str]:
        """Получает жанры трека из информации об артистах."""
        track_genres = []
        
        try:
            # Если у нас есть информация об артистах с жанрами
            for artist in track.get('artists', []):
                artist_id = artist.get('id')
                
                # Ищем артиста в профиле пользователя
                for user_artist in user_profile.favorite_artists:
                    if user_artist.get('id') == artist_id:
                        track_genres.extend(user_artist.get('genres', []))
                        break
            
            # Если не нашли точных жанров, используем простую эвристику
            if not track_genres:
                # Простая эвристика на основе названия артиста/трека
                artist_names = [a.get('name', '').lower() for a in track.get('artists', [])]
                track_name = track.get('name', '').lower()
                
                # Некоторые ключевые слова могут намекать на жанр
                genre_hints = {
                    'electronic': ['dj', 'remix', 'mix', 'beats'],
                    'rock': ['band', 'guitar', 'rock'],
                    'pop': ['pop', 'hit', 'chart'],
                    'hip hop': ['rap', 'hip', 'hop', 'trap'],
                    'jazz': ['jazz', 'blues', 'swing'],
                    'classical': ['symphony', 'orchestra', 'classical']
                }
                
                for genre, keywords in genre_hints.items():
                    for keyword in keywords:
                        if any(keyword in name for name in artist_names) or keyword in track_name:
                            track_genres.append(genre)
                            break
            
            return track_genres[:5]  # Ограничиваем количество
            
        except Exception as e:
            logger.warning(f"🔍 [TRACK_FILTER] Error getting track genres: {e}")
            return []
    
    def _apply_artist_diversity(
        self, 
        scored_tracks: List[Tuple[Dict[str, Any], float]], 
        max_per_artist: int = 2
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Применяет разнообразие по артистам."""
        artist_counts = defaultdict(int)
        diversified_tracks = []
        
        for track, score in scored_tracks:
            # Получаем ID первого артиста
            artist_ids = [a.get('id', '') for a in track.get('artists', [])]
            main_artist_id = artist_ids[0] if artist_ids else 'unknown'
            
            # Проверяем, не превышен ли лимит для этого артиста
            if artist_counts[main_artist_id] < max_per_artist:
                diversified_tracks.append((track, score))
                artist_counts[main_artist_id] += 1
        
        logger.info(f"🔍 [TRACK_FILTER] Applied artist diversity: {len(scored_tracks)} -> {len(diversified_tracks)} tracks")
        return diversified_tracks


class PersonalizedPlaylistEngine:
    """Главный класс для создания персонализированных плейлистов без audio_features."""
    
    def __init__(self, spotify_client):
        self.spotify_client = spotify_client
        self.profile_analyzer = UserMusicProfile()
        self.mood_mapper = MoodToGenreMapper()
        self.recommendation_engine = PersonalizedRecommendationEngine(spotify_client)
        self.track_filter = SmartTrackFilter()
    
    def create_personalized_playlist(
        self, 
        user_id: str, 
        mood_params: MoodParameters, 
        target_length: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Главный метод создания персонализированного плейлиста без audio_features.
        
        Args:
            user_id: ID пользователя
            mood_params: Параметры настроения
            target_length: Желаемая длина плейлиста
            
        Returns:
            Список треков для плейлиста
        """
        logger.info(f"🔍 [PERSONALIZED_ENGINE] Creating personalized playlist for user {user_id}")
        logger.info(f"🔍 [PERSONALIZED_ENGINE] Target length: {target_length}")
        logger.info(f"🔍 [PERSONALIZED_ENGINE] Mood tags: {mood_params.mood_tags}")
        
        try:
            # 1. Анализ пользователя
            logger.info(f"🔍 [PERSONALIZED_ENGINE] Step 1: Analyzing user preferences...")
            user_profile = self.profile_analyzer.analyze_user_preferences(user_id, self.spotify_client)
            
            if not user_profile.favorite_genres and not user_profile.favorite_artists:
                logger.warning(f"🔍 [PERSONALIZED_ENGINE] Limited user data, creating basic profile")
            else:
                logger.info(f"🔍 [PERSONALIZED_ENGINE] User profile: {len(user_profile.favorite_genres)} genres, "
                           f"{user_profile.preferred_popularity:.0f} avg popularity")
            
            # 2. Генерация рекомендаций
            logger.info(f"🔍 [PERSONALIZED_ENGINE] Step 2: Generating recommendations...")
            recommendations = self.recommendation_engine.generate_recommendations(
                mood_params, user_profile, limit=target_length * 8  # Получаем больше для лучшей фильтрации
            )
            
            if not recommendations:
                logger.error(f"❌ [PERSONALIZED_ENGINE] No recommendations generated!")
                return []
            
            logger.info(f"🔍 [PERSONALIZED_ENGINE] Generated {len(recommendations)} recommendations")
            
            # 3. Умная фильтрация и ранжирование
            logger.info(f"🔍 [PERSONALIZED_ENGINE] Step 3: Filtering and ranking...")
            filtered_tracks = self.track_filter.filter_and_rank_tracks(
                recommendations, mood_params, user_profile, target_length
            )
            
            if not filtered_tracks:
                logger.error(f"❌ [PERSONALIZED_ENGINE] All tracks filtered out!")
                # Возвращаем хотя бы часть рекомендаций без фильтрации
                return recommendations[:target_length]
            
            final_tracks = [track for track, score in filtered_tracks]
            
            logger.info(f"✅ [PERSONALIZED_ENGINE] Success: {len(final_tracks)} high-quality personalized tracks")
            
            # Логирование финальной статистики
            methods = defaultdict(int)
            for track in final_tracks:
                method = track.get('discovery_method', 'unknown')
                methods[method] += 1
            
            logger.info(f"🔍 [PERSONALIZED_ENGINE] Discovery methods: {dict(methods)}")
            
            return final_tracks
            
        except Exception as e:
            logger.error(f"❌ [PERSONALIZED_ENGINE] Critical error in playlist creation: {e}")
            return [] 