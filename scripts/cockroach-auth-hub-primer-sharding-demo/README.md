# CockroachDB Auth Hub Primer (with Hands-On Sharding Demo)

This primer walks you through creating a simple Auth Hub schema in CockroachDB, seeding it with multi-tenant data, and running common queries. It also includes a 100k-row demo to show how automatic sharding works and when hash-sharded indexes help.

You’ll learn:

* CockroachDB’s automatic sharding (ranges) removes manual sharding from your workflow.
* When to add hash-sharded indexes to smooth out hotspots (e.g., login paths).
* How to model tenants, users, orgs, identities, sessions.
* Practical joins & hot lookups you’ll use in an Auth Hub.

-----

### 1\) Sharding in CockroachDB: The Basics

CRDB automatically shards tables and indexes into ~512 MiB ranges, replicates them, and re-balances them across nodes. You don’t manually split or place shards. However, some access patterns—monotonic keys, hot tenants/keys—can still create hot ranges. Hash-sharded indexes evenly spread logically adjacent keys across multiple ranges to avoid hotspots. Think of CRDB as slicing your data into pizza slices for you. If your toppings (keys) pile up on one slice, hash-sharding sprinkles them across slices.

-----

### 2\) Schema: Auth Hub Example

```sql
CREATE DATABASE IF NOT EXISTS auth_hub;
USE auth_hub;

-- Tenants
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY,
    name STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Users
CREATE TABLE users (
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    email STRING NOT NULL,
    display_name STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

-- Sharded index for hot email lookups (login path)
CREATE INDEX users_by_email
ON users (tenant_id, email)
USING HASH WITH BUCKET_COUNT = 32;

-- Orgs
CREATE TABLE orgs (
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    name STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id)
);

-- Org memberships
CREATE TABLE org_memberships (
    tenant_id UUID NOT NULL,
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role STRING NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, user_id),
    FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, user_id),
    FOREIGN KEY (tenant_id, org_id) REFERENCES orgs (tenant_id, org_id)
);

-- Identities (SSO)
CREATE TABLE identities (
    tenant_id UUID NOT NULL,
    identity_id UUID NOT NULL,
    user_id UUID NOT NULL,
    provider STRING NOT NULL,
    provider_uid STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, identity_id),
    FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, user_id)
);

-- Sharded index for SSO lookups (provider, provider_uid can be hot)
CREATE INDEX identities_by_provider_uid
ON identities (tenant_id, provider, provider_uid)
USING HASH WITH BUCKET_COUNT = 32;

-- Sessions
CREATE TABLE sessions (
    tenant_id UUID NOT NULL,
    session_id UUID NOT NULL,
    user_id UUID NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    ip STRING,
    user_agent STRING,
    PRIMARY KEY (tenant_id, session_id),
    FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, user_id)
);
```

-----

### 3\) Seed Data (10 tenants + child data)

Use the prepared seed file:

* 10 tenants
* 3 users per tenant
* 2 orgs per tenant
* memberships, identities
* 2 sessions per user

Download: `auth_hub_seed.sql`
Load:

```bash
cockroach sql --url "$CRDB_URL" -d auth_hub -f auth_hub_seed.sql 
```

(SEE BELOW FOR SQL)

-----

### 4\) Joins & Hot Lookups

#### A) Login by email (uses sharded `users_by_email`)

```sql
SELECT u.user_id, u.display_name, u.created_at
FROM users AS u
WHERE u.tenant_id = '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'
AND u.email = 'user1@tenant_01.com';
```

#### B) Resolve SSO identity (uses sharded `identities_by_provider_uid`)

```sql
SELECT i.user_id, u.email, u.display_name
FROM identities AS i
JOIN users AS u
ON u.tenant_id = i.tenant_id
AND u.user_id = i.user_id
WHERE i.tenant_id = '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'
AND i.provider = 'google'
AND i.provider_uid = 'google-uid-1';
```

#### C) List sessions for a user (PK join; no sharding needed)

```sql
SELECT s.session_id, s.issued_at, s.expires_at, s.ip, s.user_agent
FROM sessions AS s
WHERE s.tenant_id = '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'
AND s.user_id = '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66'
ORDER BY s.issued_at DESC;
```

#### D) List members of an org with roles (PK joins)

```sql
SELECT m.user_id, u.email, u.display_name, m.role
FROM org_memberships AS m
JOIN users AS u
ON u.tenant_id = m.tenant_id
AND u.user_id = m.user_id
WHERE m.tenant_id = '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'
AND m.org_id = 'e117451c-5b70-4782-bbf9-5491d8f88fa2'
ORDER BY u.email;
```

**Why this works well:**

* Automatic sharding (ranges) gives distribution by default.
* Hash-sharded indexes smooth out very hot access paths (email, `provider_uid`).
* PK joins are naturally efficient and distributed.

-----

### 5\) Optional — Hands-On Demo: 100k Rows (with vs. without Hash-Sharding)

This exercise shows a classic hotspot: monotonically increasing values under the same tenant. We’ll create two user tables:

* `users_noshard` with a non-sharded email index.
* `users_shard` with a hash-sharded email index.

We’ll insert 100,000 rows with sequential emails into both and compare range distribution.

**Tip:** Run these in a test database, so you can drop them easily.

1.  **Create demo tables**

    ```sql
    USE auth_hub;
    DROP TABLE IF EXISTS users_noshard;
    DROP TABLE IF EXISTS users_shard;

    -- No sharding on (tenant_id, email)
    CREATE TABLE users_noshard (
        tenant_id UUID NOT NULL,
        user_id UUID NOT NULL DEFAULT gen_random_uuid(),
        email STRING NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, user_id)
    );
    CREATE INDEX users_by_email_noshard ON users_noshard (tenant_id, email);

    -- Sharded on (tenant_id, email)
    CREATE TABLE users_shard (
        tenant_id UUID NOT NULL,
        user_id UUID NOT NULL DEFAULT gen_random_uuid(),
        email STRING NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, user_id)
    );
    CREATE INDEX users_by_email_shard
    ON users_shard (tenant_id, email)
    USING HASH WITH BUCKET_COUNT = 32;
    ```

2.  **Insert 100k sequential emails under the same tenant**
    We keep `tenant_id` constant to accentuate potential hotspotting by lexicographic ordering. Emails are monotonic (append-only pattern), which tends to focus writes on the end of the index keyspace.

    ```sql
    -- Fixed tenant for the demo
    WITH t AS (SELECT '00000000-0000-0000-0000-000000000000'::UUID AS tid)
    -- Insert into users_noshard (100k rows)
    INSERT INTO users_noshard (tenant_id, email)
    SELECT t.tid, 'demo+' || lpad(g::STRING, 6, '0') || '@example.com'
    FROM t, generate_series(1, 100000) AS g;

    -- Insert into users_shard (same 100k rows)
    WITH t AS (SELECT '00000000-0000-0000-0000-000000000000'::UUID AS tid)
    INSERT INTO users_shard (tenant_id, email)
    SELECT t.tid, 'demo+' || lpad(g::STRING, 6, '0') || '@example.com'
    FROM t, generate_series(1, 100000) AS g;
    ```

3.  **Compare range distribution**
    Count how many ranges CRDB created per index (more ranges and a more even split are generally better for spreading load):

    ```sql
    -- Non-sharded index range count
    SELECT count(*) AS ranges_noshard
    FROM [SHOW RANGES FROM INDEX users_noshard@users_by_email_noshard];

    -- Sharded index range count
    SELECT count(*) AS ranges_shard
    FROM [SHOW RANGES FROM INDEX users_shard@users_by_email_shard];
    ```

    Inspect range boundaries (you should see bucket prefixes in the sharded case, showing spread across many ranges):

    ```sql
    -- Non-sharded boundaries (will show a tight lexicographic progression under 1 tenant)
    SELECT * FROM [SHOW RANGES FROM INDEX users_noshard@users_by_email_noshard];

    -- Sharded boundaries (look for shard bucket key prefixes)
    SELECT * FROM [SHOW RANGES FROM INDEX users_shard@users_by_email_shard];
    ```

