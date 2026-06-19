"""Motore prezzi per il dominio 'pizzeria': somma di voci di listino.

Implementazione MVP. È un'implementazione di PriceEngine: il dominio 'edilizia'
sarà un'altra implementazione (prezzo parametrico) dietro la stessa interfaccia,
senza toccare il resto del sistema.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.pricing.engine import (
    PriceEngine,
    Quote,
    QuoteKind,
    QuoteLine,
    UnknownItemError,
)


class PizzeriaEngine(PriceEngine):
    def __init__(self, currency: str, items: list[dict]) -> None:
        self._currency = currency
        # indice code -> item per lookup O(1)
        self._by_code: dict[str, dict] = {it["code"]: it for it in items}

    @classmethod
    def from_catalog(cls, catalog_path: Path) -> "PizzeriaEngine":
        data = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        return cls(currency=data.get("currency", "EUR"), items=data["items"])

    def list_items(self) -> list[dict]:
        return list(self._by_code.values())

    def find_item(self, term: str) -> dict | None:
        """Match a vocabolario chiuso: code esatto, nome, o alias. None se ignoto."""
        t = term.strip().lower()
        for item in self._by_code.values():
            if item["code"].lower() == t:
                return item
            if item["name"].lower() == t:
                return item
            if t in [a.lower() for a in item.get("aliases", [])]:
                return item
        return None

    def quote(self, selections: list[dict]) -> Quote:
        lines: list[QuoteLine] = []
        for sel in selections:
            code = sel["code"]
            item = self._by_code.get(code)
            if item is None:
                raise UnknownItemError(code)
            qty = float(sel.get("quantity", 1))
            lines.append(
                QuoteLine(
                    code=code,
                    description=item["name"],
                    quantity=qty,
                    unit_price=float(item["unit_price"]),
                )
            )
        total = round(sum(line.subtotal for line in lines), 2)
        return Quote(
            kind=QuoteKind.EXACT,
            currency=self._currency,
            lines=lines,
            total=total,
        )
