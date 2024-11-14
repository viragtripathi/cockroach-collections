# Ory Hydra & Ory Kratos Integration with CockroachDB

## Introduction

This guide demonstrates how to integrate Ory Hydra (OAuth2 provider) and Ory Kratos (identity management system) with CockroachDB. The combination of these powerful tools provides a highly scalable and secure solution for managing authentication and authorization across distributed systems.

## Why CockroachDB?

### Key Features of CockroachDB
CockroachDB is a **distributed, cloud-native SQL database** that is highly available, resilient, and capable of running across multiple regions. It offers several out-of-the-box features that make it an ideal choice for this kind of integration:

1. **Global Distribution**: CockroachDB allows you to distribute your data across multiple regions and data centers, reducing latency and improving performance for users worldwide.

2. **High Availability**: With its **multi-active availability** feature, CockroachDB can survive node, rack, and even region failures without manual intervention, ensuring zero downtime for critical services like authentication and authorization.

3. **Consistency and Strong Guarantees**: CockroachDB offers **serializable isolation**, ensuring that transactions are consistent even in a distributed environment. This is crucial for systems managing sensitive identity and authorization data.

4. **Scalability**: Horizontal scaling makes CockroachDB perfect for applications experiencing dynamic workloads. You can easily add nodes to the cluster without downtime.

5. **Automatic Failover**: CockroachDB automatically handles failovers and maintains data integrity, which is essential for services that span across multiple data centers.

### Benefits in This Use Case
Integrating Ory Hydra and Kratos with CockroachDB ensures:
- **Low latency** for global users through regional distribution.
- **Resilience** in the face of infrastructure failures.
- **Scalable identity management** that can handle high volumes of authentication requests across distributed services.

---

## High-Level Architecture Overview

### Architecture Breakdown

**1. CockroachDB Cluster**:
- The CockroachDB cluster is deployed across multiple regions or data centers.
- Data is **replicated across regions** for low-latency access and high availability.
- Ory Hydra and Ory Kratos use separate databases within CockroachDB (`hydra` and `kratos`) to store their respective data securely.
- **Automatic failover and data consistency** ensure that the system remains operational even if a node or region goes down.

**2. Ory Hydra**:
- Manages OAuth2 authorization flows and token issuance.
- Public endpoint (`http://localhost:4444`): Handles user authentication requests and issues tokens.
- Admin endpoint (`http://localhost:4445`): Used for managing OAuth2 clients, tokens, and introspection.

**3. Ory Kratos**:
- Handles user identity management, registration, and login.
- Public endpoint (`http://localhost:4433`): Manages self-service flows for users (login, registration, password recovery).
- Admin endpoint (`http://localhost:4434`): Manages identity schemas and configurations.

**4. User Interface (UI)**:
- A Node.js-based UI application runs on `http://localhost:3000` to handle user login and consent forms.
- The UI interacts with Ory Kratos for user authentication and consent management.

**5. Data Flow**:
- A user tries to access a protected resource and is redirected to Ory Hydra.
- Ory Hydra delegates user authentication to Ory Kratos.
- The user interacts with the UI to log in and consent to access.
- Upon successful login and consent, Ory Hydra issues OAuth2 tokens.
- The tokens are stored and managed in CockroachDB, leveraging its distributed nature for fast, reliable access across regions.

### Key Benefits of This Architecture
- **Global Performance**: By distributing CockroachDB nodes across regions, the system achieves low-latency access for users no matter where they are located.
- **High Availability**: CockroachDB's distributed and fault-tolerant architecture ensures that authentication services remain available even if a region goes down.
- **Scalability**: Adding new regions or scaling up is straightforward due to CockroachDB's horizontal scalability.
- **Security and Consistency**: Strong consistency guarantees in CockroachDB ensure that sensitive identity and authorization data is accurate and secure.

---

Let's enhance the guide to include an explanation of what Ory Hydra and Ory Kratos are doing in this setup, along with an updated architecture diagram. This will help make the documentation clearer for those unfamiliar with these tools. I'll also generate an architecture diagram to visually represent the integration.

---

# Ory Hydra & Ory Kratos Integration with CockroachDB

## Introduction

In this example, we're integrating Ory Hydra and Ory Kratos with CockroachDB to build a complete authentication and identity management system.

### What is Ory Hydra?
Ory Hydra is an OAuth2 and OpenID Connect server. It helps you securely manage access tokens and handle authorization flows for applications. It does not handle user authentication directly but delegates that to an identity provider.

### What is Ory Kratos?
Ory Kratos is an identity and user management system. It handles tasks like user registration, login, password recovery, and identity management. In this setup, Ory Kratos handles user authentication, while Ory Hydra manages authorization using OAuth2.

### How They Work Together
1. **Ory Hydra** handles OAuth2 flows such as authorization, token issuance, and token validation.
2. **Ory Kratos** takes care of user authentication, identity management, and login/consent flows.
3. **CockroachDB** is used as the database backend for both Ory Hydra and Ory Kratos.

