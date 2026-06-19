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

**Fase 2 in corso.** GCP: progetto `wizard-telefonico`, Vertex AI abilitata, billing
personale (temporaneo). **Twilio: trial attivo, numero `+16892250454` (USA, Voice+SMS)
agganciato al tenant pizzeria-demo, cellulare verificato, SID/Token nel `.env`.**
gcloud installato; **ngrok e dipendenze Python da installare**. Demo ufficiale di
riferimento individuata (vedi memoria `ref-demo-gemini-live-telephony`).
Prossimo: cablare il ponte Twilio↔Gemini partendo dalla demo ufficiale Google.

## TODO (immediato) — Fase 2: "far squillare"
- [ ] Installare ngrok (+ authtoken di account gratuito)
- [ ] `gcloud auth application-default login` + set-quota-project wizard-telefonico
- [ ] Installare dipendenze Python (fastapi, uvicorn, twilio, google-genai, python-samplerate, websockets)
- [ ] Portare la demo ufficiale "gemini-live-telephony-app" come base dell'idraulica
- [ ] Avviare uvicorn + ngrok → puntare il webhook Twilio (`/twiml`) all'URL ngrok
- [ ] Chiamare +16892250454 → l'agente risponde (numero che squilla, §7)
- [ ] Poi: innestare il function calling verso il motore prezzi (nostro IP)
