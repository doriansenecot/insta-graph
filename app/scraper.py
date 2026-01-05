"""Instagram scraper using instagrapi."""

import json
import logging
import random
import time
from collections.abc import Callable

import redis
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired

from app.config import get_settings
from app.models import FollowerInfo

logger = logging.getLogger(__name__)

# Redis cache TTL for user profiles (24 hours)
USER_CACHE_TTL = 86400


class InstagramScraper:
    """Scraper for Instagram followers with recursive depth support."""

    def __init__(self):
        self.client = Client()
        self.settings = get_settings()
        self._logged_in = False
        self._redis: redis.Redis | None = None

    @property
    def redis_client(self) -> redis.Redis:
        """Lazy Redis connection for user cache."""
        if self._redis is None:
            self._redis = redis.from_url(self.settings.redis_url)
        return self._redis

    def login(self) -> bool:
        """Login to Instagram. Returns True if successful."""
        if self._logged_in:
            return True

        try:
            # Try to load existing session
            try:
                self.client.load_settings("session.json")
                self.client.login(
                    self.settings.instagram_username, self.settings.instagram_password
                )
                self._logged_in = True
                logger.info("Logged in using saved session")
                return True
            except (FileNotFoundError, LoginRequired):
                pass

            # Fresh login
            self.client.login(self.settings.instagram_username, self.settings.instagram_password)
            self.client.dump_settings("session.json")
            self._logged_in = True
            logger.info("Fresh login successful, session saved")
            return True

        except ClientError as e:
            logger.error(f"Login failed: {e}")
            return False

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Add random delay to avoid rate limiting."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _get_cached_user(self, username: str) -> dict | None:
        """Get user info from Redis cache."""
        try:
            cached = self.redis_client.get(f"user:{username}")
            if cached:
                logger.debug(f"Cache hit for user {username}")
                return json.loads(cached)
        except redis.RedisError as e:
            logger.warning(f"Redis cache error: {e}")
        return None

    def _cache_user(self, username: str, user_info: dict) -> None:
        """Cache user info in Redis."""
        try:
            self.redis_client.setex(f"user:{username}", USER_CACHE_TTL, json.dumps(user_info))
            logger.debug(f"Cached user {username}")
        except redis.RedisError as e:
            logger.warning(f"Redis cache error: {e}")

    def get_user_info(self, username: str) -> dict | None:
        """Get user information by username (with Redis cache)."""
        # Check cache first
        cached = self._get_cached_user(username)
        if cached:
            return cached

        try:
            self._random_delay()
            user = self.client.user_info_by_username(username)
            user_info = {
                "user_id": user.pk,
                "username": user.username,
                "full_name": user.full_name,
                "follower_count": user.follower_count,
                "following_count": user.following_count,
                "is_private": user.is_private,
            }
            # Cache the result
            self._cache_user(username, user_info)
            return user_info
        except ClientError as e:
            logger.error(f"Failed to get user info for {username}: {e}")
            return None

    def get_followers(self, user_id: int, amount: int = 0) -> list[dict]:
        """Get followers of a user. amount=0 means all followers."""
        try:
            self._random_delay()
            followers = self.client.user_followers(user_id, amount=amount)
            return [
                {
                    "user_id": user.pk,
                    "username": user.username,
                    "full_name": user.full_name,
                    "follower_count": getattr(user, "follower_count", 0),
                    "following_count": getattr(user, "following_count", 0),
                    "is_private": user.is_private,
                }
                for user in followers.values()
            ]
        except ClientError as e:
            logger.error(f"Failed to get followers for user {user_id}: {e}")
            return []

    def analyze_recursive(
        self,
        username: str,
        current_depth: int = 1,
        max_depth: int = 1,
        min_followers: int = 3000,
        visited: set[str] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[FollowerInfo]:
        """Recursively analyze followers.

        Args:
            username: Target Instagram username
            current_depth: Current recursion depth
            max_depth: Maximum depth to traverse
            min_followers: Minimum follower count filter
            visited: Set of already visited usernames
            on_progress: Callback for progress updates

        Returns:
            List of FollowerInfo objects matching the criteria
        """
        if visited is None:
            visited = set()

        if username in visited:
            return []

        visited.add(username)
        results = []

        if on_progress:
            on_progress(f"Analyzing {username} at depth {current_depth}")

        # Get target user info
        user_info = self.get_user_info(username)
        if not user_info:
            logger.warning(f"Could not get info for {username}")
            return results

        if user_info["is_private"]:
            logger.info(f"Skipping private account: {username}")
            return results

        # Get followers
        followers = self.get_followers(user_info["user_id"])
        logger.info(f"Found {len(followers)} followers for {username}")

        for follower in followers:
            # We need full user info for follower count
            follower_info = self.get_user_info(follower["username"])
            if not follower_info:
                continue

            # Check if meets minimum followers criteria
            if follower_info["follower_count"] >= min_followers:
                results.append(
                    FollowerInfo(
                        username=follower_info["username"],
                        full_name=follower_info["full_name"],
                        follower_count=follower_info["follower_count"],
                        following_count=follower_info["following_count"],
                        is_private=follower_info["is_private"],
                        depth=current_depth,
                    )
                )

                # Recurse if not at max depth and not private
                if current_depth < max_depth and not follower_info["is_private"]:
                    nested = self.analyze_recursive(
                        follower_info["username"],
                        current_depth + 1,
                        max_depth,
                        min_followers,
                        visited,
                        on_progress,
                    )
                    results.extend(nested)

        return results
