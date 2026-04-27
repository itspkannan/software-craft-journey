# MySQL at Scale

## 1. Concept Overview

**What it is**: Horizontal scaling of MySQL beyond single-node limits using sharding, replication, and specialized tooling.

**Why it matters**: MySQL is battle-tested for ACID transactions, but a single node hits limits around 10K-50K writes/sec depending on hardware. At web scale (billions of users), you must distribute data across multiple nodes.

**When to apply**:
- Write throughput exceeds single-node capacity
- Dataset exceeds single-node storage (multi-TB)
- Read replicas alone can't handle load

**Alternatives**:
- Vertical scaling (bigger hardware) — delays the problem, doesn't solve it
- NoSQL (Cassandra, DynamoDB) — trades ACID for linear scale
- NewSQL (Spanner, CockroachDB) — global consistency but higher latency and cost

**Historical context**: MySQL dominated web 1.0/2.0. When companies hit scale limits, they built custom sharding layers (Facebook, Twitter, Pinterest) rather than abandoning MySQL's relational model.

---

## 2. Real-World Case Study: Meta (Facebook)

**Problem**: Billions of users, relational schema (users, posts, friendships), MySQL hitting single-node write limits around 2010-2012.

**Scale context**:
- Billions of rows per table
- Millions of QPS across the fleet
- Strict latency requirements (<10ms p99)

**Solution chosen**:
1. **Horizontal sharding by `user_id`** — all data for a user lives on one shard
2. **Vitess** (later) / custom sharding proxy for connection pooling and query routing
3. **MyRocks storage engine** — LSM-tree based, 50% storage reduction vs InnoDB
4. **Read replicas** — 1 primary + N replicas per shard

**Why they rejected alternatives**:
- NoSQL: Would require rewriting the entire application layer
- NewSQL: Didn't exist at the time; now considered too expensive for their scale
- Single MySQL: Physically impossible at their data volume

**What happened at scale**:
- 10x: Sharding worked, but cross-shard queries became painful
- 100x: Connection pooling became critical (10K+ app servers)
- 1000x: MyRocks reduced storage costs by billions of dollars

**Source**: Meta Engineering Blog — "Scaling MySQL at Facebook", "MyRocks: A space- and write-optimized MySQL database"

---

## 3. Architecture Deep Dive

### Components

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  App Server │     │  App Server │     │  App Server │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │
           ┌───────▼───────┐
           │  Shard Proxy  │  (Vitess VTGate / ProxySQL)
           │  - Routing    │
           │  - Pooling    │
           └───────┬───────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│  Shard 0    │ │  Shard 1    │ │  Shard N    │
