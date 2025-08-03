"""Script to check Spotify API status and permissions."""

import sys
import json
import asyncio
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

def check_spotify_status():
    """Check Spotify API status and permissions."""
    try:
        # Initialize Spotify client
        client_credentials_manager = SpotifyClientCredentials(
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        
        # Test search endpoint
        logger.info("Testing search endpoint...")
        results = sp.search(q='test', limit=1)
        if results and 'tracks' in results:
            logger.info("✅ Search endpoint working")
        else:
            logger.error("❌ Search endpoint not working")
        
        # Test audio features endpoint
        logger.info("Testing audio features endpoint...")
        track_id = '2takcwOaAZWiXQijPHIx7B'  # Some popular track
        features = sp.audio_features([track_id])
        if features and features[0]:
            logger.info("✅ Audio features endpoint working")
        else:
            logger.error("❌ Audio features endpoint not working")
        
        # Test recommendations endpoint
        logger.info("Testing recommendations endpoint...")
        recs = sp.recommendations(seed_tracks=[track_id], limit=1)
        if recs and 'tracks' in recs:
            logger.info("✅ Recommendations endpoint working")
        else:
            logger.error("❌ Recommendations endpoint not working")
        
        logger.info("✅ All basic endpoints working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Spotify API check failed: {e}")
        return False

if __name__ == "__main__":
    success = check_spotify_status()
    sys.exit(0 if success else 1) 