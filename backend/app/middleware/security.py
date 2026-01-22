"""Enhanced security middleware with stricter CSP and additional protections."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enhanced security middleware with CREST compliance improvements.
    
    Changes from original:
    - Removed 'unsafe-inline' from CSP in production
    - Increased HSTS to 2 years (CREST requirement)
    - Added Cross-Origin-* policies
    - Added X-Permitted-Cross-Domain-Policies
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        environment = os.getenv("ENVIRONMENT", "development")
        
        # Prevent clickjacking - page cannot be embedded in iframes
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS filter in browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HTTP Strict Transport Security - UPGRADED to 2 years for CREST compliance
        # includeSubDomains ensures all subdomains also use HTTPS
        # preload allows browser preload lists
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        
        # Content Security Policy - PRODUCTION removes unsafe-inline
        if environment == "production":
            # STRICT CSP for production - no unsafe-inline
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
                "style-src 'self' https://cdn.jsdelivr.net",
                "font-src 'self' https://cdn.jsdelivr.net",
                "img-src 'self' data: https:",
                "connect-src 'self' https://charitiescommissionenrichment-production.up.railway.app",
                "frame-ancestors 'none'",
                "form-action 'self'",
                "base-uri 'self'",
            ]
        else:
            # Development - keep unsafe-inline for easier development
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "font-src 'self' https://cdn.jsdelivr.net",
                "img-src 'self' data: https:",
                "connect-src 'self' https://charitiescommissionenrichment-production.up.railway.app",
                "frame-ancestors 'none'",
                "form-action 'self'",
                "base-uri 'self'",
            ]
        
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Permissions Policy - disable unnecessary browser features
        permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)
        
        # NEW: Cross-Origin policies for additional security
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        
        # NEW: Prevent Adobe Flash/PDF cross-domain policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        # Prevent caching of sensitive data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
