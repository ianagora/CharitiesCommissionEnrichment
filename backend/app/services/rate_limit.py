"""Rate limiting and account lockout service with Redis support."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import structlog

from app.config import settings

logger = structlog.get_logger()

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed - using in-memory rate limiting")


class RedisRateLimiter:
    """
    Redis-backed rate limiter for distributed deployments.
    
    Uses Redis sorted sets to track failed attempts with timestamps,
    allowing for accurate time-window based rate limiting across
    multiple server instances.
    """
    
    MAX_ATTEMPTS: int = settings.LOGIN_MAX_ATTEMPTS
    LOCKOUT_DURATION: int = settings.LOGIN_LOCKOUT_MINUTES
    ATTEMPT_WINDOW: int = settings.LOGIN_LOCKOUT_MINUTES
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
    
    def _get_attempts_key(self, email: str) -> str:
        """Get Redis key for tracking login attempts."""
        return f"login_attempts:{email.lower()}"
    
    def _get_lockout_key(self, email: str) -> str:
        """Get Redis key for lockout status."""
        return f"login_lockout:{email.lower()}"
    
    async def is_locked(self, email: str, ip: Optional[str] = None) -> Tuple[bool, Optional[int]]:
        """Check if account is locked."""
        try:
            client = await self.get_client()
            lockout_key = self._get_lockout_key(email)
            
            ttl = await client.ttl(lockout_key)
            if ttl > 0:
                return True, ttl
            
            return False, None
        except Exception as e:
            logger.error("Redis error in is_locked", error=str(e))
            return False, None
    
    async def record_failed_attempt(self, email: str, ip: Optional[str] = None) -> Tuple[bool, int]:
        """Record a failed login attempt."""
        try:
            client = await self.get_client()
            attempts_key = self._get_attempts_key(email)
            lockout_key = self._get_lockout_key(email)
            
            # Current timestamp
            now = datetime.utcnow().timestamp()
            window_start = now - (self.ATTEMPT_WINDOW * 60)
            
            # Add this attempt to sorted set (score = timestamp)
            await client.zadd(attempts_key, {f"{now}:{ip or 'unknown'}": now})
            
            # Remove attempts outside the window
            await client.zremrangebyscore(attempts_key, 0, window_start)
            
            # Set expiry on the attempts key
            await client.expire(attempts_key, self.ATTEMPT_WINDOW * 60 + 60)
            
            # Count attempts in window
            attempt_count = await client.zcard(attempts_key)
            
            logger.warning(
                "Failed login attempt",
                email=email,
                ip=ip,
                attempt_count=attempt_count,
                max_attempts=self.MAX_ATTEMPTS,
            )
            
            # Check if we should lock
            if attempt_count >= self.MAX_ATTEMPTS:
                # Set lockout
                await client.setex(
                    lockout_key,
                    self.LOCKOUT_DURATION * 60,
                    "locked"
                )
                
                logger.error(
                    "Account locked due to too many failed attempts",
                    email=email,
                    ip=ip,
                    lockout_minutes=self.LOCKOUT_DURATION,
                )
                
                return True, 0
            
            return False, self.MAX_ATTEMPTS - attempt_count
            
        except Exception as e:
            logger.error("Redis error in record_failed_attempt", error=str(e))
            return False, self.MAX_ATTEMPTS
    
    async def record_successful_login(self, email: str, ip: Optional[str] = None) -> None:
        """Clear failed attempts after successful login."""
        try:
            client = await self.get_client()
            attempts_key = self._get_attempts_key(email)
            lockout_key = self._get_lockout_key(email)
            
            # Clear attempts and lockout
            await client.delete(attempts_key, lockout_key)
            
            logger.info("Successful login", email=email, ip=ip)
            
        except Exception as e:
            logger.error("Redis error in record_successful_login", error=str(e))
    
    async def get_attempt_count(self, email: str) -> int:
        """Get current failed attempt count for an email."""
        try:
            client = await self.get_client()
            attempts_key = self._get_attempts_key(email)
            
            # Remove old attempts first
            now = datetime.utcnow().timestamp()
            window_start = now - (self.ATTEMPT_WINDOW * 60)
            await client.zremrangebyscore(attempts_key, 0, window_start)
            
            return await client.zcard(attempts_key)
            
        except Exception as e:
            logger.error("Redis error in get_attempt_count", error=str(e))
            return 0


class InMemoryRateLimiter:
    """
    In-memory rate limiter for single-instance deployments.
    
    Note: This resets on server restart and doesn't work
    across multiple instances. Use Redis for production.
    """
    
    MAX_ATTEMPTS: int = settings.LOGIN_MAX_ATTEMPTS
    LOCKOUT_DURATION: int = settings.LOGIN_LOCKOUT_MINUTES
    ATTEMPT_WINDOW: int = settings.LOGIN_LOCKOUT_MINUTES
    
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
        """Check if account is locked."""
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
        """Record a failed login attempt."""
        identifier = self._get_identifier(email, ip)
        
        async with self._lock:
            self._clean_old_attempts(identifier)
            
            # Record this attempt
            self._failed_attempts[identifier].append((datetime.utcnow(), ip))
            attempt_count = len(self._failed_attempts[identifier])
            
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
        
        logger.info("Successful login", email=email, ip=ip)
    
    async def get_attempt_count(self, email: str) -> int:
        """Get current failed attempt count for an email."""
        identifier = self._get_identifier(email)
        
        async with self._lock:
            self._clean_old_attempts(identifier)
            return len(self._failed_attempts[identifier])


def create_rate_limiter():
    """
    Factory function to create the appropriate rate limiter.
    
    Uses Redis if REDIS_URL is configured and redis package is installed,
    otherwise falls back to in-memory rate limiting.
    """
    if settings.REDIS_URL and REDIS_AVAILABLE:
        logger.info("Using Redis-backed rate limiter", redis_url=settings.REDIS_URL.split("@")[-1])
        return RedisRateLimiter(settings.REDIS_URL)
    else:
        if settings.REDIS_URL and not REDIS_AVAILABLE:
            logger.warning("REDIS_URL configured but redis package not installed - using in-memory")
        else:
            logger.info("Using in-memory rate limiter (set REDIS_URL for distributed deployments)")
        return InMemoryRateLimiter()


# Global instance - created at import time
login_rate_limiter = create_rate_limiter()
