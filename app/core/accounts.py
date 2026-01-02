"""
Multi-account manager for Instagram account rotation.
Handles loading, rotating, and managing multiple Instagram accounts.
"""

import json
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from app.core.logging import logger


@dataclass
class AccountInfo:
    """Information about an Instagram account."""
    username: str
    password: str
    enabled: bool = True
    notes: str = ""
    
    # Runtime tracking (not persisted)
    requests_this_hour: int = field(default=0, repr=False)
    last_request_time: Optional[datetime] = field(default=None, repr=False)
    rate_limited_until: Optional[datetime] = field(default=None, repr=False)
    last_error: Optional[str] = field(default=None, repr=False)
    
    @property
    def is_available(self) -> bool:
        """Check if account is available for use."""
        if not self.enabled:
            return False
        
        # Check if rate limited
        if self.rate_limited_until:
            if datetime.now() < self.rate_limited_until:
                return False
            # Rate limit expired, reset
            self.rate_limited_until = None
            self.requests_this_hour = 0
        
        # Check hourly request limit (conservative: 150/hour to stay safe)
        if self.requests_this_hour >= 150:
            return False
        
        return True
    
    def record_request(self):
        """Record that a request was made with this account."""
        self.requests_this_hour += 1
        self.last_request_time = datetime.now()
    
    def mark_rate_limited(self, duration_minutes: int = 60):
        """Mark account as rate limited."""
        self.rate_limited_until = datetime.now() + timedelta(minutes=duration_minutes)
        logger.warning(f"Account {self.username} rate limited until {self.rate_limited_until}")
    
    def reset_hourly_counter(self):
        """Reset the hourly request counter."""
        self.requests_this_hour = 0


class AccountManager:
    """
    Manages multiple Instagram accounts with rotation.
    
    Features:
    - Round-robin rotation
    - Automatic rate limit detection
    - Health tracking per account
    - Persistent configuration
    """
    
    _instance: Optional["AccountManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "AccountManager":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        self._initialized = True
        self._accounts: list[AccountInfo] = []
        self._current_index = 0
        self._accounts_lock = threading.Lock()
        
        # Hourly reset thread
        self._start_hourly_reset()
        
        logger.info("AccountManager initialized")
    
    def load_from_file(self, filepath: str = "accounts.json") -> int:
        """
        Load accounts from a JSON file.
        
        Args:
            filepath: Path to accounts JSON file
            
        Returns:
            Number of accounts loaded
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Accounts file not found: {filepath}")
            return 0
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            with self._accounts_lock:
                self._accounts = []
                for acc in data.get("accounts", []):
                    self._accounts.append(AccountInfo(
                        username=acc["username"],
                        password=acc["password"],
                        enabled=acc.get("enabled", True),
                        notes=acc.get("notes", "")
                    ))
            
            enabled_count = sum(1 for a in self._accounts if a.enabled)
            logger.info(f"Loaded {len(self._accounts)} accounts ({enabled_count} enabled)")
            return len(self._accounts)
            
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
            return 0
    
    def load_from_env(self) -> int:
        """
        Load accounts from environment variables.
        Format: INSTAGRAM_ACCOUNTS=user1:pass1,user2:pass2
        
        Returns:
            Number of accounts loaded
        """
        import os
        accounts_str = os.getenv("INSTAGRAM_ACCOUNTS", "")
        
        if not accounts_str:
            return 0
        
        with self._accounts_lock:
            for pair in accounts_str.split(","):
                if ":" in pair:
                    username, password = pair.split(":", 1)
                    self._accounts.append(AccountInfo(
                        username=username.strip(),
                        password=password.strip()
                    ))
        
        logger.info(f"Loaded {len(self._accounts)} accounts from environment")
        return len(self._accounts)
    
    def add_account(self, username: str, password: str, notes: str = "") -> bool:
        """Add a new account."""
        with self._accounts_lock:
            # Check for duplicates
            if any(a.username == username for a in self._accounts):
                logger.warning(f"Account {username} already exists")
                return False
            
            self._accounts.append(AccountInfo(
                username=username,
                password=password,
                notes=notes
            ))
            logger.info(f"Added account: {username}")
            return True
    
    def remove_account(self, username: str) -> bool:
        """Remove an account by username."""
        with self._accounts_lock:
            for i, acc in enumerate(self._accounts):
                if acc.username == username:
                    del self._accounts[i]
                    logger.info(f"Removed account: {username}")
                    return True
        return False
    
    def get_next_account(self) -> Optional[AccountInfo]:
        """
        Get the next available account using round-robin.
        
        Returns:
            AccountInfo or None if no accounts available
        """
        with self._accounts_lock:
            if not self._accounts:
                return None
            
            # Try round-robin first
            attempts = 0
            while attempts < len(self._accounts):
                account = self._accounts[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._accounts)
                
                if account.is_available:
                    return account
                
                attempts += 1
            
            # All accounts exhausted
            logger.error("All accounts are rate limited or disabled!")
            return None
    
    def get_random_account(self) -> Optional[AccountInfo]:
        """Get a random available account."""
        with self._accounts_lock:
            available = [a for a in self._accounts if a.is_available]
            if not available:
                return None
            return random.choice(available)
    
    def get_account_by_username(self, username: str) -> Optional[AccountInfo]:
        """Get a specific account by username."""
        with self._accounts_lock:
            for acc in self._accounts:
                if acc.username == username:
                    return acc
        return None
    
    def get_stats(self) -> dict:
        """Get statistics about all accounts."""
        with self._accounts_lock:
            total = len(self._accounts)
            enabled = sum(1 for a in self._accounts if a.enabled)
            available = sum(1 for a in self._accounts if a.is_available)
            rate_limited = sum(1 for a in self._accounts if a.rate_limited_until and datetime.now() < a.rate_limited_until)
            
            return {
                "total_accounts": total,
                "enabled": enabled,
                "available_now": available,
                "rate_limited": rate_limited,
                "accounts": [
                    {
                        "username": a.username,
                        "enabled": a.enabled,
                        "available": a.is_available,
                        "requests_this_hour": a.requests_this_hour,
                        "rate_limited_until": a.rate_limited_until.isoformat() if a.rate_limited_until else None,
                        "last_error": a.last_error,
                        "notes": a.notes
                    }
                    for a in self._accounts
                ]
            }
    
    def _start_hourly_reset(self):
        """Start background thread to reset hourly counters."""
        def reset_loop():
            while True:
                time.sleep(3600)  # 1 hour
                with self._accounts_lock:
                    for acc in self._accounts:
                        acc.reset_hourly_counter()
                logger.debug("Reset hourly request counters for all accounts")
        
        thread = threading.Thread(target=reset_loop, daemon=True)
        thread.start()
    
    @property
    def account_count(self) -> int:
        """Get total number of accounts."""
        return len(self._accounts)
    
    @property
    def available_count(self) -> int:
        """Get number of currently available accounts."""
        return sum(1 for a in self._accounts if a.is_available)


# Global instance getter
def get_account_manager() -> AccountManager:
    """Get the global AccountManager instance."""
    return AccountManager()
