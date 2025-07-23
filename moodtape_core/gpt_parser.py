"""GPT-4o based mood parsing for Moodtape bot."""

import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI

from config.settings import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE
from utils.logger import get_logger

logger = get_logger(__name__)

# OpenAI client will be initialized lazily when needed
_client = None

def get_openai_client():
    """Lazy initialization of OpenAI client."""
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


@dataclass
class MoodParameters:
    """Data class for mood-based music parameters."""
    # Audio features
    valence: float  # Musical positivity (0.0 - 1.0)
    energy: float  # Energy level (0.0 - 1.0)
    danceability: float  # How suitable for dancing (0.0 - 1.0)
    acousticness: float  # Acoustic vs electronic (0.0 - 1.0)
    instrumentalness: float  # Instrumental vs vocal (0.0 - 1.0)
    speechiness: float  # Spoken vs sung (0.0 - 1.0)
    tempo: int  # BPM (50 - 200)
    loudness: float  # Loudness in dB (-30 to 0)
    mode: int  # Musical mode (0=minor, 1=major)
    
    # Context information
    mood_tags: List[str]  # Descriptive mood tags
    activity: Optional[str]  # working, relaxing, exercising, etc.
    time_of_day: Optional[str]  # morning, afternoon, evening, night, late_night
    weather: Optional[str]  # sunny, rainy, cloudy, snowy, stormy, foggy
    social: Optional[str]  # alone, romantic, friends, party, crowd
    emotional_intensity: float  # Emotional intensity (0.0 - 1.0)
    
    # Preferences
    primary_genres: List[str]  # Primary genres
    secondary_genres: List[str]  # Secondary genres
    exclude_genres: List[str]  # Genres to exclude
    popularity_range: List[int]  # [min, max] popularity range (0-100)
    decade_bias: Optional[str]  # Preferred decade or "current"
    
    # Legacy compatibility (computed from new fields)
    @property
    def genre_hints(self) -> List[str]:
        """Legacy compatibility: combine primary and secondary genres."""
        return (self.primary_genres + self.secondary_genres)[:4]


