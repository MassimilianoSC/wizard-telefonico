"""Ponte Twilio Media Streams <-> Gemini Live API.

Flusso di una chiamata:
1. Twilio apre il WebSocket e invia `start` (con streamSid + tenant_id passato dal
   TwiML come custom parameter). Da lì risolviamo tenant, motore e prompt.
2. Apriamo la sessione Gemini Live (audio it-IT, voce, tool, trascrizioni) e
   iniettiamo un turno iniziale così l'agente saluta per primo.
3. Tre loop concorrenti:
   - Twilio -> Gemini: u-law 8k -> PCM16 8k -> 16k -> send_realtime_input.
   - Gemini -> Twilio: PCM16 24k -> 8k -> u-law -> base64 -> media. Le function
     call vengono eseguite sul motore deterministico; `interrupted` -> `clear`.
   - Watchdog di silenzio (Blocco B): se nessuno parla per troppo tempo, sollecita
     il cliente e, se il silenzio prosegue, congeda e chiude.
4. Chiusura: `end_call` (o il watchdog) imposta `closing`; finita la frase di
   congedo inviamo un `mark`, e quando Twilio ce lo rimanda chiudiamo il WebSocket
   (con <Connect> la chiamata termina).
5. Diagnostica: logghiamo le trascrizioni di ciò che l'utente dice e l'agente risponde.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time

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
    SILENCE_HANGUP_S,
    SILENCE_PROMPT_S,
    TWILIO_RATE,
    DEFAULT_TENANT_ID,
)
from app.agent.runtime import (
    GREETING_TRIGGER,
    SILENCE_HANGUP_TRIGGER,
    SILENCE_PROMPT_TRIGGER,
    TOOLS,
    build_system_instruction,
    dispatch_tool_call,
)
from app.platform.logging import get_logger
from app.telephony.audio import Resampler, pcm16_to_ulaw, ulaw_to_pcm16
from app.tenancy.registry import build_engine, get_tenant

log = get_logger("bridge")

_GOODBYE_MARK = "goodbye"

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
        tools=[{"function_declarations": TOOLS}],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def _send_trigger(session, text: str) -> None:
    """Inietta un turno 'di sistema' per far reagire l'agente (saluto, sollecito...)."""
    await session.send_client_content(
        turns=types.Content(role="user", parts=[types.Part.from_text(text=text)]),
        turn_complete=True,
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

    up = Resampler(TWILIO_RATE, GEMINI_IN_RATE)      # 8k -> 16k (verso Gemini)
    down = Resampler(GEMINI_OUT_RATE, TWILIO_RATE)   # 24k -> 8k (verso Twilio)

    # Stato condiviso.
    closing = False
    goodbye_sent = False
    last_activity = time.monotonic()   # ultima attività vocale (utente o agente)
    prompted_silence = False           # sollecito di silenzio già inviato

    async with _client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
        await _send_trigger(session, GREETING_TRIGGER)

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
                elif event == "mark":
                    if msg.get("mark", {}).get("name") == _GOODBYE_MARK:
                        await twilio_ws.close()
                        return
                elif event == "stop":
                    return

        async def gemini_to_twilio() -> None:
            nonlocal closing, goodbye_sent, last_activity, prompted_silence
            user_parts: list[str] = []
            agent_parts: list[str] = []
            while True:
                async for response in session.receive():
                    tool_call = getattr(response, "tool_call", None)
                    if tool_call and tool_call.function_calls:
                        replies = []
                        for fc in tool_call.function_calls:
                            log.info("TOOL CALL: %s(%s)", fc.name, dict(fc.args or {}))
                            result = dispatch_tool_call(fc.name, dict(fc.args or {}), engine)
                            if fc.name == "end_call":
                                closing = True
                            replies.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                            )
                        await session.send_tool_response(function_responses=replies)
                        continue

                    if getattr(response, "data", None):
                        last_activity = time.monotonic()
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
                    if server_content:
                        it = getattr(server_content, "input_transcription", None)
                        if it and getattr(it, "text", None):
                            user_parts.append(it.text)
                            last_activity = time.monotonic()
                            prompted_silence = False  # il cliente ha parlato
                        ot = getattr(server_content, "output_transcription", None)
                        if ot and getattr(ot, "text", None):
                            agent_parts.append(ot.text)
                            last_activity = time.monotonic()

                        if getattr(server_content, "interrupted", False):
                            await twilio_ws.send_text(
                                json.dumps({"event": "clear", "streamSid": stream_sid})
                            )

                        if getattr(server_content, "turn_complete", False):
                            if user_parts:
                                log.info("UTENTE: %s", "".join(user_parts).strip())
                            if agent_parts:
                                log.info("AGENTE: %s", "".join(agent_parts).strip())
                            user_parts.clear()
                            agent_parts.clear()
                            if closing and not goodbye_sent:
                                goodbye_sent = True
                                await twilio_ws.send_text(
                                    json.dumps(
                                        {
                                            "event": "mark",
                                            "streamSid": stream_sid,
                                            "mark": {"name": _GOODBYE_MARK},
                                        }
                                    )
                                )

        async def silence_watchdog() -> None:
            nonlocal closing, prompted_silence
            while True:
                await asyncio.sleep(1)
                if closing:
                    continue
                idle = time.monotonic() - last_activity
                if idle >= SILENCE_HANGUP_S:
                    log.info("Silenzio prolungato (%.0fs): congedo e chiusura", idle)
                    closing = True
                    await _send_trigger(session, SILENCE_HANGUP_TRIGGER)
                elif idle >= SILENCE_PROMPT_S and not prompted_silence:
                    log.info("Silenzio (%.0fs): sollecito il cliente", idle)
                    prompted_silence = True
                    await _send_trigger(session, SILENCE_PROMPT_TRIGGER)

        watchdog = asyncio.create_task(silence_watchdog())
        t_in = asyncio.create_task(twilio_to_gemini())
        t_out = asyncio.create_task(gemini_to_twilio())
        done, pending = await asyncio.wait({t_in, t_out}, return_when=asyncio.FIRST_COMPLETED)
        watchdog.cancel()
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                raise exc
