"""Canali di consegna del messaggio al cliente.

`StubDelivery` (no-op) per i test locali; `SmsDelivery` (in sms.py) per l'invio
reale via Twilio. La scelta del canale è una proprietà del tenant.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DeliveryChannel(ABC):
    @abstractmethod
    def send(self, to_number: str, body: str) -> None:
        """Invia `body` al numero `to_number`."""


class StubDelivery(DeliveryChannel):
    """No-op per l'MVP/locale: non invia nulla, stampa a console."""

    def send(self, to_number: str, body: str) -> None:
        print(f"[delivery:stub] -> {to_number}:\n{body}")
