# DynamoDB Deep Dive

## 1. Concept Overview

**What DynamoDB is**: AWS's fully managed, serverless NoSQL database offering single-digit millisecond latency at any scale.

**Why it exists**: AWS built it based on the Dynamo paper (Amazon, 2007) principles:
- Always available for writes
- Predictable performance at scale
- Zero operational overhead

**When to use DynamoDB**:
- Serverless architectures (Lambda + DynamoDB)
- Key-value or simple document access patterns
- Need managed scaling without ops burden
- AWS-native applications

---

## 2. Real-World Case Studies

### Amazon.com — Shopping Cart

**Original use case**: DynamoDB's predecessor (Dynamo) powered Amazon's shopping cart.

**Requirements**:
- Always accept writes (availability over consistency)
- Sub-10ms latency at millions of requests/sec
- Handle Prime Day traffic spikes

### Lyft — Rides and Pricing

**Problem**: Real-time ride data with extreme write throughput.

**Solution**: DynamoDB for ride events, pricing data.

**Why DynamoDB**:
- On-demand scaling for traffic spikes
- Global Tables for multi-region
- No operational overhead

### Capital One — Banking Workloads

**Scale**: 
- 60+ billion transactions/month
- Mission-critical banking data

**Why DynamoDB**: 
- Encryption at rest and in transit
- Fine-grained IAM permissions
- Compliance certifications

---

## 3. Architecture Deep Dive

### Data Distribution

```
┌─────────────────────────────────────────────────────────┐
│                    DynamoDB Table                        │
│                                                          │
│  Partition Key: user_id                                  │
│  Sort Key: order_id                                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Partition A  │  │ Partition B  │  │ Partition C  │  │
│  │ user_1-1000  │  │user_1001-2000│  │user_2001-3000│  │
│  │              │  │              │  │              │  │
│  │  3 AZs       │  │  3 AZs       │  │  3 AZs       │  │
│  │  (replicas)  │  │  (replicas)  │  │  (replicas)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  Each partition: up to 10GB storage                      │
│                  3000 RCU / 1000 WCU                    │
└─────────────────────────────────────────────────────────┘
```

### Primary Key Types

**Partition Key Only**:
```
┌─────────────────────────────────────┐
│  user_id (PK)  │  name   │  email  │
├────────────────┼─────────┼─────────┤
│  user_123      │  Alice  │ a@b.com │
│  user_456      │  Bob    │ b@c.com │
└─────────────────────────────────────┘
```

**Partition Key + Sort Key**:
```
┌───────────────────────────────────────────────────────┐
│ user_id (PK) │ order_id (SK) │ total  │ status      │
├──────────────┼───────────────┼────────┼─────────────┤
│ user_123     │ order_001     │ 99.99  │ completed   │
│ user_123     │ order_002     │ 149.99 │ pending     │
│ user_123     │ order_003     │ 49.99  │ completed   │
│ user_456     │ order_001     │ 199.99 │ completed   │
└───────────────────────────────────────────────────────┘
```

### Secondary Indexes

**Global Secondary Index (GSI)**:
```
Base Table:                    GSI (by status):
┌──────────┬──────────┐       ┌──────────┬──────────┐
│ user_id  │ order_id │       │ status   │ order_id │
│ (PK)     │ (SK)     │       │ (PK)     │ (SK)     │
├──────────┼──────────┤       ├──────────┼──────────┤
│ user_123 │ order_001│ ───▶  │ pending  │ order_002│
│ user_123 │ order_002│       │ completed│ order_001│
└──────────┴──────────┘       └──────────┴──────────┘

GSI has its own partition key — can be anything
GSI has its own throughput capacity
```

**Local Secondary Index (LSI)**:
```
Same partition key as base table
Different sort key
Must be created at table creation
Shares capacity with base table
```

---

## 4. Capacity Modes

### Provisioned Mode

```
┌─────────────────────────────────────────────────────────┐
│                   Provisioned Capacity                   │
│                                                          │
│  RCU (Read Capacity Units):                             │
│  - 1 RCU = 1 strongly consistent read/sec (4KB)        │
│  - 1 RCU = 2 eventually consistent reads/sec (4KB)     │
│                                                          │
│  WCU (Write Capacity Units):                            │
│  - 1 WCU = 1 write/sec (1KB)                           │
│                                                          │
│  Auto Scaling: Adjusts capacity based on utilization    │
└─────────────────────────────────────────────────────────┘
```

