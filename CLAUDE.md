# Wizard vocale telefonico — Guida per Claude

> File caricato a ogni sessione. Tieni aggiornate le sezioni
> **Stato attuale** e **TODO** a ogni avanzamento significativo.

## Scopo
Agente vocale che il cliente finale chiama al telefono: lo guida nella scelta
del prodotto, raccoglie i parametri di prezzo, calcola un **preventivo esatto**
con codice deterministico (mai l'LLM) e glielo recapita via messaggio (link).
Prodotto da portare sul mercato, venduto a più committenti.

Documento di riferimento completo: [piano-wizard-vocale.md](piano-wizard-vocale.md).

## Principi fermi
- **Separazione dei ruoli:** l'LLM conversa e raccoglie; il **codice calcola** il
  prezzo (motore deterministico via function calling). Mai prezzi dall'LLM/RAG.
- **Modulare e additivo:** da MVP a produzione si *indurisce*, non si riscrive.
- **Dominio-agnostico / tenant-ready:** listino = dati; motore prezzi dietro
  interfaccia; il tenant si risolve dal numero chiamato (Twilio `To`).
- **Meno lavoro = max riuso dell'idraulica, IP propria nel backend.**

## Stack
Python 3.12 + FastAPI · google-genai + ADK (voce) · Twilio (telefonia + SMS/
WhatsApp) · Gemini Live API · deploy su Google Cloud Run.

## Architettura (cartelle)
- `app/pricing/` — motore preventivi deterministico (interfaccia + pizzeria)
- `app/tenancy/` — modello Tenant + registro/risoluzione dal numero chiamato
- `app/delivery/` — consegna link (stub MVP → SMS/WhatsApp)
- `app/platform/` — ganci produzione no-op (consent/logging/retention)
- `app/telephony/` — idraulica Twilio↔Gemini (placeholder, dalla demo Google)
- `tenants/<id>/` — config per-tenant: `tenant.json` + `catalog.json` + `prompt.md`
- `tests/` — test del motore

## Roadmap (ordine di montaggio, §7-§8 del piano)
1. ✅ Scaffold tenant-ready + motore prezzi pizzeria + test (no telefonia)
2. ⬜ Idraulica: far squillare un numero (demo Google Twilio+Gemini)
3. ⬜ Function calling: l'agente chiama `quote` verso il listino finto
4. ⬜ Readback + gestione input ambigui (via di fuga)
5. ⬜ Consegna link via SMS (poi WhatsApp dopo verifica account)
6. ⬜ Riunione committente → sostituire pizzeria con tenant edilizia reale
7. ⬜ Hardening produzione (errori, logging, sicurezza, multitenant pieno)

## Stato attuale
**Fase 1 completata.** Scaffold creato, committato (branch `main`) e **pushato su
GitHub** (privato): https://github.com/MassimilianoSC/wizard-telefonico — remote
`origin`. Il motore prezzi pizzeria gira e supera i test (4/4) in locale, **senza**
telefonia né Gemini. Prossimo passo: Fase 2 (telefonia), che richiede config cloud
(numero Twilio + Gemini abilitato).

## TODO (immediato)
- [ ] Decidere se procedere con la config cloud (Twilio + Google Cloud) per la Fase 2
- [ ] Clonare/adattare la demo Google "Gemini Live Telephony" in `app/telephony/`
- [ ] Esporre un entrypoint FastAPI (`app/main.py`) col webhook Twilio
