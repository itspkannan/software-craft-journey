# Object Storage: S3 and Beyond

## 1. Concept Overview

**What object storage is**: A storage architecture that manages data as objects (file + metadata) rather than blocks or files in a hierarchy.

**Why it matters**: Object storage is the backbone of modern cloud architecture:
- Virtually unlimited scale
- 11 nines of durability (99.999999999%)
- Cost-effective for large data
- HTTP-based access (REST API)

**Key characteristics**:
| Feature | Object Storage | File Storage | Block Storage |
|---------|---------------|--------------|---------------|
| Access | HTTP/REST API | File path | Device mount |
| Scale | Unlimited | Limited by FS | Limited by volume |
| Metadata | Rich, custom | Basic (name, size) | None |
| Performance | Higher latency | Medium | Lowest latency |
| Cost | Lowest | Medium | Highest |
| Use case | Static files, backups | Shared files | Databases, OS |

---

## 2. Real-World Case Studies

### Netflix — Media Storage

**Problem**: Store and serve petabytes of video content globally.

**Solution**: S3 for master copies, CloudFront CDN for delivery.

**Why S3**:
- Durability (can't lose master copies)
- Scales with content library growth
- Integrates with transcoding pipelines

**Scale**: Exabytes of video data

### Dropbox — File Sync

**Problem**: Store billions of user files reliably.

**Solution**: Initially S3, then custom object storage (Magic Pocket).

**Why they built their own**:
- Cost at scale (billions in S3 fees)
- Performance optimization for their access patterns
- Control over infrastructure

**Lesson**: S3 is great until extreme scale justifies custom solutions.

### Airbnb — Image Storage

**Problem**: Store millions of property images with fast retrieval.

**Solution**: S3 + CloudFront CDN + image processing pipeline.

**Architecture**:
```
Upload → S3 (original) → Lambda (resize) → S3 (variants) → CDN → User
```

---

## 3. S3 Architecture Deep Dive

### Object Model

```
┌─────────────────────────────────────────────────────────┐
│                        Bucket                            │
│  Name: my-app-images                                     │
│  Region: us-east-1                                       │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │                    Object                        │    │
│  │  Key: users/123/profile.jpg                     │    │
│  │  Data: <binary image data>                      │    │
│  │  Metadata:                                       │    │
│  │    - Content-Type: image/jpeg                   │    │
│  │    - x-amz-meta-user-id: 123                    │    │
│  │    - Last-Modified: 2024-01-15T10:30:00Z        │    │
│  │  Version: v2 (if versioning enabled)            │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Object: users/123/avatar.png                   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Internal Architecture (Simplified)

```
┌─────────────────────────────────────────────────────────┐
│                    S3 Request Flow                       │
│                                                          │
│  Client                                                  │
│    │                                                     │
│    ▼                                                     │
│  ┌─────────────┐                                        │
│  │   Route 53  │  DNS → nearest S3 endpoint            │
│  └──────┬──────┘                                        │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  S3 Front   │  Authentication, routing              │
│  │   End       │                                        │
│  └──────┬──────┘                                        │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  Index      │  Maps key → storage location          │
│  │  Service    │  (distributed key-value store)        │
│  └──────┬──────┘                                        │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  Storage    │  Actual data on distributed storage   │
│  │  Nodes      │  (replicated across AZs)              │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

### Durability: How 11 Nines Works

```
11 nines = 99.999999999% durability
         = 0.000000001% chance of losing an object per year
         = If you store 10 million objects, expect to lose 1 per 10,000 years

How achieved:
1. Data chunked and erasure coded
2. Chunks distributed across multiple AZs
3. Continuous integrity checking
4. Automatic repair of any degradation

   Object → Chunk 1 ──▶ AZ-A
          → Chunk 2 ──▶ AZ-B
          → Chunk 3 ──▶ AZ-C
          → Parity  ──▶ AZ-A, AZ-B

   Any 2 of 3 AZs can reconstruct the object
```

---

## 4. Storage Classes

### S3 Storage Classes

| Class | Use Case | Retrieval | Cost (relative) |
|-------|----------|-----------|-----------------|
| Standard | Frequent access | Immediate | $$$ |
| Intelligent-Tiering | Unknown patterns | Immediate | $$ (auto-optimized) |
| Standard-IA | Infrequent access | Immediate | $$ |
| One Zone-IA | Reproducible data | Immediate | $ |
| Glacier Instant | Archive, instant | Immediate | $ |
| Glacier Flexible | Archive, hours | 1-12 hours | ¢ |
| Glacier Deep Archive | Compliance, rare | 12-48 hours | ¢ |

### Lifecycle Policies

```json
{
  "Rules": [
    {
      "ID": "Move to IA after 30 days",
      "Status": "Enabled",
      "Filter": { "Prefix": "logs/" },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

### Cost Optimization Strategy

```
Day 0-30:    Standard (frequent access)
Day 30-90:   Standard-IA (cheaper, retrieval fee)
Day 90-365:  Glacier (archive)
Day 365+:    Delete or Deep Archive

Cost reduction: 70-80% vs keeping in Standard
```

---

## 5. Access Patterns

### Presigned URLs

```python
import boto3

s3 = boto3.client('s3')

# Generate upload URL (client can PUT directly to S3)
upload_url = s3.generate_presigned_url(
    'put_object',
    Params={'Bucket': 'my-bucket', 'Key': 'uploads/file.jpg'},
    ExpiresIn=3600  # 1 hour
)

# Generate download URL
download_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': 'my-bucket', 'Key': 'files/doc.pdf'},
    ExpiresIn=86400  # 24 hours
)
```

**Benefits**:
- Clients upload directly to S3 (bypasses your server)
- Reduces bandwidth costs
- Scales better than proxying through app

### Multipart Upload

```python
# For large files (>100MB recommended)

