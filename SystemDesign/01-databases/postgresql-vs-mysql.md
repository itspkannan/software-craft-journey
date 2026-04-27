# PostgreSQL vs MySQL

## 1. Concept Overview

**What this comparison is about**: Choosing between the two most popular open-source relational databases for production workloads.

**Why it matters**: Wrong choice leads to painful migrations later. Both are excellent, but optimized for different use cases.

**Quick decision framework**:
- **MySQL**: Simpler operations, better replication tooling, proven at extreme scale (Meta, Uber)
- **PostgreSQL**: Richer SQL features, better for complex queries, extensibility (JSON, GIS, full-text)

---

## 2. Real-World Case Studies

### Uber: PostgreSQL → MySQL Migration

**Problem**: PostgreSQL replication couldn't handle Uber's write-heavy workload and geographic distribution.

**Issues encountered**:
- Replication used WAL shipping (entire WAL segments)
- Replica promotion required downtime
- Write amplification during updates (MVCC full row rewrites)

**Solution**: Migrated to MySQL with InnoDB
- Row-based replication (binlog) more efficient
- Better tooling for failover (Orchestrator)
- Simpler operational model at scale

**Source**: Uber Engineering — "Why Uber Engineering Switched from Postgres to MySQL"

### Instagram: PostgreSQL Success

**Problem**: Needed to store billions of photos with complex querying.

**Why PostgreSQL worked**:
- Rich indexing (partial indexes, expression indexes)
- JSONB for flexible metadata
- Strong consistency for social features

**Source**: Instagram Engineering Blog

---

## 3. Head-to-Head Comparison

| Dimension | MySQL | PostgreSQL |
|-----------|-------|------------|
| **SQL Compliance** | Partial (improving) | Full ANSI SQL |
| **ACID** | Yes (InnoDB) | Yes |
| **JSON Support** | JSON type (basic) | JSONB (indexed, fast) |
| **Full-Text Search** | Basic | Advanced (tsvector) |
| **Replication** | Row-based binlog | WAL-based (logical available) |
| **Failover Tooling** | Orchestrator, ProxySQL, Vitess | Patroni, pg_auto_failover |
| **Sharding** | Vitess, ProxySQL | Citus, manual |
| **Extensions** | Limited | Rich (PostGIS, pg_trgm, etc.) |
| **MVCC Implementation** | In-row versioning | Separate tuple versions |
| **Vacuum/Maintenance** | Minimal | Required (autovacuum) |
| **Connection Model** | Thread per connection | Process per connection |
| **Max Connections** | Higher (threads) | Lower (processes) |
| **Learning Curve** | Easier | Steeper |
| **Community** | Oracle-backed | Community-driven |

---

## 4. When to Choose Each

### Choose MySQL When

1. **Extreme scale with simple queries**
   - Read-heavy workloads
   - High connection counts (10K+)
   - Need battle-tested sharding (Vitess)

2. **Simpler operational model**
   - Team has MySQL expertise
   - Want mature failover tooling
   - Less maintenance overhead (no vacuum)

3. **Replication is critical**
   - Multi-region deployments
   - Read replica scaling
   - Low-latency replication needed

### Choose PostgreSQL When

1. **Complex queries and data types**
   - Analytics mixed with OLTP
   - Geospatial data (PostGIS)
   - Full-text search without Elasticsearch

2. **Schema flexibility needed**
   - JSONB for semi-structured data
   - Array types
   - Custom types and domains

3. **Data integrity is paramount**
   - Strict constraint enforcement
   - Complex foreign key relationships
   - Need CTEs, window functions, lateral joins

4. **Extensibility matters**
   - Custom functions (PL/pgSQL, PL/Python)
   - Extensions ecosystem
   - Foreign data wrappers

---

## 5. Performance Characteristics

### Write Performance

| Scenario | MySQL | PostgreSQL |
|----------|-------|------------|
| Simple INSERTs | Faster | Slightly slower |
| UPDATE (change 1 column) | Faster (in-place) | Slower (new tuple) |
| Bulk INSERT | Comparable | Comparable |
| High concurrency writes | Better | HOT helps, but vacuum overhead |

**Why MySQL wins on updates**: InnoDB updates in place. PostgreSQL creates new tuple version, requiring vacuum later.

### Read Performance

| Scenario | MySQL | PostgreSQL |
|----------|-------|------------|
| Simple SELECT by PK | Comparable | Comparable |
| Complex JOINs | Slower | Faster (better planner) |
| Aggregations | Basic | Better (parallel query) |
| Full-text search | Basic | Much better |

### Connection Overhead

```
MySQL:    ~256KB per connection (thread)
PostgreSQL: ~5-10MB per connection (process)
```

**Implication**: MySQL handles more concurrent connections natively. PostgreSQL needs PgBouncer for connection pooling at scale.

---

## 6. Replication Comparison

### MySQL Replication

```
Primary ──binlog──▶ Replica
         (row-based)
```

- **Format**: Row-based (default), statement-based, mixed
- **Latency**: Sub-second typically
- **Failover**: Orchestrator auto-promotes replica
- **Strengths**: Simple, battle-tested, GTID for tracking

