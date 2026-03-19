"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine

import backend_femi.models  # noqa: F401
from backend_femi.config import settings
from backend_femi.database import Base, engine
from backend_femi.routers.nafdac import router as nafdac_router
from backend_femi.routers.shared import router as shared_router

app = FastAPI(
    title="Sabilens National Product Integrity API",
    version="1.0.0",
    description="API for NAFDAC workflows, product verification, and location services.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nafdac_router)
app.include_router(shared_router)


@app.on_event("startup")
async def create_tables_on_startup():
    """Create DB tables for local/dev runs when migrations are not configured."""
    if settings.DATABASE_URL.startswith("sqlite+aiosqlite"):
        # Use sync SQLite engine for deterministic local table bootstrap.
        sync_url = settings.DATABASE_URL.replace("+aiosqlite", "", 1)
        sync_engine = create_engine(sync_url)
        Base.metadata.create_all(bind=sync_engine)
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@app.get("/", tags=["Health"])
async def root():
    return {"service": "sabilens-api", "status": "ok"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