# 1. Initiate multipart upload
response = s3.create_multipart_upload(Bucket='bucket', Key='large-file.zip')
upload_id = response['UploadId']

# 2. Upload parts (can be parallel)
parts = []
for i, chunk in enumerate(file_chunks):
    part = s3.upload_part(
        Bucket='bucket',
        Key='large-file.zip',
        UploadId=upload_id,
        PartNumber=i + 1,
        Body=chunk
    )
    parts.append({'PartNumber': i + 1, 'ETag': part['ETag']})

# 3. Complete upload
s3.complete_multipart_upload(
    Bucket='bucket',
    Key='large-file.zip',
    UploadId=upload_id,
    MultipartUpload={'Parts': parts}
)
```

**Benefits**:
- Resume failed uploads
- Parallel chunk uploads
- Required for files >5GB

### S3 Select / Glacier Select

```python
# Query inside objects without downloading entire file
response = s3.select_object_content(
    Bucket='my-bucket',
    Key='data/large-file.csv',
    ExpressionType='SQL',
    Expression="SELECT * FROM s3object WHERE status = 'active'",
    InputSerialization={'CSV': {'FileHeaderInfo': 'USE'}},
    OutputSerialization={'JSON': {}}
)
```

**Benefits**:
- Reduce data transfer (filter server-side)
- Faster for large files with selective reads

---

## 6. Data Organization

### Key Naming Best Practices

```
❌ Bad: Sequential prefixes (hot partitions)
   logs/2024-01-15-00001.json
   logs/2024-01-15-00002.json

✓ Good: Distributed prefixes
   logs/a3f2/2024-01-15-00001.json
   logs/b7c1/2024-01-15-00002.json

❌ Bad: Deep nesting
   data/region/us/state/ca/city/sf/user/123/file.json

✓ Good: Flat with meaningful keys
   users/123/profile.json
   orders/456/receipt.pdf
```

### Partitioning for Performance

```
High request rate bucket:

Before (hot partition):
  images/image1.jpg
  images/image2.jpg
  ...

After (hash prefix distribution):
  images/0a/image1.jpg
  images/1b/image2.jpg
  images/2c/image3.jpg
  ...

S3 partitions by prefix — distributing prefixes 
distributes load across partitions
```

### Organizing for Queries (with Athena)

```
Hive-style partitioning for analytics:

s3://bucket/events/
  year=2024/
    month=01/
      day=15/
        hour=10/
          events-001.parquet
          events-002.parquet

Query:
SELECT * FROM events 
WHERE year='2024' AND month='01' AND day='15'
-- Only scans the relevant partition
```

---

## 7. Security

### Bucket Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicRead",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-bucket/public/*"
    },
    {
      "Sid": "DenyInsecure",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::my-bucket/*",
      "Condition": {
        "Bool": { "aws:SecureTransport": "false" }
      }
    }
  ]
}
```

### Encryption Options

| Type | Key Management | Use Case |
|------|----------------|----------|
| SSE-S3 | AWS managed | Default, simplest |
| SSE-KMS | Customer managed (KMS) | Audit, key rotation control |
| SSE-C | Customer provided | Full control, you manage keys |
| Client-side | Before upload | Maximum control |

```python
# SSE-KMS encryption
s3.put_object(
    Bucket='secure-bucket',
    Key='sensitive/data.json',
    Body=data,
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId='alias/my-key'
)
```

### Access Points

```
                    ┌─────────────────┐
Analytics Team ────▶│ analytics-ap    │────▶ s3://bucket/analytics/*
                    │ (read-only)     │      
                    └─────────────────┘      
                                            
                    ┌─────────────────┐      
App Servers ───────▶│ app-ap          │────▶ s3://bucket/app/*
                    │ (read-write)    │      
                    └─────────────────┘      
                                            ┌───────────────┐
                                            │    Bucket     │
                                            │   my-bucket   │
                                            └───────────────┘
```

**Benefits**:
- Simplified access management
- Dedicated endpoints per use case
- Can restrict to specific VPC

---

## 8. Performance

### Request Rate Limits

