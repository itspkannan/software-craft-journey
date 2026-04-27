# SQL vs NoSQL: When to Use Each

## 1. Concept Overview

**What this is about**: Choosing between relational databases (SQL) and non-relational databases (NoSQL) based on your requirements.

**Why it matters**: This is often the first and most consequential database decision. Wrong choice leads to:
- Fighting the database instead of using it
- Expensive migrations mid-project
- Performance problems that architecture can't solve

**Core insight**: It's not SQL vs NoSQL — it's **consistency vs availability** and **flexibility vs structure**.

---

## 2. The Real Trade-offs

### What SQL Gives You

| Capability | Benefit | Cost |
|------------|---------|------|
| ACID transactions | Data integrity guaranteed | Write scaling limited |
| Schema enforcement | Data quality, clear contracts | Schema migrations required |
| JOINs | Query flexibility | Performance at scale |
| Foreign keys | Referential integrity | Write overhead |
| Rich query language | Ad-hoc queries | Query optimization needed |

### What NoSQL Gives You

| Capability | Benefit | Cost |
|------------|---------|------|
| Horizontal scaling | Linear write scaling | Complexity, eventual consistency |
| Schema flexibility | Fast iteration | Data quality responsibility on app |
| Denormalized data | Fast reads | Data duplication, update anomalies |
| Partition tolerance | Availability during failures | Consistency trade-offs |
| Simple data model | Predictable performance | Limited query flexibility |

---

## 3. Decision Framework

### Use SQL When

**1. Transactions are critical**
```
Examples:
- Financial systems (payments, transfers)
- Inventory management (stock levels)
- Booking systems (reservations)
- Any "if this fails, rollback everything" scenario
```

**2. Data relationships are complex**
```
Examples:
- E-commerce (users → orders → items → inventory)
- Social networks (users → friends → posts → comments)
- ERP systems (multi-entity business logic)
```

**3. Query patterns are unpredictable**
```
Examples:
- Analytics dashboards
- Business intelligence
- Ad-hoc reporting
- Search across multiple dimensions
```

**4. Data integrity is paramount**
```
Examples:
- Healthcare records
- Legal/compliance data
- Financial audit trails
```

### Use NoSQL When

**1. Scale exceeds single-node limits**
```
Examples:
- Billions of rows with high write throughput
- Global distribution requirement
- 100K+ writes/second sustained
```

**2. Data model fits NoSQL patterns**
```
Examples:
- Time-series data (metrics, logs, events)
- Document storage (user profiles, product catalogs)
- Key-value cache (sessions, shopping carts)
- Wide-column (activity feeds, messaging)
```

**3. Availability trumps consistency**
```
Examples:
- Shopping cart (available > consistent)
- Social media feed (stale OK, down not OK)
- Gaming leaderboards (eventual consistency OK)
```

**4. Schema evolves rapidly**
```
Examples:
- Startup MVP (requirements unclear)
- User-generated content (variable structure)
- IoT data (heterogeneous devices)
```

---

## 4. NoSQL Categories

### Key-Value Stores

```
┌─────────────────────────────────┐
│  Key        │  Value            │
├─────────────┼───────────────────┤
│  user:123   │  {name: "Alice"}  │
│  session:x  │  {token: "..."}   │
└─────────────┴───────────────────┘
```

| Database | Best For | Latency | Scale |
|----------|----------|---------|-------|
| Redis | Cache, sessions, real-time | Sub-ms | Cluster mode |
| Memcached | Simple caching | Sub-ms | Client-side sharding |
| DynamoDB | Serverless, managed | Single-digit ms | Unlimited |

**Use when**: Simple lookups by key, caching, session storage

### Document Stores

```json
{
  "_id": "user_123",
  "name": "Alice",
  "orders": [
    {"id": "o1", "total": 99.99},
    {"id": "o2", "total": 149.99}
  ]
}
```

| Database | Best For | Consistency | Query Power |
|----------|----------|-------------|-------------|
| MongoDB | General purpose | Tunable | Rich (aggregation) |
| Couchbase | Mobile sync, caching | Tunable | N1QL (SQL-like) |
| DocumentDB | AWS-managed Mongo | Strong | Mongo-compatible |

