# Time-Series Databases

## 1. Concept Overview

**What time-series data is**: Data points indexed by time, typically arriving in chronological order with high write rates.

**Examples**:
- Infrastructure metrics (CPU, memory, network)
- Application metrics (latency, error rates, throughput)
- IoT sensor data (temperature, location, readings)
- Financial data (stock prices, trades)
- User analytics (page views, events)

**Why specialized databases**:
| Requirement | Generic DB Problem | TSDB Solution |
|-------------|-------------------|---------------|
| High write throughput | B-tree write amplification | LSM-tree, append-only |
| Time-based queries | Full index scan | Time-partitioned storage |
| Data compression | Row-based storage | Columnar, delta encoding |
| Retention | Manual cleanup | Automatic TTL/downsampling |
| Aggregations | Slow without pre-computation | Built-in rollups |

---

## 2. Real-World Case Studies

### Netflix — Operational Metrics

**Problem**: Monitor millions of metrics across global infrastructure.

**Solution**: Atlas (custom TSDB)

**Scale**:
- 2+ billion time series
- 1+ trillion data points per day
- Query latency <1 second for dashboards

**Why custom**: No existing TSDB met their dimensional data model and query needs.

### Uber — Real-Time Analytics

**Problem**: Track millions of trips, drivers, metrics in real-time.

**Solution**: M3 (built on top of Prometheus concepts)

**Scale**:
- Billions of metrics
- Sub-second query latency
- Global deployment

**Source**: Uber Engineering Blog — "M3: Uber's Open Source, Large-scale Metrics Platform"

### CloudFlare — Edge Metrics

**Problem**: Aggregate metrics from 200+ data centers.

**Solution**: ClickHouse for analytics, custom for real-time.

**Why ClickHouse**: Columnar storage, excellent compression, fast aggregations.

---

## 3. TSDB Landscape

### Major Options

| Database | Type | Best For | Scale |
|----------|------|----------|-------|
| InfluxDB | Purpose-built TSDB | Metrics, IoT | Medium |
| TimescaleDB | PostgreSQL extension | SQL + time-series | Medium-Large |
| Prometheus | Pull-based metrics | Kubernetes, cloud-native | Medium |
| ClickHouse | Columnar analytics | Analytics, logs | Very Large |
| QuestDB | High-performance | Financial, IoT | Large |
| VictoriaMetrics | Prometheus-compatible | Prometheus replacement | Large |

### Architecture Comparison

```
InfluxDB (TSM Engine):
┌─────────────────────────────────────────┐
│              Write Path                  │
│  Points → WAL → Cache → TSM Files       │
│                          (compressed)    │
└─────────────────────────────────────────┘

TimescaleDB (Hypertables):
┌─────────────────────────────────────────┐
│           Hypertable                     │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │Chunk│ │Chunk│ │Chunk│ │Chunk│       │
│  │Jan  │ │Feb  │ │Mar  │ │Apr  │       │
│  └─────┘ └─────┘ └─────┘ └─────┘       │
│  Auto-partitioned by time               │
└─────────────────────────────────────────┘

Prometheus:
┌─────────────────────────────────────────┐
│  Scraper → TSDB → Query Engine          │
│            │                             │
│       2-hour blocks → compaction         │
└─────────────────────────────────────────┘
```

---

## 4. Data Model

### InfluxDB Data Model

```
Measurement: cpu
Tags: host=server01, region=us-east (indexed)
Fields: usage_user=23.5, usage_system=12.1 (not indexed)
Timestamp: 2024-01-15T10:30:00Z

Line Protocol:
cpu,host=server01,region=us-east usage_user=23.5,usage_system=12.1 1705315800000000000
```

### Prometheus Data Model

```
Metric name + labels:
http_requests_total{method="GET", status="200", path="/api"} 1234

Time series = unique combination of metric name + labels
```

### TimescaleDB Data Model

