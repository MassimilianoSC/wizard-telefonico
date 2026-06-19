"""Gancio consenso/opt-in (GDPR, §10). Stub no-op nell'MVP.

In produzione: persistere fonte, timestamp, scopo e identificativo dell'opt-in
(la trascrizione della chiamata è la prova, §4.5).
"""
from __future__ import annotations


def record_consent(tenant_id: str, phone: str, source: str, purpose: str) -> None:
    # MVP: no-op. Produzione: scrittura durevole con timestamp/fonte/scopo.
    print(f"[consent:stub] tenant={tenant_id} phone={phone} source={source} purpose={purpose}")