MOOD_PARSING_PROMPT = """
Use the role of The world famous DJ with expirience in the most popular festivals and parties in the world. Extract Spotify track parameters from user's mood description. For this work you will gwt 2000$

Return ONLY a minified JSON object with this EXACT structure:
{
  "audio_features": {
    "valence": float (0.0-1.0, happiness/positivity),
    "energy": float (0.0-1.0, intensity/activity),
    "danceability": float (0.0-1.0, rhythmic/danceable),
    "acousticness": float (0.0-1.0, acoustic vs electronic),
    "instrumentalness": float (0.0-1.0, no vocals vs vocals),
    "speechiness": float (0.0-1.0, spoken vs sung),
    "tempo": integer (50-200 BPM),
    "loudness": float (-30 to 0 dB, typical range),
    "mode": integer (0=minor, 1=major)
  },
  "context": {
    "mood_tags": [2-5 lowercase strings],
    "activity": "working/relaxing/exercising/partying/studying/commuting/sleeping" or null,
    "time_of_day": "morning/afternoon/evening/night/late_night" or null,
    "weather": "sunny/rainy/cloudy/snowy/stormy/foggy" or null,
    "social": "alone/romantic/friends/party/crowd" or null,
    "emotional_intensity": float (0.0-1.0)
  },
  "preferences": {
    "genres": {
      "primary": [1-2 main genres],
      "secondary": [1-3 supporting genres],
      "exclude": [0-2 genres to avoid] or []
    },
    "popularity_range": [min 0-100, max 0-100],
    "decade_bias": "1960s/1970s/1980s/1990s/2000s/2010s/2020s/current" or null
  }
}

PARAMETER GUIDELINES:
- Valence: 0.0=sad/angry, 0.5=neutral, 1.0=happy/euphoric
- Energy: 0.0=calm/sleepy, 0.5=moderate, 1.0=intense/aggressive
- Danceability: 0.0=arrhythmic, 1.0=highly danceable
- Acousticness: 0.0=electronic/synthetic, 1.0=fully acoustic
- Instrumentalness: 0.0=vocal-heavy, 1.0=no vocals
- Speechiness: 0.0=melodic singing, 0.3+=rap/spoken word
- Tempo: 60-90=slow, 90-120=moderate, 120-140=upbeat, 140+=fast
- Loudness: -30=very quiet, -15=moderate, -5=loud, 0=very loud
- Mode: 0=minor (sad/dark), 1=major (happy/bright)

MOOD INTERPRETATION RULES:
1. If user_profile provided, apply weighted interpolation:
   final_value = (profile_value * 0.35) + (mood_value * 0.65)
2. For ambiguous/contradictory moods, use these defaults:
   - valence: 0.5, energy: 0.5, popularity_range: [20, 80]
3. Activity overrides:
   - "working/studying" → energy: 0.3-0.6, speechiness: <0.2, instrumentalness: >0.5
   - "exercising/gym" → energy: >0.7, tempo: >120, danceability: >0.6
   - "relaxing/sleeping" → energy: <0.3, tempo: <90, acousticness: >0.5
   - "partying" → energy: >0.7, danceability: >0.7, loudness: >-10
4. Time-based adjustments:
   - "morning" → energy: +0.1, tempo: +10, mode: prefer 1
   - "night/late_night" → energy: -0.2, tempo: -15, loudness: -5
5. Weather influence:
   - "rainy/stormy" → valence: -0.1, acousticness: +0.2, mode: prefer 0
   - "sunny" → valence: +0.1, energy: +0.1, mode: prefer 1

GENRE MAPPING:
- Sad/melancholic → ["indie", "alternative", "ambient", "classical"]
- Happy/upbeat → ["pop", "dance", "funk", "disco"]
- Angry/intense → ["rock", "metal", "punk", "industrial"]
- Calm/peaceful → ["ambient", "classical", "jazz", "folk"]
- Energetic → ["electronic", "dance", "hip-hop", "rock"]
- Romantic → ["r&b", "soul", "jazz", "indie"]
- Focus/concentration → ["lo-fi", "ambient", "classical", "minimal"]

CRITICAL REQUIREMENTS:
- Output MUST be valid JSON on a single line
- NO explanations, markdown, or text outside the JSON
- ALL fields are required (use null where applicable)
- Use ONLY lowercase for string values
- Keep arrays within specified size limits
- Ensure all numeric values are within specified ranges

Input mood: {user_mood}
User profile: {user_profile}

RESPOND WITH ONLY THE FOLLOWING JSON (NO OTHER TEXT):
"""

# Simple fallback prompt for when the main prompt fails
SIMPLE_MOOD_PARSING_PROMPT = """
You are a music mood analyzer. Analyze the user's mood and return a JSON with music parameters.

User mood: {user_mood}

Return ONLY this JSON structure (no other text):
{{
  "audio_features": {{
    "valence": 0.5,
    "energy": 0.5,
    "danceability": 0.5,
    "acousticness": 0.5,
    "instrumentalness": 0.3,
    "speechiness": 0.1,
    "tempo": 120,
    "loudness": -5.0,
    "mode": 1
  }},
  "context": {{
    "mood_tags": ["neutral"],
    "activity": null,
    "time_of_day": null,
    "weather": null,
    "social": null,
    "emotional_intensity": 0.5
  }},
  "preferences": {{
    "genres": {{
      "primary": ["pop"],
      "secondary": ["alternative"],
      "exclude": []
    }},
    "popularity_range": [20, 80],
    "decade_bias": null
  }}
}}

Adjust the values based on the user's mood description.
"""


