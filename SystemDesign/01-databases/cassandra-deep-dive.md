# Cassandra Deep Dive

## 1. Concept Overview

**What Cassandra is**: A distributed, wide-column NoSQL database designed for high availability and linear scalability.

**Why it exists**: Built by Facebook for inbox search (2008), designed to handle:
- Massive write throughput
- No single point of failure
- Geographic distribution
- Predictable latency at scale

**When to use Cassandra**:
- Write-heavy workloads (10:1 write:read or higher)
- Time-series data (logs, metrics, events, IoT)
- High availability requirements (always-on)
- Known query patterns (design table per query)

---

## 2. Real-World Case Studies

### Discord — Billions of Messages

**Problem**: Store billions of messages with fast writes and reads by channel.

**Solution**: Cassandra with channel_id as partition key, time-bucketed.

**Data model**:
```sql
CREATE TABLE messages (
    channel_id bigint,
    bucket int,          -- time bucket (e.g., day)
    message_id bigint,
    author_id bigint,
    content text,
    PRIMARY KEY ((channel_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);
```

**Result**: Sub-millisecond reads for recent messages.

**Later**: Migrated to ScyllaDB for better p99 latency (JVM GC issues).

**Source**: Discord Engineering Blog

### Netflix — Viewing History

**Problem**: Store viewing history for 200M+ users with fast writes.

**Why Cassandra**: 
- Each view is a write (millions/second)
- Reads are per-user (partition key = user_id)
- Availability critical (always show history)

**Scale**: 30+ clusters, 10K+ nodes

**Source**: Netflix Tech Blog

### Apple — 10 PB+ Deployment

**Scale**: One of the largest Cassandra deployments
- 75,000+ nodes
- 10+ petabytes
- Millions of operations/second

---

## 3. Architecture Deep Dive

### Data Distribution

```
                        Token Ring
                    ┌───────────────┐
                   ╱                 ╲
                  ╱    Token: 0      ╲
                 │    ┌─────────┐     │
                 │    │ Node A  │     │
         Token:  │    └─────────┘     │  Token:
          270   ─┤                    ├─  90
                 │    ┌─────────┐     │
                 │    │ Node D  │     │
                  ╲   └─────────┘    ╱
                   ╲                ╱
                    └───────────────┘
                        Token: 180
                      ┌─────────┐
                      │ Node C  │
                      └─────────┘

Partition Key → Murmur3 Hash → Token → Node
```

### Write Path

```
Client
   │
   ▼
Coordinator Node (any node)
   │
   ├──▶ Commit Log (append-only, durability)
   │
   ├──▶ Memtable (in-memory, sorted)
   │
   └──▶ Replicas (based on replication factor)
         │
         ▼ (when memtable full)
      SSTable (immutable, on disk)
```

### Read Path

```
Client
   │
   ▼
Coordinator Node
   │
   ├──▶ Memtable (check memory first)
   │
   ├──▶ Row Cache (if enabled)
   │
   ├──▶ Bloom Filter (probably not in SSTable?)
   │
   ├──▶ Partition Index (find SSTable offset)
   │
   └──▶ SSTable (read from disk)
         │
         ▼
      Merge results from multiple SSTables
```

### Compaction

```
Before Compaction:
┌──────────┐ ┌──────────┐ ┌──────────┐
│SSTable 1 │ │SSTable 2 │ │SSTable 3 │
│ key:A=1  │ │ key:A=2  │ │ key:A=3  │
│ key:B=1  │ │ key:C=1  │ │ key:B=2  │
└──────────┘ └──────────┘ └──────────┘

After Compaction:
┌────────────────────────────────────┐
│          New SSTable               │
│ key:A=3 (latest), key:B=2, key:C=1 │
└────────────────────────────────────┘
```

**Compaction strategies**:
| Strategy | Best For | How It Works |
|----------|----------|--------------|
| STCS | Write-heavy | Size-tiered, merge similar sizes |
| LCS | Read-heavy | Leveled, fixed size per level |
| TWCS | Time-series | Time-windowed, oldest expires |

---

## 4. Data Modeling

### Primary Key Structure

```sql
PRIMARY KEY ((partition_key), clustering_key1, clustering_key2)
              └─────┬─────┘   └──────────────┬──────────────┘
           Determines node          Determines sort order
           (distribution)           (within partition)
```

### Modeling Rules

**Rule 1**: One table per query pattern
```sql
-- Query: Get user's recent orders
CREATE TABLE orders_by_user (
    user_id uuid,
    order_time timestamp,
    order_id uuid,
    total decimal,
    PRIMARY KEY ((user_id), order_time)
) WITH CLUSTERING ORDER BY (order_time DESC);

-- Query: Get orders by status for admin
CREATE TABLE orders_by_status (
    status text,
    order_time timestamp,
    order_id uuid,
    user_id uuid,
    PRIMARY KEY ((status), order_time)
);
```

**Rule 2**: Denormalize aggressively
```sql
-- Don't JOIN, embed the data
CREATE TABLE user_activity (
    user_id uuid,
    activity_time timestamp,
    activity_type text,
    user_name text,      -- denormalized from users table
    user_email text,     -- denormalized
    details text,
    PRIMARY KEY ((user_id), activity_time)
);
```

**Rule 3**: Bound partition size
```sql
-- Bad: Unbounded partition
PRIMARY KEY ((sensor_id), reading_time)  -- grows forever

-- Good: Time-bucketed
PRIMARY KEY ((sensor_id, day), reading_time)  -- bounded per day
```

### Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Large partitions | Slow reads, GC pressure | Time bucketing |
| Hot partitions | Uneven load | Better partition key |
| ALLOW FILTERING | Full table scan | Proper data model |
| Secondary indexes | Performance issues | Materialized view or new table |

---

