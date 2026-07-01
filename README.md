# Golden Config

> Backup and enforce the "golden" configuration of your network devices — over SSH/REST,
> from a clean web UI, with auth, RBAC, async jobs, and per-user config sharing.

Golden Config solves a problem every network/test engineer knows: lab and staging devices
are *never* configured the way you need them. Instead of hunting through running-config by
hand, Golden Config lets you:

1. **Capture** a device's full configuration into a reusable, versioned config file.
2. **Apply** a saved config file to a *compatible* device to bring it to a known-good state.
3. **Share** config files between users with a request / accept / deny workflow.

It is built as a production-style, full-stack application to demonstrate real-world
engineering practices end to end.

---

## Architecture

```text
                ┌─────────────┐      ┌──────────────────────────────────────────┐
                │   Browser   │      │                 Backend                   │
  React + TS ──▶│  (Vite/MUI) │─────▶│  FastAPI  ─┬─ REST API (/api/v1)          │
  TanStack Q    └─────────────┘      │            ├─ JWT auth + RBAC             │
                                     │            ├─ SQLAlchemy 2.0 ─▶ PostgreSQL │
                                     │            └─ enqueue ─▶ Redis ─▶ Celery   │
                                     └──────────────────────────────┬───────────┘
                                                                    │
                                          ┌─────────────────────────▼─────────────┐
                                          │  Celery worker                         │
                                          │   └─ Driver registry (pluggable)       │
                                          │        ├─ SSH/CLI  (Netmiko + NAPALM)   │
                                          │        ├─ REST     (httpx controllers)  │
                                          │        └─ Mock     (default, no HW)     │
                                          └────────────────────────────────────────┘
```

| Layer        | Technology                                                              |
| ------------ | ----------------------------------------------------------------------- |
| Frontend     | React 18, TypeScript, Vite, Material UI, TanStack Query, React Router    |
| Backend      | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic                    |
| Auth         | JWT access + refresh tokens, role-based access control (RBAC)           |
| Async jobs   | Celery + Redis (device backup/apply run as background jobs)              |
| Caching      | Redis (device inventory / config read cache)                            |
| Database     | PostgreSQL                                                               |
| Net comms    | Netmiko + NAPALM (SSH CLI), httpx (REST controllers), pluggable drivers  |
| Observability| OpenTelemetry, Prometheus, Grafana                                       |
| Packaging    | Docker, docker-compose, Kubernetes manifests + Helm chart               |
| CI / Quality | GitHub Actions, pytest, Vitest, ruff, black, mypy, pre-commit           |

---

## Supported devices

Every driver ships with a **mock** implementation so the whole app runs with zero hardware.
Set `transport: real` on a device to talk to actual gear.

| Vendor / platform                       | Driver key            | Transport |
| --------------------------------------- | --------------------- | --------- |
| Cisco IOS-XE (Catalyst 3850 / 9300)     | `cisco_ios_xe`        | SSH       |
| Cisco IOS                               | `cisco_ios`           | SSH       |
| Cisco Catalyst 9800 WLC                 | `cisco_9800_wlc`      | SSH       |
| Juniper Junos switch                    | `juniper_junos`       | SSH       |
| Arista EOS                              | `arista_eos`          | SSH       |
| Brocade / Ruckus ICX                    | `brocade_icx`         | SSH       |
| Dell OS10 / OS9                         | `dell_os`             | SSH       |
| HP / Aruba ProCurve                     | `hp_procurve`         | SSH       |
| Ruckus Unleashed / ZoneDirector         | `ruckus_unleashed`    | SSH       |
| Juniper Mist controller                 | `juniper_mist`        | REST      |
| Ruckus SmartZone High-Scale             | `ruckus_smartzone`    | REST      |
| Extreme Site Engine (XIQ-SE)            | `extreme_site_engine` | REST      |

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

| Service        | URL                              |
| -------------- | -------------------------------- |
| Frontend       | http://localhost:5173            |
| Backend (API)  | http://localhost:8000/api/v1     |
| API docs       | http://localhost:8000/docs       |
| Grafana        | http://localhost:3000            |
| Prometheus     | http://localhost:9090            |

The stack auto-seeds an admin user and demo devices. Default login:

```text
username: admin
password: admin12345
```

> Change credentials via `.env` before any real deployment.

---

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Run the Celery worker in a second shell:

```bash
celery -A app.worker.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Testing & quality

```bash
# backend
cd backend && pytest --cov=app

# frontend
cd frontend && npm run test

# everything via pre-commit
pre-commit run --all-files
```

---

## Project layout

```text
golden-config/
├── backend/            FastAPI app, drivers, Celery worker, tests, Alembic
├── frontend/           React + TS + Vite single-page app
├── deploy/
│   ├── k8s/            Raw Kubernetes manifests
│   ├── helm/           Helm chart
│   └── observability/  Prometheus, Grafana, OTel collector config
├── docker-compose.yml
└── .github/workflows/  CI pipeline
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a deeper dive and
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for development conventions.

---

## License

MIT — see [LICENSE](LICENSE).
