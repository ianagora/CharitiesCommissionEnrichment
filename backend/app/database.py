"""Database connection and session management."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

# Create async engine - use async_database_url which converts postgres:// to postgresql+asyncpg://
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    poolclass=NullPool if settings.ENVIRONMENT == "testing" else None,
    pool_size=settings.DATABASE_POOL_SIZE if settings.ENVIRONMENT != "testing" else None,
    max_overflow=settings.DATABASE_MAX_OVERFLOW if settings.ENVIRONMENT != "testing" else None,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Declarative base for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of request handlers."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables and run any needed migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Add missing columns to users table if they don't exist
        # This handles migration for new token rotation fields
        from sqlalchemy import text
        try:
            # Check if token_version column exists
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'token_version'
            """))
            if not result.fetchone():
                await conn.execute(text("""
                    ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0
                """))
                print("[MIGRATION] Added token_version column to users table")
            
            # Check if refresh_token_family column exists
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'refresh_token_family'
            """))
            if not result.fetchone():
                await conn.execute(text("""
                    ALTER TABLE users ADD COLUMN refresh_token_family VARCHAR(64)
                """))
                # Create index
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_users_refresh_token_family 
                    ON users (refresh_token_family)
                """))
                print("[MIGRATION] Added refresh_token_family column to users table")
        except Exception as e:
            print(f"[MIGRATION] Migration check/update: {e}")


async def close_db():
    """Close database connections."""
    await engine.dispose()
