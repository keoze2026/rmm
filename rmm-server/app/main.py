"""FastAPI application entrypoint for the RMM server."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, enroll, machines, sessions, support
from app.config import settings
from app.database import close_db, init_db
from app.reaper import offline_reaper
from app.redis_client import close_redis, ping as redis_ping
from app.ws import handlers
from app.ws.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await manager.start()
    reaper_task = asyncio.create_task(offline_reaper())
    yield
    # Shutdown
    reaper_task.cancel()
    await manager.stop()
    await close_redis()
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Self-hosted Remote Monitoring & Management server (Phase 1).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(sessions.router)
app.include_router(support.router)
app.include_router(enroll.router)
# WebSocket routers
app.include_router(handlers.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "redis": await redis_ping(),
    }


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"name": settings.APP_NAME, "docs": "/docs", "health": "/health"}
