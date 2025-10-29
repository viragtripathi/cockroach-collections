#!/bin/bash

set -e

echo "🔐 Generating CockroachDB Security Certificates"
echo "================================================"

# Create directories
mkdir -p certs my-safe-directory

# Clean up any existing certificates
rm -rf certs/* my-safe-directory/*
rm -f index.txt serial.txt *.csr

echo ""
echo "Step 1: Creating CA key and certificate..."

# Create CA configuration
cat > ca.cnf << 'EOF'
# OpenSSL CA configuration file
[ ca ]
default_ca = CA_default

[ CA_default ]
default_days = 365
database = index.txt
serial = serial.txt
default_md = sha256
copy_extensions = copy
unique_subject = no

[ req ]
prompt=no
distinguished_name = distinguished_name
x509_extensions = extensions

[ distinguished_name ]
organizationName = Cockroach
commonName = Cockroach CA

[ extensions ]
keyUsage = critical,digitalSignature,nonRepudiation,keyEncipherment,keyCertSign
basicConstraints = critical,CA:true,pathlen:1

[ signing_policy ]
organizationName = supplied
commonName = optional

[ signing_node_req ]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth

[ signing_client_req ]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = clientAuth
EOF

# Generate CA key
openssl genrsa -out my-safe-directory/ca.key 2048
chmod 400 my-safe-directory/ca.key

# Generate CA certificate
openssl req \
  -new \
  -x509 \
  -config ca.cnf \
  -key my-safe-directory/ca.key \
  -out certs/ca.crt \
  -days 365 \
  -batch

# Initialize database files
touch index.txt
echo '01' > serial.txt

echo "✓ CA certificate created"

echo ""
echo "Step 2: Creating node certificates for 5 nodes..."

# Node configuration template
cat > node.cnf << 'EOF'
# OpenSSL node configuration file
[ req ]
prompt=no
distinguished_name = distinguished_name
req_extensions = extensions

[ distinguished_name ]
organizationName = Cockroach
commonName = node

[ extensions ]
subjectAltName = critical,DNS:localhost,DNS:crdb-e1a,DNS:crdb-e1b,DNS:crdb-w2a,DNS:crdb-w2b,DNS:crdb-c1,DNS:haproxy,IP:127.0.0.1
EOF

# Generate single node key and certificate (shared across all nodes for simplicity)
openssl genrsa -out certs/node.key 2048
chmod 400 certs/node.key

# Create CSR
openssl req \
  -new \
  -config node.cnf \
  -key certs/node.key \
  -out node.csr \
  -batch

# Sign node certificate
openssl ca \
  -config ca.cnf \
  -keyfile my-safe-directory/ca.key \
  -cert certs/ca.crt \
  -policy signing_policy \
  -extensions signing_node_req \
  -out certs/node.crt \
  -outdir certs/ \
  -in node.csr \
  -batch

echo "✓ Node certificates created"

echo ""
echo "Step 3: Creating client certificate for root user..."

# Client configuration
cat > client.cnf << 'EOF'
[ req ]
prompt=no
distinguished_name = distinguished_name
req_extensions = extensions

[ distinguished_name ]
organizationName = Cockroach
commonName = root

[ extensions ]
subjectAltName = DNS:root
EOF

# Generate client key
openssl genrsa -out certs/client.root.key 2048
chmod 400 certs/client.root.key

# Create client CSR
openssl req \
  -new \
  -config client.cnf \
  -key certs/client.root.key \
  -out client.root.csr \
  -batch

# Sign client certificate
openssl ca \
  -config ca.cnf \
  -keyfile my-safe-directory/ca.key \
  -cert certs/ca.crt \
  -policy signing_policy \
  -extensions signing_client_req \
  -out certs/client.root.crt \
  -outdir certs/ \
  -in client.root.csr \
  -batch

echo "✓ Root client certificate created"

# Clean up
rm -f *.csr certs/*.pem

echo ""
echo "================================================"
echo "✅ Certificate generation complete!"
echo ""
echo "Files created:"
echo "  - certs/ca.crt           (CA certificate)"
echo "  - certs/node.crt         (Node certificate)"
echo "  - certs/node.key         (Node key)"
echo "  - certs/client.root.crt  (Root client certificate)"
echo "  - certs/client.root.key  (Root client key)"
echo "  - my-safe-directory/ca.key (CA key - keep safe!)"
echo ""
