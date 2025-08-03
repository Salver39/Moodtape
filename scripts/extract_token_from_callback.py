"""Script to extract Spotify token from callback URL."""

import sys
import json
import asyncio
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

def extract_token_from_url(callback_url: str):
    """
    Extract Spotify token from callback URL.
    
    Args:
        callback_url: Full callback URL from Spotify
    
    Returns:
        Token info dictionary or None if failed
    """
    try:
        # Parse URL
        parsed_url = urlparse(callback_url)
        params = parse_qs(parsed_url.query)
        
        # Check for code
        if 'code' not in params:
            logger.error("❌ No authorization code in URL")
            return None
        
        auth_code = params['code'][0]
        logger.info(f"✅ Found authorization code: {auth_code[:10]}...")
        
        # Initialize OAuth manager
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
            ]
        )
        
        # Get token info
        token_info = auth_manager.get_access_token(auth_code)
        if not token_info:
            logger.error("❌ Failed to get token info")
            return None
        
        # Print token details
        logger.info("✅ Successfully extracted token:")
        logger.info(f"Access Token: {token_info['access_token'][:10]}...")
        logger.info(f"Refresh Token: {token_info.get('refresh_token', 'None')[:10]}...")
        logger.info(f"Expires In: {token_info.get('expires_in', 'Unknown')} seconds")
        
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Error extracting token: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Please provide callback URL as argument")
        sys.exit(1)
    
    callback_url = sys.argv[1]
    token_info = extract_token_from_url(callback_url)
    sys.exit(0 if token_info else 1) 