4.  **Optional: Check write skew under concurrent load**
    On a multi-node cluster, run concurrent inserts (another 100k) into both tables from two terminals and monitor range load in DB Console. The non-sharded index will tend to concentrate new writes at the tail, while the sharded index spreads writes across 32 buckets.

    You can also `EXPLAIN` both login queries (tenant + email) and confirm the sharded index is chosen.

    ```sql
    EXPLAIN SELECT * FROM users_noshard WHERE tenant_id='00000000-0000-0000-0000-000000000000' AND email='demo+050000@example.com';
    EXPLAIN SELECT * FROM users_shard WHERE tenant_id='00000000-0000-0000-0000-000000000000' AND email='demo+050000@example.com';
    ```

5.  **Cleanup (optional)**

    ```sql
    DROP TABLE IF EXISTS users_noshard;
    DROP TABLE IF EXISTS users_shard;
    ```

**What you should observe**

* Both tables benefit from CRDB’s automatic sharding (you’ll see multiple ranges either way).
* The sharded index typically yields more, smaller ranges and spreads keys across bucketed prefixes, reducing the chance that a single range becomes write-hot during sequential inserts.
* Under concurrency, the sharded version accepts more parallelism with fewer hot ranges.

-----

### 6\) Key Takeaways

* **Automatic sharding is built-in**: you don’t manually shard tables in CRDB.
* **Hash-sharded indexes are a targeted tool** for access paths that are (or could become) hot: login by email, SSO provider UID, counters, timestamps, or any monotonic/skewed key pattern.
* **Keep `tenant_id` leading in keys** and join predicates to preserve locality and isolation.
* **Use PK joins for predictable, efficient lookups**; shard secondary indexes to smooth hotspots.

-----

### 7\) Nice extras to try

* `SHOW RANGES FROM TABLE users;` and `… FROM INDEX users@users_by_email;`
* `ALTER INDEX … BUCKET_COUNT = 64;` (rebuild) for even more distribution on very hot paths.
* **Multi-region:** add `crdb_region` and `REGIONAL BY ROW` to colocate tenant data with users.

-----

#### Auth Hub seed data (10 tenants, 3 users each, 2 orgs/tenant, memberships, identities, 2 sessions/user)

* Generated on 2025-09-09 UTC
* Assumes schema from the blog post already exists in database `auth_hub`.

<!-- end list -->

