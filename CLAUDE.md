# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SabiLens** — an AI-powered counterfeit product detection system for NAFDAC-regulated goods in Nigeria. Users scan product images; the system returns a verdict (AUTHENTIC / SUSPICIOUS / FAKE) by combining OCR, visual, and regulatory signals.

Three user roles: **Consumer** (scan & view results), **Company** (product registry & heatmaps), **NAFDAC officer** (case management & enforcement).

## Commands

### Backend
```bash
# Start backend API (from repo root)
uvicorn backend.main:app --reload --port 8000

# Run database migrations
cd backend && alembic upgrade head

# Start Celery worker (requires Redis)
celery -A backend.core.celery_app worker --loglevel=info

# Run tests
pytest tests/ -v --cov=backend --cov-report=html

# Run a single test file
pytest tests/path/to/test_file.py -v

# Install Python dependencies
pip install -r backend/requirements.txt
```

### AI Engine Services
```bash
# RAG service — ingest NAFDAC product data
python ai_engine/rag_system/main.py --mode ingest

# RAG service — serve API (port 8001)
python ai_engine/rag_system/main.py --mode serve

# AI engine FastAPI wrapper (port 8002+)
uvicorn ai_engine.api.main:app --port 8002
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # dev server
npm run build      # production build
npm run preview    # preview production build
```

## Architecture

### Request Flow (Product Scan)
```
Consumer uploads image
  → Backend (port 8000) creates Scan DB record
  → Celery task dispatched
  → Orchestrator (ai_engine/orchestrator/scan_orchestrator.py) calls all 3 AI pipelines in parallel:
      1. OCR Pipeline     — PaddleOCR + brand/structure/rule validation
      2. Visual Pipeline  — PyTorch CNN similarity + YOLO damage detection
      3. Regulatory Agent — ReAct agent queries ChromaDB (NAFDAC product vectors)
  → Fusion Engine weights all signals → numeric score → verdict
  → Result stored in DB; WebSocket pushes update to frontend
  → If counterfeit: case auto-filed in NAFDAC system
```

### Key Directories

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI app, ORM models, routers, services, Celery |
| `backend/main.py` | Backend entrypoint, CORS, router mounting |
| `backend/config.py` | All settings via `pydantic-settings` (reads `.env`) |
| `backend/database.py` | Async SQLAlchemy engine + session factory |
| `backend/models/` | 8 SQLAlchemy ORM tables (users, scans, products, cases, etc.) |
| `backend/routers/` | Endpoint groups: auth, consumer, company, nafdac, scan, admin, webhooks |
| `backend/services/` | Business logic layer (scan_service, product_service, case_service, etc.) |
| `backend/core/` | JWT auth, Celery app, WebSocket manager |
| `ai_engine/` | All AI/ML pipeline code |
| `ai_engine/ocr_linguistic/` | OCR + linguistic analysis (canonical location — not `backend/ocr_linguistic/`) |
| `ai_engine/visual/` | Visual similarity (CNN) + damage detection (YOLO) |
| `ai_engine/rag_system/` | ChromaDB vector store + NAFDAC product embedding |
| `ai_engine/agent/` | ReAct verification agent |
| `ai_engine/fusion_engine/` | Weighted signal scoring → AUTHENTIC/SUSPICIOUS/FAKE verdict |
| `ai_engine/orchestrator/` | Coordinates all 4 pipelines per scan |
| `frontend/src/pages/` | Consumer, Company, NAFDAC role-specific page sets |
| `chroma_db/` | Persisted ChromaDB vector index |

### AI Pipeline Signal Weights (Fusion Engine)
- **OCR/Linguistic**: brand validation, structural rules, category-specific rules
- **Visual**: CNN cosine similarity against reference product images, YOLO for packaging damage
- **Regulatory**: RAG lookup in NAFDAC product DB (ChromaDB / sentence-transformers)
- Final score → decision classifier → verdict displayed with confidence

### Database (Supabase PostgreSQL)
Async via `asyncpg` + SQLAlchemy 2.0. Key tables: `users`, `sessions`, `otp_verifications`, `scans`, `scan_analyses`, `companies`, `products`, `alerts`, `cases`, `enforcement_actions`.

Migrations are managed with Alembic (`backend/alembic/`).

### Background Jobs (Celery + Redis)
Celery tasks in `backend/core/` handle async AI analysis, report generation, and webhook delivery. Tasks are dispatched from `backend/services/scan_service.py` after scan creation.

## Critical Dependency Notes

- **PaddleOCR 2.6.1.3 / PaddlePaddle 2.6.2** — version-pinned; do not upgrade
- **protobuf==3.20.2** — pinned; paddlepaddle 2.6.x breaks on protobuf 4.x+
- **Python 3.10** — use the workspace interpreter at `C:\Users\PELUMI\AppData\Local\Programs\Python\Python310\python.exe`
- **ChromaDB 0.4.24** — pinned to match llama-index integration

## Environment Setup

Copy and populate `backend/.env` with:
- `DATABASE_URL` — Supabase PostgreSQL (asyncpg)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CLOUDINARY_URL` (file storage)
- `AI_VISUAL_ENDPOINT`, `AI_OCR_ENDPOINT`, `AI_REGULATORY_ENDPOINT`, `AI_FUSION_ENDPOINT` — internal microservice URLs
- `RAG_SERVICE_URL`

## Active Development Notes

- `backend/ocr_linguistic/` has been removed; canonical OCR code lives in `ai_engine/ocr_linguistic/`
- AI endpoint wiring (connecting the 4 microservices to the orchestrator) is Phase 2 work
- Test suite infrastructure exists (`pytest.ini`, `tests/`) but test files are not yet implemented
