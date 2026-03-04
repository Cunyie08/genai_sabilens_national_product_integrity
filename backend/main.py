"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.nafdac import router as nafdac_router
from backend.routers.shared import router as shared_router

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


@app.get("/", tags=["Health"])
async def root():
    return {"service": "sabilens-api", "status": "ok"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
