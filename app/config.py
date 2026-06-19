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

# --- Timeout di silenzio (secondi) — tarabili via env senza ricompilare ---
SILENCE_PROMPT_S = float(os.getenv("SILENCE_PROMPT_S", "10"))   # sollecito dopo N s di silenzio
SILENCE_HANGUP_S = float(os.getenv("SILENCE_HANGUP_S", "22"))   # chiusura dopo ulteriore silenzio
