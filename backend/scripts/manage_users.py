#!/usr/bin/env python3
"""
Admin script to manage users.

Usage:
    python scripts/manage_users.py add-user --email user@example.com --password SecurePass123! --name "John Doe"
    python scripts/manage_users.py list-users
    python scripts/manage_users.py make-superuser --email user@example.com
    python scripts/manage_users.py disable-user --email user@example.com
"""
import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import async_session_maker
from app.models.user import User
from app.services.auth import AuthService


async def add_user(email: str, password: str, full_name: str = None, is_superuser: bool = False):
    """Add a new user."""
    async with async_session_maker() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalars().first()
        
        if existing:
            print(f"❌ User with email {email} already exists!")
            return
        
        # Create user
        user = await AuthService.create_user(
            db,
            email=email,
            password=password,
            full_name=full_name
        )
        
        if is_superuser:
            user.is_superuser = True
            await db.commit()
        
        print(f"✅ User created successfully!")
        print(f"   Email: {user.email}")
        print(f"   ID: {user.id}")
        print(f"   Superuser: {user.is_superuser}")


async def list_users():
    """List all users."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        if not users:
            print("No users found.")
            return
        
        print(f"\n{'Email':<40} {'Name':<25} {'Active':<8} {'Superuser':<10} {'2FA':<6}")
        print("-" * 100)
        
        for user in users:
            print(
                f"{user.email:<40} "
                f"{(user.full_name or 'N/A'):<25} "
                f"{'Yes' if user.is_active else 'No':<8} "
                f"{'Yes' if user.is_superuser else 'No':<10} "
                f"{'Yes' if user.two_factor_enabled else 'No':<6}"
            )
        
        print(f"\nTotal users: {len(users)}")


async def make_superuser(email: str):
    """Make a user a superuser."""
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"❌ User with email {email} not found!")
            return
        
        user.is_superuser = True
        await db.commit()
        
        print(f"✅ {email} is now a superuser!")


async def disable_user(email: str):
    """Disable a user account."""
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"❌ User with email {email} not found!")
            return
        
        user.is_active = False
        await db.commit()
        
        print(f"✅ User {email} has been disabled!")


async def enable_user(email: str):
    """Enable a user account."""
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"❌ User with email {email} not found!")
            return
        
        user.is_active = True
        await db.commit()
        
        print(f"✅ User {email} has been enabled!")


def main():
    parser = argparse.ArgumentParser(description="User management script")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Add user command
    add_parser = subparsers.add_parser("add-user", help="Add a new user")
    add_parser.add_argument("--email", required=True, help="User email")
    add_parser.add_argument("--password", required=True, help="User password")
    add_parser.add_argument("--name", help="User full name")
    add_parser.add_argument("--superuser", action="store_true", help="Make user a superuser")
    
    # List users command
    subparsers.add_parser("list-users", help="List all users")
    
    # Make superuser command
    super_parser = subparsers.add_parser("make-superuser", help="Make a user a superuser")
    super_parser.add_argument("--email", required=True, help="User email")
    
    # Disable user command
    disable_parser = subparsers.add_parser("disable-user", help="Disable a user account")
    disable_parser.add_argument("--email", required=True, help="User email")
    
    # Enable user command
    enable_parser = subparsers.add_parser("enable-user", help="Enable a user account")
    enable_parser.add_argument("--email", required=True, help="User email")
    
    args = parser.parse_args()
    
    if args.command == "add-user":
        asyncio.run(add_user(
            args.email,
            args.password,
            args.name,
            args.superuser
        ))
    elif args.command == "list-users":
        asyncio.run(list_users())
    elif args.command == "make-superuser":
        asyncio.run(make_superuser(args.email))
    elif args.command == "disable-user":
        asyncio.run(disable_user(args.email))
    elif args.command == "enable-user":
        asyncio.run(enable_user(args.email))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
