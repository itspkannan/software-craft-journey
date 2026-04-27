# Database Reliability Patterns

## 1. Concept Overview

**What this covers**: Patterns and practices for ensuring database availability, durability, and recoverability.

**Why it matters**: Database failures cause:
- Data loss (catastrophic)
- Service outages (revenue impact)
- Data corruption (trust erosion)

**Core reliability dimensions**:
- **Availability**: System accepts requests
- **Durability**: Data survives failures
- **Consistency**: Data is correct
- **Recoverability**: Can restore after disaster

---

## 2. Replication Patterns

### Primary-Replica (Master-Slave)

```
                 Writes
                   │
                   ▼
              ┌─────────┐
              │ Primary │
              └────┬────┘
                   │ Replication
         ┌─────────┼─────────┐
         ▼         ▼         ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │Replica 1│ │Replica 2│ │Replica 3│
    └─────────┘ └─────────┘ └─────────┘
         ▲         ▲         ▲
         └─────────┼─────────┘
                   │
                 Reads
```

| Aspect | Sync Replication | Async Replication |
|--------|------------------|-------------------|
| Write latency | Higher (wait for ack) | Lower |
| Durability | Guaranteed | Potential data loss |
| Availability | Lower (replica must be up) | Higher |
| Use case | Financial data | Read scaling |

### Multi-Primary (Master-Master)

```
     ┌─────────┐       ┌─────────┐
     │Primary A│◀─────▶│Primary B│
     └─────────┘       └─────────┘
          ▲                 ▲
          │                 │
       Writes            Writes
       (region A)        (region B)
```

**Challenges**:
- Conflict resolution needed
- Split-brain risk
- More complex operations

**Solutions**:
- Last-writer-wins (timestamp)
- Application-level conflict resolution
- CRDTs (Conflict-free Replicated Data Types)

### Leaderless (Quorum-Based)

```
Client writes to multiple nodes simultaneously:

       ┌───────────────────────────────┐
       │           Client              │
       └───────────────┬───────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
      ┌─────────┐ ┌─────────┐ ┌─────────┐
      │ Node A  │ │ Node B  │ │ Node C  │
      │  ACK ✓  │ │  ACK ✓  │ │ (slow)  │
      └─────────┘ └─────────┘ └─────────┘

      Write succeeds when W nodes acknowledge
      (Quorum: W = 2 for RF=3)
```

**Quorum formula**: `R + W > N` for strong consistency

---

## 3. Failover Patterns

### Automatic Failover

```
Normal Operation:
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Primary │────▶│Replica 1│────▶│Replica 2│
└─────────┘     └─────────┘     └─────────┘

Primary Failure Detected:
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Primary │  X  │Replica 1│────▶│Replica 2│
│ (DOWN)  │     │         │     │         │
└─────────┘     └─────────┘     └─────────┘

After Failover:
┌─────────┐     ┌─────────┐     ┌─────────┐
│Old Prim │     │   NEW   │────▶│Replica 2│
│(removed)│     │ PRIMARY │     │         │
└─────────┘     └─────────┘     └─────────┘
```

### Failover Tools by Database

| Database | Tool | Mechanism |
|----------|------|-----------|
| MySQL | Orchestrator | Topology tracking, auto-promote |
| MySQL | MHA | Master HA, binlog apply |
| PostgreSQL | Patroni | etcd/Consul consensus |
| PostgreSQL | pg_auto_failover | Automatic HA |
| Redis | Sentinel | Quorum-based failover |
| MongoDB | Replica Set | Built-in election |

### Failover Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| Split-brain | Two nodes think they're primary | Fencing, consensus |
| Data loss | Async replica behind | Semi-sync replication |
| Flip-flop | Rapid primary changes | Cooldown periods |
| Stale reads | App reads from old primary | Connection draining |

---

## 4. Backup Strategies

### Backup Types

| Type | Description | Recovery Time | Storage |
|------|-------------|---------------|---------|
| Full | Complete database copy | Fast | Large |
| Incremental | Changes since last backup | Slower | Small |
| Differential | Changes since last full | Medium | Medium |
| Continuous (PITR) | Transaction log shipping | Very fast | Large |

### Point-in-Time Recovery (PITR)

```
Full Backup          Transaction Logs
(weekly)             (continuous)
    │                     │
    ▼                     ▼
┌────────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐
│Full    │──│Log │──│Log │──│Log │──│Log │
│Backup  │  │ 1  │  │ 2  │  │ 3  │  │ 4  │
└────────┘  └────┘  └────┘  └────┘  └────┘
    │                              │
    └────────────────┬─────────────┘
                     │
            Restore to any point
            between full backup and now
```

