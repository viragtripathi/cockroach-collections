-- Safe to run on startup
CREATE DATABASE IF NOT EXISTS fineract_tenants;
CREATE DATABASE IF NOT EXISTS fineract_default;

UPDATE tenant_server_connections
SET
  schema_server = 'cockroachdb',
  schema_server_port = '26257',
  schema_username = 'root',
  schema_password = '',
  schema_connection_parameters = '',
  readonly_schema_server = '',
  readonly_schema_server_port = '',
  readonly_schema_username = '',
  readonly_schema_password = '',
  readonly_schema_connection_parameters = ''
WHERE id = 1;

UPDATE tenants
SET
  name = 'fineract_default',
  identifier = 'default',
  timezone_id = 'Asia/Kolkata',
  created_date = current_timestamp,
  lastmodified_date = current_timestamp,
  oltp_id = 1
WHERE id = 1;