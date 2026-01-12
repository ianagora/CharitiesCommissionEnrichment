#!/bin/bash
# Push project to GitHub
# Usage: ./scripts/push-to-github.sh [repo-name]

set -e

REPO_NAME=${1:-"charity-data-enrichment-platform"}

echo "📦 Pushing to GitHub..."

cd "$(dirname "$0")/.."

# Initialize git if needed
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: Charity Commission Data Enrichment Platform"
fi

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI not found. Please install: https://cli.github.com/"
    echo ""
    echo "Manual steps:"
    echo "1. Create a new repository on GitHub: $REPO_NAME"
    echo "2. Run: git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
    echo "3. Run: git push -u origin main"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "📝 Please login to GitHub..."
    gh auth login
fi

# Check if remote exists
if git remote get-url origin &> /dev/null; then
    echo "📌 Remote 'origin' already exists. Pushing..."
    git push -u origin main
else
    # Create repository and push
    echo "📝 Creating GitHub repository: $REPO_NAME"
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
fi

echo "✅ Repository pushed to GitHub!"
echo ""
echo "📌 Your repository: https://github.com/$(gh api user -q .login)/$REPO_NAME"
