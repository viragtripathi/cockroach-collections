#!/bin/sh

echo "Waiting for tenant_server_connections table..."

# Wait until tenant_server_connections exists
until cockroach sql --insecure --host=cockroachdb --database=fineract_tenants -e "SELECT 1 FROM tenant_server_connections LIMIT 1;" >/dev/null 2>&1; do
  echo "Waiting for tenant_server_connections table to become available..."
  sleep 2
done

# Detect which columns are present
columns=$(cockroach sql --insecure --host=cockroachdb --database=fineract_tenants -e "SHOW COLUMNS FROM tenant_server_connections;" --format=csv)

# Build dynamic update statement
update_stmt="UPDATE tenant_server_connections SET
  schema_server = 'cockroachdb',
  schema_server_port = '26257',
  schema_username = 'root',
  schema_password = ''"

echo "$columns" | grep -q 'schema_connection_parameters' && update_stmt="$update_stmt, schema_connection_parameters = ''"
echo "$columns" | grep -q 'readonly_schema_server' && update_stmt="$update_stmt, readonly_schema_server = ''"
echo "$columns" | grep -q 'readonly_schema_server_port' && update_stmt="$update_stmt, readonly_schema_server_port = ''"
echo "$columns" | grep -q 'readonly_schema_username' && update_stmt="$update_stmt, readonly_schema_username = ''"
echo "$columns" | grep -q 'readonly_schema_password' && update_stmt="$update_stmt, readonly_schema_password = ''"
echo "$columns" | grep -q 'readonly_schema_connection_parameters' && update_stmt="$update_stmt, readonly_schema_connection_parameters = ''"

update_stmt="$update_stmt WHERE id = 1;"

echo "Executing update:"
echo "$update_stmt"

cockroach sql --insecure --host=cockroachdb --database=fineract_tenants -e "$update_stmt"
