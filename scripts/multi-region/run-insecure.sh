#!/bin/bash

set -e

echo "🪲 Starting CockroachDB Insecure Multi-Region Cluster"
echo "======================================================"
echo ""

# Stop any existing deployment
echo "Stopping existing containers..."
docker compose down -v 2>/dev/null || true

# Start the stack
echo ""
echo "Starting services..."
docker compose up -d --build

echo ""
echo "⏳ Waiting for cluster initialization (10 seconds)..."
sleep 10

echo ""
echo "💡 Cluster Ready!"
echo ""
echo "   CockroachDB Admin Consoles:"
echo "     - http://localhost:8080  (region: us-east-1, zone: a)"
echo "     - http://localhost:8081  (region: us-east-1, zone: b)"
echo "     - http://localhost:8082  (region: us-west-2, zone: a)"
echo "     - http://localhost:8083  (region: us-west-2, zone: b)"
echo "     - http://localhost:8084  (region: us-central-1, zone: a)"
echo ""
echo "   HAProxy stats: http://localhost:8404/stats"
echo ""
echo "   Connect:"
echo "     cockroach sql --insecure --host=localhost:26257"
echo "     or: ./connect.sh"
echo ""
echo "   Via Docker:"
echo "     docker exec -it crdb-e1a /cockroach/cockroach sql --insecure"
echo ""
echo "To stop: docker compose down -v"
echo ""
