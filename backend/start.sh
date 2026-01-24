#!/bin/bash
set -e

echo "🔧 Running database migrations..."

# Try to run migrations, but handle failures gracefully
if ! alembic upgrade head 2>&1 | tee /tmp/migration.log; then
    echo "⚠️  Migration failed. Checking if it's due to existing schema..."
    
    # Check if error is about duplicate tables/columns
    if grep -q "already exists" /tmp/migration.log || grep -q "Duplicate" /tmp/migration.log; then
        echo "✅ Schema already exists. Stamping database as up-to-date..."
        alembic stamp head
        echo "✅ Database marked as migrated"
    else
        echo "❌ Migration failed with unexpected error:"
        cat /tmp/migration.log
        exit 1
    fi
fi

echo "✅ Migrations complete. Starting server..."
exec gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind "0.0.0.0:${PORT:-8000}" --timeout 120
