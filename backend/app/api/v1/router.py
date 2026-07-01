"""Aggregate v1 router that mounts all feature routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, configs, devices, drivers, health, jobs, shares, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(drivers.router)
api_router.include_router(devices.router)
api_router.include_router(configs.router)
api_router.include_router(shares.router)
api_router.include_router(jobs.router)
