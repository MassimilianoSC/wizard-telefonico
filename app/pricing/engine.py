"""Interfaccia del motore di preventivazione e modello del preventivo.

REGOLA ARCHITETTURALE (§3 del piano): il prezzo lo calcola SEMPRE codice
deterministico, mai l'LLM. L'LLM raccoglie le selezioni e chiama quote();
riceve un numero esatto e lo comunica. Il numero non lo "pensa" mai il modello.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class QuoteKind(str, Enum):
    EXACT = "exact"   # prezzo secco (es. pizzeria)
    RANGE = "range"   # forbice min-max / stima (es. edilizia, §4.4)


@dataclass(frozen=True)
class QuoteLine:
    code: str
    description: str
    quantity: float
    unit_price: float

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class Quote:
    kind: QuoteKind
    currency: str
    lines: list[QuoteLine]
    total: float
    total_min: float | None = None   # valorizzato solo per kind=RANGE
    total_max: float | None = None
    notes: str | None = None


class UnknownItemError(KeyError):
    """Selezione non nel listino: l'agente deve disambiguare, non indovinare (§4.3)."""


class PriceEngine(ABC):
    """Contratto comune a tutti i motori prezzi (pizzeria, edilizia, ...)."""

    @classmethod
    @abstractmethod
    def from_catalog(cls, catalog_path: Path) -> "PriceEngine":
        """Costruisce il motore caricando il listino dal file dati."""

    @abstractmethod
    def list_items(self) -> list[dict]:
        """Voci di listino disponibili (vocabolario chiuso per il matching)."""

    @abstractmethod
    def find_item(self, term: str) -> dict | None:
        """Risolve un termine libero in una voce, o None se ignoto/ambiguo."""

    @abstractmethod
    def quote(self, selections: list[dict]) -> Quote:
        """Calcola il preventivo esatto dalle selezioni [{code, quantity}, ...]."""