**Use when**: Nested data, variable schema, document-centric access

### Wide-Column Stores

```
Row Key    │ Column Family: profile      │ Column Family: activity
───────────┼─────────────────────────────┼──────────────────────────
user_123   │ name:Alice, email:a@b.com   │ login:ts1, click:ts2
user_456   │ name:Bob                    │ login:ts3
```

| Database | Best For | Consistency | Write Scale |
|----------|----------|-------------|-------------|
| Cassandra | Time-series, messaging | Tunable | Linear |
| ScyllaDB | Cassandra workloads | Tunable | Better latency |
| HBase | Hadoop ecosystem | Strong | Moderate |
| Bigtable | Google Cloud, analytics | Strong | Massive |

**Use when**: Write-heavy, time-series, wide rows, known query patterns

### Graph Databases

```
(Alice)-[:FRIENDS]->(Bob)-[:PURCHASED]->(Product)
```

| Database | Best For | Query Language |
|----------|----------|----------------|
| Neo4j | General graph | Cypher |
| Neptune | AWS-managed | Gremlin, SPARQL |
| DGraph | Distributed graph | GraphQL |

**Use when**: Relationship traversal, social networks, recommendations

---

## 5. Consistency Models Compared

| Model | Guarantee | Example | Use When |
|-------|-----------|---------|----------|
| **Strong** | Read sees latest write | PostgreSQL, Spanner | Financial, inventory |
| **Eventual** | Reads converge over time | Cassandra, DynamoDB (default) | Social, analytics |
| **Causal** | Preserves cause-effect order | MongoDB (sessions) | Collaborative apps |
| **Read-your-writes** | You see your own writes | DynamoDB (strongly consistent read) | User-facing updates |

### CAP Theorem in Practice

```
                    Consistency
                        △
                       /  \
                      /    \
                     /      \
                    /   CA   \      ← Traditional RDBMS
                   /          \        (single node)
                  /            \
                 /______________\
                CP              AP
         (Spanner, CockroachDB)  (Cassandra, DynamoDB)
              ↑                      ↑
        Consistency over          Availability over
        Availability              Consistency
```

**Reality**: It's not binary. Most NoSQL databases offer tunable consistency:
- DynamoDB: Eventually consistent (default) or strongly consistent reads
- Cassandra: Tunable via quorum (ONE, QUORUM, ALL)
- MongoDB: Write concern and read concern settings

---

## 6. Scaling Comparison

### SQL Scaling

```
Vertical Scaling          Read Replicas              Sharding
      │                        │                        │
      ▼                        ▼                        ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│ Bigger Box  │         │   Primary   │         │  Shard 0    │
│ (limited)   │         │      │      │         │  Shard 1    │
└─────────────┘         │   Replica   │         │  Shard N    │
                        │   Replica   │         └─────────────┘
                        └─────────────┘
                        (read scaling)          (write scaling)
```

**SQL scaling limits**:
- Vertical: Hardware ceiling (~$100K/month for largest instances)
- Read replicas: Helps reads, not writes
- Sharding: Requires Vitess/Citus, complex operations

### NoSQL Scaling

```
┌─────────────────────────────────────────────────────────┐
│                    Consistent Hashing                    │
│                                                          │
│    Node A        Node B        Node C        Node D     │
│   ┌─────┐       ┌─────┐       ┌─────┐       ┌─────┐    │
│   │ 0-90│       │91-180│      │181-270│     │271-360│  │
│   └─────┘       └─────┘       └─────┘       └─────┘    │
│                                                          │
│   Add Node E → Only keys near E's position move         │
└─────────────────────────────────────────────────────────┘
```

**NoSQL scaling advantages**:
- Linear write scaling (add nodes = add throughput)
- Automatic rebalancing (consistent hashing)
- No single point of failure (leaderless)

---

## 7. Real-World Hybrid Architectures

Most production systems use **both SQL and NoSQL**:

### Example: E-commerce Platform

