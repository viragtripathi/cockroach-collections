#!/bin/bash

set -euo pipefail

echo "🧹 Stopping and removing Fineract demo environment..."

# Stop and remove containers, networks, and volumes
docker-compose down --volumes --remove-orphans
docker system prune --volumes -f

echo "✅ Cleanup complete."

