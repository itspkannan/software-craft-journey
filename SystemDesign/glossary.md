# System Design Glossary

## A

| Term | Definition |
|------|------------|
| ACK | Acknowledgment; confirmation that a message was received |
| ACID | Atomicity, Consistency, Isolation, Durability — database transaction guarantees |
| Active-Active | Multiple nodes serving traffic simultaneously |
| Active-Passive | One node serves traffic; others are standby |

## B

| Term | Definition |
|------|------------|
| Backpressure | Signal from downstream to upstream to slow data production |
| Binlog | MySQL binary log; records changes for replication |
| Bloom Filter | Probabilistic structure; answers "definitely not" or "possibly yes" |
| Bulkhead | Isolating components so one failure doesn't cascade |

## C

| Term | Definition |
|------|------------|
| CAP Theorem | Distributed system guarantees at most 2 of: Consistency, Availability, Partition tolerance |
| CDC | Change Data Capture; streaming database changes |
| Circuit Breaker | Pattern that fails fast when downstream is unhealthy |
| Consistent Hashing | Hash scheme minimizing remapping when nodes change |
| CQRS | Command Query Responsibility Segregation; separate read/write models |

## D-E

| Term | Definition |
|------|------------|
| DAU | Daily Active Users |
| Denormalization | Duplicating data to avoid joins |
| Error Budget | Allowed failure = 100% - SLO (e.g., 99.9% SLO = 43.8 min/month) |
| Event Sourcing | Storing state as append-only event log |
| Eventual Consistency | All replicas converge to same state, given time |

## F-G

| Term | Definition |
|------|------------|
| Failover | Switching to standby when primary fails |
| Fanout | Distributing one event to many recipients |
| Gossip Protocol | Decentralized protocol for spreading information |

## H-I

| Term | Definition |
|------|------------|
| Horizontal Scaling | Adding more machines |
| Hot Key | Key receiving disproportionate traffic |
| Idempotency | Operation produces same result regardless of call count |
| ISR | In-Sync Replicas (Kafka) |

## L-M

| Term | Definition |
|------|------------|
| Leader Election | Process for nodes to agree on coordinator |
| Linearizability | Strongest consistency; operations appear instantaneous |
| LSM Tree | Log-Structured Merge Tree; write-optimized storage |
| MAU | Monthly Active Users |

## N-P

| Term | Definition |
|------|------------|
| Partition | Dividing data across nodes (sharding) |
| Partition Tolerance | System operates despite network splits |
| Primary | Leader node that handles writes |
| p99 | 99th percentile latency |

## Q-R

| Term | Definition |
|------|------------|
| QPS | Queries Per Second |
| Quorum | Minimum nodes for consensus (typically N/2 + 1) |
| Read Replica | Copy of primary that serves read traffic |
| Replication Factor | Number of copies of data |

## S

| Term | Definition |
|------|------------|
| Saga | Distributed transaction using compensating actions |
| Scatter-Gather | Query hitting all partitions, aggregating results |
| Shard | Horizontal partition of data |
| Shard Key | Column determining partition placement |
| SLA | Service Level Agreement; contractual guarantee |
| SLI | Service Level Indicator; measured metric |
| SLO | Service Level Objective; target for SLI |
| Split Brain | Two nodes both think they're primary |
| Strong Consistency | Reads see latest write immediately |

## T-V

| Term | Definition |
|------|------------|
| Throughput | Operations per unit time |
| Thundering Herd | Many clients simultaneously hitting same resource |
| TTL | Time To Live; expiration time |
| Vertical Scaling | Adding resources to existing machine |
| Vitess | MySQL sharding middleware |

## W-Z

| Term | Definition |
|------|------------|
| WAL | Write-Ahead Log; durability mechanism |
| Write Amplification | One logical write causing multiple physical writes |
| Zookeeper | Distributed coordination service (being replaced by Raft in many systems) |
