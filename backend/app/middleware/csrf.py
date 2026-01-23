"""CSRF Protection Middleware using Double-Submit Cookie Pattern."""
import secrets
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog

from app.config import settings

logger = structlog.get_logger()

# Constants
CSRF_TOKEN_LENGTH = 32
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Paths that don't require CSRF protection (public endpoints)
CSRF_EXEMPT_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection using the Double-Submit Cookie pattern.
    
    How it works:
    1. Server sets a CSRF token in a cookie (not httpOnly, so JS can read it)
    2. Client must include the same token in the X-CSRF-Token header
    3. Server validates that cookie value matches header value
    
    This pattern is effective because:
    - Attackers cannot read cross-origin cookies
    - Cookie is bound to the domain
    - The token is random and unpredictable
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip CSRF for safe methods (they shouldn't modify state)
        if request.method in CSRF_SAFE_METHODS:
            response = await call_next(request)
            # Ensure CSRF cookie exists for future requests
            self._ensure_csrf_cookie(request, response)
            return response
        
        # Skip CSRF for exempt paths
        path = request.url.path.rstrip("/")
        if path in CSRF_EXEMPT_PATHS or any(path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            response = await call_next(request)
            self._ensure_csrf_cookie(request, response)
            return response
        
        # Validate CSRF token for state-changing requests
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        
        if not cookie_token or not header_token:
            logger.warning(
                "CSRF validation failed - missing token",
                path=request.url.path,
                has_cookie=bool(cookie_token),
                has_header=bool(header_token),
                client_ip=request.client.host if request.client else None,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )
        
        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning(
                "CSRF validation failed - token mismatch",
                path=request.url.path,
                client_ip=request.client.host if request.client else None,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid"},
            )
        
        # CSRF valid - proceed with request
        response = await call_next(request)
        return response
    
    def _ensure_csrf_cookie(self, request: Request, response: Response) -> None:
        """Ensure CSRF cookie exists, create new one if not."""
        if CSRF_COOKIE_NAME not in request.cookies:
            token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=token,
                max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=False,  # Must be readable by JavaScript
                secure=not settings.DEBUG,  # Secure in production
                samesite="strict",  # Strict SameSite policy
                path="/",
            )