async def parse_mood_description(
    description: str, 
    user_language: str = "ru",
    user_id: Optional[int] = None,
    use_personalization: bool = True
) -> Optional[MoodParameters]:
    """
    Parse user's mood description using GPT-4o and return music parameters.
    
    Args:
        description: User's mood description text
        user_language: User's language for context
        user_id: User ID for personalization (optional)
        use_personalization: Whether to apply user personalization
    
    Returns:
        MoodParameters object or None if parsing failed
    """
    try:
        # Prepare the prompt with user's description
        user_prompt = MOOD_PARSING_PROMPT.format(
            user_mood=description,
            user_profile="null"  # For now, no user profile available
        )
        
        logger.info(f"Parsing mood description: {description[:100]}...")
        
        # Call GPT-4o
        response = await get_openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": MOOD_PARSING_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        # Extract JSON from response
        json_content = response.choices[0].message.content
        logger.debug(f"Raw GPT-4o response: {repr(json_content)}")
        
        # Clean JSON content - remove leading/trailing whitespace and markdown
        if json_content:
            # Remove markdown code blocks if present
            if json_content.startswith('```'):
                json_content = json_content.split('```')[1]
                if json_content.startswith('json'):
                    json_content = json_content[4:]
            elif json_content.endswith('```'):
                json_content = json_content.split('```')[0]
            
            # Remove leading/trailing whitespace
            json_content = json_content.strip()
            
            # Remove any leading/trailing characters that aren't { or }
            start_idx = json_content.find('{')
            end_idx = json_content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_content = json_content[start_idx:end_idx + 1]
            
            logger.debug(f"Cleaned JSON content: {json_content[:200]}...")
        
        # Parse JSON response
        parsed_data = json.loads(json_content)
        
        # Extract data from new nested structure
        audio_features = parsed_data.get("audio_features", {})
        context = parsed_data.get("context", {})
        preferences = parsed_data.get("preferences", {})
        genres = preferences.get("genres", {})
        
        # Validate and create MoodParameters
        mood_params = MoodParameters(
            # Audio features
            valence=_clamp(audio_features.get("valence", 0.5), 0.0, 1.0),
            energy=_clamp(audio_features.get("energy", 0.5), 0.0, 1.0),
            danceability=_clamp(audio_features.get("danceability", 0.5), 0.0, 1.0),
            acousticness=_clamp(audio_features.get("acousticness", 0.5), 0.0, 1.0),
            instrumentalness=_clamp(audio_features.get("instrumentalness", 0.3), 0.0, 1.0),
            speechiness=_clamp(audio_features.get("speechiness", 0.0), 0.0, 1.0),
            tempo=_clamp(int(audio_features.get("tempo", 120)), 50, 200),
            loudness=_clamp(float(audio_features.get("loudness", -5.0)), -30.0, 0.0),
            mode=_clamp(int(audio_features.get("mode", 1)), 0, 1),
            
            # Context information
            mood_tags=context.get("mood_tags", [])[:5],  # Limit to 5 tags
            activity=context.get("activity"),
            time_of_day=context.get("time_of_day"),
            weather=context.get("weather"),
            social=context.get("social"),
            emotional_intensity=_clamp(float(context.get("emotional_intensity", 0.5)), 0.0, 1.0),
            
            # Preferences
            primary_genres=genres.get("primary", [])[:2],  # Limit to 2 primary
            secondary_genres=genres.get("secondary", [])[:3],  # Limit to 3 secondary
            exclude_genres=genres.get("exclude", [])[:2],  # Limit to 2 excluded
            popularity_range=preferences.get("popularity_range", [20, 80]),
            decade_bias=preferences.get("decade_bias")
        )
        
        logger.info(f"Successfully parsed mood: valence={mood_params.valence:.2f}, "
                   f"energy={mood_params.energy:.2f}, genres={mood_params.primary_genres + mood_params.secondary_genres}")
        
        # Apply personalization if enabled and user_id provided
        if use_personalization and user_id:
            try:
                from moodtape_core.personalization import personalization_engine
                personalized_params, user_preferences = personalization_engine.personalize_mood_parameters(
                    user_id, mood_params
                )
                
                if user_preferences.confidence_score >= 0.3:
                    logger.info(f"Applied personalization for user {user_id} "
                               f"(confidence: {user_preferences.confidence_score:.2f})")
                    return personalized_params
                
            except Exception as e:
                logger.error(f"Error applying personalization for user {user_id}: {e}")
                # Fall back to original parameters
        
        return mood_params
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from GPT response: {e}")
        logger.error(f"Raw response was: {repr(response.choices[0].message.content if 'response' in locals() else 'No response')}")
        
        # Try fallback with simpler prompt
        try:
            logger.info("Attempting fallback with simpler prompt...")
            fallback_prompt = SIMPLE_MOOD_PARSING_PROMPT.format(
                user_mood=description
            )
            
            fallback_response = await get_openai_client().chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": fallback_prompt}],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            fallback_content = fallback_response.choices[0].message.content.strip()
            
            # Clean fallback content same way
            start_idx = fallback_content.find('{')
            end_idx = fallback_content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                fallback_content = fallback_content[start_idx:end_idx + 1]
            
            parsed_data = json.loads(fallback_content)
            logger.info("Fallback parsing successful")
            
        except Exception as fallback_error:
            logger.error(f"Fallback parsing also failed: {fallback_error}")
            return None
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit exceeded: {e}")
        return None
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in mood parsing: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Description: {description[:100]}...")
        
        # Log raw response if available
        if 'response' in locals():
            logger.error(f"Raw GPT response: {repr(response.choices[0].message.content)}")
        
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


