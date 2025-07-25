#!/bin/bash
set -e

echo "🚀 Starting Docker Compose..."
docker-compose up -d

echo "⏳ Waiting for CockroachDB and Kafka to become ready..."
sleep 30

echo "🔧 Running setup script..."
./setup-cockroachdb.sh

echo "✅ Demo setup complete!"
echo "Visit CockroachDB UI at: http://localhost:8080"
echo "Kafka topic should now receive changefeed messages from 'products' table."

docker exec kafka-test kafka-topics --bootstrap-server localhost:9092 --list

docker exec kafka-test kafka-console-consumer --bootstrap-server localhost:9092 --topic testdb.public.products --from-beginning