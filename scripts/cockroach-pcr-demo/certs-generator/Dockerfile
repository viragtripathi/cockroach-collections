# Use the latest CockroachDB image
FROM cockroachdb/cockroach:latest

LABEL maintainer="your-email@example.com"
LABEL description="CockroachDB Certificate Generator"

# Set working directory
WORKDIR /certs

# Create required directories
RUN mkdir -p /certs/ca /certs/node /certs/client /certs/lb /safe

# Generate CA certificate
RUN cockroach cert create-ca --certs-dir=/certs/ca --ca-key=/safe/ca.key

# Generate Node certificates (for each node and HAProxy)
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node1-dc1 crdb-node2-dc1 crdb-node3-dc1 crdb-node1-dc2 crdb-node2-dc2 crdb-node3-dc2 haproxy \
    --certs-dir=/certs/node --ca-key=/safe/ca.key

# Generate Client certificate for root
RUN cockroach cert create-client root --certs-dir=/certs/client --ca-key=/safe/ca.key

# Copy the certificates to each node's directory for consistency
RUN for node in crdb-node1-dc1 crdb-node2-dc1 crdb-node3-dc1 crdb-node1-dc2 crdb-node2-dc2 crdb-node3-dc2 haproxy; do \
    mkdir -p /certs/$node && \
    cp /certs/ca/ca.crt /certs/$node/ && \
    cp /certs/node/node.crt /certs/$node/node.crt && \
    cp /certs/node/node.key /certs/$node/node.key; \
    done

# Keep container running (for debugging)
CMD ["sleep", "infinity"]

