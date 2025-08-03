"""GPT-based mood parsing and analysis for Moodtape."""

import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

@dataclass
class MoodParameters:
    """Structured mood parameters extracted from user description."""
    energy: float  # 0.0 to 1.0
    valence: float  # 0.0 to 1.0
    danceability: float  # 0.0 to 1.0
    acousticness: float  # 0.0 to 1.0
    instrumentalness: float  # 0.0 to 1.0
    mood_tags: List[str]  # e.g. ["happy", "energetic"]
    genre_hints: List[str]  # e.g. ["pop", "rock"]
    activity: Optional[str]  # e.g. "workout", "study"

async def parse_mood(description: str) -> Optional[MoodParameters]:
    """
    Parse mood description using GPT to extract structured parameters.
    
    Args:
        description: User's mood description text
    
    Returns:
        MoodParameters object or None if parsing failed
    """
    try:
        # Prepare system message
        system_message = """You are a music mood analyzer. Extract mood parameters from the user's description.
        Return a JSON object with the following numeric parameters (0.0 to 1.0):
        - energy: How energetic the music should be
        - valence: How positive/happy the music should be
        - danceability: How suitable for dancing
        - acousticness: How acoustic vs electronic
        - instrumentalness: How instrumental vs vocal
        Also include:
        - mood_tags: List of mood keywords
        - genre_hints: List of suitable music genres
        - activity: Optional activity context (or null)"""
        
        # Get completion from GPT
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": description}
            ],
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        # Parse response
        if not response.choices:
            logger.error("No choices in GPT response")
            return None
        
        try:
            # Extract and parse JSON
            content = response.choices[0].message.content
            params = json.loads(content)
            
            # Validate and create MoodParameters
            return MoodParameters(
                energy=float(params.get("energy", 0.5)),
                valence=float(params.get("valence", 0.5)),
                danceability=float(params.get("danceability", 0.5)),
                acousticness=float(params.get("acousticness", 0.5)),
                instrumentalness=float(params.get("instrumentalness", 0.5)),
                mood_tags=params.get("mood_tags", []),
                genre_hints=params.get("genre_hints", []),
                activity=params.get("activity")
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse GPT response: {e}")
            return None
        
    except Exception as e:
        logger.error(f"Error in parse_mood: {e}")
        return None 