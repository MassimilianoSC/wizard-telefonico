"""Ponte Twilio Media Streams <-> Gemini Live API.

Flusso di una chiamata:
1. Twilio apre il WebSocket e invia `start` (con streamSid + tenant_id + from_number
   passati dal TwiML come custom parameter). Da lì risolviamo tenant, motore, prompt
   e canale di consegna.
2. Apriamo la sessione Gemini Live (audio it-IT, voce, tool, trascrizioni) e
   iniettiamo un turno iniziale così l'agente saluta per primo.
3. Tre loop concorrenti: Twilio->Gemini, Gemini->Twilio, watchdog.
   Il watchdog distingue due casi:
   - **cliente che tace** (l'agente ha già risposto) -> sollecito, poi congedo/chiusura;
   - **agente muto** dopo che il cliente ha parlato (stallo) -> nudge per farlo ripartire.
4. Chiusura: `end_call` (o il watchdog) imposta `closing`; alla chiusura per
   `end_call` inviamo al cliente un SMS col riepilogo. Finita la frase di congedo
   inviamo un `mark`; quando Twilio ce lo rimanda chiudiamo il WebSocket.
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
    STALL_NUDGE_S,
    TWILIO_RATE,
    VAD_PREFIX_PADDING_MS,
    VAD_SILENCE_MS,
    DEFAULT_TENANT_ID,
)
from app.agent.runtime import (
    GREETING_TRIGGER,
    SILENCE_HANGUP_TRIGGER,
    SILENCE_PROMPT_TRIGGER,
    STALL_NUDGE_TRIGGER,
    TOOLS,
    build_system_instruction,
    dispatch_tool_call,
    format_order_sms,
)
from app.platform.logging import get_logger
from app.telephony.audio import Resampler, pcm16_to_ulaw, ulaw_to_pcm16
from app.tenancy.registry import build_delivery, build_engine, get_tenant

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
        # Rilevazione fine-turno resa ESPLICITA: il default puro lasciava l'agente
        # appeso su frasi brevi di chiusura ("No, va bene così") finche' un nuovo
        # audio non rimetteva in moto il VAD (cfr. issue live-api #142 + comfort-noise PSTN).
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                silence_duration_ms=VAD_SILENCE_MS,
                prefix_padding_ms=VAD_PREFIX_PADDING_MS,
            )
        ),
    )


async def _send_trigger(session, text: str) -> None:
    """Inietta un turno 'di sistema' per far reagire l'agente (saluto, sollecito, nudge)."""
    await session.send_client_content(
        turns=types.Content(role="user", parts=[types.Part.from_text(text=text)]),
        turn_complete=True,
    )


async def _wait_for_start(twilio_ws) -> tuple[str, str, str]:
    """Legge i messaggi finché arriva `start`; ritorna (stream_sid, tenant_id, from_number)."""
    while True:
        msg = json.loads(await twilio_ws.receive_text())
        if msg.get("event") == "start":
            start = msg["start"]
            params = start.get("customParameters", {})
            return (
                start["streamSid"],
                params.get("tenant_id", DEFAULT_TENANT_ID),
                params.get("from_number", ""),
            )


