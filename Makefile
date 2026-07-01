.PHONY: help up down logs build backend frontend test lint fmt migrate seed worker

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up:        ## Start the full stack with docker compose
	docker compose up --build

down:      ## Stop the stack
	docker compose down

logs:      ## Tail backend logs
	docker compose logs -f backend worker

migrate:   ## Run DB migrations (inside backend dir)
	cd backend && alembic upgrade head

seed:      ## Seed bootstrap admin + demo devices
	cd backend && python -m app.initial_data

worker:    ## Run a Celery worker locally
	cd backend && celery -A app.worker.celery_app worker --loglevel=info

backend:   ## Run the API locally with reload
	cd backend && uvicorn app.main:app --reload

frontend:  ## Run the Vite dev server
	cd frontend && npm run dev

test:      ## Run backend + frontend tests
	cd backend && pytest --cov=app
	cd frontend && npm run test -- --run

lint:      ## Lint backend + frontend
	cd backend && ruff check app && mypy app
	cd frontend && npm run lint

fmt:       ## Auto-format backend
	cd backend && ruff check --fix app && black app
