# NoSQL Scaling: Deep Comparison

## 1. Concept Overview

**What this covers**: How different NoSQL databases achieve horizontal scaling, their architectures, and scaling trade-offs.

**Why it matters**: Not all NoSQL databases scale the same way. Understanding the mechanisms helps you:
- Choose the right database for your scale requirements
- Anticipate operational challenges
- Design data models that scale well

---

## 2. Scaling Architectures Overview

### Architecture Types

| Type | Examples | How It Scales | Trade-off |
|------|----------|---------------|-----------|
| **Leaderless** | Cassandra, DynamoDB, Riak | Any node accepts writes | Conflict resolution needed |
| **Leader-based** | MongoDB, Redis Cluster | Primary handles writes | Primary is bottleneck |
| **Coordinator** | HBase, Bigtable | Master assigns regions | Master availability |

---

## 3. Cassandra Scaling

### Architecture

```
         ┌─────────────────────────────────────┐
         │         Consistent Hashing          │
         │              Token Ring              │
         └─────────────────────────────────────┘
                          │
    ┌─────────┬───────────┼───────────┬─────────┐
    ▼         ▼           ▼           ▼         ▼
┌───────┐ ┌───────┐   ┌───────┐   ┌───────┐ ┌───────┐
│Node A │ │Node B │   │Node C │   │Node D │ │Node E │
│ 0-20  │ │ 21-40 │   │ 41-60 │   │ 61-80 │ │81-100 │
└───────┘ └───────┘   └───────┘   └───────┘ └───────┘
    │         │           │           │         │
    └─────────┴───────────┴───────────┴─────────┘
              Replication Factor = 3
         (each token range on 3 nodes)
```

### Scaling Characteristics

| Dimension | Behavior |
|-----------|----------|
| **Write scaling** | Linear — add nodes, add throughput |
| **Read scaling** | Linear — with tunable consistency |
| **Rebalancing** | Automatic via virtual nodes (vnodes) |
| **Hotspots** | Possible with bad partition keys |

### How to Scale Cassandra

**Adding nodes**:
```bash
# 1. Bootstrap new node (streams data from existing nodes)
# 2. nodetool cleanup on existing nodes (removes migrated data)
# 3. Automatic token rebalancing with vnodes
```

**Scaling math**:
```
Current: 6 nodes, 100K writes/sec capacity
Add 3 nodes → 9 nodes
New capacity: ~150K writes/sec (linear scaling)
```

### Cassandra Scaling Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Partition size | 100MB recommended | Better partition key design |
| Cells per partition | 2 billion | Time-bucketing |
| Node count | Tested to 1000+ | Multi-DC deployment |
| Write throughput/node | ~10-15K/sec | SSD, tuning |

---

## 4. DynamoDB Scaling

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AWS DynamoDB                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Request Router                      │   │
│  └─────────────────────┬───────────────────────────┘   │
│                        │                                 │
│        ┌───────────────┼───────────────┐                │
│        ▼               ▼               ▼                │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│   │Partition│     │Partition│     │Partition│          │
│   │    0    │     │    1    │     │    N    │          │
│   │ (3 AZs) │     │ (3 AZs) │     │ (3 AZs) │          │
│   └─────────┘     └─────────┘     └─────────┘          │
│                                                         │
│   Automatic partitioning based on:                      │
│   - Storage (10GB per partition)                        │
│   - Throughput (3000 RCU / 1000 WCU per partition)     │
└─────────────────────────────────────────────────────────┘
```

### Scaling Characteristics

| Dimension | Behavior |
|-----------|----------|
| **Write scaling** | Automatic partition splits |
| **Read scaling** | Automatic, with DAX for caching |
| **Capacity modes** | Provisioned or On-Demand |
| **Global Tables** | Multi-region active-active |

### DynamoDB Capacity Planning

**Provisioned mode**:
```
RCU = (reads/sec × item_size_KB) / 4  (eventually consistent)
RCU = (reads/sec × item_size_KB) / 4 × 2  (strongly consistent)
WCU = writes/sec × item_size_KB
```

**On-Demand mode**:
- Auto-scales to traffic
- 2x previous peak capacity instantly
- Higher per-request cost

### DynamoDB Scaling Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Item size | 400KB | S3 for large objects |
| Partition throughput | 3000 RCU / 1000 WCU | Distribute across partition keys |
| GSI throughput | Same as base table | Plan GSI capacity |
| Burst capacity | 300 seconds of unused | Don't rely on it |

### Hot Partition Problem

```
Bad:  Partition Key = date (2024-01-15)
      → All traffic hits one partition

