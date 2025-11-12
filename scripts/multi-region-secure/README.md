# CockroachDB Secure Multi-Region Cluster

A 5-node secure CockroachDB cluster with HAProxy load balancing, deployed across 3 regions using Docker Compose.

## Quick Download (Without Cloning Entire Repo)

```bash
wget -c https://github.com/viragtripathi/cockroach-collections/archive/main.zip && \
mkdir -p cockroach-secure-cluster && \
unzip main.zip "cockroach-collections-main/scripts/multi-region-secure/*" -d cockroach-secure-cluster && \
cp -R cockroach-secure-cluster/cockroach-collections-main/scripts/multi-region-secure/* cockroach-secure-cluster/ && \
rm -rf main.zip cockroach-secure-cluster/cockroach-collections-main && \
cd cockroach-secure-cluster && \
chmod +x *.sh
```

## Why This Exists

Demonstrates a production-like secure CockroachDB deployment with:

- ✅ **TLS encryption** for all connections
- ✅ **Certificate-based authentication** using `cockroach cert`
- ✅ **Password authentication** with HBA configuration
- ✅ **Multi-region topology** (3 regions, 5 nodes)
- ✅ **HAProxy load balancer** with health checks
- ✅ **Automated setup** with certificate generation

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

If you get permission errors like `Cannot connect to the Docker daemon socket at /var/run/docker.sock`, add your user to the docker group:

```bash
# Add your user to the docker group
sudo usermod -aG docker "$USER"

# Refresh group membership in current shell (or log out/in)
newgrp docker

# Verify access
docker info
```

This lets you run Docker without `sudo`.

### Certificate Generation

No additional software needed! The `generate-certs.sh` script uses the CockroachDB Docker image's built-in `cockroach cert` command to generate all required certificates automatically.

## Quick Start

```bash
# Make scripts executable
chmod +x generate-certs.sh run-secure.sh

# Start the secure cluster (generates certs automatically)
./run-secure.sh

# Wait for cluster to initialize (~15 seconds), then connect
./connect.sh
```

The startup script will:
1. Generate CA, node, and client certificates
2. Start 5 CockroachDB nodes with TLS enabled
3. Initialize the cluster
4. Configure HAProxy for load balancing
5. Bootstrap sample database
6. Create demo user `craig` (password: `cockroach`) with admin privileges

**Demo Credentials:**
- Username: `craig`
- Password: `cockroach`
- Role: `admin` (full access to SQL and DB Console UI)

## Cluster Topology

| Node     | Region       | Zone | Admin UI                    | SQL Port |
|----------|--------------|------|-----------------------------|----------|
| crdb-e1a | us-east-1    | a    | https://localhost:8080      | 26257    |
| crdb-e1b | us-east-1    | b    | https://localhost:8081      | 26257    |
| crdb-w2a | us-west-2    | a    | https://localhost:8082      | 26257    |
| crdb-w2b | us-west-2    | b    | https://localhost:8083      | 26257    |
| crdb-c1  | us-central-1 | a    | https://localhost:8084      | 26257    |
| haproxy  | -            | -    | http://localhost:8404/stats | 26257    |

## User Management & Access

### Default Root User

The cluster starts with a `root` user authenticated via `certs/client.root.crt`. This is the admin user with full privileges.

### Authentication Methods

CockroachDB secure clusters support two authentication methods:
1. **Certificate-based authentication** (recommended for production)
2. **Password-based authentication** (easier for development/testing)

### Option 1: Certificate-Based Authentication

#### Step 1: Create the SQL User

```bash
# Connect as root
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs

# Create user (no password needed for cert auth)
CREATE USER appuser;

# Grant privileges
GRANT ALL ON DATABASE defaultdb TO appuser;
```

#### Step 2: Generate Client Certificate for the User

