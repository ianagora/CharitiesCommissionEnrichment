"""Enhanced security middleware with stricter CSP and additional protections."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enhanced security middleware with CREST compliance improvements.
    
    SECURITY UPDATE: Always uses strict CSP (no 'unsafe-inline')
    - Removes XSS vulnerability in all environments
    - CREST pen test ready
    - Best practice: security-by-default
    
    Changes from original:
    - ALWAYS strict CSP (no unsafe-inline) - CREST requirement
    - Increased HSTS to 2 years - CREST requirement
    - Added Cross-Origin-* policies
    - Added X-Permitted-Cross-Domain-Policies
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
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
        
        # Content Security Policy - ALWAYS STRICT (no unsafe-inline)
        # This removes the XSS vulnerability and ensures CREST compliance
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
        
        # Cross-Origin policies for additional security
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        
        # Prevent Adobe Flash/PDF cross-domain policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        # Prevent caching of sensitive data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