```sql
BEGIN;
SET TRACING = off; -- for CockroachDB shells that support it
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'Tenant_01', '2025-09-09T12:00:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'Tenant_02', '2025-09-09T12:01:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'Tenant_03', '2025-09-09T12:02:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'Tenant_04', '2025-09-09T12:03:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'Tenant_05', '2025-09-09T12:04:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', 'Tenant_06', '2025-09-09T12:05:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'Tenant_07', '2025-09-09T12:06:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'Tenant_08', '2025-09-09T12:07:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', 'Tenant_09', '2025-09-09T12:08:00+00:00');
INSERT INTO tenants (tenant_id, name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'Tenant_10', '2025-09-09T12:09:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', 'user1@tenant_01.com', 'User1_Tenant_01', '2025-09-09T12:00:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', 'user2@tenant_01.com', 'User2_Tenant_01', '2025-09-09T12:01:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '4d4f2f36-2007-4daf-aa6a-5eb78a6a3219', 'user3@tenant_01.com', 'User3_Tenant_01', '2025-09-09T12:02:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'bf24114b-e0a6-4126-88cc-4555de4d8551', 'user1@tenant_02.com', 'User1_Tenant_02', '2025-09-09T12:01:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', 'user2@tenant_02.com', 'User2_Tenant_02', '2025-09-09T12:02:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '7d2ae37b-f4aa-48fe-bd56-4e6207eb7334', 'user3@tenant_02.com', 'User3_Tenant_02', '2025-09-09T12:03:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '771bf71b-8de0-442e-be1c-28459d9b5e12', 'user1@tenant_03.com', 'User1_Tenant_03', '2025-09-09T12:02:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', 'user2@tenant_03.com', 'User2_Tenant_03', '2025-09-09T12:03:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'f0260b7b-5c0f-4dba-8d2c-5f6491824aad', 'user3@tenant_03.com', 'User3_Tenant_03', '2025-09-09T12:04:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', 'user1@tenant_04.com', 'User1_Tenant_04', '2025-09-09T12:03:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', 'user2@tenant_04.com', 'User2_Tenant_04', '2025-09-09T12:04:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'b58dc9a7-e2a4-4699-8b78-aaeae9c0df40', 'user3@tenant_04.com', 'User3_Tenant_04', '2025-09-09T12:05:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'e211606b-c782-4b15-a4cc-fbf52e237e97', 'user1@tenant_05.com', 'User1_Tenant_05', '2025-09-09T12:04:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '3e34b793-6858-4653-9bb6-68525586bdf8', 'user2@tenant_05.com', 'User2_Tenant_05', '2025-09-09T12:05:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'b1ead732-03c7-46b5-a2da-b1c8ee62c811', 'user3@tenant_05.com', 'User3_Tenant_05', '2025-09-09T12:06:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', 'user1@tenant_06.com', 'User1_Tenant_06', '2025-09-09T12:05:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '11e71f94-babe-4964-a946-b32b12fb6f8c', 'user2@tenant_06.com', 'User2_Tenant_06', '2025-09-09T12:06:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '60f91804-0d20-4bd7-bfbc-e5a6621403c8', 'user3@tenant_06.com', 'User3_Tenant_06', '2025-09-09T12:07:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', 'user1@tenant_07.com', 'User1_Tenant_07', '2025-09-09T12:06:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', 'user2@tenant_07.com', 'User2_Tenant_07', '2025-09-09T12:07:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '573d5270-1088-40cd-9249-f35cc0b2d4de', 'user3@tenant_07.com', 'User3_Tenant_07', '2025-09-09T12:08:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', 'user1@tenant_08.com', 'User1_Tenant_08', '2025-09-09T12:07:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', 'user2@tenant_08.com', 'User2_Tenant_08', '2025-09-09T12:08:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'b17460fc-d0ab-41f5-aee2-a897363bdcd7', 'user3@tenant_08.com', 'User3_Tenant_08', '2025-09-09T12:09:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', 'user1@tenant_09.com', 'User1_Tenant_09', '2025-09-09T12:08:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', 'user2@tenant_09.com', 'User2_Tenant_09', '2025-09-09T12:09:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '160e376d-3c40-4ac0-8560-8b53a43f3447', 'user3@tenant_09.com', 'User3_Tenant_09', '2025-09-09T12:10:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '34768f97-87c0-4709-8505-c959a4d291c1', 'user1@tenant_10.com', 'User1_Tenant_10', '2025-09-09T12:09:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '35c5beca-09e5-4c69-8205-39b94aa32f6d', 'user2@tenant_10.com', 'User2_Tenant_10', '2025-09-09T12:10:00+00:00');
INSERT INTO users (tenant_id, user_id, email, display_name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'c14ad34f-ffbc-4f47-a417-023884ff8467', 'user3@tenant_10.com', 'User3_Tenant_10', '2025-09-09T12:11:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'e117451c-5b70-4782-bbf9-5491d8f88fa2', 'Tenant_01_Org1', '2025-09-09T12:01:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '05b96126-ef11-4fcd-8388-739653e209c2', 'Tenant_01_Org2', '2025-09-09T12:02:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '8f8dbf2f-1fb9-437d-9403-87bbb7c40447', 'Tenant_02_Org1', '2025-09-09T12:02:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '93899b0b-814b-4897-9d9c-542d24e5f30c', 'Tenant_02_Org2', '2025-09-09T12:03:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'f9c276fd-5903-4a99-b1f1-1e2fc901a35b', 'Tenant_03_Org1', '2025-09-09T12:03:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '691ec1e2-7a7b-4f84-ac61-fdeff12bfc01', 'Tenant_03_Org2', '2025-09-09T12:04:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '402899b4-5cae-4cc1-8a75-09632613fe47', 'Tenant_04_Org1', '2025-09-09T12:04:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'a66f110d-6f65-489f-9b52-e764ea6270e7', 'Tenant_04_Org2', '2025-09-09T12:05:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'e9369e6a-04c7-4190-94ce-c757a2553dc8', 'Tenant_05_Org1', '2025-09-09T12:05:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'f5b69d8f-45db-4861-b49d-2cf010e8500e', 'Tenant_05_Org2', '2025-09-09T12:06:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '6a54f9fb-fce8-40ee-b0e3-c9713e5a14e8', 'Tenant_06_Org1', '2025-09-09T12:06:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', 'd8ec3cff-f1b1-42d3-a26e-9744af71c871', 'Tenant_06_Org2', '2025-09-09T12:07:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'fb88eb9f-ed9a-4753-b643-38c3cf1cc008', 'Tenant_07_Org1', '2025-09-09T12:07:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '9357a7e6-d3ad-4a9d-bc0e-45643ae60f48', 'Tenant_07_Org2', '2025-09-09T12:08:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '92219055-6b10-4d1d-b678-2905ec908d47', 'Tenant_08_Org1', '2025-09-09T12:08:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'e0b634b9-91ef-49a2-99aa-cca824d4de03', 'Tenant_08_Org2', '2025-09-09T12:09:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '4642c9cd-10d0-4431-9611-c8f86044c7e7', 'Tenant_09_Org1', '2025-09-09T12:09:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '59574ad1-4c81-4c14-b90b-e7d74f6c263b', 'Tenant_09_Org2', '2025-09-09T12:10:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'db6088ae-b077-4e30-b8fb-9de8e51b1c94', 'Tenant_10_Org1', '2025-09-09T12:10:00+00:00');
INSERT INTO orgs (tenant_id, org_id, name, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'ba2f9f3c-dbeb-4a97-9aac-4f30ee8c9a91', 'Tenant_10_Org2', '2025-09-09T12:11:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'e117451c-5b70-4782-bbf9-5491d8f88fa2', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', 'owner', '2025-09-09T12:01:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'e117451c-5b70-4782-bbf9-5491d8f88fa2', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', 'member', '2025-09-09T12:02:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '05b96126-ef11-4fcd-8388-739653e209c2', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', 'owner', '2025-09-09T12:02:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '05b96126-ef11-4fcd-8388-739653e209c2', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', 'member', '2025-09-09T12:03:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '8f8dbf2f-1fb9-437d-9403-87bbb7c40447', 'bf24114b-e0a6-4126-88cc-4555de4d8551', 'owner', '2025-09-09T12:02:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '8f8dbf2f-1fb9-437d-9403-87bbb7c40447', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', 'member', '2025-09-09T12:03:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '93899b0b-814b-4897-9d9c-542d24e5f30c', 'bf24114b-e0a6-4126-88cc-4555de4d8551', 'owner', '2025-09-09T12:03:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '93899b0b-814b-4897-9d9c-542d24e5f30c', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', 'member', '2025-09-09T12:04:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'f9c276fd-5903-4a99-b1f1-1e2fc901a35b', '771bf71b-8de0-442e-be1c-28459d9b5e12', 'owner', '2025-09-09T12:03:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'f9c276fd-5903-4a99-b1f1-1e2fc901a35b', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', 'member', '2025-09-09T12:04:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '691ec1e2-7a7b-4f84-ac61-fdeff12bfc01', '771bf71b-8de0-442e-be1c-28459d9b5e12', 'owner', '2025-09-09T12:04:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '691ec1e2-7a7b-4f84-ac61-fdeff12bfc01', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', 'member', '2025-09-09T12:05:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '402899b4-5cae-4cc1-8a75-09632613fe47', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', 'owner', '2025-09-09T12:04:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '402899b4-5cae-4cc1-8a75-09632613fe47', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', 'member', '2025-09-09T12:05:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'a66f110d-6f65-489f-9b52-e764ea6270e7', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', 'owner', '2025-09-09T12:05:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'a66f110d-6f65-489f-9b52-e764ea6270e7', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', 'member', '2025-09-09T12:06:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'e9369e6a-04c7-4190-94ce-c757a2553dc8', 'e211606b-c782-4b15-a4cc-fbf52e237e97', 'owner', '2025-09-09T12:05:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'e9369e6a-04c7-4190-94ce-c757a2553dc8', '3e34b793-6858-4653-9bb6-68525586bdf8', 'member', '2025-09-09T12:06:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'f5b69d8f-45db-4861-b49d-2cf010e8500e', 'e211606b-c782-4b15-a4cc-fbf52e237e97', 'owner', '2025-09-09T12:06:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'f5b69d8f-45db-4861-b49d-2cf010e8500e', '3e34b793-6858-4653-9bb6-68525586bdf8', 'member', '2025-09-09T12:07:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '6a54f9fb-fce8-40ee-b0e3-c9713e5a14e8', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', 'owner', '2025-09-09T12:06:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '6a54f9fb-fce8-40ee-b0e3-c9713e5a14e8', '11e71f94-babe-4964-a946-b32b12fb6f8c', 'member', '2025-09-09T12:07:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', 'd8ec3cff-f1b1-42d3-a26e-9744af71c871', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', 'owner', '2025-09-09T12:07:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', 'd8ec3cff-f1b1-42d3-a26e-9744af71c871', '11e71f94-babe-4964-a946-b32b12fb6f8c', 'member', '2025-09-09T12:08:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'fb88eb9f-ed9a-4753-b643-38c3cf1cc008', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', 'owner', '2025-09-09T12:07:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'fb88eb9f-ed9a-4753-b643-38c3cf1cc008', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', 'member', '2025-09-09T12:08:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '9357a7e6-d3ad-4a9d-bc0e-45643ae60f48', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', 'owner', '2025-09-09T12:08:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '9357a7e6-d3ad-4a9d-bc0e-45643ae60f48', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', 'member', '2025-09-09T12:09:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '92219055-6b10-4d1d-b678-2905ec908d47', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', 'owner', '2025-09-09T12:08:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '92219055-6b10-4d1d-b678-2905ec908d47', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', 'member', '2025-09-09T12:09:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'e0b634b9-91ef-49a2-99aa-cca824d4de03', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', 'owner', '2025-09-09T12:09:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'e0b634b9-91ef-49a2-99aa-cca824d4de03', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', 'member', '2025-09-09T12:10:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '4642c9cd-10d0-4431-9611-c8f86044c7e7', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', 'owner', '2025-09-09T12:09:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '4642c9cd-10d0-4431-9611-c8f86044c7e7', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', 'member', '2025-09-09T12:10:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '59574ad1-4c81-4c14-b90b-e7d74f6c263b', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', 'owner', '2025-09-09T12:10:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '59574ad1-4c81-4c14-b90b-e7d74f6c263b', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', 'member', '2025-09-09T12:11:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'db6088ae-b077-4e30-b8fb-9de8e51b1c94', '34768f97-87c0-4709-8505-c959a4d291c1', 'owner', '2025-09-09T12:10:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'db6088ae-b077-4e30-b8fb-9de8e51b1c94', '35c5beca-09e5-4c69-8205-39b94aa32f6d', 'member', '2025-09-09T12:11:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'ba2f9f3c-dbeb-4a97-9aac-4f30ee8c9a91', '34768f97-87c0-4709-8505-c959a4d291c1', 'owner', '2025-09-09T12:11:00+00:00');
INSERT INTO org_memberships (tenant_id, org_id, user_id, role, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'ba2f9f3c-dbeb-4a97-9aac-4f30ee8c9a91', '35c5beca-09e5-4c69-8205-39b94aa32f6d', 'member', '2025-09-09T12:12:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '532403a6-2ecb-4c9b-902c-1238d9eec3c4', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', 'google', 'google-uid-1', '2025-09-09T12:00:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'd75f31f8-3403-4b1d-ae73-5a1c6d0788f2', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', 'okta', 'okta-uid-2', '2025-09-09T12:01:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'c5268338-ae31-4c28-b8bd-468cced52762', '4d4f2f36-2007-4daf-aa6a-5eb78a6a3219', 'google', 'google-uid-3', '2025-09-09T12:02:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'c02a117c-ed1b-4f06-b990-f6bd716eeac9', 'bf24114b-e0a6-4126-88cc-4555de4d8551', 'okta', 'okta-uid-4', '2025-09-09T12:01:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '480cf2f2-6264-411e-8c28-eb7208665a4c', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', 'google', 'google-uid-5', '2025-09-09T12:02:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'f9aa35d6-e41b-45d1-9ec3-d20708b65239', '7d2ae37b-f4aa-48fe-bd56-4e6207eb7334', 'okta', 'okta-uid-6', '2025-09-09T12:03:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '04b2169b-9fa9-4b31-95d1-f690a8521146', '771bf71b-8de0-442e-be1c-28459d9b5e12', 'google', 'google-uid-7', '2025-09-09T12:02:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'c534cd94-6310-4954-9d94-13033634dc11', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', 'okta', 'okta-uid-8', '2025-09-09T12:03:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '25759ea2-53fe-40de-ac8c-44240a830e36', 'f0260b7b-5c0f-4dba-8d2c-5f6491824aad', 'google', 'google-uid-9', '2025-09-09T12:04:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'abd9fa3f-9fa2-47ad-ba79-1619183ba474', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', 'okta', 'okta-uid-10', '2025-09-09T12:03:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'a081bf5e-6e17-4aa8-8f99-53f3ab216bc9', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', 'google', 'google-uid-11', '2025-09-09T12:04:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'c2dd9c3a-c93d-4ab7-b067-c738a1f8d093', 'b58dc9a7-e2a4-4699-8b78-aaeae9c0df40', 'okta', 'okta-uid-12', '2025-09-09T12:05:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'ca3c80ea-cd5e-418a-8d90-ac65f830e47c', 'e211606b-c782-4b15-a4cc-fbf52e237e97', 'google', 'google-uid-13', '2025-09-09T12:04:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'f1b7412d-7227-48ba-97b8-e87a172fcc0f', '3e34b793-6858-4653-9bb6-68525586bdf8', 'okta', 'okta-uid-14', '2025-09-09T12:05:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '0fb71321-7097-4ad1-9d5f-77b9f5725fb7', 'b1ead732-03c7-46b5-a2da-b1c8ee62c811', 'google', 'google-uid-15', '2025-09-09T12:06:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '0849047c-2e3e-490c-853f-2395ddb6be3c', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', 'okta', 'okta-uid-16', '2025-09-09T12:05:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '5b384e48-b2a3-4211-936d-8e42c01b098b', '11e71f94-babe-4964-a946-b32b12fb6f8c', 'google', 'google-uid-17', '2025-09-09T12:06:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '7852fea1-5749-4710-bb6c-d88f2387e818', '60f91804-0d20-4bd7-bfbc-e5a6621403c8', 'okta', 'okta-uid-18', '2025-09-09T12:07:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '116b6b50-3980-4b46-8ab5-ba282ed31bca', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', 'google', 'google-uid-19', '2025-09-09T12:06:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '525971e3-04b8-499d-8edd-605bea412dab', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', 'okta', 'okta-uid-20', '2025-09-09T12:07:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'c70e3385-9fe6-4393-9b15-0556df446d9b', '573d5270-1088-40cd-9249-f35cc0b2d4de', 'google', 'google-uid-21', '2025-09-09T12:08:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '7352978a-1850-40e9-8200-49219b586023', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', 'okta', 'okta-uid-22', '2025-09-09T12:07:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '8a4b69d6-4d03-4435-afc7-d3943fb8d939', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', 'google', 'google-uid-23', '2025-09-09T12:08:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '6deae265-e48f-47ce-bdc6-5fa67e9456ff', 'b17460fc-d0ab-41f5-aee2-a897363bdcd7', 'okta', 'okta-uid-24', '2025-09-09T12:09:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '62834958-b1a9-4832-a257-b9c5cc24c266', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', 'google', 'google-uid-25', '2025-09-09T12:08:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', 'b269bd5f-c9f7-412f-b1d7-1a99ae59eaaa', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', 'okta', 'okta-uid-26', '2025-09-09T12:09:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '041b0d16-050e-48d6-ab60-22503c0dfdf4', '160e376d-3c40-4ac0-8560-8b53a43f3447', 'google', 'google-uid-27', '2025-09-09T12:10:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'eb061247-26f5-4acf-9369-2da83f8499f5', '34768f97-87c0-4709-8505-c959a4d291c1', 'okta', 'okta-uid-28', '2025-09-09T12:09:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '1b2ed538-886e-4ff2-a6a1-9bb3cf41a951', '35c5beca-09e5-4c69-8205-39b94aa32f6d', 'google', 'google-uid-29', '2025-09-09T12:10:00+00:00');
INSERT INTO identities (tenant_id, identity_id, user_id, provider, provider_uid, created_at) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '8b1c88ec-2866-4608-abcb-e8f7b8709d0a', 'c14ad34f-ffbc-4f47-a417-023884ff8467', 'okta', 'okta-uid-30', '2025-09-09T12:11:00+00:00');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '1688f351-abc3-4334-9e25-061bb6fdd6a9', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.164', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'd60dfdd3-436b-4d3e-9127-e30eab35eaf2', '5f4ca9d5-3c50-41c8-a3b8-70fa3211dc66', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.7', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '5bd8cc8d-9d99-4cb4-951d-f15960df994c', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.71', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', '20ffda6e-b88b-427e-95a4-78d0c0a6f9de', '2d6bee51-e70d-4cef-b8ce-8bd0319d91c1', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.58', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'ee966521-7f48-4854-9765-34f519fc44d9', '4d4f2f36-2007-4daf-aa6a-5eb78a6a3219', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.189', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('3bd512a9-4696-4f98-83c9-5bb5815bc0bd', 'c97cdec0-319f-4706-863e-4fa14abef5ce', '4d4f2f36-2007-4daf-aa6a-5eb78a6a3219', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.174', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '29a5104b-4c04-46ee-98c2-513ec17d57e6', 'bf24114b-e0a6-4126-88cc-4555de4d8551', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.229', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '593af03f-1746-44cd-ac6f-12937a8b5d03', 'bf24114b-e0a6-4126-88cc-4555de4d8551', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.23', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'fe5683fc-bbcf-44c5-869b-698f09d09ac9', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.109', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', '26110cfe-3305-4a23-a3bc-e5981b6c8e4c', 'fd7c8a45-3131-4337-8f3b-c259e9b32dbf', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.8', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'e522c8eb-4595-4ea4-99de-6117e99ad68b', '7d2ae37b-f4aa-48fe-bd56-4e6207eb7334', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.56', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('9e42b6c9-fad4-4d7d-b332-74078ee0aef8', 'b1554a7d-4396-4762-aec8-6905897af60a', '7d2ae37b-f4aa-48fe-bd56-4e6207eb7334', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.130', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '9236f643-a75f-43f5-889b-2ef8ab2362f2', '771bf71b-8de0-442e-be1c-28459d9b5e12', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.7', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '33a0faa6-5b27-4420-8433-d8c51bc72b68', '771bf71b-8de0-442e-be1c-28459d9b5e12', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.51', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'e2dba6d8-3661-416f-b8cf-7733fdf5d5f6', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.167', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', '14a8e23c-6348-42e8-9cb3-19cba09d0dac', '9d55593d-ff0c-4365-91a9-5e2c83abbed7', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.140', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'c19bcdd8-c1af-49d8-85c3-70ea58a302ce', 'f0260b7b-5c0f-4dba-8d2c-5f6491824aad', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.57', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('5de5f6f3-e890-4fca-bf13-3e64cb3b52a1', 'f725ec16-517f-4e12-88dd-f373557e1d18', 'f0260b7b-5c0f-4dba-8d2c-5f6491824aad', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.151', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', 'a2f2a29e-005b-4758-9303-f220971b6b9a', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.208', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '6c1344bf-ece9-4d55-828f-75204ad243dd', '0cb28e54-59c9-486f-aa3c-7d3650eb97a3', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.195', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '2865f783-43d8-494f-b9c3-c272029e2d9e', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.179', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '1fc764a6-aa19-4afe-8f73-7d60cb3524a8', 'aa90d7cb-45f6-4e2c-8ced-c95a81e3fa5e', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.88', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '9449675f-585a-4b15-afc7-6a23cf10f4ca', 'b58dc9a7-e2a4-4699-8b78-aaeae9c0df40', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.40', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('bb7602e7-a755-41f3-a72e-164bae3e3cab', '362d5445-1558-46c6-b08e-2c0899e7b27a', 'b58dc9a7-e2a4-4699-8b78-aaeae9c0df40', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.246', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '77b3074f-c7cf-4ec0-bf87-8c93df6ccc75', 'e211606b-c782-4b15-a4cc-fbf52e237e97', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.27', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '03df3dee-7077-4f67-922c-ce7143c981d1', 'e211606b-c782-4b15-a4cc-fbf52e237e97', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.98', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '844e58d7-1eee-42a7-b7a9-d56398016572', '3e34b793-6858-4653-9bb6-68525586bdf8', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.92', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '0d7468b7-0824-48f8-aa0c-50dd3f1f365e', '3e34b793-6858-4653-9bb6-68525586bdf8', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.155', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', 'ddef0296-7938-4b67-a833-aa926b5ee00a', 'b1ead732-03c7-46b5-a2da-b1c8ee62c811', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.207', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('80fc6a55-c845-4610-8bcd-304995291bff', '3390c8d3-8711-4d30-b255-919e7209a14e', 'b1ead732-03c7-46b5-a2da-b1c8ee62c811', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.187', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', 'f9ebbe61-79eb-4b17-97ee-3e9f7e5d029e', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.138', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '6878b020-fc9c-4358-9041-2990f8eedf84', '4d9053c2-0a06-4ced-a56d-6d3d469f8554', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.250', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '7836a214-16a0-4908-ae94-5d15ebfae04e', '11e71f94-babe-4964-a946-b32b12fb6f8c', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.21', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '909de526-80c2-4331-92d5-62c09ff677a8', '11e71f94-babe-4964-a946-b32b12fb6f8c', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.76', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '34509f39-d112-4970-87db-13455d81f7dd', '60f91804-0d20-4bd7-bfbc-e5a6621403c8', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.159', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('89bf2831-7b20-454c-acb4-8d4bc483d058', '11260a65-2247-4d67-9635-f88841936658', '60f91804-0d20-4bd7-bfbc-e5a6621403c8', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.148', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'a7078e6b-e19f-497a-8ef4-9c8010824a88', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.181', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '9ebb8ec7-cf38-440d-9491-fdefa30a3541', 'ba0d7191-d636-4b6e-82e6-3a4b85dc4470', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.12', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '76cc6442-08e7-4ce3-a269-771162eaee8d', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.59', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'ad2d41e8-565f-4419-924b-06c9ae1311d7', '3e19cc15-1d51-45ab-855d-e1930f7d85bb', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.253', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', 'd514f769-fee7-4be2-98e2-1918cd307e80', '573d5270-1088-40cd-9249-f35cc0b2d4de', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.219', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('b6fa66b9-524f-462e-836c-d23effe7cc56', '972e0fd6-3252-48aa-a640-d542f561796c', '573d5270-1088-40cd-9249-f35cc0b2d4de', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.222', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'b592e6a1-8c4f-4627-ac2f-fc20b7e3fdca', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.98', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '593ad50b-087e-4ac9-9d40-cb31b85fcb41', '1403087c-ae10-4ffa-b9f7-4ed257b4f937', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.117', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '762e7a58-af20-4961-a63f-b64ecef007c9', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.214', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '57b348fe-a6e2-4e52-a35b-81af754e2771', '08a659d5-f9d8-4e41-9db2-c152c2efca7c', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.42', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', '6dc92c93-ca3d-44e1-9e0a-09000ce21b79', 'b17460fc-d0ab-41f5-aee2-a897363bdcd7', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.91', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('7018dc72-d59b-49a4-a059-0b3b5fa32c09', 'dd621b1d-c349-4b7f-a336-901a183ca95c', 'b17460fc-d0ab-41f5-aee2-a897363bdcd7', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.172', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '8bc94ad2-d837-42a7-92c0-d749b58c39db', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.180', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', 'e40e72e0-4426-46a6-854a-fd7965b42070', '23059ee8-9156-47e1-adfb-f3a1c5e54de1', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.166', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', 'e140a2ed-c48c-49e5-98ab-ba8ea39bbf5d', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.156', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '1276bd35-42a6-409b-acb1-d5d05da91307', '985feae1-61f6-4bf3-851b-1f86d80a6ce5', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.44', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', 'f02c5b26-a6a2-443e-a5fb-dad0a21f1649', '160e376d-3c40-4ac0-8560-8b53a43f3447', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.187', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('d7c00098-33ff-4277-8e3d-21f2436d02bf', '973b80b2-7fd8-4d0c-b665-91a8ca0245cc', '160e376d-3c40-4ac0-8560-8b53a43f3447', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.42', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'c0f4af97-639a-49f7-a511-7ad7c764d29c', '34768f97-87c0-4709-8505-c959a4d291c1', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.98', 'Safari/17');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'd20b9be2-f3c4-4cdb-8726-4e3f9eb587dc', '34768f97-87c0-4709-8505-c959a4d291c1', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.254', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'edee986e-4ac4-4327-93fc-06e50828a859', '35c5beca-09e5-4c69-8205-39b94aa32f6d', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.177', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', 'c99ecc8f-798b-418c-ae41-a823a0fcca96', '35c5beca-09e5-4c69-8205-39b94aa32f6d', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.57', 'Firefox/128');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '64d90ddf-d810-4a9e-b98f-45148d1848eb', 'c14ad34f-ffbc-4f47-a417-023884ff8467', '2025-09-09T13:00:00+00:00', '2025-09-09T15:00:00+00:00', '203.0.113.84', 'Chrome/126');
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent) VALUES ('c5020792-5d15-4b64-87c1-cd01958d565b', '9c49649f-4db4-4221-807d-10471266635c', 'c14ad34f-ffbc-4f47-a417-023884ff8467', '2025-09-09T13:01:00+00:00', '2025-09-09T15:01:00+00:00', '203.0.113.59', 'Chrome/126');
COMMIT;
```

