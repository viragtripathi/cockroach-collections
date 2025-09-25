# Node 2 (e.g., us-central-1)
cockroach start \
  --insecure \
  --store=node2 \
  --locality=region=us-central-1,zone=b \
  --advertise-addr=localhost:26258 \
  --http-addr=localhost:8081 \
  --listen-addr=localhost:26258 \
  --join=localhost:26257,localhost:26258,localhost:26259 \
  --background
