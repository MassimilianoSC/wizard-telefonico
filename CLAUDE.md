# Wizard vocale telefonico — Guida per Claude

> File caricato a ogni sessione. Tieni aggiornate le sezioni
> **Stato attuale** e **TODO** a ogni avanzamento significativo.

## Scopo
Agente vocale che il cliente finale chiama al telefono: lo guida nella scelta
del prodotto, raccoglie i parametri di prezzo, calcola un **preventivo esatto**
con codice deterministico (mai l'LLM) e glielo recapita via messaggio.
Prodotto da portare sul mercato, venduto a più committenti.

Documento di riferimento completo: [piano-wizard-vocale.md](piano-wizard-vocale.md).

## Principi fermi
- **Separazione dei ruoli:** l'LLM conversa e raccoglie; il **codice calcola** il
  prezzo (motore deterministico via function calling). Mai prezzi dall'LLM/RAG.
- **Modulare e additivo:** da MVP a produzione si *indurisce*, non si riscrive.
- **Dominio-agnostico / tenant-ready:** listino = dati; motore prezzi dietro
  interfaccia; il tenant si risolve dal numero chiamato (Twilio `To`).
- **Meno lavoro = max riuso dell'idraulica, IP propria.** Deploy a fine batch.

## Stack
Python 3.13 + FastAPI · google-genai + Gemini Live API native-audio (Vertex AI) ·
Twilio (telefonia Media Streams + SMS) · audioop-lts (audio) · deploy su Cloud Run.

## Architettura (cartelle)
- `app/pricing/` — motore preventivi deterministico (interfaccia + pizzeria)
- `app/tenancy/` — Tenant + registro (risoluzione dal numero, build engine/delivery)
- `app/agent/runtime.py` — tool (`calcola_preventivo`, `end_call`), system instruction, trigger, SMS format
- `app/telephony/bridge.py` — ponte Twilio↔Gemini (audio, watchdog silenzio, chiusura, trascrizioni)
- `app/delivery/` — consegna: `StubDelivery` / `SmsDelivery`
- `app/main.py` — FastAPI: `/twiml` (+ from_number), WebSocket `/ws`, `/health`
- `tenants/<id>/` — `tenant.json` + `catalog.json` (con categoria) + `prompt.md`
- `Dockerfile` · `scripts/` (smoke_live, set_twilio_webhook) · `tests/`

## Roadmap
1. ✅ Scaffold tenant-ready + motore prezzi + test
2. ✅ Idraulica: far squillare (Twilio Media Streams ↔ Gemini Live)
3. ✅ Function calling: `calcola_preventivo`
4. ✅ Blocco A: saluto iniziale automatico + `end_call` con chiusura pulita
5. ✅ Prompt robusto (gestione casi, anti-invenzione, readback) — iterativo
6. ✅ Blocco B: timeout di silenzio (sollecito + congedo automatico)
7. ✅ Blocco C: caller ID + SMS riepilogo a fine chiamata
8. ✅ Blocco D: listino arricchito (bevande reali, dolci, combo) per categoria
9. 🔄 Test conversazionali + tuning (VAD/barge-in #3, prompt sui casi reali)
10. ⬜ Riunione committente (~22/6) → tenant edilizia reale (logica parametrica)
11. ⬜ Produzione: GCP aziendale HQE (org policy via admin) + hardening + Secret Manager

## Stato attuale
**MVP avanzato — feature complete, in fase di test conversazionale.**
Chiamata E2E funzionante su **Cloud Run** (GCP personale `wizard-mvp-mc25`),
revisione `00008`: `https://wizard-telefonico-699544336212.us-central1.run.app`.
Numero: **+16892250454**.

Attivi: saluto automatico, `end_call` prudente, prompt robusto anti-invenzione,
timeout silenzio (watchdog), caller ID, SMS riepilogo, listino arricchito.
Env su Cloud Run: `GOOGLE_CLOUD_PROJECT/LOCATION` + `TWILIO_*` (SMS; in prod → Secret Manager).
**Diagnostica:** i log mostrano `UTENTE:`/`AGENTE:`/`TOOL CALL:` (trascrizioni) — usarli per il tuning.

## TODO (immediato)
- [ ] Sessione di test conversazionali → annotare i casi falliti → tradurli in regole nel prompt
- [ ] Tarare VAD/barge-in (#3) e soglie silenzio (`SILENCE_PROMPT_S`/`SILENCE_HANGUP_S`, via env) coi dati
- [ ] `git push` dei commit locali su GitHub
- [ ] Produzione (post-riunione): deploy su GCP aziendale HQE + Secret Manager per i segreti

## Come riprendere
- **Servizio live:** Cloud Run `wizard-telefonico` (`wizard-mvp-mc25`, us-central1). Chiamare +16892250454.
- **Re-deploy:** `gcloud run deploy wizard-telefonico --source . --region us-central1 --allow-unauthenticated --timeout 3600 --project wizard-mvp-mc25`
  (env mantenute; per modificarle `--update-env-vars NOME=valore` — da PowerShell la virgola spezza gli argomenti, usare lo shell sh o una variabile per volta).
- **Log con trascrizioni:** `gcloud run services logs read wizard-telefonico --region us-central1 --project wizard-mvp-mc25 --limit 150`
- **Webhook Twilio:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py <https://host>`
- **Test motore (venv ha pytest):** `.venv/Scripts/python.exe -m pytest -q` · In locale usare porta 8787 (la 8000 è occupata).
