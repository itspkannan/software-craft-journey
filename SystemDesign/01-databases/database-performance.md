# Database Performance Tuning

## 1. Concept Overview

**What this covers**: Techniques for optimizing database read and write performance across SQL and NoSQL systems.

**Why it matters**: Database performance is often the bottleneck. A 10ms query optimization can save millions at scale.

**Performance optimization layers**:
1. Query optimization (biggest impact, lowest cost)
2. Indexing strategy
3. Schema design
4. Configuration tuning
5. Hardware/infrastructure

---

## 2. Query Optimization

### The Explain Plan

**MySQL**:
```sql
EXPLAIN ANALYZE SELECT * FROM orders 
WHERE user_id = 123 AND status = 'pending';

-- Key things to look for:
-- type: ALL (bad) vs ref/eq_ref (good)
-- rows: How many rows examined
-- Extra: Using filesort, Using temporary (bad)
```

**PostgreSQL**:
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) 
SELECT * FROM orders WHERE user_id = 123;

-- Key things to look for:
-- Seq Scan (bad for large tables)
-- Index Scan (good)
-- Actual time vs Planning time
-- Buffers: shared hit (cache) vs read (disk)
```

### Common Query Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| SELECT * | Retrieves unnecessary columns | Select only needed columns |
| OR conditions | Often prevents index use | UNION of separate queries |
| LIKE '%prefix%' | Can't use index | Full-text search or reverse index |
| Functions on indexed columns | WHERE YEAR(date) = 2024 | WHERE date >= '2024-01-01' |
| Implicit type conversion | String vs int comparison | Match types explicitly |
| N+1 queries | Loop with query per item | JOIN or batch query |

### Query Optimization Techniques

**1. Use covering indexes**:
```sql
-- Query
SELECT user_id, email FROM users WHERE status = 'active';

-- Covering index (no table lookup needed)
CREATE INDEX idx_status_covering ON users(status) INCLUDE (user_id, email);
```

**2. Optimize JOINs**:
```sql
-- Ensure join columns are indexed
-- Smaller table should drive the join
-- Use EXPLAIN to verify join order

SELECT o.*, u.name 
FROM orders o
JOIN users u ON o.user_id = u.id  -- u.id should be indexed (PK)
WHERE o.created_at > '2024-01-01';
```

**3. Pagination done right**:
```sql
-- Bad: OFFSET scales poorly
SELECT * FROM items ORDER BY id LIMIT 20 OFFSET 10000;

-- Good: Keyset pagination
SELECT * FROM items 
WHERE id > 10000  -- last seen id
ORDER BY id LIMIT 20;
```

---

## 3. Indexing Strategy

### Index Types

| Type | Use Case | Example |
|------|----------|---------|
| B-Tree | Equality, range queries | Most common default |
| Hash | Equality only | Redis, Memcached |
| GiST | Geometric, full-text | PostGIS, pg_trgm |
| GIN | Arrays, JSONB, full-text | PostgreSQL JSONB |
| Bitmap | Low cardinality, analytics | Oracle, PostgreSQL |

### Index Design Principles

**1. Selectivity matters**:
```sql
-- High selectivity (good for index)
SELECT * FROM users WHERE email = 'x@y.com';  -- unique

-- Low selectivity (index less useful)
SELECT * FROM users WHERE gender = 'M';  -- 50% of rows
```

**2. Column order in composite indexes**:
```sql
-- Query pattern
WHERE status = 'active' AND created_at > '2024-01-01'

