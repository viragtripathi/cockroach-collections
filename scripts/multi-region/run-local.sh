#!/bin/bash

set -e

echo "🪲 Starting CockroachDB multi-region Demo"
echo "================================================"
echo ""

# Stop any existing deployment
echo "Stopping existing containers..."
docker compose -f docker-compose.local.yml down -v 2>/dev/null || true

# Start the stack
echo ""
echo "Starting services..."
docker compose -f docker-compose.local.yml up -d --build

echo ""
echo "⏳ Waiting for cluster initialization (10 seconds)..."
sleep 10

echo ""
echo "💡 Quick Test:"
echo "   CockroachDB Admin Console: http://localhost:8080, http://localhost:8081, http://localhost:8082, http://localhost:8083, http://localhost:8084"
echo "   HAProxy stats: http://localhost:8404/stats"
echo ""
echo "To stop: docker compose -f docker-compose.local.yml down -v"
