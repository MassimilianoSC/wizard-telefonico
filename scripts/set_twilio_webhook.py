"""Imposta il Voice webhook del numero Twilio al nostro endpoint /twiml.

Uso (dalla root):
  PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py https://<host-ngrok>
"""
from __future__ import annotations

import os
import sys

import app.config  # noqa: F401 — importa per caricare il .env (load_dotenv)
from twilio.rest import Client


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: set_twilio_webhook.py https://<host-ngrok>")
        sys.exit(1)

    base = sys.argv[1].rstrip("/")
    voice_url = f"{base}/twiml"

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    number = os.environ["TWILIO_PHONE_NUMBER"]

    client = Client(sid, token)
    matches = client.incoming_phone_numbers.list(phone_number=number)
    if not matches:
        print(f"Numero {number} non trovato nell'account Twilio.")
        sys.exit(1)

    updated = client.incoming_phone_numbers(matches[0].sid).update(
        voice_url=voice_url, voice_method="POST"
    )
    print(f"OK: Voice webhook di {number} -> {updated.voice_url} ({updated.voice_method})")


if __name__ == "__main__":
    main()
