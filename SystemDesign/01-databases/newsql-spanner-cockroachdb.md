# NewSQL: Spanner & CockroachDB

## 1. Concept Overview

**What NewSQL is**: Databases that provide the scalability of NoSQL with the ACID guarantees and SQL interface of traditional relational databases.

**Why NewSQL exists**: To solve the "impossible" — horizontal scaling with strong consistency.

**The problem it solves**:
- Traditional SQL: ACID but doesn't scale horizontally
- NoSQL: Scales but sacrifices consistency (eventual consistency)
- NewSQL: ACID + horizontal scaling + SQL

**Key players**:
| Database | Origin | Cloud |
|----------|--------|-------|
| Google Spanner | Google (2012) | Google Cloud |
| CockroachDB | Ex-Googlers (2015) | Any cloud, self-hosted |
| TiDB | PingCAP | Any cloud |
| YugabyteDB | Ex-Facebook (2016) | Any cloud |

---

## 2. Real-World Case Studies

### Google Spanner — Google's Global Database

**Problem**: Google needed a globally distributed database for AdWords, Play Store with:
- Strong consistency across continents
- SQL interface (engineers know SQL)
- Horizontal scaling

**Solution**: Built Spanner with TrueTime (atomic clocks + GPS)

**Scale**:
- Manages 2+ billion directories
- Serves millions of requests/second
- Spans data centers globally

**Key insight**: TrueTime provides globally synchronized timestamps, enabling distributed transactions without coordination overhead.

**Source**: Google Research Paper — "Spanner: Google's Globally-Distributed Database"

### CockroachDB — Surviving Anything

**Problem**: Companies need Spanner-like capabilities without Google's infrastructure.

**Users**:
- DoorDash: Multi-region for delivery reliability
- Netflix: Account management
- Bose: IoT device management

**Why CockroachDB**:
- PostgreSQL-compatible (easy migration)
- Runs anywhere (not cloud-locked)
- Survives region failures automatically

**Source**: CockroachDB case studies

---

## 3. Architecture Deep Dive

### Google Spanner Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Global Spanner                        │
│                                                          │
│  ┌─────────────────┐      ┌─────────────────┐          │
│  │   Zone US-East  │      │   Zone EU-West  │          │
│  │  ┌───────────┐  │      │  ┌───────────┐  │          │
│  │  │  Spanserver│  │      │  │  Spanserver│  │          │
│  │  │  (Leader)  │  │◀────▶│  │  (Replica) │  │          │
│  │  └───────────┘  │      │  └───────────┘  │          │
│  │  ┌───────────┐  │      │  ┌───────────┐  │          │
│  │  │  Spanserver│  │      │  │  Spanserver│  │          │
│  │  └───────────┘  │      │  └───────────┘  │          │
│  └─────────────────┘      └─────────────────┘          │
│                                                          │
│                    TrueTime API                          │
│              (Atomic clocks + GPS)                       │
│         Provides globally synchronized time              │
└─────────────────────────────────────────────────────────┘
```

**Key components**:
- **Spanserver**: Storage and serving unit
- **Paxos groups**: Consensus for replication
- **TrueTime**: Provides bounded clock uncertainty
- **Directory**: Unit of data placement

### CockroachDB Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CockroachDB Cluster                    │
│                                                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │   Node 1    │  │   Node 2    │  │   Node 3    │    │
│   │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │    │
│   │ │  SQL    │ │  │ │  SQL    │ │  │ │  SQL    │ │    │
│   │ │  Layer  │ │  │ │  Layer  │ │  │ │  Layer  │ │    │
│   │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │    │
│   │ ┌────▼────┐ │  │ ┌────▼────┐ │  │ ┌────▼────┐ │    │
│   │ │ Distrib │ │  │ │ Distrib │ │  │ │ Distrib │ │    │
│   │ │  KV     │ │  │ │  KV     │ │  │ │  KV     │ │    │
│   │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │    │
│   │ ┌────▼────┐ │  │ ┌────▼────┐ │  │ ┌────▼────┐ │    │
│   │ │ Storage │ │  │ │ Storage │ │  │ │ Storage │ │    │
│   │ │(RocksDB)│ │  │ │(Pebble) │ │  │ │(Pebble) │ │    │
│   │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │    │
│   └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                          │
│   Data split into Ranges (64MB default)                 │
│   Each Range replicated via Raft consensus              │
└─────────────────────────────────────────────────────────┘
```

