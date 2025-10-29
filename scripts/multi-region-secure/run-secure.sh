#!/bin/bash

set -e

echo "🔐 Starting Secure CockroachDB Multi-Region Cluster"
echo "===================================================="
echo ""

# Stop any existing deployment
echo "Stopping existing containers..."
docker compose down -v 2>/dev/null || true

# Check if certificates exist
if [ ! -f "certs/ca.crt" ] || [ ! -f "certs/node.crt" ] || [ ! -f "certs/client.root.crt" ]; then
  echo ""
  echo "Certificates not found. Generating certificates..."
  ./generate-certs.sh
else
  echo ""
  echo "Using existing certificates..."
fi

# Start the stack
echo ""
echo "Starting secure services..."
docker compose up -d --build

echo ""
echo "⏳ Waiting for cluster initialization (15 seconds)..."
sleep 15

echo ""
echo "💡 Cluster Ready!"
echo ""
echo "   CockroachDB Admin Consoles (secure):"
echo "     - https://localhost:8080  (region: us-east-1, zone: a)"
echo "     - https://localhost:8081  (region: us-east-1, zone: b)"
echo "     - https://localhost:8082  (region: us-west-2, zone: a)"
echo "     - https://localhost:8083  (region: us-west-2, zone: b)"
echo "     - https://localhost:8084  (region: us-central-1, zone: a)"
echo ""
echo "   HAProxy stats: http://localhost:8404/stats"
echo ""
echo "   Connect via HAProxy:"
echo "     cockroach sql --certs-dir=certs --host=localhost:26257"
echo ""
echo "   Or via Docker:"
echo "     docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs"
echo ""
echo "To stop: docker compose down -v"
echo ""
