#!/bin/bash

# Always use the latest cockroach image
if [ -z "$(docker images -q cockroachdb/cockroach:latest 2> /dev/null)" ]; then
    docker rmi -f "$(docker images -q cockroachdb/cockroach:latest)"
fi

# region networks
docker network create --driver=bridge us-east-1-net

if [ -d "./data" ]
then
    rm -rf data
else
    echo "data directory doesn't exist. Skipping.."
fi

# us-east-1
mkdir -p data/us-east-1
cat - >data/us-east-1/haproxy.cfg <<EOF

global
  maxconn 4096

defaults
    mode                tcp
    # Timeout values should be configured for your specific use.
    # See: https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#4-timeout%20connect
    timeout connect     10s
    timeout client      10m
    timeout server      10m
    # TCP keep-alive on client side. Server already enables them.
    option              clitcpka

listen psql
    bind :26257
    mode tcp
    balance roundrobin
    option httpchk GET /health?ready=1
    server cockroach1 roach-newyork-1:26257 check port 8080
    server cockroach3 roach-newyork-2:26257 check port 8080
    server cockroach2 roach-newyork-3:26257 check port 8080

EOF

# New York
docker run -d --name=roach-newyork-1 --hostname=roach-newyork-1 --net=us-east-1-net -p 26257:26257 -p 8080:8080 -v "roach-newyork-1-data:/cockroach/cockroach-data" cockroachdb/cockroach:latest start --insecure --join=roach-newyork-1,roach-newyork-2,roach-newyork-3
sleep 10
docker run -d --name=roach-newyork-2 --hostname=roach-newyork-2 --net=us-east-1-net -v "roach-newyork-2-data:/cockroach/cockroach-data" cockroachdb/cockroach:latest start --insecure --join=roach-newyork-1,roach-newyork-2,roach-newyork-3
sleep 10
docker run -d --name=roach-newyork-3 --hostname=roach-newyork-3 --net=us-east-1-net -v "roach-newyork-3-data:/cockroach/cockroach-data" cockroachdb/cockroach:latest start --insecure --join=roach-newyork-1,roach-newyork-2,roach-newyork-3
sleep 10
# New York HAProxy
docker run -d --name haproxy-newyork -p 26258:26257 --net=us-east-1-net -v "$(pwd)"/data/us-east-1/:/usr/local/etc/haproxy:ro haproxy:1.7
sleep 10

docker exec -it roach-newyork-1 ./cockroach init --insecure

sleep 10

if [[ $OSTYPE == 'darwin'* ]]; then
  open http://localhost:8080/#/overview/list
fi