```sql
-- Regular SQL table with time column
CREATE TABLE metrics (
    time        TIMESTAMPTZ NOT NULL,
    host        TEXT NOT NULL,
    cpu_usage   DOUBLE PRECISION,
    mem_usage   DOUBLE PRECISION
);

-- Convert to hypertable (auto-partitioned)
SELECT create_hypertable('metrics', 'time');

-- Query with standard SQL
SELECT time_bucket('5 minutes', time) AS bucket,
       host,
       AVG(cpu_usage) AS avg_cpu
FROM metrics
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY bucket, host
ORDER BY bucket DESC;
```

### ClickHouse Data Model

```sql
CREATE TABLE metrics (
    timestamp DateTime,
    host String,
    metric_name String,
    value Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (metric_name, host, timestamp);
```

---

## 5. Write Optimization

### Why Time-Series Writes Are Different

```
Traditional OLTP:
- Random writes across rows
- B-tree index updates
- Row-level locking

Time-Series:
- Sequential writes (time-ordered)
- Append-mostly (rarely update)
- Bulk inserts common
```

### LSM-Tree Architecture (InfluxDB, Cassandra)

```
Write Path:
┌────────────┐
│   Write    │
└─────┬──────┘
      ▼
┌────────────┐
│    WAL     │  (durability)
└─────┬──────┘
      ▼
┌────────────┐
│  MemTable  │  (in-memory, sorted)
└─────┬──────┘
      ▼ (flush when full)
┌────────────┐
│  SSTable   │  (immutable, on disk)
└─────┬──────┘
      ▼ (background)
┌────────────┐
│ Compaction │  (merge SSTables)
└────────────┘

Benefits:
- Sequential writes (fast)
- No in-place updates (append-only)
- Good compression (sorted data)
```

### Batching and Buffering

```python
# Bad: Single point writes
for point in points:
    client.write(point)  # Network round-trip each time

# Good: Batch writes
batch = []
for point in points:
    batch.append(point)
    if len(batch) >= 5000:
        client.write_batch(batch)
        batch = []
```

### Compression Techniques

| Technique | Used For | Compression Ratio |
|-----------|----------|-------------------|
| Delta encoding | Timestamps | 10-100x |
| Delta-of-delta | Timestamps | 100-1000x |
| XOR encoding | Float values | 10-20x |
| Dictionary | Tags/labels | 5-10x |
| Run-length | Repeated values | Variable |

```
Raw timestamps: 1705315800, 1705315810, 1705315820, 1705315830
Delta:          1705315800, 10, 10, 10
Delta-of-delta: 1705315800, 10, 0, 0

Storage: 4 bytes vs 32 bytes (8x compression just for timestamps)
```

---

## 6. Query Patterns

### Common Time-Series Queries

```sql
-- Last value
SELECT last(value) FROM metrics WHERE host = 'server01'

-- Aggregation over time window
SELECT time_bucket('5 min', time) AS bucket,
       AVG(value), MAX(value), MIN(value)
FROM metrics
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY bucket

-- Top N
SELECT host, AVG(cpu) 
FROM metrics
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY host
ORDER BY AVG(cpu) DESC
LIMIT 10

-- Percentiles
SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency)
FROM requests
WHERE time > NOW() - INTERVAL '1 hour'
```

### PromQL Examples (Prometheus)

```promql
# Current value
http_requests_total{job="api"}

# Rate over 5 minutes
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Top 5 by memory
topk(5, container_memory_usage_bytes)

# Alerts
http_requests_total{status="500"} > 100
```

### InfluxQL / Flux Examples

```sql
-- InfluxQL
SELECT MEAN("cpu_usage") 
FROM "metrics" 
WHERE time > now() - 1h 
GROUP BY time(5m), "host"

-- Flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> aggregateWindow(every: 5m, fn: mean)
```

---

## 7. Retention and Downsampling

