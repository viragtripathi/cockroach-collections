# Ory Hydra & Ory Kratos Integration with CockroachDB

## Table of Contents
1. [Introduction](#introduction)
2. [Why Use CockroachDB](#why-use-cockroachdb)
3. [Architecture Overview](#architecture-overview)
4. [Setup Prerequisites](#setup-prerequisites)
5. [Integrated Example: Hydra + Kratos + CockroachDB](#integrated-example-hydra--kratos--cockroachdb)
    - Step 1: Project Structure
    - Step 2: CockroachDB Setup
    - Step 3: Ory Hydra Configuration
    - Step 4: Ory Kratos Configuration
    - Step 5: UI Application Setup
    - Step 6: Testing the Integration
6. [Ory Hydra Standalone Setup](#ory-hydra-standalone-setup)
7. [Ory Kratos Standalone Setup](#ory-kratos-standalone-setup)
8. [Conclusion](#conclusion)

---

## Introduction

This guide demonstrates how to integrate Ory Hydra (OAuth2 provider) and Ory Kratos (identity management system) with CockroachDB to build a scalable, secure authentication and authorization system. We will cover both integrated and standalone setups to give you flexibility in using these tools.

---

## Why Use CockroachDB

### Key Features
CockroachDB is a distributed SQL database designed for global scalability, high availability, and strong consistency. Key benefits include:

- **Global Distribution**: Replicates data across multiple regions, reducing latency for globally distributed applications.
- **High Availability**: Provides automatic failover and resilience to node or regional failures.
- **Scalability**: Scales horizontally, handling increased loads by adding more nodes.
- **Consistency**: Ensures serializable isolation, making it ideal for sensitive data like user authentication and authorization.

In our example, CockroachDB serves as a unified backend for both Ory Hydra and Ory Kratos, leveraging its distributed nature for low-latency access across regions.

---

## Architecture Overview

### Architecture Summary
1. **CockroachDB Cluster**: Distributed across multiple regions for high availability.
2. **Ory Hydra**: Manages OAuth2 authorization and token issuance.
3. **Ory Kratos**: Handles identity management and user authentication.
4. **UI Application**: Simple Node.js app for user login and consent.


## Setup Prerequisites
- Docker & Docker Compose
- CockroachDB (latest version)
- Ory Hydra (latest version)
- Ory Kratos (latest version)
- Node.js for UI application
- `curl` and `jq` (optional)

---

## Integrated Example: Hydra + Kratos + CockroachDB

### Step 1: Project Structure
Create the necessary files:
```bash
mkdir ory-demo && cd ory-demo
touch docker-compose.yml hydra.yml kratos.yml identity.schema.json server.js
```

### Step 2: CockroachDB Setup
**`docker-compose.yml`**
```yaml
version: '3.8'
services:
  cockroachdb:
    image: cockroachdb/cockroach:latest
    command: start-single-node --insecure --listen-addr=0.0.0.0
    ports:
      - "26257:26257"
      - "8080:8080"
    volumes:
      - cockroach-data:/cockroach/cockroach-data
    restart: always
volumes:
  cockroach-data:
```

**Initialize CockroachDB**
```bash
docker-compose up -d cockroachdb
docker exec -it cockroachdb ./cockroach sql --insecure --execute "
CREATE DATABASE hydra;
CREATE DATABASE kratos;
CREATE USER hydra_user WITH PASSWORD 'hydra_pass';
CREATE USER kratos_user WITH PASSWORD 'kratos_pass';
GRANT ALL ON DATABASE hydra TO hydra_user;
GRANT ALL ON DATABASE kratos TO kratos_user;
"
```

### Step 3: Ory Hydra Configuration
**`hydra.yml`**
```yaml
dsn: cockroach://hydra_user:hydra_pass@cockroachdb:26257/hydra?sslmode=disable
serve:
  public:
    base_url: http://localhost:4444
  admin:
    base_url: http://localhost:4445
urls:
  self:
    public: http://localhost:4444
    admin: http://localhost:4445
  login: http://localhost:3000/login
  consent: http://localhost:3000/consent
oidc:
  subject_identifiers:
    supported_types: ["public"]
```

**Docker Compose**
```yaml
  hydra:
    image: oryd/hydra:latest
    volumes:
      - ./hydra.yml:/etc/hydra/hydra.yml
    ports:
      - "4444:4444"
      - "4445:4445"
    depends_on:
      - cockroachdb
```

### Step 4: Ory Kratos Configuration
**`kratos.yml`**
```yaml
dsn: cockroach://kratos_user:kratos_pass@cockroachdb:26257/kratos?sslmode=disable
identity:
  default_schema_url: file:///etc/kratos/identity.schema.json
```

**`identity.schema.json`**
```json
{
  "$id": "https://example.com/identity.schema.json",
  "type": "object",
  "properties": {
    "traits": {
      "email": { "type": "string", "format": "email" }
    }
  }
}
```

### Step 5: UI Application Setup
**`server.js`**
```javascript
const express = require('express');
const app = express();
app.get('/login', (req, res) => res.send('<form method="POST"><input type="email" name="email"/><button type="submit">Login</button></form>'));
app.listen(3000, () => console.log('UI running on http://localhost:3000'));
```

### Step 6: Testing the Integration
1. Start the services:
   ```bash
   docker-compose up -d
   ```
2. Create OAuth2 client:
   ```bash
   docker exec hydra hydra clients create \
     --endpoint http://localhost:4445 \
     --id client_id \
     --secret client_secret \
     --grant-types authorization_code,refresh_token \
     --response-types code,id_token \
     --redirect-uris http://localhost:3000/callback
   ```

---

## Ory Hydra Standalone Setup
For users only interested in OAuth2 and token management:

1. Follow the **CockroachDB Setup** and **Ory Hydra Configuration** steps.
2. Skip the Kratos-related sections.
3. Test token issuance using `curl` commands.

---

## Ory Kratos Standalone Setup
For users only interested in identity management:

1. Follow the **CockroachDB Setup** and **Ory Kratos Configuration** steps.
2. Skip the Hydra-related sections.
3. Test user authentication using the UI application.

---

## Conclusion

In this guide, we've demonstrated both an integrated setup of Ory Hydra + Ory Kratos with CockroachDB, as well as standalone setups for each tool. This architecture is scalable, resilient, and optimized for distributed environments, making it suitable for globally deployed applications.