**Key components**:
- **SQL Layer**: PostgreSQL-compatible parser and optimizer
- **Distributed KV**: Transaction coordination, range distribution
- **Storage**: Pebble (LSM-tree), stores key-value pairs
- **Raft**: Consensus protocol for each range

---

## 4. How Global Consistency Works

### The Problem: Clock Skew

```
Node A (US)           Node B (EU)
Time: 10:00:00.000    Time: 10:00:00.050  ← 50ms clock skew

Transaction T1 commits at Node A: 10:00:00.010
Transaction T2 commits at Node B: 10:00:00.020

Without coordination, T2 might not see T1's writes
even though T2 started "after" T1 in real time
```

### Spanner's Solution: TrueTime

```
TrueTime API returns: [earliest, latest]

Example: TT.now() = [10:00:00.000, 10:00:00.007]
                     └─────────┬─────────┘
                         7ms uncertainty

Commit wait: Transaction waits until TrueTime.now().earliest 
             is past the commit timestamp

Guarantees: If T1 commits before T2 starts,
            T2 will see T1's writes
```

**TrueTime infrastructure**:
- Atomic clocks in data centers
- GPS receivers
- Uncertainty typically <7ms

### CockroachDB's Solution: Hybrid Logical Clocks (HLC)

```
HLC = (physical_time, logical_counter)

Physical time: Wall clock (with some skew)
Logical counter: Increments when events need ordering

Causality preserved:
- If event A happens before B on same node: HLC(A) < HLC(B)
- If A sends message to B: HLC(B) > HLC(A)
```

**Clock skew handling**:
- Maximum clock offset configured (default 500ms)
- Transactions may retry if clock skew detected
- Read/write conflicts resolved with HLC comparison

---

## 5. Consistency and Transactions

### Serializable Isolation

Both Spanner and CockroachDB provide **serializable isolation** — the strongest level:

```
Serializable: Transactions appear to execute one at a time

Read Committed → Repeatable Read → Snapshot → Serializable
      ↑                                            ↑
   Most DBs                                    NewSQL
   default                                     default
```

### Distributed Transactions

```
Transaction: Transfer $100 from Account A (US) to Account B (EU)

┌─────────────────────────────────────────────────────────┐
│                  Coordinator Node                        │
└─────────────────────────┬───────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│  Range: Acct A  │              │  Range: Acct B  │
│  (US Region)    │              │  (EU Region)    │
│                 │              │                 │
│  1. Acquire     │              │  1. Acquire     │
│     write lock  │              │     write lock  │
│  2. Stage write │              │  2. Stage write │
│  3. Vote COMMIT │              │  3. Vote COMMIT │
└────────┬────────┘              └────────┬────────┘
         │                                │
         └────────────────┬───────────────┘
                          ▼
                    All voted COMMIT
                          │
                          ▼
              Coordinator: COMMIT
                          │
         ┌────────────────┼────────────────┐
         ▼                                 ▼
    Apply write                       Apply write
    Release lock                      Release lock
```

### Read Types

| Read Type | Consistency | Latency | Use Case |
|-----------|-------------|---------|----------|
| Strong read | Linearizable | Higher (cross-region) | Default, critical data |
| Stale read | Bounded staleness | Lower | Analytics, read-heavy |
| Read-only txn | Snapshot | Medium | Consistent multi-read |

---

## 6. Spanner vs CockroachDB Comparison

| Dimension | Google Spanner | CockroachDB |
|-----------|----------------|-------------|
| **Deployment** | Google Cloud only | Any cloud, on-prem |
| **SQL Compatibility** | GoogleSQL (custom) | PostgreSQL wire protocol |
| **Consistency** | External consistency (TrueTime) | Serializable (HLC) |
| **Time sync** | TrueTime (atomic clocks) | NTP + HLC |
| **Clock uncertainty** | <7ms | Configurable (default 500ms) |
| **Pricing** | Per node-hour + storage | Per vCPU or self-hosted |
| **Schema changes** | Online, non-blocking | Online, non-blocking |
| **Multi-region** | Native, automatic | Native, automatic |
| **Operational burden** | Fully managed | Self-managed or DBaaS |

