"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers.auth import router as auth_router
from backend.routers.consumer import router as consumer_router
from backend.routers.nafdac import router as nafdac_router
from backend.routers.shared import router as shared_router

logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    logging.basicConfig(level=logging.INFO)
    print("SabiLens Backend Starting...")
    yield
    print("SabiLens Backend Shutdown...")


app = FastAPI(
    title="Sabilens National Product Integrity API",
    version=settings.APP_VERSION,
    description="API for NAFDAC workflows, product verification, and location services.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(consumer_router)
app.include_router(nafdac_router)
app.include_router(shared_router)


@app.get("/", tags=["Health"])
async def root():
    return {"service": "sabilens-api", "status": "ok", "version": settings.APP_VERSION}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=settings.DEBUG)
