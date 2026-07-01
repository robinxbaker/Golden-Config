# Golden Config — Backend

FastAPI service that powers Golden Config: device inventory, configuration capture/apply
jobs, JWT auth with RBAC, and a Celery worker that talks to network devices through a
pluggable driver layer (Netmiko / NAPALM / REST / mock).

See the [root README](../README.md) for the full picture and quick start.

## Module map

```text
app/
├── core/        settings, security, crypto, logging, redis
├── db/          SQLAlchemy base + async session
├── models/      ORM models (User, Device, ConfigFile, ShareRequest, Job, Audit)
├── schemas/     Pydantic request/response models
├── drivers/     pluggable network device drivers + registry
├── services/    business logic (auth, devices, configs, shares, jobs)
├── api/         FastAPI routers (api/v1/...)
├── tasks/       Celery tasks
├── worker.py    Celery app
└── main.py      FastAPI app factory
```

## Running tests

The suite has two layers:

- **Unit tests** (`tests/unit`) — driver framework, security helpers, and import sanity. No
  database required.
- **Integration tests** (`tests/integration`) — exercise the FastAPI app end-to-end. They run
  against PostgreSQL by default, but work on a local SQLite file too, so you don't need Docker.

```powershell
# From the backend/ directory, inside your virtualenv:
pip install -e ".[dev]"

# Unit tests only (no database):
pytest tests/unit -q

# Full suite against a throwaway SQLite database:
$env:DATABASE_URL = "sqlite+aiosqlite:///./test.db"
pytest -q
```

In CI the integration tests run against the `postgres` service defined in the workflow, which
mirrors production. The ORM uses SQLAlchemy's portable `Uuid` type, so the same models map to a
native `UUID` column on PostgreSQL and a compatible column on SQLite.

