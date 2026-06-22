# 🔍 SabiLens AI

**AI-Powered Counterfeit Detection Platform for Nigeria**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14-336791?style=flat-square&logo=postgresql)](https://postgresql.org)
[![GCP](https://img.shields.io/badge/Google_Cloud-africa--south1-4285F4?style=flat-square&logo=googlecloud)](https://cloud.google.com)

*Protecting Nigerian consumers. Defending your brand.*

[Features](#-features) · [Architecture](#-architecture) · [Setup](#-local-setup) · [API Docs](#-api-reference) · [Deployment](#-gcp-deployment) · [Team](#-team)

</div>

---

## 📌 Overview

SabiLens is a full-stack, production-deployed AI platform that enables Nigerian consumers to instantly verify the authenticity of physical products using their smartphone camera or gallery. It combines computer vision, OCR, and NAFDAC registry intelligence to return a real-time verdict - **AUTHENTIC**, **SUSPICIOUS**, or **NOT VERIFIED** - in under 5 seconds.

The platform is built for:

- **Consumers** - scan a product before buying to check if it is genuine
- **Brand owners / manufacturers** - monitor counterfeit activity with a real-time dashboard
- **NAFDAC / regulators** - access geo-tagged enforcement intelligence by state and LGA

> **Project status:** Live on Google Cloud Platform (africa-south1 region). Web-first deployment with mobile app planned post-supervisor sign-off.

---

## ✨ Features

### Consumer-Facing

- 📸 **Camera scan** - live camera scan of product label via mobile browser
- 🖼️ **Gallery upload** - upload a photo from your phone library for verification
- 🔍 **Dual-mode AI** - front label (visual recognition) + back label (OCR + NAFDAC lookup)
- ⚡ **Real-time verdict** - green (Safe to Buy), red (Suspicious), grey (Not Verified)
- 🗺️ **Geo-tagged scans** - every scan records GPS coordinates, state, and LGA
- 📜 **Scan history** - consumers can review all their previous scans

### Brand / Admin

- 📊 **Super Admin Dashboard** - platform-wide scan analytics, verdict breakdown, counterfeit heatmaps
- 🏢 **Company Dashboard** - brand-specific scan volume, verdict trends, market intelligence
- 🏛️ **NAFDAC Officer Dashboard** - enforcement case management, geo-tagged suspicious activity
- 📦 **Product registry** - manage registered products and NAFDAC numbers

### AI Engine

- 🧠 **Visual pipeline** - ResNet50-based image embedding with ChromaDB vector similarity search
- 📄 **OCR pipeline** - PaddleOCR (PP-OCRv3) for label text extraction
- 🏷️ **NAFDAC extraction** - two-pass regex engine for robust NAFDAC number parsing
- 🤖 **Regulatory agent** - LLM-powered agent that queries the NAFDAC product registry
- ⚖️ **Fusion engine** - weighted signal fusion (visual + OCR + regulatory) with decision classifier

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                         │
│          React PWA (Vite) - served via Nginx                │
│     Camera Scan │ Gallery Upload │ Scan History │ Dashboards │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────┐
│                       API LAYER                             │
│              FastAPI (Uvicorn, 2 workers)                   │
│   /api/consumer/*  │  /api/v1/auth/*  │  /api/admin/*       │
│         JWT Auth │ Rate limiting │ CORS │ Nginx proxy        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      AI ENGINE                              │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ Visual      │  │ OCR         │  │ Regulatory Agent   │  │
│  │ Pipeline    │  │ Pipeline    │  │ (LLM + ChromaDB)   │  │
│  │ ResNet50    │  │ PaddleOCR   │  │ NAFDAC Registry    │  │
│  │ ChromaDB    │  │ Regex NLP   │  │ Vector Search      │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────┬──────────┘  │
│         └────────────────▼──────────────────-─┘            │
│                   ┌──────────────┐                          │
│                   │ Fusion Engine│                          │
│                   │ + Classifier │                          │
│                   └──────────────┘                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    DATA LAYER (GCP)                         │
│  Cloud SQL (PostgreSQL 14)  │  Redis  │  Cloud Storage      │
│  Cloud SQL Proxy (:5433)    │  (:6379) │  (3 GCS buckets)   │
└─────────────────────────────────────────────────────────────┘
```

### Stack Summary

| Layer            | Technology                                          |
| ---------------- | --------------------------------------------------- |
| Frontend         | React 18, Vite, TailwindCSS, PWA                    |
| Backend          | FastAPI, Uvicorn, SQLAlchemy (async), Alembic       |
| AI Vision     | ResNet50 (PyTorch), ChromaDB, sentence-transformers |
| AI OCR        | PaddleOCR (PP-OCRv3), custom regex NLP              |
| AI Regulatory | LlamaIndex, ChromaDB, NAFDAC registry               |
| Database         | PostgreSQL 14 (GCP Cloud SQL)                       |
| Cache            | Redis 7 (GCP Memorystore)                           |
| Storage          | Google Cloud Storage (3 buckets)                    |
| Infrastructure   | GCP Compute Engine (africa-south1), Nginx, systemd  |
| Auth             | JWT (access + refresh tokens), bcrypt               |

---

## 📁 Project Structure

```
sabilens/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (env-driven)
│   ├── database.py              # Async SQLAlchemy engine
│   ├── models/                  # ORM models (User, Scan, Company …)
│   ├── routers/
│   │   ├── consumer.py          # Scan, history, upload endpoints
│   │   ├── auth.py              # Login, register, refresh
│   │   └── admin.py             # Dashboard, reports
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/
│   │   ├── ai_integration.py    # Bridge: API ↔ AI engine
│   │   └── image_upload.py      # GCS upload service
│   └── alembic/                 # Database migrations (001–005)
│
├── ai_engine/
│   ├── orchestrator/
│   │   └── scan_orchestrator.py # Main scan entry point
│   ├── visual/
│   │   ├── visual_pipeline.py   # ResNet50 embedding + similarity
│   │   └── vision_dataset/      # Training images + labels
│   ├── ocr_linguistic/
│   │   ├── extractor.py         # PaddleOCR + NAFDAC regex
│   │   └── pipeline.py          # Full OCR pipeline
│   ├── agent/
│   │   └── verification_agent.py # NAFDAC regulatory agent
│   ├── rag_system/              # ChromaDB + embedder
│   └── fusion/
│       └── fusion_engine.py     # Signal fusion + classifier
│
├── frontend/
│   ├── src/
│   │   ├── pages/               # Scan, Home, History, Dashboard
│   │   ├── components/          # Camera, ResultCard, NavBar …
│   │   └── api/                 # Axios API client
│   └── public/
│       └── sw.js                # Service worker (PWA)
│
├── chroma_db/                   # ChromaDB persistent store (15 products)
├── .env                         # Environment variables (never commit)
└── requirements.txt
```

---

## 🖥️ Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14 (local) or GCP Cloud SQL access
- Redis (local or remote)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/sabilens.git
cd sabilens
```

### 2. Backend setup

```bash
# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
nano .env  # Fill in DATABASE_URL, JWT_SECRET, GCS credentials etc.
```

### 3. Database setup

```bash
# Run all migrations
cd backend
alembic upgrade head

# Verify tables
psql $DATABASE_URL -c "\dt"
```

### 4. AI engine setup

```bash
# Download PaddleOCR models (first run only - ~200MB)
python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)"

# Verify ChromaDB product database
python -c "
import chromadb
client = chromadb.PersistentClient(path='chroma_db')
col = client.get_collection('nafdac_food_products')
print('Products in DB:', col.count())
"
```

### 5. Run the backend

```bash
cd /path/to/sabilens
PYTHONPATH=/path/to/sabilens uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Frontend setup

```bash
cd frontend
npm install
npm run dev  # Development server on http://localhost:5173
```

---

## ⚙️ Environment Variables

Create a `.env` file at the project root. Never commit this file.

```env
# Database
DATABASE_URL="postgresql+asyncpg://postgres:password@127.0.0.1:5433/sabilens"

# Security
JWT_SECRET_KEY="your-secret-key-min-32-chars"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google Cloud Storage
GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
GCS_BUCKET="sabilens-scan-images-prod"
GCS_REPORTS_BUCKET="sabilens-reports-prod"
GCS_MODELS_BUCKET="sabilens-models-prod"

# App
DEBUG=false
ENVIRONMENT="production"
```

---

## 📡 API Reference

Base URL: `https://sabilens.com/api`

### Authentication

| Method   | Endpoint              | Description               |
| -------- | --------------------- | ------------------------- |
| `POST` | `/v1/auth/register` | Register new user         |
| `POST` | `/v1/auth/login`    | Login, returns JWT tokens |
| `GET`  | `/v1/auth/me`       | Get current user profile  |
| `POST` | `/v1/auth/refresh`  | Refresh access token      |

### Consumer - Scans

| Method   | Endpoint                      | Description                       |
| -------- | ----------------------------- | --------------------------------- |
| `POST` | `/consumer/scan`            | Run AI scan on uploaded image(s)  |
| `GET`  | `/consumer/scans`           | Fetch user's scan history         |
| `GET`  | `/consumer/scans/{scan_id}` | Get full detail for a single scan |

#### `POST /consumer/scan` - Request body

```json
{
  "front_image": "data:image/jpeg;base64,/9j/4AAQ...",
  "back_image": "data:image/jpeg;base64,/9j/4AAQ...",
  "nafdac_no": "",
  "category": "Cosmetics",
  "latitude": 6.5244,
  "longitude": 3.3792,
  "location_text": "Lagos Island, Lagos"
}
```

#### `POST /consumer/scan` - Response

```json
{
  "status": "success",
  "data": {
    "scan_id": "fce92b84-1636-4895-af62-358a2f858268",
    "final_verdict": "AUTHENTIC",
    "confidence_pct": 89.7,
    "severity": "NONE",
    "action": "SAFE_TO_BUY",
    "summary": "Product verified against NAFDAC registry. Genuine Closeup Complete Fresh Protection Toothpaste.",
    "product_name": "Closeup Complete Fresh Protection Toothpaste",
    "nafdac_number": "A2-5334",
    "manufacturer": "Unilever Nigeria PLC",
    "expiry_date": "2031-01-26",
    "vision_mocked": false,
    "ocr_mocked": false
  }
}
```

### Admin

| Method  | Endpoint             | Auth      | Description             |
| ------- | -------------------- | --------- | ----------------------- |
| `GET` | `/admin/dashboard` | Admin JWT | Platform-wide analytics |
| `GET` | `/admin/scans`     | Admin JWT | All scans with filters  |
| `GET` | `/admin/companies` | Admin JWT | Registered companies    |

---

## 🚀 GCP Deployment

### Infrastructure

| Resource | Config                                                  |
| -------- | ------------------------------------------------------- |
| VM       | `sabilens-backend` - Compute Engine, africa-south1-a |
| Database | Cloud SQL PostgreSQL 14 -`sabilens-db`               |
| Cache    | Cloud Memorystore Redis -`sabilens-redis`            |
| Storage  | 3 GCS buckets - images, reports, models                |
| Proxy    | Cloud SQL Proxy on `127.0.0.1:5433`                   |

### SSH into VM

```bash
gcloud compute ssh sabilens-backend \
  --zone=africa-south1-a \
  --tunnel-through-iap \
  --project=YOUR_PROJECT_ID
```

### Services

The backend runs as two systemd services:

```bash
# Check service status
sudo systemctl status fastapi

# View live logs
sudo journalctl -u fastapi -f

# Restart backend
sudo systemctl restart fastapi

# Nginx
sudo systemctl status nginx
sudo nginx -t && sudo systemctl reload nginx
```

### Stop/Start VM (to save costs when not testing)

```bash
# Stop
gcloud compute instances stop sabilens-backend \
  --zone=africa-south1-a --project=YOUR_PROJECT_ID

# Start
gcloud compute instances start sabilens-backend \
  --zone=africa-south1-a --project=YOUR_PROJECT_ID
```

### Run database migrations on GCP

```bash
# Via Cloud SQL Proxy (already running on VM at port 5433)
cd /opt/sabilens
source venv/bin/activate
alembic upgrade head
```

### Nginx config location

```
/etc/nginx/sites-enabled/sabilens
```

Key settings to verify:

```nginx
client_max_body_size 20M;   # Required for high-res mobile photo uploads
proxy_pass http://127.0.0.1:8000;
```

---

## 🧪 Testing the AI Engine

Run a direct scan test on the VM to verify AI components:

```bash
cd /opt/sabilens
sudo -u deployer /opt/sabilens/venv/bin/python3 -c "
import sys, os
sys.path.insert(0, '/opt/sabilens')
sys.path.insert(0, '/opt/sabilens/ai_engine')
sys.path.insert(0, '/opt/sabilens/ai_engine/visual')
os.chdir('/opt/sabilens')
from ai_engine.orchestrator.scan_orchestrator import ScanOrchestrator
o = ScanOrchestrator()
front = 'ai_engine/visual/test_images/Product_images_labeled/closeup_comple_fresh_protection_bottom.jpg'
back  = 'ai_engine/visual/test_images/Product_images_labeled/closeup_comple_fresh_protection_back.jpg'
result = o.scan(
    image_path=front,
    image_paths=[front, back],
    nafdac_no='',
    scanned_category='Cosmetics',
    gps_coordinates={'lat': 6.5244, 'lng': 3.3792, 'accuracy': 10.0},
    purchase_channel='unknown',
)
print('Verdict:', result.final_verdict)
print('Vision mocked:', result.vision_signal.mocked)
print('OCR mocked:', result.ocr_signal.mocked)
" 2>&1 | grep -E "Verdict|mocked|NAFDAC"
```

Expected output:

```
Verdict: AUTHENTIC
Vision mocked: False
OCR mocked: False
```

---

## 🗄️ Database Schema (Key Tables)

```sql
-- Core scan record
scans (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  status VARCHAR NOT NULL,          -- AUTHENTIC | SUSPICIOUS | NOT_VERIFIED
  product_name VARCHAR(255),
  nafdac_number VARCHAR(100),
  manufacturer VARCHAR(255),
  confidence_score NUMERIC(5,4),
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  scan_location_state VARCHAR(100),
  scan_location_lga VARCHAR(150),
  scan_data JSONB,                  -- Full AI engine response
  created_at TIMESTAMP DEFAULT now()
)

-- AI analysis detail (linked to scan)
scan_analyses (
  id UUID PRIMARY KEY,
  scan_id UUID REFERENCES scans ON DELETE CASCADE,
  vision_verdict VARCHAR,
  ocr_verdict VARCHAR,
  regulatory_verdict VARCHAR,
  fusion_score NUMERIC,
  evidence_package JSONB
)
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please ensure:

- All AI engine changes are tested with the direct scan test above
- Do not commit `.env`, service account keys, or `chroma_db/` contents
- PaddleOCR model files are downloaded at runtime - do not commit them

---

## 🚧 Known Issues & Roadmap

| Issue                                            | Status                                                                       |
| ------------------------------------------------ | ---------------------------------------------------------------------------- |
| iPhone 14 Pro high-res uploads (>1MB) fail       | 🔧 Fix in progress - nginx `client_max_body_size` + frontend image resize |
| Duplicate scan records from frontend double POST | 🔧 Fix in progress - remove redundant `/api/consumer/scans` call          |
| Scan history response size (~31MB)               | 🔧 Lightweight list schema planned                                           |
| GCS image upload (placeholder credentials)       | 🔧 Service account key setup pending                                         |
| Mobile app (iOS/Android)                         | 📋 Planned post-supervisor sign-off                                          |
| NAFDAC Officer dashboard                         | 📋 Planned                                                                   |

---

## 👥 Team

**SabiLens** is a group final-year project.

| Role               | Responsibility                                                       |
| ------------------ | -------------------------------------------------------------------- |
| AI / Backend Lead  | AI engine (vision, OCR, fusion), FastAPI backend, GCP infrastructure |
| Frontend Lead      | React PWA, camera integration, dashboards                            |
| Database / DevOps  | PostgreSQL schema, Alembic migrations, systemd, Nginx                |
| Product / Research | NAFDAC data ingestion, product registry, documentation               |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ in Nigeria · Powered by Google Cloud · Fighting counterfeits with AI

**sabilens.com**

</div>
