"""Impostazioni globali dell'applicazione (non per-tenant).

Le configurazioni per-tenant (listino, prompt, numeri) vivono nei file sotto
tenants/<id>/ e si caricano via app.tenancy.registry, NON qui.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Radice del progetto e cartella dei tenant.
BASE_DIR = Path(__file__).resolve().parent.parent
TENANTS_DIR = BASE_DIR / "tenants"

# Carica le variabili dal .env (se presente) nell'ambiente.
load_dotenv(BASE_DIR / ".env")

# Tenant di default usato in locale quando la chiamata non porta un numero
# (es. test del motore senza telefonia). Nell'MVP esiste un solo tenant.
DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "pizzeria-demo")

# Valuta di fallback se un listino non la specifica.
DEFAULT_CURRENCY = "EUR"

# --- Twilio (per l'invio SMS; su Cloud Run vanno passati come env/segreti) ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# --- Google / Gemini (Vertex AI) ---
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "wizard-telefonico")
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-live-2.5-flash-native-audio")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Kore")
GEMINI_LANGUAGE = os.getenv("GEMINI_LANGUAGE", "it-IT")

# --- Telefonia ---
# Host pubblico (ngrok in dev, Cloud Run in prod), SENZA schema. Vuoto in dev:
# viene dedotto dall'header Host della richiesta Twilio.
SERVICE_HOST = os.getenv("SERVICE_HOST", "").strip()

# --- Sample rate audio (Hz) ---
TWILIO_RATE = 8000      # G.711 u-law in/out verso Twilio
GEMINI_IN_RATE = 16000  # PCM16 atteso da Gemini in ingresso
GEMINI_OUT_RATE = 24000  # PCM16 prodotto da Gemini in uscita

# --- Timeout di silenzio e anti-stallo (secondi) — tarabili via env ---
SILENCE_PROMPT_S = float(os.getenv("SILENCE_PROMPT_S", "16"))   # sollecito se il CLIENTE tace (dopo che l'agente ha finito)
SILENCE_HANGUP_S = float(os.getenv("SILENCE_HANGUP_S", "30"))   # chiusura dopo ulteriore silenzio
STALL_NUDGE_S = float(os.getenv("STALL_NUDGE_S", "6"))          # nudge se l'AGENTE non risponde dopo che il cliente ha parlato (rete anti-stallo fine-turno; era 9)

# --- VAD: automatic_activity_detection (rilevazione fine-turno utente) — tarabili via env ---
# silence_duration_ms: silenzio RILEVATO prima di chiudere il turno utente.
#   Default server ~800ms; consigliato 500-800. Più basso = chiude prima (ma rischio di spezzare frasi).
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "500"))
# prefix_padding_ms: audio incluso PRIMA che lo speech sia rilevato (evita di tagliare l'inizio delle parole in ingresso).
#   Default native-audio = 0 (taglia gli attacchi); 100 = compromesso prudente.
VAD_PREFIX_PADDING_MS = int(os.getenv("VAD_PREFIX_PADDING_MS", "100"))
