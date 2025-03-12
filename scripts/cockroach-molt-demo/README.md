# **🚀 PostgreSQL to CockroachDB Migration Using Molt Tools (Podman/Docker)**
This guide includes:
- **Schema migration** using **Molt [Convert](https://www.cockroachlabs.com/docs/molt/molt-overview#schema-conversion-tool)**
- **Data migration** using **Molt [Fetch](https://www.cockroachlabs.com/docs/molt/molt-overview#fetch)**
- **Validation** using **Molt [Verify](https://www.cockroachlabs.com/docs/molt/molt-overview#verify)**

---

## **🛠 Prerequisites**
1. **[Podman](https://podman-desktop.io/)** (or **[Docker](https://docs.docker.com/get-started/get-docker/)**) installed.
2. **CockroachDB and PostgreSQL running in containers**.
3. **[Molt CLI](https://www.cockroachlabs.com/docs/releases/molt)** running via Podman/Docker.

---

## **Step 1: Start PostgreSQL and CockroachDB in Podman**
Start a **PostgreSQL** container:

```sh
podman run --name postgres \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_USER=admin \
  -e POSTGRES_DB=sampledb \
  -p 5432:5432 -d postgres
```

Start a **CockroachDB** container:

```sh
podman run --name crdb \
  -p 26257:26257 -p 8080:8080 \
  -d cockroachdb/cockroach start-single-node --insecure
```

Check if they are running:

```sh
podman ps
```

---

## **Step 2: Create a Sample Table in PostgreSQL**
Connect to PostgreSQL:

```sh
podman exec -it postgres psql -U admin -d sampledb
```

Run:

```sql
-- Create an ENUM type
CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');

-- Create the users table with an ENUM column
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role user_role NOT NULL DEFAULT 'viewer'
);

-- Insert sample data
INSERT INTO users (name, email, role) VALUES
    ('Alice', 'alice@example.com', 'admin'),
    ('Bob', 'bob@example.com', 'editor'),
    ('Charlie', 'charlie@example.com', 'viewer');
```

Exit:

```sh
\q
```

Validate data:

```sh
podman exec -it postgres psql -U admin -d sampledb -c "SELECT * FROM users;"
```

---

## **Step 3: Extract PostgreSQL Schema**
Dump only the **schema (DDL)**:

```sh
mkdir -p molt-data
```
```sh
podman exec -i postgres pg_dump -U admin -d sampledb --schema-only > molt-data/postgres_schema.sql
```

Verify:

```sh
cat molt-data/postgres_schema.sql
```

---

## **Step 4: Convert PostgreSQL Schema to CockroachDB Format**
Run **Molt Convert** to transform the schema.

```sh
podman run --rm \
  -v $(pwd)/molt-data:/molt-data \
  cockroachdb/molt convert postgres \
  --schema /molt-data/postgres_schema.sql \
  --url "postgres://root@host.docker.internal:26257/defaultdb?sslmode=disable"
```

If there are **failed statements**, edit them manually:

```sh
vi molt-data/postgres_schema.sql.1
```

Once fixed, **apply the converted schema to CockroachDB**:

```sh
podman exec -i crdb cockroach sql --insecure --host=localhost < molt-data/postgres_schema.sql.1
```

Validate the schema:

```sh
podman exec -it crdb cockroach sql --insecure --host=localhost -e "SHOW TABLES;"
```

---

## **Step 5: Migrate Data Using Molt Fetch**
Instead of using `pg_dump`, we'll use **Molt Fetch** to migrate data.

```sh
podman run --rm \
  -v $(pwd)/molt-data:/molt-data \
  cockroachdb/molt fetch \
  --source "postgres://admin:secret@host.docker.internal:5432/sampledb?sslmode=disable" \
  --target "postgres://root@host.docker.internal:26257/defaultdb?sslmode=disable" \
  --allow-tls-mode-disable \
  --direct-copy \
  /molt-data/fetch_output.sql
```

> **Explanation:**
> - **`--direct-copy`** → Enables **direct data migration** from PostgreSQL to CockroachDB.
> - **`fetch_output.sql`** → Contains any necessary adjustments for compatibility.

Once completed, **apply the data to CockroachDB**:

```sh
podman exec -i crdb cockroach sql --insecure --host=localhost < molt-data/fetch_output.sql
```

---

## **Step 6: Verify Data Using Molt Verify**
Now, **Molt Verify** will compare the **PostgreSQL** and **CockroachDB** datasets to ensure correctness.

```sh
podman run --rm \
  -v $(pwd)/molt-data:/molt-data \
  cockroachdb/molt verify \
  --source "postgres://admin:secret@host.docker.internal:5432/sampledb?sslmode=disable" \
  --target "postgres://root@host.docker.internal:26257/defaultdb?sslmode=disable" \
  --allow-tls-mode-disable
```

> **What this does:**
> - Compares the data between PostgreSQL and CockroachDB.
> - Ensures no rows are missing or corrupted.

If any mismatches are found, **Molt Verify** will report them.

---

## **Step 7: Final Validation in CockroachDB**
Manually check if data exists:

```sh
podman exec -it crdb cockroach sql --insecure --host=localhost -e "SELECT * FROM users;"
```

Expected output:
```
 id |   name   |        email         |  role  
----+---------+---------------------+---------
  1 | Alice   | alice@example.com   | admin
  2 | Bob     | bob@example.com     | editor
  3 | Charlie | charlie@example.com | viewer
(3 rows)
```

---

## **Step 8: Cleanup (Optional)**
Once the migration is verified, stop and remove the containers:

```sh
podman stop postgres crdb
podman rm postgres crdb
```

---

## **✅ Summary of Steps**
| Step  | Command                             | Purpose                                     |
|-------|-------------------------------------|---------------------------------------------|
| **1** | `podman run`                        | Start PostgreSQL & CockroachDB              |
| **2** | `psql -U admin -d sampledb`         | Create tables in PostgreSQL                 |
| **3** | `pg_dump --schema-only`             | Extract PostgreSQL schema                   |
| **4** | `molt convert postgres`             | Convert schema for CockroachDB              |
| **5** | `molt fetch`                        | Migrate data from PostgreSQL to CockroachDB |
| **6** | `molt verify`                       | Validate data integrity                     |
| **7** | `SHOW TABLES; SELECT * FROM users;` | Final manual validation                     |

---

## **🎯 Final Checks**
✅ **Schema exists in CockroachDB (`SHOW TABLES;`)**  
✅ **Data exists and matches PostgreSQL (`SELECT * FROM users;`)**  
✅ **Molt Verify confirms data integrity**

---