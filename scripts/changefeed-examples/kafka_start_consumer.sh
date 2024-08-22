cd kafka_2.13-3.7.0 || exit
bin/kafka-console-consumer.sh --topic orders --from-beginning --bootstrap-server localhost:9092