async def run_bridge(twilio_ws) -> None:
    stream_sid, tenant_id, from_number = await _wait_for_start(twilio_ws)
    tenant = get_tenant(tenant_id)
    engine = build_engine(tenant)
    delivery = build_delivery(tenant)
    log.info("Chiamata per tenant '%s' da %s (stream %s)", tenant.id, from_number, stream_sid)

    config = _live_config(build_system_instruction(tenant, engine))

    up = Resampler(TWILIO_RATE, GEMINI_IN_RATE)      # 8k -> 16k (verso Gemini)
    down = Resampler(GEMINI_OUT_RATE, TWILIO_RATE)   # 24k -> 8k (verso Twilio)

    # Stato condiviso.
    closing = False
    goodbye_sent = False
    last_activity = time.monotonic()    # ultima attività vocale (utente o agente)
    last_user_speech = time.monotonic()  # ultima volta che il CLIENTE ha parlato
    awaiting_agent = False               # il cliente ha parlato, l'agente non ha ancora finito di rispondere
    nudged = False                       # nudge anti-stallo già inviato in questo turno
    prompted_silence = False             # sollecito di silenzio già inviato
    last_quote: dict | None = None       # ultimo preventivo calcolato, per l'SMS
    t0 = time.monotonic()                # riferimento per i timestamp relativi degli eventi

    def ev(msg: str) -> None:
        """Logga un evento NELL'ISTANTE in cui accade → ordine e timing affidabili.
        Le righe `UTENTE:`/`AGENTE:` complete restano a fine turno solo come riepilogo
        del CONTENUTO: NON usarle per dedurre l'ordine degli eventi (escono insieme,
        in ordine prefissato, a `turn_complete`). Per ordine/timing usare le righe `EV`."""
        log.info("EV +%6.2fs %s", time.monotonic() - t0, msg)

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
            nonlocal closing, goodbye_sent, last_activity, last_user_speech
            nonlocal awaiting_agent, nudged, prompted_silence, last_quote
            user_parts: list[str] = []
            agent_parts: list[str] = []
            while True:
                async for response in session.receive():
                    tool_call = getattr(response, "tool_call", None)
                    if tool_call and tool_call.function_calls:
                        replies = []
                        for fc in tool_call.function_calls:
                            args = dict(fc.args or {})
                            log.info("TOOL CALL: %s(%s)", fc.name, args)
                            ev("tool: %s" % fc.name)
                            result = dispatch_tool_call(fc.name, args, engine)
                            if fc.name == "calcola_preventivo" and "total" in result:
                                last_quote = result
                            elif fc.name == "end_call":
                                closing = True
                                if from_number and last_quote:
                                    body = format_order_sms(last_quote, tenant.display_name)
                                    try:
                                        await asyncio.to_thread(delivery.send, from_number, body)
                                        log.info("SMS riepilogo inviato a %s", from_number)
                                        result = {"status": "ok", "sms": "inviato"}
                                    except Exception:
                                        log.exception("Invio SMS fallito")
                                        result = {"status": "ok", "sms": "fallito"}
                            replies.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                            )
                        await session.send_tool_response(function_responses=replies)
                        continue

                    if getattr(response, "data", None):
                        if awaiting_agent:
                            ev("agente: prima risposta (%.2fs dopo l'utente)"
                               % (time.monotonic() - last_user_speech))
                        last_activity = time.monotonic()
                        awaiting_agent = False   # l'agente sta emettendo audio: il suo turno e' partito
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
                            if not user_parts:
                                ev("utente: inizio parlato")
                            user_parts.append(it.text)
                            now = time.monotonic()
                            last_activity = now
                            last_user_speech = now
                            awaiting_agent = True   # il cliente ha parlato: aspettiamo l'agente
                            nudged = False
                            prompted_silence = False
                        ot = getattr(server_content, "output_transcription", None)
                        if ot and getattr(ot, "text", None):
                            if awaiting_agent:
                                ev("agente: prima risposta (%.2fs dopo l'utente)"
                                   % (time.monotonic() - last_user_speech))
                            agent_parts.append(ot.text)
                            last_activity = time.monotonic()
                            awaiting_agent = False   # l'agente ha prodotto output: non e' piu' "muto"

                        if getattr(server_content, "interrupted", False):
                            ev("barge-in: l'utente interrompe l'agente")
                            await twilio_ws.send_text(
                                json.dumps({"event": "clear", "streamSid": stream_sid})
                            )

                        if getattr(server_content, "turn_complete", False):
                            ev("--- fine turno ---")
                            if user_parts:
                                log.info("UTENTE: %s", "".join(user_parts).strip())
                            if agent_parts:
                                log.info("AGENTE: %s", "".join(agent_parts).strip())
                            user_parts.clear()
                            agent_parts.clear()
                            # awaiting_agent NON si resetta qui: turn_complete puo' arrivare
                            # col turno utente chiuso ma SENZA output dell'agente (agente
                            # piantato dopo la conferma). Il reset avviene sull'output reale
                            # dell'agente (response.data / output_transcription), cosi' il
                            # watchdog puo' fare il nudge a 6s invece di lasciarlo appeso.
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

        async def watchdog() -> None:
            nonlocal closing, prompted_silence, awaiting_agent, nudged
            while True:
                await asyncio.sleep(1)
                if closing:
                    continue
                now = time.monotonic()
                if awaiting_agent:
                    # L'agente dovrebbe rispondere ma tace: nudge (una volta), poi
                    # torniamo al regime di silenzio normale.
                    if not nudged and (now - last_user_speech) >= STALL_NUDGE_S:
                        log.info("Stallo agente (%.0fs): nudge", now - last_user_speech)
                        nudged = True
                        awaiting_agent = False
                        await _send_trigger(session, STALL_NUDGE_TRIGGER)
                    continue
                # Cliente in silenzio dopo che l'agente ha finito.
                idle = now - last_activity
                if idle >= SILENCE_HANGUP_S:
                    log.info("Silenzio prolungato (%.0fs): congedo e chiusura", idle)
                    closing = True
                    await _send_trigger(session, SILENCE_HANGUP_TRIGGER)
                elif idle >= SILENCE_PROMPT_S and not prompted_silence:
                    log.info("Silenzio (%.0fs): sollecito il cliente", idle)
                    prompted_silence = True
                    await _send_trigger(session, SILENCE_PROMPT_TRIGGER)

        wd = asyncio.create_task(watchdog())
        t_in = asyncio.create_task(twilio_to_gemini())
        t_out = asyncio.create_task(gemini_to_twilio())
        done, pending = await asyncio.wait({t_in, t_out}, return_when=asyncio.FIRST_COMPLETED)
        wd.cancel()
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                raise exc
