# Redis Patterns and Use Cases

## 1. Concept Overview

**What Redis is**: An in-memory data structure store used as cache, message broker, and database.

**Why Redis is everywhere**: 
- Sub-millisecond latency
- Rich data structures (not just key-value)
- Atomic operations
- Pub/sub capabilities

**Common use cases**:
- Caching (most common)
- Session storage
- Rate limiting
- Leaderboards
- Real-time analytics
- Message queues
- Distributed locks

---

## 2. Data Structures

### Strings

```redis
# Basic operations
SET user:123:name "Alice"
GET user:123:name

# Atomic increment (counters)
INCR page:views:home
INCRBY user:123:points 10

# Expiration
SET session:abc "user_123" EX 3600  # expires in 1 hour
TTL session:abc  # check remaining time

# Conditional set
SETNX lock:resource "owner_1"  # set if not exists (for locking)
SET key value XX  # set only if exists
SET key value NX  # set only if not exists
```

### Hashes

```redis
# User profile (like a row/document)
HSET user:123 name "Alice" email "alice@example.com" age 30
HGET user:123 name
HGETALL user:123
HINCRBY user:123 age 1

# Advantages over string JSON:
# - Partial updates (HSET single field)
# - Atomic field operations
# - Memory efficient for small hashes
```

### Lists

```redis
# Queue (FIFO)
LPUSH queue:emails "email_1"  # push left
RPOP queue:emails             # pop right

# Stack (LIFO)
LPUSH stack:undo "action_1"
LPOP stack:undo

# Blocking pop (worker pattern)
BRPOP queue:jobs 30  # block up to 30 seconds for item

# Recent items (capped list)
LPUSH recent:user:123 "item_456"
LTRIM recent:user:123 0 99  # keep only 100 most recent
```

### Sets

```redis
# Unique collections
SADD tags:post:456 "redis" "database" "cache"
SMEMBERS tags:post:456
SISMEMBER tags:post:456 "redis"  # check membership

# Set operations
SINTER tags:post:456 tags:post:789  # common tags
SUNION tags:post:456 tags:post:789  # all tags
SDIFF tags:post:456 tags:post:789   # tags in 456 not in 789

# Random selection
SRANDMEMBER tags:post:456 2  # 2 random tags
```

### Sorted Sets

```redis
# Leaderboard
ZADD leaderboard 1000 "player:123"
ZADD leaderboard 1500 "player:456"
ZINCRBY leaderboard 100 "player:123"  # atomic score update

# Top 10 (highest scores)
ZREVRANGE leaderboard 0 9 WITHSCORES

# Rank lookup
ZREVRANK leaderboard "player:123"  # 0-indexed position

# Range by score
ZRANGEBYSCORE leaderboard 1000 2000  # scores 1000-2000

# Time-based expiration (score = timestamp)
ZADD events:user:123 1704067200 "event_1"
ZRANGEBYSCORE events:user:123 -inf 1704067200  # events before timestamp
ZREMRANGEBYSCORE events:user:123 -inf 1704067200  # cleanup old
```

---

## 3. Caching Patterns

### Cache-Aside (Lazy Loading)

```python
def get_user(user_id):
    # Try cache first
    cached = redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    
    # Cache miss - fetch from DB
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    
    # Populate cache
    redis.setex(f"user:{user_id}", 3600, json.dumps(user))
    return user
```

### Write-Through

```python
def update_user(user_id, data):
    # Update DB
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)
    
    # Update cache (same transaction context)
    redis.setex(f"user:{user_id}", 3600, json.dumps(data))
```

### Write-Behind (Async)

```python
def update_user(user_id, data):
    # Update cache immediately
    redis.setex(f"user:{user_id}", 3600, json.dumps(data))
    
    # Queue DB write for async processing
    redis.lpush("queue:db_writes", json.dumps({
        "type": "user_update",
        "user_id": user_id,
        "data": data
    }))
```

### Cache Invalidation

```python
# Event-driven invalidation
def on_user_updated(user_id):
    redis.delete(f"user:{user_id}")
    redis.delete(f"user_profile:{user_id}")  # related caches

# Versioned keys
def get_user(user_id, version):
    return redis.get(f"user:{user_id}:v{version}")

# Tag-based invalidation (using sets)
redis.sadd("cache_tags:user:123", "user:123:profile", "user:123:orders")
# Invalidate all caches for user
keys = redis.smembers("cache_tags:user:123")
redis.delete(*keys)
```