-- Index column order: equality columns first, then range
CREATE INDEX idx_status_created ON orders(status, created_at);
```

**3. Index-only scans**:
```sql
-- If index contains all needed columns, no table access needed
CREATE INDEX idx_covering ON orders(user_id, status, total);
SELECT status, total FROM orders WHERE user_id = 123;
-- ↑ Can be satisfied entirely from index
```

### When NOT to Index

| Scenario | Why |
|----------|-----|
| Small tables (<1000 rows) | Full scan is fast |
| Columns rarely in WHERE | Index maintenance cost > benefit |
| High write, low read | Index updates slow writes |
| Low selectivity columns | Gender, boolean flags |
| Frequently updated columns | Index reorganization overhead |

---

## 4. Schema Design for Performance

### Normalization vs Denormalization

| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| Normalized | Less redundancy, easier updates | JOIN overhead | OLTP, data integrity critical |
| Denormalized | Faster reads, fewer JOINs | Update anomalies, storage | Read-heavy, known queries |

### Partitioning

**Horizontal Partitioning (Sharding)**:
```sql
-- By range (time-based)
CREATE TABLE orders_2024_01 PARTITION OF orders
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- By hash (even distribution)
CREATE TABLE orders PARTITION BY HASH(user_id);
```

**When to partition**:
- Table > 100GB
- Clear partition key (time, tenant)
- Queries naturally filter on partition key
- Need to drop old data efficiently

### Data Types

| Principle | Example |
|-----------|---------|
| Use smallest sufficient type | TINYINT vs INT vs BIGINT |
| Avoid TEXT for indexed columns | VARCHAR(255) instead |
| Use native types | TIMESTAMP vs VARCHAR for dates |
| Consider compression | JSON vs JSONB (binary) |

---

## 5. Connection Management

### Connection Pooling

```
Without pooling:                 With pooling:
┌────────┐                      ┌────────┐
│ App 1  │──conn──┐             │ App 1  │──┐
├────────┤        │             ├────────┤  │
│ App 2  │──conn──┼──▶ DB      │ App 2  │──┼──▶ Pool ──▶ DB
├────────┤        │             ├────────┤  │     (10 conns)
│ App N  │──conn──┘             │ App N  │──┘
└────────┘                      └────────┘
N connections                   10 connections (shared)
```

### Pool Sizing

**Formula (PostgreSQL)**:
```
connections = (core_count * 2) + effective_spindle_count
```

**General guidance**:
| Workload | Pool Size |
|----------|-----------|
| OLTP (short queries) | 10-20 per app instance |
| Reporting (long queries) | 2-5 per app instance |
| Mixed | Separate pools for each |

### Pooling Tools

| Database | Tools |
|----------|-------|
| PostgreSQL | PgBouncer, pgpool-II |
| MySQL | ProxySQL, MySQL Router |
| Application | HikariCP (Java), SQLAlchemy pool |

---

## 6. Caching Strategies

### Cache Levels

```
┌─────────────────────────────────────────────────────────┐
│                     Application                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              L1: In-Process Cache                  │ │
│  │              (Guava, Caffeine)                     │ │
│  │              ~microseconds                         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               L2: Distributed Cache                      │
│               (Redis, Memcached)                         │
│               ~milliseconds                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               L3: Database Cache                         │
│               (Buffer pool, query cache)                 │
│               ~milliseconds                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     Disk                                 │
│                     ~10+ milliseconds                    │
└─────────────────────────────────────────────────────────┘
```

### Caching Patterns

| Pattern | How It Works | Use When |
|---------|--------------|----------|
| Cache-aside | App checks cache, then DB | General purpose |
| Read-through | Cache fetches from DB on miss | Simpler app code |
| Write-through | Write to cache and DB together | Consistency important |
| Write-behind | Write to cache, async to DB | Write-heavy |

### Cache Invalidation

| Strategy | Pros | Cons |
|----------|------|------|
| TTL-based | Simple, automatic | May serve stale |
| Event-driven | Real-time accuracy | Complex |
| Version-based | Atomic updates | Cache key management |

---

## 7. NoSQL Performance

### Cassandra Performance

**Partition design**:
```sql
-- Bad: Large partitions
PRIMARY KEY (user_id)  -- all user data in one partition

-- Good: Bounded partitions
PRIMARY KEY ((user_id, month), timestamp)  -- monthly buckets
```

**Read optimization**:
- Use partition key in all queries
- Avoid ALLOW FILTERING
- Use appropriate consistency level

### DynamoDB Performance

**Capacity planning**:
```
Hot partition symptoms:
- ProvisionedThroughputExceededException
- Throttling despite available capacity