## 5. Consistency Model

### Tunable Consistency

| Level | Behavior | Use Case |
|-------|----------|----------|
| ONE | Single replica | Fast reads, stale OK |
| QUORUM | Majority (RF/2 + 1) | Balance |
| LOCAL_QUORUM | Majority in local DC | Multi-DC |
| ALL | All replicas | Strongest, slowest |

### Consistency Formula

```
Strong consistency when: R + W > RF

Example with RF=3:
- QUORUM read (2) + QUORUM write (2) = 4 > 3 ✓ Strong
- ONE read (1) + ONE write (1) = 2 < 3 ✗ Eventual
```

### Lightweight Transactions (LWT)

```sql
-- Compare-and-set (Paxos-based)
INSERT INTO users (user_id, email) 
VALUES (uuid(), 'new@email.com')
IF NOT EXISTS;

-- Conditional update
UPDATE inventory SET quantity = 5 
WHERE item_id = 123 
IF quantity = 10;
```

**Warning**: LWT is 4x slower than normal writes. Use sparingly.

---

## 6. Operations & Reliability

### Key Metrics to Monitor

| Metric | Warning | Critical |
|--------|---------|----------|
| Read latency p99 | >50ms | >200ms |
| Write latency p99 | >25ms | >100ms |
| Compaction pending | >10 | >50 |
| Heap usage | >70% | >85% |
| Dropped mutations | >0 | >100 |

### Common Operational Tasks

**Adding a node**:
```bash
# 1. Configure and start new node
# 2. Node bootstraps (streams data)
nodetool status  # verify UN (Up Normal)

# 3. Run cleanup on other nodes
nodetool cleanup
```

**Repair**:
```bash
# Run regularly to fix inconsistencies
nodetool repair -pr keyspace_name
```

**Snapshot/Backup**:
```bash
nodetool snapshot keyspace_name
# Copies SSTables to snapshots/ directory
```

### Failure Scenarios

| Failure | Impact | Recovery |
|---------|--------|----------|
| Single node down | Reads/writes continue (RF>1) | Restart or replace |
| Network partition | Split cluster | Hinted handoff when healed |
| Disk failure | Node data lost | Replace node, rebuild |
| DC failure | Local reads fail | Fail over to other DC |

---

## 7. Performance Tuning

### JVM Tuning

```yaml
# cassandra-env.sh
MAX_HEAP_SIZE="8G"           # Don't exceed 8GB (GC issues)
HEAP_NEWSIZE="2G"            # 1/4 of heap

# G1GC settings (recommended for 3.11+)
-XX:+UseG1GC
-XX:MaxGCPauseMillis=500
```

### cassandra.yaml Key Settings

```yaml
# Compaction throughput
compaction_throughput_mb_per_sec: 64

# Concurrent reads/writes
concurrent_reads: 32
concurrent_writes: 32

# Memtable size
memtable_heap_space_in_mb: 2048
```

### Query Optimization

```sql
-- Use token() for large partition scans
SELECT * FROM events 
WHERE token(partition_key) > token('start')
AND token(partition_key) <= token('end');

-- Avoid ALLOW FILTERING
-- Bad:
SELECT * FROM users WHERE email = 'x@y.com' ALLOW FILTERING;

-- Good: Create a table for that query
CREATE TABLE users_by_email (
    email text PRIMARY KEY,
    user_id uuid
);
```

---

## 8. Interview Answer — Authority Mode

**Question**: "When would you choose Cassandra over other databases?"

**Answer**:

Choose Cassandra when:
- **Write-heavy workloads** — append-only writes to commit log, no read-before-write
- **Time-series data** — log, event, IoT data with TWCS compaction for efficient TTL
- **High availability required** — no single point of failure, survives node/DC outages
- **Linear scalability needed** — double nodes = double throughput
- **Known query patterns** — can model tables per query, no ad-hoc queries needed

Avoid Cassandra when:
- **Need ad-hoc queries** — no JOINs, secondary indexes are limited
- **Strong consistency required everywhere** — LWT is slow
- **Small dataset** — operational overhead not worth it under 100GB
- **Need transactions** — no multi-partition ACID

**Real-world proof**: Discord (billions of messages), Netflix (viewing history), Apple (75K+ nodes). All write-heavy, time-series or event-driven workloads.

**Trade-off**: Cassandra trades query flexibility for write scalability. You must know your queries upfront and denormalize aggressively.

---

## 9. FAQ

**Q: How big should a partition be?**
Target: <100MB, <100K rows. Larger partitions cause GC pressure and slow reads.

**Q: When should I use LWT?**
Rarely. Only for uniqueness constraints or compare-and-set. Regular writes are 4x faster.

**Q: How do I handle time-series data?**
Use TWCS compaction, time-bucket your partition key, set TTL on data.

**Q: Cassandra vs ScyllaDB?**
ScyllaDB is a C++ rewrite of Cassandra. Same data model, better latency (no JVM GC). Consider for latency-sensitive workloads.

**Q: How many nodes do I need?**
Minimum: 3 (for RF=3). Production: Start with 6+ for headroom. Scale based on throughput/storage needs.

---

## 10. Key Terms

| Term | Definition |
|------|------------|
| SSTable | Sorted String Table — immutable on-disk data file |
| Memtable | In-memory write buffer, flushed to SSTable |
| Commit Log | Append-only durability log |
| Compaction | Merging SSTables, removing tombstones |
| Tombstone | Marker for deleted data (TTL before removal) |
| Gossip | Protocol for nodes to share cluster state |
| Hinted Handoff | Temporarily store writes for down nodes |
| Bloom Filter | Probabilistic filter to skip SSTable reads |
| Vnodes | Virtual nodes — multiple token ranges per node |
| RF | Replication Factor — copies of each partition |
