# Convert CockroachDB Changefeed output to Debezium format

## Step-by-Step Example

**1.** Create the `orders` table

````sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    order_total DECIMAL(10, 2),
    order_status STRING,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now() ON UPDATE now()
);
````

**2.** Create the Changefeed
<br>To create a Changefeed that streams data in JSON format, using the correct connection string format, follow this structure. Ensure you specify a valid target sink like Kafka or cloud storage:

**Example for a Local Kafka Sink:**
````sql
CREATE CHANGEFEED FOR TABLE orders
INTO 'kafka://localhost:9092?topic=orders_changes'
WITH format = 'json', resolved = '10s';
````
This would stream changes from the orders table to a Kafka topic called orders_changes in JSON format. The resolved timestamps will be emitted every 10 seconds.

**3.** Start the Kafka environment

````bash
./kafka_kraft_setup.sh
````

**4.** Start the Kafka Console Consumer

````bash
./kafka_start_consumer.sh
````

**5.** Convert the Changefeed

````bash
cat changefeed_event.json
{"after": {"created_at": "2024-08-21T20:05:02.048754", "customer_id": "3b75f86e-d3ad-4b7e-bb27-ef0e50c6f36e", "id": "ddbeddb2-ef34-444f-a5f4-1eae49a1e9bf", "order_status": "Pending", "order_total": 150.75, "updated_at": "2024-08-21T20:05:02.048754"}, "operation": "insert"}

➜  python3 changefeed_to_debezium.py changefeed_event.json
Loaded changefeed event from file: changefeed_event.json
{
  "before": null,
  "after": {
    "created_at": "2024-08-21T20:05:02.048754",
    "customer_id": "3b75f86e-d3ad-4b7e-bb27-ef0e50c6f36e",
    "id": "ddbeddb2-ef34-444f-a5f4-1eae49a1e9bf",
    "order_status": "Pending",
    "order_total": 150.75,
    "updated_at": "2024-08-21T20:05:02.048754"
  },
  "op": "c",
  "source": {
    "version": "2.7.1.Final",
    "connector": "cockroachdb",
    "name": "dbserver1",
    "ts_ms": 1724285102048,
    "db": "orders_db",
    "table": "orders"
  },
  "ts_ms": 1724285102048
}
````