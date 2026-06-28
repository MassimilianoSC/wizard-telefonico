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
(GCP **personale** `wizard-mvp-mc25`), region **`europe-west8` (Milano)** dal 21/6/2026:
`https://wizard-telefonico-699544336212.europe-west8.run.app` · Numeri **+390250074071 (IT, voce)** e **+16892250454 (USA, mittente SMS + rollback)**.
(Vecchio servizio `us-central1` — `https://wizard-telefonico-eydiobgqqq-uc.a.run.app` — spento dal traffico, resta come rollback.)

Ultima sessione: applicati e **validati dai log** i fix conversazionali —
watchdog che non interrompe più durante le elaborazioni, anti-stallo (niente più
"agente muto"), flusso ordine rigido (calcola subito dopo conferma). Gli ordini
normali (1-3 voci) filano; readback, totale, SMS e chiusura funzionano. SMS
**verificato** (arriva). Latenza US↔IT ~1-2s, accettabile.
Env su Cloud Run: `GOOGLE_CLOUD_PROJECT/LOCATION` + `TWILIO_*`.
**Diagnostica:** i log mostrano `UTENTE:`/`AGENTE:`/`TOOL CALL:`/`Silenzio`/`Stallo` — usarli per il tuning.

**Aggiornamento 21/6/2026 — spostamento in EU:** Cloud Run + Vertex/Gemini spostati in **`europe-west8`
(Milano)** (URL sopra; webhook Twilio ripuntato; env copiate dal servizio US senza esporre i segreti).
**Smoke test E2E passato**: chiamata → conversazione → calcolo → SMS (201) → chiusura, tutta da Milano,
nessun errore di region. Disponibilità native-audio in EU **verificata** (memoria `native-audio-eu-disponibile`,
script `probe_live_region.py`). I test conversazionali "seri" in EU restano per la prossima sessione
(problemi P1 noti, indipendenti dalla region: es. ~8s di stallo prima del readback a fine ordine).

**Aggiornamento 22/6/2026 (lun) — fix turn-taking** (diagnosi dai log → fix mirato → deploy):
- **VAD esplicito** (`realtime_input_config.automatic_activity_detection`: `END_SENSITIVITY_HIGH`,
  `silence_duration_ms`/`prefix_padding_ms` via env) + **`STALL_NUDGE_S` 9→6**: il turno utente ora si
  chiude da solo (niente più "Pronto?" per sbloccare). **Validato dai log.**
- **Fix `awaiting_agent`** (revision `00003-bzl`): il reset avviene sull'output reale dell'agente, non
  più su `turn_complete` → l'agente piantato *dopo la conferma* è risvegliato dal nudge a 6s invece di
  restare appeso. **Deployato, in attesa di validazione** col test.
- Sospetto ambientale: i test mattutini erano all'esterno (rumoroso) → il brusio può amplificare i
  problemi di turn-taking; ri-testare in ambiente silenzioso per isolare causa upstream (VAD) vs rete (watchdog).
- **Piano dei lavori rimanenti** (gruppi A–F, con test di esistenza): vedi `piano-operativo.md`.

**Aggiornamento 28/6/2026 (dom) — numero IT + strumentazione log** (revision `00005-dv2`):
- **Numero italiano attivo e integrato:** `+390250074071` (solo-Voce in ingresso). Il modello `Tenant`
  ora supporta **più numeri** (`phone_numbers: list[str]`, retrocompatibile); `resolve()` matcha sulla
  lista. `pizzeria-demo` ha due numeri di ingresso (USA + IT). **Ruoli separati:** IT = voce in ingresso,
  **USA (`TWILIO_PHONE_NUMBER`) = mittente SMS** (il numero IT non invia SMS). Vedi memoria `twilio-bundle-numero-italiano`.
- **Catena tutta-EU validata E2E** sul numero IT: routing esplicito → ordine → calcolo → SMS (da USA) → chiusura.
  **Latenza utente→agente ~0,36s mediana** (misurata), contro ~1-2s del numero USA.