**Capacity calculation**:
```
Reads:
  - Item size: 8KB
  - Reads/sec: 100
  - Strongly consistent: (8KB / 4KB) × 100 = 200 RCU
  - Eventually consistent: 200 / 2 = 100 RCU

Writes:
  - Item size: 3KB
  - Writes/sec: 50
  - WCU: ceil(3KB / 1KB) × 50 = 150 WCU
```

### On-Demand Mode

```
┌─────────────────────────────────────────────────────────┐
│                    On-Demand Capacity                    │
│                                                          │
│  - Pay per request (no capacity planning)               │
│  - Instant scaling to traffic                           │
│  - 2x previous peak (instant), then gradual             │
│  - ~6x more expensive per request than provisioned      │
│                                                          │
│  Best for:                                               │
│  - Unpredictable workloads                              │
│  - New applications (unknown traffic)                    │
│  - Spiky traffic patterns                               │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Data Modeling Patterns

### Single-Table Design

```
┌─────────────────────────────────────────────────────────┐
│ PK           │ SK              │ Attributes            │
├──────────────┼─────────────────┼───────────────────────┤
│ USER#123     │ PROFILE         │ name, email, ...      │
│ USER#123     │ ORDER#001       │ total, status, ...    │
│ USER#123     │ ORDER#002       │ total, status, ...    │
│ ORDER#001    │ ITEM#A          │ product, qty, ...     │
│ ORDER#001    │ ITEM#B          │ product, qty, ...     │
└─────────────────────────────────────────────────────────┘

Query: Get user profile
  PK = "USER#123", SK = "PROFILE"

Query: Get user's orders
  PK = "USER#123", SK begins_with "ORDER#"

Query: Get order items
  PK = "ORDER#001", SK begins_with "ITEM#"
```

### Common Access Patterns

| Pattern | Implementation |
|---------|----------------|
| Get by ID | GetItem with PK |
| List by parent | Query with PK, filter SK |
| Get latest N | Query with SK DESC, Limit N |
| Get by date range | Query with SK between dates |
| Get by attribute | GSI with attribute as PK |

### Handling Many-to-Many

```
Users ←──▶ Groups (many-to-many)

┌─────────────────────────────────────────────────────────┐
│ PK           │ SK              │ Attributes            │
├──────────────┼─────────────────┼───────────────────────┤
│ USER#123     │ GROUP#A         │ joined_at, role       │
│ USER#123     │ GROUP#B         │ joined_at, role       │
│ GROUP#A      │ USER#123        │ joined_at, role       │
│ GROUP#A      │ USER#456        │ joined_at, role       │
└─────────────────────────────────────────────────────────┘

Query: Get user's groups → PK = "USER#123", SK begins_with "GROUP#"
Query: Get group's users → PK = "GROUP#A", SK begins_with "USER#"
```

---

## 6. Consistency & Transactions

### Read Consistency

| Type | Latency | Cost | Use When |
|------|---------|------|----------|
| Eventually Consistent | Lower | 0.5 RCU/4KB | Stale OK, read-heavy |
| Strongly Consistent | Higher | 1 RCU/4KB | Must see latest write |

### DynamoDB Transactions

```python
# TransactWriteItems — ACID across up to 100 items
response = dynamodb.transact_write_items(
    TransactItems=[
        {
            'Put': {
                'TableName': 'Orders',
                'Item': {'order_id': {'S': '123'}, ...}
            }
        },
        {
            'Update': {
                'TableName': 'Inventory',
                'Key': {'item_id': {'S': 'ABC'}},
                'UpdateExpression': 'SET quantity = quantity - :dec',
                'ConditionExpression': 'quantity >= :dec',
                'ExpressionAttributeValues': {':dec': {'N': '1'}}
            }
        }
    ]
)
```

**Transaction costs**: 2x normal (read + write capacity)

### Optimistic Locking

```python
# Version-based concurrency control
response = table.update_item(
    Key={'id': '123'},
    UpdateExpression='SET #data = :data, #ver = :newver',
    ConditionExpression='#ver = :oldver',  # Fails if version changed
    ExpressionAttributeNames={'#data': 'data', '#ver': 'version'},
    ExpressionAttributeValues={
        ':data': 'new_value',
        ':oldver': 5,
        ':newver': 6
    }
)
```

---

## 7. Global Tables (Multi-Region)

### Architecture

```
┌─────────────────┐              ┌─────────────────┐
│   US-EAST-1     │◀────────────▶│   EU-WEST-1     │
│                 │  Replication │                 │
│  ┌───────────┐  │   (async)    │  ┌───────────┐  │
│  │  Table    │  │              │  │  Table    │  │
│  │  Replica  │  │              │  │  Replica  │  │
│  └───────────┘  │              │  └───────────┘  │
└─────────────────┘              └─────────────────┘
         │                                │
         ▼                                ▼
   Local reads/writes               Local reads/writes
   (low latency)                    (low latency)