```
┌─────────────────────────────────────────────────────────┐
│                      Application                         │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  PostgreSQL   │ │    Redis      │ │  Cassandra    │
│               │ │               │ │               │
│ • Orders      │ │ • Sessions    │ │ • Activity    │
│ • Inventory   │ │ • Cart        │ │ • Events      │
│ • Users       │ │ • Rate limits │ │ • Analytics   │
│               │ │ • Cache       │ │               │
│ (ACID needed) │ │ (speed needed)│ │ (scale needed)│
└───────────────┘ └───────────────┘ └───────────────┘
```

### Example: Social Media Platform

| Data | Database | Reason |
|------|----------|--------|
| User accounts | PostgreSQL | ACID for auth, billing |
| User profiles | MongoDB | Flexible schema, nested data |
| Sessions | Redis | Speed, TTL |
| Timeline/Feed | Cassandra | Write-heavy, time-series |
| Social graph | Neo4j | Relationship queries |
| Search | Elasticsearch | Full-text, aggregations |

---

## 8. Migration Patterns

### SQL → NoSQL Migration

**When it makes sense**:
- Hit vertical scaling ceiling
- Specific tables with clear access patterns
- Can tolerate eventual consistency for those tables

**Pattern**: Strangler Fig
```
Phase 1: Dual-write to both databases
Phase 2: Read from NoSQL, write to both
Phase 3: Write only to NoSQL
Phase 4: Decommission SQL table
```

### NoSQL → SQL Migration

**When it makes sense**:
- Need transactions you didn't anticipate
- Query flexibility became critical
- Data relationships grew complex

**Pattern**: Event sourcing bridge
```
NoSQL ──events──▶ Kafka ──▶ SQL (materialized view)
```

---

## 9. Interview Answer — Authority Mode

**Question**: "When would you use NoSQL instead of SQL?"

**Answer**:

Use NoSQL when:
- **Write scale exceeds SQL limits** — need 100K+ writes/sec sustained, linear horizontal scaling
- **Data model fits NoSQL** — time-series, documents, key-value; known access patterns
- **Availability over consistency** — shopping cart, social feed where stale OK, down not OK
- **Schema flexibility** — rapid iteration, variable structure, user-generated content

Stay with SQL when:
- **ACID transactions required** — payments, inventory, bookings
- **Complex relationships** — JOINs across entities, referential integrity
- **Query flexibility** — ad-hoc reporting, unpredictable access patterns
- **Data integrity paramount** — healthcare, finance, compliance

**Production reality**: Most systems use both. SQL for core transactional data, NoSQL for specific scale/speed needs (cache, events, sessions).

**Trade-off**: NoSQL gives scale and availability at the cost of consistency and query flexibility. Choose based on which constraints you can live with.

---

## 10. FAQ

**Q: Can't I just use PostgreSQL with JSONB for document needs?**
Yes, for moderate scale. PostgreSQL JSONB is excellent. But it won't scale horizontally like MongoDB or DynamoDB. Use PostgreSQL JSONB when you need documents AND relational features together.

**Q: Is MongoDB ACID now?**
MongoDB 4.0+ supports multi-document ACID transactions. But they're slower than single-document operations and don't scale as well. If you need heavy transactions, SQL is still better.

**Q: What about NewSQL (CockroachDB, Spanner)?**
NewSQL offers SQL + horizontal scaling + strong consistency. Trade-off is latency (consensus overhead) and cost. Good for global consistency needs, not for latency-sensitive workloads.

**Q: How do I handle JOINs in NoSQL?**
You don't — you denormalize. Embed related data in documents, or do application-level joins. This is a fundamental model shift, not a workaround.

**Q: What's the biggest mistake teams make?**
Choosing NoSQL because "it's modern" without understanding the consistency trade-offs. Then discovering they need transactions and doing expensive migrations back to SQL.

---

## Key Terms

| Term | Definition |
|------|------------|
| ACID | Atomicity, Consistency, Isolation, Durability |
| BASE | Basically Available, Soft state, Eventually consistent |
| Denormalization | Duplicating data to avoid joins |
| Sharding | Horizontal partitioning across nodes |
| Quorum | Majority agreement for reads/writes |
| Tunable consistency | Adjusting consistency level per operation |
