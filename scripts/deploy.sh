#!/usr/bin/env bash
# Runs on the GCE VM as the `deployer` user.
# Called remotely via: ssh deployer@VM "bash /opt/sabilens/scripts/deploy.sh"
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
APP_DIR="/opt/sabilens"
VENV="${APP_DIR}/venv"
ENV_FILE="${APP_DIR}/backend/.env"
SECRET_NAME="sabilens-env"
SERVICES=(fastapi celery-worker celery-beat)
PYTHON="python3.11"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Resolve project ID from the GCE metadata server (no hardcoding needed)
PROJECT_ID=$(curl -sf "http://metadata.google.internal/computeMetadata/v1/project/project-id" \
  -H "Metadata-Flavor: Google")

# ─── 1. Pull Latest Code ──────────────────────────────────────────────────────
log "Step 1/6 — Pulling latest code..."
cd "$APP_DIR"
git fetch --all --prune
git reset --hard origin/master
log "Code updated → $(git rev-parse --short HEAD) ($(git log -1 --format='%s'))"

# ─── 2. Activate Virtual Environment ─────────────────────────────────────────
log "Step 2/6 — Preparing virtual environment..."
if [[ ! -d "$VENV" ]]; then
  log "  Creating new venv with $PYTHON"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"

# ─── 3. Install / Upgrade Dependencies ───────────────────────────────────────
log "Step 3/6 — Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt -r backend/requirements.txt --quiet
log "  Dependencies up to date"

# ─── 4. Fetch .env from Secret Manager ───────────────────────────────────────
# The VM's attached service account has roles/secretmanager.secretAccessor.
# The secret payload is the raw .env file content — no encoding needed.
log "Step 4/6 — Fetching .env from Secret Manager (secret: $SECRET_NAME)..."
gcloud secrets versions access latest \
  --secret="$SECRET_NAME" \
  --project="$PROJECT_ID" \
  > "$ENV_FILE"
chmod 600 "$ENV_FILE"
log "  .env updated ($(wc -l < "$ENV_FILE") lines)"

# ─── 5. Run Database Migrations ──────────────────────────────────────────────
log "Step 5/6 — Running Alembic migrations..."

# CRITICAL FIX: Move into the backend folder where alembic.ini and the alembic folder live
cd "$APP_DIR/backend"

set +e  # alembic prints to stderr on "no new revisions" — capture cleanly
ALEMBIC_OUT=$(alembic upgrade head 2>&1)
EXIT_CODE=$?
set -e

echo "$ALEMBIC_OUT"
if [[ $EXIT_CODE -ne 0 ]]; then
  log "FATAL: Alembic migration failed. Aborting before service restart."
  exit 1
fi
log "  Migrations applied"

# Return to root directory for the remainder of the script
cd "$APP_DIR"

# ─── 6. Restart Services and Verify ──────────────────────────────────────────
log "Step 6/6 — Restarting services: ${SERVICES[*]}"
sudo systemctl restart "${SERVICES[@]}"

sleep 4  # Give services time to reach their steady state

FAILED=()
for svc in "${SERVICES[@]}"; do
  if systemctl is-active --quiet "$svc"; then
    log "  [OK] $svc is running"
  else
    log "  [FAIL] $svc did not start"
    systemctl status "$svc" --no-pager -l || true
    FAILED+=("$svc")
  fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
  log "DEPLOYMENT FAILED — services that did not start: ${FAILED[*]}"
  exit 1
fi

log "=== Deployment complete ==="