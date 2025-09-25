## Trino ↔ CockroachDB Demo (via PostgreSQL connector)

This Demo shows Trino querying CockroachDB Cloud using the PostgreSQL connector.

### Prereqs
- Docker
- CockroachDB Cloud CA at `~/.postgresql/root.crt`
- `DATABASE_URL` set, e.g.  
  `export DATABASE_URL="postgresql://USER:PASS@HOST:26257/defaultdb?sslmode=verify-full"`

### Run
```bash
chmod +x run_trino_cockroach_poc.sh
./run_trino_cockroach_poc.sh
