# Convert changefeed output to Debezium format

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