│  user_id    │ │  user_id    │ │  user_id    │
│  0-999999   │ │  1M-1.99M   │ │  ...        │
├─────────────┤ ├─────────────┤ ├─────────────┤
│ Primary     │ │ Primary     │ │ Primary     │
│ Replica x2  │ │ Replica x2  │ │ Replica x2  │
└─────────────┘ └─────────────┘ └─────────────┘
```

### Request Lifecycle

1. App server sends query with `user_id`
2. Shard proxy extracts shard key from query
3. Proxy routes to correct shard (hash(user_id) % num_shards)
4. If read: route to replica; if write: route to primary
5. Connection pooling reuses connections (critical at scale)
6. Result returned through proxy to app

### Key Interfaces

| Component | Interface | Purpose |
|-----------|-----------|---------|
| App → Proxy | MySQL protocol | Transparent to application |
| Proxy → Shard | MySQL protocol | Standard replication |
| Shard → Replica | Binlog replication | Async or semi-sync |

---

## 4. Scenario-Based Design

**Scenario**: Design a sharded MySQL system for a social network with 500M users.

### Requirements

**Functional**:
- User profiles (read-heavy)
- Posts (write-heavy, 10 posts/user/day average)
- Friend relationships (graph queries)

**Non-functional**:
- p99 read latency < 10ms
- p99 write latency < 50ms
- 99.99% availability
- Strong consistency for writes

### Capacity Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| DAU | 500M × 20% | 100M |
| Read QPS | 100M × 50 reads/day / 86400 | ~58K QPS |
| Write QPS | 100M × 10 writes/day / 86400 | ~12K QPS |
| Storage/year | 500M users × 10 posts/day × 365 × 1KB | ~1.8 PB |

### High-Level Design

1. **Shard key**: `user_id` (keeps user's data co-located)
2. **Number of shards**: Start with 256, plan for 1024
3. **Replication**: 1 primary + 2 replicas per shard
4. **Proxy layer**: Vitess for routing and connection pooling

### Low-Level Design

**User table** (per shard):
```sql
CREATE TABLE users (
  user_id BIGINT PRIMARY KEY,
  username VARCHAR(64),
  email VARCHAR(256),
  created_at TIMESTAMP
) ENGINE=InnoDB;
```

**Posts table** (per shard):
```sql
CREATE TABLE posts (
  post_id BIGINT,
  user_id BIGINT,
  content TEXT,
  created_at TIMESTAMP,
  PRIMARY KEY (user_id, post_id)  -- user_id first for shard locality
) ENGINE=InnoDB;
```

### Bottlenecks and Resolutions

| Bottleneck | Resolution |
|------------|------------|
| Cross-shard friend queries | Denormalize friend lists; accept eventual consistency |
| Hot shards (celebrity users) | Shard by post_id for posts table; separate from user shard |
| Connection exhaustion | Vitess connection pooling; limit per-shard connections |

---

## 5. Technology Comparison

| Technology | Best For | Pros | Cons | Avoid When |
|------------|----------|------|------|------------|
| MySQL + Vitess | Relational data at scale | ACID, mature tooling, horizontal scale | Operational complexity, cross-shard joins | Simple apps, <1M users |
| PostgreSQL + Citus | Analytics + OLTP hybrid | Rich SQL, columnar storage | Less battle-tested at extreme scale | Pure OLTP at Meta scale |
| CockroachDB | Global strong consistency | Distributed ACID, no sharding logic | Higher latency, cost | Latency-sensitive, cost-constrained |
| Cassandra | Write-heavy, eventual OK | Linear scale, tunable consistency | No ACID, limited query flexibility | Complex transactions needed |

---

## 6. Pros & Cons

### Sharded MySQL

| Dimension | Pro | Con |
|-----------|-----|-----|
| Consistency | Full ACID per shard | Cross-shard transactions are expensive |
| Latency | Sub-ms reads with replicas | Cross-shard queries add network hops |
| Cost | Commodity hardware, open source | Operational overhead is high |
| Operability | Mature tooling, known failure modes | Resharding is painful |
| Team skills | Most engineers know MySQL | Sharding logic adds complexity |

### Shard Key Choice Trade-offs

| Shard Key | Pro | Con |
|-----------|-----|-----|
| user_id | User data co-located | Celebrity users create hot shards |
| post_id | Even distribution | User queries hit all shards |
| Composite | Flexible | Complex routing logic |

---

## 7. Failure Modes & SRE Lens

### What Breaks at Scale

| Failure Mode | Cause | Impact |
|--------------|-------|--------|
| Primary failure | Hardware, network partition | Writes blocked until failover |
| Replica lag | Write spikes, slow queries | Stale reads, inconsistency |
| Connection exhaustion | App server scaling, no pooling | Cascading failures |
| Hot shard | Celebrity user, viral content | p99 spikes, timeouts |
| Split brain | Network partition during failover | Data corruption |

### Detection

| Failure | Metric | Alert Threshold |
|---------|--------|-----------------|
| Primary down | `mysql_up` | == 0 for 10s |
| Replica lag | `seconds_behind_master` | > 30s |
| Connection exhaustion | `threads_connected / max_connections` | > 80% |
| Hot shard | `queries_per_shard` | > 2x mean |

### Recovery

| Failure | Recovery Steps |
|---------|----------------|
| Primary failure | 1. Orchestrator promotes replica 2. Update proxy routing 3. Rebuild failed node |
| Replica lag | 1. Kill long-running queries 2. Add replica 3. Investigate write pattern |
| Connection exhaustion | 1. Restart proxy 2. Increase pool size 3. Add proxy instances |
| Hot shard | 1. Cache hot data in Redis 2. Rate limit requests 3. Split shard |

### Post-Mortem Template

```
## Incident: Shard 42 Primary Failure
**Duration**: 2024-01-15 14:32 - 14:47 UTC (15 min)
**Impact**: 0.4% of users saw write errors

