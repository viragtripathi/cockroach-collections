#!/bin/bash

set -euo pipefail

echo "🚀 Starting Apache Fineract + CockroachDB demo environment..."

# Step 1: Start containers
docker-compose up -d

# Step 2: Wait and initialize CockroachDB with databases and user
./init-db.sh

# Step 3: Wait for Fineract to finish Liquibase migration
echo "⏳ Waiting for Fineract to start (this may take 30–60 seconds)..."
until curl -sSf -u mifos:password http://localhost:8080/fineract-provider/api/v1/clients > /dev/null 2>&1; do
  sleep 5
done

# Step 4: Show access info
echo
echo "✅ Fineract is up and running!"
echo "📘 Swagger UI:       http://localhost:8080/fineract-provider/swagger-ui.html"
echo "🔑 Default login:    mifos / password"
echo "📂 Sample endpoint:  http://localhost:8080/fineract-provider/api/v1/clients"
echo

