#!/bin/bash

docker rmi -f crdb
docker build -t crdb .

# region networks
docker network create --driver=bridge --subnet=172.27.0.0/16 --ip-range=172.27.0.0/24 --gateway=172.27.0.1 us-west-2-net
docker network create --driver=bridge --subnet=172.28.0.0/16 --ip-range=172.28.0.0/24 --gateway=172.28.0.1 us-east-1-net
docker network create --driver=bridge --subnet=172.29.0.0/16 --ip-range=172.29.0.0/24 --gateway=172.29.0.1 eu-west-1-net

# inter-regional networks
docker network create --driver=bridge --subnet=172.30.0.0/16 --ip-range=172.30.0.0/24 --gateway=172.30.0.1 uswest-useast-net
docker network create --driver=bridge --subnet=172.31.0.0/16 --ip-range=172.31.0.0/24 --gateway=172.31.0.1 useast-euwest-net
docker network create --driver=bridge --subnet=172.32.0.0/16 --ip-range=172.32.0.0/24 --gateway=172.32.0.1 uswest-euwest-net

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
    server cockroach2 roach-newyork-3:26257 check port 8080
    server cockroach3 roach-newyork-2:26257 check port 8080

EOF

# us-west-2
mkdir data/us-west-2
cat - >data/us-west-2/haproxy.cfg <<EOF

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
    server cockroach4 roach-seattle-1:26257 check port 8080
    server cockroach5 roach-seattle-2:26257 check port 8080
    server cockroach6 roach-seattle-3:26257 check port 8080

EOF

# eu-west-1
mkdir data/eu-west-1
cat - >data/eu-west-1/haproxy.cfg <<EOF

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
    server cockroach7 roach-london-1:26257 check port 8080
    server cockroach8 roach-london-2:26257 check port 8080
    server cockroach9 roach-london-3:26257 check port 8080
EOF

# Seattle
docker run -d --name=roach-seattle-1 --hostname=roach-seattle-1 --ip=172.27.0.11 --cap-add NET_ADMIN --net=us-west-2-net --add-host=roach-seattle-1:172.27.0.11 --add-host=roach-seattle-2:172.27.0.12 --add-host=roach-seattle-3:172.27.0.13 -p 8080:8080 -v "roach-seattle-1-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-west-2,zone=a
sleep 10
docker run -d --name=roach-seattle-2 --hostname=roach-seattle-2 --ip=172.27.0.12 --cap-add NET_ADMIN --net=us-west-2-net --add-host=roach-seattle-1:172.27.0.11 --add-host=roach-seattle-2:172.27.0.12 --add-host=roach-seattle-3:172.27.0.13 -p 8081:8080 -v "roach-seattle-2-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-west-2,zone=b
sleep 10
docker run -d --name=roach-seattle-3 --hostname=roach-seattle-3 --ip=172.27.0.13 --cap-add NET_ADMIN --net=us-west-2-net --add-host=roach-seattle-1:172.27.0.11 --add-host=roach-seattle-2:172.27.0.12 --add-host=roach-seattle-3:172.27.0.13 -p 8082:8080 -v "roach-seattle-3-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-west-2,zone=c
sleep 10
# Seattle HAProxy
docker run -d --name haproxy-seattle --ip=172.27.0.10 -p 26257:26257 --net=us-west-2-net -v `pwd`/data/us-west-2/:/usr/local/etc/haproxy:ro haproxy:1.7
sleep 10

