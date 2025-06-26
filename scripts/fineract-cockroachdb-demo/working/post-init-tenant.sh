#!/bin/sh

echo "⏳ Waiting for tenant_server_connections table..."

# Wait until the tenant_server_connections table is created
until cockroach sql --insecure --host=cockroachdb --database=fineract_tenants \
  -e "SHOW TABLES;" --format=csv | grep -q ",tenant_server_connections,"; do
  echo "⏳ Waiting for tenant_server_connections table to become available..."
  sleep 2
done

echo "✅ Table exists."

# Wait until the row with id = 1 is available
echo "⏳ Waiting for row with id = 1..."
until cockroach sql --insecure --host=cockroachdb --database=fineract_tenants \
  -e "SELECT 1 FROM tenant_server_connections WHERE id = 1;" | grep -q "1"; do
  echo "⏳ Waiting for row id = 1 to become available..."
  sleep 2
done

echo "✅ Row with id = 1 found."

# Detect available columns
columns=$(cockroach sql --insecure --host=cockroachdb --database=fineract_tenants \
  -e "SHOW COLUMNS FROM tenant_server_connections;" --format=csv)

# Build dynamic UPDATE statement
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

echo "🚀 Executing update:"
echo "$update_stmt"

cockroach sql --insecure --host=cockroachdb --database=fineract_tenants -e "$update_stmt"

