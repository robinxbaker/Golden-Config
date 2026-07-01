# Golden Config - Detailed Architecture Explanation

## **System Architecture Overview**

Golden Config is a production-grade network device configuration management system built as a full-stack application. It enables users to capture device configurations, apply "golden" configs to compatible devices, and share configurations across teams with a role-based permission model.

---

## **1. Frontend Layer**

**Technology Stack:** React 18 + TypeScript, Material UI (MUI), TanStack Query (React Query), React Router v6, Vite build tool

The frontend is a **Single Page Application (SPA)** served by **nginx** in production. It communicates with the backend exclusively over HTTP/JSON using RESTful conventions.

**Key Architectural Decisions:**
- **TanStack Query** handles all server state management, providing automatic caching, background refetching, and optimistic updates
- **AuthContext** wraps the app to manage JWT tokens (access + refresh), storing them in memory and handling automatic refresh flows
- **Axios client** injects Bearer tokens into every request and intercepts 401 responses to trigger token refresh
- Components are organized by feature (devices, configs, jobs, shares) with shared layout components
- **TypeScript types** are generated from the backend's OpenAPI schema, ensuring type safety across the wire

The frontend never directly talks to Redis, PostgreSQL, or Celery — all state changes flow through the REST API.

---

## **2. Backend Layer (FastAPI)**

**Technology Stack:** FastAPI (ASGI), Uvicorn server, Pydantic v2 for validation, SQLAlchemy 2.0 (async), Alembic for migrations

The backend is a **stateless REST API** that validates all input, enforces authentication/authorization, orchestrates business logic, and coordinates between the database, cache, and job queue.

**Layered Architecture (Dependency Inversion):**
```
API routes (api/v1/*.py)
    ↓
Pydantic schemas (schemas/*.py) — request/response validation
    ↓
Services (services/*.py) — business logic, RBAC checks, transaction boundaries
    ↓
SQLAlchemy models (models/*.py) — ORM table definitions
    ↓
Database/Redis (db/session.py, core/redis.py)
```

Each layer depends only on the layer below it. Services never import from API routes, models never import from schemas, maintaining clean separation of concerns.

**Key Responsibilities:**
- **Input validation** via Pydantic — every request is parsed and validated before hitting business logic
- **Authentication** via JWT access/refresh token pairs (see Security section)
- **Authorization** via RBAC role checks in service methods
- **Transaction management** — services coordinate database sessions and commit/rollback boundaries
- **Job orchestration** — synchronously creates `Job` records, then asynchronously dispatches Celery tasks
- **Caching** — Redis caches expensive reads (device lists, config metadata) with configurable TTL

The API instantly returns **202 Accepted** for long-running operations (backup, apply) with a job ID, allowing the frontend to poll for status.

---

## **3. Database Layer (PostgreSQL)**

**Technology Stack:** PostgreSQL 15+, SQLAlchemy 2.0 ORM with async support (asyncpg driver), Alembic for schema migrations

**Data Model:** The schema tracks users, devices, configuration files, jobs, share requests/grants, and an append-only audit log.

**Core Tables:**
- **users** — username, hashed password, email, role (admin/operator/viewer)
- **devices** — hostname, platform (e.g., cisco_ios_xe), IP, encrypted credentials, owner
- **config_files** — config text blob, platform compatibility tag, owner, timestamps
- **jobs** — type (backup/apply), status (pending/running/succeeded/failed), target device, result/error
- **share_requests** — requester → config owner, status (pending/accepted/denied)
- **config_share_grants** — explicit read grants, checked during config access
- **audit_logs** — immutable log of all mutating actions (create/update/delete device/config/job)

**Relationships:**
- A user **owns** devices and configs
- A config can be **granted** to multiple users via share grants
- Jobs reference a device and optionally a config (for apply operations)
- Every mutating action is recorded in audit_logs with user/timestamp/action

**Encryption:** Device credentials (SSH passwords, API tokens) are encrypted at rest using **Fernet symmetric encryption** (see `app/core/crypto.py`). The encryption key is loaded from the `CREDENTIAL_ENCRYPTION_KEY` environment variable.

---

## **4. Caching & Message Broker (Redis)**

**Technology Stack:** Redis 7+, used as both a Celery message broker and application cache

Redis serves **three distinct roles** (isolated by DB number):
1. **Celery broker** (DB 0) — message queue for background jobs
2. **Celery result backend** (DB 1) — stores task results and state
3. **Application cache** (DB 2) — caches expensive API queries (device lists, config metadata)

**Caching Strategy:**
- Services use a simple key-value cache with configurable TTL (default 60s)
- Cache is **invalidated on writes** — when a device is updated, the cache key is deleted
- Cache misses fall through to PostgreSQL, then populate the cache for the next request
- Cache keys are namespaced by resource type (e.g., `device:123`, `config:456`)

Redis runs in-memory with optional persistence (RDB snapshots) in production. If Redis is unavailable, the app gracefully degrades — caching is disabled, but core functionality continues.

---

## **5. Asynchronous Job Processing (Celery Worker)**

