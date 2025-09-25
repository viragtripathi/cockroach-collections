# Node 3 (e.g., us-west-1)
cockroach start \
  --insecure \
  --store=node3 \
  --locality=region=us-west-1,zone=c \
  --advertise-addr=localhost:26259 \
  --http-addr=localhost:8082 \
  --listen-addr=localhost:26259 \
  --join=localhost:26257,localhost:26258,localhost:26259 \
  --background
