#!/bin/bash
set -e

# Function to check command success
check_success() {
  if [ $? -ne 0 ]; then
    echo "Error encountered. Exiting."
    exit 1
  fi
}

# Function to clean up local mounts
delete_local_data() {
  echo "Deleting existing local mounts (certs and cockroach-data)..."
  rm -rf ./certs ./cockroach-data
  check_success
}

# Function to clean up network
cleanup_network() {
  echo "Removing Podman network..."
  podman network rm dc1 dc2 || true
  check_success
}

# Check if teardown is requested
if [ "$1" == "teardown" ]; then
  echo "Tearing down CockroachDB cluster..."
  podman-compose down
  check_success
  delete_local_data
  cleanup_network
  echo "Teardown completed."
  exit 0
fi

# Start Podman Compose cluster
echo "Starting CockroachDB cluster with HAProxy..."
delete_local_data
podman-compose up -d
check_success

# Wait for nodes to be ready
echo "Waiting for nodes to start..."
sleep 10

# Initialize the clusters
#echo "Initializing the CockroachDB clusters..."
#podman exec -it crdb-node1-dc1 cockroach init --certs-dir=/certs --host=crdb-node1-dc1 --virtualized
#check_success
#podman exec -it crdb-node1-dc2 cockroach init --certs-dir=/certs --host=crdb-node1-dc2 --virtualized-empty
#check_success

# Create a CockroachDB user
#echo "Creating admin user..."
#podman exec -it crdb-node1-dc1 cockroach sql --certs-dir=/certs --host=crdb-node1-dc1 --execute="CREATE USER pcr WITH PASSWORD 'securepassword';"
#check_success
#podman exec -it crdb-node1-dc2 cockroach sql --certs-dir=/certs --host=crdb-node1-dc2 --execute="CREATE USER pcr WITH PASSWORD 'securepassword';"
#check_success

# Grant admin privileges
#echo "Granting admin privileges to user..."
#podman exec -it crdb-node1-dc1 cockroach sql --certs-dir=/certs --host=crdb-node1-dc1 --execute="GRANT admin TO pcr;"
#check_success
#podman exec -it crdb-node1-dc2 cockroach sql --certs-dir=/certs --host=crdb-node1-dc2 --execute="GRANT admin TO pcr;"
#check_success

# Confirm cluster status
#echo "Checking cluster status..."
#podman exec -it crdb-node1-dc1 cockroach node status --certs-dir=/certs --host=crdb-node1-dc1
#check_success
#podman exec -it crdb-node1-dc2 cockroach node status --certs-dir=/certs --host=crdb-node1-dc2
#check_success

# Setup complete
echo "CockroachDB cluster setup completed successfully!"
echo "Access Admin Console: https://localhost:8080 with user 'pcr'"

