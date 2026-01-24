#!/bin/bash

echo "🔧 Running database migrations..."

# Run migrations and capture output/status
if alembic upgrade head 2>&1 | tee /tmp/migration.log; then
    echo "✅ Migrations successful"
else
    EXIT_CODE=$?
    echo "⚠️  Migration command exited with code $EXIT_CODE"
    
    # Check if error is about duplicate tables/columns (expected for existing schema)
    if grep -qi "already exists\|Duplicate" /tmp/migration.log; then
        echo "✅ Schema already exists. Marking migrations as applied..."
        alembic stamp head
        echo "✅ Database marked as up-to-date"
    else
        echo "❌ Migration failed with unexpected error:"
        cat /tmp/migration.log
        echo "❌ Exiting with error"
        exit $EXIT_CODE
    fi
fi

echo "✅ Starting server..."
exec gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind "0.0.0.0:${PORT:-8000}" --timeout 120