### When to Choose Spanner

- Already on Google Cloud
- Need <7ms clock uncertainty for latency-sensitive global transactions
- Want fully managed, zero ops
- Can accept GoogleSQL (not standard PostgreSQL)

### When to Choose CockroachDB

- Multi-cloud or on-premises requirement
- Need PostgreSQL compatibility (easier migration)
- Want to avoid vendor lock-in
- Cost-sensitive (self-hosted option)

---

## 7. Performance Characteristics

### Latency Expectations

| Operation | Same Region | Cross-Region |
|-----------|-------------|--------------|
| Single-row read | 1-5ms | 50-200ms |
| Single-row write | 5-15ms | 100-300ms |
| Multi-row transaction | 10-50ms | 200-500ms |

**Why cross-region is slower**: Consensus requires round trips between regions.

### Throughput Scaling

```
Linear scaling with nodes:

3 nodes:  ~15,000 writes/sec
6 nodes:  ~30,000 writes/sec
9 nodes:  ~45,000 writes/sec

(Actual numbers depend on workload, hardware, network)
```

### Optimizing Performance

**1. Locality hints** (CockroachDB):
```sql
-- Pin data to specific regions
ALTER TABLE users CONFIGURE ZONE USING 
  constraints = '[+region=us-east]';

-- Keep related data together
ALTER TABLE orders CONFIGURE ZONE USING 
  lease_preferences = '[[+region=us-east]]';
```

**2. Follower reads** (both):
```sql
-- Read from nearest replica (may be slightly stale)
-- CockroachDB
SET CLUSTER SETTING kv.closed_timestamp.target_duration = '5s';
SELECT * FROM users AS OF SYSTEM TIME '-5s' WHERE id = 1;

-- Spanner
SELECT * FROM users WHERE id = 1 
WITH MAX_STALENESS = 15 SECONDS;
```

**3. Batch operations**:
```sql
-- Instead of single inserts
INSERT INTO events VALUES (...), (...), (...);
```

---

## 8. Data Modeling

### Primary Key Design

```sql
-- CockroachDB: UUID for even distribution
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    ...
);

-- Spanner: Avoid sequential keys (hot spots)
-- Use UUIDs or hash-prefixed keys
CREATE TABLE orders (
    order_id STRING(36) NOT NULL,  -- UUID
    user_id STRING(36) NOT NULL,
    ...
) PRIMARY KEY (order_id);
```

### Interleaved Tables (Spanner)

```sql
-- Parent table
CREATE TABLE users (
    user_id STRING(36) NOT NULL,
    name STRING(100),
) PRIMARY KEY (user_id);

-- Child table interleaved with parent
-- Stores child rows physically with parent
CREATE TABLE orders (
    user_id STRING(36) NOT NULL,
    order_id STRING(36) NOT NULL,
    total NUMERIC,
) PRIMARY KEY (user_id, order_id),
  INTERLEAVE IN PARENT users ON DELETE CASCADE;

-- Benefit: User + orders fetched in single read
-- (co-located on same node)
```

### Secondary Indexes

```sql
-- Both support secondary indexes
CREATE INDEX idx_orders_user ON orders(user_id);

-- CockroachDB: Storing columns (covering index)
CREATE INDEX idx_orders_user ON orders(user_id) 
  STORING (total, status);

-- Spanner: Interleaved indexes
CREATE INDEX idx_orders_by_user ON orders(user_id)
  INTERLEAVE IN users;
```

---

## 9. Operational Considerations

### Multi-Region Setup

**CockroachDB regions**:
```sql
-- Define regions
ALTER DATABASE mydb PRIMARY REGION "us-east1";
ALTER DATABASE mydb ADD REGION "eu-west1";
ALTER DATABASE mydb ADD REGION "ap-southeast1";

-- Table locality options
-- GLOBAL: Read from any region, write to all
ALTER TABLE config SET LOCALITY GLOBAL;

-- REGIONAL BY ROW: Each row pinned to a region
ALTER TABLE users SET LOCALITY REGIONAL BY ROW;
ALTER TABLE users ADD COLUMN region crdb_internal_region;
```

