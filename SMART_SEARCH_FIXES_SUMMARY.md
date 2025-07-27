# 🔧 SmartSearchStrategy - Исправления совместимости

## ✅ Исправления выполнены

### 1️⃣ **MoodParameters structure fix**
**Было:**
```python
# Прямой доступ к flat структуре
mood_params.valence
mood_params.primary_genres  
mood_params.mood_tags
```

**Стало:**
```python
# Поддержка nested структуры с fallback
mood_params.audio_features.valence      # или mood_params.valence (fallback)
mood_params.preferences.genres.primary  # или mood_params.primary_genres (fallback)
mood_params.context.mood_tags           # или mood_params.mood_tags (fallback)
```

### 2️⃣ **SpotifyClient integration**
**Было:**
```python
self.client = spotify_client.client if spotify_client else None
```

**Стало:**
```python
# Robust client detection with multiple fallbacks
if spotify_client:
    if hasattr(spotify_client, 'client') and spotify_client.client:
        self.client = spotify_client.client
    elif hasattr(spotify_client, 'sp') and spotify_client.sp:
        self.client = spotify_client.sp  # Alternative attribute
    else:
        self.client = spotify_client  # Direct spotipy instance
else:
    self.client = None
```

### 3️⃣ **Market configuration**
**Было:**
```python
def search_mood_tracks(self, mood_params, total_limit=200):
    # Hardcoded market='US' in API calls
```

**Стало:**
```python
def search_mood_tracks(self, mood_params, total_limit=200, market='US'):
    # Configurable market parameter passed to all APIs
    results = self.client.search(q=query, market=market)
    recommendations = self.client.recommendations(market=market, ...)
    playlist_tracks = self.client.playlist_tracks(id, market=market)
```

### 4️⃣ **Safe attribute access**
**Добавлены helper функции:**
```python
def _get_audio_features(self, mood_params) -> Dict[str, Any]:
    """Get audio features with nested structure support."""
    if hasattr(mood_params, 'audio_features'):
        af = mood_params.audio_features
        return {
            'valence': getattr(af, 'valence', 0.5),
            'energy': getattr(af, 'energy', 0.5),
            # ... other features with defaults
        }
    else:
        # Fallback to flat structure
        return {
            'valence': getattr(mood_params, 'valence', 0.5),
            # ... flat structure access
        }

def _get_context_info(self, mood_params) -> Dict[str, Any]:
    """Get context with nested structure support."""
    # Similar pattern for context.mood_tags, context.activity, etc.

def _get_preferences(self, mood_params) -> Dict[str, Any]:
    """Get preferences with nested structure support."""
    # Handles preferences.genres.primary, preferences.popularity_range, etc.
```

---

## 🔧 Архитектурные улучшения

### Helper функции с fallback логикой:

| Функция | Назначение | Nested доступ | Flat fallback |
|---------|------------|---------------|---------------|
| `_get_audio_features()` | Audio параметры | `mood_params.audio_features.valence` | `mood_params.valence` |
| `_get_context_info()` | Контекст | `mood_params.context.mood_tags` | `mood_params.mood_tags` |
| `_get_preferences()` | Предпочтения | `mood_params.preferences.genres.primary` | `mood_params.primary_genres` |

### Безопасный доступ с defaults:

```python
# Если nested структура неполная, используются разумные defaults
audio_features = {
    'valence': getattr(af, 'valence', 0.5),      # Default: нейтральное настроение
    'energy': getattr(af, 'energy', 0.5),        # Default: умеренная энергия
    'tempo': getattr(af, 'tempo', 120),          # Default: 120 BPM
    # ... другие параметры с defaults
}
```

---

## 🧪 Тестирование

### Новый тест файл: `test_smart_search_fixed.py`
```bash
python test_smart_search_fixed.py

# Ожидаемый результат:
# 🧪 Testing Nested Structure Compatibility
# 📋 Testing Helper Functions
#    Audio features: valence=0.8, energy=0.7
#    Context: tags=['happy', 'energetic'], activity=working
#    Preferences: primary_genres=['pop', 'electronic']
#    ✅ Helper functions work correctly with nested structure
# 
# 🌍 Testing Market Parameter Support
# 🔄 Testing Fallback Compatibility  
# 🎯 Testing Combined Search with Market
# 🛡️ Testing Safe Attribute Access
# 
# 🎉 All compatibility tests passed!
```

### Тестовые сценарии:
- ✅ **Nested structure**: полная поддержка `mood_params.audio_features.valence`
- ✅ **Flat structure**: fallback к `mood_params.valence`
- ✅ **Market parameter**: передача во все API вызовы
- ✅ **Safe access**: обработка отсутствующих полей
- ✅ **SpotifyClient detection**: множественные fallback варианты

---

## 📊 Структуры данных

### Поддерживаемые форматы MoodParameters:

#### 1. Nested структура (предпочтительно):
```python
mood_params = MoodParameters(
    audio_features=AudioFeatures(
        valence=0.7, energy=0.6, tempo=120
    ),
    context=Context(
        mood_tags=["happy"], activity="working"
    ),
    preferences=Preferences(
        genres=Genres(primary=["pop"], secondary=["dance"]),
        popularity_range=[40, 80]
    )
)
```

#### 2. Flat структура (fallback):
```python
mood_params = MoodParameters(
    valence=0.7, energy=0.6, tempo=120,
    mood_tags=["happy"], activity="working",
    primary_genres=["pop"], secondary_genres=["dance"],
    popularity_range=[40, 80]
)
```

#### 3. Смешанная структура (частично nested):
```python
mood_params = MoodParameters(
    audio_features=AudioFeatures(valence=0.7),  # Nested audio
    mood_tags=["happy"],                         # Flat context  
    primary_genres=["pop"]                       # Flat preferences
)
# Все будет работать корректно с fallback логикой
```

---

## 🚀 Использование в коде

### Обновленная интеграция:
```python
from moodtape_core.smart_search import create_smart_search_strategy

# Создание с market параметром
smart_search = create_smart_search_strategy(spotify_client)

# Использование с market и nested структурой
tracks = smart_search.search_mood_tracks(
    mood_params,           # Любая поддерживаемая структура
    total_limit=200,       # Лимит треков
    market='RU'            # Configurable market
)

# Аналитика (без изменений)
analytics = smart_search.get_search_analytics(tracks)
```

### В playlist_builder.py:
```python
# Обновленный метод с market support
def _get_mood_based_tracks_with_smart_search(self, mood_params, limit, market='US'):
    smart_search = create_smart_search_strategy(self.spotify_client)
    return smart_search.search_mood_tracks(mood_params, total_limit=limit * 10, market=market)
```

---

## 🔄 Обратная совместимость

### 100% совместимость с:
- ✅ **Существующим кодом**: все старые вызовы работают
- ✅ **Flat MoodParameters**: fallback к прямому доступу
- ✅ **Любыми SpotifyClient**: множественные варианты обнаружения  
- ✅ **Всеми market кодами**: 'US', 'RU', 'GB', 'DE', и др.

### Graceful degradation:
- ❌ **Нет nested структуры** → используется flat доступ
- ❌ **Нет audio_features** → defaults (valence=0.5, energy=0.5)
- ❌ **Нет SpotifyClient.client** → пробует .sp или direct instance
- ❌ **Нет market параметра** → default 'US'

---

**Результат**: SmartSearchStrategy теперь полностью совместима с вашей nested структурой данных и безопасно работает со всеми вариантами MoodParameters! 🎵✨ 