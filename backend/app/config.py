"""Application configuration settings."""
import secrets
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Charity Commission Data Enrichment Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/charity_platform"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    @property
    def async_database_url(self) -> str:
        """Convert DATABASE_URL to async format for SQLAlchemy.
        
        Railway provides postgres:// but SQLAlchemy async needs postgresql+asyncpg://
        """
        url = self.DATABASE_URL
        # Handle Railway's postgres:// URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        # Handle standard postgresql:// URL
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
    
    # JWT Authentication - MUST be set via environment variable in production
    JWT_SECRET_KEY: str = ""  # Will be validated below
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Ensure JWT secret is set and secure."""
        if not v or v == "your-super-secret-key-change-in-production":
            # In development, generate a random key (will change on restart)
            import os
            if os.getenv("ENVIRONMENT", "production") == "development":
                return secrets.token_urlsafe(32)
            raise ValueError(
                "JWT_SECRET_KEY must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return v
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    
    # Charity Commission API
    CHARITY_COMMISSION_API_BASE_URL: str = "https://api.charitycommission.gov.uk/register/api"
    CHARITY_COMMISSION_API_KEY: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Security - Account Lockout
    LOGIN_MAX_ATTEMPTS: int = 5  # Lock after this many failed attempts
    LOGIN_LOCKOUT_MINUTES: int = 15  # Lock duration in minutes
    
    # CORS - Explicit allowed origins (no wildcards in production)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://charity-data-enrichment.pages.dev"
    
    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = ".csv,.xlsx,.xls"
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    
    # Allowed CORS methods and headers (explicit, not wildcards)
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type,X-API-Key,Accept,Origin"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def cors_methods_list(self) -> list[str]:
        """Parse CORS methods into a list."""
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(",")]
    
    @property
    def cors_headers_list(self) -> list[str]:
        """Parse CORS headers into a list."""
        return [header.strip() for header in self.CORS_ALLOW_HEADERS.split(",")]
    
    @property
    def allowed_extensions_list(self) -> list[str]:
        """Parse allowed file extensions into a list."""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
