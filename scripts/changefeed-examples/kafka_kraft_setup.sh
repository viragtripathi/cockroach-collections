# Ref: https://kafka.apache.org/quickstart
# setup a local Kafka server that we'll use as CDC sink (using KRaft over ZK)

cd kafka_2.13-3.7.0 || exit
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c config/kraft/server.properties
bin/kafka-server-start.sh config/kraft/server.properties