### Backup Best Practices

| Practice | Why |
|----------|-----|
| Test restores regularly | Backups are useless if restore fails |
| Store offsite/cross-region | Survive regional disasters |
| Encrypt backups | Protect sensitive data |
| Retain multiple generations | Recover from delayed discovery |
| Monitor backup jobs | Alert on failures |

### RPO and RTO

```
         ─────────────────────────────────────────▶ Time
              │                     │            │
         Last backup            Disaster      Recovery
              │◀────── RPO ───────▶│◀── RTO ──▶│
              │     (Data Loss)    │  (Downtime) │
```

| Term | Definition | Example Targets |
|------|------------|-----------------|
| RPO | Recovery Point Objective — max data loss | 1 hour, 15 min, 0 |
| RTO | Recovery Time Objective — max downtime | 4 hours, 1 hour, 5 min |

---

## 5. High Availability Architectures

### Single-Region HA

```
┌─────────────────────────────────────────────────────────┐
│                      Region: US-East-1                   │
│                                                          │
│   AZ-A              AZ-B              AZ-C              │
│ ┌─────────┐      ┌─────────┐      ┌─────────┐          │
│ │ Primary │      │ Replica │      │ Replica │          │
│ │   DB    │─────▶│   DB    │─────▶│   DB    │          │
│ └─────────┘      └─────────┘      └─────────┘          │
│      ▲                                                   │
│      │           ┌─────────────┐                        │
│      └───────────│ Load        │◀──── Application       │
│                  │ Balancer    │                        │
│                  └─────────────┘                        │
└─────────────────────────────────────────────────────────┘

Survives: Single AZ failure, instance failure
RTO: Minutes (automatic failover)
```

### Multi-Region HA

```
┌──────────────────────┐     ┌──────────────────────┐
│    US-East-1         │     │    EU-West-1         │
│  ┌─────────────┐     │     │  ┌─────────────┐     │
│  │  Primary    │─────┼─────┼─▶│  Replica    │     │
│  │  Cluster    │     │     │  │  Cluster    │     │
│  └─────────────┘     │     │  └─────────────┘     │
│        ▲             │     │        ▲             │
│        │             │     │        │             │
│   Application        │     │   Application        │
│   (writes here)      │     │   (reads OK,         │
│                      │     │    writes to US)     │
└──────────────────────┘     └──────────────────────┘

Survives: Region failure
RTO: Minutes to hours (DNS failover)
RPO: Seconds to minutes (async replication)
```

### Active-Active Multi-Region

```
┌──────────────────────┐     ┌──────────────────────┐
│    US-East-1         │     │    EU-West-1         │
│  ┌─────────────┐     │     │  ┌─────────────┐     │
│  │   Primary   │◀───────────▶│   Primary   │     │
│  │   (writes)  │ bi-direct  │   (writes)  │     │
│  └─────────────┘     │     │  └─────────────┘     │
│        ▲             │     │        ▲             │
│        │             │     │        │             │
│   US Users           │     │   EU Users           │
│   (local writes)     │     │   (local writes)     │
└──────────────────────┘     └──────────────────────┘

Survives: Region failure with zero failover
Challenges: Conflict resolution, eventual consistency
```

---

## 6. Consistency vs Availability Trade-offs

### Decision Matrix

| Requirement | Architecture | Trade-off |
|-------------|--------------|-----------|
| Zero data loss | Sync replication | Higher latency |
| Always writable | Async replication | Potential data loss |
| Global low latency | Active-active | Eventual consistency |
| Strong consistency | Single primary | Single region latency |

### Consistency Levels Comparison

| Level | Guarantee | Latency | Availability |
|-------|-----------|---------|--------------|
| Strong | Read latest write | Highest | Lowest |
| Bounded staleness | Read within X seconds | Medium | Medium |
| Session | Read your writes | Low | High |
| Eventual | Reads converge | Lowest | Highest |

---

## 7. Monitoring for Reliability

### Key Metrics

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Replication lag | >10s | >60s | Investigate primary load |
| Connections | >80% max | >95% max | Scale or pool |
| Disk usage | >70% | >85% | Add storage |
| Query latency p99 | >100ms | >500ms | Query optimization |
| Errors/sec | >1 | >10 | Check logs |

