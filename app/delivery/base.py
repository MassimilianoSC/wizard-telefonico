"""Canali di consegna del preventivo (link).

Nell'MVP solo uno stub che stampa. SMS e WhatsApp (§4.5) sono implementazioni
successive della stessa interfaccia.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DeliveryChannel(ABC):
    @abstractmethod
    def send_quote_link(self, to_number: str, link: str, summary: str) -> None:
        ...


class StubDelivery(DeliveryChannel):
    """No-op per l'MVP: non invia nulla, registra l'intento a console."""

    def send_quote_link(self, to_number: str, link: str, summary: str) -> None:
        print(f"[delivery:stub] -> {to_number}: {link}\n{summary}")
