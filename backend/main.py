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
from backend.routers.scan_session import router as scan_session_router
from backend.admin.routers.company import router as company_router
from backend.admin.routers.nafdac import router as nafdac_admin_router
from backend.admin.routers.super_admin import router as super_admin_router

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
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://34.35.129.170:3000",
        "https://sabilens.com",
        "https://www.sabilens.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers without /api prefix
app.include_router(auth_router, prefix="/v1/auth")
app.include_router(consumer_router)
app.include_router(nafdac_router)
app.include_router(shared_router)
app.include_router(scan_session_router)
app.include_router(company_router,      prefix="/v1/admin/company", tags=["Company Admin"])
app.include_router(nafdac_admin_router, prefix="/v1/admin/nafdac",  tags=["NAFDAC Admin"])
app.include_router(super_admin_router,  prefix="/v1/admin/super",   tags=["Super Admin"])


@app.get("/", tags=["Health"])
async def root():
    return {"service": "sabilens-api", "status": "ok", "version": settings.APP_VERSION}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # Bind to 127.0.0.1 instead of 0.0.0.0 to prevent Nginx IPv6 loopback errors
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=settings.DEBUG)
