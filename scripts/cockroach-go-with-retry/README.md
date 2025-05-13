## ✅ CockroachDB Connection Retry Example (Go + pgx)

This repository demonstrates how to implement **safe connection and query retries** in Go when using [CockroachDB](https://www.cockroachlabs.com/) with the [`pgx`](https://github.com/jackc/pgx) PostgreSQL driver.

---

## 📌 Why This Matters

CockroachDB uses PostgreSQL error codes and is a distributed database. This means you can occasionally hit transient errors like:

- `08006` — connection failure
- `57P03` — cannot connect now
- `57P01` — admin shutdown

Most Go drivers (even `pgx`) **don’t retry automatically**. If a connection drops or a node is unavailable mid-query, the application must retry manually.

---

## ✅ What This Example Covers

- **Connection retries** using exponential backoff
- **Query retries** (via a generic retry wrapper)
- PostgreSQL SQLSTATE code matching (for safe retries)
- Fully uses `pgx/v5` + `pgxpool` (production-ready)

---

## 🔧 Prerequisites

- Go 1.20+
- Docker

---

## 🐳 Step 1: Start CockroachDB v25.1.6 via Docker

```bash
docker run -d \
  --name=cockroach-single \
  -p 26257:26257 -p 8080:8080 \
  cockroachdb/cockroach:v25.1.6 start-single-node \
  --insecure \
  --store=attrs=ssd,path=/cockroach/cockroach-data
````

---

## 🧪 Step 2: Set Up Schema

```bash
docker exec -it cockroach-single ./cockroach sql --insecure
```

Inside the SQL shell:

```sql
CREATE DATABASE defaultdb;
CREATE TABLE defaultdb.users (
  id SERIAL PRIMARY KEY,
  name STRING NOT NULL
);
```

Exit with `\q`

---

## 🧑‍💻 Step 3: Prepare and Run

Tidy up Go dependencies:

```bash
go mod tidy
```

Then run the example:

```bash
go run main.go
```

✅ You should see:

```
Insert succeeded with retry logic.
```

---

## 💥 Step 4: Simulate Failure to Trigger Retry

To simulate a transient error:

```bash
docker stop cockroach-single
sleep 5
docker start cockroach-single
```

When you rerun `main.go`, you'll see retry logs until CockroachDB is back.

---

## 🔁 PostgreSQL SQLSTATE Codes Checked

This example retries on the following error classes:

* `08XXX` — connection exceptions
* `57XXX` — operator intervention (e.g., shutdown, disconnect)

Reference: [PostgreSQL Error Codes](https://www.postgresql.org/docs/current/errcodes-appendix.html)

---

## Use Case

> “Drivers don’t retry failed operations after reconnect — so apps must.”

---