"""Modello del Tenant.

Un Tenant è un committente servito dal sistema (una pizzeria, un'impresa
edile, ...). Nell'MVP ne esiste uno solo, ma il codice ne tratta sempre uno
risolto a runtime: aggiungere clienti = aggiungere tenant, senza riscrivere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Tenant:
    id: str
    display_name: str
    phone_number: str          # numero chiamato (Twilio "To") che identifica il tenant
    engine_type: str           # quale motore prezzi usare: "pizzeria", "edilizia", ...
    catalog_path: Path         # file del listino
    prompt_path: Path          # file del prompt del wizard
    delivery_channels: list[str] = field(default_factory=lambda: ["stub"])