**Technology Stack:** Celery 5+ with Redis broker, running as a separate process

The **core architectural pattern** of Golden Config is **asynchronous background job processing**. Slow operations (SSH to devices, REST API calls, config diffs) are never executed synchronously in the API request path.

**Flow:**
1. User clicks "Backup device"
2. API creates a `Job(status=pending, type=backup)` in PostgreSQL
3. API dispatches a Celery task (`backup_device_task.delay(device_id)`) to Redis
4. API **immediately returns 202 Accepted** with the job ID
5. Frontend polls `GET /jobs/{id}` every few seconds
6. Celery worker picks up the task from Redis
7. Worker calls the driver layer to communicate with the device
8. Worker updates the `Job` record to `status=succeeded` or `failed`
9. Frontend sees the status change and updates the UI

**Why This Matters:**
- **Responsiveness** — API never blocks on network I/O
- **Scalability** — workers can be scaled horizontally (multiple worker processes/machines)
- **Resilience** — if a worker crashes, Celery can retry the task
- **Progress tracking** — jobs can report intermediate progress (not yet implemented, but supported by the architecture)

The worker process (`app/worker.py`) watches Redis, picks up tasks, and executes them via the driver layer.

---

## **6. Device Communication Layer (Driver Registry)**

**Technology Stack:** Netmiko (SSH/CLI), NAPALM (multi-vendor abstraction), httpx (REST controllers)

Golden Config uses a **pluggable driver system** to abstract device communication. Each driver (e.g., `CiscoIOSXEDriver`, `JuniperMistDriver`) inherits from a base and implements:
- **`backup()`** — retrieve running config
- **`apply(config, dry_run)`** — push a config (with optional dry-run diff)
- **`sample_config()`** — return mock data for testing without hardware

**Driver Registry:**
Drivers **self-register** on import via a decorator:
```python
@register_driver("cisco_ios_xe")
class CiscoIOSXEDriver(NetmikoDriver):
    ...
```

At runtime, the worker looks up `device.platform` in the registry to find the appropriate driver.

**Transport Modes:**
- **Mock** (default) — returns realistic sample configs, no network calls, perfect for dev/test
- **Real** — connects to actual devices via SSH or REST

**Driver Inheritance Hierarchy:**
```
BaseDriver (abstract)
  ├─ NetmikoDriver (SSH-based, uses Netmiko + NAPALM)
  │    ├─ CiscoIOSXEDriver
  │    ├─ JuniperJunosDriver
  │    └─ AristaEOSDriver
  └─ RestControllerDriver (REST-based, uses httpx)
       ├─ JuniperMistDriver
       ├─ RuckusSmartZoneDriver
       └─ ExtremeSiteEngineDriver
```

This design makes adding new vendors trivial — just subclass and override `sample_config()` + real transport methods.

---

## **7. Authentication & Authorization**

**Technology Stack:** JWT (access + refresh tokens), bcrypt for password hashing, RBAC with three roles

**Authentication Flow:**
1. User submits credentials to `POST /api/v1/auth/login`
2. API validates password (bcrypt hash comparison)
3. API issues two tokens:
   - **Access token** (30-minute expiry, contains user ID + role)
   - **Refresh token** (7-day expiry, opaque, stored in DB)
4. Frontend stores tokens in memory (not localStorage, to avoid XSS)
5. Every API request includes `Authorization: Bearer <access_token>`
6. When access token expires, frontend calls `POST /auth/refresh` with the refresh token to get a new access pair

**Role-Based Access Control (RBAC):**
- **viewer** — read-only access to devices/configs they own or have been granted
- **operator** — can create/update/delete devices and run backup/apply jobs
- **admin** — full access, including user management and audit log access

Services enforce RBAC via checks like:
```python
if current_user.role not in [UserRole.operator, UserRole.admin]:
    raise ForbiddenError()
```

**Ownership & Sharing:**
- Every device and config has an `owner_id`
- Users can only see/modify resources they own, **unless**:
  - They have admin role (see everything), OR
  - They have an explicit `ConfigShareGrant` (for configs)

---

## **8. Configuration Sharing**

Golden Config implements a **request/accept workflow** for sharing configs between users:

1. User A owns `config_123` (e.g., a gold standard Catalyst 9300 config)
2. User B browses the share marketplace and clicks "Request Access"
3. API creates `ShareRequest(requester=B, config=123, status=pending)`
4. User A sees the request in their UI and clicks "Accept"
5. API creates `ConfigShareGrant(user=B, config=123)`
6. User B can now read (but not modify) `config_123`

**Authorization Check (Pseudocode):**
```python
def can_read_config(user, config):
    if user.role == admin: return True
    if config.owner == user: return True
    if ConfigShareGrant(user=user, config=config).exists(): return True
    return False
```

This enables collaboration in multi-user environments (dev teams, NOCs) while maintaining clear ownership boundaries.

---

## **9. Observability & Monitoring**

**Technology Stack:** OpenTelemetry (distributed tracing), Prometheus (metrics), Grafana (dashboards), structured logging (JSON)