### Alerting Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    Alert Severity                        │
├─────────────────────────────────────────────────────────┤
│ P1 (Page immediately)                                    │
│   - Primary down                                         │
│   - Replication broken                                   │
│   - Data corruption detected                             │
│   - Disk full                                           │
├─────────────────────────────────────────────────────────┤
│ P2 (Page during business hours)                         │
│   - High replication lag                                │
│   - Approaching connection limit                        │
│   - Backup failure                                      │
├─────────────────────────────────────────────────────────┤
│ P3 (Ticket, no page)                                    │
│   - Disk usage warning                                  │
│   - Slow query increase                                 │
│   - Certificate expiring soon                           │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Disaster Recovery Patterns

### Pilot Light

```
Primary Region (Active):        DR Region (Pilot Light):
┌────────────────────────┐     ┌────────────────────────┐
│  ┌──────────────────┐  │     │  ┌──────────────────┐  │
│  │   Full Stack     │  │     │  │   DB Replica     │  │
│  │   Running        │  │────▶│  │   Only           │  │
│  └──────────────────┘  │     │  │   (minimal cost) │  │
│                        │     │  └──────────────────┘  │
└────────────────────────┘     └────────────────────────┘

Failover: Scale up DR infra, promote replica
RTO: Hours
Cost: Low (only DB running)
```

### Warm Standby

```
Primary Region (Active):        DR Region (Warm Standby):
┌────────────────────────┐     ┌────────────────────────┐
│  ┌──────────────────┐  │     │  ┌──────────────────┐  │
│  │   Full Stack     │  │     │  │   Reduced Stack  │  │
│  │   100% capacity  │  │────▶│  │   10% capacity   │  │
│  └──────────────────┘  │     │  └──────────────────┘  │
└────────────────────────┘     └────────────────────────┘

Failover: Scale up DR, DNS switch
RTO: 30 min - 1 hour
Cost: Medium
```

### Hot Standby (Multi-Region Active-Active)

```
Region A (Active):              Region B (Active):
┌────────────────────────┐     ┌────────────────────────┐
│  ┌──────────────────┐  │     │  ┌──────────────────┐  │
│  │   Full Stack     │◀─┼─────┼─▶│   Full Stack     │  │
│  │   50% traffic    │  │     │  │   50% traffic    │  │
│  └──────────────────┘  │     │  └──────────────────┘  │
└────────────────────────┘     └────────────────────────┘

Failover: DNS weight shift (already running)
RTO: Minutes
Cost: High (2x infrastructure)
```

---

## 9. Interview Answer — Authority Mode

**Question**: "How do you ensure database reliability at scale?"

**Answer**:

**Replication** — multiple copies of data:
- Sync replication for critical data (zero data loss)
- Async replication for read scaling (higher availability)
- Quorum-based for distributed systems (tunable consistency)

**Automatic failover** — minimize downtime:
- Use orchestration tools (Orchestrator, Patroni)
- Implement consensus-based leader election
- Practice failover regularly (chaos engineering)

**Backups** — recover from disasters:
- Continuous PITR for low RPO
- Cross-region storage for regional disasters
- Test restores monthly

**Monitoring** — detect issues early:
- Alert on replication lag, connection saturation, disk usage
- Page for data-loss risks, ticket for degradation

**Architecture choice based on requirements**:
- RPO=0, RTO=minutes: Sync replication, auto-failover
- RPO=minutes, RTO=minutes: Async replication, warm standby
- Global availability: Active-active with conflict resolution

**Trade-off**: Stronger durability guarantees = higher latency and cost. Choose based on data criticality.

---

## 10. FAQ

**Q: Sync vs async replication — which should I use?**
Sync for data you can't afford to lose (financial transactions). Async for everything else (user activity, logs). Hybrid is common: sync to one replica, async to others.

**Q: How often should I test DR?**
Quarterly at minimum. Monthly is better. Netflix runs "Chaos Kong" (simulated region failure) regularly.

**Q: What's the biggest reliability mistake?**
Not testing backups. Many teams discover backup corruption only during a real disaster.

**Q: How do I choose RTO/RPO targets?**
Business-driven. Calculate cost of downtime/data loss vs cost of achieving lower RTO/RPO. Financial systems: RPO=0, RTO=minutes. Marketing data: RPO=hours, RTO=hours.

---

## Key Terms

| Term | Definition |
|------|------------|
| RPO | Recovery Point Objective — max acceptable data loss |
| RTO | Recovery Time Objective — max acceptable downtime |
| PITR | Point-in-Time Recovery — restore to any moment |
| Failover | Switching from failed primary to replica |
| Split-brain | Multiple nodes believing they're primary |
| Quorum | Majority agreement for distributed operations |
| Replication lag | Delay between primary write and replica |
