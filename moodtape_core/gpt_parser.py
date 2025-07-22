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

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


@dataclass
class MoodParameters:
    """Data class for mood-based music parameters."""
    valence: float  # Musical positivity (0.0 - 1.0)
    energy: float  # Energy level (0.0 - 1.0)
    danceability: float  # How suitable for dancing (0.0 - 1.0)
    acousticness: float  # Acoustic vs electronic (0.0 - 1.0)
    instrumentalness: float  # Instrumental vs vocal (0.0 - 1.0)
    tempo: int  # BPM (50 - 200)
    genre_hints: List[str]  # Suggested genres
    mood_tags: List[str]  # Descriptive mood tags
    time_of_day: Optional[str]  # morning, afternoon, evening, night
    weather: Optional[str]  # sunny, rainy, cloudy, etc.
    activity: Optional[str]  # working, relaxing, exercising, etc.


MOOD_PARSING_PROMPT = """
You are a music mood analyzer. Your task is to analyze a user's text description of their mood or situation and convert it into specific music parameters.

The user will describe their current mood, situation, or desired atmosphere. You need to extract musical characteristics that would match their description.

Return a JSON object with the following structure:
{
    "valence": 0.0-1.0,  // Musical positivity (0=sad, 1=happy)
    "energy": 0.0-1.0,   // Energy level (0=calm, 1=energetic)
    "danceability": 0.0-1.0,  // How danceable (0=not danceable, 1=very danceable)
    "acousticness": 0.0-1.0,  // Acoustic feel (0=electronic, 1=acoustic)
    "instrumentalness": 0.0-1.0,  // Instrumental preference (0=vocals, 1=instrumental)
    "tempo": 50-200,  // BPM that matches the mood
    "genre_hints": ["genre1", "genre2"],  // 2-4 relevant genres
    "mood_tags": ["tag1", "tag2"],  // 2-5 descriptive mood tags
    "time_of_day": "morning/afternoon/evening/night",  // if mentioned
    "weather": "sunny/rainy/cloudy/snow/storm",  // if mentioned
    "activity": "working/relaxing/exercising/partying/studying"  // if mentioned
}

Examples:
- "feeling sad and lonely, rainy day" → low valence (0.2), low energy (0.3), high acousticness (0.8)
- "pumped up for the gym" → high valence (0.9), high energy (0.9), high danceability (0.8)
- "cozy evening at home with tea" → medium valence (0.6), low energy (0.2), high acousticness (0.7)
- "ready to party all night" → high valence (0.9), high energy (0.9), high danceability (0.9)

Important guidelines:
- Always return valid JSON
- Keep values within specified ranges
- Choose genres that match the mood (pop, rock, jazz, classical, electronic, indie, etc.)
- Be creative with mood_tags but keep them concise
- If time/weather/activity aren't clear, set them to null
- Consider cultural context (if text is in Russian, consider Russian music genres too)
"""


async def parse_mood_description(
    description: str, 
    user_language: str = "en",
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
        user_prompt = f"""
        User language: {user_language}
        User description: "{description}"
        
        Analyze this mood description and return the JSON parameters for music matching.
        """
        
        logger.info(f"Parsing mood description: {description[:100]}...")
        
        # Call GPT-4o
        response = await client.chat.completions.create(
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
        logger.debug(f"GPT-4o response: {json_content}")
        
        # Parse JSON response
        parsed_data = json.loads(json_content)
        
        # Validate and create MoodParameters
        mood_params = MoodParameters(
            valence=_clamp(parsed_data.get("valence", 0.5), 0.0, 1.0),
            energy=_clamp(parsed_data.get("energy", 0.5), 0.0, 1.0),
            danceability=_clamp(parsed_data.get("danceability", 0.5), 0.0, 1.0),
            acousticness=_clamp(parsed_data.get("acousticness", 0.5), 0.0, 1.0),
            instrumentalness=_clamp(parsed_data.get("instrumentalness", 0.3), 0.0, 1.0),
            tempo=_clamp(int(parsed_data.get("tempo", 120)), 50, 200),
            genre_hints=parsed_data.get("genre_hints", [])[:4],  # Limit to 4 genres
            mood_tags=parsed_data.get("mood_tags", [])[:5],  # Limit to 5 tags
            time_of_day=parsed_data.get("time_of_day"),
            weather=parsed_data.get("weather"),
            activity=parsed_data.get("activity")
        )
        
        logger.info(f"Successfully parsed mood: valence={mood_params.valence:.2f}, "
                   f"energy={mood_params.energy:.2f}, genres={mood_params.genre_hints}")
        
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
        return None
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit exceeded: {e}")
        return None
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in mood parsing: {e}")
        return None


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


async def get_mood_summary(mood_params: MoodParameters, language: str = "en") -> str:
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
        "energy": energy_desc.get(language, energy_desc["en"]),
        "valence": valence_desc.get(language, valence_desc["en"])
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