---

## 4. Rate Limiting

### Fixed Window

```python
def is_rate_limited(user_id, limit=100, window=60):
    key = f"ratelimit:{user_id}:{int(time.time() / window)}"
    current = redis.incr(key)
    if current == 1:
        redis.expire(key, window)
    return current > limit
```

### Sliding Window Log

```python
def is_rate_limited(user_id, limit=100, window=60):
    key = f"ratelimit:{user_id}"
    now = time.time()
    
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)  # remove old entries
    pipe.zadd(key, {str(now): now})              # add current request
    pipe.zcard(key)                              # count requests
    pipe.expire(key, window)
    _, _, count, _ = pipe.execute()
    
    return count > limit
```

### Token Bucket

```lua
-- Lua script for atomic token bucket
local key = KEYS[1]
local rate = tonumber(ARGV[1])  -- tokens per second
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_time')
local tokens = tonumber(data[1]) or capacity
local last_time = tonumber(data[2]) or now

-- Add tokens based on time passed
local elapsed = now - last_time
tokens = math.min(capacity, tokens + (elapsed * rate))

-- Check if enough tokens
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_time', now)
    redis.call('EXPIRE', key, capacity / rate * 2)
    return 1  -- allowed
else
    return 0  -- denied
end
```

---

## 5. Distributed Locking

### Simple Lock (SETNX)

```python
def acquire_lock(lock_name, timeout=10):
    lock_key = f"lock:{lock_name}"
    identifier = str(uuid.uuid4())
    
    if redis.set(lock_key, identifier, nx=True, ex=timeout):
        return identifier
    return None

def release_lock(lock_name, identifier):
    lock_key = f"lock:{lock_name}"
    # Lua script for atomic check-and-delete
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    return redis.eval(script, 1, lock_key, identifier)
```

### Redlock (Multi-Instance)

```python
# For high availability, acquire lock on majority of Redis instances
# Redlock algorithm:
# 1. Get current time
# 2. Try to acquire lock on N instances with short timeout
# 3. Lock acquired if majority (N/2+1) succeed and total time < lock TTL
# 4. If failed, release all locks

# Use redlock-py library for production
from redlock import Redlock

dlm = Redlock([
    {"host": "redis1", "port": 6379},
    {"host": "redis2", "port": 6379},
    {"host": "redis3", "port": 6379},
])

lock = dlm.lock("resource_name", 1000)  # 1000ms TTL
if lock:
    try:
        # do work
        pass
    finally:
        dlm.unlock(lock)
```

---

## 6. Pub/Sub and Streams

### Pub/Sub (Fire and Forget)

```python
# Publisher
redis.publish("channel:notifications", json.dumps({
    "user_id": 123,
    "message": "New follower!"
}))

# Subscriber
pubsub = redis.pubsub()
pubsub.subscribe("channel:notifications")

for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        handle_notification(data)
```

**Limitations**:
- No persistence (miss messages if not subscribed)
- No acknowledgment
- No replay

### Streams (Persistent, Replayable)

```redis
# Producer
XADD stream:orders * user_id 123 product_id 456 quantity 2

# Consumer (read new messages)
XREAD BLOCK 5000 STREAMS stream:orders $

# Consumer group (distributed processing)
XGROUP CREATE stream:orders group1 0  # create group

# Consumer reads from group
XREADGROUP GROUP group1 consumer1 COUNT 10 STREAMS stream:orders >

# Acknowledge processed message
XACK stream:orders group1 1234567890123-0
```

**Use Streams when you need**:
- Message persistence
- Consumer groups (distributed processing)
- Message replay
- Acknowledgments

---

## 7. Session Storage

### Simple Sessions

```python
def create_session(user_id, ttl=3600):
    session_id = str(uuid.uuid4())
    redis.setex(
        f"session:{session_id}",
        ttl,
        json.dumps({"user_id": user_id, "created": time.time()})
    )
    return session_id

def get_session(session_id):
    data = redis.get(f"session:{session_id}")
    if data:
        redis.expire(f"session:{session_id}", 3600)  # refresh TTL
        return json.loads(data)
    return None

def destroy_session(session_id):
    redis.delete(f"session:{session_id}")
```

