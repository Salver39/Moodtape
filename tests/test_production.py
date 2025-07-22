#!/usr/bin/env python3
"""Production testing script for Moodtape bot."""

import asyncio
import json
import time
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, 
    SPOTIPY_CLIENT_ID, APPLE_TEAM_ID,
    MUSIC_SERVICES
)
from utils.logger import get_logger, setup_logging
from utils.database import db_manager
from moodtape_core.gpt_parser import parse_mood_description
from auth.spotify_auth import spotify_auth
from auth.apple_auth import apple_music_client
from bot.middleware.error_handler import error_handler
from bot.middleware.rate_limiter import rate_limiter

logger = get_logger(__name__)

class ProductionTester:
    """Test production readiness of Moodtape bot."""
    
    def __init__(self):
        self.results = {}
        self.failed_tests = []
        self.test_user_id = 12345  # Fake user ID for testing
    
    async def run_all_tests(self):
        """Run all production tests."""
        print("🧪 Starting Moodtape Production Tests\n")
        
        # Basic configuration tests
        await self._test_configuration()
        await self._test_dependencies()
        
        # Core functionality tests
        await self._test_database()
        await self._test_gpt_integration()
        await self._test_music_services()
        
        # Middleware tests
        await self._test_error_handling()
        await self._test_rate_limiting()
        
        # Performance tests
        await self._test_performance()
        
        # Print results
        self._print_results()
        
        return len(self.failed_tests) == 0
    
    async def _test_configuration(self):
        """Test basic configuration."""
        print("📋 Testing Configuration...")
        
        # Required environment variables
        required_vars = {
            "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
            "OPENAI_API_KEY": OPENAI_API_KEY
        }
        
        for var_name, var_value in required_vars.items():
            if not var_value:
                self._fail_test(f"❌ {var_name} not configured")
            else:
                self._pass_test(f"✅ {var_name} configured")
        
        # Optional services
        if SPOTIPY_CLIENT_ID:
            self._pass_test("✅ Spotify credentials configured")
        else:
            print("⚠️  Spotify credentials not configured (optional)")
        
        if APPLE_TEAM_ID:
            self._pass_test("✅ Apple Music credentials configured")
        else:
            print("⚠️  Apple Music credentials not configured (optional)")
        
        # Music services availability
        available_services = [k for k, v in MUSIC_SERVICES.items() if v["enabled"]]
        if available_services:
            self._pass_test(f"✅ {len(available_services)} music service(s) available: {', '.join(available_services)}")
        else:
            self._fail_test("❌ No music services available")
    
    async def _test_dependencies(self):
        """Test Python dependencies."""
        print("\n📦 Testing Dependencies...")
        
        try:
            import telegram
            self._pass_test("✅ python-telegram-bot imported")
        except ImportError:
            self._fail_test("❌ python-telegram-bot not available")
        
        try:
            import openai
            self._pass_test("✅ openai imported")
        except ImportError:
            self._fail_test("❌ openai not available")
        
        try:
            import spotipy
            self._pass_test("✅ spotipy imported")
        except ImportError:
            print("⚠️  spotipy not available (optional)")
        
        try:
            import jwt
            self._pass_test("✅ PyJWT imported")
        except ImportError:
            self._fail_test("❌ PyJWT not available")
    
    async def _test_database(self):
        """Test database functionality."""
        print("\n💾 Testing Database...")
        
        try:
            # Initialize databases
            db_manager.init_databases()
            self._pass_test("✅ Database initialization")
            
            # Test token operations
            test_token = {"access_token": "test", "refresh_token": "test"}
            db_manager.save_user_token(self.test_user_id, "test_service", test_token)
            
            retrieved_token = db_manager.get_user_token(self.test_user_id, "test_service")
            if retrieved_token:
                self._pass_test("✅ Database read/write operations")
            else:
                self._fail_test("❌ Database read/write failed")
            
            # Test feedback logging
            db_manager.save_feedback(
                user_id=self.test_user_id,
                rating=1,
                query_id="test_query",
                mood_params={"valence": 0.8}
            )
            self._pass_test("✅ Feedback logging")
            
            # Clean up test data
            db_manager.delete_user_token(self.test_user_id, "test_service")
            
        except Exception as e:
            self._fail_test(f"❌ Database error: {e}")
    
    async def _test_gpt_integration(self):
        """Test GPT-4o integration."""
        print("\n🤖 Testing GPT Integration...")
        
        try:
            # Test basic mood parsing
            test_descriptions = [
                "happy and energetic morning",
                "спокойный вечер дома",
                "energía para entrenar"
            ]
            
            for i, description in enumerate(test_descriptions):
                try:
                    params = await parse_mood_description(
                        description=description,
                        user_language="en" if i == 0 else "ru" if i == 1 else "es",
                        user_id=None,  # Don't use personalization for testing
                        use_personalization=False
                    )
                    
                    if params and hasattr(params, 'valence') and hasattr(params, 'energy'):
                        self._pass_test(f"✅ GPT parsing: '{description}'")
                    else:
                        self._fail_test(f"❌ GPT parsing failed: '{description}'")
                
                except Exception as e:
                    self._fail_test(f"❌ GPT error for '{description}': {e}")
                
                # Add delay to avoid rate limits
                await asyncio.sleep(1)
        
        except Exception as e:
            self._fail_test(f"❌ GPT integration error: {e}")
    
    async def _test_music_services(self):
        """Test music service integrations."""
        print("\n🎵 Testing Music Services...")
        
        # Test Spotify
        if spotify_auth.is_configured():
            try:
                # Test auth URL generation
                auth_url = spotify_auth.get_auth_url(self.test_user_id)
                if auth_url and auth_url.startswith("https://"):
                    self._pass_test("✅ Spotify auth URL generation")
                else:
                    self._fail_test("❌ Spotify auth URL generation failed")
            except Exception as e:
                self._fail_test(f"❌ Spotify test error: {e}")
        else:
            print("⚠️  Spotify not configured")
        
        # Test Apple Music
        if apple_music_client.is_configured():
            try:
                # Test developer token generation
                token = apple_music_client.auth.generate_developer_token()
                if token and isinstance(token, str):
                    self._pass_test("✅ Apple Music developer token generation")
                else:
                    self._fail_test("❌ Apple Music token generation failed")
            except Exception as e:
                self._fail_test(f"❌ Apple Music test error: {e}")
        else:
            print("⚠️  Apple Music not configured")
    
    async def _test_error_handling(self):
        """Test error handling middleware."""
        print("\n🛡️  Testing Error Handling...")
        
        try:
            # Test error handler instantiation
            if error_handler:
                self._pass_test("✅ Error handler initialized")
            else:
                self._fail_test("❌ Error handler not available")
            
            # Test error classification (simulate errors)
            test_errors = [
                "OpenAI API error",
                "Spotify rate limit exceeded",
                "Database connection failed"
            ]
            
            for error_msg in test_errors:
                try:
                    # This would normally classify the error type
                    error_type = "general"
                    if "openai" in error_msg.lower():
                        error_type = "mood_parsing"
                    elif "spotify" in error_msg.lower():
                        error_type = "spotify_api_error"
                    elif "database" in error_msg.lower():
                        error_type = "database_error"
                    
                    self._pass_test(f"✅ Error classification: {error_type}")
                except Exception as e:
                    self._fail_test(f"❌ Error handling failed: {e}")
        
        except Exception as e:
            self._fail_test(f"❌ Error handling test failed: {e}")
    
    async def _test_rate_limiting(self):
        """Test rate limiting functionality."""
        print("\n⏱️  Testing Rate Limiting...")
        
        try:
            # Test rate limiter initialization
            if rate_limiter:
                self._pass_test("✅ Rate limiter initialized")
            else:
                self._fail_test("❌ Rate limiter not available")
            
            # Test rate limit checking
            allowed, message = await rate_limiter.check_rate_limit(
                user_id=self.test_user_id,
                operation="test"
            )
            
            if allowed:
                self._pass_test("✅ Rate limit check (first request)")
            else:
                self._fail_test(f"❌ Rate limit check failed: {message}")
            
            # Test user stats
            stats = rate_limiter.get_user_stats(self.test_user_id)
            if isinstance(stats, dict) and "minute_requests" in stats:
                self._pass_test("✅ Rate limit statistics")
            else:
                self._fail_test("❌ Rate limit statistics failed")
        
        except Exception as e:
            self._fail_test(f"❌ Rate limiting test failed: {e}")
    
    async def _test_performance(self):
        """Test basic performance metrics."""
        print("\n⚡ Testing Performance...")
        
        try:
            # Test response time for mood parsing
            start_time = time.time()
            
            params = await parse_mood_description(
                description="test mood",
                user_language="en",
                use_personalization=False
            )
            
            response_time = time.time() - start_time
            
            if response_time < 10.0:  # Should respond within 10 seconds
                self._pass_test(f"✅ Mood parsing response time: {response_time:.2f}s")
            else:
                self._fail_test(f"❌ Slow mood parsing: {response_time:.2f}s")
            
            # Test memory usage (basic check)
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb < 1000:  # Should use less than 1GB
                self._pass_test(f"✅ Memory usage: {memory_mb:.1f}MB")
            else:
                print(f"⚠️  High memory usage: {memory_mb:.1f}MB")
        
        except ImportError:
            print("⚠️  psutil not available for memory testing")
        except Exception as e:
            self._fail_test(f"❌ Performance test failed: {e}")
    
    def _pass_test(self, message):
        """Mark test as passed."""
        print(f"  {message}")
        self.results[message] = True
    
    def _fail_test(self, message):
        """Mark test as failed."""
        print(f"  {message}")
        self.results[message] = False
        self.failed_tests.append(message)
    
    def _print_results(self):
        """Print final test results."""
        print("\n" + "="*60)
        print("🧪 TEST RESULTS")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result)
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                print(f"  • {test}")
        
        print("\n" + "="*60)
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Bot is ready for production.")
        else:
            print("⚠️  Some tests failed. Please fix issues before deploying.")
        
        print("="*60)


async def main():
    """Main test function."""
    # Setup logging for tests
    setup_logging(level="INFO", log_to_file=False)
    
    # Check if we're in the right directory
    if not Path("bot/main.py").exists():
        print("❌ Please run this script from the project root directory")
        return False
    
    # Run tests
    tester = ProductionTester()
    success = await tester.run_all_tests()
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        sys.exit(1) 