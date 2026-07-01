# Golden Config — In-Depth Study Answers

Answers compiled from `GOLDEN_CONFIG_TUTORIAL.md` and the repository source.

---

## PART 1 — Product, architecture, and the big picture

### What does the product do?
Golden Config is an internal web tool for managing **network device configurations**. Network teams manage switches, routers, firewalls, access points, and wireless controllers, each of which has a long text "running-config." Doing config work by hand (SSH in, `show running-config`, copy/paste into a file, paste it back later) is slow and error-prone. Golden Config automates that loop. A user can:

1. **Register devices** — store metadata (name, platform/driver key, vendor, model, host/IP, port, transport, credentials). Credentials are encrypted at rest.

·

2. **Capture (backup) a configuration** — click a button; the system connects to the device, runs the right "show config" command, and stores the result as a private, **versioned** config file.

·

3. **Apply a configuration** — push a saved config onto a *compatible* device (platforms must match). Supports a **dry run** that previews the diff without changing anything.

·

4. **Share configurations** — configs are private to their owner; another user sends a **share request** that the owner accepts/denies, granting read access.

·

5. **Watch jobs** — backup/apply run as background jobs (device I/O is slow), so the UI shows `pending → running → succeeded/failed` plus logs and diffs.

Crucially, every driver ships a **mock** transport that generates realistic fake config text, so the whole system runs locally with zero network hardware. It also has authentication (login) and authorization (role-based: admin/operator/viewer). It exists as a production-style portfolio project demonstrating real backend/full-stack skills.

### What is the architecture of the project?
Six cooperating processes (plus the browser):

1. **React frontend** (served by nginx, port 5173) — draws the UI, talks to the backend over HTTP/JSON.

·

2. **FastAPI backend** (uvicorn, port 8000) — the "brain": validates input, enforces auth/permissions, reads/writes the database, enqueues slow work.

·

3. **PostgreSQL** — durable storage for users, devices, configs, jobs, share requests/grants, audit logs.

·

4. **Redis** — plays two roles: Celery **message broker** (queue between API and worker) and a **cache**.

·

5. **Celery worker** — a separate process that watches Redis, picks up tasks, runs the slow device work via the driver layer, writes results to Postgres.

·

6. **Driver layer** — not a process; a body of code that knows how to talk to each device kind (mock / SSH / REST).

The backend is layered: `api/v1` routes → `schemas` (Pydantic) → `services` (business rules) → `models` (ORM tables) → `db`/`core` → Postgres/Redis. Dependencies flow one direction (outer depends on inner, never the reverse). The central architectural idea is **asynchronous background jobs via a queue**: the API records a `pending` job, drops a task into Redis, and instantly returns `202 Accepted`; the worker does the work; the UI polls until the job is done.

### How does authentication and authorization work? Why this way? Why not something else? Pros and cons.
- **Authentication (who are you):** username + password login. The backend verifies the password (bcrypt) and issues two **JWTs** — a short-lived **access token** (30 min) and a longer **refresh token** (7 days). The client attaches the access token (`Authorization: Bearer <token>`) on every request. The server verifies the signature and expiry and trusts the claims without a session lookup.

·

- **Authorization (what may you do):** **RBAC** via role guards (`require_admin`, `require_operator`) plus per-row **ownership** checks.

**Why tokens (JWT) instead of server-side sessions?** HTTP is stateless, so the server must re-recognize you each request. Sessions require the server to store session state (a lookup per request, sticky to one server). JWTs are self-contained and signed, so any backend copy can verify them with just the secret key — **stateless and horizontally scalable**.

**Why access + refresh pair?** Long-lived tokens are convenient but dangerous if stolen; short-lived tokens are safe but annoying. The pair gives both: a leaked access token is useless within 30 minutes, while the refresh token spares constant re-login. The frontend auto-refreshes transparently on a 401.

**Pros:** stateless, scalable, no session store, standards-based, works well across services.
**Cons:** tokens can't be easily revoked before expiry (mitigated by short lifetime); the payload is readable (base64, not encrypted — never put secrets in it); you must protect the signing key; storing tokens in `localStorage` is XSS-exposed (mitigated by React escaping output). Alternatives: server-side sessions (easy revocation, but stateful) or opaque tokens with a DB lookup (revocable but stateful).

### Do we implement RBAC? Roles, access, enforcement, and ownership.
Yes. Three roles forming a privilege ladder:
- **admin** — full control including **user management**; can see everyone's devices/configs/jobs (the superuser).

·

- **operator** — everyday power user: create/edit/delete their own devices, run backup/apply jobs, request/respond to shares. Cannot manage users.

·

- **viewer** — read-only: can log in and view what they have access to; cannot create devices or run jobs.

**Where enforced:** at the route layer using reusable dependency guards in `api/deps.py` — `require_role(*roles)` is a factory that returns a guard; `require_admin = require_role(ADMIN)` and `require_operator = require_role(ADMIN, OPERATOR)`. Routes either list the guard in `dependencies=[Depends(require_operator)]` or take `current_user` and check in the body. A 401 means "I don't know who you are"; a 403 means "I know you, but you can't do this."

**Ownership** is the complementary mechanism. Roles decide *what kind of action*; ownership decides *which specific rows*. Non-admins only see/edit their own devices and configs (services filter `WHERE owner_id = me`; routes use helpers like `_get_owned_or_404`). Sharing is the controlled exception to ownership: an accepted share grant gives one other user **read** access to one config (but not write — only the owner/admin can modify). So every permission check is one of: role, ownership, or share grant.

### Explain how register devices works.
1. User opens "Add device" on `DevicesPage`, fills the form (name, platform from the `useDrivers()` dropdown, host, transport=mock by default, optional credentials).

·

2. The mutation `POST /api/v1/devices`; Axios attaches the JWT automatically.

·

3. The route runs `require_operator` (role gate), validates the body against `DeviceCreate` (e.g. port 1–65535), and checks the platform is a registered driver (else 422).

·

4. `device_service.create` **Fernet-encrypts** the secret before saving, stamps `owner_id = current_user.id`, commits.

·

5. The route audits `device.create`, serializes via `_to_read` which sets `has_secret = encrypted_secret is not None` (never returns the secret), and returns `201 Created`.

·

6. TanStack Query invalidates `["devices"]`, so the list auto-refetches and the new device appears.

### Explain how capture a configuration (backup) works.
1. Click "Backup" → `POST /jobs/backup`.

·

2. Route checks `require_operator` and device ownership, then the three-step dance: `create_backup_job` writes a `pending` job row → `dispatch(job)` enqueues a Celery message into Redis carrying **only the job id** → `mark_dispatched` records the task id. Returns `202 Accepted` with the pending job.

·

3. The Celery worker pulls the message, runs `run_backup(job_id)` → `asyncio.run(_run_backup(...))`. It opens its own DB session, marks the job `running`, loads the device, and `build_target` decrypts the credential.

·

4. `get_driver(target).backup()` selects the driver; mock transport returns `sample_config()` (a real device would SSH and run `show running-config`).

·

