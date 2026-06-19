"""Ponte Twilio Media Streams <-> Gemini Live API.

Flusso di una chiamata:
1. Twilio apre il WebSocket e invia `start` (con streamSid + tenant_id passato dal
   TwiML come custom parameter). Da lì risolviamo tenant, motore e prompt.
2. Apriamo la sessione Gemini Live (audio it-IT, voce, tool `calcola_preventivo`).
3. Due loop concorrenti:
   - Twilio -> Gemini: u-law 8k -> PCM16 8k -> 16k -> send_realtime_input.
   - Gemini -> Twilio: PCM16 24k -> 8k -> u-law -> base64 -> media. Le function
     call vengono eseguite sul motore deterministico; `interrupted` -> `clear`
     (barge-in).
"""
from __future__ import annotations

import asyncio
import base64
import json

from google import genai
from google.genai import types

from app.config import (
    GCP_LOCATION,
    GCP_PROJECT,
    GEMINI_IN_RATE,
    GEMINI_LANGUAGE,
    GEMINI_MODEL,
    GEMINI_OUT_RATE,
    GEMINI_VOICE,
    TWILIO_RATE,
    DEFAULT_TENANT_ID,
)
from app.agent.runtime import QUOTE_TOOL, build_system_instruction, dispatch_tool_call
from app.platform.logging import get_logger
from app.telephony.audio import Resampler, pcm16_to_ulaw, ulaw_to_pcm16
from app.tenancy.registry import build_engine, get_tenant

log = get_logger("bridge")

# Client Vertex AI condiviso (usa ADC; nessuna chiamata di rete all'init).
_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)


def _live_config(system_instruction: str) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_instruction,
        speech_config=types.SpeechConfig(
            language_code=GEMINI_LANGUAGE,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE)
            ),
        ),
        tools=[{"function_declarations": [QUOTE_TOOL]}],
    )


async def _wait_for_start(twilio_ws) -> tuple[str, str]:
    """Legge i messaggi finché arriva `start`; ritorna (stream_sid, tenant_id)."""
    while True:
        msg = json.loads(await twilio_ws.receive_text())
        if msg.get("event") == "start":
            start = msg["start"]
            stream_sid = start["streamSid"]
            tenant_id = start.get("customParameters", {}).get("tenant_id", DEFAULT_TENANT_ID)
            return stream_sid, tenant_id


async def run_bridge(twilio_ws) -> None:
    stream_sid, tenant_id = await _wait_for_start(twilio_ws)
    tenant = get_tenant(tenant_id)
    engine = build_engine(tenant)
    log.info("Chiamata per tenant '%s' (stream %s)", tenant.id, stream_sid)

    config = _live_config(build_system_instruction(tenant, engine))

    # Resampler con stato, uno per direzione.
    up = Resampler(TWILIO_RATE, GEMINI_IN_RATE)      # 8k -> 16k (verso Gemini)
    down = Resampler(GEMINI_OUT_RATE, TWILIO_RATE)   # 24k -> 8k (verso Twilio)

    async with _client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:

        async def twilio_to_gemini() -> None:
            while True:
                msg = json.loads(await twilio_ws.receive_text())
                event = msg.get("event")
                if event == "media":
                    ulaw = base64.b64decode(msg["media"]["payload"])
                    pcm16 = up.process(ulaw_to_pcm16(ulaw))
                    await session.send_realtime_input(
                        media=types.Blob(data=pcm16, mime_type=f"audio/pcm;rate={GEMINI_IN_RATE}")
                    )
                elif event == "stop":
                    return

        async def gemini_to_twilio() -> None:
            while True:
                async for response in session.receive():
                    tool_call = getattr(response, "tool_call", None)
                    if tool_call and tool_call.function_calls:
                        replies = [
                            types.FunctionResponse(
                                id=fc.id,
                                name=fc.name,
                                response=dispatch_tool_call(fc.name, dict(fc.args or {}), engine),
                            )
                            for fc in tool_call.function_calls
                        ]
                        await session.send_tool_response(function_responses=replies)
                        continue

                    if getattr(response, "data", None):
                        ulaw = pcm16_to_ulaw(down.process(response.data))
                        await twilio_ws.send_text(
                            json.dumps(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": base64.b64encode(ulaw).decode("ascii")},
                                }
                            )
                        )

                    server_content = getattr(response, "server_content", None)
                    if server_content and getattr(server_content, "interrupted", False):
                        # Barge-in: svuota l'audio in coda su Twilio.
                        await twilio_ws.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )

        t_in = asyncio.create_task(twilio_to_gemini())
        t_out = asyncio.create_task(gemini_to_twilio())
        done, pending = await asyncio.wait({t_in, t_out}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                raise exc