### PostgreSQL Replication

```
Primary ──WAL──▶ Replica
        (streaming)
```

- **Format**: Physical (WAL shipping) or Logical
- **Latency**: Sub-second with streaming
- **Failover**: Patroni, pg_auto_failover
- **Strengths**: Logical replication for selective sync

### Key Differences

| Aspect | MySQL | PostgreSQL |
|--------|-------|------------|
| Replica reads during replication | Yes | Yes |
| Replica can have different indexes | No (physical) | Yes (logical) |
| Cross-version replication | Limited | Yes (logical) |
| Replication lag visibility | `SHOW SLAVE STATUS` | `pg_stat_replication` |

---

## 7. Scaling Patterns

### MySQL Scaling

```
                    ┌─────────────┐
                    │   Vitess    │
                    │  (Proxy)    │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐     ┌─────────┐     ┌─────────┐
      │ Shard 0 │     │ Shard 1 │     │ Shard N │
      │ Primary │     │ Primary │     │ Primary │
      │ Replica │     │ Replica │     │ Replica │
      └─────────┘     └─────────┘     └─────────┘
```

- **Tool**: Vitess (YouTube, Slack, Square)
- **Sharding**: Application-transparent
- **Cross-shard**: Scatter-gather queries supported

### PostgreSQL Scaling

```
                    ┌─────────────┐
                    │   Citus    │
                    │ Coordinator │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐     ┌─────────┐     ┌─────────┐
      │ Worker  │     │ Worker  │     │ Worker  │
      │  Node   │     │  Node   │     │  Node   │
      └─────────┘     └─────────┘     └─────────┘
```

- **Tool**: Citus (Microsoft), manual sharding
- **Sharding**: Distributed tables, reference tables
- **Cross-shard**: Parallel query execution

---

## 8. Reliability & HA

### MySQL HA Stack

| Component | Purpose |
|-----------|---------|
| Orchestrator | Topology management, auto-failover |
| ProxySQL | Connection pooling, query routing |
| Vitess | Sharding + HA + pooling |
| Semi-sync replication | Durability guarantee |

**Failover time**: 10-30 seconds with Orchestrator

### PostgreSQL HA Stack

| Component | Purpose |
|-----------|---------|
| Patroni | Consensus-based leader election |
| PgBouncer | Connection pooling |
| HAProxy | Load balancing |
| Synchronous replication | Durability guarantee |

**Failover time**: 10-30 seconds with Patroni

---

## 9. Interview Answer — Authority Mode

**Question**: "When would you choose PostgreSQL over MySQL?"

**Answer**:

Choose PostgreSQL when:
- **Complex queries** — superior query planner, CTEs, window functions, lateral joins
- **Data type flexibility** — JSONB with indexing, arrays, custom types, PostGIS for geospatial
- **Extensibility** — rich extension ecosystem, custom functions, foreign data wrappers
- **Analytics workloads** — parallel query execution, better aggregation performance

Choose MySQL when:
- **Extreme scale with simple queries** — proven at Meta/Uber scale with Vitess
- **High connection counts** — thread-per-connection vs PostgreSQL's process model
- **Simpler operations** — no vacuum, mature failover tooling
- **Write-heavy OLTP** — in-place updates, less write amplification

**Trade-off acknowledged**: PostgreSQL's MVCC creates vacuum overhead; MySQL's simpler model wins on pure OLTP. But PostgreSQL's query capabilities make it better for mixed workloads.

---

## 10. FAQ

**Q: Can PostgreSQL handle Meta-scale?**
Not easily with current tooling. Citus helps but isn't as mature as Vitess. PostgreSQL excels at medium-to-large scale with complex queries rather than extreme scale with simple queries.

**Q: Is MySQL's query planner really worse?**
For simple queries, no difference. For complex JOINs and subqueries, PostgreSQL's planner is significantly better. MySQL has improved (8.0+) but still lags.

**Q: Should I use PgBouncer with PostgreSQL?**
Yes, always in production. PostgreSQL's process-per-connection model doesn't scale without pooling.

**Q: What about MySQL 8.0 improvements?**
MySQL 8.0 added CTEs, window functions, and JSON improvements. Gap is narrowing, but PostgreSQL still leads in SQL completeness.

**Q: Which has better cloud support?**
Both have excellent managed options (RDS, Cloud SQL, Aurora, AlloyDB). Aurora MySQL and AlloyDB (PostgreSQL-compatible) offer additional scaling.

---

## Key Terms

| Term | Definition |
|------|------------|
| MVCC | Multi-Version Concurrency Control — how both handle concurrent access |
| WAL | Write-Ahead Log — PostgreSQL's durability and replication mechanism |
| Binlog | Binary Log — MySQL's change log for replication |
| Vacuum | PostgreSQL process to reclaim space from dead tuples |
| HOT | Heap-Only Tuples — PostgreSQL optimization avoiding index updates |
| GTID | Global Transaction ID — MySQL's replication tracking |