Solutions:
- Distribute partition keys
- Use write sharding
- Consider on-demand mode
```

### MongoDB Performance

**Index optimization**:
```javascript
// Covered query (index-only)
db.orders.createIndex({ user_id: 1, status: 1, total: 1 });
db.orders.find(
  { user_id: 123 },
  { status: 1, total: 1, _id: 0 }  // projection matches index
);
```

---

## 8. Configuration Tuning

### MySQL/InnoDB

| Parameter | Default | Tuning Guidance |
|-----------|---------|-----------------|
| innodb_buffer_pool_size | 128MB | 70-80% of RAM (dedicated server) |
| innodb_log_file_size | 48MB | 1-2GB for write-heavy |
| innodb_flush_log_at_trx_commit | 1 | 2 for performance (less durable) |
| max_connections | 151 | Based on pool size needs |

### PostgreSQL

| Parameter | Default | Tuning Guidance |
|-----------|---------|-----------------|
| shared_buffers | 128MB | 25% of RAM |
| effective_cache_size | 4GB | 50-75% of RAM |
| work_mem | 4MB | Increase for complex queries |
| maintenance_work_mem | 64MB | Higher for vacuum/index creation |
| random_page_cost | 4.0 | 1.1-1.5 for SSD |

### Redis

| Parameter | Default | Tuning Guidance |
|-----------|---------|-----------------|
| maxmemory | 0 (unlimited) | Set to available RAM - 2GB |
| maxmemory-policy | noeviction | allkeys-lru for cache |
| tcp-keepalive | 300 | Lower for faster dead connection detection |

---

## 9. Interview Answer — Authority Mode

**Question**: "How do you optimize database performance?"

**Answer**:

**Query level** (biggest impact):
- Analyze explain plans — eliminate full table scans
- Fix N+1 queries with JOINs or batching
- Use keyset pagination instead of OFFSET

**Indexing**:
- Create indexes for WHERE, JOIN, ORDER BY columns
- Composite indexes: equality columns first, then range
- Use covering indexes for frequently run queries

**Schema design**:
- Denormalize for read-heavy workloads
- Partition large tables by time or tenant
- Choose appropriate data types (smallest sufficient)

**Infrastructure**:
- Connection pooling (PgBouncer, HikariCP)
- Read replicas for read scaling
- Caching layer (Redis) for hot data

**Configuration**:
- Buffer pool sized to RAM (70-80%)
- Connection limits matching pool sizes
- I/O settings tuned for SSD

**Monitoring**:
- Track slow queries and optimize top 10
- Alert on query latency p99, connection saturation

**Trade-off**: Denormalization and caching improve reads but complicate writes and consistency. Choose based on read/write ratio.

---

## 10. FAQ

**Q: What's the first thing to optimize?**
Slow query log. Find the top 10 slowest queries by total time (frequency × duration). Optimize those first.

**Q: Should I index every column in WHERE clauses?**
No. Index high-selectivity columns that are frequently queried. Each index slows writes and uses storage.

**Q: How much should I increase buffer pool?**
For dedicated database servers: 70-80% of RAM for MySQL, 25% for PostgreSQL (plus OS cache). Test and monitor.

**Q: When is caching the answer vs query optimization?**
Optimize first. Caching adds complexity (invalidation, consistency). Cache only after queries are optimized and you still need more speed.

**Q: How do I handle slow queries in production?**
1. Add query timeout to prevent resource exhaustion
2. Kill long-running queries automatically
3. Add the query to slow log investigation queue
4. Consider read replicas for heavy reports

---

## Key Terms

| Term | Definition |
|------|------------|
| Explain plan | Query execution analysis showing access method, rows examined |
| Covering index | Index containing all columns needed by query |
| Selectivity | Ratio of distinct values to total rows |
| Buffer pool | In-memory cache for database pages |
| Connection pool | Pre-established database connections shared by app |
| N+1 query | Pattern where loop makes one query per item |
| Keyset pagination | Pagination using last-seen key instead of OFFSET |
