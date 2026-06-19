"""Consegna via SMS attraverso Twilio.

Richiede le credenziali Twilio nelle variabili d'ambiente (vedi app.config).
In account trial, l'SMS parte solo verso numeri verificati.
"""
from __future__ import annotations

from twilio.rest import Client

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
from app.delivery.base import DeliveryChannel


class SmsDelivery(DeliveryChannel):
    def __init__(self) -> None:
        self._client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self._from = TWILIO_PHONE_NUMBER

    def send(self, to_number: str, body: str) -> None:
        self._client.messages.create(to=to_number, from_=self._from, body=body)