5. The worker creates a new `ConfigFile` (tagged with the driver's `config_format`, owned by the user, with `source_device_id`), marks the job `succeeded` with a log.

·

6. The Jobs page poll (every 4s) sees `succeeded`; because the mutation also invalidated `["configs"]`, the new config appears on the Config Files page.

### Explain how apply a configuration works.
1. Choose a config + device, optionally check "dry run" → `POST /jobs/apply`.

·

2. Route checks `require_operator`, device ownership, and config access (`user_has_access`: own/admin/granted). `create_apply_job` enforces the **platform-compatibility rule** — if config.platform ≠ device.platform it raises `JobError` → route returns `422`.

·

3. Same dispatch dance, but the task is `run_apply` carrying `dry_run`. Returns `202`.

·

4. The worker's `_run_apply` builds the target and calls `driver.apply(config.content, dry_run=...)`, returning an `ApplyResult(diff, applied, log)`. On a dry run, `applied=False` and you get a preview diff without changing the device. Real applies prefer **NAPALM** for an atomic commit + rollback.

·

5. The diff + applied flag + log are serialized into the job's `log` field; job marked `succeeded`.

·

6. Polling shows the result; the operator reads the diff to see what changed (or would change).

### Explain how sharing a configuration works.
1. Requester views a config they don't own and clicks "Request access" → `POST /shares`.

·

2. `share_service.create_request` enforces three guard rails (can't request your own config; can't stack a duplicate pending request; can't request something already granted) — each raises `ShareError` → `409 Conflict`. A clean request creates a `pending` `ShareRequest`.

·

3. The owner sees it on `SharesPage`'s **incoming** list, showing the requester's username (the service `selectinload`s the `requester` relationship; the read schema nests `UserPublic`). Owner clicks Accept.

·

4. `POST /shares/{id}/decision` confirms the caller is the config owner, then `share_service.decide(accept=True)` — in **one transaction** — marks the request `accepted` *and* inserts a `ConfigShareGrant`. Atomicity means you never get "accepted but no grant."

·

5. The requester's mutation invalidated `["configs"]`; `user_has_access` now finds a grant, so the shared config appears in their list — **readable but not editable** (only owner/admin can modify).

### Explain how watching jobs works.
Backup/apply are background jobs, so the UI must observe progress without blocking. The `JobsPage` uses `useJobs(pollMs=4000)`, a TanStack Query hook with `refetchInterval: 4000` that silently re-fetches `GET /jobs` every four seconds. The worker writes status transitions (`pending → running → succeeded/failed`) and `log`/`error` into the `jobs` table in Postgres. Each poll reads the latest rows, so the status chip and logs update on their own. When you navigate away, the hook unmounts and polling stops. Polling is the simplest mechanism here; WebSockets would be more complex and unnecessary.

### Do we use a mock device for demo/testing? How does it work?
Yes — the **mock transport** is the keystone design choice. Each device has a `transport` field defaulting to `MOCK`. In `BaseDriver`, every public method checks `self.target.transport == "mock"`:
- `test_connection()` → returns `True` instantly.

·

- `backup()` → returns `sample_config()` (realistic fabricated text each concrete driver supplies).

·

- `apply()` → `_mock_apply` echoes the config as a "diff" and reports success (or a preview for dry run).

Because the mock is at the *driver* level, every layer above (services, tasks, API, UI, tests) exercises the **exact same code paths** it would for a real device — only the leaf I/O differs. This means `docker compose up` gives a fully usable app with no hardware, and tests run against mock transport. Flipping `transport: real` switches to actual Netmiko/NAPALM/httpx I/O.

### What are the big "buzzword" things this project uses/implements?
REST API design; relational data modeling; authentication and role-based access control; asynchronous background job processing (producer/broker/consumer); a pluggable integration layer (driver registry / Open-Closed Principle); caching (Redis); encryption-at-rest (Fernet for credentials) and password hashing (bcrypt); automated testing (unit + integration, pytest/Vitest); containers (Docker, multi-stage builds); CI pipelines (GitHub Actions); Kubernetes deployment + Helm packaging; a clean React/TypeScript SPA frontend; observability (structured logs, Prometheus metrics, OpenTelemetry traces); database migrations (Alembic); async I/O throughout (FastAPI/asyncpg/SQLAlchemy 2.0 async); JWT auth with access/refresh tokens; ORM with parameterized queries (SQL-injection safe); twelve-factor config.

### How does the program communicate with the devices? (SSH and REST API)
Two transports, both hidden behind the uniform `BaseDriver` interface:
- **SSH/CLI** — most platforms (Cisco, Juniper, Arista, Dell, HPE, Brocade, Ruckus). Real I/O uses **Netmiko** (CLI over SSH) and **NAPALM** (for apply: real diffs + atomic commit/rollback).

·

- **REST API over HTTPS** — cloud-managed wireless controllers (Juniper Mist, Ruckus SmartZone, Extreme Site Engine). Real I/O uses **httpx** to GET/PUT JSON config.

From the caller's perspective a REST driver and an SSH driver are identical — both expose `backup()`/`apply()`. The transport difference is encapsulated (polymorphism).

### What tools are we using for SSH? Explain, pros/cons, alternatives. (Netmiko, NAPALM)
- **Netmiko** — a Python library that automates SSH sessions to network gear across many vendors (it knows each vendor's CLI quirks via `device_type`). Used for `_real_backup` (`send_command("show running-config")`) and as the apply fallback.

·

  - *Pros:* broad multi-vendor support, simple send/receive CLI model, mature, widely used.

·

  - *Cons:* it's CLI text scraping (no structured data, no native diff), synchronous/blocking (one reason device work runs in the worker, not the async web server), brittle to prompt/format changes.

·

- **NAPALM** — a higher-level abstraction the apply path *prefers*. It can compute a real configuration **diff** and do an **atomic replace/merge with commit and rollback**.

·

  - *Pros:* structured config operations, safe atomic commits, real diffs — exactly the safety you want pushing config to live gear.

·

  - *Cons:* supports fewer platforms than Netmiko, heavier, more setup; falls back to Netmiko when unsupported.

·

- **Alternatives:** Paramiko (lower-level raw SSH — Netmiko is built on it), Scrapli (faster modern async-capable CLI library), Ansible network modules, vendor SDKs (e.g. Cisco pyATS/Genie).

### What tool for REST API of devices? Explain, pros/cons, alternatives. (httpx)
- **httpx** — a modern Python HTTP client with a requests-style API that **also supports async**. The REST drivers use it for authenticated GET/PUT to controller APIs over HTTPS, returning/sending JSON.

·

  - *Pros:* async-capable (fits the async stack), HTTP/2 support, connection pooling, timeouts, requests-compatible ergonomics; also powers the in-process test client (`ASGITransport`).

·

  - *Cons:* slightly newer/less ubiquitous than `requests`; you still hand-roll the per-vendor API specifics.

·

- **Alternatives:** `requests` (sync only, the classic), `aiohttp` (async but lower-level/less ergonomic), `urllib` (stdlib, verbose).

---

## PART 2 — Stack deep dives (frontend, backend, DB, Redis, Celery, drivers, async)

### Explain the frontend in detail.
A **single-page application (SPA)**: the browser loads one HTML page + a JS bundle once, then JavaScript re-renders in place and fetches only JSON from the API. Stack: **TypeScript** (typed JS), **React 18** (component/hooks UI), **Vite** (build tool/dev server), **React Router** (URL→component), **TanStack Query** (server-state cache + polling), **Axios** (HTTP client with interceptors), **Material UI** (component/design system), **Vitest** (test runner). Boot flow: `main.tsx` mounts a provider stack (QueryClient, Theme, BrowserRouter, AuthProvider) → `App.tsx` gates routes by auth → pages read data via hooks and render with MUI. Writes go through `useMutation`, which invalidates cache keys so reads re-sync.
- *Why React/this stack:* React is the dominant declarative SPA library; TypeScript catches bugs at compile time; TanStack Query removes hand-rolled loading/error/cache/poll code; MUI gives consistent accessible UI without hand CSS; Vite is near-instant.

·

- *Pros:* fast app-like UX, strong typing, minimal boilerplate for data flow, large ecosystem.

·

- *Cons:* heavier build toolchain, JS must run in the browser (SEO/initial-load considerations), client now runs a real program. *Alternatives:* Vue, Svelte, Angular; Next.js (SSR); plain server-rendered templates.

### Explain the backend in detail.
**Python 3.11 + FastAPI** served by **uvicorn**. FastAPI is an async, type-hint-driven web framework: it auto-validates requests via Pydantic and auto-generates OpenAPI docs. The backend is strictly layered (routes → schemas → services → models → db/core), async top to bottom (asyncpg + SQLAlchemy 2.0 async). It enforces auth/RBAC, owns business rules in services, and enqueues slow work to Celery instead of doing it inline.
- *Why FastAPI:* async-native (good for I/O-bound web work), less boilerplate than Django REST Framework, more batteries than Flask, free validation + docs from type hints.

·

- *Pros:* fast, typed, self-documenting, modern async model.

·

- *Cons:* younger ecosystem than Django, fewer built-ins (no ORM/admin/migrations bundled — you assemble them), async adds complexity. *Alternatives:* Django/DRF (batteries-included, sync-first), Flask (minimal), Node/Express, Go.

### Explain the database in detail.
**PostgreSQL**, a relational, fully ACID DBMS. Data lives in tables (`users`, `devices`, `config_files`, `config_share_grants`, `share_requests`, `jobs`, `audit_logs`) with UUID primary keys, foreign keys, indexes, and native ENUM types. The app talks to it via the **SQLAlchemy 2.0 async ORM** over the **asyncpg** driver.
- *Why Postgres:* fully ACID/reliable, free/open-source, feature-rich (real ENUM, native UUID, JSON/JSONB), great concurrency via **MVCC** (readers don't block writers).

·

- *Pros:* correctness guarantees, mature, scalable, standards-compliant.

·

- *Cons:* needs a running server (heavier than embedded DBs), tuning required at scale. *Alternatives:* MySQL/MariaDB (also solid), SQLite (used in tests — embedded, single-file, but not 100% identical and weaker concurrency), NoSQL (MongoDB — wrong fit for this relational, transaction-heavy data).

### Explain Redis in detail.
**Redis** is an in-memory key–value store (microsecond reads, RAM-resident, native TTL). This project uses it for **three** roles, separated by logical DB number to avoid collisions: Celery **broker** (`/0`), Celery **result backend** (`/1`), and a general **cache** (`/2`).
- *Why Redis:* fast, shared, external store every process can reach over the network — exactly what a multi-process architecture needs (a Python dict can't be shared across the API and a separate worker).

·

- *Pros:* extremely fast, simple, doubles as broker + cache, TTL/expiry built in.

·

- *Cons:* in-memory (data is ephemeral unless persistence configured), single-threaded core, not a durable store of record. *Alternatives:* RabbitMQ (a dedicated, more feature-rich broker), Kafka (event streaming), Memcached (cache only).

### Explain the Celery workers in detail.
**Celery** is the most popular Python distributed task-queue framework. `worker.py` defines the Celery app (broker=Redis/0, backend=Redis/1, JSON serialization, `task_time_limit=300`, `result_expires=3600`, UTC). `tasks/device_tasks.py` defines `run_backup`/`run_apply`. The worker is a **separate process** that watches Redis, pops task messages, and runs the slow device work, updating Postgres. Tasks are synchronous wrappers that call `asyncio.run(...)` to reuse the app's async DB code.
- *Why Celery:* de-facto Python background-job framework; decouples slow work from the request path; enables independent scaling and retry/resilience.

·

- *Pros:* mature, integrates with Redis/RabbitMQ, retries, scheduling, time limits.

·

- *Cons:* operational overhead (extra process + broker), config complexity, sync-first model. *Alternatives:* RQ (simpler, Redis-only), Dramatiq, ARQ (async-native), cloud queues (SQS + Lambda).

### Explain the driver layer in detail.
The cleverest design: an **abstract base class** (`BaseDriver`, an `ABC` with an abstract `sample_config`) defines the contract (`test_connection`, `backup`, `apply`); concrete subclasses implement one platform each. A **registry** dict maps `platform` string → driver class, populated by the `@register` decorator at import time; `get_driver(target)` is the factory. SSH drivers share a Netmiko mixin; REST drivers share an httpx mixin; each concrete class is tiny (identity `ClassVar`s + `sample_config`). The mock/real split lives in the base.
- *Why:* it answers "talk to many device types without business logic caring which" via **polymorphism** + the **Open/Closed Principle** — add a platform by writing one decorated subclass; nothing else changes.

·

- *Pros:* extensible, testable (mock-first), clean separation of identity/behavior/selection.

·

- *Cons:* indirection/abstraction to learn; real I/O still per-vendor work. *Alternatives:* big `if/elif` branching (rejected), a config-driven plugin loader, entry-point plugins.

### Explain the architecture behind how this project is async.
Two distinct kinds of "async":
1. **Async I/O concurrency in the web layer.** FastAPI runs on an event loop; nearly every function is `async def` and DB calls are `await`ed. asyncpg (async Postgres driver) + SQLAlchemy 2.0 async engine let one backend process handle many concurrent requests: while one request waits on the DB, others progress. This is for **I/O-bound waiting**, not CPU work.

·

2. **Background processing via a queue.** Slow, blocking device work (SSH handshakes, NAPALM commits) would block the event loop, so it's handed to the **Celery worker** (a separate process). The API enqueues a task and returns `202` immediately; the worker does the slow work. Celery tasks are synchronous functions that internally call `asyncio.run(...)` to reuse the async DB code (the worker can afford to block because it isn't serving web requests). Don't confuse async concurrency (one thread juggling waits) with parallelism (multiple cores) or background processing (a separate process via a queue) — this app uses async for web concurrency and a queue+worker for background jobs.

### Why six separate programs instead of one?
Each split buys something concrete:
- **Frontend vs backend** — they do different jobs (render pixels in a browser vs enforce rules/store data on a server) and run in different places.

·

- **Database in its own process (Postgres)** — a dedicated, battle-tested engine solves durable, concurrent, queryable storage; you'd never reinvent that.

·

- **Worker separate from backend** — slow device work doesn't clog the fast request/response path; the web server stays snappy, and you scale the two independently (more workers vs more backends).

·

- **Redis between backend and worker** — a neutral hand-off so the two don't need to know about each other or run at the same instant; tasks wait safely if workers are busy.

The cost — more moving parts — is exactly what Docker Compose manages.

### Give me an example of the data's journey.
A **backup**: You click "Backup" in the browser → authenticated `POST /api/v1/jobs/backup` → backend checks you're an operator and own the device, writes a `pending` `jobs` row to Postgres, calls Celery `.delay(...)` which drops a task (job id) into Redis, records the task id, and instantly replies `202 Accepted`. The Celery worker (watching Redis) picks up the task, loads the job from Postgres, marks it `running`, asks the driver layer for the config (mock returns realistic text), creates a `config_files` row, marks the job `succeeded`, commits. Meanwhile the browser polls `GET /api/v1/jobs` every few seconds; the next poll after `succeeded` updates the UI. Every concept in the project is a detail of some step in that journey.

### Is the backend stateless or stateful? Explain.
**Stateless.** The backend stores nothing permanent in its own memory; every durable fact (users, devices, configs, jobs) lives in PostgreSQL. This is why you can run several backend copies or restart it without losing anything, and why the worker — an entirely separate process — can "see" the same jobs: they share the *database*, not memory. The Redis queue carries only an id; the worker re-reads authoritative state from Postgres rather than trusting the message. Pushing all durable state into the database and keeping app processes stateless is the foundation for horizontal scaling and surviving restarts. (Postgres and Redis are the *stateful* components.)

---

## PART 3 — Computer science foundations

### Difference between a program and a process.
A **program** is a file of instructions on disk (the Python files). A **process** is a *running instance* of a program — the OS has loaded it into memory and is executing it, giving it its own private memory and CPU time slice. The six boxes in the architecture are six processes. Processes are isolated (one can't read another's memory by default), so cooperating processes must communicate over sockets, files, a database, or a queue.

### Difference between a server and a client.
A **server** is a long-running process that starts, **listens** on a port, and waits for incoming requests, handling each and replying. A **client** *initiates* requests. The backend is a server (listens on 8000); the browser is a client. But "client"/"server" are *roles in a conversation*, not fixed identities — the backend is also a *client* of Postgres (5432) and Redis (6379).

### Describe all 5 HTTP methods and what they do.
- **GET** — read a resource. Safe (never changes data) and idempotent.

·

- **POST** — create/submit. *Not* idempotent (POST twice = two things created).

·

- **PATCH** — partially update (send only the fields you want changed).

·

- **PUT** — replace a resource wholesale. Idempotent.

·

- **DELETE** — remove a resource. Idempotent.

This app: list = GET, create = POST, edit = PATCH, remove = DELETE.

### Explain the main HTTP status codes.
Grouped by first digit:
- **2xx success:** `200 OK`, `201 Created` (resource created), `202 Accepted` (queued/async), `204 No Content` (success, no body — used for delete).

·

- **3xx redirection.**

·

- **4xx client error:** `400 Bad Request`, `401 Unauthorized` (not authenticated), `403 Forbidden` (authenticated but not allowed), `404 Not Found`, `409 Conflict` (e.g. duplicate share request), `422 Unprocessable Entity` (validation failure / platform mismatch).

·

- **5xx server error:** `500 Internal Server Error`.

The project is deliberate: `202` for "job queued," `409` for "already requested," `422` for "config incompatible with device."

### Difference between a header and a body.
**Headers** are key–value metadata about the message: `Authorization: Bearer <token>` (who you are), `Content-Type: application/json` (the body's format), `Content-Disposition: attachment; filename=...` (trigger a download). The **body** is the optional payload — the actual data, usually JSON for POST/PATCH/PUT requests and for responses. Login is the one endpoint that uses a form-encoded body instead of JSON.

### Explain REST.
**RE**presentational **S**tate **T**ransfer is a *style* (set of conventions) for HTTP APIs, not a library. Model your app as **resources** (nouns) and manipulate them with standard HTTP **methods** (verbs) rather than inventing function-style URLs. So instead of `/getAllDevices`, `/createNewDevice`, you have one resource `devices` and express intent via method + path: `GET /devices` (list), `GET /devices/{id}` (one), `POST /devices` (create), `PATCH /devices/{id}` (update), `DELETE /devices/{id}` (delete). The same path does different things depending on the verb; learn the pattern once, know it for all resources. `/api/v1` is **versioning** so a future `v2` can break things while `v1` clients keep working.

### What is serialization and deserialization (parsing)?
**Serialization** is turning an in-memory object into a transmittable format (e.g. a Python object → a JSON string) to send over the wire. **Deserialization** (parsing) is the reverse — JSON text → in-memory typed object. The Python backend uses **Pydantic** for both (validating on the way in, serializing on the way out); the TypeScript frontend uses Axios, which wraps `JSON.stringify`/`JSON.parse`. Both ends agreeing on JSON is what lets a Python program and a TypeScript program exchange structured data.

### Benefits of a database over writing to files manually.
A DBMS solves, for you, problems you'd otherwise hand-roll and get subtly wrong: fast lookups without reading the whole file (indexes); safe concurrent reads/writes by many users (isolation/locking/MVCC); crash safety so a half-finished update doesn't corrupt data (atomicity/durability — transactions); and rule enforcement like uniqueness and referential integrity (constraints/foreign keys). You also get a powerful query language (SQL) for filtering/joining/aggregating. Files give you none of that for free.

---

## PART 4 — Database & data modeling

### What tables does this project have? What do the columns represent?
- **users** — `id` (UUID PK), `username` (unique, indexed), `email` (unique, indexed), `hashed_password` (bcrypt hash), `full_name` (optional), `role` (enum admin/operator/viewer, default viewer), `is_active` (bool — disable instead of delete), `created_at`/`updated_at`.

·

- **devices** — `id`, `name` (indexed), `platform` (driver key, indexed), `vendor`, `model`, `host`, `port` (default 22), `transport` (enum mock/real, default mock), `username`, `encrypted_secret` (Fernet, never returned), `owner_id` (FK→users, CASCADE), timestamps.

·

- **config_files** — `id`, `name` (indexed), `description`, `platform` (indexed — compatibility key), `format` (enum cli/json/set), `content` (Text — the config), `version` (int, bumps on content change), `owner_id` (FK→users, CASCADE), `source_device_id` (FK→devices, SET NULL), timestamps.

·

- **config_share_grants** — join table: `id`, `config_file_id` (FK, CASCADE), `user_id` (FK, CASCADE), unique constraint on the pair; means "user U may read config C."

·

- **share_requests** — `id`, `config_file_id` (FK, CASCADE), `requester_id` (FK→users), `owner_id` (FK→users), `status` (enum pending/accepted/denied), `message`, `responded_at`, timestamps.

·

- **jobs** — `id`, `type` (enum backup/apply), `status` (enum pending/running/succeeded/failed), `device_id` (FK, CASCADE), `config_file_id` (FK, SET NULL — null for backups), `user_id` (FK, CASCADE), `celery_task_id` (indexed), `log` (Text), `error` (Text), timestamps.

·

- **audit_logs** — `id`, `actor_id` (FK→users, SET NULL — survives user deletion), `action` (dotted string, indexed, e.g. `login.success`), `target_type`, `target_id` (loose string refs, not FKs), `detail`, timestamps.

### Explain one one-to-many relationship.
One **user** owns many **devices**. The "many" side (`devices`) holds the foreign key `owner_id` pointing to `users.id`. In the ORM, `user.devices` is a list and `device.owner` points back (paired via `back_populates`). It uses `ON DELETE CASCADE`, so deleting a user deletes their devices. (Other one-to-many: user→config_files, user→jobs, device→jobs.)

### Explain one many-to-many relationship.
Users ↔ config files via sharing: one user can be granted many configs, and one config can be shared with many users. This requires the **join table** `config_share_grants`, each row linking a `config_file_id` to a `user_id` ("this user may read this config"). A unique constraint on `(config_file_id, user_id)` prevents duplicate grants.

### What does this project index? Why those?
Indexes speed up the columns you frequently search/filter/join by, at the cost of storage and slightly slower writes. Indexed here: `users.username` and `users.email` (login lookups + uniqueness), `devices.name` and `devices.platform` (filtering/grouping), `config_files.name` and `config_files.platform`, `jobs.celery_task_id` (look up a job by its Celery id), `audit_logs.action` (filter by action type), and the foreign keys (fast joins/ownership filters). Unique indexes on `users.username`, `users.email`, and the `(config_file_id, user_id)` grant pair also enforce no duplicates. You don't index everything because each index costs write performance and disk.

### Give an example of an SQL command.
```sql
SELECT id, name, platform
FROM devices
WHERE owner_id = '1a2b...'
ORDER BY name
LIMIT 100;
```
`SELECT` chooses columns, `FROM` the table, `WHERE` filters rows, `ORDER BY` sorts, `LIMIT` slices. The ORM generates exactly this kind of SQL — `db.get(Device, id)` becomes `SELECT * FROM devices WHERE id = …`.

### What is a transaction?
A group of SQL statements treated as a single, indivisible unit: either all succeed and `COMMIT` (made permanent), or any failure triggers `ROLLBACK` (undo it all). Example: accepting a share marks the request `accepted` *and* inserts a grant; a transaction guarantees you never get one without the other. `session.commit()` commits; `get_db` rolls back on exceptions.

### Does our database guarantee ACID? What is ACID?
Yes, PostgreSQL is fully ACID:
- **Atomicity** — all statements in a transaction succeed or none do (no half-states).

·

- **Consistency** — every transaction moves the DB from one valid state to another; all rules (types, FKs, uniqueness, NOT NULL) hold.

·

- **Isolation** — concurrent transactions don't see each other's uncommitted changes; results are as if they ran one at a time (Postgres uses MVCC).

·

- **Durability** — once committed, data survives crashes/power loss (written safely to disk).

ACID is the main reason to use a relational DB for important data rather than files or a cache. (SQLite, used in tests, is also ACID but weaker on concurrency.)

### What DBMS does this project use? Why? Why not an alternative?
**PostgreSQL** in production. Why: fully ACID/reliable, free and open-source, feature-rich (real ENUM types for roles/statuses/formats, native UUID, JSON/JSONB, strong indexing), and excellent concurrency via MVCC (readers don't block writers — vital for many simultaneous users). Why not alternatives: MySQL is fine but historically weaker on some standards/features; NoSQL (MongoDB) is the wrong fit for highly relational, transactional data; SQLite (used in tests for speed/hermeticity) lacks a server and strong concurrency for production. The ORM abstracts the engine, which is what lets tests swap in SQLite.

### Why UUIDs and not integers?
- **No coordination to generate** — a random UUID (128-bit, `uuid.uuid4()`) is astronomically unlikely to collide, so any process (even the backend before touching the DB) can mint an id without asking a central counter.

·

- **No information leak** — sequential integers reveal row counts and let attackers enumerate ids (`/devices/41`, `/42`); UUIDs are unguessable, closing enumeration attacks (defense in depth, not a substitute for ownership checks).

·

- **Safe to merge across systems** — integers from two databases clash; UUIDs don't.

Trade-offs: UUIDs are bigger (16 vs 4–8 bytes) and random, so naive indexing is slightly less cache-friendly — negligible at this scale.

---

## PART 5 — Security

### How do we handle authentication and authorization? Why this method?
Authentication: username/password → bcrypt verify → issue access (30 min) + refresh (7 day) JWTs; client sends the access token on every request; server verifies signature/expiry statelessly. Authorization: RBAC role guards (`require_admin`/`require_operator`) + per-row ownership checks + share grants. Why JWT over sessions: HTTP is stateless, and JWTs are self-contained and signed so any backend copy verifies them with just the secret key — stateless, horizontally scalable, no session store. The access/refresh split limits leak damage while avoiding constant re-login. (See Part 1 for full pros/cons.)

### What hashing tool do we use for passwords? How does it work?
**bcrypt** (via **passlib**'s `CryptContext`). bcrypt is purpose-built for passwords: deliberately **slow** (resists brute force) and includes a per-password random **salt** mixed in, so two users with the same password get different hashes and precomputed "rainbow tables" don't work. It has an adjustable **work factor** to stay slow as hardware speeds up. The stored string bundles algorithm + cost + salt + hash. To verify, you re-hash the submitted password with the stored salt and compare in constant time — it never reverses the hash (hashing is one-way).

### Difference between encryption and hashing.
**Hashing** is one-way: easy forward (`password → hash`), practically impossible to reverse. Correct for passwords — you only ever need to *verify*, never recover the original; a leak reveals nothing usable. **Encryption** is two-way/reversible, keyed by a secret — you can get the original back. Correct for device credentials, because the worker must replay the actual password to open an SSH session. Same category ("protect secrets at rest"), opposite mechanism, dictated by the requirement.

### Explain JWTs in detail.
A **JSON Web Token** is a string of three dot-separated, base64 parts: `header.payload.signature`.
- **Header** — the signing algorithm (HS256 here).

·

- **Payload** — JSON **claims**: `sub` (subject = user id), `type` (access/refresh — checked so a refresh token can't be used as an access token), `iat` (issued-at), `exp` (expiry — what makes it stop working), plus a custom `role` hint.

·

- **Signature** — a cryptographic stamp the server creates with its **secret key** (HMAC-SHA256). 

Anyone can *read* a JWT (it's base64, **not encrypted** — never put secrets in it), but only the holder of the secret key can produce a valid signature. On each request the server re-checks the signature and expiry; if valid, it trusts the claims without a session lookup → stateless. The app still loads the live user and checks the DB role on protected routes, so a stale `role` in an old token can't escalate privileges. Access (30 min) + refresh (7 day) tokens balance security and convenience.

### What ORM do we use? Why? Pros and cons.
**SQLAlchemy 2.0** (async). An ORM maps tables/rows/columns onto classes/instances/attributes and generates SQL for you. Why: industry-standard Python ORM, the 2.0 async API pairs with FastAPI's async model, database-agnostic (Postgres in prod, SQLite in tests), and it uses **parameterized queries** so user input is never interpreted as SQL (structural protection against **SQL injection**).
- *Pros:* type-safe, injection-safe, DB-agnostic data access; sessions (unit of work + transactions); relationships (navigate `config.owner` instead of writing joins).

·

- *Cons:* "magic" you must understand (when it hits the DB, lazy vs eager loading, the N+1 problem); a learning curve; sometimes you still drop to SQL for complex queries.

---

## PART 6 — Async, Redis, queues

### How do we achieve async?
The web layer is async end to end: FastAPI on an event loop, `async def` routes, `await`ed DB calls via asyncpg + SQLAlchemy 2.0 async. One process handles many concurrent I/O-bound requests because waiting requests yield to others. Slow blocking device work is offloaded to the Celery worker (separate process), so it never blocks the event loop. Celery tasks bridge to async code with `asyncio.run(...)`.

### What do we use Redis for and why?
Three roles: (1) Celery **broker** (the queue carrying job messages from API to worker, Redis DB 0); (2) Celery **result backend** (stores task status/return values, DB 1); (3) general **cache** (cache-aside helpers with TTL, DB 2). Why Redis: it's a fast, shared, external in-memory store every process can reach over the network — a Python dict couldn't be shared across the separate API and worker processes. Separate logical DBs keep the three concerns from colliding.

### Explain producer, broker, consumer — and what they are here. Why this way?
- **Producer** — drops "please do this" messages onto the queue. Here: the **FastAPI backend** (when it enqueues a job).

·

- **Broker** — holds the line/queue. Here: **Redis**.

·

- **Consumer/worker** — picks up messages and processes them. Here: the **Celery worker**.

Why: (1) **responsiveness** — slow work doesn't block the user's request; the producer enqueues and returns `202` instantly. (2) **resilience** — if all workers are busy, tasks wait safely instead of being lost; a crashed task can be re-delivered. (3) **independent scaling** — run more workers vs more web processes depending on load. The queue carries only an id; the worker re-reads truth from Postgres.

### What is the task-queue framework? Why, alternatives?
**Celery** — the de-facto Python distributed task queue. You decorate a function with `@celery_app.task`; calling `.delay(args)` serializes the args and pushes a message onto the broker instead of running now; a worker pops it and runs it. Chosen because it's mature, integrates with Redis, and is the standard Python way to run background jobs. Alternatives: RQ (simpler, Redis-only), Dramatiq, ARQ (async-native), cloud queues (SQS+Lambda).

### Does the queue store the actual result of a job? If not, what, and how does the result reach the frontend?
No — the queue (broker) carries only the task message (the **job id** and a name/flag), never the heavy result. Celery's separate **result backend** can store a task's return/status, but this project **doesn't rely on it** for results. Instead, the worker re-reads the job from Postgres, does the work, and writes the result (status, `log`/`error`, the new config row) back into **PostgreSQL** — the single source of truth. The frontend learns the outcome by **polling** `GET /jobs` via the API (every 4s), reading the database state — never by reading Celery's result backend.

---

## PART 7 — Frontend concepts

### Explain the DOM.
The **Document Object Model** is the browser's live, in-memory tree of the page's elements. JavaScript changes the DOM to change what you see on screen. React keeps a lightweight copy (the "virtual DOM") and computes the minimal real-DOM updates when your data changes.

### Explain React.
A library for building UIs as a tree of **components** — functions that take inputs (**props**) and return a description of UI written in **JSX** (HTML-like syntax in JS). React is **declarative**: you describe what the UI should look like for the current data, and React figures out the DOM changes. **Hooks** (`useState`, `useEffect`, `useContext`) manage state and side effects. It's the dominant way to build SPAs.

### Explain State.
**State** is data that can change over time and, when it does, should re-render the UI. React's `useState` hook holds a piece of state; calling its setter triggers a re-render of the components that use it. *UI is a function of state* — flipping `user` from `null` to an object is what makes `App.tsx` switch from login to the app. The project distinguishes **server state** (cached/shared/refetched by TanStack Query) from **local UI state** (ephemeral, per-screen, in `useState` — e.g. "is the dialog open").

### Explain TypeScript.
JavaScript plus a **static type system**. You annotate values with types (`string`, `number`, custom `interface`s mirroring the API JSON), and a compiler catches type mismatches *before* the code runs — the same safety idea as Python type hints, but stricter and compiled away before shipping. The frontend's `types.ts` mirrors the backend Pydantic schemas so the contract is explicit and the two ends stay in sync.

### Explain TanStack Query.
(React Query) A data-fetching library that manages **server state**: it fetches, **caches**, dedupes, and **re-fetches** (including **polling** on an interval) API data, exposing `{ data, isLoading, error }` so components don't hand-roll that plumbing. You describe data with a **query key** (cache identity) and a fetch function. `useMutation` handles writes; `onSuccess: invalidateQueries(...)` marks cache keys stale so reads auto-refetch (the invalidate-on-mutation pattern). The jobs hook uses `refetchInterval` to watch background jobs.

### Explain Material UI.
**MUI** is a React component library implementing Google's Material Design — ready-made buttons, tables, dialogs, app bars, etc. — so the app looks consistent and accessible without hand-writing CSS. The app wraps everything in a `ThemeProvider` and uses these components throughout (e.g. `AppLayout`'s AppBar/Drawer, page tables, dialogs, the loading `CircularProgress`).

### Explain Vite.
The frontend **build tool / dev server**. In development it serves code instantly with hot reload; for production it **bundles** and minifies TypeScript/React into a few optimized static files. `vite.config.ts` configures it; `npm run dev` starts the dev server; `npm run build` produces the bundle that goes into the nginx image. It also exposes build-time env vars like `import.meta.env.VITE_API_BASE_URL`.

### Explain React Router.
Client-side routing: it maps URL paths (`/devices`, `/configs`) to which component to render, giving the SPA multiple "pages" without server round-trips. `<Routes>`/`<Route>` declare path→component; `<Navigate>` redirects; `<Link>` changes the URL without a reload. In `App.tsx` it doubles as the auth gate (protected routes aren't in the table until you're logged in).

### Explain Axios.
The HTTP client that actually calls the backend. One shared instance is configured with the API base URL and two **interceptors**: a request interceptor that injects `Authorization: Bearer <token>` on every call, and a response interceptor that transparently refreshes the access token on a `401` (calling `/auth/refresh`, replaying the original request, deduping concurrent refreshes, and firing a `gc:logout` event if refresh fails). It wraps `JSON.stringify`/`parse` for serialization.

---

## PART 8 — Containers, orchestration, observability

### Do we use containers? Which? Why? Pros/cons. Explain the container.
Yes — **Docker**. A container packages a process with everything it needs (runtime, libraries, files) into an isolated unit that runs identically anywhere, lighter than a VM because it shares the host OS kernel. The repo has a backend `Dockerfile` and a multi-stage frontend `Dockerfile`; `docker-compose.yml` runs the whole six-service stack. Why: reproducibility ("the exact image tested in CI is what runs in production") and frictionless onboarding (`git clone` → `docker compose up`).
- *Pros:* identical environments everywhere, fast startup, isolation, easy scaling.

·

- *Cons:* added build/runtime complexity, image management, a learning curve. *Alternatives:* VMs (heavier), bare-metal installs (drift-prone), Podman.

### What is a Docker image?
A built, immutable, read-only snapshot of "app + environment" — the template. A **container** is a running instance of an image (image is to container as class is to object). You build an image from a `Dockerfile` (a recipe of steps: start from a base image, copy code, install deps, set the start command).

### What is Docker Compose?
A tool that runs several containers together from one `docker-compose.yml`, wiring up their networking (service discovery by name), environment variables, volumes (persistent data), health checks, and start order. `docker compose up` brings the whole stack (Postgres, Redis, backend, worker, frontend, observability) to life with one command. The backend and worker build the *same* image but run different commands (uvicorn vs `celery worker`).

### Explain Kubernetes.
A production-grade **container orchestrator** that runs containers across a cluster of machines. It's **declarative**: you describe the desired state ("3 backend replicas") and Kubernetes continuously reconciles reality to match — restarting crashed containers, rescheduling on node failure, rolling updates, scaling, service discovery, and load balancing. The repo ships manifests in `deploy/k8s/`: Namespace, ConfigMap/Secret, StatefulSets+PersistentVolumes for Postgres/Redis, Deployments+Services for backend/worker/frontend, with **liveness** probe→`/health` and **readiness** probe→`/ready`.

### Explain Helm chart.
Helm is "a package manager for Kubernetes." A **chart** is a packaged, parameterized k8s app: `Chart.yaml` (metadata), `values.yaml` (defaults like image tags/replica counts), and `templates/` (manifests with `{{ .Values.xxx }}` placeholders). `helm install` (optionally `--values prod.yaml`) renders the templates into final manifests and applies them — so one chart deploys to every environment, differing only by a values file. It turns "deploy the app" into one repeatable, versioned command.

### What is observability, the three pillars, how we achieve them, and is it required?
Observability is making a system's internal state visible from outside. Three pillars:
- **Logs** — timestamped event records. Achieved with **structlog** (structured key–value/JSON logs; pretty in dev, JSON in prod), written to stdout.

·

- **Metrics** — numeric measurements over time. Exposed in **Prometheus** format at `/metrics`; Prometheus scrapes and stores; **Grafana** dashboards visualize.

·

- **Traces** — the path/timing of a single request through the system. Optional **OpenTelemetry** traces to an OTel Collector.

The user does **not** have to have these: observability is **optional and best-effort** — `observability.py` wraps instrumentation in `try/except` and gates tracing behind `OTEL_ENABLED`, so if the libraries aren't installed or the flag is off, it silently no-ops and the core app runs fine (graceful degradation).

---

## PART 9 — Glossary terms (what is X?)

### What is an Abstract Base Class (ABC)?
A Python class that can't be instantiated directly and declares methods subclasses *must* implement (via `@abstractmethod`). It defines a contract. Here, `BaseDriver` is an ABC declaring `test_connection`/`backup`/`apply`/`sample_config`, so callers can rely on the interface without knowing the concrete class.

### What is Alembic / a database migration?
**Alembic** is the migration tool for SQLAlchemy. A **migration** is a versioned, ordered, reversible script that evolves the database schema (create/alter/drop tables, add indexes) — version control for your tables. You never edit the live schema by hand; you write or autogenerate a migration and apply it with `alembic upgrade head`, which runs automatically at container startup before seeding and serving. Each migration links to its parent, forming an ordered chain, and can be rolled back.

### What is an audit log?
An append-only record of who did what and when (logins, device/config/user creation, share decisions) for security and compliance. It's written by `audit_service` after meaningful actions. The `actor_id` foreign key uses `SET NULL` on delete so the log survives even if the acting user is later removed.

### What is a Bearer token?
An access token sent in the `Authorization: Bearer <token>` header — whoever "bears" (holds) it is granted access, like cash. The app's JWTs are bearer tokens; the Axios request interceptor attaches one to every call.

### What is cache-aside (and TTL)?
**Cache-aside** is a caching pattern: check the cache first → on a miss, compute/fetch the value and store it with a **TTL** → on a write that changes the data, invalidate the cached copy. The **TTL (time-to-live)** is an expiry after which the value auto-deletes, so stale data isn't served forever. Redis provides this toolkit, used sparingly on purpose.

### What is CI (Continuous Integration)?
Automatically building and testing code on every push/PR so breakage is caught before merge. Implemented with **GitHub Actions**: on each push it lints (ruff), type-checks (mypy), and runs the backend tests against real Postgres and Redis, plus lints/tests/builds the frontend and builds the images. It's the safety net that lets many people change the codebase without breaking `main`.

### What is a ClassVar?
A type hint marking an attribute that belongs to the *class* (shared by all instances), not to each instance. Driver metadata like `platform` and `config_format` are `ClassVar`s because they describe the driver *type* itself, not a particular object.

### What is the composition root?
The single place where all the separate modules are wired together into a running application. Here it's `main.py`'s `create_app()` — it builds the FastAPI app, attaches middleware (CORS), includes the routers, and configures startup. Keeping wiring in one place keeps the rest of the code decoupled.

### What is CORS?
**Cross-Origin Resource Sharing** is a browser security rule: a page served from one origin (e.g. `localhost:5173`) can't call a different origin (the API on `localhost:8000`) unless the server returns headers permitting it. The backend's CORS middleware allows the frontend origin. Key nuance: CORS protects *users* and is enforced by the *browser*, not the server — non-browser clients (curl, scripts) ignore it.

### What is CRUD?
Create, Read, Update, Delete — the four basic data operations, mapped in REST to POST/GET/PATCH (or PUT)/DELETE and underneath to SQL INSERT/SELECT/UPDATE/DELETE.

### What is a dataclass?
A Python class whose boilerplate (`__init__`, `__repr__`, equality) is auto-generated from simple field declarations. `DeviceTarget` and `ApplyResult` are dataclasses — lightweight typed data carriers passed between the service and driver layers.

### What does "declarative" mean?
Describing *what* you want, not *how* to achieve it. React UIs ("the UI for this state looks like this"), SQLAlchemy models, and Kubernetes manifests ("I want 3 replicas") are declarative — you state the desired result and the system figures out the steps.

### What is dependency injection (DI)?
A pattern where the framework provides ("injects") the things a function needs instead of the function constructing them itself. FastAPI's `Depends(...)` injects the database session, the current user, and the role guards into routes. DI decouples code and creates seams — e.g. tests override `get_db` to point the whole app at a test database.

### What is a Dockerfile?
A recipe for building a container image, one instruction per line (start from a base image, copy files, install dependencies, set the start command). The backend and frontend each have one; `docker build` runs it to produce the image.

### What is eager vs lazy loading?
Two ways an ORM fetches related rows. **Lazy**: load related data on first access (a separate query each time — can cause N+1). **Eager**: fetch related rows up front in one batched query (`selectinload`). Async SQLAlchemy needs eager loading before serializing nested relationships, because a lazy load during serialization would trigger I/O the async session can't do transparently.

### What is an Enum?
A type whose value must be one of a fixed, named set. Roles (admin/operator/viewer), job statuses (pending/running/succeeded/failed), and config formats are enums, giving both the database and the code a closed, valid vocabulary and making illegal values impossible.

### What is an environment variable (and 12-factor config)?
A setting passed to a process by its environment rather than hard-coded in source. The `Settings` object reads them (with defaults and validation) so the *same* image runs differently in dev, CI, and prod just by changing the environment. This is the Twelve-Factor App principle: store config in the environment, keep secrets out of source.

### What is a pytest fixture?
A reusable setup function pytest injects into a test by name. The app, HTTP client, and DB-session fixtures build the test world (a fresh schema, an in-memory database, a logged-in client) so each test starts from a known state without repeating setup code.

### What is a foreign key?
A column in one table that stores the primary key of a row in another table, encoding a relationship and enforcing referential integrity (the DB refuses to point at a non-existent row). Example: `device.owner_id → users.id`. The `ON DELETE` rule (CASCADE or SET NULL) says what happens to the child when the parent is deleted.

### What is a health probe (liveness vs readiness)?
Endpoints an orchestrator polls. **Liveness** (`/health`) = "is the process alive?" — if it fails, Kubernetes restarts the pod. **Readiness** (`/ready`) = "can I actually serve traffic?" — it checks dependencies (DB + Redis); if they're down, Kubernetes stops routing users to the pod without killing it. You need both because a pod can be alive but not yet ready.

### What is idempotency (in the seed script)?
An idempotent operation can be run repeatedly with the same effect as running it once. The seed script checks whether the admin/demo data exists before creating it, so it's safe to run on every container startup without crashing on duplicate-key errors.

### What is JSX?
HTML-like syntax written inside JavaScript/TypeScript that compiles to function calls building the UI tree. React components return JSX (e.g. `<Button>Save</Button>`), which is why markup and logic live together in one component.

### What is localStorage?
Browser key–value storage that persists across page reloads (unlike in-memory state). The frontend stores the two JWTs there so the session survives a refresh. Trade-off: it's readable by any JavaScript on the page, so it's XSS-exposed — mitigated by React escaping output by default.

### What is middleware?
Code that wraps every request/response to handle cross-cutting concerns. The CORS middleware is one example; logging or metrics middleware are others. It runs before/after your route logic without each route having to call it.

### What is a mixin?
A class that provides shared methods to be combined into other classes via inheritance (not meant to stand alone). `NetmikoDriver` is a mixin holding shared SSH I/O reused by the concrete SSH drivers; the `UUIDPrimaryKeyMixin`/`TimestampMixin` add common columns to every model.

### What is monkey-patching?
Replacing a function or attribute at runtime, typically in tests. The integration tests monkey-patch `job_service.dispatch` so jobs run inline instead of being sent to a real Celery broker/worker — letting the full HTTP flow be tested with no infrastructure.

### What is the N+1 query problem (and a subquery)?
**N+1** is when you issue one query to get a list, then one more query *per item* to load related data — N+1 queries total, which kills performance. The code avoids it two ways: `config_service.list_accessible` fetches owned-or-granted configs in a single statement using a **subquery** (a query nested inside another) plus `OR`, and `share_service` uses `selectinload` to eager-load the requester in one batched query.

### What is nginx?
A fast web server / reverse proxy. In the frontend container it serves the built static SPA files and proxies API routes to the backend. It's the production web server in front of the React app.

### What is OpenAPI / Swagger?
A machine-readable description of the API that FastAPI auto-generates from your typed routes and Pydantic schemas, rendered as interactive docs at `/docs`. You get accurate, always-up-to-date documentation (and a "try it" UI) for free.

### What is a React Context Provider?
A component that makes a value/capability available to all nested components without passing props down every level. `main.tsx` nests several: QueryClient (TanStack Query), Theme (MUI), Router, and Auth providers — so any component can read the logged-in user or run a query.

### What is Pydantic?
A Python library for typed data validation and serialization. Schemas are Pydantic models that validate incoming JSON at the API boundary (rejecting bad input with a `422` before your code runs) and shape outgoing JSON. Its v2 core is written in Rust, so it's fast, and FastAPI uses it for both validation and auto-generated docs.

### What is the registry pattern?
A central map of key → implementation that classes add themselves to. Here a module-level dict maps platform string → driver class, populated by the `@register` decorator at import time. `get_driver()` looks up the class by platform. It makes the system extensible without editing existing code — adding a platform is purely additive.

### What is the difference between a Schema and a Model here?
**Model** (SQLAlchemy) = the database/storage shape (a table). **Schema** (Pydantic) = the wire/API shape (validated JSON in and out). They're kept separate so storage and API can evolve independently and secrets never leak — the `User` model has `hashed_password` but `UserRead` omits it; the `Device` model stores `encrypted_secret` but the schema exposes only a `has_secret` boolean.

### What is the service layer?
HTTP-ignorant modules that hold the business logic (the rules and verbs: create, list, decide, dispatch). Because they don't import FastAPI or touch the request object, they're reusable by the routes, the Celery worker, and the seed script, and testable as plain Python functions.

### What is uvicorn (and ASGI)?
**uvicorn** is the **ASGI** server that runs the FastAPI app — the process that listens on a port, accepts TCP connections, parses HTTP, and drives the async event loop. **ASGI** (Asynchronous Server Gateway Interface) is the standard contract between an async Python web app and the server that runs it, so you can swap servers without changing app code. FastAPI is the app; uvicorn is the engine that serves it.

---

## PART 10 — More interview-style questions

### Why version the API path with /api/v1?
So you can introduce breaking changes later as `/api/v2` while existing clients keep using `/api/v1`. It's a contract-stability decision — you never force every consumer to update in lockstep with the server. The router structure makes mounting a parallel `v2` straightforward.

### Why does the login endpoint use form-encoding instead of JSON?
Because it implements the OAuth2 "password" flow via FastAPI's `OAuth2PasswordRequestForm`, which by standard expects an `application/x-www-form-urlencoded` body with `username`/`password` fields. This makes the `/docs` "Authorize" button work and matches the OAuth2 convention. It's the one deliberate exception to the otherwise JSON-everywhere API.

### Why a relational database here rather than NoSQL?
The data is highly relational and benefits from integrity guarantees: users own devices, devices produce configs, jobs reference devices and configs, shares link users to configs. Foreign keys enforce valid references and transactions give atomicity for multi-step operations like accepting a share. The structure is known and consistency matters, so a relational DB with SQL is the natural fit.

### How does the app change the database schema safely in production?
With Alembic migrations — versioned, ordered, reversible scripts checked into git like any other code. You never edit the live schema by hand; you write or autogenerate a migration and apply it. `alembic upgrade head` runs automatically at container startup, before seeding and serving, so every deployment brings the schema up to date in place without dropping data.

### How does the system resist someone tampering with a JWT?
The token is signed with the server's secret using HS256. If anyone alters the payload (e.g. changes their role to admin), the recomputed signature no longer matches and `decode_token` raises → `401`. They can't forge a valid signature without the secret. Also, role guards check the *database* role, not just the token claim, so even a valid-but-stale token can't preserve revoked privileges.

### Why store JWTs in localStorage, and what's the risk?
localStorage persists across reloads, so the session survives a refresh. The trade-off: it's readable by any JavaScript on the page, so it's vulnerable to XSS — mitigated by not having XSS (React escapes rendered content by default, plus a Content-Security-Policy). The alternative is httponly cookies (invisible to JS) at the cost of CSRF handling. The project chose localStorage for simplicity; articulating that trade-off is the point.

### How does the app guard against username enumeration on login?
`authenticate` returns the same `None` whether the username doesn't exist or the password is wrong, so the route returns an identical `401` either way — an attacker can't tell which usernames are valid. Failed logins are also audited (with the attempted username but a null actor), leaving a trail for brute-force attempts.

### Why pass only the job id to the worker instead of the whole job object?
The worker runs in a *different process* and shares no memory with the API; the database is the single source of truth both coordinate through. Passing the id forces the worker to re-read the authoritative, current state from Postgres, avoiding stale data. (Also, Celery serializes args to JSON, so a UUID is passed as a string.)

### Celery tasks are synchronous but your code is async — how is that bridged?
Each task is a thin synchronous function that immediately calls `asyncio.run(...)` on an async implementation. `asyncio.run` spins up an event loop, runs the coroutine to completion, and tears it down — each task invocation gets its own loop. That lets tasks reuse the same async database sessions and services as the rest of the app.

### What happens if a background job fails or hangs?
Every task is wrapped in try/except — on any exception the job is marked `failed` with the error text (shown in the UI) and logged; the worker never crashes silently. For hangs, Celery's `task_time_limit=300` kills any task running longer than five minutes, so a stuck SSH session can't occupy a worker slot forever.

### How does the registry work (driver selection)?
A module-level dict maps platform string → driver class. The `@register` decorator above each driver class runs at import time and inserts the class keyed by its `platform` attribute. `get_driver(target)` looks up the class by platform and instantiates it. A class "announces" the platform it handles just by being decorated — no central list to maintain, and adding a platform is purely additive.

### Why separate Pydantic schemas from SQLAlchemy models?
Storage shape and wire shape should evolve independently, and to prevent leaks. The `User` model has `hashed_password`; `UserRead` omits it, so it's structurally impossible to return. The `Device` model stores `encrypted_secret`; the schema exposes a computed `has_secret` instead. Schemas also carry validation the DB doesn't (username length, port range) and differ by operation — create needs a password, update makes fields optional, read adds server-generated fields.

### How does validation protect the system?
Pydantic validates incoming JSON at the boundary *before any of your code runs*. A bad request (username too short, port out of range, malformed email) gets a clean `422` with field-level errors, and your service logic only ever sees well-formed, typed data. "Validate at the boundary" keeps invalid data from ever reaching business logic or the database.

### What's the difference between ConfigFileRead and ConfigFileSummary?
A deliberate performance decision. A config's content can be large, so the *list* endpoint returns `ConfigFileSummary` (metadata only, no content) — listing 200 configs doesn't ship megabytes. Only the *detail* endpoint returns the full `ConfigFileRead` with content. A lightweight list schema plus a heavy detail schema keeps list endpoints fast.

### What does from_attributes=True do?
It lets a Pydantic model be built from any object with matching attributes — like a SQLAlchemy model — rather than only from a dict. That's what makes `UserRead.model_validate(user_orm_object)` work: Pydantic reads fields off the ORM instance. Every read schema inherits it via the `ORMModel` base.

### How is auth enforced on the frontend, and why isn't that a security risk?
`App.tsx` only includes protected routes in the route table when a user is logged in — otherwise the only reachable route is `/login`. So auth is enforced structurally in the UI. But the frontend isn't the security authority: every API request is independently verified by the backend, which re-checks the user and role on every call. The frontend gate is just UX; bypassing it still hits `401`/`403`.

### Why distinguish "server state" from "UI state" on the frontend?
Server state (devices, jobs, configs) lives in TanStack Query — cached, shared across components, refetched/invalidated. UI state (is this dialog open, what's typed in a form) is ephemeral and local, held in `useState`. Conflating them causes stale or duplicated data; keeping them separate is a key discipline — let the query library own server data, let components own transient UI.

### What are useState and useEffect?
`useState` declares a piece of state whose setter triggers a re-render — UI is a function of state, so flipping `user` from null to an object swaps the login screen for the app. `useEffect` runs side effects after render (API calls, subscriptions) and can return a cleanup function that runs on unmount (used to subscribe/unsubscribe from the `gc:logout` event).

### Why is the frontend Dockerfile multi-stage?
Building React needs Node and hundreds of MB of npm packages, but *serving* the result needs only a static web server. One stage builds the bundle with Node; a second tiny stage copies just the built `dist/` into an nginx image, discarding the toolchain. "Build big, ship small" — the shipped image is small, fast, and has a minimal attack surface.

### Why copy dependencies before code in the backend Dockerfile?
Docker caches image layers. Copying only the dependency manifest and running `pip install` *before* copying the app code means the expensive install layer is cached and only re-runs when dependencies change — a one-line code edit then rebuilds only the fast final layers, dramatically speeding rebuilds.

### What does CI do here and why does it matter?
On every push, GitHub Actions lints (ruff), type-checks (mypy), and tests (pytest) the backend against real Postgres and Redis, lints/tests/builds the frontend, and builds the images. Failures flag the change and can block merging. It's the safety net that lets many people change the codebase without breaking `main` — every change is verified in a clean environment.

### How is the application tested, and why is it testable?
Unit tests (password hashing round-trips, each driver returns mock config) plus integration tests (full HTTP journeys: login, CRUD, jobs, shares, authorization). It's testable by design: integration tests swap the DB for in-memory SQLite via a `get_db` override, stub Celery's `dispatch` to run jobs inline (no broker), and use the mock transport (no devices). Those seams — DI for the session, a substitutable dispatch, a mock transport — were built in so testing is fast and hermetic.

### Why test against in-memory SQLite and real Postgres in CI?
SQLite in-memory makes the suite fast and hermetic — each test starts from a pristine schema that vanishes afterward. But SQLite isn't identical to Postgres, so CI *also* runs the suite against real Postgres and Redis to catch Postgres-specific behavior. Fast local tests for the inner loop, realistic tests in CI for confidence.

### What is dependency injection and how does it help testing?
DI means the framework provides what a function needs rather than the function fetching it — FastAPI injects the database session via `Depends(get_db)`. Because every route gets its session that way, tests override that one dependency to point the *entire* application at a test database without touching any route code. That single seam is what makes the whole app testable.

### Where did this codebase deliberately choose NOT to add complexity, and why?
Caching is the clearest example. Redis and a clean cache-aside toolkit are fully wired in, but used sparingly because the read endpoints are already fast over modest, indexed data — and premature caching introduces the hard problem of invalidation for no benefit. Providing the capability without sprinkling caches everywhere shows judgment: knowing *when not to* cache matters as much as knowing how.

### What's the single most important design idea in the codebase?
Separation of concerns via layering — but the one concrete thing is the **mock-transport driver abstraction**. It delivers extensibility (add a platform = drop in a subclass), polymorphism (one interface over SSH and REST), and above all testability and instant runnability with no real hardware. Everything above it (services, jobs, API, UI, tests) quietly depends on it.

---

## PART 11 — Rapid-fire concept checks (Appendix B)

### Where is the platform-compatibility rule enforced?
In `job_service.create_apply_job`; the route surfaces the resulting `JobError` as a `422`.

### What makes the seed script safe to run on every startup?
It's idempotent — it checks existence before creating, so re-running can't violate unique constraints.

### What does dependency_overrides[get_db] do in tests?
Redirects the entire app onto the test (SQLite) session through one DI swap, without touching any route code.

### Why monkey-patch dispatch in tests?
To run jobs inline without a real Celery broker/worker, so the full HTTP flow is testable with no infrastructure.

### Where does business logic live, and what does it not know about?
In the services; they don't know about HTTP, so they're reusable by routes, the worker, and the seed script.

### What is the composition root?
`main.py`'s `create_app()`, where all modules are wired together — app, middleware, routers, startup.

### Why is the role re-checked from the database, not just the token?
So revoked privileges take effect on the next request — a stale token can't preserve access that was removed.

### What does exclude_unset=True accomplish in updates?
It applies only the fields the client actually sent, giving a true partial update (PATCH semantics).

### What is build_target for?
It decrypts the device secret and packs the connection details into a `DeviceTarget` to hand to a driver.

### What does asyncio.run do in a Celery task?
Bridges the synchronous task to the async implementation by running the coroutine in a fresh event loop.

### What's the cleanest single trace that touches every layer?
Running a backup job — browser → route → service → Redis → worker → driver → Postgres → poll → UI.

---

## PART 12 — Common pitfalls & gotchas (Appendix C)

### Pitfall: returning the ORM model directly from a route.
Returning the SQLAlchemy `User` as JSON would leak `hashed_password`. The rule: always serialize through a read schema that omits secrets. The schema/model separation is a leak-prevention boundary, not bureaucracy.

### Pitfall: lazy-loading a relationship in async code at serialization time.
If `share_service` didn't `selectinload` the `requester`, serializing `ShareRequestRead` (which nests `UserPublic`) would trigger a lazy DB access during rendering — which async SQLAlchemy can't do transparently, raising an error. Whenever a read schema nests a relationship, the query that built it must eager-load that relationship.

### Pitfall: passing whole objects to background tasks.
Handing the worker a full `Job` object risks operating on stale data and breaks JSON serialization. The rule: pass ids, re-read from the database in the worker.

### Pitfall: forgetting key when rendering a React list.
`devices.map(d => <Row/>)` without `key={d.id}` makes React unable to track rows efficiently and causes subtle update bugs. Every list render supplies a stable `key`.

### Pitfall: storing server state in useState.
Copying fetched data into local component state leads to staleness and duplication. The discipline: server data lives in TanStack Query (cached, shared, invalidated); only ephemeral UI state lives in `useState`.

### Pitfall: catching a domain rule in the wrong layer.
If a route hand-checked platform compatibility, the rule could drift from the worker's view. Instead `create_apply_job` owns the rule and raises `JobError`; the route only translates it to `422`. Rules live in services, HTTP codes in routes.

### Pitfall: non-idempotent startup scripts.
A seed that blindly inserts the admin would crash on the second container start with a unique-constraint violation. The seed checks existence first, so it's safe on every boot.

### Pitfall: hard-coding configuration.
URLs, secrets, and credentials baked into code can't change per environment and leak in version control. `Settings` reads them from the environment with defaults, so the same image runs anywhere.

### Pitfall: editing the production schema by hand.
Manual SQL is unrepeatable and untracked. Every schema change is a reviewed, versioned Alembic migration applied automatically at deploy time.

### Pitfall: premature caching.
Adding caches everywhere creates invalidation bugs for no benefit when queries are already fast. The repo provides the cache toolkit but uses it sparingly, on purpose.

### Pitfall: treating the frontend as the security authority.
If the backend trusted the frontend's auth gate, anyone could bypass the UI and hit the API directly. The backend independently verifies the JWT and re-checks role/ownership every request; the frontend gate is purely UX.

### Pitfall: blocking the event loop with sync I/O.
A synchronous, blocking DB or network call inside an async route would stall the whole event loop, defeating async. The backend uses async drivers (asyncpg, aioredis, httpx) and offloads genuinely blocking device I/O entirely to the Celery worker.

> The pattern across all of these: every pitfall has a corresponding *structural* choice that makes the mistake hard to make — schemas that can't leak, services that own rules, ids passed to workers, DI seams for tests. Good architecture shapes the code so the easy path is the correct path.

---

## PART 13 — Deeper dives on the hardest concepts (Appendix D)

### Deep dive: what actually happens over the network (TCP, ports, HTTP)?
Every machine has an **IP address**; a **port** (0–65535) identifies which program on it — backend `8000`, Postgres `5432`, Redis `6379` (which is why `DeviceCreate` bounds `port` to 1–65535). Before any HTTP, client and server establish a **TCP** connection (a reliable, ordered byte stream via the SYN→SYN-ACK→ACK handshake; TCP retransmits lost bytes). In production the connection is wrapped in **TLS** (the "S" in HTTPS, port 443) so eavesdroppers see ciphertext and the server is authenticated by certificate. The **HTTP request** itself is just text over that connection: a request line (`POST /api/v1/devices HTTP/1.1`), headers, a blank line, then the JSON body; the response mirrors it (status line, headers, body). uvicorn accepts the TCP connection, parses the HTTP text into Python objects for FastAPI, and writes the response back as HTTP text.

### Deep dive: how does bcrypt actually protect passwords?
A **hash** is one-way: easy to compute `hash(password)`, infeasible to invert, so a thief gets hashes not passwords; at login you hash the input and compare. A **salt** (random bytes mixed in before hashing, stored inside the hash) makes the same password hash differently per user, defeating precomputed "rainbow tables" and forcing each password to be attacked individually. **Deliberate slowness** via a tunable **work factor** makes each hash take ~100 ms — invisible for one login but making mass guessing thousands of times slower, turning a feasible attack infeasible (raise the cost as hardware improves). `verify_password` extracts the salt from the stored hash, re-hashes the input with it and the same cost, and compares — it never "decrypts," because there's nothing to decrypt.

### Deep dive: how is a JWT signed and verified?
A JWT is `header.payload.signature`. The first two parts are base64url-encoded JSON — *not encrypted*, just encoded, so anyone can read the user id/role/expiry. Security is entirely in the **signature**: `HMAC_SHA256(base64(header) + "." + base64(payload), secret)`. HMAC is a keyed hash — only someone with the secret can produce a signature matching the message. To verify, the server recomputes the HMAC over the received header+payload with its secret and checks it equals the token's signature; if an attacker changed the payload, it won't match, because they can't recompute a valid signature without the secret. So tampering is detectable and forgery infeasible. Because the server stores nothing and re-verifies on each request, auth is stateless and scales across many instances. The `exp` claim makes tokens expire; you never put secrets in the readable payload, and the backend re-checks the live DB role rather than trusting the token's role outright.

### Deep dive: why do database indexes make lookups fast (B-trees)?
Without an index, `WHERE username = 'admin'` requires a **full table scan** — reading every row, O(n). A **B-tree index** keeps the column's values in a balanced, sorted tree; searching it is like a phone book — each step eliminates a large fraction of remaining entries, so lookup is **O(log n)** (~23 steps for 10 million rows instead of 10 million). Trade-offs: an index is extra storage and every write must also update it, slightly slowing INSERT/UPDATE/DELETE — so you index only the columns you filter/join on frequently (`username`, `owner_id`) and leave the rest unindexed. `UNIQUE` constraints are enforced *by* an index too, which is why unique columns are also indexed.

### Deep dive: the event loop — how does one thread serve many requests?
Synchronous (blocking) I/O wastes a thread: it sends a query then *sleeps* doing nothing until the answer returns; serving hundreds of concurrent requests that way needs hundreds of memory-heavy threads. An **event loop** is a single thread running "is any awaited operation ready? resume that coroutine; otherwise keep going." When a coroutine hits `await db.execute(...)`, it *yields control back to the loop* instead of blocking, so the loop runs *other* requests while this one waits, resuming it when its data arrives. Because web work is mostly *waiting* on I/O, one thread stays busy and handles huge concurrency with little memory. The catch: never block the loop — a synchronous slow call that doesn't `await` freezes every request, which is why the backend uses async drivers throughout and offloads blocking device I/O to the worker. `async`/`await` is "viral" because to yield at an I/O point a function must be `async def` and all its callers must `await` it.

### Deep dive: ACID — what do transactions really guarantee?
**Atomicity** — all-or-nothing; accept-share (mark accepted + insert grant) fully happens or fully rolls back. **Consistency** — every transaction respects all constraints (FKs, uniqueness, not-null); you can't commit a `device.owner_id` pointing at a non-existent user. **Isolation** — concurrent transactions don't see each other's half-finished work; they appear to run one at a time, so two simultaneous accepts don't corrupt each other. **Durability** — once committed, data survives crashes (written to disk). The app *relies* on these: sharing rules assume FKs hold, the accept handshake assumes atomicity, concurrency assumes isolation, and a committed backup must not vanish. A non-transactional store would force you to reimplement these by hand, badly — the concrete reason a relational DB is the right call.

### Deep dive: what does docker compose up do, step by step?
(1) **Read** `docker-compose.yml` into services, a private network, and named volumes. (2) **Build images** for `build:` services (using the layer cache) and **pull** `image:` ones (postgres, redis). (3) **Create** the private bridge network (services resolve each other by name) and the `pgdata` volume. (4) **Start in dependency order** (`depends_on`): Postgres and Redis first, then the backend (whose command runs `alembic upgrade head` → `python -m app.initial_data` → `uvicorn`), the worker (`celery ... worker`), the frontend, and observability. (5) **Wire ports** so `localhost:8000`/`localhost:5173` reach the right containers. (6) **Stream logs** from every container into your terminal. The result is the whole system — built, migrated, seeded, networked, serving — from one command. `docker compose down` reverses it, keeping the `pgdata` volume unless you remove it.

### Deep dive: producer/consumer and back-pressure — why do queues scale?
**Decoupling rates** — the API (producer) accepts job requests faster than slow devices can be contacted (consumer); the queue absorbs the difference and the producer never waits. **Independent scaling** — run more worker containers and they all pull from the same Redis queue, sharing load automatically; the API scales with user traffic, workers scale with device-operation volume. **Resilience** — if all workers are down, jobs sit safely in the queue and run when one returns; an API restart doesn't lose queued work (it's in Redis/Postgres, not API memory). **Back-pressure** — if work outpaces workers, the queue visibly grows, signaling "add workers," whereas a synchronous design would just time out with no clear cause. **Why polling fits** — the result lands in Postgres asynchronously, so the client polls (cheap, stateless, fine at a 4-second cadence); pushing over WebSockets would add persistent-connection machinery this app doesn't need.

---

## PART 14 — Scenario & system-design questions (Appendix E)

### Scenario: backups are "stuck on pending forever." How do you diagnose it?
"Pending forever" means the job row was created and dispatched but no worker moved it to `running`, so check the *consumer* side first: is the Celery worker process running and connected to Redis (`docker compose logs worker`)? If it's down or can't reach the broker, messages queue untouched. Then confirm the message reached Redis (the API's `dispatch` step) and check worker logs for a startup exception (e.g. it couldn't import the tasks module). The architecture makes this tractable because the stages are explicit — row created (Postgres), message enqueued (Redis), consumed (worker) — so you inspect each boundary; the `/ready` probe also tells you if Redis is reachable.

### Scenario: the app is slow under load. Where do you look and what do you change?
First *measure* with the observability stack (structlog request logs, Prometheus latency metrics) to find *which* endpoints are slow and whether the bottleneck is the database, the event loop, or downstream. Common fixes: (1) a missing index on a filtered column → add one via a migration; (2) an N+1 query → batch it with a subquery or `selectinload`; (3) the event loop blocked by something synchronous → move it to the worker; (4) genuinely expensive repeated reads → add caching with a TTL using the existing Redis toolkit. Resist caching first — it's the last resort because of invalidation cost.

### Scenario: add scheduled nightly backups for every device. Design it.
Add a **Celery beat** (periodic scheduler) that, on a cron schedule, enumerates devices and calls the *same* `job_service.create_backup_job` + `dispatch` the API route already uses — reusing the HTTP-ignorant service layer rather than duplicating logic. No new driver, model, or route work is needed for the core; optionally add a `backup_schedule` field to the device model (with a migration) for per-device schedules and surface it in the UI. That the answer is mostly "reuse existing services" is evidence the layering is right.

### Scenario: a security review says JWTs in localStorage are an XSS risk. How do you respond?
Acknowledge the trade-off honestly: localStorage is readable by any JS, so an XSS bug could exfiltrate tokens. The current mitigation is to prevent XSS (React escapes output by default; add a Content-Security-Policy). The alternative is **httponly cookies** (invisible to JS), which closes the XSS exfiltration path but opens CSRF, requiring CSRF tokens or `SameSite` settings and changes to how Axios attaches credentials. Both are defensible; cookies are more secure but more complex. For sensitive production data I'd likely move to httponly + SameSite cookies.

### Scenario: support 100 worker machines processing jobs. How?
The architecture already supports it: workers are stateless consumers that pull from the shared Redis queue and coordinate only through Postgres. Run more worker containers/pods — in Kubernetes, scale the worker Deployment's replicas — and they all draw from the same queue, sharing load automatically. The constraints then become the *shared* resources: Postgres connection limits (tune the pool, possibly add PgBouncer) and Redis throughput. No code changes are needed to scale workers horizontally — the payoff of decoupling them from the API.

### Scenario: configs must be versioned with full history, not just a counter.
Today `ConfigFile.version` is just an incrementing integer. For full history, add a `config_file_versions` table (config_file_id FK, version number, content, created_at, created_by) and, in `config_service.update`, insert a new version row instead of overwriting `content`, pointing the config at the latest. Expose a `/configs/{id}/versions` endpoint and a diff between versions. It's an additive change: one migration, one service change, new read schemas and routes — no churn elsewhere, thanks to the layering.

### Scenario: roll out a breaking API change without breaking the existing frontend.
That's why the API is versioned at `/api/v1`. Introduce the breaking change under `/api/v2`, leaving `/api/v1` intact so the current frontend keeps working; the router structure makes mounting a parallel `v2` straightforward. Then migrate the frontend to `v2` and, once nothing uses `v1`, deprecate and remove it. The principle: additive, versioned changes over in-place breaking ones.

### Scenario: Postgres goes down briefly in production. What happens?
The `/ready` readiness probe pings the database, so when Postgres is unreachable readiness fails and Kubernetes stops routing new traffic to affected pods — a fast clear failure rather than hung requests. In-flight requests error out (no session). Background jobs mid-flight fail and are marked `failed` with the error (the worker's try/except), visible to the user to retry later; queued messages sit safely in Redis. When Postgres recovers, readiness passes, traffic resumes, and users re-run failed jobs. Durable shared stores plus explicit failure handling make recovery graceful instead of a cascade.

### Scenario: add a "viewer can comment on a config" feature. Walk the layers.
Bottom-up, following the build order: (1) a `Comment` model (FK to config and user, body, timestamps) + migration; (2) `Create`/`Read` schemas; (3) a `comment_service` with the rule "you may comment if you have *read* access," reusing `config_service.user_has_access` so sharing rules apply automatically; (4) routes `POST /configs/{id}/comments` and `GET /configs/{id}/comments` authorizing via the existing `_get_readable_or_404` helper; (5) frontend `useComments`/`useAddComment` hooks and a comments panel, with the mutation invalidating the comments query. Most of it is *reuse* — the access predicate, route helpers, hook pattern — which is the point of consistent layering.

### Scenario: how would you test the share workflow's atomicity?
Write an integration test that accepts a share and asserts *both* effects — the request is `accepted` *and* a `ConfigShareGrant` now exists (verified by the requester then successfully reading the config). To probe atomicity directly, simulate a failure between the two writes (monkey-patch the grant insert to raise) and assert the request was *not* left `accepted` — i.e. the transaction rolled back both. The in-memory SQLite harness makes setting up these scenarios fast.

### Scenario: first thing you'd add for real production with real devices?
Beyond hardening secrets (a real `SECRET_KEY` and `FERNET_KEY` from a secrets manager, not defaults), prioritize **safety around apply**: dry-run-by-default in the UI, require confirmation, and lean on NAPALM's atomic commit/rollback and diff so an operator always previews changes before they hit live gear. Pushing wrong config to production network equipment is the highest-consequence action, so invest there first — then real connectivity timeouts/retries in the drivers and alerting on failed jobs via the observability stack.

---

## PART 15 — Backend tech choices (one-by-one)

- **Backend language: Python 3.11.** Readable, huge ecosystem for web + networking (Netmiko/NAPALM are Python). 3.11 adds speed and `StrEnum`.

·

- **Backend web framework: FastAPI.** Type-hint-driven: auto-validates requests and auto-generates OpenAPI docs; async-native; less boilerplate than Django REST Framework, more batteries than Flask.

·

- **ASGI + the server.** **ASGI** (Asynchronous Server Gateway Interface) is the async successor to WSGI — the standard interface between an async Python web app and a server, allowing concurrent, non-blocking request handling. The ASGI server running FastAPI is **uvicorn**: a high-performance server process that speaks HTTP and drives the async event loop (FastAPI is just the app object; uvicorn runs it).

·

- **Data validation/serialization: Pydantic v2.** Turns "is this JSON valid?" into "does it fit this typed class?" — validates at the boundary, converts to/from JSON, powers FastAPI's docs. v2's core is Rust → fast.

·

- **Async Postgres driver: asyncpg.** The fast, async, low-level library SQLAlchemy uses to talk to Postgres without blocking the event loop (the `postgresql+asyncpg://` URL scheme).

·

- **Migration tool: Alembic.** From the SQLAlchemy authors; versions your schema as code so every environment reaches the same structure reproducibly.

·

- **Relational database: PostgreSQL.** ACID, free, feature-rich (ENUM, UUID, JSON), great concurrency via MVCC. (Pros/cons in Part 2.)

·

- **JWT creation/verification: python-jose.** Encodes/decodes and signs the access/refresh tokens (HS256).

·

- **Cryptography: `cryptography` (Fernet).** Symmetric AES-128-CBC + HMAC recipe; reversibly encrypts device credentials at rest.

·

- **SSH/CLI libraries: Netmiko + NAPALM.** Real SSH backup/apply across vendors; NAPALM adds diffs + atomic commits. (Part 1.)

·

- **Async-capable HTTP client: httpx.** Talks to REST controllers and powers the in-process test client. (Part 1.)

·

- **Test framework: pytest.** Concise tests, fixtures, parametrization; the Python testing standard.

·

- **Lint/format/type-check: ruff / black / mypy.** ruff = fast linter (style + error checks); black = opinionated formatter; mypy = static type checker. Run in CI and pre-commit to catch errors and enforce consistent style automatically.

## PART 15b — Frontend & infra tech choices (one-by-one)

- **Frontend language: TypeScript.** Typed JavaScript; catches bugs at compile time; `types.ts` mirrors backend schemas.

·

- **Frontend UI library: React 18.** Declarative components + hooks; the dominant SPA approach.

·

- **Build tool / dev server: Vite.** Near-instant dev server with hot reload; fast production bundling. (Part 7.)

·

- **Client-side routing: React Router.** URLs→pages without server round-trips. (Part 7.)

·

- **Server-state management: TanStack Query.** Fetching, caching, polling, invalidation. (Part 7.)

·

- **Frontend HTTP client: Axios.** Interceptors enable JWT injection + auto-refresh. (Part 7.)

·

- **Component/design system: Material UI (MUI).** Consistent, accessible UI without hand CSS. (Part 7.)

·

- **Frontend test runner: Vitest.** Vite-native, Jest-compatible; tests the API client.

·

- **Containerization: Docker.** One reproducible runtime per service. (Part 8.)

·

- **Multi-container local orchestration: Docker Compose.** One command brings up all six services. (Part 8.)

·

- **Production orchestration + packaging: Kubernetes + Helm.** Resilient/scalable deployment; Helm templatizes manifests. (Part 8.)

·

- **CI/CD: GitHub Actions.** Runs lint, type-check, tests (and image builds) on every push/PR.

·

- **Git hooks before commits: pre-commit.** Runs formatters/linters before each commit so bad code never lands.

·

- **Web server / reverse proxy: nginx.** Serves the built frontend static files and routes unknown paths back to `index.html` (so client-side routes work on refresh); proxies API calls in the container.

---

## PART 16 — File-by-file (backend)

### Explain the layering principle. Why?
The backend folders form **layers** with one-directional dependencies (outer/HTTP depends on inner/business, never the reverse): routes → schemas → services → models → db/core → Postgres/Redis. Why: **separation of concerns** — each layer has one job and can be understood and tested in isolation. Routes know HTTP but not storage; services know business rules but not HTTP (so they're reusable from routes, the worker, and the seed script); models know the DB shape; schemas know the wire format (separate from models so the API can differ from storage — e.g. never return a password hash). One-directional dependencies keep a growing codebase from becoming a tangle.

### Where is config.py? What does it do?
`backend/app/core/config.py`. It defines a typed **`Settings`** object (subclassing `pydantic-settings`' `BaseSettings`) that reads configuration from environment variables (and a `.env` file in dev), coerces and validates each to its declared type (fail-fast on bad config), and provides sensible defaults so the app runs out of the box. It holds project name, CORS origins, security keys/token lifetimes, the credential encryption key, Postgres parts, and the three Redis URLs. Helpers: a CORS validator that accepts a comma-separated string, `sqlalchemy_database_uri` (builds the DB URL or uses `DATABASE_URL`), `is_production`, and an `@lru_cache`'d `get_settings()` so settings are built once. Every module imports `from app.core.config import settings`.

### Explain CORS.
**Cross-Origin Resource Sharing** is a browser security rule: by default a page served from one origin (e.g. `http://localhost:5173`) is *not allowed* to call an API on a different origin (`http://localhost:8000`) unless the API explicitly opts in by returning CORS headers. `BACKEND_CORS_ORIGINS` lists trusted frontend origins; `main.py` adds `CORSMiddleware` with them. CORS is enforced by the *browser* (tools like curl ignore it) — it protects users, not the server.

### Why a typed settings object instead of os.environ?
Three wins: (1) one place documents every knob the app has; (2) values are validated and typed at startup, so misconfiguration fails fast and loudly instead of mysteriously later; (3) the rest of the code reads `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (an `int`) instead of `int(os.environ["..."])` scattered everywhere.

### Purpose of the folder core?
`core/` holds cross-cutting "plumbing" every other module depends on — settings, logging, observability helpers, security (passwords/JWT), credential crypto, and Redis cache helpers. These files implement no feature; they provide the foundations features build on.

### Where is logging.py? Purpose? What it does.
`backend/app/core/logging.py`. It configures **structlog** so logs are leveled, **structured** (machine-parsable key–value/JSON, not free-form prose), timestamped, and routed to stdout (where container platforms collect them). `configure_logging()` sets a processor pipeline (merge context vars, add level, ISO timestamp, render stack/exception, then a renderer) and picks `JSONRenderer` in production vs `ConsoleRenderer` in dev. `get_logger(name)` is what the rest of the app imports. Why structured: at 3 a.m. you can filter "every event for job abc-123, ordered by time" instead of grepping prose.

### Where is observability.py? Purpose? What it does.
`backend/app/observability.py`. It wires up optional, best-effort **metrics and traces**. `setup_observability(app)` tries to attach Prometheus instrumentation (metrics at `/metrics`) and, if `OTEL_ENABLED`, OpenTelemetry tracing (spans exported to an OTel Collector). Everything is wrapped in `try/except` and gated behind a flag, so if the optional libraries are missing or disabled it logs a skip line and the core app runs normally (graceful degradation — a nice-to-have never breaks the must-have).

### Where is security.py? Purpose? What it does.
`backend/app/core/security.py`. Passwords + JWT. `hash_password`/`verify_password` use passlib+bcrypt (one-way, salted). `_create_token`/`create_access_token`/`create_refresh_token`/`decode_token` build and verify JWTs with python-jose (claims `sub`/`type`/`iat`/`exp`, signed HS256 with `SECRET_KEY`). `TokenType` distinguishes access vs refresh. This is the authentication core every protected request relies on.

### Where is crypto.py? Purpose? What it does.
`backend/app/core/crypto.py`. **Reversible** credential encryption via **Fernet** (AES-128-CBC + HMAC). `_build_fernet` loads `CREDENTIAL_ENCRYPTION_KEY` (or derives a dev key from `SECRET_KEY` so local runs work, with a comment that production must set a real key). `encrypt_secret`/`decrypt_secret` are the only two functions used: the device service encrypts a plaintext secret before saving and decrypts it at the last moment before handing it to a driver. Plaintext lives in memory only momentarily and is never stored or returned.

### Why hash user passwords but encrypt device credentials?
A user password only needs to be *verified*, so a one-way **hash** is sufficient and safer (a leak reveals nothing usable, and you never need the original). A device credential must be *replayed* to the device by the worker to open an SSH/REST session, so it must be *recoverable* — hence reversible **encryption**, with the key kept outside the database. Same goal (protect secrets at rest), opposite mechanism, dictated by opposite requirements.

### Purpose of the db folder?
`db/` sets up the async ORM machinery: the declarative base + mixins (`base.py`) and the async engine, session factory, and `get_db` dependency (`session.py`). Everything in models and services sits on top of it.

### Where is base.py? What does it do?
`backend/app/db/base.py`. Defines `Base(DeclarativeBase)` — the root every model inherits from (SQLAlchemy collects all tables onto `Base.metadata`, which Alembic and tests read) — plus reusable mixins: `UUIDPrimaryKeyMixin` (a UUID `id` defaulting to `uuid.uuid4`) and `TimestampMixin` (timezone-aware `created_at`/`updated_at` with DB-side defaults and `onupdate`). DRY columns shared by every model.

### Where is session.py? What does it do?
`backend/app/db/session.py`. Creates the async **engine** (manages the connection pool; `pool_pre_ping=True` checks dead connections), the **session factory** `AsyncSessionLocal` (`expire_on_commit=False`, `autoflush=False`), and the `get_db` async-generator dependency that yields one session per request and rolls back on exceptions. One engine per process; one session (transactional scope) per request. The worker uses `AsyncSessionLocal()` directly.

### Purpose of the models folder?
`models/` defines the database tables as SQLAlchemy classes — the **data model**, the most important design artifact, since everything else manipulates these shapes. Plus shared enums.

### Where is enums.py? What does it do?
`backend/app/models/enums.py`. Defines `StrEnum` enumerations whose values must be one of a fixed set: `UserRole` (admin/operator/viewer), `TransportType` (mock/real), `ConfigFormat` (cli/json/set), `JobType` (backup/apply), `JobStatus` (pending/running/succeeded/failed), `ShareStatus` (pending/accepted/denied). `StrEnum` members *are* strings, so they serialize straight to JSON/DB and compare to plain strings. One source of truth consumed by models, schemas, and (mirrored in) the frontend. They become real Postgres ENUM types.

### Where is user.py? What does it do?
`backend/app/models/user.py`. The `User` model (`users` table): `username`/`email` (unique, indexed), `hashed_password`, `full_name`, `role` (default viewer — least privilege), `is_active` (disable, don't delete), and relationships `devices`/`config_files` (one-to-many, `cascade="all, delete-orphan"`). Uses forward references + `TYPE_CHECKING` to avoid circular imports.

### Where is device.py? What does it do?
`backend/app/models/device.py`. The `Device` model: `name`/`platform` (indexed; platform is the driver key), `vendor`/`model`, `host`/`port`, `transport` (default mock — what makes the app runnable with no hardware), `username`/`encrypted_secret` (stored encrypted, never exposed), `owner_id` FK→users (CASCADE), and the `owner` relationship.

### Where is config_file.py? What does it do?
`backend/app/models/config_file.py`. Two models: `ConfigFile` (`content` as `Text`, `platform` as compatibility key, `version` int, `format` enum, `owner_id` FK CASCADE, `source_device_id` FK SET NULL — config survives device deletion, `grants` relationship) and the many-to-many join table `ConfigShareGrant` (`config_file_id` + `user_id`, both FK CASCADE, unique constraint on the pair).

### Where is share_request.py? What does it do?
`backend/app/models/share_request.py`. The `ShareRequest` workflow model: `config_file_id`, `requester_id` and `owner_id` (two FKs to the *same* `users` table — so each `relationship` must spell out `foreign_keys=[...]`), `status` (pending/accepted/denied), `message`, `responded_at`. Distinct from a grant: the request is the conversation ("may I?"), the grant is the resulting permission.

### Where is job.py? What does it do?
`backend/app/models/job.py`. The `Job` model — the durable record that makes async jobs observable: `type` (backup/apply), `status` lifecycle, `device_id` (CASCADE), `config_file_id` (SET NULL; null for backups), `user_id`, `celery_task_id` (indexed, links DB row to the queue record), `log` and `error` (Text). The frontend learns outcomes by polling this table.

### Where is audit.py? What does it do?
`backend/app/models/audit.py`. The `AuditLog` model — append-only record of security-relevant actions: `actor_id` (FK SET NULL, so the log survives user deletion), `action` (dotted string, indexed, e.g. `login.success`), `target_type`/`target_id` (loose *string* references, deliberately not FKs so they can reference deleted things), `detail`. Answers "who did what, when?"

### Explain models/__init__.py.
It re-exports every model and enum so the rest of the app writes `from app.models import Device, User, JobStatus`. It also serves an essential second purpose: importing the package **registers every table on `Base.metadata`**. Alembic's `env.py` does `from app import models` precisely so all tables are known during migration; if a model were never imported, its table would be invisible to migrations.

### Explain the whole schema at a glance.
A **user** owns many **devices** and **config files** and runs many **jobs**. A **job** targets one device (and, for applies, references one config). A config can be **shared** with other users via **grants** (created when **share requests** are accepted). Every meaningful action leaves an **audit log**. Delete rules are deliberate: `owner_id` CASCADE (a config/device without an owner is meaningless) vs `source_device_id`/`config_file_id` SET NULL (a config without its original device, or a job without its config, is still useful history) vs audit `actor_id` SET NULL (never erase evidence). The unique constraint on grants prevents duplicates.

### Why are schemas separate from the models?
To decouple storage from the wire and prevent leaks: the `User` model has `hashed_password` but `UserRead` simply omits it (structurally impossible to leak); the `Device` model stores `encrypted_secret` but `DeviceRead` exposes only `has_secret: bool`. Inputs also need validation the DB doesn't express (username length, password ≥ 8, port range, email shape — Pydantic enforces these). And create/update/read shapes differ (create needs a password; update makes fields optional; read adds server-generated `id`/timestamps). Schemas are the **contract** between client and server, free to evolve independently of the tables.

### Where is common.py? What does it do?
`backend/app/schemas/common.py`. Shared schema base: `ORMModel` (sets `from_attributes=True` so Pydantic can build a schema from a SQLAlchemy object's attributes — every read schema inherits it) and `Message` (a tiny `{"detail": "..."}` envelope for simple text responses).

### Purpose of the services package?
`services/` holds the **business logic** — the rules. A service takes a DB session + plain args, does the work (queries, mutations, rule checks), and returns models, **without knowing about HTTP**. That HTTP-ignorance lets the same service be called from a route, a Celery task, or the seed script, and tested without the web layer. Routes stay thin; the interesting logic lives in one reusable place. Services raise *domain* exceptions (`JobError`, `ShareError`).

### Where is user_service.py? What does it do?
`backend/app/services/user_service.py`. User CRUD + auth logic: `get_by_username`/`get_by_id`/`get_by_email`, `create_user` (hashes the password in the service), `update_user` (partial update via `model_dump(exclude_unset=True)`, special-casing the password), `list_users`, and `authenticate` (unknown/inactive/wrong-password → `None`; returns the same `None` either way so the route can't reveal which usernames exist).

### Where is device_service.py? What does it do?
`backend/app/services/device_service.py`. Device CRUD with two key ideas: **ownership-scoped listing** (`list_for_user` adds `WHERE owner_id = me` for non-admins) and **encrypt-on-write / decrypt-on-use** (`create` Fernet-encrypts the secret before saving; `build_target` decrypts at the last moment and packs connection details into a `DeviceTarget` for the driver layer — called by the connectivity test and the Celery tasks).

### Where is config_service.py? What does it do?
`backend/app/services/config_service.py`. Config CRUD plus access control: `user_has_access` (the central predicate — admin? owner? else is there a share grant?), `list_accessible` (one query combining ownership OR granted-ids subquery, avoiding N+1), `create`, and `update` (bumps `version` only when `content` actually changes).

### Where is job_service.py? What does it do?
`backend/app/services/job_service.py`. The async heart. `create_backup_job`/`create_apply_job` write the `pending` row (apply enforces the platform-compatibility rule, raising `JobError`). `dispatch(job)` (a plain synchronous function — substitutable in tests) calls Celery `.delay(str(job.id), ...)` to enqueue, passing only the id. `mark_dispatched`/`mark_running`/`mark_succeeded`/`mark_failed` drive the status transitions. The route orchestrates create → dispatch → mark_dispatched.

### Where is share_service.py? What does it do?
`backend/app/services/share_service.py`. The request/accept workflow with guard rails. `create_request` rejects requesting your own config, a duplicate pending request, or something already granted (each `ShareError`). `_load_with_requester` uses `selectinload` to eager-load the requester (needed because the read schema nests `UserPublic` and async lazy-loading at serialization time would fail). `decide(accept=...)` is idempotency-guarded and **atomic**: in one transaction it marks the request accepted/denied *and* (on accept) inserts a `ConfigShareGrant`.

### Where is audit_service.py? What does it do?
`backend/app/services/audit_service.py`. A single `record(...)` helper (keyword-only args) called from routes after meaningful actions, writing an `AuditLog` row. `commit=True` by default but can be `False` to fold the audit write into a larger surrounding transaction. Coerces `target_id` to `str` (loose string refs, not FKs).

### Where is deps.py? What does it do?
`backend/app/api/deps.py`. Dependency injection wiring. Defines `DbSession`/`CurrentUser` annotated aliases, `oauth2_scheme`, `get_current_user` (decodes/verifies the JWT, checks it's an access token, loads the *live* user, confirms active — any failure → a uniform 401), and the RBAC guards `require_role`/`require_admin`/`require_operator` (raise 403 on wrong role). It's where a raw JWT becomes a verified `User`.

### Explain the auth flow.
`get_current_user` is the gate on every protected request: (1) decode + verify the JWT signature/expiry; (2) confirm `type == "access"` (not a refresh token); (3) extract `sub` (user id); (4) load that user from the DB; (5) confirm they exist and are active. Any failure raises the *same* generic 401 (so it never reveals why). It loads the **live** user every request, so the DB role is authoritative — demoting an admin takes effect on their next request even with an old token. No session is stored; identity is reconstructed from the signed token + one user lookup (statelessness).

### Explain the role guards.
`require_role(*roles)` is a dependency **factory**: called with allowed roles, it returns a `_guard` coroutine that depends on `CurrentUser` (so authentication runs first), then checks `current_user.role in roles`, returning the user or raising **403 Forbidden**. `require_admin` allows only admins (user management); `require_operator` allows admins *and* operators (create devices, run jobs). Routes use them either as `dependencies=[Depends(require_operator)]` (pure side-effect check) or by taking `current_user` and doing ownership checks in the body. 401 = "who are you?"; 403 = "you may not."

### Purpose of the api/v1 package.
The HTTP layer: one router file per resource (auth, users, devices, configs, jobs, shares, drivers, health) plus `router.py` assembling them. Each route is thin: parse → authorize → call one service → shape the response. `/api/v1` is the version prefix so a future `v2` can coexist.

### Where is router.py? What does it do?
`backend/app/api/v1/router.py`. Defines `api_router = APIRouter()` and `include_router`s every resource router (health, auth, users, drivers, devices, configs, jobs, shares) into one aggregator, which `main.py` mounts under `/api/v1`. Adding a resource is "write a file, add one include line."

### Where is auth.py? What does it do?
`backend/app/api/v1/auth.py`. Auth routes: `POST /login` (uses `OAuth2PasswordRequestForm` — the one form-encoded endpoint, for OAuth2 standards compliance — authenticates, audits success/failure, returns the token pair with the role hint), `POST /refresh` (verifies a refresh token, reissues a fresh pair), and `GET /me` (returns the current user via `UserRead`).

### Where is devices.py? What does it do?
`backend/app/api/v1/devices.py`. Device routes. Helpers: `_to_read` (serializes + sets `has_secret`, never the secret) and `_get_owned_or_404` (404 if missing, 403 if not yours and not admin). `GET ""` (owner-scoped list), `POST ""` (`require_operator` + validates platform is registered + audits + 201), `GET/PATCH/DELETE /{id}`, and `POST /{id}/test` (synchronous connectivity check via the driver, decrypting the secret at the last moment).

### Where is configs.py? What does it do?
`backend/app/api/v1/configs.py`. Config routes with two gates: `_get_readable_or_404` (uses `user_has_access` — own/admin/granted) for reads, and `_require_owner` (owner/admin only) for modifications — cleanly separating shareable read access from owner-only write access. List returns lightweight `ConfigFileSummary` (no content); detail returns full `ConfigFileRead`. `GET /{id}/download` returns `PlainTextResponse` with a `Content-Disposition: attachment` header (extension from `format`) to trigger a file download.

### Where is jobs.py? What does it do?
`backend/app/api/v1/jobs.py`. The async trigger. `POST /backup` and `POST /apply` (both `require_operator`, `status_code=202`) run the three-step dance (create pending job → dispatch to Redis → mark dispatched), with apply additionally checking config access and translating the platform-mismatch `JobError` to 422. `GET ""` (owner-scoped list, polled by the UI) and `GET /{id}` (ownership-checked).

### Where is shares.py? What does it do?
`backend/app/api/v1/shares.py`. Share workflow routes: `POST ""` (create request; `ShareError` → 409), `GET /incoming` and `GET /outgoing` (the two sides of the workflow), and `POST /{id}/decision` (only the config owner may answer; calls `share_service.decide`).

### Where is users.py in v1? What does it do?
`backend/app/api/v1/users.py`. `GET ""` returns `UserPublic` (id/username/full_name only) to any logged-in user (so the share picker can choose a recipient without exposing emails/roles). `POST ""` and update are `require_admin` (only admins manage accounts), with friendly 409s on duplicate username/email before the DB constraint.

### Where is drivers.py? What does it do?
`backend/app/api/v1/drivers.py`. `GET ""` serializes the driver registry's metadata (`list_drivers()`) into `DriverInfo` so the UI can populate platform dropdowns. Requires a logged-in user but no special role.

### Where is health.py? What does it do?
`backend/app/api/v1/health.py`. Orchestrator probes. `GET /health` = **liveness** ("is the process alive?" — restart me if not). `GET /ready` = **readiness** ("can I serve traffic?") by pinging Postgres (`SELECT 1`) and Redis (`ping()`), returning a per-dependency breakdown and overall ok/degraded. Kubernetes wires liveness→`/health` and readiness→`/ready`.

### Where is main.py? What does it do?
`backend/app/main.py`. The **composition root**. `lifespan` (startup/shutdown hook — configure logging, log events). `create_app()` (application factory) builds the FastAPI app, adds CORS middleware (if origins configured), mounts `api_router` under `/api/v1`, adds a friendly `/` route, sets up OpenAPI/`/docs`, and calls `setup_observability`. Ends with `app = create_app()` so uvicorn finds `app.main:app`. (Migrations/seeding are not here — the container command runs them before uvicorn.)

### Purpose of the drivers package / having a driver layer.
To talk to many device types (Cisco SSH, Juniper `set`, Mist REST, …) without business logic caring which, via **polymorphism**: one interface, one implementation per platform, selected at runtime by a registry. It eliminates `if platform == ...` branching and embodies the **Open/Closed Principle** — adding a platform is purely additive (one decorated subclass). It also cleanly separates identity (class metadata), behavior (shared mixins), and selection (registry/factory), and provides the mock transport that makes the whole app runnable/testable with no hardware.

### What does BaseDriver do?
`BaseDriver` is the **abstract base class** (`ABC`) defining the driver contract. Public methods `test_connection`/`backup`/`apply` each check `transport == "mock"` and either return fabricated data or call `_real_*`. `sample_config` is `@abstractmethod` (every concrete driver must supply realistic mock text). `ClassVar` metadata (`platform`, `vendor`, `transport_kind`, `config_format`, `default_port`) describes the kind of device. It also defines the `DeviceTarget` (connection details) and `ApplyResult` (diff/applied/log) dataclasses. The mock/real split lives here — the single most important design choice in the layer.

### Explain the registry (turning a class into a plugin).
A module-level `registry: dict[str, type[BaseDriver]]` maps platform string → driver class. The `@register` decorator runs at import time and inserts the class keyed by its `platform` — so a class announces "I handle this platform" just by being decorated, with no central list to edit (additive). `get_driver_class(platform)` looks it up (raising `DriverError` if unknown); `get_driver(target)` is the factory that instantiates the right class; `list_drivers()` produces the catalog the `/drivers` endpoint serves. Classic decorator/registry + factory pattern.

### Where is ssh_drivers.py? What does it do?
`backend/app/drivers/ssh_drivers.py`. Holds the `NetmikoDriver` mixin with the shared real SSH I/O (`_connect_netmiko`, `_real_backup` via `send_command("show running-config")`, `_real_apply` preferring NAPALM for diff + atomic commit, falling back to Netmiko) and the nine concrete SSH platform classes (Cisco IOS-XE/IOS/9800 WLC, Juniper Junos, Arista EOS, Brocade ICX, Dell OS, HP ProCurve, Ruckus Unleashed), each tiny: identity `ClassVar`s, `netmiko_device_type`, `config_format`, and a `sample_config`, all `@register`ed.

### Where is rest_drivers.py? What does it do?
`backend/app/drivers/rest_drivers.py`. Holds the `RestControllerDriver` mixin (transport_kind=`rest`, config_format=`json`, default_port=443) with real I/O over **httpx** (authenticated GET/PUT of JSON config), and the three cloud-controller classes (Juniper Mist, Ruckus SmartZone, Extreme Site Engine), each `@register`ed with a JSON `sample_config`. From the caller's view these are identical to SSH drivers — both expose `backup()`/`apply()`.

### Why must our backend be asynchronous?
Because a web backend spends most of its time **waiting on I/O** (Postgres queries, network). Synchronous handling would tie up a thread per request while waiting, serving few users. Async lets one process start a slow op, set it aside, serve other requests, and resume when data arrives — so one backend handles many concurrent requests efficiently. (Genuinely slow/blocking device work is offloaded to the worker, since `await` doesn't help CPU-bound or non-async blocking code.)

### Where is worker.py? What does it do?
`backend/app/worker.py`. Defines the Celery application (`celery_app = Celery("golden_config", broker=Redis/0, backend=Redis/1, include=["app.tasks.device_tasks"])`) and its config (JSON serialization, `task_track_started=True`, `task_time_limit=300`, `result_expires=3600`, UTC). It's the worker's equivalent of `create_app()`; the worker is started with `celery -A app.worker.celery_app worker`.

### Where is device_tasks.py? What does it do?
`backend/app/tasks/device_tasks.py`. Defines the Celery tasks `run_backup`/`run_apply` (synchronous wrappers calling `asyncio.run(_run_backup/_run_apply)`). The async implementations open the worker's *own* DB session, mark the job running, load the device (and config for apply), `build_target` to decrypt the credential, call `get_driver(target).backup()/.apply()`, write the result (new ConfigFile or the diff/log) and mark the job succeeded — all wrapped in `try/except` so any failure marks the job `failed` with the error. Only the job id was passed; truth is re-read from Postgres.

### Explain how the API process and worker process coordinate.
They're **peers that never call each other directly**. They communicate through two shared stores: **Redis** (the queue: "here's a job id to run") and **PostgreSQL** (the truth: job status + the resulting config). The API *produces* a message and writes a `pending` row; the worker *consumes* the message and updates the row; the browser *polls* the row. No component blocks on another — which is why you can scale workers independently, restart the API without losing queued work, and survive a slow device without freezing the UI.

### What three roles does Redis play?
(1) Celery **broker** — the queue carrying job messages from API to worker (DB 0). (2) Celery **result backend** — stores task status/return values (DB 1). (3) General-purpose **cache** — cache-aside helpers with TTL (DB 2). Separate logical DBs keep them from colliding while sharing one Redis server.

### Explain why we use Redis as a cache.
A cache stores the answer to an expensive question so the next asker gets it cheaply (cache-aside: check cache → hit returns fast → miss does the work, stores with a TTL → invalidate on change). Redis is ideal because it's RAM-resident (microsecond reads), a key→value store ("key = question, value = answer"), and supports **TTL** natively (`SET ... EX 300`) so the cache self-cleans and never serves very-stale data.

### Where is redis.py? What does it do?
`backend/app/core/redis.py`. Provides the cache toolkit: `get_redis()` (a lazy singleton `aioredis` client to `CACHE_REDIS_URL`, `decode_responses=True`), and the cache-aside primitives `cache_get_json`, `cache_set_json` (default 300s TTL), and `cache_delete`. The same `get_redis()` is what the `/ready` health probe pings.

### We implement caching but don't use it much. Why?
The read endpoints are already fast (indexed Postgres lookups over modest data), so aggressive caching isn't necessary — and **premature caching is a classic mistake** because every cache adds the hard problem of **invalidation** ("there are only two hard things in CS: cache invalidation and naming things"). So the repo provides a clean, correct caching toolkit and wires Redis fully in, rather than sprinkling caches where they aren't needed. The right place to use it would be a genuinely expensive, read-heavy, rarely-changing computation (e.g. an aggregated dashboard). Knowing *when not to cache* is as important as knowing how.

### Where is initial_data.py? What does it do?
`backend/app/initial_data.py`. The **idempotent seed script**: `seed()` creates a first admin user (from settings) if absent and some demo devices if absent, and pre-captures a golden config for the flagship Cisco device via the normal mock backup path. Idempotent (checks existence before creating) so it's safe to run on every container boot; it reuses services (so passwords get hashed, secrets encrypted) rather than raw SQL. Runnable as `python -m app.initial_data`.

### Explain database migrations, why we need it, what tool.
A **migration** is a versioned, ordered, reversible script that transforms the DB schema from one state to the next — version control for your database structure. You need it to evolve a live schema (add a column/table/index) *without dropping and recreating it* (which would delete data), reproducibly across every environment, with history and rollback. The tool is **Alembic** (from the SQLAlchemy authors). Its `env.py` points `target_metadata` at `Base.metadata` and does `from app import models` so all tables are known.

### Where is 0001_initial.py? What does it do?
`backend/app/alembic/versions/0001_initial.py`. The first migration (`revision="0001"`, `down_revision=None`). `upgrade()` creates every Postgres ENUM type and every table with columns, constraints, and indexes (the whole schema). `downgrade()` reverses it, dropping tables in reverse dependency order (children before parents) so foreign keys don't block. `revision`/`down_revision` form the linked list Alembic walks to order migrations.

### Give me the migration workflow.
1. **Change a model** in Python. 2. **Autogenerate**: `alembic revision --autogenerate -m "msg"` (Alembic diffs models vs DB and drafts a migration). 3. **Review and edit** the draft (autogenerate isn't perfect). 4. **Apply**: `alembic upgrade head` runs all not-yet-applied migrations. In this project `alembic upgrade head` runs automatically at container startup, before seeding and launching uvicorn:
`sh -c "alembic upgrade head && python -m app.initial_data && uvicorn app.main:app ..."`.

### Explain why we test, and the unit/integration split.
Tests run your code and assert the result, so you catch breakage before users do — enabling confident change. **Unit tests** check one small piece in isolation (a driver returns sensible mock config; password hash/verify round-trips) — fast, pinpoint failures. **Integration tests** exercise many pieces together through the real HTTP API (register → log in → create device → run backup → see config) — catching bugs *between* units (wrong status codes, broken auth wiring, serialization mistakes). You want both: units for precision, integrations for confidence the whole thing works.

### What testing framework? Why?
**pytest** (backend) — discovers `test_*` functions, runs them, reports pass/fail on plain `assert`s, with **fixtures** (reusable, injected setup) and parametrization; the Python testing standard. **Vitest** (frontend) — Vite-native, Jest-compatible, tests the API client.

### Where is conftest.py? What does it do?
`backend/tests/conftest.py` (and `tests/integration/conftest.py`). pytest's special file for shared fixtures. The integration `conftest` builds a test app: an in-memory SQLite database (`Base.metadata.create_all`), overrides the `get_db` dependency to use the test session, **monkey-patches `job_service.dispatch`** to run jobs inline (no Redis/worker needed), and provides an `AsyncClient` over `ASGITransport` that drives the FastAPI app in-process (no real network). This makes the slow external dependencies (Postgres, Redis, Celery, devices) disappear while still exercising the real app code.

### What do the unit tests check vs the integration tests?
**Unit tests** pin invariants: passwords are hashed and verify correctly; *every* registered driver returns a non-empty mock config (so a new driver can't ship without sample data); JWTs encode/decode correctly. **Integration tests** walk real user journeys through the API: login returns a token and `/me` identifies you; creating a device requires the operator role; a backup produces a config; the share request/accept workflow grants access; ownership rules return 403/404 correctly — proving the *system* works, not just the parts.

---

## PART 17 — Frontend file-by-file

### What is a SPA? Why do we use it?
A **single-page application** loads one HTML page + a JS bundle once, then JavaScript re-renders in place and fetches only JSON from the API — no full page reloads when navigating. We use it for a fast, app-like UX where the backend serves *data* (JSON over `/api/v1`) and the frontend, running in the browser, renders the UI and calls that API. They're developed/deployed separately and only talk over HTTP.

### What is our frontend toolchain? Explain each.
- **TypeScript** — typed JS, compiled to plain JS for the browser; catches type errors at compile time.

·

- **Vite** — dev server (instant, hot reload) + production bundler (minified static files).

·

- **package.json** — dependency manifest + scripts (`dev`/`build`/`test`/`lint`).

·

- **React + JSX** — declarative component UI.

·

- (Plus React Router, TanStack Query, Axios, MUI, Vitest — see Part 7/15b.)

### Explain JSX and the components.
A **component** is a Capitalized function that returns **JSX** — HTML-like syntax that compiles to JavaScript function calls building a UI tree. Curly braces `{value}` embed live JS values into markup. You compose UI by nesting components like HTML tags, each with its own logic. **Props** are read-only inputs passed parent→child. JSX makes React **declarative**: describe what the screen should look like for the current data, and React computes the DOM changes.

### Where is main.tsx? What does it do?
`frontend/src/main.tsx`. The React entry point. `ReactDOM.createRoot(...).render(...)` mounts the app into the `#root` div and wraps it in a **provider stack**: `QueryClientProvider` (TanStack Query cache), `ThemeProvider` + `CssBaseline` (MUI styling/reset), `BrowserRouter` (routing), `AuthProvider` (login state), then `<App/>`. Each provider makes a capability available to every nested component. `React.StrictMode` surfaces dev-time bugs.

### Where is App.tsx? What does it do?
`frontend/src/App.tsx`. Top-level routing + **auth gate**. It reads `user`/`loading` from the auth context: while verifying a stored token, show a spinner; if no user, the only reachable route is `/login` (everything else redirects there); if logged in, mount `AppLayout` with the real pages (Devices/Configs/Jobs/Shares). Authentication is enforced *structurally* — protected routes aren't in the table until you're logged in.

### Where is AuthContext.tsx? What does it do?
`frontend/src/auth/AuthContext.tsx`. The single source of truth for "who is logged in." `AuthProvider` holds `user`/`loading` state and exposes `login`/`logout`. On startup `loadUser` validates a stored token via `/auth/me` (restoring the session or clearing a bad token). `login` posts **form-encoded** credentials to `/auth/login`, stores the token pair, then fetches `/auth/me`. It listens for the global `gc:logout` window event (fired by the Axios interceptor when refresh fails) and logs out — decoupling the HTTP layer from React state.

### Where is AppLayout.tsx? What does it do?
`frontend/src/components/AppLayout.tsx`. The persistent shell every logged-in page renders inside: a top AppBar and a side Drawer with nav links (Devices/Config Files/Jobs/Shares), the current user's name, and a logout button, all MUI. It renders `{children}` (the current page) in the main area. Nav links are React Router `<Link>`s, so navigation swaps the page without a reload. The shell lives in one place, so every page gets the same frame.

### Where is client.ts? What does it do?
`frontend/src/api/client.ts`. The Axios layer. Configures one shared `api` instance with the base URL; a `tokenStore` wrapping `localStorage` (so JWTs survive reloads); a **request interceptor** injecting `Authorization: Bearer <token>`; a **response interceptor** doing transparent token refresh on 401 (call `/auth/refresh`, replay the original request, dedupe concurrent refreshes, fire `gc:logout` if refresh fails); and `apiErrorMessage` to extract the backend's `detail` for the UI.

### Explain TanStack Query and why we use it.
See Part 7. We use it because UI data fetching has a lot of incidental complexity (loading/error states, caching, dedup, refetch-after-write, polling). TanStack Query handles all of it: `useQuery` (read, with a cache `queryKey`), `useMutation` (write, with `onSuccess: invalidateQueries` so reads auto-refresh), and `refetchInterval` (polling). Pages stay simple because the hard data-flow problems are solved once in the hooks.

### How do we handle polling for job status?
`useJobs(pollMs=4000)` is a `useQuery` with `refetchInterval: 4000`, silently re-fetching `GET /jobs` every four seconds. The worker writes status transitions into Postgres; each poll reads the latest rows, so the status chip and logs update on their own until `succeeded`/`failed`. Polling stops automatically when you navigate away (the hook unmounts). It's the consumer side of the async story.

### Explain pages.
Each file in `frontend/src/pages/` is one screen component that reads server data via hooks, renders it with MUI, and wires buttons to mutations:
- **LoginPage** — username/password form calling `auth.login`; the only page reachable logged out.

·

- **DevicesPage** — the hub: lists devices, an Add dialog (platform dropdown from `useDrivers()`), a connectivity Test button, and per-device Backup/Apply actions.

·

- **ConfigsPage** — lists configs (lightweight summaries), view/download/delete, and request-a-share.

·

- **JobsPage** — lists jobs with 4s polling; status chip + log/error; the visible face of the async architecture.

·

- **SharesPage** — incoming requests (Accept/Deny) and outgoing requests (status).

### Explain the anatomy of a page.
Every page follows the same shape: **data via hooks** (`useDevices`, etc.) not props; a **loading branch** (`if (isLoading) return <CircularProgress/>`); **rendering a list with `.map()` + `key={d.id}`** (the stable key React needs); **buttons call `mutation.mutate(...)`** which, via `onSuccess` invalidation, refresh the list; and **local UI state** (`useState`) for screen-only things like "is the dialog open." Server state (cached/shared) is kept distinct from ephemeral UI state.

### Explain what a page does.
A page is a thin **view**: it pulls exactly the server data it needs from TanStack Query hooks (shared cache, no double-fetch), renders it with MUI components, and triggers writes through mutations that invalidate cache keys so the UI re-syncs itself. The genuinely hard problems (auth lifecycle, caching, polling) were solved once in the client/hooks/auth layers, so pages stay simple.

### Explain how a page triggers the async backend.
Clicking "Backup" calls `backup.mutate({device_id, name})`, which POSTs to `/jobs/backup` and gets `202` + a pending job. Its `onSuccess` invalidates `["jobs"]` (and `["configs"]`). The Jobs page's `useJobs` polling then watches the status flip to `succeeded` as the worker finishes, and the new config appears on the Config Files page. One click flows: mutation → API `202` → Celery → worker → Postgres → polling → UI update — touching every layer of the system.

---

## PART 18 — Infrastructure & end-to-end

### Explain containers and dockers.
A container packages a process with its entire environment into an isolated, portable unit that runs identically anywhere (sharing the host kernel, lighter than a VM). An **image** is the built template; a **container** is a running instance. **Docker** builds images from Dockerfiles and runs containers. The payoff: the exact image tested in CI runs in production — no "works on my machine" drift.

### Explain our backend Dockerfile.
`FROM python:3.11-slim` (lean base) → `WORKDIR /app` → `COPY pyproject.toml ./` then `RUN pip install` **before** copying app code (so the expensive dependency layer is **cached** and only re-runs when deps change) → `COPY . .` → `EXPOSE 8000` → `CMD uvicorn app.main:app ...`. Compose overrides the command to also run migrations + seed first.

### Explain our frontend Dockerfile.
A **multi-stage** build: stage 1 (`node:20-alpine`) runs `npm ci` + `npm run build` so Vite compiles TS/React into static files in `/app/dist`; stage 2 (`nginx:alpine`) copies **only** `dist/` (`--from=build`) plus `nginx.conf` and serves it. The heavy Node toolchain is thrown away, so the shipped image is just nginx + static files — small, fast, minimal attack surface. nginx also routes unknown paths back to `index.html` so client-side routes work on refresh.

### Where is docker-compose.yml? What does it do?
`docker-compose.yml` (repo root). Declares the whole stack as services (postgres, redis, backend, worker, frontend, plus prometheus/grafana/otel-collector) and starts them with `docker compose up`. Compose gives them a private network with **service discovery by name** (so `DATABASE_URL` uses `@postgres`, not an IP). Backend and worker build the *same* image but run different commands (uvicorn vs `celery worker`). The backend command chains `alembic upgrade head && python -m app.initial_data && uvicorn ...` (safe on every boot because the seed is idempotent and migrations are versioned). `depends_on` orders startup; `ports` map to the host; the `pgdata` volume persists the database.

### Explain how we implement continuous integration.
**GitHub Actions** (`.github/workflows/ci.yml`) runs on every push/PR. Three jobs: **backend** (spins up real Postgres + Redis as services, then `ruff check`, `mypy`, `pytest`), **frontend** (`npm ci`, lint, test, `npm run build`), and **docker** (builds the images, gated on the first two via `needs:`). Any failing step flags the push red and can block a PR merge. CI exercises the code against genuine Postgres/Redis (complementing the fast SQLite test shim) — its value is confidence that every change is linted, type-checked, and tested in a clean environment before it can break `main`.

### Explain Kubernetes.
See Part 8. Declarative container orchestrator across a cluster: you declare desired state and it continuously reconciles (restart, reschedule, scale, rolling update, service discovery, load balancing). Repo manifests: Namespace; ConfigMap/Secret (production config injection); StatefulSets + PersistentVolumes for Postgres/Redis; Deployments + Services for backend/worker/frontend with liveness→`/health`, readiness→`/ready`; often an Ingress for external traffic.

### Explain Helm.
See Part 8. A package manager for Kubernetes. A **chart** (`Chart.yaml`, `values.yaml`, `templates/`) is a parameterized k8s app; `{{ .Values.xxx }}` placeholders are filled from a values file, so one chart deploys to every environment differing only by values (more replicas/resources in prod). Turns "deploy" into one repeatable, versioned command.

### Explain observability in production.
`deploy/observability/` holds the monitoring stack configs: an **OpenTelemetry Collector** (receives traces/metrics the app emits), a **Prometheus** config (scrapes the app's `/metrics`, storing time series), and **Grafana** provisioning (dashboards visualizing those metrics). The app is instrumented (structlog logs to stdout, Prometheus metrics at `/metrics`, optional OTel traces); these configs collect and display it so operators see request rates, error rates, latency, and job throughput. It's optional/best-effort.

### End-to-end walkthrough 1 — Logging in.
1. **LoginPage**: type `admin`/`admin12345`, submit → `auth.login(username, password)`. 2. **Auth context**: builds a form-encoded body (not JSON) and POSTs `/api/v1/auth/login`. 3. **Axios**: request interceptor sees no token yet, sends as-is. 4. **Route `/auth/login`**: parses `OAuth2PasswordRequestForm`, calls `user_service.authenticate`. 5. **Service**: loads the user, checks `is_active`, `verify_password` (bcrypt re-hash with stored salt) — matches. 6. **Route**: audits `login.success`, mints access (30 min, role claim) + refresh (7 day) JWTs, returns a `Token`. 7. **Auth context**: stores both tokens in `localStorage`, calls `/auth/me`, `setUser(me)`. 8. **React re-renders**: `user` non-null → `App.tsx` mounts `AppLayout` + pages. *Touches:* form-encoded OAuth2 login, password hashing/verification, JWT issuance, localStorage persistence, state-driven navigation.

### End-to-end walkthrough 2 — Creating a device.
1. **DevicesPage**: Add device dialog (name, platform from `useDrivers()`, host, transport=mock), submit → `createDevice.mutate(payload)`. 2. **Axios**: attaches `Authorization: Bearer <token>`. 3. **Route `POST /devices`**: `require_operator` passes; `DeviceCreate` validation (port range); checks platform is registered (else 422). 4. **Service `device.create`**: Fernet-encrypts the secret, stamps `owner_id`, commits. 5. **Route**: audits `device.create`, serializes via `_to_read` (sets `has_secret`, never the secret), returns `201`. 6. **TanStack Query**: `onSuccess` invalidates `["devices"]` → the list re-fetches and the device appears. *Touches:* role authz, schema validation, registry check, credential encryption, ownership stamping, auditing, correct status code, cache-invalidation refresh.

### End-to-end walkthrough 3 — Running a backup (the async flagship).
1. **Browser**: "Backup" → `useBackupJob().mutate({device_id, name})` POSTs `/jobs/backup`. 2. **Route**: `require_operator` + ownership; the three-step dance — `create_backup_job` (pending row) → `dispatch` (enqueue job id to Redis) → `mark_dispatched`; returns `202` with the pending job. 3. **TanStack Query**: invalidates `["jobs"]`. 4. **Celery worker** (separate process): pulls the message, `run_backup(job_id)` → `asyncio.run(_run_backup)`; opens its own DB session, marks `running`, loads the device, `build_target` decrypts the credential. 5. **Driver**: `get_driver(target).backup()`; mock returns `sample_config()` (real would SSH `show running-config`) — same code path. 6. **Worker**: creates a `ConfigFile` (tagged with `config_format`), marks job `succeeded` with a log. 7. **Browser**: the Jobs poll sees `succeeded`; the also-invalidated `["configs"]` makes the new config appear. *Touches:* async queue (producer/consumer via Redis), 202 semantics, two-process coordination via Postgres, decryption at point of use, driver polymorphism + mock transport, polling-driven UI. **The best trace to know.**

### End-to-end walkthrough 4 — Applying a config (with a guard rail).
1. **Browser**: choose config + device, optional dry run → `useApplyJob().mutate({device_id, config_file_id, dry_run})` POSTs `/jobs/apply`. 2. **Route**: `require_operator` + device ownership + config access (`user_has_access`); `create_apply_job` enforces **platform compatibility** — mismatch raises `JobError` → `422`. 3. **Dispatch**: same dance, task `run_apply` carrying `dry_run`; returns `202`. 4. **Worker**: `_run_apply` builds the target; `driver.apply(config.content, dry_run=...)` returns `ApplyResult(diff, applied, log)`; dry run gives a preview without changing the device. 5. **Worker**: serializes diff + applied + log into the job's `log`, marks `succeeded`. 6. **Browser**: polling shows the result; the operator reads the diff. *Touches:* layered authorization (role + device ownership + config access), a domain-rule guard as 422, apply/diff/dry-run safety, `ApplyResult`.

### End-to-end walkthrough 5 — Sharing a config (request/accept handshake).
1. **Requester**: on a config they don't own, "Request access" → `useRequestShare().mutate({config_file_id, message})` POSTs `/shares`. 2. **Route**: `share_service.create_request` enforces three guard rails (not your own; no duplicate pending; not already granted) → `ShareError` → `409`; a clean request creates a `pending` ShareRequest. 3. **Owner**: `SharesPage` incoming list shows the request *with the requester's username* (service `selectinload`s `requester`; read schema nests `UserPublic`); clicks Accept. 4. **Route `/shares/{id}/decision`**: confirms the caller is the config owner; `share_service.decide(accept=True)` — in **one transaction** — marks the request `accepted` *and* inserts a `ConfigShareGrant` (atomic: never "accepted but no grant"). 5. **Requester**: their mutation invalidated `["configs"]`; `user_has_access` now finds a grant, so the shared config appears — readable, not editable (owner-only writes). *Touches:* the workflow with invariants, 409 for conflicts, eager-loading + nested schemas, per-row ownership, transactional atomicity, read-vs-write access distinction.
