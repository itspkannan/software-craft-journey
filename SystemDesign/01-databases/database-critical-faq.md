# Database Critical FAQ: Scalability, Availability & Failure Handling

A comprehensive FAQ covering the hard questions about database scaling, replication, sharding, and failure scenarios across SQL, NoSQL, and NewSQL systems.

---

## Table of Contents

1. [Scalability Fundamentals](#1-scalability-fundamentals)
2. [Sharding](#2-sharding)
3. [Replication](#3-replication)
4. [Consistency & CAP Theorem](#4-consistency--cap-theorem)
5. [Failure Scenarios & Recovery](#5-failure-scenarios--recovery)
6. [Database-Specific Failures](#6-database-specific-failures)
7. [Operational Challenges](#7-operational-challenges)
8. [Migration & Evolution](#8-migration--evolution)
9. [Cost & Capacity Planning](#9-cost--capacity-planning)
10. [Decision Framework](#10-decision-framework)

---

## 1. Scalability Fundamentals

### Q: What's the difference between vertical and horizontal scaling?

**Vertical Scaling (Scale Up)**:
- Add more CPU, RAM, storage to existing machine
- Simpler (no code changes)
- Hard limit (biggest available machine)
- Single point of failure remains
- Cost: Exponential at high end

**Horizontal Scaling (Scale Out)**:
- Add more machines
- Requires architecture changes (sharding, replication)
- Theoretically unlimited
- Better fault tolerance
- Cost: Linear

**When to choose**:
- Start vertical until you hit limits (~$10K/month instance)
- Go horizontal when: single node can't handle load, need HA, or vertical cost is prohibitive

---

### Q: At what point should I start thinking about scaling?

**Warning signs**:
| Metric | Warning | Critical |
|--------|---------|----------|
| CPU utilization | >70% sustained | >85% |
| Memory usage | >80% | >90% |
| Disk I/O | >70% capacity | >85% |
| Connection count | >70% max | >85% |
| Query latency p99 | 2x baseline | 5x baseline |
| Replication lag | >10 seconds | >60 seconds |

**Rule of thumb**: Start planning when at 50% capacity. Implement when at 70%.

---

### Q: How do read replicas help scaling, and what are their limits?

**What read replicas solve**:
- Read scaling (distribute read load)
- Geographic latency (replica near users)
- Analytics isolation (heavy queries don't impact production)
- Backup source (backup from replica, not primary)

**What read replicas DON'T solve**:
- Write scaling (all writes still go to primary)
- Storage limits (each replica has full copy)
- Write latency
- Strong consistency (replication lag)

**Limits**:
```
Practical limit: 5-10 read replicas
Beyond that:
- Replication overhead on primary
- Consistency issues multiply
- Operational complexity

If you need more read capacity:
- Add caching layer (Redis)
- Consider sharding
```

---

### Q: When do I need sharding vs. read replicas vs. caching?

| Problem | Solution |
|---------|----------|
| Read throughput | Read replicas → Caching → Sharding |
| Write throughput | Sharding (only solution) |
| Storage capacity | Sharding (only solution) |
| Read latency | Caching → Read replicas |
| Write latency | Better hardware → Async writes → Sharding |
| Geographic latency | Multi-region replicas → Global sharding |

**Decision flow**:
```
Is it a write problem?
  Yes → Sharding (no other solution at scale)
  No → Is it a latency problem?
    Yes → Caching first, then replicas
    No → Is it a throughput problem?
      Yes → Read replicas first, then sharding
```

---

## 2. Sharding

### Q: How do I choose a shard key?

**Shard key requirements**:
1. **High cardinality** — many unique values for even distribution
2. **Query inclusion** — present in most queries to avoid scatter-gather
3. **Even distribution** — prevents hot shards
4. **Stability** — rarely changes (changing shard key = data migration)

**Common shard key patterns**:

| Pattern | Pros | Cons | Use When |
|---------|------|------|----------|
| `user_id` | User data co-located | Celebrity users = hot shards | User-centric apps |
| `tenant_id` | Tenant isolation | Uneven tenant sizes | Multi-tenant SaaS |
| `hash(id)` | Even distribution | Range queries hit all shards | Write-heavy, random access |
| `time` | Easy archival | Recent data = hot shard | Time-series with even write rate |
| `geo_region` | Data locality | Uneven region sizes | Compliance, latency requirements |
| `composite` | Flexible | Complex routing | Multiple access patterns |

**Example bad choices**:
```
❌ timestamp alone — all writes hit latest shard
❌ boolean fields — only 2 shards
❌ low-cardinality fields — uneven distribution
❌ frequently updated fields — shard key should be immutable
```

---

### Q: What happens when I need to re-shard?

**Why re-sharding happens**:
- Wrong initial shard key choice
- Business model changed
- Hot shards emerged
- Need more shards for capacity

**Re-sharding approaches**:

**1. Double-write migration**:
```
Phase 1: Write to both old and new shards
Phase 2: Backfill historical data to new shards
Phase 3: Switch reads to new shards
Phase 4: Stop writes to old shards
Phase 5: Decommission old shards

Duration: Days to weeks
Risk: Data inconsistency during migration
```

**2. Ghost table migration** (MySQL):
```
1. Create new table with new sharding
2. pt-online-schema-change or gh-ost copies data
3. Triggers keep new table in sync
4. Atomic swap when caught up

Duration: Hours to days
Risk: Trigger overhead, lock during swap
```

**3. Vitess resharding**:
```
1. Define new sharding scheme
2. Vitess clones data to new shards
3. Vitess switches traffic
4. Drop old shards

Duration: Hours (depending on data size)
Risk: Lower (purpose-built tooling)
```

**Key insight**: Re-sharding is expensive. Over-shard initially (256 shards even if you need 4).

---

### Q: How do I handle cross-shard queries?

**The problem**:
```sql
-- If orders are sharded by user_id:
SELECT * FROM orders WHERE status = 'pending'  -- hits ALL shards
SELECT * FROM orders WHERE user_id = 123       -- hits ONE shard
```

**Solutions**:

**1. Denormalization** — duplicate data to avoid joins:
```
Instead of: users JOIN orders
Store: user_name in orders table
```

**2. Application-level joins**:
```python
users = query_shard_1("SELECT * FROM users WHERE region = 'US'")
user_ids = [u.id for u in users]
orders = query_all_shards(f"SELECT * FROM orders WHERE user_id IN ({user_ids})")
```

**3. Scatter-gather** (accept the cost):
```
Query all shards in parallel → Merge results
Acceptable for: Admin queries, reports, low-frequency operations
```

**4. Secondary index table** (separate sharding):
```
orders: sharded by user_id
orders_by_status: sharded by status, contains (status, user_id, order_id)

Query by status → orders_by_status → get user_ids → query orders
```

**5. Search index**:
```
Sync data to Elasticsearch
Complex queries go to Elasticsearch
Primary data fetched from sharded DB
```

---

### Q: How do I handle transactions across shards?

**The hard truth**: Cross-shard transactions are expensive. Avoid if possible.

**Options**:

**1. Design to avoid them**:
```
Keep all related data on same shard
Example: user_id as shard key keeps user + orders + payments together
```

**2. Saga pattern** (eventual consistency):
```
Transaction: Transfer $100 from User A (shard 1) to User B (shard 2)

1. Debit User A (shard 1) — reserve $100
2. Credit User B (shard 2) — add $100
3. Confirm debit (shard 1) — finalize

If step 2 fails: Compensating action on shard 1 (refund)
```

**3. Two-Phase Commit (2PC)**:
```
Coordinator:
  1. Prepare: Ask all shards to prepare
  2. Commit: If all prepared, tell all to commit

Problems:
- Coordinator failure = blocked transactions
- Lock held during entire process
- Performance impact
```

**4. Use NewSQL** (Spanner, CockroachDB):
```
Distributed transactions built-in
Handled at database level
Trade-off: Higher latency
```

**Recommendation**: Design data model to minimize cross-shard transactions. Use sagas for the few that remain.

---

### Q: What's the hot shard problem and how do I solve it?

**What it is**: One shard receives disproportionate traffic, becoming a bottleneck while others are underutilized.

**Causes**:
- Celebrity users (1M followers posting)
- Viral content
- Poor shard key distribution
- Time-based keys (all writes to "today" shard)

**Solutions**:

**1. Shard splitting**:
```
If shard 5 is hot:
Split into shard 5a and 5b
Redistribute data
Update routing

Problem: Operational overhead
```

**2. Write sharding for hot keys**:
```
Normal user: user_123 → shard 7
Celebrity: user_celebrity_123_shard_0, user_celebrity_123_shard_1, ...

Write to random sub-shard
Read: scatter-gather across sub-shards
```

**3. Caching**:
```
Put hot data in Redis
Absorb read load
Doesn't help write-hot scenarios
```

**4. Rate limiting**:
```
Limit writes per user
Queue excess writes
Process asynchronously
```

**5. Separate storage for hot data**:
```
Hot users → dedicated high-performance cluster
Regular users → standard cluster
Route at application layer
```

---

## 3. Replication

### Q: Sync vs. async replication — when to use each?

**Synchronous Replication**:
```
Primary ──write──▶ Replica (waits for ACK) ──▶ Commit confirmed

Guarantees: Zero data loss (RPO = 0)
Cost: Higher write latency (network round trip)
Risk: Replica failure blocks writes
```

**Asynchronous Replication**:
```
Primary ──write──▶ Commit confirmed ──▶ Replica (eventually)

Guarantees: None (potential data loss)
Cost: Lowest latency
Risk: Data loss if primary fails before replication
```

**Semi-synchronous** (MySQL):
```
Primary ──write──▶ At least 1 replica ACKs ──▶ Commit confirmed

Guarantees: Survives single failure
Cost: Moderate latency increase
Best balance for most use cases
```

**Decision matrix**:

| Data Type | Replication | Rationale |
|-----------|-------------|-----------|
| Financial transactions | Sync | Cannot lose money |
| User authentication | Semi-sync | Important but some loss OK |
| User activity logs | Async | Rebuild from events if lost |
| Session data | Async | Recreate on loss |
| Analytics events | Async | Eventual consistency fine |

---

### Q: What is replication lag and how do I handle it?

**What it is**: Time delay between write on primary and visibility on replica.

**Causes**:
- Network latency
- Replica under-provisioned (slower than primary)
- Large transactions
- Heavy write load
- Long-running queries on replica blocking replication

**Problems caused**:
```
1. User writes data, immediately reads from replica → doesn't see their write
2. Reports show stale data
3. Dependent operations fail (read-after-write)
```

**Solutions**:

**1. Read-your-writes consistency**:
```python
# Track recent write timestamps per user
last_write_time[user_id] = now()

# When reading, choose source
if now() - last_write_time[user_id] < 10 seconds:
    read_from_primary()  # or wait for replica to catch up
else:
    read_from_replica()
```

**2. Monotonic reads**:
```python
# Remember which replica served last read
# Always use same replica for session (sticky sessions)
# Or track LSN/GTID and wait for replica to reach it
```

**3. Replica health-based routing**:
```python
def get_read_connection():
    for replica in replicas:
        if replica.lag < 5 seconds:
            return replica
    return primary  # fallback
```

**4. Synchronous replication for critical paths**:
```
Most reads: async replicas (fast)
Critical reads (after write): primary or sync replica
```

**Monitoring**:
```sql
-- MySQL
SHOW SLAVE STATUS\G  -- Seconds_Behind_Master

-- PostgreSQL
SELECT pg_last_wal_receive_lsn() - pg_last_wal_replay_lsn();
```

---

### Q: How does failover work and what can go wrong?

**Failover process**:
```
1. Detect primary failure (health checks fail)
2. Elect new primary (most up-to-date replica)
3. Promote replica to primary
4. Redirect traffic to new primary
5. Reconfigure other replicas to follow new primary
6. (Later) Recover old primary as replica
```

**What can go wrong**:

**1. Split-brain**:
```
Problem: Network partition makes both nodes think they're primary
Result: Both accept writes → data divergence

Solutions:
- Quorum-based election (majority required)
- STONITH (Shoot The Other Node In The Head) — fence failed node
- Witness/arbiter node
```

**2. Data loss (async replication)**:
```
Problem: Primary fails before replicating recent writes
Result: Committed transactions lost

Solutions:
- Semi-sync replication
- Acknowledge to client only after replication
- Accept some data loss (design for it)
```

**3. Flip-flopping**:
```
Problem: Unstable network causes repeated failovers
Result: Service disruption, potential data issues

Solutions:
- Cooldown period between failovers
- Require sustained failure (not just blip)
- Manual intervention for ambiguous cases
```

**4. Application connection issues**:
```
Problem: Apps still connected to old primary
Result: Writes to wrong node, split-brain at app level

Solutions:
- Connection pooler with health checks (ProxySQL, PgBouncer)
- DNS-based failover with low TTL
- Application retry with new primary discovery
```

**Failover tools by database**:
| Database | Tool | Mechanism |
|----------|------|-----------|
| MySQL | Orchestrator | Topology tracking, GTID-based |
| MySQL | MHA | Log apply, VIP management |
| PostgreSQL | Patroni | etcd/Consul consensus |
| PostgreSQL | pg_auto_failover | Built-in monitor |
| Redis | Sentinel | Quorum-based |
| MongoDB | Replica Set | Built-in election |

---

### Q: Multi-region replication — what are the trade-offs?

**Architectures**:

**1. Active-Passive (Primary in one region)**:
```
US-East (Primary) ──async──▶ EU-West (Replica)

Pros: Simple, no conflicts
Cons: High write latency from EU, failover complexity
```

**2. Active-Active (Primary per region)**:
```
US-East (Primary) ◀──async──▶ EU-West (Primary)

Pros: Low latency everywhere
Cons: Conflict resolution, eventual consistency
```

**3. Partitioned (Data pinned to region)**:
```
US users → US-East (Primary + Replicas)
EU users → EU-West (Primary + Replicas)

Pros: Strong consistency per region, data sovereignty
Cons: Cross-region queries expensive
```

**Conflict resolution** (active-active):

| Strategy | How It Works | Pros | Cons |
|----------|--------------|------|------|
| Last-write-wins | Timestamp comparison | Simple | Data loss possible |
| Version vectors | Track causality | Preserves all writes | Complex |
| CRDTs | Conflict-free data types | Automatic merge | Limited data types |
| Application logic | Custom merge | Domain-specific | Development effort |

**Latency expectations**:
```
Same AZ: <1ms
Same region, different AZ: 1-2ms
Cross-region (US-EU): 70-150ms
Cross-region (US-Asia): 150-300ms
```

---

## 4. Consistency & CAP Theorem

### Q: What does CAP theorem actually mean for my database choice?

**CAP Theorem**: In a distributed system, during a network partition, you must choose between Consistency and Availability.

**What it actually means**:
```
Normal operation: You can have all three (C, A, P)

During partition (network split):
- CP: Refuse requests to maintain consistency (some nodes unavailable)
- AP: Accept requests but may return stale data (eventually consistent)
```

**Database classifications**:

| Database | During Partition | Trade-off |
|----------|------------------|-----------|
| PostgreSQL (single) | N/A (not distributed) | No partition tolerance |
| PostgreSQL + sync replica | CP | Replica down = writes blocked |
| MySQL + async replica | AP | Potential data loss |
| Cassandra (QUORUM) | CP | Minority partitions unavailable |
| Cassandra (ONE) | AP | May read stale data |
| DynamoDB (default) | AP | Eventually consistent |
| DynamoDB (strong read) | CP | Higher latency |
| Spanner | CP | Waits for TrueTime uncertainty |
| CockroachDB | CP | Refuses writes if no quorum |
| MongoDB | CP (default) | Primary election during partition |

**Practical advice**:
```
1. Most partitions are brief — design for recovery, not steady-state partition
2. Consistency requirements vary by data — use different DBs for different needs
3. "Eventual" consistency often means milliseconds, not hours
4. Test your failure modes — don't assume, verify
```

---

### Q: What's the difference between consistency levels?

| Level | Guarantee | Example |
|-------|-----------|---------|
| **Linearizable** | Operations appear instantaneous, global order | Spanner |
| **Sequential** | Operations appear in some total order | Single-node PostgreSQL |
| **Causal** | Causally related operations ordered | MongoDB sessions |
| **Read-your-writes** | See your own writes | DynamoDB consistent read |
| **Monotonic reads** | Never see older data after newer | Same replica sticky |
| **Eventual** | All replicas converge eventually | Cassandra ONE/ONE |

**Choosing consistency level**:
```
Financial transactions: Linearizable (Spanner, CockroachDB)
User-facing writes: Read-your-writes (most apps)
Social feeds: Eventual (stale is OK)
Analytics: Eventual (reports on yesterday's data anyway)
```

---

### Q: How do I handle eventual consistency in my application?

**Design patterns**:

**1. Idempotency** — handle duplicate operations:
```python
# Bad: Non-idempotent
def add_money(account, amount):
    account.balance += amount

# Good: Idempotent with unique operation ID
def add_money(account, amount, operation_id):
    if operation_id in processed_operations:
        return  # Already processed
    account.balance += amount
    processed_operations.add(operation_id)
```

**2. Compensating actions** — undo on failure:
```python
# Saga pattern
def transfer_money(from_acc, to_acc, amount):
    try:
        debit(from_acc, amount)  # Step 1
        credit(to_acc, amount)   # Step 2
    except:
        refund(from_acc, amount)  # Compensate step 1
```

**3. Read-repair** — fix inconsistencies on read:
```python
def get_user(user_id):
    results = query_all_replicas(user_id)
    if not all_same(results):
        latest = max(results, key=lambda r: r.timestamp)
        repair_replicas(user_id, latest)
    return latest
```

**4. Anti-entropy** — background consistency checks:
```python
# Periodic job
def anti_entropy_repair():
    for key in all_keys():
        values = read_from_all_replicas(key)
        if inconsistent(values):
            correct_value = resolve(values)
            write_to_all_replicas(key, correct_value)
```

**5. UI patterns** — set user expectations:
```
"Your changes are being saved..."
"This report reflects data as of 5 minutes ago"
"Refreshing..." (show loading state)
```

---

## 5. Failure Scenarios & Recovery

### Q: What are the most common database failure scenarios?

**Tier 1: Infrastructure failures**
| Failure | Likelihood | Impact | Recovery |
|---------|------------|--------|----------|
| Disk failure | Medium | Data loss if no RAID/replication | Replace disk, rebuild from replica |
| Network partition | Low-Medium | Split-brain, unavailability | Automatic (if designed for it) |
| Instance crash | Medium | Brief unavailability | Automatic restart, failover |
| AZ outage | Low | Regional unavailability | Failover to other AZ |
| Region outage | Very Low | Major outage | DR failover (manual/auto) |

**Tier 2: Database-level failures**
| Failure | Likelihood | Impact | Recovery |
|---------|------------|--------|----------|
| Replication break | Medium | Data divergence, stale reads | Re-sync replica |
| Connection exhaustion | Medium | New connections rejected | Pool tuning, restart |
| Lock contention | High | Slow queries, timeouts | Query optimization, kill locks |
| OOM (Out of Memory) | Medium | Crash, restart | Tune memory, add RAM |
| Disk full | Medium | Writes fail | Add storage, cleanup |

**Tier 3: Data-level failures**
| Failure | Likelihood | Impact | Recovery |
|---------|------------|--------|----------|
| Data corruption | Low | Query errors, wrong results | Restore from backup |
| Accidental deletion | Medium | Data loss | Point-in-time recovery |
| Schema migration failure | Medium | Broken queries, downtime | Rollback migration |
| Bad data (application bug) | High | Business logic errors | Application fix + data repair |

---

### Q: How do I design for failure?

**Principles**:

**1. Assume everything fails**:
```
- Network will partition
- Disks will fail
- Processes will crash
- Humans will make mistakes
```

**2. Blast radius containment**:
```
- Isolate tenants (separate schemas, databases, clusters)
- Bulkhead pattern (separate connection pools)
- Circuit breakers (stop cascading failures)
```

**3. Graceful degradation**:
```python
def get_user_recommendations():
    try:
        return recommendation_service.get()  # Personalized
    except ServiceUnavailable:
        return cache.get('popular_items')  # Fallback to popular
    except:
        return []  # Empty is better than error
```

**4. Redundancy at every layer**:
```
Application: Multiple instances behind load balancer
Database: Primary + replicas + cross-region DR
Storage: Replication + backups + different storage systems
Network: Multiple paths, multiple providers
```

**5. Test failure modes**:
```
- Chaos engineering (kill random instances)
- Game days (simulate major failures)
- DR drills (actually failover to DR)
- Backup restore tests (actually restore)
```

---

### Q: What's the recovery process for different failure types?

**Primary database failure**:
```
Automatic (with proper setup):
1. Health check detects failure (5-30 seconds)
2. Orchestrator/Patroni initiates failover
3. Most up-to-date replica promoted
4. DNS/proxy updated
5. Other replicas reconfigured
6. Alert sent to on-call

Manual investigation:
7. Diagnose root cause
8. Recover failed node as replica
9. Post-mortem
```

**Data corruption**:
```
1. Detect: Monitoring alerts, application errors, checksum failures
2. Isolate: Remove corrupted node from serving traffic
3. Assess: Determine extent of corruption
4. Recover:
   - Point-in-time recovery to before corruption
   - Or restore from backup + replay logs
5. Validate: Verify data integrity
6. Resume: Return to service
7. Post-mortem: How did corruption happen?
```

**Accidental data deletion**:
```
1. Stop the bleeding: Revoke access, prevent further damage
2. Assess: What was deleted? When?
3. Recover options:
   - PITR: Restore to just before deletion
   - Delayed replica: If you have one with lag
   - Backup restore: Restore table/data from backup
4. Reconcile: Handle transactions during recovery window
5. Post-mortem: Improve access controls, add safeguards
```

**Cluster-wide outage**:
```
1. Incident declared, war room activated
2. Assess: What's the state of each node?
3. Triage:
   - If one node healthy: Promote it
   - If all down: Restore from backup
4. Recovery:
   - Bring up primary first
   - Add replicas
   - Validate data integrity
5. Resume traffic gradually
6. Extended post-mortem
```

---

## 6. Database-Specific Failures

### Q: What are MySQL-specific failure scenarios?

**1. Replication drift/break**:
```
Symptoms: Slave SQL thread stopped, GTID gaps
Causes: Network issues, slave too slow, DDL conflicts

Recovery:
- Check SHOW SLAVE STATUS
- If small gap: pt-table-checksum + pt-table-sync
- If large gap: Re-provision replica from backup

Prevention:
- Semi-sync replication
- GTID-based replication
- Monitor replication lag
```

**2. InnoDB corruption**:
```
Symptoms: Crash on startup, "InnoDB: corrupted" in logs
Causes: Disk failure, power loss, bugs

Recovery:
- innodb_force_recovery (escalating levels 1-6)
- mysqldump what you can
- Restore from backup

Prevention:
- innodb_flush_log_at_trx_commit = 1
- Battery-backed RAID
- Regular backups
```

**3. Table lock contention**:
```
Symptoms: Queries stuck "Waiting for table metadata lock"
Causes: Long-running queries, DDL blocking

Recovery:
- SHOW PROCESSLIST to find blockers
- KILL blocking query
- pt-kill for automation

Prevention:
- Query timeouts
- pt-online-schema-change for DDL
- Avoid long transactions
```

---

### Q: What are PostgreSQL-specific failure scenarios?

**1. Bloat (dead tuples)**:
```
Symptoms: Table size growing, slow queries, disk full
Causes: Autovacuum not keeping up, long transactions

Recovery:
- pg_repack (online rebuild)
- VACUUM FULL (blocks table)
- Increase autovacuum aggressiveness

Prevention:
- Tune autovacuum settings
- Avoid long-running transactions
- Monitor pg_stat_user_tables (n_dead_tup)
```

**2. Transaction ID wraparound**:
```
Symptoms: Warnings in logs, eventually database refuses writes
Causes: Vacuum not running, very old transactions

Recovery:
- Emergency VACUUM FREEZE
- May require single-user mode

Prevention:
- Monitor age(datfrozenxid)
- Alert at 500M, critical at 1B
- Ensure autovacuum is working
```

**3. Connection exhaustion**:
```
Symptoms: "FATAL: too many connections"
Causes: Connection leak, no pooling, pool misconfigured

Recovery:
- Identify connection hogs: SELECT * FROM pg_stat_activity
- Terminate idle connections
- Restart pooler if stuck

Prevention:
- Use PgBouncer
- Set statement_timeout
- Monitor connections
```

---

### Q: What are Cassandra-specific failure scenarios?

**1. Tombstone overload**:
```
Symptoms: Slow reads, OOM, "TombstoneOverwhelmingException"
Causes: Too many deletes, range deletes, TTL expiration

Recovery:
- Force compaction: nodetool compact
- Increase gc_grace_seconds temporarily
- Rebuild table if severe

Prevention:
- Design data model to minimize deletes
- Use TTL carefully
- Run repairs regularly
```

**2. Gossip/cluster membership issues**:
```
Symptoms: Nodes not seeing each other, split cluster
Causes: Network issues, clock skew, gossip overload

Recovery:
- Check nodetool gossipinfo
- Restart gossip: nodetool disablegossip/enablegossip
- Restart node if needed

Prevention:
- NTP on all nodes
- Stable network
- Monitor gossip metrics
```

**3. Compaction falling behind**:
```
Symptoms: Disk usage growing, read latency increasing
Causes: Write-heavy workload, undersized cluster

Recovery:
- Increase compaction throughput
- Add nodes to distribute load
- nodetool compact (forces immediate compaction)

Prevention:
- Monitor pending compactions
- Proper capacity planning
- Choose right compaction strategy (LCS vs STCS)
```

---

### Q: What are DynamoDB-specific failure scenarios?

**1. Throttling (ProvisionedThroughputExceededException)**:
```
Symptoms: Requests rejected, increased latency
Causes: Hot partition, exceeded capacity, burst depleted

Recovery:
- Exponential backoff (SDK does this)
- Enable auto-scaling
- Switch to on-demand

Prevention:
- Distribute partition keys
- Right-size provisioned capacity
- Use on-demand for unpredictable workloads
```

**2. Hot partition**:
```
Symptoms: Throttling despite available capacity
Causes: Uneven partition key distribution

Recovery:
- Identify hot key via CloudWatch
- Implement write sharding
- Add caching (DAX) for hot reads

Prevention:
- High-cardinality partition keys
- Add randomness if needed (composite key)
```

**3. GSI propagation lag**:
```
Symptoms: GSI query returns stale/missing data
Causes: GSI updates are eventually consistent

Recovery:
- Wait for propagation
- Query base table for critical reads

Prevention:
- Understand GSI is eventually consistent
- Don't rely on GSI for strongly consistent reads
```

---

### Q: What are Redis-specific failure scenarios?

**1. Memory exhaustion**:
```
Symptoms: OOM errors, evictions, rejections
Causes: Data growth, no eviction policy, memory leak

Recovery:
- Enable eviction: maxmemory-policy allkeys-lru
- Delete unnecessary keys
- Add memory or nodes

Prevention:
- Set maxmemory
- Use TTL on cache entries
- Monitor memory usage
```

**2. Cluster slot migration issues**:
```
Symptoms: CLUSTERDOWN, slot in migrating state
Causes: Failed migration, node crash during rebalance

Recovery:
- redis-cli --cluster fix
- Manual slot assignment if needed

Prevention:
- Monitor cluster health
- Avoid rebalancing during peak
```

**3. Persistence issues (RDB/AOF)**:
```
Symptoms: Failed background saves, data loss on restart
Causes: Disk full, slow I/O, large dataset

Recovery:
- Free disk space
- Check RDB/AOF file integrity
- Restore from backup if corrupted

Prevention:
- Monitor disk space
- Use both RDB + AOF
- Test recovery regularly
```

---

## 7. Operational Challenges

### Q: How do I perform zero-downtime schema migrations?

**Principles**:
1. Make all changes backwards compatible
2. Deploy in phases (expand-migrate-contract)
3. Never hold locks for long

**Adding a column**:
```sql
-- Safe: Add nullable column (no lock)
ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL;

-- Application deploys to write phone
-- Backfill existing rows
UPDATE users SET phone = '...' WHERE phone IS NULL;  -- batched

-- Later: Add NOT NULL constraint
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
```

**Removing a column**:
```sql
-- Phase 1: Stop reading column (application deploy)
-- Phase 2: Stop writing column (application deploy)
-- Phase 3: Drop column
ALTER TABLE users DROP COLUMN old_field;
```

**Renaming a column** (most dangerous):
```sql
-- Bad: Direct rename breaks application
ALTER TABLE users RENAME COLUMN name TO full_name;

-- Good: Phased approach
-- 1. Add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(100);
-- 2. Deploy app to write to both
-- 3. Backfill
UPDATE users SET full_name = name WHERE full_name IS NULL;
-- 4. Deploy app to read from new
-- 5. Deploy app to stop writing old
-- 6. Drop old column
ALTER TABLE users DROP COLUMN name;
```

**MySQL-specific tools**:
- `pt-online-schema-change` (Percona)
- `gh-ost` (GitHub)

**PostgreSQL**: Most ALTERs are online, but some require exclusive lock.

---

### Q: How do I handle database upgrades?

**Major version upgrade strategy**:

**1. Blue-Green deployment**:
```
1. Build new cluster on new version
2. Set up replication from old to new
3. Test thoroughly on new
4. Cut over traffic
5. Decommission old

Pros: Easy rollback, thorough testing
Cons: Double infrastructure cost temporarily
```

**2. Rolling upgrade** (for clusters):
```
1. Upgrade replicas one by one
2. Failover to upgraded replica
3. Upgrade old primary
4. Add back as replica

Pros: No double infra
Cons: Mixed versions during upgrade, riskier
```

**Pre-upgrade checklist**:
```
[ ] Read release notes for breaking changes
[ ] Test on staging with production-like data
[ ] Verify replication compatibility
[ ] Test application compatibility
[ ] Prepare rollback plan
[ ] Schedule maintenance window (if needed)
[ ] Have database team on standby
```

---

### Q: What should I monitor for database health?

**Essential metrics**:

| Category | Metrics | Alert Thresholds |
|----------|---------|------------------|
| **Availability** | Up/down, connection success | Down > 30s |
| **Performance** | Query latency p50/p95/p99 | p99 > 2x baseline |
| **Throughput** | QPS, transactions/sec | Sudden drops |
| **Replication** | Lag seconds, replication state | Lag > 30s |
| **Resources** | CPU, memory, disk, connections | >80% sustained |
| **Errors** | Error rate, deadlocks, timeouts | Any increase |
| **Capacity** | Disk usage, row counts | >70% capacity |

**Query-level monitoring**:
```sql
-- Slow queries (MySQL)
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;

-- Active queries (PostgreSQL)
SELECT * FROM pg_stat_activity WHERE state = 'active';

-- Lock waits
SELECT * FROM information_schema.innodb_lock_waits;
```

**Dashboards to build**:
1. Overview: Availability, latency, throughput
2. Replication: Lag per replica, replication state
3. Resources: CPU, memory, disk, connections
4. Slow queries: Top 10 by time, frequency
5. Errors: Error types, trends

---

## 8. Migration & Evolution

### Q: How do I migrate from one database to another?

**Migration approaches**:

**1. Dual-write migration**:
```
Phase 1: Application writes to both DBs
Phase 2: Verify data consistency
Phase 3: Switch reads to new DB
Phase 4: Remove writes to old DB
Phase 5: Decommission old DB

Duration: Weeks
Risk: Data drift, complexity
Best for: Critical systems needing verification
```

**2. CDC (Change Data Capture)**:
```
1. Initial bulk load to new DB
2. Set up CDC (Debezium, DMS) to capture changes
3. Apply changes to new DB continuously
4. When caught up, switch over

Duration: Days to weeks
Risk: CDC lag, transformation errors
Best for: Large datasets, minimal application changes
```

**3. Strangler fig pattern**:
```
1. New features use new DB
2. Gradually migrate old features
3. Eventually all traffic on new DB
4. Decommission old

Duration: Months
Risk: Maintaining two systems
Best for: Monolith to microservices
```

**Validation strategy**:
```python
def validate_migration():
    for entity in sample_entities(10000):
        old = old_db.get(entity.id)
        new = new_db.get(entity.id)
        if not equivalent(old, new):
            log_discrepancy(entity.id, old, new)
    
    # Run continuously during migration
    # Alert on discrepancy rate > threshold
```

---

### Q: When should I consider switching databases?

**Valid reasons to switch**:
| Signal | From | To |
|--------|------|-----|
| Hit scaling ceiling | PostgreSQL | CockroachDB, Cassandra |
| Need strong consistency + scale | Cassandra | Spanner, CockroachDB |
| Simplify operations | Self-managed | Managed (RDS, Cloud SQL) |
| Reduce cost | DynamoDB | Self-managed Cassandra |
| Need SQL flexibility | DynamoDB | PostgreSQL, MySQL |
| Need time-series features | PostgreSQL | TimescaleDB, InfluxDB |

**Invalid reasons to switch**:
```
❌ "X is trending" — technology hype
❌ "Our queries are slow" — optimize first
❌ "It's too expensive" — often misattributed to DB vs application
❌ "Engineers want to learn Y" — training cost > migration cost
```

**Migration decision framework**:
```
1. Can you solve the problem with current DB? (tuning, scaling)
2. Is the pain severe enough to justify migration cost?
3. Do you have the expertise for the new system?
4. Is there a clear path from A to B?
5. What's the rollback plan if migration fails?
```

---

## 9. Cost & Capacity Planning

### Q: How do I estimate database capacity needs?

**Sizing formula**:

**Storage**:
```
Storage = (rows × avg_row_size) × (1 + index_overhead) × replication_factor × growth_buffer

Example:
- 100M users × 2KB/user = 200GB
- Indexes: 200GB × 1.5 = 300GB
- 3 replicas: 300GB × 3 = 900GB
- 2-year growth: 900GB × 3 = 2.7TB
```

**IOPS**:
```
IOPS = (reads/sec × read_multiplier) + (writes/sec × write_multiplier)

Read multiplier: 1 (cached) to 5 (cold)
Write multiplier: 2-10 (depending on indexes)

Example:
- 10K reads/sec × 2 = 20K read IOPS
- 1K writes/sec × 5 = 5K write IOPS
- Total: 25K IOPS
```

**Connections**:
```
Connections = app_instances × connections_per_instance × safety_factor

Example:
- 20 app servers × 10 connections × 1.5 = 300 connections
```

**Memory**:
```
Memory = working_set_size + (connections × memory_per_connection) + buffer

Working set: Frequently accessed data (often 10-20% of total)
```

---

### Q: How do I reduce database costs?

**Quick wins**:
| Action | Savings | Effort |
|--------|---------|--------|
| Right-size instances | 20-50% | Low |
| Reserved instances (AWS) | 30-60% | Low |
| Delete unused indexes | 10-20% storage | Medium |
| Archive old data | 50%+ storage | Medium |
| Add caching layer | 30-50% reads | Medium |

**Medium-term optimizations**:
| Action | Savings | Effort |
|--------|---------|--------|
| Query optimization | Reduces CPU/IOPS | Medium |
| Connection pooling | Smaller instances | Medium |
| Read replicas for reports | Reduce primary size | Medium |
| Storage tiering | 50%+ on cold data | High |

**Long-term strategies**:
| Action | Savings | Effort |
|--------|---------|--------|
| Self-managed vs managed | 30-50% | High |
| Different database type | Variable | Very High |
| Multi-tenancy redesign | 40-60% | Very High |

---

## 10. Decision Framework

### Q: Quick reference — which database for which use case?

| Use Case | Primary Choice | Alternative | Avoid |
|----------|---------------|-------------|-------|
| General OLTP | PostgreSQL | MySQL | NoSQL without need |
| High-write throughput | Cassandra | ScyllaDB | Single-node SQL |
| Global strong consistency | Spanner | CockroachDB | Async-replicated SQL |
| Document store | MongoDB | PostgreSQL JSONB | Relational-first design |
| Caching | Redis | Memcached | Database for cache |
| Time-series metrics | InfluxDB, VictoriaMetrics | TimescaleDB | Generic SQL |
| Analytics | ClickHouse, BigQuery | Redshift | OLTP databases |
| Search | Elasticsearch | PostgreSQL FTS | Relational for search |
| Graph queries | Neo4j | Neptune | SQL for graphs |
| Serverless/managed | DynamoDB | Fauna | Self-managed for small scale |
| IoT high cardinality | TimescaleDB | InfluxDB | Generic NoSQL |

### Q: Decision flowchart for new projects

```
START
  │
  ▼
Do you need ACID transactions?
  │
  ├─Yes──▶ Do you need horizontal scaling?
  │           │
  │           ├─Yes──▶ Global distribution needed?
  │           │           │
  │           │           ├─Yes──▶ Spanner / CockroachDB
  │           │           └─No───▶ Vitess / Citus
  │           │
  │           └─No───▶ PostgreSQL / MySQL
  │
  └─No───▶ Is it time-series data?
              │
              ├─Yes──▶ InfluxDB / TimescaleDB
              │
              └─No───▶ Is write throughput critical?
                          │
                          ├─Yes──▶ Cassandra / ScyllaDB
                          │
                          └─No───▶ What's the data model?
                                      │
                                      ├─Documents──▶ MongoDB
                                      ├─Key-Value──▶ Redis / DynamoDB
                                      └─Graph──────▶ Neo4j
```

---

## Summary: Top 10 Rules for Database Reliability

1. **Test your backups** — A backup that can't be restored isn't a backup

2. **Monitor replication lag** — Most "database down" incidents are actually replication issues

3. **Plan for failure** — Design assuming your primary will fail tonight

4. **Over-shard early** — 256 shards is easier than re-sharding from 4 to 16

5. **Consistency requirements vary** — Not all data needs strong consistency

6. **Idempotency everywhere** — Retries are inevitable, make them safe

7. **Connection pooling always** — Every production database needs a pooler

8. **Capacity plan at 50%, act at 70%** — Don't wait for emergencies

9. **Schema changes in phases** — Expand, migrate, contract — never big bang

10. **The database is usually not the bottleneck** — Profile before blaming the DB

---

## Quick Troubleshooting Reference

| Symptom | Likely Cause | First Action |
|---------|--------------|--------------|
| High latency | Missing index, lock contention | Check slow query log |
| Connection refused | Max connections, firewall | Check connection count |
| Replication stopped | Network, disk full, conflict | Check replication status |
| Disk full | Logs, temp files, bloat | Identify largest consumers |
| High CPU | Bad query, compaction, vacuum | Identify top queries |
| OOM | Working set > RAM, connection leak | Check memory breakdown |
| Timeouts | Lock waits, network | Check active queries |
| Data inconsistency | Replication lag, bug | Compare source of truth |
