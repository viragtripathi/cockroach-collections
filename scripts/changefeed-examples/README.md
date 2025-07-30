# CockroachDB Changefeed to Kafka Demo

## Introduction

This demo showcases [CockroachDB's Change Data Capture (CDC)](https://www.cockroachlabs.com/docs/v25.2/change-data-capture-overview) feature (called **changefeeds**) streaming data changes into an Apache Kafka topic. Changefeeds capture row-level changes (inserts, updates, and deletes) from a CockroachDB table and publish them as events to an external sink like Kafka. In this example, we use CockroachDB **v25.2.2** in a single-node insecure cluster, and a local Kafka/Zookeeper instance to demonstrate an end-to-end changefeed. The target table is a **`products`** table in the `testdb` database, containing a realistic schema with a UUID primary key and various fields (strings, decimals, boolean, array, JSONB, etc.). We will see how to set up the changefeed, and examine the **enriched** changefeed messages produced to the Kafka topic, including all components of the feed (before/after data, operation type, timestamps, source metadata, schema info, and resolved timestamps).

## Setup and Running the Demo

**Prerequisites:** Ensure you have Docker and Docker Compose installed. The repository includes a `docker-compose.yml` that defines three services: **CockroachDB**, **Kafka**, and **Zookeeper**. We use Confluent Inc.'s official images for Kafka (`confluentinc/cp-kafka:7.4.0`) and Zookeeper (`confluentinc/cp-zookeeper:7.4.0`), and `cockroachdb/cockroach:v25.2.2` for CockroachDB. All services share a Docker network for connectivity.

Before we can create a changefeed, we must **enable rangefeeds** on CockroachDB, since changefeeds rely on the rangefeed mechanism to stream changes in real-time. The demo setup script takes care of this by executing:

```sql
SET CLUSTER SETTING kv.rangefeed.enabled = true;
```

*(CockroachDB will throw an error if you attempt to create a changefeed before enabling this setting.)*

The general steps to run the demo are:

1. **Launch the Docker Compose cluster:** Run the provided script `./run-demo.sh`. This brings up CockroachDB, Kafka, and Zookeeper containers in the background (`docker-compose up -d`) and waits \~30 seconds for them to become ready.
2. **Initialize the database and changefeed:** The script then runs `setup-cockroachdb.sh`, which:

    * Creates a database `testdb` and a user `testuser` (with no password in insecure mode).
    * Creates a `products` table (in `testdb.public` schema) with a comprehensive schema, including various data types and constraints (see next section).
    * Inserts 5 sample product rows into the table (each with a unique SKU, name, description, price, etc., including one with `sku='MOUSE-003'` for a wireless mouse, which we'll see in the output).
    * Grants the necessary privileges to `testuser` on the `products` table, including the `CHANGEFEED` privilege (non-admin users must have this privilege to create changefeeds on a table).
    * Enables the cluster setting for rangefeeds (as shown above).
    * Creates a **changefeed** on the `products` table that writes to the Kafka topic. This is the core step, explained in detail below.
3. **Verify the changefeed output:** After setup, `run-demo.sh` uses the Kafka console consumer to print messages from the topic `testdb.public.products` (starting from the beginning). You should see JSON messages corresponding to the initial table rows, followed by periodic **resolved** timestamp messages.

Once the script completes, you can also visit the CockroachDB Admin UI at [http://localhost:8080](http://localhost:8080) to inspect the database (the UI is enabled because we exposed port 8080 in Docker). The Kafka broker is reachable at `localhost:9092` for any other Kafka client operations. The topic name we use is `testdb.public.products` (we explicitly set this to include the database and schema for clarity).

## Changefeed Configuration (Creating the Feed)

Let's break down the [`CREATE CHANGEFEED`](https://www.cockroachlabs.com/docs/v25.2/create-and-configure-changefeeds) statement used in this demo and explain each component. The setup script executes the following SQL (against CockroachDB) to start the changefeed:

```sql
USE testdb;
CREATE CHANGEFEED FOR TABLE public.products
INTO 'kafka://kafka:9092?topic_name=testdb.public.products'
WITH envelope = 'enriched', enriched_properties = 'source,schema', updated, diff, resolved = '10s';
```

**Sink URI (Kafka):** The `INTO 'kafka://kafka:9092?...'` part specifies the *sink* as Kafka. Here, `kafka` is the hostname of the Kafka container (as defined in Docker Compose), and `9092` is the Kafka broker port. We provide a query parameter `topic_name=testdb.public.products` to name the topic. By default, if no topic name or prefix is given, Cockroach would use the table name as the topic name. In our case we chose a fully qualified name *testdb.public.products* for clarity (to avoid collisions and indicate the source). Kafka will automatically create this topic when the changefeed connects if auto-creation is enabled on the broker (our Kafka config allows auto-create; we set `auto.create.topics.enable=true` by default in the Confluent image).

**Envelope = 'enriched':** We specify an **enriched envelope** for the changefeed messages. The envelope defines the structure of the emitted messages. The default envelope in CockroachDB is `wrapped`, which would include the row data and some metadata in a simpler format. By choosing `enriched`, we get a more verbose JSON structure that includes additional fields, such as the operation type and timestamps. In fact, using `envelope='enriched'` is what allows the message to carry an `"op"` field indicating the type of operation. With an enriched envelope, each message will contain fields like `"after"` (the state after the change), and `"op"` (operation code). The `"op"` field is `"c"` for inserts/creates, `"u"` for updates, and `"d"` for deletes. In our initial load of data (which is done via inserts), the changefeed records will have `"op": "c"` for each inserted row.

Additionally, with `envelope=enriched`, CockroachDB includes a `"ts_ns"` field representing a timestamp. By default, this `ts_ns` in the envelope is the time the changefeed processed the event (in nanoseconds since epoch). In our output we will see a `ts_ns` value for each message.

**enriched\_properties = 'source,schema':** The enriched envelope can be further augmented with optional **properties**. We requested two of them:

* **`source`:** This adds a `"source"` field in the message payload containing metadata about the source of the change. It includes information such as the CockroachDB cluster ID, the database and table names, the node that produced the change, the changefeed job ID, and so on. Crucially, because we also used the `updated` option (explained next), the source field will include **timestamps of the change event's commit time**. In particular, you'll see `source.ts_hlc` (the CockroachDB **HLC timestamp** of the change commit, as a string) and `source.ts_ns` (the same timestamp in nanosecond int form). By including `enriched_properties='source'` and `updated`, we ensure the commit timestamp of each event is captured in the message. This is important if consumers need to order events by the actual commit time rather than by feed processing time.
* **`schema`:** This adds a `"schema"` field at the top level of each message. The schema field describes the structure (fields and data types) of the payload. Essentially, it provides a self-describing schema for the `"after"`, `"before"`, and other fields in the message. This can be useful for downstream systems to understand the data types or adapt to schema changes over time. Including the schema does make each message larger (since the field definitions are repeated in every message), but it can be valuable for strict schema enforcement or integration with schema-aware systems. In our output, the `"schema"` object will list all fields (with their type, whether they're optional, etc.) for the `before`, `after`, `source`, `ts_ns`, and `op` portions of the payload.

**updated:** The `WITH updated` option tells CockroachDB to include an "updated" timestamp for each row change event. In the context of an enriched envelope, this works in conjunction with the `source` property as mentioned. Essentially, `updated` ensures that the changefeed records carry the **MVCC timestamp** at which the row was updated in the database. Without `updated`, the enriched envelope's `ts_ns` might only reflect when the changefeed job processed the event. With `updated` (plus `enriched_properties='source'`), we get the exact commit timestamp (`ts_hlc`/`ts_ns` in source) which is useful for accurate ordering of events by commit time. Since we did not specify any `cursor` (start time) for the changefeed, it will perform an **initial scan** of the existing table; all those initial results will have an "updated" timestamp equal to the time the changefeed started (because the rows existed already). Going forward, any new writes will carry their actual commit timestamps.

**diff:** We include the `diff` option to capture **before-and-after** states for updates. The diff option instructs the changefeed to add a `"before"` field in the envelope, which contains the previous state of the row before the change. For an **update**, `"before"` will be a JSON object of the row's columns with their old values, and `"after"` will contain the new values after the update. This is extremely useful for auditing or incremental processing scenarios. In the case of an **insert**, there is no "previous" state, so as expected, the `"before"` field will be `null`. In our initial data capture (inserts of new rows), the emitted messages will have `"before": null` because those rows did not exist prior.

**resolved = '10s':** Finally, we set `resolved = '10s'`. This option enables **resolved timestamps** with a frequency of 10 seconds. A *resolved timestamp* is a watermark indicating that **no changes earlier than that timestamp will be produced** in the future. CockroachDB will emit a special message every 10 seconds (approximately) to signify the cluster's progress. The resolved message is separate from the row data messages; it has its own small envelope containing only a `"resolved"` field with a timestamp value (as a string). The presence of resolved events allows downstream consumers to know when they've caught up to a certain point in time. For example, if you see a resolved timestamp `1753805445318192128.0000000000`, it means the changefeed has emitted all changes up to that CockroachDB timestamp. In our demo, the changefeed will emit these every 10 seconds. (Note: CockroachDB requires the `min_checkpoint_frequency` cluster setting to be <= the resolved interval if you use a frequency below 30s, but 10s is allowed with default settings. The script implicitly uses defaults that accommodate this.)

In summary, our changefeed is configured to stream all changes from `testdb.public.products` into Kafka, with each message containing a full JSON envelope of the change (including before/after images, operation type, and metadata), and we also get periodic resolved watermark messages.

## The `products` Table and Initial Data

For completeness, let's summarize the `products` table that is being monitored. The table was created with a variety of columns:

* `id UUID PRIMARY KEY` (defaulting to `gen_random_uuid()` for new rows).
* `sku STRING UNIQUE NOT NULL` – stock keeping unit.
* `name STRING NOT NULL`, `description STRING` (optional text fields).
* `price DECIMAL(10,2) NOT NULL` and `cost DECIMAL(10,2)` – numeric fields with constraints.
* `category STRING NOT NULL`, `brand STRING`.
* `in_stock BOOLEAN` (with default true) and `stock_quantity INTEGER` (inventory count).
* `weight_grams DECIMAL(8,2)`, `dimensions_cm STRING` (dimensions as LxWxH).
* `is_active BOOLEAN` (flag for product active status).
* `tags STRING[]` (array of text tags).
* `metadata JSONB` (for miscellaneous structured data).
* `created_at TIMESTAMP` (default now()), `updated_at TIMESTAMP` (default now()), and `created_by`, `updated_by` (to track user IDs who made changes, null in this demo).

Several secondary indexes are created on sku, category, brand, etc., and a trigger ensures `updated_at` is set to current timestamp on every update. The `setup-cockroachdb.sh` script inserts 5 sample rows into this table. For example, one of the rows inserted is a **Wireless Ergonomic Mouse** with SKU `MOUSE-003` (category "Electronics", brand "TechPro", price \$29.99, cost \$18.50, not in stock with quantity 0, some tags like \["wireless","ergonomic","gaming"], and a JSON metadata of `{"dpi": "12000", "battery_life_hours": 72, "connectivity": "2.4GHz"}`). We will see this row in the changefeed output.

Because we started the changefeed on an existing table without specifying `no_initial_scan`, the **initial table contents** are emitted as **"catch-up" events** on the Kafka topic. Each existing row generates an insert (`"op": "c"`) event at the beginning of the feed. After that, any new insert/update/delete on the table would stream in realtime.

## Observing the Changefeed Output

When you run the demo, the `kafka-console-consumer` will output the messages from the `testdb.public.products` topic. Here is an example of what an **enriched changefeed message** looks like for one of the inserted rows (formatted for readability):

```json
{
  "payload": {
    "after": {
      "brand": "TechPro",
      "category": "Electronics",
      "cost": 18.50,
      "created_at": "2025-07-29T16:10:45.185197",
      "created_by": null,
      "description": "Ergonomic wireless mouse with precision tracking, long battery life, and customizable buttons",
      "dimensions_cm": "12x7x4",
      "id": "ac88f64b-af7d-4174-9284-82f9b348e079",
      "in_stock": false,
      "is_active": true,
      "metadata": {"battery_life_hours": 72, "connectivity": "2.4GHz", "dpi": "12000"},
      "name": "Wireless Ergonomic Mouse",
      "price": 29.99,
      "sku": "MOUSE-003",
      "stock_quantity": 0,
      "tags": ["wireless", "ergonomic", "gaming"],
      "updated_at": "2025-07-29T16:10:45.185197",
      "updated_by": null,
      "weight_grams": 95.00
    },
    "before": null,
    "op": "c",
    "source": {
      "changefeed_sink": "kafka",
      "cluster_id": "b7d4bf91-3164-42eb-9c7e-0b32a10d1653",
      "cluster_name": "",
      "database_name": "testdb",
      "db_version": "v25.2.2",
      "job_id": "1093582996546060289",
      "node_id": "1",
      "node_name": "127.0.0.1",
      "origin": "cockroachdb",
      "primary_keys": ["id"],
      "schema_name": "public",
      "source_node_locality": "",
      "table_name": "products",
      "ts_hlc": "1753805445318192128.0000000000",
      "ts_ns": 1753805445318192128
    },
    "ts_ns": 1753805445363174228
  },
  "schema": {
    "fields": [
      {
        "field": "before",
        "fields": [
          {"field": "id", "optional": false, "type": "string"},
          {"field": "sku", "optional": false, "type": "string"},
          {"field": "name", "optional": false, "type": "string"},
          {"field": "description", "optional": true, "type": "string"},
          {"field": "price", "name": "decimal", "optional": false, "parameters": {"precision": "10", "scale": "2"}, "type": "float64"},
          {"field": "cost", "name": "decimal", "optional": true, "parameters": {"precision": "10", "scale": "2"}, "type": "float64"},
          {"field": "category", "optional": false, "type": "string"},
          {"field": "brand", "optional": true, "type": "string"},
          {"field": "in_stock", "optional": true, "type": "boolean"},
          {"field": "stock_quantity", "optional": true, "type": "int64"},
          {"field": "weight_grams", "name": "decimal", "optional": true, "parameters": {"precision": "8", "scale": "2"}, "type": "float64"},
          {"field": "dimensions_cm", "optional": true, "type": "string"},
          {"field": "is_active", "optional": true, "type": "boolean"},
          {"field": "tags", "items": {"optional": false, "type": "string"}, "optional": true, "type": "array"},
          {"field": "metadata", "optional": true, "type": "json"},
          {"field": "created_at", "name": "timestamp", "optional": true, "type": "string"},
          {"field": "updated_at", "name": "timestamp", "optional": true, "type": "string"},
          {"field": "created_by", "optional": true, "type": "string"},
          {"field": "updated_by", "optional": true, "type": "string"}
        ],
        "name": "products.before.value",
        "optional": true,
        "type": "struct"
      },
      {
        "field": "after",
        "fields": [  /* similar field definitions as "before" */  ],
        "name": "products.after.value",
        "optional": false,
        "type": "struct"
      },
      {
        "field": "source",
        "fields": [
          {"field": "mvcc_timestamp", "optional": true, "type": "string"},
          {"field": "database_name", "optional": false, "type": "string"},
          {"field": "table_name", "optional": false, "type": "string"},
          {"field": "job_id", "optional": false, "type": "string"},
          {"field": "cluster_name", "optional": false, "type": "string"},
          {"field": "cluster_id", "optional": false, "type": "string"},
          {"field": "changefeed_sink", "optional": false, "type": "string"},
          {"field": "db_version", "optional": false, "type": "string"},
          {"field": "node_id", "optional": false, "type": "string"},
          {"field": "node_name", "optional": false, "type": "string"},
          {"field": "primary_keys", "items": {"optional": false, "type": "string"}, "optional": false, "type": "array"},
          {"field": "ts_hlc", "optional": true, "type": "string"},
          {"field": "schema_name", "optional": false, "type": "string"},
          {"field": "origin", "optional": false, "type": "string"},
          {"field": "source_node_locality", "optional": false, "type": "string"},
          {"field": "ts_ns", "optional": true, "type": "int64"}
        ],
        "name": "cockroachdb.source",
        "optional": true,
        "type": "struct"
      },
      {
        "field": "ts_ns",
        "optional": false,
        "type": "int64"
      },
      {
        "field": "op",
        "optional": false,
        "type": "string"
      }
    ],
    "name": "cockroachdb.envelope",
    "optional": false,
    "type": "struct"
  }
}
```

And periodically (every 10s) you'll see a **resolved timestamp message** like:

```json
{"resolved":"1753805445318192128.0000000000"}
```

*(The resolved timestamp is formatted as CockroachDB's HLC timestamp string.)*

Let's interpret the fields in the enriched changefeed message:

* **`payload.after`:** This contains the state of the row *after* the change. In the example above, it lists all columns of the **Wireless Ergonomic Mouse** product after insertion. Since this was a new insert, those are the inserted values. If this were an update event, `after` would show the new values after the update.

* **`payload.before`:** This shows the state of the row *before* the change. In our insert case, `"before": null` (no previous state). For an update, this would be an object with the previous values (because we used the `diff` option to include it). For a delete operation, `after` would be null (row doesn't exist after deletion) and `before` would contain the state prior to deletion.

* **`payload.op`:** The operation code, here `"c"` meaning **create** (insert). If a row were updated, this would be `"u"`; if deleted, `"d"`. This field is present because we used the enriched envelope (standard `wrapped` envelope does not include op by default).

* **`payload.ts_ns`:** A timestamp in nanoseconds denoting when the changefeed processed this event. In our example, `ts_ns: 1753805445363174228` is a large integer timestamp. Note that this is slightly different from the commit timestamp of the transaction – it's the time the change was **emitted** by the changefeed job. The docs note that with only `envelope=enriched`, `ts_ns` is the time the changefeed processed the message. We included `updated` and `source` to also capture the commit time, which appears next:

* **`payload.source`:** This object is included due to `enriched_properties='source'`. It contains metadata about the source and context of this change:

    * Fields like `"database_name": "testdb"`, `"table_name": "products"`, `"origin": "cockroachdb"`, `"changefeed_sink": "kafka"`, etc., identify where the change came from.
    * `"cluster_id"` and `"node_id"` identify the CockroachDB cluster and node that produced the change.
    * `"primary_keys": ["id"]` lists the primary key column(s) of the table (so consumers know the unique key of the row).
    * `"db_version": "v25.2.2"` indicates the CockroachDB version.
    * Most importantly, `"ts_hlc": "1753805445318192128.0000000000"` is the **Hybrid Logical Clock timestamp** of this change, representing the commit time in CockroachDB. This is a string combining a physical timestamp and logical count. The `"ts_ns": 1753805445318192128` (as an integer) in the source is essentially the same timestamp in nanoseconds. These come from using `updated` with `enriched_properties='source'`, which ensures the commit timestamp is included. In our example, the commit HLC was `1753805445318192128` (as seen in source), and the changefeed processed it at `1753805445363174228` (a few hundred thousand nanoseconds later).

* **`schema`:** The top-level schema object (present because we set `enriched_properties='schema'`) describes the structure of the payload. It lists each field in the payload and its type. For instance, it defines that `"before"` is a struct (object) with all the product fields (id, sku, name, etc.) each having a certain type (string, boolean, etc.) and optionality. `"after"` has the same structure (optional = false because after must exist for inserts/updates). The `"source"` field's schema is also described (with various metadata fields and their types). Finally, it shows that `ts_ns` is an `int64` and `op` is a `string`. This schema is useful for consumers to validate and parse the message correctly, especially in systems that can evolve (if the `products` table schema changes, the changefeed's schema field would reflect that change in new messages, allowing consumers to adapt). Keep in mind that including the schema on every message adds overhead, but it provides strong self-descriptive messages.

* **Resolved Message:** The separate `{ "resolved": "…timestamp…" }` messages (with no other payload) indicate **no missing changes up to that timestamp**. CockroachDB emits these to signal downstream systems that it has caught up to a certain time. The resolved timestamp is formatted as a string HLC timestamp. In this demo, we set a 10s interval, so you will see such messages periodically. They have their own minimal envelope (just the "resolved" field). Consumers can use resolved events as watermarks – for example, to know when they can safely move on to processing a new interval of time or to trigger periodic checkpointing in sink applications.

## Conclusion

Through this demo, we've seen an end-to-end setup where CockroachDB streams changes from a table into a Kafka topic using a changefeed. We configured the changefeed with an **enriched JSON envelope** to include comprehensive information: the changed data (before/after), the type of operation, timestamps, source metadata, and schema info. This rich feed can be consumed by downstream systems for various use cases such as auditing, materialized views, real-time ETL, etc.

Key takeaways and features demonstrated:

* **Rangefeed & Changefeed setup:** Enabled the `kv.rangefeed.enabled` cluster setting and used `GRANT CHANGEFEED` privilege for a user to allow creating changefeeds.
* **Kafka sink integration:** Used the `kafka://` URI to direct change events to a Kafka topic. CockroachDB handled connecting to Kafka and writing JSON messages for each change. We explicitly named the topic with `topic_name`, but otherwise Cockroach will default to using the table name as topic.
* **Enriched envelope:** Included operation codes ("c","u","d" for insert/update/delete) in the messages, as well as a processing timestamp. This is a new feature in v25.2 (currently in preview) that gives more context per message.
* **Diff (before/after):** Captured the previous state of rows on updates by using `WITH diff`. In our case, initial inserts show `"before": null` as expected for new rows.
* **Including commit timestamps:** Used `WITH updated, envelope=enriched, enriched_properties=source` to embed the commit timestamp (HLC) of each change in the message. This is crucial for accurately ordering events by transaction commit time if needed.
* **Schema in messages:** Included `enriched_properties=schema` to attach the schema definition of the payload in each message. This makes the feed self-describing, which can be useful for consumers that automatically handle schema evolution.
* **Resolved watermarks:** Configured `resolved='10s'` to get periodic resolved timestamp messages, which help track the progress of the changefeed and can be used to checkpoint or trigger downstream processing logic once no lagging changes remain for a given interval.

By following this README and running the provided scripts, you can observe the CDC stream in action. The CockroachDB documentation provides more details on [how to create and configure changefeeds】, various [changefeed sink options】 (including security configurations for Kafka, etc.), and the specifics of [message [formats](https://www.cockroachlabs.com/docs/v25.2/create-changefeed#format) and [envelopes](https://www.cockroachlabs.com/docs/v25.2/changefeed-message-envelopes)】. This demo uses JSON for simplicity (the default [`format=json`](https://www.cockroachlabs.com/docs/v25.2/create-changefeed#format)), but Avro is also supported (it would require a schema registry and using [`WITH format = avro`](https://www.cockroachlabs.com/docs/v25.2/create-changefeed#format), which we did not cover here).

With this setup, any new insert/update/delete on the `products` table will immediately emit a message to Kafka. You can experiment by opening a SQL shell to the CockroachDB container (or using the admin UI) and performing some inserts or updates on `testdb.public.products` – you should see new messages appear on the Kafka consumer in real time. This confirms the end-to-end changefeed pipeline is working, providing a robust way to capture changes from CockroachDB into streaming systems like Kafka for further processing.
