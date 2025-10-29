# CockroachDB Insecure Multi-Region Cluster

A 5-node insecure CockroachDB cluster with HAProxy load balancing, deployed across 3 regions using Docker Compose.

## Quick Download (Without Cloning Entire Repo)

```bash
wget -c https://github.com/viragtripathi/cockroach-collections/archive/main.zip && \
mkdir -p cockroach-insecure-cluster && \
unzip main.zip "cockroach-collections-main/scripts/multi-region/*" -d cockroach-insecure-cluster && \
cp -R cockroach-insecure-cluster/cockroach-collections-main/scripts/multi-region/* cockroach-insecure-cluster/ && \
rm -rf main.zip cockroach-insecure-cluster/cockroach-collections-main && \
cd cockroach-insecure-cluster && \
chmod +x *.sh
```

## Why This Exists

Demonstrates a simple multi-region CockroachDB deployment for **development and testing only**:

- ✅ **No TLS/certificates required** - quick setup
- ✅ **Multi-region topology** (3 regions, 5 nodes)
- ✅ **HAProxy load balancer** with health checks
- ✅ **Automated setup** with Docker Compose

⚠️ **WARNING: This is INSECURE. Use only for development/testing. For production, use the [multi-region-secure](../multi-region-secure) setup.**

## Prerequisites

### Docker or Podman

You need either:

- **Docker Desktop** (Linux/Mac/Windows), or
- **Podman Desktop** with `podman-compose`

#### If using Podman

Create symlinks so scripts can use `docker` commands:

```bash
sudo ln -s $(which podman) /usr/local/bin/docker
sudo ln -s $(which podman-compose) /usr/local/bin/docker-compose
```

### Docker Permissions Issue (Linux)

If you get permission errors, add your user to the docker group:

```bash
# Add your user to the docker group
sudo usermod -aG docker "$USER"

# Refresh group membership
newgrp docker

# Verify access
docker info
```

## Quick Start

```bash
# Make scripts executable
chmod +x run-insecure.sh connect.sh

# Start the cluster
./run-insecure.sh

# Wait ~10 seconds, then connect
./connect.sh
```

The startup script will:
1. Start 5 CockroachDB nodes in insecure mode
2. Initialize the cluster
3. Configure HAProxy for load balancing
4. Bootstrap sample database

## Cluster Topology

| Node     | Region       | Zone | Admin UI                    | SQL Port |
|----------|--------------|------|-----------------------------|----------|
| crdb-e1a | us-east-1    | a    | http://localhost:8080       | 26257    |
| crdb-e1b | us-east-1    | b    | http://localhost:8081       | 26257    |
| crdb-w2a | us-west-2    | a    | http://localhost:8082       | 26257    |
| crdb-w2b | us-west-2    | b    | http://localhost:8083       | 26257    |
| crdb-c1  | us-central-1 | a    | http://localhost:8084       | 26257    |
| haproxy  | -            | -    | http://localhost:8404/stats | 26257    |

## Connecting to the Cluster

### Quick Connect (Easiest)

```bash
# Use the helper script
./connect.sh

# Or connect directly to a node
docker exec -it crdb-e1a /cockroach/cockroach sql --insecure
```

### Via HAProxy (Recommended for Load Balancing)

```bash
# Using cockroach CLI
cockroach sql --insecure --host=localhost:26257

# Connection string for applications
postgresql://root@localhost:26257/defaultdb?sslmode=disable
```

### Direct to Node

```bash
# Connect to any specific node
docker exec -it crdb-e1a /cockroach/cockroach sql --insecure
docker exec -it crdb-w2a /cockroach/cockroach sql --insecure
```

## Admin Console Access

Open any of these URLs in your browser:
- http://localhost:8080 (region: us-east-1, zone: a)
- http://localhost:8081 (region: us-east-1, zone: b)
- http://localhost:8082 (region: us-west-2, zone: a)
- http://localhost:8083 (region: us-west-2, zone: b)
- http://localhost:8084 (region: us-central-1, zone: a)

**No login required** - insecure mode has no authentication.

## Application Examples

### Python

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=26257,
    user="root",
    database="defaultdb",
    sslmode="disable"
)

cursor = conn.cursor()
cursor.execute("SELECT version()")
print(cursor.fetchone())
conn.close()
```

### Connection String

```bash
postgresql://root@localhost:26257/defaultdb?sslmode=disable
```

## Multi-Region Database Setup

```sql
-- Connect to cluster
cockroach sql --insecure --host=localhost:26257

-- Convert database to multi-region
ALTER DATABASE defaultdb SET PRIMARY REGION "us-east-1";
ALTER DATABASE defaultdb ADD REGION "us-west-2";
ALTER DATABASE defaultdb ADD REGION "us-central-1";
ALTER DATABASE defaultdb SET SECONDARY REGION "us-west-2";

-- Create regional table
CREATE TABLE regional_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region STRING AS (crdb_region) STORED,
  data TEXT
) LOCALITY REGIONAL BY ROW;
```

## HAProxy Configuration

The HAProxy config includes:

- **TCP passthrough** for connections
- **TCP health checks** on port 26257
- **Round-robin load balancing** across all 5 nodes
- **Stats UI** at http://localhost:8404/stats

### Monitoring Node Health

Visit HAProxy stats: http://localhost:8404/stats

- Green = healthy node
- Red = node down or unhealthy

## Stopping the Cluster

```bash
# Stop and remove containers
docker compose down

# Stop and remove everything including volumes
docker compose down -v
```

## Common Issues

### "Connection refused"

Ensure the cluster is running:
```bash
docker ps
docker logs crdb-e1a
```

### HAProxy shows all nodes as DOWN

Check that nodes are running:
```bash
docker ps
docker logs haproxy
```

Restart if needed:
```bash
docker compose restart haproxy
```

## Migration to Secure Cluster

For production use, switch to the secure cluster setup:

```bash
cd ../multi-region-secure
./run-secure.sh
```

The secure cluster provides:
- TLS encryption for all connections
- Certificate-based authentication
- Password authentication
- Full production security

## More Information

- [CockroachDB Multi-Region Capabilities](https://www.cockroachlabs.com/docs/stable/multiregion-overview)
- [Secure Cluster Setup](../multi-region-secure)
- [HAProxy Documentation](https://docs.haproxy.org/)
