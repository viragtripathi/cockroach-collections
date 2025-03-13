# Stage 1 - generate certs
FROM cockroachdb/cockroach:latest AS generator

LABEL version="1.0"
LABEL description="cockroach cert generator container"

RUN mkdir -pv /tmp/certs/ca /tmp/certs/crdb-node1-dc1 /tmp/certs/crdb-node2-dc1 /tmp/certs/crdb-node3-dc1 \
    /tmp/certs/crdb-node1-dc2 /tmp/certs/crdb-node2-dc2 /tmp/certs/crdb-node3-dc2 \
    /tmp/safe /tmp/certs/client /tmp/certs/lb

RUN cockroach cert create-ca --certs-dir=/tmp/certs/ca --ca-key=/tmp/safe/ca.key \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/client \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node1-dc1 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node2-dc1 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node3-dc1 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node1-dc2 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node2-dc2 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/crdb-node3-dc2 \
    && cp -v /tmp/certs/ca/ca.crt /tmp/certs/lb

RUN ./cockroach cert create-client root --certs-dir=/tmp/certs/client --ca-key=/tmp/safe/ca.key --also-generate-pkcs8-key
RUN ./cockroach cert create-client roach --certs-dir=/tmp/certs/client --ca-key=/tmp/safe/ca.key --also-generate-pkcs8-key

RUN cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node1-dc1 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node2-dc1 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node3-dc1 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node1-dc2 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node2-dc2 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/crdb-node3-dc2 \
    && cp -v /tmp/certs/client/client.* /tmp/certs/lb

RUN cockroach cert create-node localhost 127.0.0.1 crdb-node1-dc1 lb --certs-dir=/tmp/certs/crdb-node1-dc1 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node2-dc1 lb --certs-dir=/tmp/certs/crdb-node2-dc1 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node3-dc1 lb --certs-dir=/tmp/certs/crdb-node3-dc1 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node1-dc2 lb --certs-dir=/tmp/certs/crdb-node1-dc2 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node2-dc2 lb --certs-dir=/tmp/certs/crdb-node2-dc2 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 crdb-node3-dc2 lb --certs-dir=/tmp/certs/crdb-node3-dc2 --ca-key=/tmp/safe/ca.key
RUN cockroach cert create-node localhost 127.0.0.1 lb --certs-dir=/tmp/certs/lb --ca-key=/tmp/safe/ca.key

# Stage 2 - share certs

FROM alpine:3

RUN mkdir -pv /certs/crdb-node1-dc1 /certs/crdb-node2-dc1 /certs/crdb-node3-dc1 \
    /certs/crdb-node1-dc2 /certs/crdb-node2-dc2 /certs/crdb-node3-dc2 /certs/client /certs/lb

COPY --from=generator  /tmp/certs/crdb-node1-dc1/* /certs/crdb-node1-dc1/
COPY --from=generator  /tmp/certs/crdb-node2-dc1/* /certs/crdb-node2-dc1/
COPY --from=generator  /tmp/certs/crdb-node3-dc1/* /certs/crdb-node3-dc1/
COPY --from=generator  /tmp/certs/crdb-node1-dc2/* /certs/crdb-node1-dc2/
COPY --from=generator  /tmp/certs/crdb-node2-dc2/* /certs/crdb-node2-dc2/
COPY --from=generator  /tmp/certs/crdb-node3-dc2/* /certs/crdb-node3-dc2/
COPY --from=generator  /tmp/certs/client/* /certs/client/
COPY --from=generator /tmp/certs/lb/* /certs/lb/

CMD tail -f /dev/null
