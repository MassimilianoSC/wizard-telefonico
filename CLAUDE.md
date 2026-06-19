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
Python 3.13 + FastAPI · google-genai + Gemini Live API native-audio (Vertex AI) ·
Twilio (telefonia Media Streams + SMS) · audioop-lts (audio) · deploy su Cloud Run.

## Architettura (cartelle)
- `app/pricing/` — motore preventivi deterministico (interfaccia + pizzeria)
- `app/tenancy/` — modello Tenant + registro/risoluzione dal numero chiamato
- `app/agent/` — runtime: tool `calcola_preventivo`, system instruction, dispatch
- `app/telephony/` — ponte Twilio↔Gemini Live (`bridge.py`, `audio.py`)
- `app/delivery/` — consegna link (stub MVP → SMS/WhatsApp)
- `app/platform/` — ganci produzione no-op (consent/logging/retention)
- `app/main.py` — FastAPI: `/twiml`, WebSocket `/ws`, `/health`
- `tenants/<id>/` — config per-tenant: `tenant.json` + `catalog.json` + `prompt.md`
- `Dockerfile` + `.dockerignore` — deploy Cloud Run
- `scripts/` — `smoke_live.py` (test Gemini), `set_twilio_webhook.py`
- `tests/` — test del motore

## Roadmap
1. ✅ Scaffold tenant-ready + motore prezzi pizzeria + test
2. ✅ Idraulica: far squillare (Twilio Media Streams ↔ Gemini Live)
3. ✅ Function calling: l'agente chiama `calcola_preventivo` verso il motore
4. 🔄 Readback + gestione input ambigui (da raffinare/osservare sul campo)
5. ⬜ Consegna link/riepilogo via SMS (ora è uno stub) → poi WhatsApp
6. ✅ Primi test E2E: **chiamata reale funzionante**
7. ⬜ Arricchire il listino pizzeria (varianti/aggiunte, formati, combo)
8. ⬜ Riunione committente → tenant edilizia reale (listino + logica parametrica)
9. ⬜ Produzione: migrare su GCP aziendale HQE (org policy via admin) + hardening
   (errori, logging, sicurezza, multitenant pieno, billing aziendale)

## Stato attuale
**Fase 2 COMPLETATA ✅ — la chiamata telefonica end-to-end funziona.**
L'agente risponde su **+16892250454**, conversa in italiano (Gemini Live
native-audio) e calcola i preventivi col motore deterministico.

Deploy: **Cloud Run sul GCP personale** `wizard-mvp-mc25` →
`https://wizard-telefonico-699544336212.us-central1.run.app` (us-central1),
pubblico, webhook Twilio su `/twiml`.

**Contesto:** gira sul GCP **personale** (test di sostenibilità). Per la produzione
(azienda HQE) si replica lo stesso deploy sul GCP aziendale, sistemando la org policy
`iam.allowedPolicyMemberDomains` con l'admin (vedi memoria `vincoli-rete-aziendale-gcp`).
**Lezione appresa:** passare env multiple a gcloud da PowerShell — la virgola unisce
gli argomenti in una sola stringa; settarle una alla volta o dallo shell sh.

## TODO (immediato)
- [ ] `git push` dei commit locali su GitHub (diversi commit non ancora pushati)
- [ ] Raffinare/osservare readback e gestione input ambigui in chiamata
- [ ] Implementare consegna link/riepilogo via SMS (ora `StubDelivery`)
- [ ] (Con l'utente) discutere le evoluzioni del prodotto
- [ ] Produzione (post-riunione 22/6): replicare il deploy sul GCP aziendale HQE

## Come riprendere
- **Servizio live:** Cloud Run `wizard-telefonico` (progetto `wizard-mvp-mc25`,
  us-central1). Demo: chiamare +16892250454 (premere un tasto al messaggio trial).
- **Re-deploy dopo modifiche:** dalla root →
  `gcloud run deploy wizard-telefonico --source . --region us-central1 --allow-unauthenticated --timeout 3600`
  (env già sulla revisione; per modificarle `--update-env-vars` UNA alla volta).
- **Log:** `gcloud run services logs read wizard-telefonico --region us-central1 --project wizard-mvp-mc25 --limit 100`
- **Webhook Twilio:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py <https://host>`
- **Smoke test Gemini:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/smoke_live.py`
- **Test motore:** `pytest -q`  ·  In locale usare la porta 8787 (la 8000 è occupata).
