"""Impostazioni globali dell'applicazione (non per-tenant).

Le configurazioni per-tenant (listino, prompt, numeri) vivono nei file sotto
tenants/<id>/ e si caricano via app.tenancy.registry, NON qui.
"""
from __future__ import annotations

import os
from pathlib import Path

# Radice del progetto e cartella dei tenant.
BASE_DIR = Path(__file__).resolve().parent.parent
TENANTS_DIR = BASE_DIR / "tenants"

# Tenant di default usato in locale quando la chiamata non porta un numero
# (es. test del motore senza telefonia). Nell'MVP esiste un solo tenant.
DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "pizzeria-demo")

# Valuta di fallback se un listino non la specifica.
DEFAULT_CURRENCY = "EUR"
