"""Registro dei tenant: caricamento e risoluzione.

Carica i tenant dai file tenants/<id>/tenant.json e li risolve a partire dal
numero chiamato. Factory del motore prezzi in base a engine_type.
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import DEFAULT_TENANT_ID, TENANTS_DIR
from app.delivery.base import DeliveryChannel, StubDelivery
from app.delivery.sms import SmsDelivery
from app.pricing.engine import PriceEngine
from app.pricing.pizzeria import PizzeriaEngine
from app.tenancy.models import Tenant

# Mappa engine_type -> classe del motore. Estendere qui per nuovi domini.
_ENGINES: dict[str, type[PriceEngine]] = {
    "pizzeria": PizzeriaEngine,
}


@lru_cache(maxsize=1)
def _load_all() -> dict[str, Tenant]:
    tenants: dict[str, Tenant] = {}
    for tenant_file in TENANTS_DIR.glob("*/tenant.json"):
        data = json.loads(tenant_file.read_text(encoding="utf-8"))
        tenant_dir = tenant_file.parent
        tenant = Tenant(
            id=data["id"],
            display_name=data["display_name"],
            # Accetta sia `phone_numbers` (lista) sia `phone_number` (singolo, retrocompat).
            phone_numbers=data.get("phone_numbers")
            or ([data["phone_number"]] if data.get("phone_number") else []),
            engine_type=data["engine_type"],
            catalog_path=tenant_dir / data["catalog_file"],
            prompt_path=tenant_dir / data["prompt_file"],
            delivery_channels=data.get("delivery_channels", ["stub"]),
        )
        tenants[tenant.id] = tenant
    return tenants


def get_tenant(tenant_id: str) -> Tenant:
    tenants = _load_all()
    if tenant_id not in tenants:
        raise KeyError(f"Tenant sconosciuto: {tenant_id!r}")
    return tenants[tenant_id]


def resolve(to_number: str | None = None) -> Tenant:
    """Risolve il tenant dal numero chiamato (campo Twilio 'To').

    Nell'MVP, se il numero non è fornito o non corrisponde, si ricade sul
    tenant di default. In produzione un numero non mappato sarà un errore.
    """
    tenants = _load_all()
    if to_number:
        for tenant in tenants.values():
            if to_number in tenant.phone_numbers:
                return tenant
    return get_tenant(DEFAULT_TENANT_ID)


def build_engine(tenant: Tenant) -> PriceEngine:
    """Istanzia il motore prezzi giusto per il tenant."""
    try:
        engine_cls = _ENGINES[tenant.engine_type]
    except KeyError:
        raise ValueError(f"engine_type non supportato: {tenant.engine_type!r}")
    return engine_cls.from_catalog(tenant.catalog_path)


def build_delivery(tenant: Tenant) -> DeliveryChannel:
    """Istanzia il canale di consegna del tenant (SMS reale o stub)."""
    channel = tenant.delivery_channels[0] if tenant.delivery_channels else "stub"
    if channel == "sms":
        return SmsDelivery()
    return StubDelivery()