Good: Partition Key = date#shard (2024-01-15#3)
      → Traffic distributed across shards
```

---

## 5. MongoDB Scaling

### Architecture (Sharded Cluster)

```
┌─────────────────────────────────────────────────────────┐
│                      mongos Router                       │
│               (stateless, multiple for HA)               │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────┐
│              Config Servers (Replica Set)                │
│              (metadata, chunk → shard mapping)           │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │ Shard 0 │       │ Shard 1 │       │ Shard 2 │
   │(Replica │       │(Replica │       │(Replica │
   │   Set)  │       │   Set)  │       │   Set)  │
   └─────────┘       └─────────┘       └─────────┘
```

### Scaling Characteristics

| Dimension | Behavior |
|-----------|----------|
| **Write scaling** | Per-shard primary handles writes |
| **Read scaling** | Read preference to secondaries |
| **Rebalancing** | Balancer moves chunks automatically |
| **Transactions** | Supported across shards (4.2+) |

### MongoDB Sharding Strategies

| Strategy | How It Works | Use When |
|----------|--------------|----------|
| **Hashed** | Hash of shard key | Even distribution, random access |
| **Ranged** | Key ranges to shards | Range queries on shard key |
| **Zone** | Tags to assign data to shards | Data locality, compliance |

### MongoDB Scaling Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Document size | 16MB | GridFS for large files |
| Shard key | Immutable once set | Careful planning |
| Jumbo chunks | 250MB+ | Better shard key |
| Max shards | 1024 | Usually sufficient |

---

## 6. Redis Cluster Scaling

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Redis Cluster                          │
│                                                          │
│   Slot Range: 0 ─────────────────────────────── 16383   │
│                                                          │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│   │Master 0 │     │Master 1 │     │Master 2 │          │
│   │0-5460   │     │5461-10922│    │10923-16383│         │
│   │         │     │         │     │         │          │
│   │Replica  │     │Replica  │     │Replica  │          │
│   └─────────┘     └─────────┘     └─────────┘          │
│                                                          │
│   16384 hash slots distributed across masters            │
└─────────────────────────────────────────────────────────┘
```

### Scaling Characteristics

| Dimension | Behavior |
|-----------|----------|
| **Write scaling** | Shard by key hash slot |
| **Read scaling** | Replicas can serve reads |
| **Rebalancing** | Manual slot migration |
| **Cross-slot** | Operations limited |

### Redis Cluster Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Cluster size | 1000 nodes recommended | Multiple clusters |
| Key size | 512MB | Avoid large values |
| Cross-slot ops | Same slot only | Hash tags `{user}:data` |
| Memory | Per-node RAM | Add nodes, eviction |

---

## 7. Scaling Comparison Matrix

### Write Scaling

| Database | Mechanism | Scaling Factor | Complexity |
|----------|-----------|----------------|------------|
| Cassandra | Leaderless, any node | Linear | Low |
| DynamoDB | Auto-partition split | Automatic | None |
| MongoDB | Shard primary writes | Per-shard limited | Medium |
| Redis Cluster | Hash slot per master | Per-slot limited | Medium |

### Read Scaling

