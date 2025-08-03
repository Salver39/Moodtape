"""Simple script to get Spotify access token."""

import sys
import json
import asyncio
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

def get_spotify_token():
    """Get Spotify access token using OAuth flow."""
    try:
        # Initialize Spotify OAuth
        auth_manager = SpotifyOAuth(
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET,
            redirect_uri=settings.SPOTIFY_REDIRECT_URI,
            scope=[
                "user-read-private",
                "user-library-read",
                "user-top-read",
                "playlist-modify-public",
                "playlist-modify-private"
            ],
            show_dialog=True  # Force auth dialog
        )
        
        # Get token info
        token_info = auth_manager.get_access_token()
        if not token_info:
            logger.error("❌ Failed to get token info")
            return None
        
        # Print token details
        logger.info("✅ Successfully got Spotify token:")
        logger.info(f"Access Token: {token_info['access_token'][:10]}...")
        logger.info(f"Refresh Token: {token_info.get('refresh_token', 'None')[:10]}...")
        logger.info(f"Expires In: {token_info.get('expires_in', 'Unknown')} seconds")
        
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Error getting Spotify token: {e}")
        return None

if __name__ == "__main__":
    token_info = get_spotify_token()
    sys.exit(0 if token_info else 1) 