### Timeline
- 14:32 - Primary node disk failed
- 14:34 - Alert fired (mysql_up == 0)
- 14:36 - On-call acknowledged
- 14:41 - Orchestrator promoted replica
- 14:47 - Full recovery confirmed

### Root Cause
Hardware failure (disk). Node was 3 years old, past warranty.

### Action Items
- [ ] Replace all nodes >2 years old (P1)
- [ ] Reduce failover time to <5 min (P2)
- [ ] Add disk health monitoring (P2)
```

---

## 8. Interview Answer — Authority Mode

**Question**: "How would you scale MySQL to handle billions of users?"

**Answer**:

- **Horizontal sharding by user_id** — keeps each user's data on one shard, avoids cross-shard joins for common queries
- **Vitess or ProxySQL** — handles routing, connection pooling, and abstracts sharding from the application
- **Read replicas** — 1 primary + 2 replicas per shard; route reads to replicas, writes to primary
- **Capacity planning** — start with 256 shards, plan resharding at 70% capacity; resharding is expensive so over-provision
- **Storage optimization** — MyRocks engine reduces storage 50% vs InnoDB; critical at petabyte scale

**Trade-offs acknowledged**:
- Cross-shard queries are expensive; denormalize where needed
- Shard key choice is permanent; wrong choice requires full migration
- Operational complexity is high; need strong automation (Orchestrator for failover)

**Real-world proof**: Meta runs this architecture for billions of users; Vitess powers YouTube's MySQL layer.

---

## 9. FAQ

**Q: When should I shard vs. use read replicas?**
Read replicas solve read scaling; sharding solves write scaling and storage limits. If you're write-bound or exceeding single-node storage, you need sharding.

**Q: How do I handle cross-shard joins?**
Avoid them. Denormalize data, use application-level joins, or accept that some queries will be slow. Scatter-gather across shards is expensive.

**Q: What's the right number of shards to start with?**
256 is a common starting point. It's easier to merge shards than split them. Plan for 3-5 years of growth.

**Q: How does failover work?**
Use Orchestrator or Vitess VTOrc. They monitor replication topology and automatically promote a replica when the primary fails. Typical failover time: 10-30 seconds.

**Q: Should I use synchronous or asynchronous replication?**
Semi-synchronous for durability (at least one replica confirms). Fully synchronous kills write performance. Async risks data loss on primary failure.

---

## 10. Key Terms

| Term | Definition |
|------|------------|
| Shard | A horizontal partition of data; each shard is an independent MySQL instance |
| Shard key | The column used to determine which shard holds a row (e.g., user_id) |
| Vitess | Open-source sharding middleware for MySQL, originally from YouTube |
| Orchestrator | MySQL replication topology manager and failover tool |
| MyRocks | LSM-tree storage engine for MySQL, optimized for write-heavy and space efficiency |
| Binlog | MySQL's binary log; records all changes for replication |
| Semi-sync replication | Primary waits for at least one replica to acknowledge before committing |
| Scatter-gather | Query pattern that hits all shards and aggregates results |

---

## Progress Tracker

```
Topic Progress:
- [x] MySQL at Scale (Meta's approach)
- [ ] PostgreSQL vs MySQL
- [ ] NoSQL: Cassandra, DynamoDB, MongoDB
- [ ] NewSQL: CockroachDB, Spanner
- [ ] Redis patterns
- [ ] Object storage (S3)
- [ ] Time-series databases
```

**Next**: `postgresql-vs-mysql.md` — Use command `next topic` to continue.