```bash
# Create client config
cat > client-appuser.cnf << EOF
[ req ]
prompt=no
distinguished_name = distinguished_name

[ distinguished_name ]
organizationName = Cockroach
commonName = appuser
EOF

# Generate key
openssl genrsa -out certs/client.appuser.key 2048
chmod 400 certs/client.appuser.key

# Create CSR
openssl req -new -config client-appuser.cnf -key certs/client.appuser.key -out client.appuser.csr -batch

# Sign certificate (need to reset index if needed)
openssl ca -config ca.cnf -keyfile my-safe-directory/ca.key -cert certs/ca.crt \
  -policy signing_policy -extensions signing_client_req \
  -out certs/client.appuser.crt -outdir certs/ -in client.appuser.csr -batch

# Cleanup
rm client-appuser.cnf client.appuser.csr certs/*.pem
```

#### Step 3: Connect as the New User

```bash
# Via HAProxy
cockroach sql --certs-dir=certs --host=localhost:26257 --user=appuser

# Direct to node
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs --user=appuser
```

### Option 2: Password-Based Authentication

Password authentication is simpler - you only need the CA certificate for TLS, not client certificates.

#### Step 1: Enable Password Authentication

Password authentication is automatically enabled by `init.sql`. To verify or change:

```bash
# Connect as root
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs

# Check current setting
SHOW CLUSTER SETTING server.host_based_authentication.configuration;

# Enable certificate OR password authentication (already set in init.sql)
SET CLUSTER SETTING server.host_based_authentication.configuration = 'host all all all cert-password';
```

#### Step 2: Create User with Password

```bash
# Connect as root
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs

# Create user with password
CREATE USER appuser WITH PASSWORD 'secure_password_here';

# Grant privileges
GRANT ALL ON DATABASE defaultdb TO appuser;
```

#### Step 3: Connect with Password

**Using cockroach CLI (recommended):**
```bash
# Direct to node - will prompt for password
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs --user=appuser
# Then enter password when prompted

# Or specify password in environment variable
docker exec -it -e COCKROACH_PASSWORD='secure_password_here' crdb-e1a \
  /cockroach/cockroach sql --certs-dir=/certs --user=appuser
```

**Using psql (alternative):**
```bash
# Via HAProxy (for load balancing)
docker run --rm -it --network multi-region-secure_default \
  -v "$(pwd)/certs:/certs:ro" postgres:16 \
  psql "postgresql://appuser:secure_password_here@haproxy:26257/defaultdb?sslmode=require&sslrootcert=/certs/ca.crt"
```

**Note:** Password authentication still requires TLS encryption (the CA certificate), but you don't need client certificates. This is easier for development but less secure than certificate-based authentication.



## Connecting to the Cluster

### Quick Connect (Easiest)

```bash
# Use the helper script to connect as root
./connect.sh

# Or connect directly to a node
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs
```

### Direct to Node (Recommended for cockroach CLI)

The `cockroach sql` CLI works best when connecting directly to nodes, not through HAProxy:

```bash
# Connect to specific node as root
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs

# As a different user (needs client certificate for that user)
docker exec -it crdb-e1a /cockroach/cockroach sql --certs-dir=/certs --user=appuser

# You can connect to any node
docker exec -it crdb-w2a /cockroach/cockroach sql --certs-dir=/certs
```

### Via HAProxy (For Load Balancing)

HAProxy distributes connections across all 5 nodes for high availability.

**For Applications (Python, Java, Go, etc.):**

Use standard PostgreSQL connection strings with `sslmode=require`:

```python
# Python example
import psycopg2

# Certificate-based auth
conn = psycopg2.connect(
    host="localhost",
    port=26257,
    user="appuser",
    database="defaultdb",
    sslmode="require",
    sslrootcert="certs/ca.crt",
    sslcert="certs/client.appuser.crt",
    sslkey="certs/client.appuser.key"
)

# Password-based auth
conn = psycopg2.connect(
    host="localhost",
    port=26257,
    user="craig",
    password="cockroach",
    database="defaultdb",
    sslmode="require",
    sslrootcert="certs/ca.crt"
)
```

**For Testing with psql:**

