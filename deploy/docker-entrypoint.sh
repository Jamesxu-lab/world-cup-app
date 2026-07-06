#!/bin/sh
set -eu

mkdir -p /app/backend/data

if [ -d /app/seed-data ]; then
  for file in worldcup.db prediction_snapshot.json champion_prediction_cache.json; do
    if [ -f "/app/seed-data/$file" ] && [ ! -f "/app/backend/data/$file" ]; then
      cp "/app/seed-data/$file" "/app/backend/data/$file"
    fi
  done
fi

exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port "${PORT:-8000}"