### Session with Hash (Partial Updates)

```python
def set_session_data(session_id, key, value):
    redis.hset(f"session:{session_id}", key, value)
    redis.expire(f"session:{session_id}", 3600)

def get_session_data(session_id, key):
    return redis.hget(f"session:{session_id}", key)
```

---

## 8. Performance & Operations

### Memory Management

```redis
# Check memory usage
INFO memory

# Memory per key
MEMORY USAGE key_name

# Eviction policies
# - noeviction: error on memory limit (default)
# - allkeys-lru: evict least recently used
# - volatile-lru: evict LRU with TTL set
# - allkeys-random: evict random keys
# - volatile-ttl: evict shortest TTL first
```

### Pipelining

```python
# Without pipeline: N round trips
for i in range(1000):
    redis.set(f"key:{i}", f"value:{i}")

# With pipeline: 1 round trip
pipe = redis.pipeline()
for i in range(1000):
    pipe.set(f"key:{i}", f"value:{i}")
pipe.execute()
```

### Cluster Mode

```
┌─────────────────────────────────────────────────────────┐
│                   Redis Cluster                          │
│                                                          │
│   Slot 0-5460      Slot 5461-10922   Slot 10923-16383  │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐        │
│   │Master 1 │      │Master 2 │      │Master 3 │        │
│   │Replica  │      │Replica  │      │Replica  │        │
│   └─────────┘      └─────────┘      └─────────┘        │
│                                                          │
│   Keys distributed by: CRC16(key) mod 16384             │
└─────────────────────────────────────────────────────────┘
```

**Cluster limitations**:
- Multi-key operations must be in same slot (use hash tags: `{user:123}:profile`)
- No multi-database support (only DB 0)
- Lua scripts must use keys on same slot

---

## 9. Interview Answer — Authority Mode

**Question**: "When and how would you use Redis?"

**Answer**:

**Primary use cases**:
- **Caching** — sub-ms reads, 100x faster than DB; use cache-aside with TTL
- **Session storage** — low latency, automatic expiration, horizontal scaling
- **Rate limiting** — atomic INCR, sliding window with sorted sets
- **Leaderboards** — sorted sets give O(log N) rank lookups
- **Distributed locks** — SETNX with TTL, Redlock for HA

**Why Redis over alternatives**:
- **vs Memcached**: Rich data structures (lists, sets, sorted sets), persistence, pub/sub
- **vs DB caching**: Order of magnitude faster, purpose-built for caching patterns

**Operational considerations**:
- **Memory-bound** — size dataset to fit in RAM
- **Single-threaded** — one CPU per instance, scale with cluster
- **Persistence options** — RDB (snapshots) or AOF (append log) or both

**Anti-patterns to avoid**:
- Storing large values (>100KB) — network/CPU overhead
- Using as primary database without backups — memory can be lost
- Not setting TTL on cache entries — memory leak

---

## 10. FAQ

**Q: Redis vs Memcached?**
Redis: More features (data structures, persistence, pub/sub). Memcached: Simpler, multi-threaded (better for simple caching at very high scale).

**Q: When to use Streams vs Pub/Sub?**
Streams: Need persistence, replay, consumer groups. Pub/Sub: Real-time, fire-and-forget, pattern subscriptions.

**Q: How do I handle Redis failures?**
Use Redis Sentinel (HA) or Redis Cluster. Application should handle connection errors gracefully (fallback to DB).

**Q: Should I persist Redis data?**
For cache: Optional (can rebuild from DB). For sessions/queues: Yes (RDB + AOF). For primary data: Yes, but consider if Redis is the right choice.

**Q: How to avoid hot keys?**
Shard hot keys: `key:{shard_id}`. Use local caching for extremely hot data. Consider read replicas.

---

## Key Terms

| Term | Definition |
|------|------------|
| SETNX | SET if Not eXists — atomic conditional set |
| TTL | Time To Live — automatic key expiration |
| Pipeline | Batch multiple commands in single round trip |
| Pub/Sub | Publish/Subscribe messaging pattern |
| Streams | Persistent, replayable message log |
| Sentinel | Redis HA solution for automatic failover |
| Cluster | Redis horizontal scaling with hash slots |
| Lua scripting | Atomic server-side scripting |