# New York
docker run -d --name=roach-newyork-1 --hostname=roach-newyork-1 --ip=172.28.0.11 --cap-add NET_ADMIN --net=us-east-1-net --add-host=roach-newyork-1:172.28.0.11 --add-host=roach-newyork-2:172.28.0.12 --add-host=roach-newyork-3:172.28.0.13 -p 8180:8080 -v "roach-newyork-1-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-east-1,zone=a
sleep 10
docker run -d --name=roach-newyork-2 --hostname=roach-newyork-2 --ip=172.28.0.12 --cap-add NET_ADMIN --net=us-east-1-net --add-host=roach-newyork-1:172.28.0.11 --add-host=roach-newyork-2:172.28.0.12 --add-host=roach-newyork-3:172.28.0.13 -p 8181:8080 -v "roach-newyork-2-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-east-1,zone=b
sleep 10
docker run -d --name=roach-newyork-3 --hostname=roach-newyork-3 --ip=172.28.0.13 --cap-add NET_ADMIN --net=us-east-1-net --add-host=roach-newyork-1:172.28.0.11 --add-host=roach-newyork-2:172.28.0.12 --add-host=roach-newyork-3:172.28.0.13 -p 8182:8080 -v "roach-newyork-3-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=us-east-1,zone=c
sleep 10
# New York HAProxy
docker run -d --name haproxy-newyork --ip=172.28.0.10 -p 26258:26257 --net=us-east-1-net -v `pwd`/data/us-east-1/:/usr/local/etc/haproxy:ro haproxy:1.7
sleep 10

# London
docker run -d --name=roach-london-1 --hostname=roach-london-1 --ip=172.29.0.11 --cap-add NET_ADMIN --net=eu-west-1-net --add-host=roach-london-1:172.29.0.11 --add-host=roach-london-2:172.29.0.12 --add-host=roach-london-3:172.29.0.13 -p 8280:8080 -v "roach-london-1-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=eu-west-1,zone=a
sleep 10
docker run -d --name=roach-london-2 --hostname=roach-london-2 --ip=172.29.0.12 --cap-add NET_ADMIN --net=eu-west-1-net --add-host=roach-london-1:172.29.0.11 --add-host=roach-london-2:172.29.0.12 --add-host=roach-london-3:172.29.0.13 -p 8281:8080 -v "roach-london-2-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=eu-west-1,zone=b
sleep 10
docker run -d --name=roach-london-3 --hostname=roach-london-3 --ip=172.29.0.13 --cap-add NET_ADMIN --net=eu-west-1-net --add-host=roach-london-1:172.29.0.11 --add-host=roach-london-2:172.29.0.12 --add-host=roach-london-3:172.29.0.13 -p 8282:8080 -v "roach-london-3-data:/cockroach/cockroach-data" crdb start --insecure --join=roach-seattle-1,roach-newyork-1,roach-london-1 --locality=region=eu-west-1,zone=c
sleep 10
# London HAProxy
docker run -d --name haproxy-london --ip=172.29.0.10 -p 26259:26257 --net=eu-west-1-net -v `pwd`/data/eu-west-1/:/usr/local/etc/haproxy:ro haproxy:1.7
sleep 10

docker exec -it roach-newyork-1 ./cockroach init --insecure
sleep 10

# Seattle
for j in 1 2 3
do
    docker network connect uswest-useast-net roach-seattle-$j
    docker network connect uswest-euwest-net roach-seattle-$j
    docker exec roach-seattle-$j tc qdisc add dev eth1 root netem delay 30ms
    docker exec roach-seattle-$j tc qdisc add dev eth2 root netem delay 90ms
done

# New York
for j in 1 2 3
do
    docker network connect uswest-useast-net roach-newyork-$j
    docker network connect useast-euwest-net roach-newyork-$j
    docker exec roach-newyork-$j tc qdisc add dev eth1 root netem delay 32ms
    docker exec roach-newyork-$j tc qdisc add dev eth2 root netem delay 60ms
done

# London
for j in 1 2 3
do
    docker network connect useast-euwest-net roach-london-$j
    docker network connect uswest-euwest-net roach-london-$j
    docker exec roach-london-$j tc qdisc add dev eth1 root netem delay 62ms
    docker exec roach-london-$j tc qdisc add dev eth2 root netem delay 88ms
done

sleep 10
if [[ $OSTYPE == 'darwin'* ]]; then
  open http://localhost:8080/#/overview/list
fi
