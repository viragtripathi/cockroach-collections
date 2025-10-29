#!/bin/bash

# Helper script to connect to secure CockroachDB cluster

# Certificate-based connection (root user)
# Direct to node (bypasses HAProxy, recommended for CLI)
echo "Connecting to cluster as root user..."
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs

# Alternative: Connect via specific user  
# docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs --user=appuser

# Note: For HAProxy connections, use psql or application drivers
# cockroach CLI has issues with HAProxy due to TLS hostname verification