```
S3 supports:
- 3,500 PUT/COPY/POST/DELETE requests per second per prefix
- 5,500 GET/HEAD requests per second per prefix

To increase throughput: Use multiple prefixes
  uploads/a/ → 3,500 writes/sec
  uploads/b/ → 3,500 writes/sec
  uploads/c/ → 3,500 writes/sec
  Total: 10,500 writes/sec
```

### S3 Transfer Acceleration

```
Normal:    Client ──internet──▶ S3 (us-east-1)
                    (variable latency)

Accelerated: Client ──▶ Edge Location ──AWS backbone──▶ S3
                       (nearest)        (optimized)

Enable:
aws s3api put-bucket-accelerate-configuration \
  --bucket my-bucket \
  --accelerate-configuration Status=Enabled

Use endpoint: my-bucket.s3-accelerate.amazonaws.com
```

### CloudFront Integration

```
┌──────────┐      ┌─────────────┐      ┌──────────┐
│  Users   │─────▶│  CloudFront │─────▶│    S3    │
│ (global) │      │  (edge CDN) │      │ (origin) │
└──────────┘      └─────────────┘      └──────────┘
                         │
                    Cache hit: ~10ms
                    Cache miss: ~100ms + origin

Benefits:
- Lower latency (served from edge)
- Reduced S3 requests (cache hits)
- DDoS protection
- Custom domain + HTTPS
```

---

## 9. Alternatives to S3

| Service | Provider | Differentiation |
|---------|----------|-----------------|
| S3 | AWS | Most features, largest ecosystem |
| GCS | Google | Strong analytics integration, uniform bucket |
| Azure Blob | Microsoft | Good for Azure ecosystem |
| MinIO | Self-hosted | S3-compatible, on-prem |
| Cloudflare R2 | Cloudflare | Zero egress fees |
| Backblaze B2 | Backblaze | Lowest cost |

### S3-Compatible APIs

```python
# MinIO, R2, B2 all support S3 API
import boto3

# Connect to MinIO instead of S3
s3 = boto3.client(
    's3',
    endpoint_url='http://minio.local:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin'
)

# Same API works
s3.put_object(Bucket='my-bucket', Key='file.txt', Body='data')
```

---

## 10. Interview Answer — Authority Mode

**Question**: "When and how would you use S3 in a system design?"

**Answer**:

**Use S3 for**:
- **Static assets** (images, videos, JS/CSS) — served via CloudFront CDN
- **User uploads** — presigned URLs for direct upload, bypasses app server
- **Backups and archives** — lifecycle policies move to Glacier automatically
- **Data lake** — store raw data, query with Athena/Spark
- **Application artifacts** — deployment packages, logs, exports

**Key design patterns**:
- **Presigned URLs** for upload/download — scales better than proxying
- **Multipart upload** for large files — parallel, resumable
- **Lifecycle policies** for cost optimization — Standard → IA → Glacier
- **Event notifications** — trigger Lambda on upload for processing

**Performance considerations**:
- 3,500 writes/sec per prefix — use multiple prefixes for high throughput
- CloudFront for read-heavy — cache at edge, reduce S3 load
- Transfer Acceleration for global uploads — uses AWS backbone

**Cost optimization**:
- Intelligent-Tiering for unpredictable access patterns
- Delete incomplete multipart uploads (they accumulate)
- Use appropriate storage class based on access frequency

**Trade-off**: S3 has higher latency than block storage or local disk. Not suitable for database storage or low-latency random access.

---

## 11. FAQ

**Q: S3 vs EBS vs EFS?**
- S3: Object storage, HTTP access, unlimited scale, highest latency
- EBS: Block storage, attached to EC2, low latency, single instance
- EFS: File storage, shared across instances, medium latency

**Q: Is S3 strongly consistent?**
Yes, since December 2020. Read-after-write consistency for all operations.

**Q: How to handle S3 costs at scale?**
1. Lifecycle policies (move to cheaper tiers)
2. Intelligent-Tiering (automatic optimization)
3. Delete old versions and incomplete uploads
4. Consider R2 or B2 for egress-heavy workloads

**Q: Can S3 host a static website?**
Yes. Enable static website hosting, configure index/error documents. Use CloudFront for HTTPS and custom domain.

**Q: How to migrate large data to S3?**
- <10TB: AWS CLI with multipart
- 10-50TB: S3 Transfer Acceleration
- >50TB: AWS Snowball (physical device)

---

## Key Terms

| Term | Definition |
|------|------------|
| Object | Data + metadata, identified by key |
| Bucket | Container for objects, globally unique name |
| Key | Unique identifier for object within bucket |
| Presigned URL | Time-limited URL for secure access |
| Multipart upload | Upload large files in chunks |
| Storage class | Tier determining cost and access speed |
| Lifecycle policy | Rules for transitioning/expiring objects |
| Versioning | Keep multiple versions of objects |
| Replication | Copy objects across buckets/regions |
