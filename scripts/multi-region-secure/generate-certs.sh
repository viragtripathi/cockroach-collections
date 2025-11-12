#!/bin/bash

set -e

echo "🔐 Generating CockroachDB Security Certificates"
echo "================================================"

# Create directories
mkdir -p certs my-safe-directory

# Clean up any existing certificates
rm -rf certs/* my-safe-directory/*

echo ""
echo "Step 1: Creating CA certificate..."

# Create CA certificate and key using cockroach cert
docker run --rm -v "$(pwd)/certs:/certs" -v "$(pwd)/my-safe-directory:/ca-key" \
  cockroachdb/cockroach:v25.3.4 cert create-ca \
  --certs-dir=/certs \
  --ca-key=/ca-key/ca.key

echo "✓ CA certificate created"

echo ""
echo "Step 2: Creating node certificate..."

# Create node certificate (includes CN=node automatically)
# Add all hostnames that nodes will use
docker run --rm -v "$(pwd)/certs:/certs" -v "$(pwd)/my-safe-directory:/ca-key" \
  cockroachdb/cockroach:v25.3.4 cert create-node \
  localhost \
  crdb-e1a \
  crdb-e1b \
  crdb-w2a \
  crdb-w2b \
  crdb-c1 \
  haproxy \
  127.0.0.1 \
  --certs-dir=/certs \
  --ca-key=/ca-key/ca.key

echo "✓ Node certificate created"

echo ""
echo "Step 3: Creating client certificate for root user..."

# Create client certificate for root user
docker run --rm -v "$(pwd)/certs:/certs" -v "$(pwd)/my-safe-directory:/ca-key" \
  cockroachdb/cockroach:v25.3.4 cert create-client \
  root \
  --certs-dir=/certs \
  --ca-key=/ca-key/ca.key

echo "✓ Root client certificate created"

echo ""
echo "Step 4: Creating client certificate for craig user..."

# Create client certificate for craig user
docker run --rm -v "$(pwd)/certs:/certs" -v "$(pwd)/my-safe-directory:/ca-key" \
  cockroachdb/cockroach:v25.3.4 cert create-client \
  craig \
  --certs-dir=/certs \
  --ca-key=/ca-key/ca.key

echo "✓ Craig client certificate created"

echo ""
echo "================================================"
echo "✅ Certificate generation complete!"
echo ""
echo "Files created:"
echo "  - certs/ca.crt           (CA certificate)"
echo "  - certs/node.crt         (Node certificate with CN=node)"
echo "  - certs/node.key         (Node key)"
echo "  - certs/client.root.crt  (Root client certificate)"
echo "  - certs/client.root.key  (Root client key)"
echo "  - certs/client.craig.crt (Craig client certificate)"
echo "  - certs/client.craig.key (Craig client key)"
echo "  - my-safe-directory/ca.key (CA key - keep safe!)"
echo ""