This integration is useful for applications that require secure user authentication and fine-grained access control.

---

## Architecture Diagram
I will now generate an architecture diagram to illustrate how these components interact with each other.



Here's an updated guide with an explanation of what each component is doing, along with a breakdown of the flow in this example. Unfortunately, I wasn't able to generate an architecture diagram due to content policy restrictions. However, I'll describe the architecture in detail so you can create a visual representation if needed.

---

# Ory Hydra & Ory Kratos Integration with CockroachDB

## Introduction

This guide demonstrates how to integrate Ory Hydra and Ory Kratos with CockroachDB to set up a secure authentication and authorization system.

### **What Ory Hydra and Ory Kratos are Doing in This Setup**

**Ory Hydra** is an OAuth2 and OpenID Connect provider:
- It handles **OAuth2 authorization flows** and manages access tokens.
- It delegates user authentication to an identity provider (Ory Kratos in this case).
- It secures APIs by issuing, validating, and refreshing access tokens.

**Ory Kratos** is an identity management solution:
- It handles **user registration, login, and password management**.
- It manages user identities with support for different schemas.
- It provides endpoints for self-service authentication, recovery, and profile management.

**CockroachDB** serves as the backend database:
- Stores data for both Hydra (OAuth2 clients, tokens) and Kratos (user identities, sessions).

### **High-Level Workflow**

1. **User Authentication Flow**:
    - A user initiates the OAuth2 flow by trying to access a protected resource through Hydra.
    - Hydra redirects the user to Kratos for authentication.
    - Kratos presents a login page, where the user provides credentials.
    - After successful login, Kratos redirects the user back to Hydra.
    - Hydra requests consent from the user for accessing specific scopes.
    - Once the user consents, Hydra issues an authorization code, which can be exchanged for an access token.

2. **Access Control and Token Management**:
    - Ory Hydra handles token issuance, refresh tokens, and token introspection.
    - Ory Kratos ensures that only authenticated users can access the system.

---

## Detailed Architecture Breakdown

Here’s how the components interact:

1. **CockroachDB**:
    - Two databases are used:
        - `hydra`: for storing OAuth2 clients, tokens, and consent data.
        - `kratos`: for managing user identities, sessions, and authentication data.

2. **Ory Hydra**:
    - Public endpoint (`http://localhost:4444`): Handles OAuth2 authorization requests and token issuance.
    - Admin endpoint (`http://localhost:4445`): Manages clients, tokens, and introspection.

3. **Ory Kratos**:
    - Public endpoint (`http://localhost:4433`): Handles self-service login, registration, and identity flows.
    - Admin endpoint (`http://localhost:4434`): Manages identity schemas, configurations, and administrative tasks.

4. **UI Application**:
    - A simple web server (`http://localhost:3000`) handles user interaction for login and consent.

---

## Demo

### Step 1: Initialize Project Structure
```bash
mkdir ory-demo && cd ory-demo
touch docker-compose.yml hydra.yml kratos.yml identity.schema.json server.js
```

### Step 2: Setup CockroachDB
Ensure your `docker-compose.yml` has the following configuration for CockroachDB:

```yaml
services:
  cockroachdb:
    image: cockroachdb/cockroach
    command: start-single-node --insecure --listen-addr=0.0.0.0
    ports:
      - "26257:26257"
      - "8080:8080"
    volumes:
      - cockroach-data:/cockroach/cockroach-data
volumes:
  cockroach-data:
```

### Step 3: Initialize Databases
```bash
docker exec -it cockroachdb ./cockroach sql --insecure --execute "
CREATE DATABASE hydra;
CREATE DATABASE kratos;
CREATE USER hydra_user WITH PASSWORD 'hydra_pass';
CREATE USER kratos_user WITH PASSWORD 'kratos_pass';
GRANT ALL ON DATABASE hydra TO hydra_user;
GRANT ALL ON DATABASE kratos TO kratos_user;
"
```

### Step 4: Configure Ory Hydra
Create `hydra.yml`:

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

### Step 5: Configure Ory Kratos
Create `kratos.yml`:

```yaml
dsn: cockroach://kratos_user:kratos_pass@cockroachdb:26257/kratos?sslmode=disable
identity:
  default_schema_url: file:///etc/kratos/identity.schema.json
```

Create `identity.schema.json`:

```json
{
  "$id": "https://example.com/identity.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "traits": {
      "type": "object",
      "properties": {
        "email": { "type": "string", "format": "email" }
      }
    }
  }
}
```

### Step 6: Build and Run Services
```bash
docker-compose up -d
docker exec -it hydra hydra migrate sql --yes
docker exec -it kratos kratos migrate sql --yes
```

### Step 7: Test the Integration
1. Visit `http://localhost:4444/oauth2/auth` in your browser.
2. Authenticate using the UI and consent screens.
3. Hydra issues an access token upon successful authentication.

---
