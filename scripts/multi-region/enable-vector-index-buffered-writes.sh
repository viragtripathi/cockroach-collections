# vector index
cockroach sql --insecure --host=localhost:26257 --execute="SHOW CLUSTER SETTING feature.vector_index.enabled;"
cockroach sql --insecure --host=localhost:26257 --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;"
cockroach sql --insecure --host=localhost:26257 --execute="SHOW CLUSTER SETTING feature.vector_index.enabled;"
# buffered writes
cockroach sql --insecure --host=localhost:26257 --execute="SHOW CLUSTER SETTING kv.transaction.write_buffering.enabled;"
cockroach sql --insecure --host=localhost:26257 --execute="SET CLUSTER SETTING kv.transaction.write_buffering.enabled = true;"
cockroach sql --insecure --host=localhost:26257 --execute="SHOW CLUSTER SETTING kv.transaction.write_buffering.enabled;"

