cockroach sql --insecure --host=localhost:26257 \
  --execute="INSERT INTO system.locations VALUES \
  ('region', 'us-east-1', 37.478397, -76.453077), \
  ('region', 'us-central-1', 41.2619, -95.8608), \
  ('region', 'us-west-1', 38.837522, -120.895824);"
