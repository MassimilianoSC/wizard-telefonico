"""Smoke test: apre una sessione Gemini Live su Vertex AI e la chiude.

Valida credenziali ADC + project + location + model ID, SENZA telefonia.
Esegui dalla root:  PYTHONPATH=. .venv/Scripts/python.exe scripts/smoke_live.py
"""
from __future__ import annotations

import asyncio

from app.config import GCP_LOCATION, GCP_PROJECT, GEMINI_MODEL
from app.telephony.bridge import _client, _live_config


async def main() -> None:
    print(f"Project={GCP_PROJECT}  Location={GCP_LOCATION}  Model={GEMINI_MODEL}")
    config = _live_config("Sei un assistente di test. Rispondi in modo brevissimo.")
    async with _client.aio.live.connect(model=GEMINI_MODEL, config=config):
        print("OK: sessione Gemini Live aperta correttamente.")
    print("OK: sessione chiusa. Lato Gemini cablato correttamente.")


if __name__ == "__main__":
    asyncio.run(main())