async def get_mood_summary(mood_params: MoodParameters, language: str = "ru") -> str:
    """
    Generate a human-readable summary of parsed mood parameters.
    
    Args:
        mood_params: Parsed mood parameters
        language: Language for summary
    
    Returns:
        Human-readable mood summary
    """
    # Energy level descriptions
    energy_desc = {
        "en": {
            (0.0, 0.3): "calm and peaceful",
            (0.3, 0.7): "moderate energy",
            (0.7, 1.0): "high energy and dynamic"
        },
        "ru": {
            (0.0, 0.3): "спокойное и умиротворённое",
            (0.3, 0.7): "умеренная энергия",
            (0.7, 1.0): "высокая энергия и динамика"
        },
        "es": {
            (0.0, 0.3): "calmado y pacífico",
            (0.3, 0.7): "energía moderada", 
            (0.7, 1.0): "alta energía y dinámico"
        }
    }
    
    # Valence descriptions
    valence_desc = {
        "en": {
            (0.0, 0.3): "melancholic and introspective",
            (0.3, 0.7): "balanced emotional tone",
            (0.7, 1.0): "positive and uplifting"
        },
        "ru": {
            (0.0, 0.3): "меланхоличное и задумчивое",
            (0.3, 0.7): "сбалансированный эмоциональный тон",
            (0.7, 1.0): "позитивное и воодушевляющее"
        },
        "es": {
            (0.0, 0.3): "melancólico e introspectivo",
            (0.3, 0.7): "tono emocional equilibrado",
            (0.7, 1.0): "positivo y edificante"
        }
    }
    
    def get_description(value: float, desc_dict: Dict) -> str:
        for (min_val, max_val), desc in desc_dict.items():
            if min_val <= value < max_val:
                return desc
        return list(desc_dict.values())[-1]  # fallback to last description
    
    lang_descs = {
        "energy": energy_desc.get(language, energy_desc["ru"]),
        "valence": valence_desc.get(language, valence_desc["ru"])
    }
    
    energy_text = get_description(mood_params.energy, lang_descs["energy"])
    valence_text = get_description(mood_params.valence, lang_descs["valence"])
    
    # Combine genres and mood tags
    genres_text = ", ".join(mood_params.genre_hints[:3]) if mood_params.genre_hints else ""
    mood_tags_text = ", ".join(mood_params.mood_tags[:3]) if mood_params.mood_tags else ""
    
    if language == "ru":
        summary = f"Настроение: {valence_text}, {energy_text}"
        if genres_text:
            summary += f"\nЖанры: {genres_text}"
        if mood_tags_text:
            summary += f"\nТеги: {mood_tags_text}"
    elif language == "es":
        summary = f"Estado de ánimo: {valence_text}, {energy_text}"
        if genres_text:
            summary += f"\nGéneros: {genres_text}"
        if mood_tags_text:
            summary += f"\nEtiquetas: {mood_tags_text}"
    else:  # English
        summary = f"Mood: {valence_text}, {energy_text}"
        if genres_text:
            summary += f"\nGenres: {genres_text}"
        if mood_tags_text:
            summary += f"\nTags: {mood_tags_text}"
    
    return summary 