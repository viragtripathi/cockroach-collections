# Apache Fineract + CockroachDB Demo (Docker-Based)

This repo demonstrates how to run **Apache Fineract** with **CockroachDB** using Docker.  
It sets up a complete local environment suitable for experimentation and future development toward full CockroachDB compatibility.

---

## 🚀 What’s Inside

- 🐳 `docker-compose.yaml` to spin up:
  - CockroachDB (PostgreSQL-compatible mode)
  - Fineract backend (official image)
- 🐚 `init-db.sh` to bootstrap Fineract tenant databases and user in CockroachDB
- 🟢 `start-demo.sh` to launch everything and guide you
- 🧹 `cleanup-demo.sh` to tear down the environment
- ✅ Preconfigured default credentials: `mifos / password`

---

## 🛠️ Requirements

- Docker or Podman (Compose v2 support)
- Bash shell (for running scripts)

---

## ⚙️ Getting Started

Clone this repo:

```bash
git clone https://github.com/YOUR_USERNAME/cockroachdb-fineract-demo.git
cd cockroachdb-fineract-demo
````

### 🔹 Start the environment

```bash
./start-demo.sh
```

This will:

* Start CockroachDB
* Wait until it’s ready
* Create required Fineract databases and a user
* Launch the Fineract backend container

Once started, you’ll see:

```
✅ Fineract is up and running!
📘 Swagger UI:       http://localhost:8080/fineract-provider/swagger-ui.html
🔑 Default login:    mifos / password
📂 Sample endpoint:  http://localhost:8080/fineract-provider/api/v1/clients
```

---

## 🧹 Cleanup

To stop and remove everything:

```bash
./cleanup-demo.sh
```

---

## ⚠️ Known Limitations (CockroachDB Compatibility)

This demo **does not fully work yet out-of-the-box** due to an incompatibility in Fineract’s Liquibase migrations:

* ❌ `ALTER COLUMN TYPE ...` on indexed columns is not supported in CockroachDB
* ❌ Liquibase fails during startup with:

  ```
  ERROR: unimplemented: ALTER COLUMN TYPE requiring rewrite of on-disk data is currently not supported
  ```

This means **the Fineract server does not finish initializing**, and schema migrations are incomplete.

---

## 🔗 References

* [Apache Fineract](https://github.com/apache/fineract)
* [CockroachDB Docs - PostgreSQL Compatibility](https://www.cockroachlabs.com/docs/stable/postgresql-compatibility.html)
* [CockroachDB Issue #47636 (ALTER COLUMN TYPE)](https://github.com/cockroachdb/cockroach/issues/47636)

