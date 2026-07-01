# Golden Config - Interview Preparation Guide

> **Purpose**: This guide prepares you to confidently discuss your Golden Config project in technical interviews. Focus on understanding the *why* behind decisions, not memorizing every line of code.

---

## Part 1: The Elevator Pitch (5-10 minutes)

### The Problem
In network testing and lab environments, devices are rarely configured consistently. Engineers waste hours:
- Hunting through running-config to figure out what changed
- Manually copying configurations between similar devices
- Losing track of known-good configurations that worked last week

### The Solution
**Golden Config** is a full-stack web application that lets network and test engineers:

1. **Capture** a device's complete configuration and save it as a versioned config file
2. **Apply** saved configs to compatible devices to restore known-good states
3. **Share** configs between team members with a request/approval workflow

### What Makes It Production-Grade
This isn't just a proof-of-concept—it demonstrates real-world engineering practices:
- **Modern full-stack architecture**: React SPA + FastAPI backend
- **Async job processing**: Long-running device operations via Celery workers
- **Production security**: JWT auth, RBAC, encrypted credentials at rest
- **Observability**: OpenTelemetry traces, Prometheus metrics, structured logging
- **Multi-device support**: Pluggable driver architecture supporting 12+ vendor platforms (Cisco, Juniper, Arista, etc.)
- **Containerized deployment**: Docker Compose for local dev, Kubernetes + Helm for production
- **Complete test coverage**: Integration and unit tests with pytest

### Tech Stack at a Glance
| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Material UI + TanStack Query |
| Backend | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| Database | PostgreSQL |
| Job Queue | Celery + Redis |
| Device Communication | Netmiko + NAPALM (SSH), httpx (REST APIs) |
| Auth | JWT access/refresh tokens + RBAC |
| Deployment | Docker, Kubernetes, Helm |

---

## Part 2: Architecture Decisions and Rationale

### Why FastAPI?
**Decision**: FastAPI over Flask, Django, or Node.js

**Rationale**:
- **Automatic validation**: Pydantic schemas validate all input/output at runtime and generate OpenAPI docs automatically
- **Async support**: Native async/await lets us use async SQLAlchemy and scale I/O-bound operations
- **Type safety**: Full type hints catch bugs at development time (mypy) and improve IDE autocomplete
- **Modern Python**: Uses Python 3.11+ features, faster than Django for API-heavy workloads
- **Developer experience**: `/docs` endpoint with interactive Swagger UI comes free

### Why SQLAlchemy 2.0 (async)?
**Decision**: Async SQLAlchemy over Django ORM or raw SQL

**Rationale**:
- **Non-blocking I/O**: Async sessions allow FastAPI to handle other requests while waiting on database queries
- **Type safety**: SQLAlchemy models are strongly typed; mypy validates queries at dev time
- **Migration tooling**: Alembic (built for SQLAlchemy) handles schema evolution cleanly
- **Flexibility**: ORM for common CRUD, raw SQL for complex queries when needed

### Why Celery + Redis?
**Decision**: Celery for background jobs, Redis for both broker and result backend

**Rationale**:
- **Device operations are slow**: SSH sessions and config pushes can take 30+ seconds; can't block HTTP requests
- **Job visibility**: Users see real-time job status (pending → running → succeeded/failed)
- **Retry logic**: Celery handles retries, timeouts, and failure tracking automatically
- **Redis over RabbitMQ**: Simpler operations (one service), lower memory footprint, also used for caching

### Why PostgreSQL?
**Decision**: PostgreSQL over MySQL or NoSQL

**Rationale**:
- **Relational data**: Devices, users, configs, jobs, and share requests have clear relationships (foreign keys, joins)
- **JSON support**: `JSONB` columns let us store semi-structured data (driver metadata) when needed
- **Reliability**: ACID transactions ensure data consistency even with concurrent job updates
- **Industry standard**: Most teams know Postgres; easy to find managed services (AWS RDS, GCP Cloud SQL)

### Why React + TypeScript?
**Decision**: React SPA with TypeScript over Vue, Angular, or server-rendered templates

**Rationale**:
- **Interactive UI**: Real-time job polling, modals for config apply, share requests—SPA is the right pattern
- **TypeScript**: API response types generated from backend schemas catch integration bugs at compile time
- **TanStack Query**: Automatic caching, refetching, optimistic updates—handles async state elegantly
- **Material UI**: Pre-built accessible components accelerate UI development

