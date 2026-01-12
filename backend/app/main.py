"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from app.config import settings
from app.database import init_db, close_db
from app.api import api_router
from app.middleware.security import SecurityHeadersMiddleware

# Configure Python logging to use stdout/stderr
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
)

# Configure structured logging with console renderer for Railway visibility
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # Use ConsoleRenderer for Railway logs (easier to read)
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=False,  # Allow log level changes
)

# Print startup log level
print(f"[STARTUP] Log level set to: {settings.LOG_LEVEL}", file=sys.stdout, flush=True)

logger = structlog.get_logger()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting application", app_name=settings.APP_NAME)
    
    # Try to initialize database, but don't fail if it's not ready
    # This allows the health endpoint to work while DB is still starting
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database initialization failed - will retry on first request", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning("Error closing database connections", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Charity Commission Data Enrichment Platform API
    
    ## Features
    - Entity batch upload (CSV/Excel)
    - Auto-resolution to Charity Commission records
    - Recursive corporate ownership tree building
    - Multi-tab Excel export
    - JWT authentication
    - Rate limiting and security
    """,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security headers middleware (must be added before CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS with explicit methods and headers (no wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=settings.cors_methods_list,  # Explicit methods, not "*"
    allow_headers=settings.cors_headers_list,  # Explicit headers, not "*"
    expose_headers=["X-Request-ID"],  # Headers client can access
    max_age=600,  # Cache preflight requests for 10 minutes
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.utcnow()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    # Log request (skip health checks)
    if not request.url.path.startswith("/api/v1/health"):
        logger.info(
            "Request processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration,
            client_ip=request.client.host if request.client else None,
        )
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions securely."""
    import traceback
    
    # Generate a unique error ID for correlation (don't expose timestamp)
    error_id = str(uuid4())[:8]
    
    # Log full details server-side only
    logger.error(
        "Unhandled exception",
        error_id=error_id,
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
        client_ip=request.client.host if request.client else None,
    )
    
    # Print to stderr for Railway logs (full details for debugging)
    print(f"[ERROR {error_id}] {request.method} {request.url.path}", file=sys.stderr, flush=True)
    print(f"[ERROR {error_id}] {type(exc).__name__}: {str(exc)}", file=sys.stderr, flush=True)
    if settings.DEBUG:
        print(f"[ERROR {error_id}] Traceback:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
    
    # Return generic error to client (don't leak internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error_id": error_id,  # Allow user to report this ID
        },
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
        "health": "/api/v1/health",
    }


# Apply rate limiting to specific routes
@app.get("/api/v1/limited")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def limited_endpoint(request: Request):
    """Example rate-limited endpoint."""
    return {"message": "This endpoint is rate limited"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
