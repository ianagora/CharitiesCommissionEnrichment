#!/bin/bash
# Deploy Backend to Railway
# Usage: ./scripts/deploy-backend.sh

set -e

echo "🚀 Deploying Backend to Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    npm install -g @railway/cli
fi

# Navigate to backend directory
cd "$(dirname "$0")/../backend"

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "📝 Please login to Railway..."
    railway login
fi

# Check if project is linked
if [ ! -f ".railway/config.json" ]; then
    echo "📝 Linking Railway project..."
    railway link
fi

# Deploy
echo "📦 Deploying to Railway..."
railway up --detach

echo "✅ Backend deployment initiated!"
echo ""
echo "📌 Next steps:"
echo "1. Check deployment status: railway logs"
echo "2. Get your backend URL from the Railway dashboard"
echo "3. Set environment variables in Railway dashboard:"
echo "   - DATABASE_URL (auto-provisioned if using Railway Postgres)"
echo "   - JWT_SECRET_KEY"
echo "   - OPENAI_API_KEY"
echo "   - CHARITY_COMMISSION_API_KEY"
