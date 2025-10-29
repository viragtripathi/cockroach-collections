#!/bin/bash

# Helper script to connect to insecure CockroachDB cluster

echo "Connecting to cluster..."
docker exec -it crdb-e1a /cockroach/cockroach sql --insecure