### Why Pluggable Driver Architecture?
**Decision**: Registry-based driver system with mock/real transport modes

**Rationale**:
- **Multi-vendor support**: Adding a new device vendor is ~50 lines (inherit from `NetmikoDriver`, provide sample config)
- **Testability**: Mock transport returns sample configs—entire app runs with zero hardware
- **Separation of concerns**: Core business logic (jobs, auth, sharing) is independent of device communication protocols

### Why JWT over Session Cookies?
**Decision**: JWT access + refresh tokens

**Rationale**:
- **Stateless**: Backend doesn't store session data; scales horizontally without sticky sessions
- **Mobile-ready**: Tokens work seamlessly in mobile apps, CLI tools, or third-party integrations
- **Microservices-friendly**: Other services can validate JWTs without hitting a central session store
- **Refresh tokens**: Short-lived access tokens (30 min) reduce breach window; refresh tokens handle re-auth

### Why OpenTelemetry + Prometheus?
**Decision**: Observability stack with traces + metrics

**Rationale**:
- **Distributed tracing**: See full request path (API → database → Celery worker → device) in one span
- **Metrics**: Track job success rates, response times, error rates—critical for production ops
- **Vendor-neutral**: OpenTelemetry exports to any backend (Grafana, Datadog, New Relic)

---

## Part 3: Three Interesting Technical Problems

### Problem 1: Secure Credential Storage for Worker Access

**Challenge**: Device passwords must be stored in the database so Celery workers can open SSH sessions, but storing plaintext passwords is a security disaster.

**Initial Approach**: One-way hash passwords with bcrypt (like user passwords).

**Why It Failed**: Workers need the *actual* password to authenticate to devices. Hashes are irreversible.

**Solution**: **Symmetric encryption with Fernet (AES-128-CBC + HMAC-SHA256)**

**Implementation** ([crypto.py](backend/app/core/crypto.py)):
```python
from cryptography.fernet import Fernet

# Key derived from SECRET_KEY in dev, explicit CREDENTIAL_ENCRYPTION_KEY in prod
_fernet = Fernet(key)

def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt_secret(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()
```

