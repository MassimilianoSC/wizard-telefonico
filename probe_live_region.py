#!/usr/bin/env python3
"""Probe di disponibilità region per il modello Gemini Live API native-audio.

Scopo: confermare SUL CAMPO che `gemini-live-2.5-flash-native-audio` (GA) è
servito da `europe-west8` (Milano), aprendo una vera sessione Live API
(`live.connect`). Se l'handshake/setup va a buon fine → la region serve il
modello. Se torna un policy/region error → no.

Perché NON `gcloud ai models list`: quel comando elenca i modelli del Model
Registry del progetto (i custom caricati da te), non i foundation model
gestiti di Gemini. Su europe-west8 tornerebbe vuoto a prescindere → falso
negativo. L'unico test affidabile è l'apertura di sessione Live.

Logica dell'esperimento:
  - Probe PRIMARIO  -> europe-west8   (quello che vuoi confermare)
  - Probe CONTROLLO -> us-central1     (region notoriamente servita)
  Interpretazione:
    EU ok                       -> CONFERMATO: Milano serve il native-audio.
    EU fallisce + US ok         -> problema di REGION (EU non serve il modello).
    EU fallisce + US fallisce   -> problema di SETUP (ADC/quota/permessi), non region.

Prerequisiti:
  pip install --upgrade google-genai
  gcloud auth application-default login
  gcloud auth application-default set-quota-project wizard-telefonico

Uso:
  python probe_live_region.py
  python probe_live_region.py --project wizard-telefonico --region europe-west8
  python probe_live_region.py --no-control          # solo europe-west8
  python probe_live_region.py --send-turn           # invia anche un turno e attende 1 risposta (prova più "forte")
"""
from __future__ import annotations

import argparse
import asyncio
import sys

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit(
        "Manca il pacchetto google-genai.\n"
        "Installa con:  pip install --upgrade google-genai"
    )

MODEL = "gemini-live-2.5-flash-native-audio"

# Euristiche per classificare l'errore (solo per leggibilità: l'errore grezzo
# viene SEMPRE stampato, così puoi giudicare da te).
REGION_HINTS = ("not supported", "not available", "failed_precondition",
                "is not allowed", "unsupported location", "location",
                "region", "policy", "not found for api version")
AUTH_HINTS = ("credential", "authenticat", "permission", "401", "403",
              "default credentials", "could not automatically determine")
QUOTA_HINTS = ("quota", "resource_exhausted", "429", "rate limit")


def classify(err_text: str) -> str:
    t = err_text.lower()
    if any(h in t for h in AUTH_HINTS):
        return "SETUP/AUTH (ADC o permessi) — non è un verdetto sulla region"
    if any(h in t for h in QUOTA_HINTS):
        return "QUOTA/RATE LIMIT — non è un verdetto sulla region"
    if any(h in t for h in REGION_HINTS):
        return "REGION/POLICY — la region rifiuta il modello"
    return "ALTRO — leggi l'errore grezzo qui sotto"


async def probe(project: str, region: str, send_turn: bool) -> bool:
    """Apre una sessione Live verso `region`. Ritorna True se l'handshake regge."""
    label = f"[{region}]"
    print(f"\n{label} Creo client Vertex (project={project})...")
    client = genai.Client(vertexai=True, project=project, location=region)

    config = types.LiveConnectConfig(response_modalities=["AUDIO"])

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            # Se siamo qui, il setup di sessione è stato ACCETTATO dal server:
            # è già la prova che region+modello sono validi.
            print(f"{label} ✓ Sessione aperta: setup accettato (handshake OK).")

            if send_turn:
                # Prova più forte: invio un turno minimo e attendo la prima
                # risposta del server, con timeout, per confermare che il
                # modello risponde davvero da questa region.
                print(f"{label}   Invio un turno di prova e attendo 1 risposta...")
                await session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text="ping")]),
                    turn_complete=True,
                )
                try:
                    async with asyncio.timeout(20):
                        async for _ in session.receive():
                            print(f"{label}   ✓ Ricevuta risposta dal server "
                                  "(il modello risponde da questa region).")
                            break
                except TimeoutError:
                    print(f"{label}   ⚠ Nessuna risposta entro 20s. Il setup era "
                          "OK ma il turno non ha prodotto output: anomalia da "
                          "indagare (non necessariamente di region).")
                    return True  # il setup è comunque passato: region valida
            return True

    except Exception as exc:  # noqa: BLE001  (vogliamo vedere QUALSIASI errore)
        err_text = f"{type(exc).__name__}: {exc}"
        print(f"{label} ✗ Sessione NON aperta.")
        print(f"{label}   Classificazione: {classify(err_text)}")
        print(f"{label}   Errore grezzo:   {err_text}")
        return False


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="wizard-telefonico",
                    help="Google Cloud project id (default: wizard-telefonico)")
    ap.add_argument("--region", default="europe-west8",
                    help="Region primaria da verificare (default: europe-west8)")
    ap.add_argument("--control", default="us-central1",
                    help="Region di controllo (default: us-central1)")
    ap.add_argument("--no-control", action="store_true",
                    help="Salta il probe di controllo")
    ap.add_argument("--send-turn", action="store_true",
                    help="Oltre all'handshake, invia un turno e attende 1 risposta")
    args = ap.parse_args()

    print("=" * 64)
    print("PROBE Live API — disponibilità region")
    print(f"Modello: {MODEL}")
    print("=" * 64)

    eu_ok = await probe(args.project, args.region, args.send_turn)

    us_ok = None
    if not args.no_control:
        us_ok = await probe(args.project, args.control, args.send_turn)

    # Verdetto
    print("\n" + "=" * 64)
    print("VERDETTO")
    print("=" * 64)
    if eu_ok:
        print(f"✓ CONFERMATO: {args.region} serve {MODEL}.")
        print("  La doc ufficiale è confermata sul campo. Data residency UE e")
        print("  guadagno di latenza (Cloud Run + modello in EU) sono reali.")
    else:
        if us_ok is True:
            print(f"✗ {args.region} NON serve il modello, ma {args.control} sì.")
            print("  => È un problema di REGION: il native-audio non è (ancora)")
            print("     disponibile su quella region per il tuo progetto.")
            print("     Rivedi la doc/region o apri un caso a Google Cloud.")
        elif us_ok is False:
            print(f"✗ Falliscono SIA {args.region} SIA {args.control}, allo stesso modo.")
            print("  => Probabile problema di SETUP (ADC/quota/permessi), NON di")
            print("     region. Controlla:")
            print("       gcloud auth application-default login")
            print("       gcloud auth application-default set-quota-project " + args.project)
            print("     e che l'API aiplatform sia abilitata sul progetto.")
        else:
            print(f"✗ {args.region} non ha aperto sessione (controllo saltato).")
            print("  Rilancia senza --no-control per distinguere region vs setup.")

    return 0 if eu_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
