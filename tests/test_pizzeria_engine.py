from pathlib import Path

import pytest

from app.pricing.engine import QuoteKind, UnknownItemError
from app.pricing.pizzeria import PizzeriaEngine

CATALOG = (
    Path(__file__).resolve().parent.parent
    / "tenants"
    / "pizzeria-demo"
    / "catalog.json"
)


@pytest.fixture
def engine() -> PizzeriaEngine:
    return PizzeriaEngine.from_catalog(CATALOG)


def test_quote_totale_corretto(engine: PizzeriaEngine):
    q = engine.quote(
        [
            {"code": "pizza_margherita", "quantity": 2},
            {"code": "birra_33cl", "quantity": 1},
        ]
    )
    assert q.kind is QuoteKind.EXACT
    assert q.currency == "EUR"
    # 2 * 6.00 + 1 * 3.50 = 15.50
    assert q.total == 15.5
    assert len(q.lines) == 2


def test_codice_sconosciuto_solleva_errore(engine: PizzeriaEngine):
    with pytest.raises(UnknownItemError):
        engine.quote([{"code": "pizza_inesistente", "quantity": 1}])


def test_find_item_per_alias(engine: PizzeriaEngine):
    item = engine.find_item("margherita")
    assert item is not None and item["code"] == "pizza_margherita"


def test_find_item_ignoto_ritorna_none(engine: PizzeriaEngine):
    assert engine.find_item("sushi") is None