**Key Insights**:
- Encryption key is stored in environment variables, *never* in code or database
- In production, use a key management service (AWS KMS, HashiCorp Vault)
- This is "encryption at rest"—credentials are still decrypted in worker memory (that's unavoidable)

---

### Problem 2: Preventing Race Conditions with JWT Refresh

**Challenge**: On token expiry (401), multiple in-flight requests would all try to refresh tokens simultaneously, causing:
- Wasted API calls (5 requests = 5 refresh attempts)
- Race condition where old token overwrites new token in localStorage

**Initial Approach**: Each request independently retries with refresh token.

**Why It Failed**: Refresh endpoint can only be used once per token (for security). Second request would fail.

**Solution**: **Single-flight token refresh with promise memoization**

**Implementation** ([client.ts](frontend/src/api/client.ts)):
```typescript
let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  // ... refresh logic
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401 && !original._retried) {
      original._retried = true;
      // Only one refresh happens; others await the same promise
      refreshing = refreshing ?? refreshAccessToken();
      const newToken = await refreshing;
      refreshing = null;
      if (newToken) {
        return api(original);  // Retry with new token
      }
    }
    return Promise.reject(error);
  }
);
```

**Key Insights**:
- The `??` operator ensures only the first failing request triggers `refreshAccessToken()`
- Subsequent requests await the existing promise
- After refresh completes, all requests retry with the new token
- The `_retried` flag prevents infinite retry loops

---

### Problem 3: Async Worker with Sync Drivers (Netmiko/NAPALM)

**Challenge**: FastAPI is fully async, but Netmiko and NAPALM are synchronous blocking libraries (they use paramiko, which predates asyncio).

**Initial Approach**: Call Netmiko directly in Celery tasks → blocks the worker thread.

**Why That's Acceptable**: Celery workers are *process-based* (not async). Each worker handles one task at a time anyway.

**The Tricky Part**: Workers need to update job status in the database, which uses async SQLAlchemy.

**Solution**: **Run async functions inside Celery tasks with `asyncio.run()`**

**Implementation** ([device_tasks.py](backend/app/tasks/device_tasks.py)):
```python
async def _run_backup(job_id: str, name: str) -> None:
    async with AsyncSessionLocal() as db:  # Async context manager
        job = await _load_job(db, job_id)
        job.status = JobStatus.RUNNING
        await db.commit()

        device = await device_service.get(db, job.device_id)
        target = device_service.build_target(device)
        
        # This is sync and blocks, but that's OK in a Celery worker
        content = get_driver(target).backup()
        
        # Save result (async)
        config = ConfigFile(...)
        db.add(config)
        await db.commit()

@celery_app.task(name="device.backup")
def run_backup(job_id: str, name: str) -> None:
    asyncio.run(_run_backup(job_id, name))  # Bridge sync→async
```

**Key Insights**:
- Celery task is sync function, calls `asyncio.run()` to enter async context
- Inside `_run_backup`, we can use `await` for database operations
- Driver calls (`backup()`, `apply()`) are sync—they block, but only one task runs per worker
- Alternative would be `asyncio.to_thread()` for true parallelism, but not needed here

---

## Part 4: Code Flow for Two Key Features

### Feature 1: Backup Flow (Create Config from Device)

**User Action**: Clicks "Backup" button on a device in the UI

**Step 1: Frontend Request** ([DevicesPage.tsx](frontend/src/pages/DevicesPage.tsx))
```typescript
const backupMutation = useMutation({
  mutationFn: (params: { deviceId: string; name: string }) =>
    api.post(`/devices/${params.deviceId}/backup`, { name: params.name }),
  onSuccess: () => {
    queryClient.invalidateQueries(['jobs']);  // Refresh job list
  }
});
```

**Step 2: API Endpoint** ([devices.py](backend/app/api/v1/devices.py))
```python
@router.post("/{device_id}/backup", status_code=201)
async def backup_device(
    device_id: UUID,
    payload: BackupRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    device = await device_service.get(db, device_id)
    # Create job record
    job = Job(
        type=JobType.BACKUP,
        status=JobStatus.PENDING,
        device_id=device.id,
        user_id=current_user.id,
    )
    db.add(job)
    await db.commit()
    
    # Enqueue Celery task
    device_tasks.run_backup.delay(str(job.id), payload.name)
    return job
```

**Step 3: Celery Worker** ([device_tasks.py](backend/app/tasks/device_tasks.py))
```python
async def _run_backup(job_id: str, name: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await _load_job(db, job_id)
        job.status = JobStatus.RUNNING
        await db.commit()

        device = await device_service.get(db, job.device_id)
        target = device_service.build_target(device)  # Decrypt credentials
        
        # Call driver (sync, blocks worker)
        content = get_driver(target).backup()
        
        # Save config file
        config = ConfigFile(
            name=name,
            platform=device.platform,
            content=content,
            owner_id=job.user_id,
        )
        db.add(config)
        await db.flush()
        
        job.config_file_id = config.id
        job.status = JobStatus.SUCCEEDED
        await db.commit()
```

**Step 4: Driver Execution** ([ssh_drivers.py](backend/app/drivers/ssh_drivers.py))
```python
def _real_backup(self) -> str:
    conn = self._connect_netmiko()  # SSH session
    try:
        return conn.send_command("show running-config")
    finally:
        conn.disconnect()
```

**Step 5: Frontend Polling** (TanStack Query auto-refetches jobs every 5 seconds)
```typescript
const { data: jobs } = useQuery({
  queryKey: ['jobs'],
  queryFn: () => api.get('/jobs').then(r => r.data),
  refetchInterval: 5000,  // Poll for status updates
});
```

**Key Takeaways**:
- API returns immediately with `job_id`—doesn't wait for backup to finish
- Worker runs async function to access database, then calls sync driver
- Driver resolves transport (mock vs. real) and executes appropriate method
- Frontend polls job status until it transitions to `succeeded` or `failed`

---

### Feature 2: Config Sharing Workflow

**User Action**: User B requests access to a config file owned by User A

**Step 1: Create Share Request** ([shares.py](backend/app/api/v1/shares.py))
```python
@router.post("/requests", status_code=201)
async def create_share_request(
    payload: ShareRequestCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    config = await config_service.get(db, payload.config_file_id)
    
    # Service validates: not owner, no duplicate request, doesn't already have access
    request = await share_service.create_request(
        db, requester=current_user, config=config, message=payload.message
    )
    return request
```

**Step 2: Validation in Service** ([share_service.py](backend/app/services/share_service.py))
```python
async def create_request(
    db: AsyncSession, requester: User, config: ConfigFile, message: str | None
) -> ShareRequest:
    # Prevent self-sharing
    if config.owner_id == requester.id:
        raise ShareError("You already own this config file.")
    
    # Prevent duplicate requests
    existing = await db.execute(
        select(ShareRequest).where(
            ShareRequest.config_file_id == config.id,
            ShareRequest.requester_id == requester.id,
            ShareRequest.status == ShareStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise ShareError("You already have a pending request.")
    
    # Check if already has access via grant
    grant = await db.execute(
        select(ConfigShareGrant.id).where(
            ConfigShareGrant.config_file_id == config.id,
            ConfigShareGrant.user_id == requester.id,
        )
    )
    if grant.scalar_one_or_none():
        raise ShareError("You already have access.")
    
    # Create the request
    request = ShareRequest(
        config_file_id=config.id,
        requester_id=requester.id,
        owner_id=config.owner_id,
        message=message,
    )
    db.add(request)
    await db.commit()
    return request
```

**Step 3: Owner Views Incoming Requests** ([shares.py](backend/app/api/v1/shares.py))
```python
@router.get("/requests/incoming")
async def list_incoming_requests(
    db: DbSession,
    current_user: CurrentUser,
):
    return await share_service.list_incoming(db, current_user)
```

**Step 4: Owner Accepts Request** ([shares.py](backend/app/api/v1/shares.py))
```python
@router.post("/requests/{request_id}/decide")
async def decide_share_request(
    request_id: UUID,
    payload: ShareDecision,
    db: DbSession,
    current_user: CurrentUser,
):
    request = await share_service.get(db, request_id)
    
    # Only owner can decide
    if request.owner_id != current_user.id:
        raise HTTPException(403, "Not your request to decide")
    
    # Update status and create grant if accepted
    await share_service.decide(db, request, accept=payload.accept)
    return request
```

**Step 5: Grant Created on Accept** ([share_service.py](backend/app/services/share_service.py))
```python
async def decide(db: AsyncSession, request: ShareRequest, *, accept: bool):
    if request.status != ShareStatus.PENDING:
        raise ShareError("This request has already been answered.")
    
    request.status = ShareStatus.ACCEPTED if accept else ShareStatus.DENIED
    request.responded_at = datetime.now(timezone.utc)
    
    if accept:
        # Create grant to give requester read access
        grant = ConfigShareGrant(
            config_file_id=request.config_file_id,
            user_id=request.requester_id,
        )
        db.add(grant)
    
    await db.commit()
    return request
```

**Step 6: Access Check When User B Views Configs** ([config_service.py](backend/app/services/config_service.py))
```python
async def user_has_access(db: AsyncSession, user: User, config: ConfigFile) -> bool:
    # Admin or owner always have access
    if user.role == UserRole.ADMIN or config.owner_id == user.id:
        return True
    
    # Check for grant
    result = await db.execute(
        select(ConfigShareGrant.id).where(
            ConfigShareGrant.config_file_id == config.id,
            ConfigShareGrant.user_id == user.id,
        )
    )
    return result.scalar_one_or_none() is not None
```

**Key Takeaways**:
- Three-table design: `ShareRequest` (the ask), `ConfigShareGrant` (the permission), `ConfigFile` (the resource)
- Status machine: `PENDING` → `ACCEPTED`/`DENIED`
- Access checks happen at service layer, enforced on every config read
- Owner-based model: Only the config owner can approve requests

---

## Part 5: Top 20 Interview Questions (With Answers)

### General / Overview (Asked in ~90% of interviews)

#### Q1: "Walk me through this project. What does it do?"
**Answer**: It's a configuration management tool for network devices. Think "Git for router configs." Engineers can save a working config from a device, then restore it later or apply it to similar devices. It's built like a production SaaS app with a React frontend, FastAPI backend, async job processing, and multi-device support.

---

#### Q2: "Why did you build this? What problem were you solving?"
**Answer**: In test labs, devices are constantly getting misconfigured. Tracking down a working config or getting a device back to a known state was manual and error-prone. This gives engineers a self-service UI to capture, version, and restore configs—saving hours per week.

---

#### Q3: "What was your role? Did you build this alone?"
**Answer**: (Be honest here—adjust based on your actual contribution)
- If solo: "This was a personal project to demonstrate full-stack skills and production practices."
- If team: "I was responsible for [backend architecture / frontend / DevOps / testing], working with [X] other developers."

**Pro tip**: Emphasize what YOU personally designed/implemented.

---

### Architecture & Design Decisions

#### Q4: "Why FastAPI instead of Flask or Django?"
**Answer**: FastAPI gives automatic input validation via Pydantic, built-in async support for non-blocking I/O, and auto-generated API docs. Django is overkill for an API-only backend, and Flask would require adding validation, async, and OpenAPI manually.

---

#### Q5: "Why use Celery for background jobs? Why not just threads or async tasks?"
**Answer**: Device operations (SSH sessions, config pushes) can take 30+ seconds. Blocking HTTP requests isn't acceptable. Celery runs in separate worker processes, handles retries automatically, and gives us job status visibility. The Redis broker ensures jobs survive even if the API server restarts.

---

#### Q6: "You used SQLAlchemy async—why? Isn't that more complex?"
**Answer**: FastAPI is async-first. With async SQLAlchemy, database queries don't block the event loop, so the server can handle other requests while waiting on Postgres. Sync SQLAlchemy would tie up a thread per request.

---

#### Q7: "Why PostgreSQL over something like MongoDB?"
**Answer**: The data is highly relational—devices belong to users, configs belong to devices, jobs reference both. Postgres enforces foreign keys, supports ACID transactions, and is a mature ecosystem. NoSQL makes sense for document stores or time-series; that's not this project.

---

#### Q8: "What's the driver registry pattern and why use it?"
**Answer**: Each device vendor (Cisco, Juniper, Arista) needs custom logic for SSH commands or REST APIs. The registry pattern lets me define a base `Driver` class, then subclass it for each platform. The registry maps platform strings (`"cisco_ios"`) to driver classes. Adding a new vendor is just 50 lines of code.

---

### Security & Authentication

#### Q9: "How do you handle authentication? Walk me through the login flow."
**Answer**:
1. User submits username/password
2. Backend verifies with bcrypt hash
3. Returns JWT access token (30 min TTL) + refresh token (7 days)
4. Frontend stores tokens in localStorage, adds `Authorization: Bearer <token>` to requests
5. On 401, frontend uses refresh token to get a new access token
6. Refresh tokens are one-time use (invalidated after refresh)

---

#### Q10: "How are device passwords stored? Aren't those sensitive?"
**Answer**: Device passwords are encrypted at rest using Fernet (AES-128). The encryption key is in environment variables, never in code. When the worker needs to SSH, it decrypts the password on the fly. This is "encryption at rest"—it protects against database dumps but doesn't prevent a compromised worker from reading passwords. For higher security, you'd integrate a secrets manager like Vault.

---

#### Q11: "What's RBAC? How did you implement it?"
**Answer**: Role-Based Access Control. Three roles:
- **Admin**: Full access (manage users, see all configs)
- **Operator**: Can manage devices, run jobs, CRUD their own configs
- **Viewer**: Read-only

Role is stored in the JWT payload and checked via dependency injection in FastAPI:
```python
@router.post("/devices", dependencies=[Depends(require_operator)])
```

---

### Frontend & State Management

#### Q12: "Why React over Vue or Angular?"
**Answer**: React has the largest ecosystem and job market. For this use case—interactive SPA with real-time updates—all three would work, but I'm most productive in React. TypeScript adds type safety across the API boundary.

---

#### Q13: "What's TanStack Query and why use it?"
**Answer**: Formerly React Query—it's a data-fetching library that handles caching, background refetching, and loading states automatically. For example, the job list auto-refetches every 5 seconds to show status updates. Without it, I'd manually manage `useEffect` timers and stale data.

---

#### Q14: "How does JWT refresh work on the frontend?"
**Answer**: Axios interceptor catches 401 responses. On first 401, it calls the refresh endpoint to get a new access token, then retries the original request. To prevent multiple simultaneous refreshes (race condition), I use promise memoization—only one refresh happens, and all failing requests await the same promise.

---

### Testing & Quality

#### Q15: "What's your testing strategy?"
**Answer**:
- **Unit tests**: Pure functions (crypto, validation) with pytest
- **Integration tests**: Full API tests with a real Postgres database (SQLite for CI)
- **Driver tests**: Mock transport returns sample configs—no hardware needed
- **Frontend**: Component tests with Vitest

Goal is fast feedback—mock external dependencies (devices, hardware) to keep tests under 30 seconds.

---

#### Q16: "How do you test device drivers without real hardware?"
**Answer**: Every driver has two modes—`mock` and `real`. Mock transport returns a realistic sample config (hardcoded string). In tests, all devices use `transport: mock`, so the entire app runs with zero physical gear. For real deployments, you set `transport: real` per device.

---

### DevOps & Deployment

#### Q17: "How do you deploy this? Kubernetes? Docker?"
**Answer**: Three modes:
- **Local dev**: `docker-compose up` runs Postgres, Redis, backend, frontend, worker
- **Production**: Kubernetes manifests deploy each service as a pod. Helm chart makes it configurable.
- **Observability**: Prometheus scrapes `/metrics`, Grafana dashboards, OpenTelemetry traces

The backend and worker are separate deployments (same image, different command).

---

#### Q18: "What's the difference between backend and worker containers?"
**Answer**: Same image, different entrypoint:
- **Backend**: `uvicorn app.main:app` (HTTP server)
- **Worker**: `celery -A app.worker worker` (job processor)

They share code but run independently. Backend handles API requests, worker handles async tasks.

---

### Observability & Debugging

#### Q19: "How do you debug a job that fails?"
**Answer**:
1. Check job status in UI—shows `FAILED` with error message
2. Check structured logs—every job has `job_id` in log context
3. Check Grafana—job failure rate dashboard
4. Check OpenTelemetry trace—see full span from API → worker → device

Failures usually mean: wrong credentials, device unreachable, or timeout.

---

#### Q20: "What's OpenTelemetry and why use it?"
**Answer**: Distributed tracing framework. Each request gets a `trace_id` that follows it through multiple services (API → database → Celery → driver). In Grafana, I can see the full timeline—e.g., "This job spent 2 seconds in SSH connection, 8 seconds pulling config." It's vendor-neutral, so you can export to any observability backend.

---

### Bonus: Scalability & Future Improvements

#### Q21: "How would you scale this to 10,000 devices?"
**Answer**:
- **Database**: Connection pooling (already using SQLAlchemy pool), read replicas for job/config queries
- **Workers**: Horizontal scaling—spin up more Celery workers (Kubernetes HPA based on queue depth)
- **API**: Stateless, already scales horizontally (add more pods behind load balancer)
- **Caching**: Redis cache for device inventory (already implemented, 60s TTL)

Bottleneck would be worker throughput—but with 10 workers @ 30s per job, that's ~1200 jobs/hour.

---

#### Q22: "What would you improve if you had more time?"
**Good answers** (shows you think about production):
- **WebSocket job updates**: Replace polling with real-time updates (Socket.IO or Server-Sent Events)
- **Config diff viewer**: Side-by-side comparison before applying
- **Audit log UI**: Currently append-only in database, no UI to browse it
- **Multi-tenancy**: Isolate teams/orgs with separate device lists
- **Backup scheduling**: Cron-like config backups (hourly, daily)

---

## Study Plan Summary

### Days 1-2: Internalize Part 1 & 2
- Memorize the elevator pitch (practice out loud)
- Understand every architecture decision *why*
- Draw the architecture diagram from memory

### Days 3-4: Master Part 3 & 4
- Walk through the three problems and solutions
- Trace the backup flow in the actual code
- Trace the share workflow in the actual code

### Days 5-6: Drill Part 5
- Practice answering each question in 60-90 seconds
- Record yourself or explain to a friend
- Identify gaps, revisit code for specifics

### Day 7: Mock Interview
- Have someone ask you random questions from Part 5
- Time yourself on the elevator pitch (stay under 5 minutes)
- Focus on explaining *why*, not *what*

---

## Final Tips

### During the Interview
✅ **Lead with the problem**: "Network devices get misconfigured, and we needed a way to..."
✅ **Use the product, not the code**: "It captures configs and restores them," not "There's a Celery task that..."
✅ **Show trade-offs**: "I used JWT over sessions because it's stateless, but the downside is..."
❌ **Don't memorize code**: You won't remember exact lines. Understand concepts.
❌ **Don't undersell**: This is a *real* production-grade app. Own it.

### Red Flags to Avoid
- "I copied this from a tutorial" → shows you didn't design it
- "I'm not sure why we used X" → shows surface-level understanding
- "It just works" → shows you don't understand trade-offs

### Green Flags to Hit
- "I chose X over Y because..." → shows intentional decision-making
- "The tricky part was Z..." → shows you solved real problems
- "If I did this again, I'd..." → shows you reflect and improve

---

## Next Steps After This Guide

Once you've mastered this guide:
1. **Add it to your GitHub README** (link to this guide in the main README)
2. **Prepare a 3-minute demo** (record yourself walking through the UI)
3. **Practice the elevator pitch** with non-technical friends (if they understand, you're clear enough)

Good luck! 🚀