**Spanner configuration**:
```
Instance config: nam-eur-asia1 (3 continents)
- Read replicas: Nearest region
- Write quorum: Majority across regions
```

### Backup and Recovery

```sql
-- CockroachDB
BACKUP DATABASE mydb TO 's3://bucket/backup' 
  AS OF SYSTEM TIME '-10s';

RESTORE DATABASE mydb FROM 's3://bucket/backup';

-- Spanner: Automatic backups
-- Point-in-time recovery up to 7 days
gcloud spanner databases restore ...
```

### Monitoring

Key metrics:
| Metric | Warning | Critical |
|--------|---------|----------|
| P99 latency | >100ms | >500ms |
| Replication lag | >10s | >30s |
| Leaseholder imbalance | >20% | >50% |
| Clock offset (CRDB) | >250ms | >500ms |

---

## 10. Interview Answer — Authority Mode

**Question**: "When would you use NewSQL like Spanner or CockroachDB?"

**Answer**:

**Use NewSQL when you need**:
- **Global distribution with strong consistency** — transactions that span continents and must be ACID
- **SQL interface** — existing team knows SQL, easier than redesigning for NoSQL
- **Horizontal scaling** — beyond single-node MySQL/PostgreSQL limits
- **Automatic failover** — survive region failures without manual intervention

**Spanner vs CockroachDB**:
- **Spanner**: Best for Google Cloud, lowest clock skew (<7ms), fully managed
- **CockroachDB**: Multi-cloud/on-prem, PostgreSQL compatible, avoids vendor lock-in

**Trade-offs vs alternatives**:
- **vs MySQL/PostgreSQL**: Higher latency (consensus overhead), more expensive
- **vs Cassandra/DynamoDB**: Slower writes, but strong consistency
- **vs custom sharding**: Less operational burden, but less control

**When NOT to use**:
- Single region only — traditional SQL is simpler and faster
- Eventual consistency acceptable — NoSQL is cheaper and faster
- Latency-critical (<5ms writes) — consensus adds overhead

**Real-world proof**: Google runs Spanner for AdWords (money). DoorDash uses CockroachDB for multi-region delivery reliability.

---

## 11. FAQ

**Q: Is NewSQL replacing NoSQL?**
No. NewSQL is for workloads that need ACID + scale. NoSQL is still better for eventual consistency workloads with extreme write throughput (logs, metrics, events).

**Q: How does CockroachDB handle clock skew without atomic clocks?**
It uses Hybrid Logical Clocks (HLC) and configured max clock offset. Transactions may need to retry if uncertainty overlaps. Practically, NTP keeps skew under 100ms.

**Q: Can I migrate from PostgreSQL to CockroachDB?**
Mostly yes. CockroachDB is PostgreSQL wire-compatible. Some features differ (no triggers, limited stored procedures). Test thoroughly.

**Q: What's the cost compared to RDS?**
Higher. You're paying for global distribution and strong consistency. For single-region, RDS is cheaper. Multi-region with strong consistency, NewSQL can be cost-effective vs building it yourself.

**Q: How does Spanner achieve external consistency?**
TrueTime provides bounded uncertainty. Commits wait until the uncertainty interval passes, guaranteeing that if T1 commits before T2 starts, T2 sees T1's writes.

---

## Key Terms

| Term | Definition |
|------|------------|
| NewSQL | Databases combining SQL/ACID with horizontal scaling |
| TrueTime | Google's globally synchronized time API using atomic clocks |
| HLC | Hybrid Logical Clock — combines wall clock with logical counter |
| External consistency | Strongest guarantee — respects real-time ordering |
| Serializable | Transactions appear to execute one at a time |
| Raft | Consensus protocol used by CockroachDB |
| Paxos | Consensus protocol used by Spanner |
| Range | CockroachDB's unit of data distribution (64MB default) |
| Leaseholder | Node responsible for serving reads for a range |
