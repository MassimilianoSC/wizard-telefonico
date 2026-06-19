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
6. ⬜ Primi test E2E del giro completo (squillo → ordine → preventivo → link)
7. ⬜ Arricchire il listino pizzeria di test: varianti/aggiunte, formati, combo
   (stressa meccaniche vicine all'edilizia; additivo, non rompe l'E2E) — DOPO il punto 6
8. ⬜ Riunione committente → sostituire pizzeria con tenant edilizia reale
9. ⬜ Hardening produzione (errori, logging, sicurezza, multitenant pieno,
   billing su account aziendale)

## Stato attuale
**Fase 1 completata.** Scaffold + motore prezzi pizzeria, committato e **pushato su
GitHub** (privato): https://github.com/MassimilianoSC/wizard-telefonico (remote
`origin`). Test 4/4 verdi in locale.

**Fase 2 — codice completo e deployato; manca solo l'accesso pubblico.**
Ponte Twilio↔Gemini scritto e validato (motore 4/4, smoke test Gemini Live OK).
App **deployata su Cloud Run**: `https://wizard-telefonico-850927676767.us-central1.run.app`
(region us-central1). Twilio: trial, numero `+16892250454`, SID/Token nel `.env`.

**Blocco (amministrativo, non tecnico):** la org policy aziendale (Domain Restricted
Sharing) vieta `allUsers` → il servizio risponde 403 agli anonimi, quindi Twilio non
lo raggiunge. Anche i quick tunnel Cloudflare non instradano dalla rete aziendale
(vedi memoria `vincoli-rete-aziendale-gcp`).

**Per sbloccare:** admin GCP che consenta `allUsers` (run.invoker) / eccezione alla
policy (soluzione di produzione), oppure rete non aziendale (hotspot) + tunnel per i
test. Test telefonico end-to-end ancora da fare.

## TODO (immediato) — sbloccare l'accesso pubblico, poi testare
- [ ] **Admin GCP**: eccezione alla org policy `iam.allowedPolicyMemberDomains`
      per consentire `allUsers` con ruolo `run.invoker` sul servizio `wizard-telefonico`
      (oppure l'admin esegue il binding). → rende pubblico l'endpoint per Twilio.
- [ ] In alternativa, per test immediati: rete non aziendale (hotspot) + tunnel.
- [ ] Test telefonico E2E: chiamare +16892250454 → agente pizzeria → ordine → totale.
- [ ] Verificare function calling/readback, poi consegna link via SMS.

## Come riprendere (servizi locali)
- Server locale per i test via tunnel: `PYTHONPATH=. .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787`
  (la porta 8000 è occupata da un altro programma dell'utente → usare 8787).
- Webhook Twilio: `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py <https://host>`
- Smoke test Gemini: `PYTHONPATH=. .venv/Scripts/python.exe scripts/smoke_live.py`
