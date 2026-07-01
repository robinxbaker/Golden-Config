# Contributing & development guide

## Prerequisites

- Python 3.11+
- Node 20+
- Docker (for the full local stack) or local PostgreSQL + Redis

## Running the stack

The fastest path is docker-compose:

```bash
cp .env.example .env
docker compose up --build
```

## Backend development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.initial_data        # seed admin + demo devices
uvicorn app.main:app --reload
celery -A app.worker.celery_app worker --loglevel=info   # second shell
```

### Conventions

- **Layers:** `api` (routing/validation) → `services` (business logic) → `models` (ORM).
  Keep SQL out of routers.
- **Async everywhere** in the request path; the Celery worker bridges to async via
  `asyncio.run`.
- **Schemas** (`app/schemas`) define the API contract; never return ORM objects directly.
- Format/lint with `ruff`, `black`, and `mypy` (run `pre-commit run --all-files`).

### Adding a device driver

1. Subclass `NetmikoDriver` (SSH) or `RestControllerDriver` (REST) in
   `app/drivers/ssh_drivers.py` / `rest_drivers.py`.
2. Set the class metadata (`platform`, `display_name`, `vendor`, device type).
3. Implement `sample_config()` for the mock transport.
4. Decorate with `@register`. It now appears automatically in the API and UI.

## Frontend development

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run test
npm run lint
```

- Server state is managed by **TanStack Query** hooks in `src/api/hooks.ts`.
- The axios client (`src/api/client.ts`) injects the JWT and transparently refreshes it.

## Testing

```bash
# Backend (needs PostgreSQL + Redis; CI provides them)
cd backend && pytest --cov=app

# Frontend
cd frontend && npm run test -- --run
```

> Integration tests reset the database schema between tests, so always point them at a
> disposable database (CI uses `goldenconfig_test`).

## Commit hygiene

- Conventional, present-tense commit messages.
- Run `pre-commit` before pushing.
- CI must be green (lint, type-check, tests, image build) before merge.