### Retention Policies

```sql
-- InfluxDB
CREATE RETENTION POLICY "one_week" ON "mydb" 
  DURATION 7d REPLICATION 1

CREATE RETENTION POLICY "one_year" ON "mydb"
  DURATION 365d REPLICATION 1

-- TimescaleDB
SELECT add_retention_policy('metrics', INTERVAL '30 days');
```

### Downsampling (Rollups)

```
Raw data (1 second):     10:00:00  10:00:01  10:00:02  ...
                         23.5      24.1      23.8

5-minute rollup:         10:00:00 - 10:05:00
                         avg=23.8, min=22.1, max=25.3, count=300

1-hour rollup:           10:00:00 - 11:00:00
                         avg=24.2, min=20.5, max=28.7, count=3600
```

**Continuous Aggregates (TimescaleDB)**:
```sql
CREATE MATERIALIZED VIEW metrics_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       host,
       AVG(cpu_usage) AS avg_cpu,
       MAX(cpu_usage) AS max_cpu
FROM metrics
GROUP BY bucket, host;

-- Automatically refreshed as new data arrives
```

### Storage Tiering

```
┌─────────────────────────────────────────────────────────┐
│                   Storage Tiers                          │
│                                                          │
│  Hot (0-7 days):    Raw data, fast SSD                  │
│  Warm (7-30 days):  5-min rollups, slower storage       │
│  Cold (30+ days):   1-hour rollups, object storage      │
│  Archive:           Daily rollups, Glacier              │
│                                                          │
│  Query routing based on time range                       │
└─────────────────────────────────────────────────────────┘
```

---

## 8. High Availability

### InfluxDB Clustering (Enterprise)

```
┌─────────────────────────────────────────────────────────┐
│                 InfluxDB Enterprise                      │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Meta Node  │  │  Meta Node  │  │  Meta Node  │     │
│  │  (Raft)     │  │  (Raft)     │  │  (Raft)     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Data Node  │  │  Data Node  │  │  Data Node  │     │
│  │  (writes)   │  │  (writes)   │  │  (writes)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                          │
│  Replication factor: 2 or 3                             │
└─────────────────────────────────────────────────────────┘
```

### Prometheus HA + Thanos

```
┌─────────────────────────────────────────────────────────┐
│                  Prometheus + Thanos                     │
│                                                          │
│  ┌────────────┐   ┌────────────┐                        │
│  │Prometheus A│   │Prometheus B│  (scrape same targets) │
│  │  + Sidecar │   │  + Sidecar │                        │
│  └─────┬──────┘   └─────┬──────┘                        │
│        │                │                                │
│        └────────┬───────┘                                │
│                 ▼                                        │
│        ┌────────────────┐                               │
│        │  Thanos Query  │  (deduplicates)               │
│        └────────────────┘                               │
│                 │                                        │
│                 ▼                                        │
│        ┌────────────────┐                               │
│        │  Object Store  │  (long-term, S3/GCS)          │
│        └────────────────┘                               │
└─────────────────────────────────────────────────────────┘
```

### VictoriaMetrics Cluster

