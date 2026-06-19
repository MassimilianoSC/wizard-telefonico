# Wizard vocale telefonico — Guida per Claude

> File caricato a ogni sessione: è il punto di partenza per riprendere il lavoro.
> Tieni aggiornate **Stato attuale** e **TODO** a ogni avanzamento significativo.
> Le **decisioni e il loro "perché"** stanno nelle *memorie* (caricate in automatico;
> indice in fondo). Il **piano strategico** è in [piano-wizard-vocale.md](piano-wizard-vocale.md).

## 1. Scopo (il task)
Agente vocale che il cliente finale **chiama al telefono**: una voce (LLM) lo guida
nella scelta del prodotto, raccoglie i parametri di prezzo, calcola un **preventivo
esatto con codice deterministico (mai l'LLM)** e glielo recapita via messaggio.
Prodotto da portare sul mercato, venduto a più committenti (multi-tenant).

**Caso d'uso reale:** impresa edile. **Ora** è un MVP di test personale (dominio
"giocattolo" = pizzeria finta) per validare la sostenibilità; **dopo la riunione col
committente (~lun 22/6/2026)** diventa progetto aziendale (HQE) verso la produzione.

## 2. Principi fermi
- **Separazione dei ruoli:** l'LLM conversa e raccoglie; il **codice calcola** il
  prezzo (motore deterministico via function calling). Mai prezzi dall'LLM/RAG.
- **Modulare e additivo:** da MVP a produzione si *indurisce*, non si riscrive.
- **Dominio-agnostico / tenant-ready:** listino = dati; motore prezzi dietro
  interfaccia; il tenant si risolve dal numero chiamato (Twilio `To`).
- **Meno lavoro = max riuso dell'idraulica, IP propria.** Deploy a fine batch.

## 3. Stack
Python 3.13 + FastAPI · google-genai + Gemini Live API native-audio (Vertex AI) ·
Twilio (telefonia Media Streams + SMS) · audioop-lts (audio) · deploy su Cloud Run.

## 4. Architettura (cartelle)
- `app/pricing/` — motore preventivi deterministico (interfaccia `PriceEngine` + `pizzeria`)
- `app/tenancy/` — `Tenant` + registro (risolve dal numero, `build_engine`/`build_delivery`)
- `app/agent/runtime.py` — tool (`calcola_preventivo`, `end_call`), system instruction, trigger, SMS format
- `app/telephony/bridge.py` — ponte Twilio↔Gemini (audio, watchdog, anti-stallo, chiusura, trascrizioni)
- `app/delivery/` — consegna: `StubDelivery` / `SmsDelivery`
- `app/main.py` — FastAPI: `/twiml` (+ tenant_id, from_number), WebSocket `/ws`, `/health`
- `tenants/<id>/` — `tenant.json` + `catalog.json` (con categoria/alias) + `prompt.md`
- `Dockerfile` · `scripts/` (smoke_live, set_twilio_webhook) · `tests/`

## 5. Cosa abbiamo fatto (roadmap; il "perché" → memorie)
1. ✅ Scaffold tenant-ready + motore prezzi + test
2. ✅ Idraulica: far squillare (Twilio Media Streams ↔ Gemini Live)
3. ✅ Function calling: `calcola_preventivo` verso il motore
4. ✅ Blocco A: saluto iniziale automatico + `end_call` con chiusura pulita (mark)
5. ✅ Prompt robusto (gestione casi, anti-invenzione, readback, flusso ordine rigido)
6. ✅ Blocco B: timeout di silenzio (sollecito + congedo automatico)
7. ✅ Blocco C: caller ID + SMS riepilogo a fine chiamata
8. ✅ Blocco D: listino arricchito (bevande reali, dolci, combo) per categoria
9. ✅ Fix conversazionali: watchdog non invasivo + anti-stallo + flusso rigido
10. 🔄 Test conversazionali iterativi (annota i casi → regole nel prompt)
11. ⬜ Riunione committente (~22/6) → tenant edilizia reale (logica parametrica)
12. ⬜ Produzione: GCP aziendale HQE (org policy via admin) + hardening + Secret Manager + guardrail

## 6. Stato attuale (dove siamo)
**MVP avanzato, funzionante e in test.** Chiamata E2E completa su **Cloud Run**
(GCP **personale** `wizard-mvp-mc25`), **revisione `00009`**:
`https://wizard-telefonico-699544336212.us-central1.run.app` · Numero **+16892250454**.

