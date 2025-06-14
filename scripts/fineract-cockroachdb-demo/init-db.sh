#!/bin/bash

set -euo pipefail

echo "⏳ Waiting for CockroachDB to be ready..."

# Wait until CockroachDB accepts SQL connections
until docker exec cockroachdb ./cockroach sql --insecure -e "SELECT 1;" >/dev/null 2>&1; do
  sleep 2
done

echo "✅ CockroachDB is ready. Creating databases and user..."

docker exec cockroachdb ./cockroach sql --insecure -e "
  CREATE DATABASE IF NOT EXISTS fineract_tenants;
  CREATE DATABASE IF NOT EXISTS fineract_default;
  -- No user creation necessary; root will be used
  GRANT ALL ON DATABASE fineract_tenants TO root;
  GRANT ALL ON DATABASE fineract_default TO root;
"

echo "✅ Databases and user created."

