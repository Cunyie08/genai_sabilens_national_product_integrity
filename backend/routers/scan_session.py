"""
Scan session endpoints — /api/v1/scan/session/*

In-memory implementation — no Redis required for session management.
Each session holds an asyncio.Queue; the consumer endpoint puts the scan
result on the queue, and the WebSocket pops it and forwards it to the desktop.

Works for any single-process Uvicorn deployment (the common dev/staging setup).
"""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.config import settings
from backend.utils.response import error_response, success_response

logger = logging.getLogger("scan_session")

SESSION_TTL_SECONDS = 300  # 5 min — long enough for the phone to complete the scan

router = APIRouter(prefix="/api/v1/scan", tags=["Scan Session"])

# ── In-process session store ──────────────────────────────────────────────────
# { session_id: {"status": str, "queue": asyncio.Queue, ...} }
# Possible statuses: "pending" | "location_ready" | "complete" | (expired = key removed)
_sessions: dict[str, dict] = {}


class _LocationPayload(BaseModel):
    latitude: float
    longitude: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/session")
async def create_session():
    """
    Create a pending scan session.
    Called by the desktop immediately before showing the QR code.
    Returns {session_id, mobile_url} — no external services required.
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "status": "pending",
        "queue": asyncio.Queue(maxsize=1),
    }

    # Schedule cleanup so abandoned sessions don't leak memory
    asyncio.get_event_loop().call_later(
        SESSION_TTL_SECONDS, _sessions.pop, session_id, None
    )

    logger.info("Scan session created: %s", session_id)
    return success_response({
        "session_id": session_id,
        "mobile_url": f"{settings.FRONTEND_URL}/mobile-scan/{session_id}",
    })


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Polling endpoint — desktop calls this every 2.5 s.
    Returns the current status plus any available data:
      • location_ready  → includes latitude / longitude from the phone
      • complete        → includes the full AI result dict
      • expired         → session not found
    """
    session = _sessions.get(session_id)
    if session is None:
        return success_response({"status": "expired"})
    payload: dict = {"status": session["status"]}
    if session["status"] == "location_ready":
        payload["latitude"]  = session["latitude"]
        payload["longitude"] = session["longitude"]
    elif session["status"] == "complete" and "result" in session:
        payload["result"] = session["result"]
    return success_response(payload)


@router.put("/session/{session_id}/location")
async def submit_location(session_id: str, body: _LocationPayload):
    """
    Called by the phone's MobileLocationHandoff component.
    Stores the GPS fix and advances the session to 'location_ready' so the
    desktop's polling loop can pick it up and proceed with the scan.
    """
    session = _sessions.get(session_id)
    if session is None:
        return error_response("Session not found or expired", code="NOT_FOUND", status_code=404)
    session["status"]    = "location_ready"
    session["latitude"]  = body.latitude
    session["longitude"] = body.longitude
    logger.info(
        "Location received for session %s: %.5f, %.5f",
        session_id, body.latitude, body.longitude,
    )
    return success_response({"message": "Location received"})


@router.websocket("/session/{session_id}/ws")
async def session_websocket(websocket: WebSocket, session_id: str):
    """
    Desktop connects here after creating a session.
    Blocks until the phone's scan result is published via publish_result(),
    then forwards the JSON payload to the desktop and closes.
    """
    await websocket.accept()

    session = _sessions.get(session_id)
    if session is None:
        # Session expired or never existed
        await websocket.close(code=4004)
        return

    queue: asyncio.Queue = session["queue"]

    try:
        async def _wait_for_result():
            return await queue.get()

        async def _wait_for_disconnect():
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            return None

        result_task     = asyncio.create_task(_wait_for_result())
        disconnect_task = asyncio.create_task(_wait_for_disconnect())

        done, pending = await asyncio.wait(
            {result_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if result_task in done and not result_task.cancelled():
            payload = result_task.result()
            if payload is not None:
                try:
                    await websocket.send_text(json.dumps(payload, default=str))
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error session=%s: %s", session_id, exc)
    finally:
        _sessions.pop(session_id, None)


# ── Called by consumer.py after a scan completes ──────────────────────────────

def publish_result(session_id: str, result: dict) -> bool:
    """
    Deliver a scan result to the waiting desktop WebSocket.
    Called synchronously from consumer.py — no await needed.
    Returns True if the session existed and was notified.
    """
    session = _sessions.get(session_id)
    if session is None:
        logger.warning("publish_result: session %s not found (expired?)", session_id)
        return False

    try:
        session["queue"].put_nowait(result)
        session["status"] = "complete"
        session["result"] = result  # kept for polling fallback
        logger.info("Result published to session %s", session_id)
        return True
    except asyncio.QueueFull:
        logger.warning("publish_result: session %s queue full — result dropped", session_id)
        return False
