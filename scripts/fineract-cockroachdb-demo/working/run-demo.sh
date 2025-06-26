#!/bin/bash

set -euo pipefail

echo "🚀 Starting Apache Fineract + CockroachDB demo environment..."

# Step 1: cleanup containers
echo "🧼 Cleaning up any previous demo containers..."
docker-compose down || true

# Step 2: Start containers
docker-compose up -d

# Step 3: Wait for Fineract to finish Liquibase migration
echo "⏳ Waiting for Fineract to start..."
until curl -k -sSf https://localhost:8085/fineract-provider/actuator/health | grep -q '"status":"UP"' > /dev/null 2>&1; do
  echo "⌛ Still waiting for Fineract to become available..."
  sleep 5
done
echo "✅ Fineract is up and healthy!"

# Step 4: Show access info
echo
echo "✅ Fineract is up and running!"
echo "📘 Swagger UI:       https://localhost:8085/fineract-provider/swagger-ui/index.html"
echo "🔑 Default login:    mifos / password"
echo "📂 health endpoint:  https://localhost:8085/fineract-provider/actuator/health"
echo
