#!/bin/bash
# Local Development Setup Script
# Usage: ./scripts/setup-local.sh

set -e

echo "🔧 Setting up local development environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "📌 Python version: $PYTHON_VERSION"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "📌 Node.js version: $NODE_VERSION"

# Setup backend
echo ""
echo "📦 Setting up backend..."
cd "$(dirname "$0")/../backend"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📝 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "📝 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit backend/.env with your configuration!"
fi

# Setup frontend
echo ""
echo "📦 Setting up frontend..."
cd ../frontend

# Install dependencies
echo "📝 Installing Node.js dependencies..."
npm install

# Copy environment file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
fi

echo ""
echo "✅ Local setup complete!"
echo ""
echo "📌 Next steps:"
echo ""
echo "1. Configure backend environment:"
echo "   cd backend && nano .env"
echo ""
echo "2. Start PostgreSQL database (using Docker):"
echo "   docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=charity_platform -p 5432:5432 postgres:15"
echo ""
echo "3. Run database migrations:"
echo "   cd backend && source venv/bin/activate && alembic upgrade head"
echo ""
echo "4. Start backend server:"
echo "   cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "5. Start frontend (in new terminal):"
echo "   cd frontend && npm run dev"
echo ""
echo "6. Open http://localhost:5173 in your browser"
