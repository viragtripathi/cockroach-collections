#!/usr/bin/env bash
set -euo pipefail

# === Inputs ===
: "${DATABASE_URL:?Set DATABASE_URL (postgresql://user:pass@host:26257/db?sslmode=verify-full)}"
CERT_PATH="${HOME}/.postgresql/root.crt"
TRINO_IMAGE="trinodb/trino:latest"
CATALOG_NAME="cockroach"
CATALOG_DIR="./etc/catalog"
CERTS_MOUNT_SRC="${HOME}/.postgresql"
CERTS_MOUNT_DST="/root/.postgresql"
CONTAINER_NAME="trino"
TRINO_PORT=8080

# === Preflight ===
if [ ! -f "${CERT_PATH}" ]; then
  echo "❌ CA cert not found at ${CERT_PATH}"; exit 1
fi
mkdir -p "${CATALOG_DIR}"

# === Parse DATABASE_URL safely ===
# Accepts forms like:
#  postgresql://user:pass@host:26257/db?sslmode=verify-full
#  postgresql://user:pass@host:26257/db
proto_stripped="${DATABASE_URL#postgresql://}"
# Split on first '@'
userpass="${proto_stripped%%@*}"
rest="${proto_stripped#*@}"

# user:pass
user="${userpass%%:*}"
pass="${userpass#*:}"

# host:port / path
hostport="${rest%%/*}"
host="${hostport%%:*}"
port="${hostport#*:}"

# db?params
dbq="${rest#*/}"                  # e.g. defaultdb?sslmode=...
db="${dbq%%\?*}"                  # defaultdb
params=""
if [[ "${dbq}" == *"?"* ]]; then
  params="${dbq#*?}"              # sslmode=...
fi

# Build JDBC URL; ensure sslmode + sslrootcert present
jdbc_base="jdbc:postgresql://${host}:${port}/${db}"

# helper to add/replace a query param
add_or_replace_param () {
  local q="$1"; local key="$2"; local val="$3"
  if [[ "${q}" == *"${key}="* ]]; then
    echo "${q}" | awk -v k="${key}" -v v="${val}" '
      BEGIN{FS="&"; OFS="&"}
      {
        for (i=1;i<=NF;i++){
          split($i,a,"=");
          if(a[1]==k){a[2]=v;$i=a[1]"="a[2]}
        }
        print $0
      }' | tr -d '\n'
  else
    [[ -z "${q}" ]] && echo "${key}=${val}" && return
    echo "${q}&${key}=${val}"
  fi
}

# Start with whatever was in the URL
q="${params}"

# enforce sslmode=verify-full
q="$(add_or_replace_param "${q}" "sslmode" "verify-full")"
# enforce sslrootcert path inside container
q="$(add_or_replace_param "${q}" "sslrootcert" "${CERTS_MOUNT_DST}/root.crt")"

jdbc_url="${jdbc_base}?${q}"

# === Write catalog properties ===
cat > "${CATALOG_DIR}/${CATALOG_NAME}.properties" <<EOF
connector.name=postgresql
connection-url=${jdbc_url}
connection-user=${user}
connection-password=\${ENV:TRINO_COCKROACH_PASSWORD}

# Helpful defaults
case-insensitive-name-matching=true
metadata.cache-ttl=1m
EOF

echo "✅ Wrote ${CATALOG_DIR}/${CATALOG_NAME}.properties"
echo "🔐 Password will be supplied via env var only."

# === (Re)start container ===
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "♻️  Removing existing container ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

echo "🚀 Starting Trino on :${TRINO_PORT} ..."
docker run -d --name "${CONTAINER_NAME}" \
  -p ${TRINO_PORT}:8080 \
  -e "TRINO_COCKROACH_PASSWORD=${pass}" \
  -v "$(pwd)/etc/catalog":/etc/trino/catalog \
  -v "${CERTS_MOUNT_SRC}:${CERTS_MOUNT_DST}:ro" \
  "${TRINO_IMAGE}" >/dev/null

# === Wait for readiness ===
echo -n "⏳ Waiting for Trino to accept queries"
for i in {1..60}; do
  if docker exec "${CONTAINER_NAME}" trino -e "SELECT 1" >/dev/null 2>&1; then
    echo " ... ready!"
    break
  fi
  echo -n "."
  sleep 1
  if [[ $i -eq 60 ]]; then
    echo -e "\n❌ Trino did not come up in time. Recent logs:"
    docker logs --tail 200 "${CONTAINER_NAME}" || true
    exit 1
  fi
done

# === Demo SQL ===
read -r -d '' DEMO_SQL <<'SQL'
SHOW CATALOGS;
SHOW SCHEMAS FROM cockroach;

CREATE SCHEMA IF NOT EXISTS cockroach.defaultdb.trino_poc;

CREATE TABLE IF NOT EXISTS cockroach.defaultdb.trino_poc.demo_tbl (
  id UUID,
  name VARCHAR,
  created_at TIMESTAMP
);

INSERT INTO cockroach.defaultdb.trino_poc.demo_tbl VALUES
  (gen_random_uuid(), 'alpha', current_timestamp),
  (gen_random_uuid(), 'beta',  current_timestamp);

SELECT * FROM cockroach.defaultdb.trino_poc.demo_tbl ORDER BY created_at DESC;

-- CTAS (safe pattern: create empty + insert)
CREATE TABLE IF NOT EXISTS cockroach.defaultdb.trino_poc.demo_ctas AS
SELECT id, name FROM cockroach.defaultdb.trino_poc.demo_tbl WITH NO DATA;
INSERT INTO cockroach.defaultdb.trino_poc.demo_ctas
SELECT id, name FROM cockroach.defaultdb.trino_poc.demo_tbl;

SELECT * FROM cockroach.defaultdb.trino_poc.demo_ctas;

UPDATE cockroach.defaultdb.trino_poc.demo_tbl SET name='alpha2' WHERE name='alpha';
DELETE FROM cockroach.defaultdb.trino_poc.demo_tbl WHERE name='beta';

SELECT * FROM cockroach.defaultdb.trino_poc.demo_tbl ORDER BY created_at DESC;
SQL

echo "▶️  Running demo queries..."
docker exec -i "${CONTAINER_NAME}" trino <<EOF
${DEMO_SQL}
EOF

cat <<EON

✅ Demo complete.

Web UI:   http://localhost:${TRINO_PORT}
Catalog:  ${CATALOG_NAME}
DB:       ${db}
User:     ${user}

# Cleanup when done:
docker rm -f ${CONTAINER_NAME}
EON