| Database | Mechanism | Consistency Options |
|----------|-----------|---------------------|
| Cassandra | Any replica | ONE, QUORUM, ALL |
| DynamoDB | Any partition replica | Eventual, Strong |
| MongoDB | Secondaries | Primary, Secondary, Nearest |
| Redis Cluster | Replicas (READONLY) | Eventual |

### Rebalancing

| Database | Automatic? | Impact During |
|----------|------------|---------------|
| Cassandra | Yes (vnodes) | Minimal with streaming |
| DynamoDB | Yes | Transparent |
| MongoDB | Yes (balancer) | Chunk migration overhead |
| Redis Cluster | Manual | Slot migration latency |

### Global Distribution

| Database | Multi-Region | Consistency |
|----------|--------------|-------------|
| Cassandra | Native (NetworkTopologyStrategy) | Tunable per-DC |
| DynamoDB | Global Tables | Eventual (seconds) |
| MongoDB | Zone sharding | Within zone only |
| Redis | Enterprise Geo-Replication | Eventual |

---

## 8. Scaling Anti-Patterns

### 1. Hot Partition Key

```
❌ Bad: partition_key = "2024-01-15" (all today's data)
✅ Good: partition_key = "2024-01-15#shard_5" (distributed)
```

### 2. Unbounded Growth in One Partition

```
❌ Bad: All user's messages in one partition
✅ Good: Time-bucket: user_123#2024-01 (monthly buckets)
```

### 3. Scatter-Gather Queries

```
❌ Bad: Query that hits all partitions/shards
✅ Good: Query that targets specific partition
```

### 4. Large Items/Documents

```
❌ Bad: 10MB documents in MongoDB
✅ Good: Reference large blobs in S3, store metadata only
```

### 5. Uneven Shard Key Distribution

```
❌ Bad: country as shard key (US gets 50% traffic)
✅ Good: user_id with good hash distribution
```

---

## 9. Interview Answer — Authority Mode

**Question**: "How does Cassandra scale differently from MongoDB?"

**Answer**:

**Cassandra** (leaderless):
- Any node accepts writes — no single primary bottleneck
- Linear write scaling — add nodes, add throughput proportionally
- Consistent hashing with virtual nodes — automatic data distribution
- Tunable consistency — trade consistency for performance per query
- Best for: Write-heavy, time-series, known query patterns

**MongoDB** (leader-based sharding):
- Each shard has a primary that handles all writes for that shard
- Write scaling limited by per-shard primary capacity
- Chunk-based rebalancing — balancer moves data between shards
- Supports cross-shard transactions (with overhead)
- Best for: Document workloads, flexible queries, need transactions

**Key difference**: Cassandra's leaderless architecture gives better write scaling. MongoDB's leader-per-shard gives stronger consistency and transactions but limits write throughput to what the primary can handle.

---

## 10. FAQ

**Q: Which scales better, Cassandra or DynamoDB?**
Both scale to millions of requests/sec. DynamoDB is fully managed and auto-scales. Cassandra requires capacity planning but gives more control and no vendor lock-in.

**Q: Can MongoDB match Cassandra's write throughput?**
Not easily. MongoDB's shard primary limits write throughput per shard. You'd need many shards. Cassandra's leaderless model scales writes more naturally.

**Q: How do I know when to add nodes?**
Monitor: CPU >70%, disk I/O saturation, p99 latency increasing, compaction falling behind. Add nodes before hitting limits.

**Q: What's the hardest part of scaling NoSQL?**
Data modeling. Poor partition keys cause hot spots that can't be fixed by adding nodes. Redesigning partition keys requires data migration.

---

## Key Terms

| Term | Definition |
|------|------------|
| Partition | Horizontal unit of data distribution |
| Consistent hashing | Hash scheme minimizing data movement on cluster changes |
| Vnodes | Virtual nodes — multiple token ranges per physical node |
| Replication factor | Number of copies of each partition |
| Quorum | Majority of replicas agreeing |
| Chunk | MongoDB's unit of data for sharding |
| Hash slot | Redis Cluster's 16384 slots for key distribution |
