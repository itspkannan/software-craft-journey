# System Design Knowledge Base

A structured knowledge base for system design, distributed systems, and SRE patterns. Built using the 10-section format for comprehensive coverage.

## Structure

```
system-design/
├── 01-databases/           # MySQL, PostgreSQL, NoSQL, NewSQL, Redis
├── 02-distributed-systems/ # CAP, consistent hashing, consensus, transactions
├── 03-messaging/           # Kafka, RabbitMQ, SQS, stream processing
├── 04-caching/             # Strategies, invalidation, CDN, Redis vs Memcached
├── 05-apis/                # REST, GraphQL, gRPC, rate limiting
├── 06-scalability/         # Horizontal/vertical, load balancing, microservices
├── 07-reliability-sre/     # SLOs, chaos engineering, incident management
├── 08-system-designs/      # Twitter, YouTube, Uber, payments, etc.
└── glossary.md             # All terminology in one place
```

## How to Use

### For Learning
1. Start with `01-databases/mysql-at-scale.md`
2. Follow the "Next" link at the bottom of each file
3. Use the Progress Tracker to monitor coverage

### For Interview Prep
- Jump to Section 8 (Authority Mode) for verbatim answers
- Practice scenarios in `08-system-designs/`
- Review FAQ sections for gotcha questions

### For Quick Reference
- Use `glossary.md` for terminology
- Section 5 (Technology Comparison) has decision tables
- Section 7 (SRE Lens) has runbook templates

## 10-Section Format

Each topic follows this structure:

| Section | Purpose |
|---------|---------|
| 1. Concept Overview | What, why, when, alternatives |
| 2. Case Study | Real company, real problem, real solution |
| 3. Architecture Deep Dive | Components, data flow, diagrams |
| 4. Scenario Design | Requirements → capacity → design → bottlenecks |
| 5. Technology Comparison | Decision tables |
| 6. Pros & Cons | Trade-offs across dimensions |
| 7. Failure Modes & SRE | What breaks, detection, recovery |
| 8. Interview Answer | Authority mode — concise, structured |
| 9. FAQ | Common follow-ups and gotchas |
| 10. Glossary | Topic-specific terms |

## Progress

### Databases & Storage ✓ COMPLETE
- [x] MySQL at Scale — sharding, replication, Vitess, Meta's approach
- [x] PostgreSQL vs MySQL — when to choose each, replication, scaling
- [x] SQL vs NoSQL — decision framework, CAP theorem, hybrid architectures
- [x] NoSQL Scaling Comparison — Cassandra, DynamoDB, MongoDB, Redis scaling
- [x] Cassandra Deep Dive — architecture, data modeling, tuning
- [x] DynamoDB Deep Dive — architecture, capacity, single-table design
- [x] Database Reliability — replication, failover, backups, HA architectures
- [x] Database Performance — query optimization, indexing, caching
- [x] Redis Patterns — caching, rate limiting, locks, pub/sub
- [x] NewSQL (Spanner, CockroachDB) — TrueTime, HLC, global consistency
- [x] Object Storage (S3) — architecture, storage classes, patterns
- [x] Time-Series Databases — InfluxDB, Prometheus, TimescaleDB, ClickHouse

### Distributed Systems
- [ ] CAP theorem
- [ ] Consistent hashing
- [ ] Leader election (Raft vs Paxos)
- [ ] Distributed transactions (2PC vs Sagas)
- [ ] Event sourcing and CQRS
- [ ] Idempotency

### Messaging & Streaming
- [ ] Kafka internals
- [ ] Kafka vs RabbitMQ vs SQS
- [ ] Stream processing

### Caching
- [ ] Cache strategies
- [ ] Cache invalidation
- [ ] CDN caching
- [ ] Hot key problem

### APIs & Communication
- [ ] REST vs GraphQL vs gRPC
- [ ] Rate limiting algorithms
- [ ] API Gateway patterns

### Scalability
- [ ] Horizontal vs vertical scaling
- [ ] Load balancing
- [ ] Microservices boundaries

### Reliability & SRE
- [ ] SLOs, SLIs, SLAs
- [ ] Circuit breaker pattern
- [ ] Chaos engineering
- [ ] Incident management

### System Designs
- [ ] Twitter/X feed
- [ ] URL shortener
- [ ] Payment system
- [ ] Notification system
- [ ] YouTube video pipeline
- [ ] Uber location tracking

## Commands

When using with the system-design-knowledge-base skill:

| Command | Action |
|---------|--------|
| `next topic` | Generate next uncovered topic |
| `drill down on [X]` | Deep dive on specific area |
| `scenario: [desc]` | Practice system design |
| `compare [A] vs [B]` | Generate comparison table |
| `give me a quiz on [topic]` | Test your knowledge |
