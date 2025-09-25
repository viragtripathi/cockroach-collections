# Node 1 (e.g., us-east-1)
cockroach start \
  --insecure \
  --store=node1 \
  --locality=region=us-east-1,zone=a \
  --advertise-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --listen-addr=localhost:26257 \
  --join=localhost:26257,localhost:26258,localhost:26259 \
  --background