**Structured Logging:**
- All logs are JSON with `timestamp`, `level`, `message`, `context` fields
- Correlation IDs can be added to trace requests across API → worker
- Logs go to stdout (captured by Docker/Kubernetes)

**Metrics (Prometheus):**
- **HTTP metrics** — request rate, latency (p50/p95/p99), status code distribution
- **Job metrics** — job duration, success/failure rate by type (backup/apply)
- **Database metrics** — query duration, connection pool stats
- Exposed via `GET /metrics` endpoint

**Distributed Tracing (OpenTelemetry):**
- Optional (enabled via `OTEL_ENABLED=true`)
- Traces follow requests from API → database, API → Celery task → worker
- Exported to an OTLP collector (e.g., Jaeger, Honeycomb, Lightstep)
- Useful for debugging latency issues and understanding async job flow

**Dashboards (Grafana):**
- Pre-configured dashboards for HTTP traffic, job throughput, error rates
- Connects to Prometheus for time-series data

---

## **10. Deployment & Infrastructure**

**Technology Stack:** Docker, docker-compose (dev), Kubernetes (production), Helm (K8s packaging), GitHub Actions (CI/CD)

**Containerization:**
- **Frontend** — multi-stage build (npm install → vite build → nginx image)
- **Backend** — Poetry for dependency management, Python 3.11+ base image
- **Worker** — same image as backend, different entrypoint (`celery worker`)

**Docker Compose (Development):**
Single command (`docker compose up`) starts:
- Frontend (port 5173)
- Backend API (port 8000)
- Worker (no exposed port)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Prometheus (port 9090)
- Grafana (port 3000)

**Kubernetes (Production):**
Separate manifests in `deploy/k8s/`:
- **Namespace** — `golden-config`
- **ConfigMaps** — environment variables
- **Secrets** — database passwords, JWT secrets
- **Deployments** — frontend (nginx), backend (uvicorn), worker (celery)
- **Services** — LoadBalancer for frontend, ClusterIP for backend/PostgreSQL/Redis
- **PersistentVolumeClaims** — for PostgreSQL data

**Helm Chart:**
Parameterized Kubernetes deployment in `deploy/helm/golden-config/`:
- `values.yaml` defines overridable defaults (replica counts, resource limits, image tags)
- Supports multiple environments via value overrides (`values-prod.yaml`)

**CI/CD Pipeline (GitHub Actions):**
On every push to `main`:
1. **Lint** — ruff (Python), ESLint (TypeScript)
2. **Format check** — black, prettier
3. **Type check** — mypy (Python), tsc (TypeScript)
4. **Unit tests** — pytest (backend), Vitest (frontend)
5. **Integration tests** — full stack with postgres/redis
6. **Build images** — docker build for frontend/backend
7. **Push to registry** — GitHub Container Registry or Docker Hub
8. **(Optional) Deploy** — kubectl apply or helm upgrade to staging

---

## **11. Testing Strategy**

**Backend:**
- **Unit tests** (`tests/unit/`) — driver logic, security utilities, import checks
- **Integration tests** (`tests/integration/`) — full API tests with real DB (pytest fixtures spin up a test PostgreSQL instance)
- **Fixtures** — `conftest.py` provides test client, DB session, authenticated users
- **Coverage** — pytest-cov tracks line coverage

**Frontend:**
- **Unit tests** — Vitest for utility functions
- **API mocking** — MSW (Mock Service Worker) intercepts HTTP requests in tests
- **No E2E yet** — could add Playwright or Cypress for full browser testing

**Testing Philosophy:**
- Integration tests are preferred over unit tests for business logic (testing the system as users will use it)
- Mock transport mode allows full system tests without hardware
- Tests run in CI on every PR

---

## **12. Security Best Practices**

- **No plaintext passwords** — bcrypt with salt rounds, never reversible
- **Encrypted device credentials** — Fernet symmetric encryption, key in environment variable
- **JWT tokens** — short-lived access tokens (30 min), longer-lived refresh tokens (7 days)
- **CORS** — configurable allowed origins (never `*` in production)
- **SQL injection prevention** — SQLAlchemy ORM (parameterized queries)
- **XSS prevention** — React escapes by default, CSP headers in nginx
- **Rate limiting** — not yet implemented (future work)
- **Audit log** — append-only, cannot be deleted by non-admins

---

## **13. Key Architectural Patterns**

- **Async job pattern** — API never blocks, always returns 202 + job ID for slow operations
- **Dependency inversion** — outer layers depend on inner, never reverse (API → Services → Models → DB)
- **Repository pattern** — services abstract database access, models never leak to API layer
- **Driver pattern** — pluggable, registry-based device communication
- **Mock/Real modes** — every driver has a mock implementation for hardware-free testing
- **Optimistic UI** — TanStack Query enables instant UI updates with background sync
- **Cache-aside** — application manages cache explicitly, DB is source of truth

---

## **Summary**

This architecture prioritizes **developer experience** (works with zero hardware), **production readiness** (observability, RBAC, encryption), and **extensibility** (adding new device types is trivial). The separation of API and worker processes enables horizontal scaling, while the layered backend design keeps code maintainable as complexity grows.
