## ✅ Working Demo with CockroachDB (With Workaround)

This is a fully working Fineract + CockroachDB Docker demo that bypasses incompatible ALTER statements.

- 🚀 Docker Hub Image: [virag/fineract-cockroachdb-demo](https://hub.docker.com/r/virag/fineract-cockroachdb-demo)
- 📁 Location: [`working`](./working/README.md)
- 🧪 Known Limitations: Full functionality is **not yet guaranteed**. This demo works by bypassing some Liquibase ALTER statements. Further testing is needed.

### Usage

```bash
cd scripts/fineract-cockroachdb-demo/working
docker compose up --build
```

⚠️ If you're looking for the original unpatched version (fails due to `ALTER TABLE` incompatibility), see [`non-working`](./non-working/README.md)
