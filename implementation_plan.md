# Refactoring Plan: Dynamic Pathing & Nginx Alignment

This plan outlines the steps to decouple the `/api` prefix from your internal FastAPI routes. By utilizing `root_path="/api"`, FastAPI will generate correct OpenAPI documentation, but its internal sockets will respond purely to the stripped paths (e.g., `/v1/auth/login`), perfectly aligning with Nginx's `proxy_pass http://127.0.0.1:8000/;` trailing-slash behavior.

## User Review Required

> [!WARNING]
> **Important Path Change:** Once this refactor is deployed, hitting the backend **directly** on port 8000 (bypassing Nginx) will require you to omit the `/api` prefix (e.g., `http://127.0.0.1:8000/v1/auth/login`). Hitting it through Nginx remains unchanged (e.g., `https://sabilens.com/api/v1/auth/login`). This is the standard microservice behavior.

## Proposed Changes

### Core Configuration
#### [MODIFY] `backend/main.py`
- Add `root_path="/api"` to the `FastAPI()` instantiation.
- Change `docs_url`, `redoc_url`, and `openapi_url` from `/api/docs` to `/docs` (since `root_path` handles the prefix automatically).
- Remove `/api` from all `app.include_router()` prefixes (e.g., `/api/v1/auth` becomes `/v1/auth`).
- Update the `uvicorn.run()` host parameter from `0.0.0.0` to `127.0.0.1` to enforce IPv4 loopback and prevent IPv6 Nginx connection refusals.

---

### Internal Routers
#### [MODIFY] `backend/routers/consumer.py`
- Change router prefix: `prefix="/api/consumer"` ➔ `prefix="/consumer"`

#### [MODIFY] `backend/routers/nafdac.py`
- Change router prefix: `prefix="/api/nafdac"` ➔ `prefix="/nafdac"`

#### [MODIFY] `backend/routers/scan_session.py`
- Change router prefix: `prefix="/api/v1/scan"` ➔ `prefix="/v1/scan"`

#### [MODIFY] `backend/routers/shared.py`
- Strip `/api` from all 9 hardcoded endpoint paths (e.g., `@router.get("/api/verify/nafdac/{number}")` ➔ `@router.get("/verify/nafdac/{number}")`).

---

## Playwright Diagnostic Test

I will create a Playwright test script (`frontend/tests/backend_routing.spec.js`) that verifies the paths. It will:
1. Test the endpoint via Nginx/Proxy at `http://localhost:3000/api/v1/auth/login`.
2. Test the endpoint directly at `http://127.0.0.1:8000/v1/auth/login` (the raw socket).
3. Authenticate and test the `detect-product` endpoint to ensure the path stripping works securely and JWTs remain valid.

## Verification Plan

### Automated Tests
1. Run the new Playwright script `npx playwright test tests/backend_routing.spec.js` to ensure 200 OK responses on both proxy and direct routes.
2. The AI processing blocks and Celery tasks (ports 8001-8004) are entirely untouched since they operate on their own internal ports and do not route through Nginx's `/api` block. JWTs are validated via `auth_service.py` which does not rely on URL prefixes.
