"""Rate limiting and account lockout service."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import structlog

logger = structlog.get_logger()


class LoginRateLimiter:
    """
    In-memory rate limiter for login attempts.
    
    Implements account lockout after too many failed attempts:
    - Tracks failed attempts per email/IP
    - Locks accounts after MAX_ATTEMPTS failures
    - Auto-unlocks after LOCKOUT_DURATION
    - Logs all security events
    
    For production, consider using Redis for distributed rate limiting.
    """
    
    MAX_ATTEMPTS: int = 5  # Lock after 5 failed attempts
    LOCKOUT_DURATION: int = 15  # Lock for 15 minutes
    ATTEMPT_WINDOW: int = 15  # Track attempts within 15-minute window
    
    def __init__(self):
        # Track failed attempts: {identifier: [(timestamp, ip), ...]}
        self._failed_attempts: Dict[str, list] = defaultdict(list)
        # Track lockouts: {identifier: unlock_time}
        self._lockouts: Dict[str, datetime] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def _get_identifier(self, email: str, ip: Optional[str] = None) -> str:
        """Get identifier for rate limiting (email is primary)."""
        return email.lower()
    
    def _clean_old_attempts(self, identifier: str) -> None:
        """Remove attempts older than the window."""
        cutoff = datetime.utcnow() - timedelta(minutes=self.ATTEMPT_WINDOW)
        self._failed_attempts[identifier] = [
            (ts, ip) for ts, ip in self._failed_attempts[identifier]
            if ts > cutoff
        ]
    
    async def is_locked(self, email: str, ip: Optional[str] = None) -> Tuple[bool, Optional[int]]:
        """
        Check if account is locked.
        
        Returns:
            (is_locked, seconds_remaining) - seconds_remaining is None if not locked
        """
        identifier = self._get_identifier(email, ip)
        
        async with self._lock:
            if identifier in self._lockouts:
                unlock_time = self._lockouts[identifier]
                if datetime.utcnow() < unlock_time:
                    remaining = int((unlock_time - datetime.utcnow()).total_seconds())
                    return True, remaining
                else:
                    # Lockout expired, remove it
                    del self._lockouts[identifier]
                    self._failed_attempts[identifier] = []
            
            return False, None
    
    async def record_failed_attempt(self, email: str, ip: Optional[str] = None) -> Tuple[bool, int]:
        """
        Record a failed login attempt.
        
        Returns:
            (is_now_locked, attempts_remaining)
        """
        identifier = self._get_identifier(email, ip)
        
        async with self._lock:
            self._clean_old_attempts(identifier)
            
            # Record this attempt
            self._failed_attempts[identifier].append((datetime.utcnow(), ip))
            attempt_count = len(self._failed_attempts[identifier])
            
            # Log the failed attempt
            logger.warning(
                "Failed login attempt",
                email=email,
                ip=ip,
                attempt_count=attempt_count,
                max_attempts=self.MAX_ATTEMPTS,
            )
            
            # Check if we should lock
            if attempt_count >= self.MAX_ATTEMPTS:
                unlock_time = datetime.utcnow() + timedelta(minutes=self.LOCKOUT_DURATION)
                self._lockouts[identifier] = unlock_time
                
                logger.error(
                    "Account locked due to too many failed attempts",
                    email=email,
                    ip=ip,
                    lockout_minutes=self.LOCKOUT_DURATION,
                    unlock_time=unlock_time.isoformat(),
                )
                
                return True, 0
            
            return False, self.MAX_ATTEMPTS - attempt_count
    
    async def record_successful_login(self, email: str, ip: Optional[str] = None) -> None:
        """Clear failed attempts after successful login."""
        identifier = self._get_identifier(email, ip)
        
        async with self._lock:
            if identifier in self._failed_attempts:
                del self._failed_attempts[identifier]
            if identifier in self._lockouts:
                del self._lockouts[identifier]
        
        logger.info(
            "Successful login",
            email=email,
            ip=ip,
        )
    
    async def get_attempt_count(self, email: str) -> int:
        """Get current failed attempt count for an email."""
        identifier = self._get_identifier(email)
        
        async with self._lock:
            self._clean_old_attempts(identifier)
            return len(self._failed_attempts[identifier])


# Global instance
login_rate_limiter = LoginRateLimiter()