```

### Conflict Resolution

- **Last-writer-wins**: Based on timestamp
- **Replication lag**: Typically <1 second, but can be longer
- **Not suitable for**: Strong consistency requirements across regions

### Global Tables Costs

- Pay for each region's capacity
- Replicated writes consume WCU in target regions
- Network transfer costs between regions

---

## 8. Performance & Limits

### Key Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Item size | 400 KB | S3 for large objects |
| Partition throughput | 3000 RCU / 1000 WCU | Distribute keys |
| GSIs per table | 20 | Careful design |
| LSIs per table | 5 | Plan at creation |
| Batch operations | 25 items | Multiple batches |
| Transaction items | 100 | Split transactions |
| Query/Scan result | 1 MB | Pagination |

### Hot Partition Solutions

```
Problem: Popular item getting all traffic

Solution 1: Write sharding
  PK: item_123#shard_1, item_123#shard_2, ...
  Read: Scatter-gather across shards

Solution 2: Caching (DAX)
  Cache hot items, reduce DynamoDB load

Solution 3: On-demand mode
  Better burst handling (but more expensive)
```

### DAX (DynamoDB Accelerator)

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ Application │─────▶│    DAX      │─────▶│  DynamoDB   │
│             │      │   Cluster   │      │             │
│             │◀─────│ (in-memory) │◀─────│             │
└─────────────┘      └─────────────┘      └─────────────┘
                     
                     Cache hit: ~microseconds
                     Cache miss: normal DynamoDB latency
```

**DAX best for**:
- Read-heavy workloads
- Same items read repeatedly
- Microsecond read latency needed

---

## 9. Interview Answer — Authority Mode

**Question**: "When would you choose DynamoDB?"

**Answer**:

Choose DynamoDB when:
- **Serverless/AWS-native** — seamless Lambda integration, IAM permissions, no infrastructure
- **Managed scaling** — on-demand mode for unpredictable traffic, no capacity planning
- **Simple access patterns** — key-value or key-sortkey lookups, not complex queries
- **Global distribution** — Global Tables for multi-region active-active
- **Operational simplicity** — zero maintenance, automatic backups, point-in-time recovery

Avoid DynamoDB when:
- **Complex queries** — no JOINs, limited filtering, GSIs have their own limits
- **Cost-sensitive at scale** — provisioned capacity planning required, on-demand is expensive
- **Avoid vendor lock-in** — DynamoDB is AWS-only
- **Need strong cross-region consistency** — Global Tables are eventually consistent

**Cost consideration**: DynamoDB can be expensive without careful capacity planning. On-demand is 6x more expensive per request than optimized provisioned capacity.

**Trade-off**: You trade query flexibility and portability for operational simplicity and AWS integration.

---

## 10. FAQ

**Q: Single-table vs multi-table design?**
Single-table is more efficient (fewer round trips) but harder to understand. Use single-table for performance-critical apps with well-known access patterns. Multi-table is simpler for CRUD apps.

**Q: When to use GSI vs LSI?**
GSI: Different partition key needed, can add anytime. LSI: Same partition key, different sort key, must create at table creation.

**Q: How do I handle large items?**
Store large data in S3, keep metadata/reference in DynamoDB. Maximum item size is 400KB.

**Q: DynamoDB vs MongoDB?**
DynamoDB: Managed, serverless, AWS-integrated. MongoDB: More query flexibility, richer aggregation, portable across clouds.

**Q: How do I migrate away from DynamoDB?**
Use DynamoDB Streams to replicate changes to another database. Or export to S3 and import elsewhere.

---

## Key Terms

| Term | Definition |
|------|------------|
| RCU | Read Capacity Unit — throughput for reads |
| WCU | Write Capacity Unit — throughput for writes |
| GSI | Global Secondary Index — alternate PK/SK |
| LSI | Local Secondary Index — same PK, different SK |
| DAX | DynamoDB Accelerator — in-memory cache |
| Partition | Storage and throughput unit |
| Streams | Change data capture for DynamoDB |
| TTL | Time to Live — automatic item expiration |