- **Strumentazione log (`EV`)**: ogni evento è loggato NELL'ISTANTE reale (`utente: inizio parlato`,
  `agente: prima risposta (Ns dopo l'utente)`, `tool:`, `barge-in`, `--- fine turno ---`). Le righe
  `UTENTE:`/`AGENTE:` restano come riepilogo del CONTENUTO ma escono a `turn_complete`: per **ordine/timing
  usare le righe `EV`** (i log "vecchi" NON erano affidabili sull'ordine). Sblocca i test di timing del Gruppo B.
- **Sintomi conversazionali ancora aperti** (da fix in batch): doppio `end_call`→doppio SMS (intermittente);
  annuncio riepilogo/SMS "a vuoto" quando non c'è ordine. Vedi `piano-operativo.md` (Gruppi A/B).
- **Twilio Voice region del numero IT — tentativo IE1 (Irlanda) FALLITO, rollback a US1:** spostare lo
  smistamento chiamate del numero IT su **IE1** ha reso il numero **irraggiungibile da rete italiana**
  ("numero non corretto"). **Rollback a US1 → funziona.** Causa **non determinata con certezza**. La
  region IT **resta su US1**. La latenza ~0,36s è già ottima così (criterio: 0,36s va benissimo, anche
  più alta). In futuro si potrà **riprovare IE1** verificando con cura la **config per-region** prima di
  attivare (vedi nota §9).

## 7. TODO (immediato)
> Piano completo e ordinato **per gruppi** (con test di esistenza per ogni voce): **`piano-operativo.md`**.
- [ ] **Validare il fix `awaiting_agent`** (rev `00003-bzl`) con un test in ambiente *silenzioso*: ordina → conferma → l'agente riparte da solo entro ~6s? (nei log cercare `Stallo agente … nudge`)
- [ ] **Gruppo A — `prompt.md`** (un file, un deploy): totale anticipato, "annuncio SMS a vuoto", coerenza quantità, "chiedi-non-indovinare", readback non saltabile
- [ ] **Gruppo C — `voci` malformate** a `calcola_preventivo` (bug offline, test deterministico)
- [ ] **Gruppo B — turn-taking/audio**: prima la *strumentazione* (misura), poi tarature `VAD_SILENCE_MS`/`SILENCE_PROMPT_S`, troncamento saluto, doppio `end_call`
- [ ] **Gruppo D — hardening**: Secret Manager, firma webhook, rate limit, cold start, tetto durata, riconnessione WS, recupero lead, osservabilità
- [ ] **Gruppo E — valore committente**: notifica lead, cruscotto/storico, CRM GoHighLevel, link preventivo, WhatsApp
- [ ] **Gruppo F — tenant edilizia** (dopo la spina dorsale conversazionale): motore parametrico + fuzzy-match listino
- [ ] Produzione: GCP aziendale HQE (org policy via admin) — vedi §8 e memoria `vincoli-rete-aziendale-gcp`

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
- **Latenza:** *(superato 21/6)* il native-audio (GA) **è servito anche da `europe-west8`** e il
  servizio è stato spostato lì. Il fondo residuo dipende ora dal **numero USA** (edge Twilio US):
  si ridurrà col numero italiano (Regulatory Bundle in corso, memoria `twilio-bundle-numero-italiano`).

## 9. Note operative (cose da sapere / trappole già incontrate)
- **Twilio trial:** max **5 SMS/giorno** (oltre → HTTP 429, error 63038) e messaggio
  "press any key" a ogni chiamata. Un piccolo **upgrade** li rimuove entrambi.
- **Twilio Voice region del numero IT = US1 (non IE1):** spostare la region di smistamento del numero
  IT su **IE1 (Irlanda)** lo ha reso **irraggiungibile da rete italiana** ("numero non corretto");
  **rollback a US1** ha ripristinato. Causa non certa (probabile config per-region da rivedere).
  Tenere **US1**. Riprovare IE1 solo verificando bene la configurazione per-region prima di attivare.
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
- **Servizio live:** Cloud Run `wizard-telefonico` (`wizard-mvp-mc25`, **`europe-west8`** dal 21/6). Chiamare +16892250454.
- **Re-deploy:** `gcloud run deploy wizard-telefonico --source . --region europe-west8 --allow-unauthenticated --timeout 3600 --project wizard-mvp-mc25` (env mantenute).
- **Log con trascrizioni:** `gcloud run services logs read wizard-telefonico --region europe-west8 --project wizard-mvp-mc25 --limit 150`
- **Rollback su us-central1:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py https://wizard-telefonico-eydiobgqqq-uc.a.run.app`
- **Webhook Twilio (se cambia l'host):** `PYTHONPATH=. .venv/Scripts/python.exe scripts/set_twilio_webhook.py <https://host>`
- **Smoke test Gemini:** `PYTHONPATH=. .venv/Scripts/python.exe scripts/smoke_live.py`
- **Test motore:** `.venv/Scripts/python.exe -m pytest -q`

## 11. Indice memorie (decisioni e contesto, caricate a ogni sessione)
principio-riuso-ip · stack-python-deciso · mvp-pizzeria-pre-riunione ·
multitenancy-tenant-ready · documentazione-stato-progetto · workflow-quando-serve ·
deploy-a-fine-batch · ref-demo-gemini-live-telephony · vincoli-rete-aziendale-gcp ·
guardrail-produzione · diagnosi-da-log-prima-di-modificare · doc-ufficiale-gemini-live ·
native-audio-eu-disponibile · twilio-bundle-numero-italiano