-----

## Appendix: Multi-Region Setup with REGIONAL BY ROW and Region Survival

### Why Multi-Region?

CockroachDB lets you colocate tenant data (users, orgs, sessions, identities in specific regions, so:

* Queries like login/session checks happen locally.
* Data is geo-replicated across regions for resilience.
* You can survive an entire region outage if configured properly.

### 1\. Verify Available Regions

Check your cluster’s regions before configuring:

```sql
SHOW REGIONS FROM CLUSTER;
```

Example output (your cluster):

```
region       | zones   | database_name | survival_goal | primary_region
-------------+---------+---------------+---------------+---------------
europewest1  | {b,c,d} | {}            | {}            | {}
us-east1     | {b,c,d} | {}            | {}            | {}
us-west1     | {a,b,c} | {}            | {}            | {}
```

### 2\. Configure the Database with These Regions

Make us-east1 the primary region, then add the others:

```sql
ALTER DATABASE auth_hub SET PRIMARY REGION "us-east1";
ALTER DATABASE auth_hub ADD REGION "us-west1";
ALTER DATABASE auth_hub ADD REGION "europe-west1";

-- Ensure availability if an entire region goes offline
ALTER DATABASE auth_hub SURVIVE REGION FAILURE;
```

### 3\. Set Locality

Apply `REGIONAL BY ROW` locality to each table:

```sql
ALTER TABLE tenants SET LOCALITY REGIONAL BY ROW;
ALTER TABLE users SET LOCALITY REGIONAL BY ROW;
ALTER TABLE orgs SET LOCALITY REGIONAL BY ROW;
ALTER TABLE org_memberships SET LOCALITY REGIONAL BY ROW;
ALTER TABLE identities SET LOCALITY REGIONAL BY ROW;
ALTER TABLE sessions SET LOCALITY REGIONAL BY ROW;
```

### 4\. Insert Multi-Region Data

Let’s create tenants and users across all three regions.

```sql
-- Tenants in each region
INSERT INTO tenants (tenant_id, name, crdb_region)
VALUES
('aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Acme East', 'us-east1'),
('bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Acme West', 'us-west1'),
('cccc3333-cccc-cccc-cccc-cccccccccccc', 'Acme Europe', 'europe-west1');
```

```sql
-- Users for Acme East
INSERT INTO users (tenant_id, user_id, email, display_name, crdb_region)
VALUES
('aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'lee@acme-east.com', 'Lee', 'us-east1'),
('aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'ava@acme-east.com', 'Ava', 'us-east1');
-- Users for Acme West
INSERT INTO users (tenant_id, user_id, email, display_name, crdb_region)
VALUES
('bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb', gen_random_uuid(), 'kai@acme-west.com', 'Kai', 'us-west1'),
('bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb', gen_random_uuid(), 'mia@acme-west.com', 'Mia', 'us-west1');
-- Users for Acme Europe
INSERT INTO users (tenant_id, user_id, email, display_name, crdb_region)
VALUES
('cccc3333-cccc-cccc-cccc-cccccccccccc', gen_random_uuid(), 'noah@acme-eu.com', 'Noah', 'europe-west1'),
('cccc3333-cccc-cccc-cccc-cccccccccccc', gen_random_uuid(), 'zoe@acme-eu.com', 'Zoe', 'europe-west1');
```

Add sessions for one tenant in each region:

```sql
-- Session in us-east1
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent, crdb_region)
VALUES (
'aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
gen_random_uuid(),
(SELECT user_id FROM users WHERE email='lee@acme-east.com'),
now(), now() + interval '2h',
'203.0.113.11', 'Chrome/126', 'us-east1'
);
-- Session in us-west1
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent, crdb_region)
VALUES (
'bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
gen_random_uuid(),
(SELECT user_id FROM users WHERE email='kai@acme-west.com'),
now(), now() + interval '2h',
'203.0.113.22', 'Safari/17', 'us-west1'
);
-- Session in europe-west1
INSERT INTO sessions (tenant_id, session_id, user_id, issued_at, expires_at, ip, user_agent, crdb_region)
VALUES (
'cccc3333-cccc-cccc-cccc-cccccccccccc',
gen_random_uuid(),
(SELECT user_id FROM users WHERE email='noah@acme-eu.com'),
now(), now() + interval '2h',
'203.0.113.33', 'Firefox/128', 'europe-west1'
);
```

### 5\. Query Local Data

When querying for EU users, CRDB serves results from europe-west1 replicas:

```sql
SELECT u.user_id, u.display_name
FROM users AS u
WHERE u.tenant_id = 'cccc3333-cccc-cccc-cccc-cccccccccccc'
AND u.email = 'noah@acme-eu.com';
```

## Best Practices

* Always check available regions with `SHOW REGIONS FROM CLUSTER`.
* Use 3+ regions if you need `SURVIVE REGION FAILURE`.
* Keep tenant + child rows in the same `crdb_region`.
* Default rows go to the DB’s primary region if not specified.
* Assign new tenants explicitly to the right region.

-----

## COMPLEX Queries for the Auth Hub

### 1\) Tenant health dashboard (rollups, filters)

```sql
WITH params AS (
SELECT '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'::UUID AS tenant_id
)
SELECT
   t. name AS tenant,
COUNT(DISTINCT u.user_id) AS users,
COUNT(DISTINCT s.session_id)
FILTER (WHERE s.issued_at >= now() - '24h'::INTERVAL)
AS sessions_24h,
round(
   1.0 * COUNT(s.session_id)
FILTER (WHERE s.issued_at >= now() - '24h'::INTERVAL)
/ NULLIF(COUNT(DISTINCT u.user_id),0), 2
) AS sess_per_user_24h,
COUNT(*) FILTER (WHERE m.role = 'owner') AS owners
FROM params p
JOIN tenants t ON t.tenant_id = p.tenant_id
LEFT JOIN users u ON u.tenant_id = p.tenant_id
LEFT JOIN org_memberships m
ON m.tenant_id = u.tenant_id AND m.user_id = u.user_id
LEFT JOIN sessions s ON s.tenant_id = u.tenant_id AND s.user_id = u.user_id
GROUP BY t.name;
```

### 2\) Top users by recent activity (stable variants)

#### 2A) Single-tenant Top 5 (no window)

```sql
WITH params AS (
SELECT '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'::UUID AS tenant_id
)
SELECT
   u.tenant_id,
   u.user_id,
   u.email,
   u.display_name,
SUM(CASE WHEN s.issued_at >= now() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS sessions_7d
FROM users AS u
LEFT JOIN sessions AS s
ON s.tenant_id = u.tenant_id
AND s.user_id = u.user_id
WHERE u.tenant_id = (SELECT tenant_id FROM params)
GROUP BY u.tenant_id, u.user_id, u.email, u.display_name
ORDER BY sessions_7d DESC, u.email
LIMIT 5;
```

#### 2B) Multi-tenant Top 5 per tenant (LATERAL, no windows)

```sql
WITH tenants_to_rank AS (
SELECT DISTINCT tenant_id FROM users
)
SELECT
   t.tenant_id,
   x.user_id,
   x.email,
   x.display_name,
   x.sessions_7d
FROM tenants_to_rank AS t
JOIN LATERAL (
SELECT
   u.user_id,
   u.email,
   u.display_name,
SUM(CASE WHEN s.issued_at >= now() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS sessions_7d
FROM users AS u
LEFT JOIN sessions AS s
ON s.tenant_id = u.tenant_id
AND s.user_id = u.user_id
WHERE u.tenant_id = t.tenant_id
GROUP BY u.user_id, u.email, u.display_name
ORDER BY sessions_7d DESC, u.email
LIMIT 5
) AS x ON true
ORDER BY t.tenant_id, x.sessions_7d DESC, x.email;
```

### 3\) SSO coverage matrix (pivot with FILTER)

```sql
WITH params AS (
SELECT '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'::UUID AS tenant_id
)
SELECT
COUNT(DISTINCT i.user_id) FILTER (WHERE i.provider = 'google') AS google_users,
COUNT(DISTINCT i.user_id) FILTER (WHERE i.provider = 'okta') AS okta_users,
COUNT(DISTINCT u.user_id) AS total_users,
COUNT(DISTINCT u.user_id) - COUNT(DISTINCT i.user_id) AS users_without_sso
FROM params p
JOIN users u ON u.tenant_id = p.tenant_id
LEFT JOIN identities i
ON i.tenant_id = u.tenant_id AND i.user_id = u.user_id;
```

### 4\) Popular email domains per region

```sql
SELECT
   u.crdb_region,
regexp_replace(u.email, '.*@', '') AS domain,
COUNT(*) AS users
FROM users u
GROUP BY 1,2
ORDER BY u.crdb_region, users DESC, domain
LIMIT 100;
```

### 5\) Login time series (5-minute buckets)

```sql
WITH buckets AS (
SELECT generate_series(
date_trunc('minute', now() - '60 minutes'::INTERVAL),
date_trunc('minute', now()),
'5 minutes'::INTERVAL
) AS ts
)
SELECT
   b.ts AS bucket_start,
COUNT(s.session_id) AS logins
FROM buckets b
LEFT JOIN sessions s
ON s.issued_at >= b.ts
AND s.issued_at < b.ts + '5 minutes'::INTERVAL
GROUP BY b.ts
ORDER BY b.ts;
```

### 6\) Last login per user (window row\_number on sessions only)

```sql
WITH last_sess AS (
SELECT
   s.tenant_id, s.user_id, s.session_id, s.issued_at,
ROW_NUMBER() OVER (PARTITION BY s.tenant_id, s.user_id ORDER BY s.issued_at DESC) AS rn
FROM sessions s
)
SELECT u.tenant_id, u.user_id, u.email, u.display_name,
ls.session_id AS last_session_id, ls.issued_at AS last_login_at
FROM users u
LEFT JOIN last_sess ls
ON ls.tenant_id = u.tenant_id AND ls.user_id = u.user_id AND ls.rn = 1
ORDER BY last_login_at DESC NULLS LAST, email;
```

### 7\) Orphan/consistency sweeps (should be empty with proper FKs)

```sql
-- identities without a backing user
SELECT i.*
FROM identities i
LEFT JOIN users u
ON u.tenant_id = i.tenant_id AND u.user_id = i.user_id
WHERE u.user_id IS NULL
LIMIT 50;

-- memberships referencing missing orgs/users
SELECT m.*
FROM org_memberships m
LEFT JOIN orgs o ON o.tenant_id = m.tenant_id AND o.org_id = m.org_id
LEFT JOIN users u ON u.tenant_id = m.tenant_id AND u.user_id = m.user_id
WHERE o.org_id IS NULL OR u.user_id IS NULL
LIMIT 50;
```

### 8\) Region drift detector (compact)

```sql
SELECT 'users' AS table_name, COUNT(*) AS mismatches
FROM users u JOIN tenants t USING (tenant_id)
WHERE u.crdb_region <> t.crdb_region
UNION ALL
SELECT 'orgs', COUNT(*) FROM orgs o JOIN tenants t USING (tenant_id)
WHERE o.crdb_region <> t.crdb_region
UNION ALL
SELECT 'identities', COUNT(*) FROM identities i JOIN tenants t USING (tenant_id)
WHERE i.crdb_region <> t.crdb_region
UNION ALL
SELECT 'sessions', COUNT(*) FROM sessions s JOIN tenants t USING (tenant_id)
WHERE s.crdb_region <> t.crdb_region
UNION ALL
SELECT 'org_memberships', COUNT(*) FROM org_memberships m JOIN tenants t USING (tenant_id)
WHERE m.crdb_region <> t.crdb_region;
```

### 9\) Per-org roster as JSON (nested JSONB)

```sql
-- List orgs for the tenant, so you can pick a real org_id
SELECT org_id, name, created_at
FROM orgs
WHERE tenant_id = '3bd512a9-4696-4f98-83c9-5bb5815bc0bd'
ORDER BY created_at;

-- Then use an org_id from the query above
WITH params AS (
SELECT
'e117451c-5b70-4782-bbf9-5491d8f88fa2'::UUID AS org_id, -- << replace with a real one
'3bd512a9-4696-4f98-83c9-5bb5815bc0bd'::UUID AS tenant_id
)
SELECT jsonb_build_object(
'org', o.name,
'tenant_id', o.tenant_id::STRING,
'members',
COALESCE(
jsonb_agg(
jsonb_build_object(
'user_id', u.user_id::STRING,
'email', u.email,
'name', u.display_name,
'role', m.role
)
ORDER BY u.email
) FILTER (WHERE u.user_id IS NOT NULL),
'[]'::JSONB
)
) AS org_roster
FROM params p
JOIN orgs o
ON o.tenant_id = p.tenant_id AND o.org_id = p.org_id
LEFT JOIN org_memberships m
ON m.tenant_id = o.tenant_id AND m.org_id = o.org_id
LEFT JOIN users u
ON u.tenant_id = m.tenant_id AND u.user_id = m.user_id
GROUP BY o.tenant_id, o.org_id, o.name;
```

### 10\) Hot keys: most logins per email/tenant last 24h

```sql
SELECT
    s.tenant_id,
    u.email,
COUNT(*) AS logins_24h
FROM sessions s
JOIN users u
ON u.tenant_id = s.tenant_id AND u.user_id = s.user_id
WHERE s.issued_at >= now() - '24h'::INTERVAL
GROUP BY 1,2
ORDER BY logins_24h DESC, email
LIMIT 50;
```

### 11\) Show range distribution for sharded indexes (CRDB special)

```sql
-- Sharded SSO index
SELECT * FROM [SHOW RANGES FROM INDEX identities@identities_by_provider_uid];
-- Sharded email index
SELECT * FROM [SHOW RANGES FROM INDEX users@users_by_email];
```

### 12\) Who would be affected by a tenant region migration? (dry-run counts)

```sql
WITH params AS (
SELECT 'cccc3333-cccc-cccc-cccc-cccccccccccc'::UUID AS tenant_id,
'europe-west1'::crdb_internal_region AS to_region
)
SELECT
(SELECT COUNT(*) FROM users WHERE tenant_id = (SELECT tenant_id FROM params)) AS users_rows,
(SELECT COUNT(*) FROM orgs WHERE tenant_id = (SELECT tenant_id FROM params)) AS org_rows,
(SELECT COUNT(*) FROM identities WHERE tenant_id = (SELECT tenant_id FROM params)) AS identity_rows,
(SELECT COUNT(*) FROM sessions WHERE tenant_id = (SELECT tenant_id FROM params)) AS session_rows,
(SELECT COUNT(*) FROM org_memberships WHERE tenant_id = (SELECT tenant_id FROM params)) AS membership_rows;
```

### 13\) Safe tenant region move (one stmt per table; use inside a txn)

```sql
BEGIN;
-- UPDATE tenants SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
UPDATE users SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
UPDATE orgs SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
UPDATE identities SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
UPDATE sessions SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
UPDATE org_memberships SET crdb_region = 'europe-west1' WHERE tenant_id = '...';
COMMIT;
```

### 14\) “Owner” coverage per tenant and region

```sql
SELECT
    t.tenant_id,
COALESCE(u.crdb_region, t.crdb_region) AS region,
COUNT(DISTINCT u.user_id) AS users,
COUNT(DISTINCT u.user_id) FILTER (WHERE m.role='owner') AS owners
FROM tenants t
LEFT JOIN users u ON u.tenant_id = t.tenant_id
LEFT JOIN org_memberships m ON m.tenant_id = u.tenant_id AND m.user_id = u.user_id
GROUP BY t.tenant_id, region
ORDER BY t.tenant_id, region;
```

### Consistency check queries to ensure that all child rows (users, orgs, sessions, identities, memberships) have the same `crdb_region` as their parent tenant.

Here are some useful SQL snippets for your Auth Hub schema:

#### 1\. Users vs Tenants

```sql
SELECT u.tenant_id, COUNT(*) AS mismatches
FROM users u
JOIN tenants t
ON u.tenant_id = t.tenant_id
WHERE u.crdb_region <> t.crdb_region
GROUP BY u.tenant_id
HAVING COUNT(*) > 0;
```

Returns tenants that have at least one user row in a different region.

#### 2\. Orgs vs Tenants

```sql
SELECT o.tenant_id, COUNT(*) AS mismatches
FROM orgs o
JOIN tenants t
ON o.tenant_id = t.tenant_id
WHERE o.crdb_region <> t.crdb_region
GROUP BY o.tenant_id
HAVING COUNT(*) > 0;
```

#### 3\. Sessions vs Tenants

```sql
SELECT s.tenant_id, COUNT(*) AS mismatches
FROM sessions s
JOIN tenants t
ON s.tenant_id = t.tenant_id
WHERE s.crdb_region <> t.crdb_region
GROUP BY s.tenant_id
HAVING COUNT(*) > 0;
```

#### 4\. Identities vs Tenants

```sql
SELECT i.tenant_id, COUNT(*) AS mismatches
FROM identities i
JOIN tenants t
ON i.tenant_id = t.tenant_id
WHERE i.crdb_region <> t.crdb_region
GROUP BY i.tenant_id
HAVING COUNT(*) > 0;
```

#### 5\. Org Memberships vs Tenants

```sql
SELECT m.tenant_id, COUNT(*) AS mismatches
FROM org_memberships m
JOIN tenants t
ON m.tenant_id = t.tenant_id
WHERE m.crdb_region <> t.crdb_region
GROUP BY m.tenant_id
HAVING COUNT(*) > 0;
```

#### 6\. Global Check (all tables at once)

If you want to run one combined query across all child tables:

```sql
WITH mismatches AS (
SELECT 'users' AS table_name, u.tenant_id, COUNT(*) AS bad
FROM users u
JOIN tenants t ON u.tenant_id = t.tenant_id
WHERE u.crdb_region <> t.crdb_region
GROUP BY u.tenant_id
UNION ALL
SELECT 'orgs', o.tenant_id, COUNT(*)
FROM orgs o
JOIN tenants t ON o.tenant_id = t.tenant_id
WHERE o.crdb_region <> t.crdb_region
GROUP BY o.tenant_id
UNION ALL
SELECT 'sessions', s.tenant_id, COUNT(*)
FROM sessions s
JOIN tenants t ON s.tenant_id = t.tenant_id
WHERE s.crdb_region <> t.crdb_region
GROUP BY s.tenant_id
UNION ALL
SELECT 'identities', i.tenant_id, COUNT(*)
FROM identities i
JOIN tenants t ON i.tenant_id = t.tenant_id
WHERE i.crdb_region <> t.crdb_region
GROUP BY i.tenant_id
UNION ALL
SELECT 'org_memberships', m.tenant_id, COUNT(*)
FROM org_memberships m
JOIN tenants t ON m.tenant_id = t.tenant_id
WHERE m.crdb_region <> t.crdb_region
GROUP BY m.tenant_id
)
SELECT * FROM mismatches WHERE bad > 0;
```

### (Optional) Find & fix existing mismatches first

```sql
-- See where child rows don't match their tenant's crdb_region:
WITH mismatches AS (
SELECT 'users' AS tbl, u.tenant_id, COUNT(*) AS n
FROM users u JOIN tenants t USING (tenant_id)
WHERE u.crdb_region <> t.crdb_region GROUP BY 1,2
UNION ALL
SELECT 'orgs', o.tenant_id, COUNT(*) FROM orgs o JOIN tenants t USING (tenant_id)
WHERE o.crdb_region <> t.crdb_region GROUP BY 1,2
UNION ALL
SELECT 'identities', i.tenant_id, COUNT(*) FROM identities i JOIN tenants t USING (tenant_id)
WHERE i.crdb_region <> t.crdb_region GROUP BY 1,2
UNION ALL
SELECT 'sessions', s.tenant_id, COUNT(*) FROM sessions s JOIN tenants t USING (tenant_id)
WHERE s.crdb_region <> t.crdb_region GROUP BY 1,2
UNION ALL
SELECT 'org_memberships', m.tenant_id, COUNT(*) FROM org_memberships m JOIN tenants t USING (tenant_id)
WHERE m.crdb_region <> t.crdb_region GROUP BY 1,2
)
SELECT * FROM mismatches WHERE n > 0;
```

If any rows are listed, fix them (set the child’s `crdb_region` to match the tenant’s) before proceeding, e.g.:

```sql
UPDATE users u
SET crdb_region = t.crdb_region
FROM tenants t
WHERE u.tenant_id = t.tenant_id
AND u.crdb_region <> t.crdb_region;
```

\-- Repeat similarly for `orgs`, `identities`, `sessions`, `org_memberships`

### 1\) Ensure tenants has a unique key on (`tenant_id`, `crdb_region`)

Foreign keys must point to a unique or primary key. Since `tenants` PK is just `tenant_id`, add a unique key that includes the region:

```sql
-- safe even if it already exists (use IF NOT EXISTS on newer CRDB versions)
CREATE UNIQUE INDEX tenants_tenant_region_uniq
ON tenants (tenant_id, crdb_region);
```

### 2\) Make sure every child table has `crdb_region` (and default)

Skip any column that already exists.

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS crdb_region crdb_internal_region NOT NULL DEFAULT default_to_database_primary_region();
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS crdb_region crdb_internal_region NOT NULL DEFAULT default_to_database_primary_region();
ALTER TABLE identities ADD COLUMN IF NOT EXISTS crdb_region crdb_internal_region NOT NULL DEFAULT default_to_database_primary_region();
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS crdb_region crdb_internal_region NOT NULL DEFAULT default_to_database_primary_region();
ALTER TABLE org_memberships ADD COLUMN IF NOT EXISTS crdb_region crdb_internal_region NOT NULL DEFAULT default_to_database_primary_region();
```

(If you use `REGIONAL BY ROW AS crdb_region`, keep that in place—these constraints complement locality.)

### 3\) Add composite FKs from children → `tenants(tenant_id, crdb_region)`

These enforce “child’s `tenant_id` and `crdb_region` must match an existing (`tenant_id`, `crdb_region`) in tenants.”

```sql
-- USERS must match TENANTS region
ALTER TABLE users
ADD CONSTRAINT fk_users_tenant_region
FOREIGN KEY (tenant_id, crdb_region)
REFERENCES tenants (tenant_id, crdb_region)
ON UPDATE CASCADE;

-- ORGS must match TENANTS region
ALTER TABLE orgs
ADD CONSTRAINT fk_orgs_tenant_region
FOREIGN KEY (tenant_id, crdb_region)
REFERENCES tenants (tenant_id, crdb_region)
ON UPDATE CASCADE;

-- IDENTITIES must match TENANTS region
ALTER TABLE identities
ADD CONSTRAINT fk_identities_tenant_region
FOREIGN KEY (tenant_id, crdb_region)
REFERENCES tenants (tenant_id, crdb_region)
ON UPDATE CASCADE;

-- SESSIONS must match TENANTS region
ALTER TABLE sessions
ADD CONSTRAINT fk_sessions_tenant_region
FOREIGN KEY (tenant_id, crdb_region)
REFERENCES tenants (tenant_id, crdb_region)
ON UPDATE CASCADE;

-- ORG_MEMBERSHIPS must match TENANTS region
ALTER TABLE org_memberships
ADD CONSTRAINT fk_memberships_tenant_region
FOREIGN KEY (tenant_id, crdb_region)
REFERENCES tenants (tenant_id, crdb_region)
ON UPDATE CASCADE;
```

That’s the minimal, robust enforcement.

-----

## (Optional, stricter) Also enforce region equality to the immediate parent

If you want extra belt-and-suspenders, add parent-level composite FKs that include `crdb_region`. These ensure the membership row matches the org’s region; identities/sessions match the user’s region, etc.
First, create unique indexes on the parent composite keys to satisfy FK requirements:

#### Parents

```sql
CREATE UNIQUE INDEX users_user_region_uniq ON users (tenant_id, user_id, crdb_region);
CREATE UNIQUE INDEX orgs_org_region_uniq ON orgs (tenant_id, org_id, crdb_region);
```

Then add FKs on children:

#### `identities` (child) must match `users` (parent) region

```sql
ALTER TABLE identities
ADD CONSTRAINT fk_identities_user_region
FOREIGN KEY (tenant_id, user_id, crdb_region)
REFERENCES users (tenant_id, user_id, crdb_region)
ON UPDATE CASCADE;
```

#### `sessions` (child) must match `users` (parent) region

```sql
ALTER TABLE sessions
ADD CONSTRAINT fk_sessions_user_region
FOREIGN KEY (tenant_id, user_id, crdb_region)
REFERENCES users (tenant_id, user_id, crdb_region)
ON UPDATE CASCADE;
```

#### `org_memberships` (child) must match `orgs` (parent) region

```sql
ALTER TABLE org_memberships
ADD CONSTRAINT fk_memberships_org_region
FOREIGN KEY (tenant_id, org_id, crdb_region)
REFERENCES orgs (tenant_id, org_id, crdb_region)
ON UPDATE CASCADE;
```

With these in place, a row can’t exist unless both the tenant and the immediate parent have the same `crdb_region`. If you ever move a tenant or parent to a different region, `ON UPDATE CASCADE` will carry the new region down to children.

-----

## Notes & tips

* **Order matters:** add the `tenants(tenant_id, crdb_region)` unique index before creating child FKs. Same for the optional user/org unique composites.
* **Existing data:** constraints will fail to add if any row violates them—use the mismatch fix step first.
* **Region changes:** changing a tenant’s or parent’s `crdb_region` will cascade to children if you used `ON UPDATE CASCADE`.
* **Performance:** the added unique indexes help FKs and are small (lean on existing PK prefixes).

---

## Acknowledgments

This content was created and generously shared by [Andrew Deally](mailto:drew@cockroachlabs.com).