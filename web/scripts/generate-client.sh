#!/bin/sh
# Regenerate the typed API client from the running API's OpenAPI schema.
# Start the API first:  .venv/bin/uvicorn sanad.api.app:create_app --factory --port 8000
set -e
URL="${SANAD_OPENAPI_URL:-http://localhost:8000/openapi.json}"
npx openapi-typescript "$URL" -o src/api/types.ts
echo "wrote src/api/types.ts from $URL"
