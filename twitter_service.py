"""
X (Twitter) Service Module

Handles posting tweets using X API v2 with OAuth 1.0a authentication.

Usage:
    from twitter_service import TwitterService

    service = TwitterService()
    result = service.post_tweet("Hello from the Sports Journalist Agent!")

Requirements:
    pip install tweepy

Environment Variables:
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class TwitterService:
    """Service for posting tweets to X (Twitter)."""

    # X/Twitter character limit
    MAX_TWEET_LENGTH = 280

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None
    ):
        """
        Initialize Twitter service with OAuth 1.0a credentials.

        Args:
            api_key: X API Key (Consumer Key)
            api_secret: X API Secret (Consumer Secret)
            access_token: X Access Token
            access_token_secret: X Access Token Secret
        """
        self.api_key = api_key or os.getenv("X_API_KEY")
        self.api_secret = api_secret or os.getenv("X_API_SECRET")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("X_ACCESS_TOKEN_SECRET")

        self._client = None
        self._validate_credentials()

    def _validate_credentials(self):
        """Validate that all required credentials are present."""
        missing = []
        if not self.api_key:
            missing.append("X_API_KEY")
        if not self.api_secret:
            missing.append("X_API_SECRET")
        if not self.access_token:
            missing.append("X_ACCESS_TOKEN")
        if not self.access_token_secret:
            missing.append("X_ACCESS_TOKEN_SECRET")

        if missing:
            raise ValueError(f"Missing X API credentials: {', '.join(missing)}")

    @property
    def client(self):
        """Lazy-load tweepy client."""
        if self._client is None:
            try:
                import tweepy
            except ImportError:
                raise ImportError("tweepy is required. Install with: pip install tweepy")

            self._client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
        return self._client

    def extract_tweet_from_article(self, article: str) -> Optional[str]:
        """
        Extract tweet-worthy content from an AI-generated article.

        Looks for sections like:
        - "Tweet:" or "**Tweet:**"
        - "Tweet-worthy summary"
        - Content in quotes that looks like a tweet

        Args:
            article: The full article text

        Returns:
            Extracted tweet text or None if not found
        """
        # Pattern 1: Look for explicit tweet section
        patterns = [
            r'\*\*Tweet:?\*\*\s*["\']?(.+?)["\']?\s*(?:\n|$)',
            r'Tweet:?\s*["\']?(.+?)["\']?\s*(?:\n|$)',
            r'\*\*Tweet-worthy[^:]*:\*\*\s*["\']?(.+?)["\']?\s*(?:\n|$)',
            r'Tweet-worthy[^:]*:\s*["\']?(.+?)["\']?\s*(?:\n|$)',
            r'(?:^|\n)>\s*(.{50,280})\s*(?:\n|$)',  # Blockquote style
        ]

        for pattern in patterns:
            match = re.search(pattern, article, re.IGNORECASE | re.MULTILINE)
            if match:
                tweet = match.group(1).strip()
                # Clean up markdown formatting
                tweet = re.sub(r'\*+', '', tweet)
                tweet = re.sub(r'_+', '', tweet)
                if len(tweet) <= self.MAX_TWEET_LENGTH:
                    return tweet

        return None

    def truncate_tweet(self, text: str, add_ellipsis: bool = True) -> str:
        """
        Truncate text to fit within Twitter's character limit.

        Args:
            text: Text to truncate
            add_ellipsis: Whether to add "..." at the end

        Returns:
            Truncated text
        """
        if len(text) <= self.MAX_TWEET_LENGTH:
            return text

        max_len = self.MAX_TWEET_LENGTH - 3 if add_ellipsis else self.MAX_TWEET_LENGTH
        truncated = text[:max_len].rsplit(' ', 1)[0]  # Break at word boundary

        if add_ellipsis:
            truncated += "..."

        return truncated

    def post_tweet(self, text: str, auto_truncate: bool = True) -> dict:
        """
        Post a tweet to X.

        Args:
            text: Tweet content
            auto_truncate: Whether to automatically truncate if too long

        Returns:
            dict with success status and tweet details
        """
        if not text or not text.strip():
            return {
                "success": False,
                "error": "Tweet text cannot be empty"
            }

        text = text.strip()

        # Handle length
        if len(text) > self.MAX_TWEET_LENGTH:
            if auto_truncate:
                text = self.truncate_tweet(text)
            else:
                return {
                    "success": False,
                    "error": f"Tweet exceeds {self.MAX_TWEET_LENGTH} characters ({len(text)} chars)"
                }

        try:
            response = self.client.create_tweet(text=text)

            tweet_id = response.data['id']
            tweet_url = f"https://x.com/i/web/status/{tweet_id}"

            return {
                "success": True,
                "tweet_id": tweet_id,
                "tweet_url": tweet_url,
                "text": text,
                "character_count": len(text)
            }

        except Exception as e:
            error_msg = str(e)

            # Parse common Twitter API errors
            if "403" in error_msg:
                error_msg = "Access forbidden. Check your API permissions (need Read and Write)."
            elif "401" in error_msg:
                error_msg = "Authentication failed. Check your API credentials."
            elif "429" in error_msg:
                error_msg = "Rate limit exceeded. Please wait before posting again."
            elif "duplicate" in error_msg.lower():
                error_msg = "Duplicate tweet. Twitter doesn't allow posting the same content twice."

            return {
                "success": False,
                "error": error_msg
            }

    def post_tweet_from_article(self, article: str, fallback_text: Optional[str] = None) -> dict:
        """
        Extract and post a tweet from an AI-generated article.

        Args:
            article: The full article text
            fallback_text: Text to use if no tweet can be extracted

        Returns:
            dict with success status and tweet details
        """
        tweet_text = self.extract_tweet_from_article(article)

        if not tweet_text and fallback_text:
            tweet_text = self.truncate_tweet(fallback_text)

        if not tweet_text:
            return {
                "success": False,
                "error": "Could not extract tweet from article. No tweet section found."
            }

        return self.post_tweet(tweet_text)

    def is_configured(self) -> bool:
        """Check if Twitter service is properly configured."""
        try:
            self._validate_credentials()
            return True
        except ValueError:
            return False


# Singleton instance for easy import
_twitter_service = None

def get_twitter_service() -> TwitterService:
    """Get or create the singleton TwitterService instance."""
    global _twitter_service
    if _twitter_service is None:
        _twitter_service = TwitterService()
    return _twitter_service


if __name__ == "__main__":
    # Test the service
    try:
        service = TwitterService()
        print("Twitter service initialized successfully!")
        print(f"API Key: {service.api_key[:8]}...")

        # Test tweet (commented out to avoid accidental posting)
        # result = service.post_tweet("Test tweet from Sports Journalist Agent!")
        # print(result)

    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")
