"""
Core Instaloader service - manages the Instaloader instance and provides
thread-safe operations with async wrappers for FastAPI.

This service wraps the synchronous Instaloader library and provides:
- Thread-safe session management
- Async wrappers for all blocking operations
- Exception mapping to API exceptions
- Resource pooling for concurrent requests
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, TypeVar

import instaloader
from instaloader import (
    Instaloader,
    Profile,
    Post,
    Story,
    StoryItem,
    Highlight,
    Hashtag,
    TopSearchResults,
)
from instaloader.exceptions import (
    InstaloaderException,
    LoginRequiredException,
    BadCredentialsException,
    TwoFactorAuthRequiredException,
    ProfileNotExistsException,
    PrivateProfileNotFollowedException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
    ConnectionException,
)

from app.core.config import get_settings
from app.core.logging import logger
from app.core.accounts import AccountManager, AccountInfo, get_account_manager
from app.core.exceptions import (
    APIException,
    AuthenticationError,
    ProfileNotFoundError,
    PrivateProfileError,
    PostNotFoundError,
    RateLimitError,
    LoginRequiredError,
    InvalidCredentialsError,
    TwoFactorRequiredError,
    ServiceUnavailableError,
)

T = TypeVar("T")


def map_instaloader_exception(exc: Exception) -> APIException:
    """
    Map Instaloader exceptions to API exceptions.
    
    Args:
        exc: The original exception from Instaloader
        
    Returns:
        Appropriate APIException subclass
    """
    if isinstance(exc, BadCredentialsException):
        return InvalidCredentialsError()
    elif isinstance(exc, TwoFactorAuthRequiredException):
        return TwoFactorRequiredError()
    elif isinstance(exc, LoginRequiredException):
        return LoginRequiredError(str(exc))
    elif isinstance(exc, ProfileNotExistsException):
        # Try to extract username from exception message
        return ProfileNotFoundError(str(exc))
    elif isinstance(exc, PrivateProfileNotFollowedException):
        return PrivateProfileError(str(exc))
    elif isinstance(exc, QueryReturnedNotFoundException):
        return PostNotFoundError(str(exc))
    elif isinstance(exc, TooManyRequestsException):
        return RateLimitError(str(exc))
    elif isinstance(exc, ConnectionException):
        return ServiceUnavailableError(f"Instagram connection error: {exc}")
    elif isinstance(exc, InstaloaderException):
        return APIException(message=str(exc), status_code=500)
    else:
        return APIException(message=f"Unexpected error: {exc}", status_code=500)


class InstaloaderService:
    """
    Thread-safe service for Instaloader operations.
    
    This class manages a pool of Instaloader instances for handling
    concurrent requests. It provides async wrappers for all blocking
    operations and handles session management.
    
    Usage:
        service = InstaloaderService()
        profile = await service.get_profile("instagram")
    """
    
    _instance: Optional["InstaloaderService"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "InstaloaderService":
        """Singleton pattern to ensure only one service instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the service with configuration."""
        # Prevent re-initialization
        if hasattr(self, "_initialized") and self._initialized:
            return
            
        self._initialized = True
        self._settings = get_settings()
        self._loader: Optional[Instaloader] = None
        self._loader_lock = threading.RLock()
        self._logged_in_user: Optional[str] = None
        
        # Account manager for multi-account rotation
        self._account_manager = get_account_manager()
        self._loaders: dict[str, Instaloader] = {}  # Cache loaders per account
        self._current_account: Optional[AccountInfo] = None
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=self._settings.max_concurrent_downloads,
            thread_name_prefix="instaloader_"
        )
        
        logger.info("InstaloaderService initialized")
        
        # Try to auto-load session on startup
        self._try_auto_load_session()
    
    def _get_loader(self) -> Instaloader:
        """
        Get or create the Instaloader instance.
        Thread-safe with lazy initialization.
        """
        if self._loader is None:
            with self._loader_lock:
                if self._loader is None:
                    self._loader = Instaloader(
                        quiet=not self._settings.debug,
                        download_videos=True,
                        download_video_thumbnails=True,
                        download_geotags=True,
                        download_comments=False,
                        save_metadata=True,
                        compress_json=True,
                        request_timeout=self._settings.request_timeout,
                        max_connection_attempts=3,  # Allow a few retries for transient errors
                    )
                    # Set download directory
                    self._loader.dirname_pattern = str(
                        self._settings.downloads_path / "{target}"
                    )
                    logger.debug("Created new Instaloader instance")
        return self._loader
    
    def _get_loader_for_account(self, account: AccountInfo) -> Instaloader:
        """
        Get or create an Instaloader instance for a specific account.
        Caches loaders per account to reuse sessions.
        """
        with self._loader_lock:
            if account.username in self._loaders:
                return self._loaders[account.username]
            
            # Create new loader for this account
            loader = Instaloader(
                quiet=not self._settings.debug,
                download_videos=True,
                download_video_thumbnails=True,
                download_geotags=True,
                download_comments=False,
                save_metadata=True,
                compress_json=True,
                request_timeout=self._settings.request_timeout,
                max_connection_attempts=3,  # Allow a few retries for transient errors
            )
            loader.dirname_pattern = str(
                self._settings.downloads_path / "{target}"
            )
            
            # Try to load session from multiple sources (in order of priority):
            # 1. Environment variable (INSTAGRAM_SESSIONS) - for Render/cloud deployment
            # 2. Session file on disk
            # 3. Fresh login
            
            session_loaded = False
            
            # 1. Try environment variable first (base64 encoded pickle)
            import os
            import base64
            env_sessions = os.getenv("INSTAGRAM_SESSIONS", "")
            if env_sessions and not session_loaded:
                try:
                    # Format: username1:base64data,username2:base64data
                    for pair in env_sessions.split(","):
                        if ":" in pair:
                            username, b64data = pair.split(":", 1)
                            if username.strip() == account.username:
                                import pickle
                                cookies = pickle.loads(base64.b64decode(b64data.strip()))
                                loader.context._session.cookies.update(cookies)
                                loader.context.username = account.username.split('@')[0]
                                session_loaded = True
                                logger.info(f"Loaded session for {account.username} from env var")
                                break
                except Exception as e:
                    logger.warning(f"Failed to load session from env for {account.username}: {e}")
            
            # 2. Try session file on disk
            session_file = self._settings.session_path / f"session-{account.username}"
            if session_file.exists() and not session_loaded:
                try:
                    # Load cookies directly (more reliable than load_session_from_file)
                    import pickle
                    with open(session_file, 'rb') as f:
                        cookies = pickle.load(f)
                    loader.context._session.cookies.update(cookies)
                    # Set username (without @domain part if present)
                    loader.context.username = account.username.split('@')[0]
                    session_loaded = True
                    logger.info(f"Loaded session for {account.username} from file (sessionid present: {'sessionid' in [c.name for c in cookies]})")
                except Exception as e:
                    logger.warning(f"Session file load failed for {account.username}: {e}")
            
            # 3. No session available, try fresh login
            if not session_loaded:
                try:
                    loader.login(account.username, account.password)
                    self._settings.session_path.mkdir(parents=True, exist_ok=True)
                    loader.save_session_to_file(str(session_file))
                    logger.info(f"Logged in and saved session for {account.username}")
                except Exception as e:
                    account.last_error = str(e)
                    logger.error(f"Login failed for {account.username}: {e}")
                    raise
            
            self._loaders[account.username] = loader
            return loader
    
    def _get_rotated_loader(self) -> tuple[Instaloader, Optional[AccountInfo]]:
        """
        Get a loader using account rotation if accounts are configured.
        Falls back to default loader if no accounts.
        
        Returns:
            Tuple of (loader, account_info or None)
        """
        # Try to get next available account
        account = self._account_manager.get_next_account()
        
        if account:
            try:
                loader = self._get_loader_for_account(account)
                self._current_account = account
                return loader, account
            except Exception as e:
                logger.error(f"Failed to get loader for {account.username}: {e}")
                # Mark account as having an error and try next
                account.enabled = False
                # Recursive call to try next account
                return self._get_rotated_loader()
        
        # No accounts configured or all exhausted, use default loader
        self._current_account = None
        return self._get_loader(), None
    
    def _try_auto_load_session(self) -> None:
        """
        Try to auto-load a saved session on startup.
        This runs synchronously during initialization.
        """
        try:
            session_dir = self._settings.session_path
            if not session_dir.exists():
                return
            
            # Look for session files
            session_files = list(session_dir.glob("session-*"))
            if not session_files:
                return
            
            # Use the most recently modified session
            newest_session = max(session_files, key=lambda f: f.stat().st_mtime)
            username = newest_session.name.replace("session-", "")
            
            loader = self._get_loader()
            loader.load_session_from_file(username, str(newest_session))
            
            # Skip test_login() - it's slow. Trust the session.
            self._logged_in_user = username
            logger.info(f"Auto-loaded session for {username}")
        except Exception as e:
            logger.debug(f"No session auto-loaded: {e}")
    
    def get_available_sessions(self) -> list[str]:
        """
        Get list of available saved sessions.
        
        Returns:
            List of usernames with saved sessions
        """
        session_dir = self._settings.session_path
        if not session_dir.exists():
            return []
        
        sessions = []
        for f in session_dir.glob("session-*"):
            username = f.name.replace("session-", "")
            sessions.append(username)
        
        return sessions
        return self._loader
    
    @property
    def loader(self) -> Instaloader:
        """Public property to access the loader."""
        return self._get_loader()
    
    @property
    def context(self) -> instaloader.InstaloaderContext:
        """Get the Instaloader context for low-level operations."""
        return self.loader.context
    
    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self._logged_in_user is not None
    
    @property
    def logged_in_user(self) -> Optional[str]:
        """Get the currently logged-in username."""
        return self._logged_in_user
    
    @property
    def current_account(self) -> Optional[str]:
        """Get the username of the account used for the last request."""
        return self._current_account.username if self._current_account else None
    
    @property
    def account_manager(self) -> AccountManager:
        """Get the account manager."""
        return self._account_manager
    
    async def _run_in_executor(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """
        Run a blocking function in the thread pool executor.
        
        Args:
            func: The blocking function to run
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The function result
            
        Raises:
            APIException: Mapped from Instaloader exceptions
        """
        loop = asyncio.get_event_loop()
        try:
            # Create a partial function with kwargs
            def wrapper():
                return func(*args, **kwargs)
            
            result = await loop.run_in_executor(self._executor, wrapper)
            return result
        except Exception as exc:
            logger.error(f"Error in executor: {type(exc).__name__}: {exc}")
            raise map_instaloader_exception(exc)
    
    async def _run_with_rotation(
        self,
        func: Callable[[Instaloader], T],
        require_auth: bool = False
    ) -> T:
        """
        Run a function with automatic account rotation.
        
        This method:
        1. Gets the next available account (if configured)
        2. Gets/creates a loader for that account
        3. Runs the function
        4. Tracks request count and handles rate limits
        
        Args:
            func: Function that takes a loader and returns a result
            require_auth: If True, must use an authenticated account
            
        Returns:
            The function result
            
        Raises:
            LoginRequiredError: If auth required but no accounts available
            RateLimitError: If all accounts are rate limited
        """
        loop = asyncio.get_event_loop()
        
        # Get rotated loader
        loader, account = self._get_rotated_loader()
        
        # Check if we need auth but don't have it
        if require_auth and account is None and not self._logged_in_user:
            raise LoginRequiredError("This operation requires authentication. Please login or configure accounts.")
        
        try:
            def wrapper():
                return func(loader)
            
            result = await loop.run_in_executor(self._executor, wrapper)
            
            # Record successful request
            if account:
                account.record_request()
                logger.debug(f"Request completed with account {account.username} (#{account.requests_this_hour} this hour)")
            
            return result
            
        except TooManyRequestsException as exc:
            # Handle rate limit
            if account:
                account.mark_rate_limited(duration_minutes=60)
                logger.warning(f"Rate limited on account {account.username}, will rotate to next")
            raise map_instaloader_exception(exc)
            
        except Exception as exc:
            # Record error on account
            if account:
                account.last_error = str(exc)
            logger.error(f"Error in executor: {type(exc).__name__}: {exc}")
            raise map_instaloader_exception(exc)

    # ==================== Authentication Methods ====================
    
    async def login(self, username: str, password: str) -> bool:
        """
        Login to Instagram with username and password.
        
        Args:
            username: Instagram username
            password: Instagram password
            
        Returns:
            True if login successful
            
        Raises:
            InvalidCredentialsError: If credentials are invalid
            TwoFactorRequiredError: If 2FA is needed
        """
        def _login():
            loader = self._get_loader()
            loader.login(username, password)
            return True
        
        try:
            await self._run_in_executor(_login)
            self._logged_in_user = username
            
            # Save session for future use
            await self.save_session(username)
            
            logger.info(f"Successfully logged in as {username}")
            return True
        except TwoFactorRequiredError:
            # Re-raise 2FA requirement
            raise
        except APIException:
            raise
    
    async def two_factor_login(self, username: str, code: str) -> bool:
        """
        Complete two-factor authentication.
        
        Args:
            username: Instagram username
            code: 2FA code
            
        Returns:
            True if 2FA successful
        """
        def _two_factor():
            loader = self._get_loader()
            loader.two_factor_login(code)
            return True
        
        await self._run_in_executor(_two_factor)
        self._logged_in_user = username
        await self.save_session(username)
        
        logger.info(f"2FA completed for {username}")
        return True
    
    async def load_session(self, username: str, session_file: Optional[str] = None) -> bool:
        """
        Load a saved session from file.
        
        Args:
            username: Instagram username
            session_file: Optional custom session file path
            
        Returns:
            True if session loaded successfully
        """
        def _load():
            loader = self._get_loader()
            if session_file:
                loader.load_session_from_file(username, session_file)
            else:
                default_path = self._settings.session_path / f"session-{username}"
                if default_path.exists():
                    loader.load_session_from_file(username, str(default_path))
                else:
                    raise FileNotFoundError(f"No session file found for {username}")
            return True
        
        try:
            await self._run_in_executor(_load)
            self._logged_in_user = username
            logger.info(f"Session loaded for {username}")
            return True
        except FileNotFoundError as e:
            raise AuthenticationError(str(e))
    
    async def save_session(self, username: str) -> bool:
        """
        Save the current session to file.
        
        Args:
            username: Instagram username
            
        Returns:
            True if session saved successfully
        """
        def _save():
            loader = self._get_loader()
            session_path = self._settings.session_path / f"session-{username}"
            loader.save_session_to_file(str(session_path))
            return True
        
        await self._run_in_executor(_save)
        logger.info(f"Session saved for {username}")
        return True
    
    async def test_login(self) -> Optional[str]:
        """
        Test if the current session is valid.
        
        Returns:
            Username if logged in, None otherwise
        """
        def _test():
            loader = self._get_loader()
            return loader.test_login()
        
        try:
            result = await self._run_in_executor(_test)
            return result
        except Exception:
            return None
    
    async def logout(self) -> bool:
        """
        Logout and clear the current session.
        
        Returns:
            True if logout successful
        """
        with self._loader_lock:
            if self._loader is not None:
                self._loader.close()
                self._loader = None
            self._logged_in_user = None
        
        logger.info("Logged out successfully")
        return True
    
    # ==================== Profile Methods ====================
    
    async def get_profile(self, username: str) -> Profile:
        """
        Get profile information by username.
        Uses automatic account rotation if accounts are configured.
        
        Args:
            username: Instagram username
            
        Returns:
            Profile object
            
        Raises:
            ProfileNotFoundError: If profile doesn't exist
        """
        def _get(loader: Instaloader):
            return Profile.from_username(loader.context, username)
        
        try:
            return await self._run_with_rotation(_get, require_auth=False)
        except APIException as e:
            if "not found" in str(e).lower() or e.error_code == "PROFILE_NOT_FOUND":
                raise ProfileNotFoundError(username)
            raise
    
    async def get_profile_by_id(self, user_id: int) -> Profile:
        """
        Get profile information by user ID.
        Uses automatic account rotation if accounts are configured.
        
        Args:
            user_id: Instagram user ID
            
        Returns:
            Profile object
        """
        def _get(loader: Instaloader):
            return Profile.from_id(loader.context, user_id)
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    async def get_followers(
        self,
        username: str,
        limit: int = 50
    ) -> Iterator[Profile]:
        """
        Get followers of a profile.
        Requires authentication.
        
        Args:
            username: Instagram username
            limit: Maximum number of followers to return
            
        Returns:
            Iterator of Profile objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            followers = []
            for i, follower in enumerate(profile.get_followers()):
                if i >= limit:
                    break
                followers.append(follower)
            return followers
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_followees(
        self,
        username: str,
        limit: int = 50
    ) -> Iterator[Profile]:
        """
        Get accounts followed by a profile.
        
        Args:
            username: Instagram username
            limit: Maximum number of followees to return
            
        Returns:
            Iterator of Profile objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            followees = []
            for i, followee in enumerate(profile.get_followees()):
                if i >= limit:
                    break
                followees.append(followee)
            return followees
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_similar_accounts(
        self,
        username: str,
        limit: int = 10
    ) -> list[Profile]:
        """
        Get similar/suggested accounts for a profile.
        
        Args:
            username: Instagram username
            limit: Maximum number of suggestions
            
        Returns:
            List of Profile objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            similar = []
            for i, account in enumerate(profile.get_similar_accounts()):
                if i >= limit:
                    break
                similar.append(account)
            return similar
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    # ==================== Post Methods ====================
    
    async def get_post(self, shortcode: str) -> Post:
        """
        Get a post by its shortcode.
        Requires authentication.
        
        Args:
            shortcode: Post shortcode (from URL)
            
        Returns:
            Post object
            
        Raises:
            PostNotFoundError: If post doesn't exist
        """
        def _get(loader: Instaloader):
            return Post.from_shortcode(loader.context, shortcode)
        
        try:
            return await self._run_with_rotation(_get, require_auth=True)
        except APIException as e:
            if "not found" in str(e).lower():
                raise PostNotFoundError(shortcode)
            raise
    
    async def get_post_basic_info(self, shortcode: str) -> dict:
        """
        Get basic post info by scraping Instagram's public web page.
        This works without authentication but provides limited data.
        
        Args:
            shortcode: Post shortcode (from URL)
            
        Returns:
            Dictionary with basic post info extracted from the page
        """
        import httpx
        import re
        import json
        
        url = f"https://www.instagram.com/p/{shortcode}/"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                raise PostNotFoundError(shortcode)
            elif response.status_code != 200:
                raise ServiceUnavailableError(f"Instagram returned {response.status_code}")
            
            html = response.text
            
            # Try to extract data from meta tags
            result = {
                "shortcode": shortcode,
                "url": url,
            }
            
            # Extract title/caption from meta tag
            title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            if title_match:
                result["title"] = title_match.group(1)
            
            # Extract description
            desc_match = re.search(r'<meta property="og:description" content="([^"]*)"', html)
            if desc_match:
                result["description"] = desc_match.group(1)
            
            # Extract image URL
            image_match = re.search(r'<meta property="og:image" content="([^"]*)"', html)
            if image_match:
                result["thumbnail_url"] = image_match.group(1)
            
            # Extract video URL if present
            video_match = re.search(r'<meta property="og:video" content="([^"]*)"', html)
            if video_match:
                result["video_url"] = video_match.group(1)
                result["is_video"] = True
            else:
                result["is_video"] = False
            
            # Extract type
            type_match = re.search(r'<meta property="og:type" content="([^"]*)"', html)
            if type_match:
                result["type"] = type_match.group(1)
            
            # Try to extract username from title or URL
            username_match = re.search(r'@(\w+)', result.get("title", ""))
            if username_match:
                result["author_username"] = username_match.group(1)
            
            # Check if we got any useful data
            if not result.get("thumbnail_url") and not result.get("title"):
                raise ServiceUnavailableError(
                    "Could not extract post data. Instagram may require login for this post."
                )
            
            return result
    
    async def get_profile_posts(
        self,
        username: str,
        limit: int = 12
    ) -> list[Post]:
        """
        Get posts from a profile.
        
        Args:
            username: Instagram username
            limit: Maximum number of posts to return
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            posts = []
            for i, post in enumerate(profile.get_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    async def get_post_comments(
        self,
        shortcode: str,
        limit: int = 50
    ) -> list[dict]:
        """
        Get comments on a post.
        
        Args:
            shortcode: Post shortcode
            limit: Maximum number of comments
            
        Returns:
            List of comment dictionaries
        """
        def _get(loader: Instaloader):
            post = Post.from_shortcode(loader.context, shortcode)
            comments = []
            for i, comment in enumerate(post.get_comments()):
                if i >= limit:
                    break
                comments.append({
                    "id": comment.id,
                    "text": comment.text,
                    "owner_username": comment.owner.username,
                    "owner_id": comment.owner.userid,
                    "created_at": comment.created_at_utc,
                    "likes_count": comment.likes_count,
                })
            return comments
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_post_likes(
        self,
        shortcode: str,
        limit: int = 50
    ) -> list[dict]:
        """
        Get users who liked a post.
        
        Args:
            shortcode: Post shortcode
            limit: Maximum number of likers
            
        Returns:
            List of user dictionaries
        """
        def _get(loader: Instaloader):
            post = Post.from_shortcode(loader.context, shortcode)
            likes = []
            for i, profile in enumerate(post.get_likes()):
                if i >= limit:
                    break
                likes.append({
                    "username": profile.username,
                    "user_id": profile.userid,
                    "full_name": profile.full_name,
                })
            return likes
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_tagged_posts(
        self,
        username: str,
        limit: int = 12
    ) -> list[Post]:
        """
        Get posts where a user is tagged.
        
        Args:
            username: Instagram username
            limit: Maximum number of posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            posts = []
            for i, post in enumerate(profile.get_tagged_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_reels(
        self,
        username: str,
        limit: int = 12
    ) -> list[Post]:
        """
        Get reels from a profile.
        
        Args:
            username: Instagram username
            limit: Maximum number of reels
            
        Returns:
            List of Post objects (reels)
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            reels = []
            for i, post in enumerate(profile.get_reels()):
                if i >= limit:
                    break
                reels.append(post)
            return reels
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    async def get_igtv_posts(
        self,
        username: str,
        limit: int = 12
    ) -> list[Post]:
        """
        Get IGTV posts from a profile.
        
        Args:
            username: Instagram username
            limit: Maximum number of IGTV posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            posts = []
            for i, post in enumerate(profile.get_igtv_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    # ==================== Hashtag Methods ====================
    
    async def get_hashtag(self, name: str) -> Hashtag:
        """
        Get hashtag information.
        
        Args:
            name: Hashtag name (without #)
            
        Returns:
            Hashtag object
        """
        def _get(loader: Instaloader):
            return Hashtag.from_name(loader.context, name)
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    async def get_hashtag_posts(
        self,
        name: str,
        limit: int = 12,
        top_posts_only: bool = False
    ) -> list[Post]:
        """
        Get posts for a hashtag.
        
        Args:
            name: Hashtag name (without #)
            limit: Maximum number of posts
            top_posts_only: Only return top posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            hashtag = Hashtag.from_name(loader.context, name)
            posts = []
            iterator = hashtag.get_top_posts() if top_posts_only else hashtag.get_posts_resumable()
            for i, post in enumerate(iterator):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=False)
    
    # ==================== Story Methods ====================
    
    async def get_stories(
        self,
        user_ids: Optional[list[int]] = None
    ) -> Iterator[Story]:
        """
        Get stories from followed users or specific users.
        
        Args:
            user_ids: Optional list of user IDs (None for all followed)
            
        Returns:
            Iterator of Story objects
        """
        def _get(loader: Instaloader):
            return list(loader.get_stories(user_ids))
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_user_stories(self, username: str) -> list[Story]:
        """
        Get stories from a specific user.
        
        Args:
            username: Instagram username
            
        Returns:
            List of Story objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            return list(loader.get_stories([profile.userid]))
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_highlights(
        self,
        username: str,
        include_items: bool = False
    ) -> list[Highlight]:
        """
        Get highlights from a profile.
        
        Args:
            username: Instagram username
            include_items: Whether to fetch items for each highlight
            
        Returns:
            List of Highlight objects
        """
        def _get(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            highlights = list(loader.get_highlights(profile))
            if include_items:
                # Pre-fetch items for each highlight
                for highlight in highlights:
                    list(highlight.get_items())  # Force iteration to cache items
            return highlights
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    # ==================== Search Methods ====================
    
    async def search(self, query: str) -> TopSearchResults:
        """
        Search Instagram for profiles, hashtags, and locations.
        
        Args:
            query: Search query
            
        Returns:
            TopSearchResults object
        """
        def _search(loader: Instaloader):
            return TopSearchResults(loader.context, query)
        
        return await self._run_with_rotation(_search, require_auth=False)
    
    # ==================== Feed Methods ====================
    
    async def get_feed_posts(self, limit: int = 12) -> list[Post]:
        """
        Get posts from the user's feed.
        
        Args:
            limit: Maximum number of posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            posts = []
            for i, post in enumerate(loader.get_feed_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_explore_posts(self, limit: int = 12) -> list[Post]:
        """
        Get posts from the explore page.
        
        Args:
            limit: Maximum number of posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            posts = []
            for i, post in enumerate(loader.get_explore_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    async def get_saved_posts(self, limit: int = 12) -> list[Post]:
        """
        Get the user's saved posts.
        
        Args:
            limit: Maximum number of posts
            
        Returns:
            List of Post objects
        """
        def _get(loader: Instaloader):
            if not self._logged_in_user:
                raise LoginRequiredException("get_saved_posts")
            profile = Profile.from_username(loader.context, self._logged_in_user)
            posts = []
            for i, post in enumerate(profile.get_saved_posts()):
                if i >= limit:
                    break
                posts.append(post)
            return posts
        
        return await self._run_with_rotation(_get, require_auth=True)
    
    # ==================== Download Methods ====================
    
    async def download_post(self, shortcode: str, target: Optional[str] = None) -> bool:
        """
        Download a post and its media.
        
        Args:
            shortcode: Post shortcode
            target: Optional custom target directory
            
        Returns:
            True if download successful
        """
        def _download(loader: Instaloader):
            post = Post.from_shortcode(loader.context, shortcode)
            target_dir = target or post.owner_username
            return loader.download_post(post, target=target_dir)
        
        return await self._run_with_rotation(_download, require_auth=True)
    
    async def download_profile_picture(self, username: str) -> bool:
        """
        Download a profile's picture.
        
        Args:
            username: Instagram username
            
        Returns:
            True if download successful
        """
        def _download(loader: Instaloader):
            profile = Profile.from_username(loader.context, username)
            loader.download_profilepic(profile)
            return True
        
        return await self._run_with_rotation(_download, require_auth=False)
    
    async def download_story_item(
        self,
        item: StoryItem,
        target: Optional[str] = None
    ) -> bool:
        """
        Download a story item.
        
        Args:
            item: StoryItem object
            target: Optional custom target directory
            
        Returns:
            True if download successful
        """
        def _download(loader: Instaloader):
            target_dir = target or item.owner_username
            return loader.download_storyitem(item, target=target_dir)
        
        return await self._run_with_rotation(_download, require_auth=True)
    
    # ==================== Cleanup ====================
    
    def shutdown(self):
        """Shutdown the service and cleanup resources."""
        logger.info("Shutting down InstaloaderService")
        
        # Close all account loaders
        with self._loader_lock:
            for username, loader in self._loaders.items():
                try:
                    loader.close()
                    logger.debug(f"Closed loader for {username}")
                except Exception:
                    pass
            self._loaders.clear()
            
            # Close the default loader
            if self._loader is not None:
                self._loader.close()
                self._loader = None
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("InstaloaderService shutdown complete")


# Singleton instance
_service_instance: Optional[InstaloaderService] = None


def get_instaloader_service() -> InstaloaderService:
    """
    Get the singleton InstaloaderService instance.
    Used as a FastAPI dependency.
    
    Returns:
        InstaloaderService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = InstaloaderService()
    return _service_instance