```bash
# Certificate-based
docker run --rm -it --network multi-region-secure_default \
  -v "$(pwd)/certs:/certs:ro" postgres:16 \
  psql "postgresql://root@haproxy:26257/defaultdb?sslmode=require&sslrootcert=/certs/ca.crt&sslcert=/certs/client.root.crt&sslkey=/certs/client.root.key"

# Password-based
docker run --rm -it --network multi-region-secure_default \
  -v "$(pwd)/certs:/certs:ro" postgres:16 \
  psql "postgresql://craig:cockroach@haproxy:26257/defaultdb?sslmode=require&sslrootcert=/certs/ca.crt"
```

**Note:** We use `sslmode=require` (not `verify-full`) because HAProxy passes through connections to backend nodes, which present certificates for their own hostnames (`crdb-e1a`, etc.) rather than `haproxy` or `localhost`. This still provides TLS encryption while avoiding hostname verification issues.

## Admin Console (DB Console) Access

The admin console UI is available at:
- https://localhost:8080 (region: us-east-1, zone: a)
- https://localhost:8081 (region: us-east-1, zone: b)
- https://localhost:8082 (region: us-west-2, zone: a)
- https://localhost:8083 (region: us-west-2, zone: b)
- https://localhost:8084 (region: us-central-1, zone: a)

### Logging into the Admin Console

The admin console UI supports two authentication methods. **Users must have the `admin` role** to access the DB Console.

#### Method 1: Password Login (Easiest)

Simply open https://localhost:8080 (or any port 8080-8084) in your browser and login with:
- **Username:** `craig`
- **Password:** `cockroach`

**Requirements:**
- User must have `admin` role
- Password authentication must be enabled (automatically configured in init.sql)

#### Method 2: Session-Based Authentication

For programmatic access or if password login isn't working:

```bash
# Generate session cookie
docker exec crdb-e1a /cockroach/cockroach auth-session login craig --certs-dir=/certs --only-cookie

# Copy the session cookie value (e.g., session=ABC123...)
# Then:
# 1. Open https://localhost:8080 in browser
# 2. Open Dev Tools (F12) → Application/Storage → Cookies
# 3. Add new cookie:
#    - Name: session
#    - Value: <paste the value from above>
#    - Path: /
#    - HttpOnly: checked
# 4. Refresh the page
```

#### Grant Admin Role to New Users

```bash
# For new users to access DB Console
docker exec crdb-e1a /cockroach/cockroach sql --certs-dir=/certs \
  --execute="GRANT admin TO username;"
```

## Certificate Management

### How Certificate Generation Works

The `generate-certs.sh` script uses CockroachDB's built-in `cockroach cert` command (via Docker) to generate all required certificates:

1. **CA Certificate** - Certificate Authority for signing other certs
2. **Node Certificate** - Used by all CockroachDB nodes (includes `CN=node` for node-to-node auth)
3. **Client Certificates** - For `root` and `craig` users

**Why `cockroach cert` instead of OpenSSL?**
- ✅ **Simple** - No complex OpenSSL config files
- ✅ **Clean** - No temporary database files (`index.txt`, `serial.txt`, etc.)
- ✅ **Automatic** - Handles `CN=node` requirement automatically
- ✅ **Fast** - ~5 seconds vs ~15 seconds with OpenSSL

### Manual Certificate Generation

```bash
./generate-certs.sh
```

This creates:
- `certs/ca.crt` - CA certificate
- `certs/node.crt` / `certs/node.key` - Node certificate/key (with CN=node)
- `certs/client.root.crt` / `certs/client.root.key` - Root client certificate/key
- `certs/client.craig.crt` / `certs/client.craig.key` - Craig client certificate/key
- `my-safe-directory/ca.key` - CA private key (keep secure!)

### Certificate Expiration

All certificates are valid for 365 days. To check expiration:

```bash
# Check CA certificate
openssl x509 -in certs/ca.crt -noout -dates

# Check node certificate
openssl x509 -in certs/node.crt -noout -dates

# Check client certificate
openssl x509 -in certs/client.root.crt -noout -dates
```

## Configuration

### Environment Variables

```bash
# Change CockroachDB version
CRDB_VERSION=v25.3.4 docker compose up -d

# Default is v25.3.4
```

### Multi-Region Database Setup

```sql
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

- **TCP passthrough** for TLS connections (clients connect directly to CockroachDB with TLS)
- **TCP health checks** on port 26257 (simple connection test)
- **Round-robin load balancing** across all 5 nodes
- **Stats UI** at http://localhost:8404/stats

**Note:** HAProxy operates in TCP mode and passes through encrypted connections. It does not terminate TLS, allowing clients to establish secure connections directly with CockroachDB nodes. Health checks use simple TCP connection tests because the HTTP admin endpoint (port 8080) requires authentication in secure mode.

### Monitoring Node Health

Visit HAProxy stats: http://localhost:8404/stats

- Green = healthy node
- Red = node down or unhealthy

## Stopping the Cluster

```bash
# Stop and remove containers (preserves certificates)
docker compose down

# Stop and remove everything including volumes
docker compose down -v
```

## Common Issues

### "server closed the connection" or "tls error (EOF)"

```
ERROR: server closed the connection.
Is this a CockroachDB node?
failed to connect to `host=localhost user=root database=`: tls error (EOF)
```

This indicates a TLS handshake failure. Common causes:
- **Missing CA certificate**: Ensure `certs/ca.crt` exists and is specified with `--certs-dir=certs` or `sslrootcert=certs/ca.crt`
- **Wrong connection method**: Don't use `--insecure` flag for secure clusters
- **HAProxy misconfiguration**: HAProxy should pass through TLS, not terminate it (already configured correctly)

Solution:
```bash
# Correct way to connect
cockroach sql --certs-dir=certs --host=localhost:26257

# Or with URL
cockroach sql --url "postgresql://root@localhost:26257/defaultdb?sslmode=verify-full&sslrootcert=certs/ca.crt&sslcert=certs/client.root.crt&sslkey=certs/client.root.key"
```

### "Certificate verify failed"

Ensure you're using the correct certificates:
```bash
ls -la certs/
# Should show: ca.crt, node.crt, node.key, client.root.crt, client.root.key
```

### "Connection refused" on 8080-8084

Admin UI uses HTTPS (not HTTP) in secure mode. Use `https://` in your browser and accept the self-signed certificate.

### "Permission denied" on certificate files

```bash
chmod 400 certs/*.key
chmod 644 certs/*.crt
```

### HAProxy shows all nodes as DOWN

Check HAProxy logs for the reason:
```bash
docker logs haproxy
```

Common causes:
- **"401 Unauthorized"**: This means HAProxy tried HTTP health checks on the admin port (8080), which requires auth in secure mode. The config has been updated to use TCP checks instead.
- **Nodes not started**: Check that nodes are running with `docker ps`
- **Network issues**: Check with `docker logs crdb-e1a`

If you see 401 errors, restart HAProxy with the fixed config:
```bash
docker compose restart haproxy
```

## Security Best Practices

1. **Protect CA Key**: Store `my-safe-directory/ca.key` securely offline
2. **Rotate Certificates**: Generate new certs before expiration (365 days)
3. **Limit Access**: Use firewall rules to restrict access to ports
4. **Strong Passwords**: If using password authentication, enforce strong policies
5. **Audit Logs**: Enable cluster audit logging for production

## More Information

- [CockroachDB Security Docs](https://www.cockroachlabs.com/docs/stable/security-reference/transport-layer-security)
- [Multi-Region Capabilities](https://www.cockroachlabs.com/docs/stable/multiregion-overview)
- [HAProxy Documentation](https://docs.haproxy.org/)

## License

This example configuration is provided for educational purposes. CockroachDB is licensed under the Business Source License 1.1 and/or Apache License 2.0.
