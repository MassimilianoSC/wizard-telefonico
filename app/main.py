"""Entrypoint FastAPI del wizard vocale.

Endpoint:
- GET  /health  → healthcheck.
- POST /twiml   → webhook voce di Twilio: risolve il tenant dal numero chiamato
                  (campo `To`) e risponde con TwiML che apre lo stream audio.
- WS   /ws      → Media Streams di Twilio, gestito dal ponte verso Gemini Live.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect

from app.config import SERVICE_HOST
from app.platform.logging import get_logger
from app.telephony.bridge import run_bridge
from app.tenancy.registry import resolve

log = get_logger("main")
app = FastAPI(title="Wizard vocale telefonico")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/twiml")
async def twiml(request: Request) -> Response:
    form = await request.form()
    to_number = str(form.get("To", ""))
    from_number = str(form.get("From", ""))
    tenant = resolve(to_number)
    host = SERVICE_HOST or request.headers.get("host", request.url.hostname)
    ws_url = f"wss://{host}/ws"
    log.info("Chiamata da %s su %s → tenant '%s'", from_number, to_number, tenant.id)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        "  <Connect>\n"
        f'    <Stream url="{ws_url}">\n'
        f'      <Parameter name="tenant_id" value="{tenant.id}"/>\n'
        f'      <Parameter name="from_number" value="{from_number}"/>\n'
        "    </Stream>\n"
        "  </Connect>\n"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await run_bridge(websocket)
    except WebSocketDisconnect:
        log.info("WebSocket Twilio disconnesso")
    except Exception:  # noqa: BLE001 — non far cadere il server per una chiamata
        log.exception("Errore nel ponte della chiamata")
