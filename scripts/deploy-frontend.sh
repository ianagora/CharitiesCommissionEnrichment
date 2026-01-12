#!/bin/bash
# Deploy Frontend to Cloudflare Pages
# Usage: ./scripts/deploy-frontend.sh

set -e

echo "🚀 Deploying Frontend to Cloudflare Pages..."

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend"

# Check if wrangler is available
if ! npx wrangler --version &> /dev/null; then
    echo "❌ Wrangler not found. Installing..."
    npm install -g wrangler
fi

# Build the project
echo "📦 Building frontend..."
npm run build

# Check if authenticated
if ! npx wrangler whoami &> /dev/null; then
    echo "📝 Please login to Cloudflare..."
    npx wrangler login
fi

# Create project if it doesn't exist
echo "📝 Creating/updating Cloudflare Pages project..."
npx wrangler pages project create charity-data-enrichment --production-branch main 2>/dev/null || true

# Deploy
echo "🚀 Deploying to Cloudflare Pages..."
npx wrangler pages deploy dist --project-name charity-data-enrichment

echo "✅ Frontend deployment complete!"
echo ""
echo "📌 Next steps:"
echo "1. Note your deployment URL from above"
echo "2. Set environment variables in Cloudflare dashboard:"
echo "   - API_BASE_URL: Your Railway backend URL"
echo "3. Add your Cloudflare Pages URL to backend CORS_ORIGINS"