```
┌─────────────────────────────────────────────────────────┐
│              VictoriaMetrics Cluster                     │
│                                                          │
│  ┌──────────────┐                                       │
│  │  vminsert    │  (stateless, horizontal scaling)      │
│  │  vminsert    │                                       │
│  └──────┬───────┘                                       │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                       │
│  │  vmstorage   │  (sharded by time + series)           │
│  │  vmstorage   │                                       │
│  │  vmstorage   │                                       │
│  └──────┬───────┘                                       │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                       │
│  │  vmselect    │  (stateless, scatter-gather queries)  │
│  │  vmselect    │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 9. Choosing a TSDB

### Decision Matrix

| Requirement | Best Choice |
|-------------|-------------|
| Kubernetes metrics | Prometheus + Thanos |
| SQL interface needed | TimescaleDB |
| Highest write throughput | VictoriaMetrics, QuestDB |
| IoT / embedded | InfluxDB |
| Analytics + time-series | ClickHouse |
| Managed service | InfluxDB Cloud, Timescale Cloud |
| PostgreSQL ecosystem | TimescaleDB |
| Prometheus compatibility | VictoriaMetrics, Thanos, Cortex |

### Comparison Table

| Feature | InfluxDB | TimescaleDB | Prometheus | ClickHouse |
|---------|----------|-------------|------------|------------|
| Query language | InfluxQL/Flux | SQL | PromQL | SQL |
| Write throughput | High | High | Medium | Very High |
| Compression | Excellent | Good | Excellent | Excellent |
| Joins | Limited | Full SQL | No | Full SQL |
| Clustering | Enterprise | Yes (paid) | Via Thanos | Yes |
| Learning curve | Medium | Low (SQL) | Medium | Low (SQL) |

---

## 10. Interview Answer — Authority Mode

**Question**: "How would you design a metrics system for a large-scale application?"

**Answer**:

**Architecture**:
```
Apps → Metrics Agent → Kafka → TSDB → Grafana
              │
       (local buffer for resilience)
```

**TSDB selection based on scale**:
- <100K series: Prometheus (simple, battle-tested)
- 100K-10M series: VictoriaMetrics or InfluxDB
- >10M series: VictoriaMetrics cluster or ClickHouse

**Key design decisions**:

1. **Cardinality control** — limit unique tag combinations
   - Don't use high-cardinality values as tags (user IDs, request IDs)
   - Alerts on cardinality growth

2. **Retention tiers** — balance cost and query speed
   - Hot: 7 days raw data (fast storage)
   - Warm: 30 days 5-min rollups
   - Cold: 1 year hourly rollups (object storage)

3. **Write buffering** — handle spikes
   - Kafka or local queue between apps and TSDB
   - Prevents data loss during TSDB issues

4. **Query optimization** — pre-aggregate common queries
   - Continuous aggregates for dashboards
   - Recording rules for frequent PromQL

**Trade-offs**:
- Higher cardinality = more storage, slower queries
- Longer retention = higher cost
- More rollup levels = query complexity

---

## 11. FAQ

**Q: Prometheus vs InfluxDB?**
Prometheus: Better for Kubernetes, pull-based, simpler. InfluxDB: Push-based, better for IoT, more flexible data model.

**Q: When is ClickHouse better than a purpose-built TSDB?**
When you need complex SQL joins, analytics mixed with time-series, or have existing ClickHouse expertise. Pure metrics: purpose-built TSDB is simpler.

**Q: How to handle high cardinality?**
1. Don't use unbounded values as tags
2. Use fields instead of tags for high-cardinality data
3. Consider separate tables/measurements for different cardinality levels

**Q: Push vs Pull metrics?**
- Pull (Prometheus): Better for dynamic environments, service discovery
- Push (InfluxDB, StatsD): Better for short-lived jobs, behind firewalls

**Q: How much storage do I need?**
Rough formula: `series_count × points_per_day × bytes_per_point × retention_days`
With compression: typically 1-2 bytes per point.
Example: 1M series × 86400 points/day × 2 bytes × 30 days ≈ 5TB

---

## Key Terms

| Term | Definition |
|------|------------|
| Time series | Sequence of data points indexed by time |
| Cardinality | Number of unique time series (metric + tag combinations) |
| Downsampling | Reducing resolution by aggregating (1s → 5m) |
| Retention | How long data is kept before deletion |
| Rollup | Pre-computed aggregations at lower resolution |
| Tag/Label | Indexed dimension for filtering (host, region) |
| Field | Non-indexed value (actual measurements) |
| Continuous aggregate | Auto-refreshing materialized view |
| PromQL | Prometheus Query Language |
| Flux | InfluxDB's functional query language |