Ultima sessione: applicati e **validati dai log** i fix conversazionali —
watchdog che non interrompe più durante le elaborazioni, anti-stallo (niente più
"agente muto"), flusso ordine rigido (calcola subito dopo conferma). Gli ordini
normali (1-3 voci) filano; readback, totale, SMS e chiusura funzionano. SMS
**verificato** (arriva). Latenza US↔IT ~1-2s, accettabile.
Env su Cloud Run: `GOOGLE_CLOUD_PROJECT/LOCATION` + `TWILIO_*`.
**Diagnostica:** i log mostrano `UTENTE:`/`AGENTE:`/`TOOL CALL:`/`Silenzio`/`Stallo` — usarli per il tuning.

## 7. TODO (immediato)
- [ ] Continuare i test conversazionali → annotare i casi falliti → regole nel prompt
- [ ] Tarare, coi dati, soglie silenzio/stallo (`SILENCE_PROMPT_S`/`SILENCE_HANGUP_S`/`STALL_NUDGE_S`, via env) ed eventuale VAD
- [ ] `git push` dei commit locali su GitHub (parecchi in coda)
- [ ] Preparare il tenant **edilizia** dopo la riunione (listino reale + logica parametrica/forbice)
- [ ] Produzione: deploy su GCP aziendale HQE + Secret Manager + guardrail (vedi §8)

## 8. Possibili miglioramenti / backlog (già discussi)
- **Guardrail di produzione** (memoria `guardrail-produzione`): totale detto = calcolato;
  readback non saltabile; per l'edilizia **stima/forbice non vincolante** (§4.4 piano).
- **Coerenza quantità su ordini complessi/caotici:** caso limite osservato (ordini
  assurdi con tante voci → l'agente perde il conto). Migliorabile via prompt; non urgente.
- **Consegna evoluta:** link a una pagina preventivo invece del solo SMS testuale (§4.1 piano);
  e **WhatsApp** oltre l'SMS (§4.5: verifica account Meta 1-6 settimane → avviare per tempo).
- **Disambiguazione/fuzzy-match del listino** (vocabolario chiuso + sinonimi) in vista
  della terminologia edile regionale (§4.3 piano).
- **Tuning VAD avanzato** (`RealtimeInputConfig.automatic_activity_detection`: sensitivity,
  silence_duration) se il barge-in/timing va affinato.
- **Latenza:** Gemini Live native-audio è solo in `us-central1`; per l'Italia resta un
  fondo fisiologico. Valutare opzioni region/modello in futuro.

## 9. Note operative (cose da sapere / trappole già incontrate)
- **Twilio trial:** max **5 SMS/giorno** (oltre → HTTP 429, error 63038) e messaggio
  "press any key" a ogni chiamata. Un piccolo **upgrade** li rimuove entrambi.
- **Produzione bloccata dall'org aziendale:** org policy `iam.allowedPolicyMemberDomains`
  vieta `allUsers` → Cloud Run pubblico solo con eccezione dell'admin (memoria `vincoli-rete-aziendale-gcp`).
  Per questo l'MVP gira sul **GCP personale**. Billing = carta personale (temporaneo).
- **Env multiple con gcloud da PowerShell:** la virgola spezza gli argomenti →
  GOOGLE_CLOUD_PROJECT prese un valore sbagliato. Usare lo shell `sh`/Git Bash o `--update-env-vars` una variabile per volta.
- **Porte locali:** la **8000 è occupata** da un altro programma dell'utente (su IPv6) →
  in locale usare la **8787**.
- **Accenti nei log:** i `?`/`�` sono solo resa della console; i file sono UTF-8 corretti.
- **Segreti:** ora `TWILIO_*` sono env su Cloud Run; in produzione → **Secret Manager**.

## 10. Come riprendere (comandi)
- **Servizio live:** Cloud Run `wizard-telefonico` (`wizard-mvp-mc25`, us-central1). Chiamare +16892250454.
- **Re-deploy:** `gcloud run deploy wizard-telefonico --source . --region us-central1 --allow-unauthenticated --timeout 3600 --project wizard-mvp-mc25` (env mantenute).
- **Log con trascrizioni:** `gcloud run services logs read wizard-telefonico --region us-central1 --project wizard-mvp-mc25 --limit 150`
- **Webhook Twilio (se cambia l'host):** `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py <https://host>`
- **Smoke test Gemini:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/smoke_live.py`
- **Test motore:** `.venv/Scripts/python.exe -m pytest -q`

## 11. Indice memorie (decisioni e contesto, caricate a ogni sessione)
principio-riuso-ip · stack-python-deciso · mvp-pizzeria-pre-riunione ·
multitenancy-tenant-ready · documentazione-stato-progetto · workflow-quando-serve ·
deploy-a-fine-batch · ref-demo-gemini-live-telephony · vincoli-rete-aziendale-gcp ·
guardrail-produzione
