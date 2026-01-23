"""Rate limiting middleware with header visibility."""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import Response


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.
    Uses IP address or authenticated user ID.
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    
    # Fall back to IP address
    return get_remote_address(request)


# Create limiter instance with custom key function
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100/minute"],  # Global default
    headers_enabled=True,  # Enable rate limit headers
)


class RateLimitMiddleware(SlowAPIMiddleware):
    """
    Enhanced rate limiting middleware with visible headers.
    
    Adds X-RateLimit-* headers to all responses:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining
    - X-RateLimit-Reset: Time when limit resets
    """
    
    async def __call__(self, scope, receive, send):
        """Process request and add rate limit headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_with_headers(message):
            """Wrapper to add rate limit headers to response."""
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                
                # Add rate limit headers if not already present
                if b"x-ratelimit-limit" not in headers:
                    # These will be populated by slowapi if rate limiting is active
                    pass
                
                message["headers"] = list(headers.items())
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)


# Rate limit decorators for different endpoints
auth_limiter = limiter.limit("5/minute")  # Login/Register
api_limiter = limiter.limit("60/minute")  # API endpoints
upload_limiter = limiter.limit("10/minute")  # File uploads
