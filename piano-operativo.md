# Piano operativo — lavori rimanenti (wizard vocale)

> Complemento a [CLAUDE.md](CLAUDE.md) (stato) e alle memorie (decisioni). Qui sta il
> **cosa rimane da implementare** e **come provarlo**. Solo lavoro tecnico
> (escluse normativa GDPR e decisioni da prendere col committente).

## Due principi guida
1. **Raggruppa per contesto di lavoro, non per tema.** Ogni salto tra file/sottosistemi
   costa un ricarico mentale: si lavora a blocchi che vivono nello stesso file e si
   testano allo stesso modo.
2. **Test di esistenza PRIMA del fix.** Per ogni problema serve uno scenario che produce
   il sintomo *on-demand, misurato (numero o trascrizione), ripetibile*. È il baseline
   che dimostra il bug; lo stesso test, dopo, è il criterio di successo.
   - **[DET]** test deterministico (codice/offline): risultato binario, ripetibile al 100%.
   - **[PROB]** test probabilistico (LLM/prompt): l'esito varia tra run → criterio di
     successo = "il sintomo non ricompare su N tentativi", **non** "passa una volta".
     Non confondere i due: dichiarare risolto un bug di prompt dopo un solo run fortunato
     è l'errore più facile di questa lista.

## Ordine consigliato
**Valida fix di oggi → A → C → B → D → E → F**
(economico/basso-rischio prima; misura-prima-dell'azione al centro; infra poi; costruzione infine.)

---

## Gruppo 0 — Validazione fix di oggi (prima di tutto)
- [ ] **Fix `awaiting_agent`** (rev `00003-bzl`). **Test [PROB]:** in ambiente *silenzioso*,
  ordina → conferma → cronometra la ripartenza dell'agente. *Successo:* riparte entro ~6s
  senza tuo sollecito; nei log compare `Stallo agente … nudge` (watchdog) oppure riparte ancora
  più liscio (VAD). Baseline pre-fix: 8-15s di stallo + serviva intervento vocale.

## Gruppo A — `tenants/<id>/prompt.md` — un file, **un** deploy, test via trascrizione [tutti PROB]
- [ ] **Totale anticipato prima della conferma.** Test: ordina e NON confermare (di' qualcosa di
  ambiguo). *Successo:* l'agente non dà il totale finché non confermi.
- [ ] **"Annuncio SMS a vuoto".** Test: chiama e chiudi senza ordinare ("ho sbagliato numero").
  *Successo:* l'agente NON promette il riepilogo via messaggio.
- [ ] **Coerenza quantità su ordini caotici.** Test: ordine confuso ("due, anzi tre, no due e una
  marinara"). *Successo:* il readback combacia con l'ordine reale.
- [ ] **"Chiedi-non-indovinare" su ASR sporco.** Test: frase volutamente ambigua/sporca.
  *Successo:* chiede di ripetere invece di inventare.
- [ ] **Readback non saltabile.** *Successo:* il readback precede SEMPRE il totale.
- **Mossa efficiente:** UNA chiamata "cattiva" (ordine caotico + niente conferma + niente ordine
  finale) può dimostrare 3-4 di questi in un'unica trascrizione.
- **Nota deploy:** `prompt.md` è letto dal container → le modifiche richiedono **un re-deploy**
  per essere testate in produzione (non "zero deploy", ma uno solo per tutto il blocco).

## Gruppo C — `app/agent/runtime.py` — bug di contratto dati, offline [DET]
- [ ] **`voci` malformate a `calcola_preventivo`.** Test: invoca
  `dispatch_tool_call("calcola_preventivo", {"voci": ["margherita","birra"]}, engine)`
  (lista di *stringhe* invece di `{code, quantity}`). *Successo:* ritorna l'errore parlante,
  NON solleva eccezione non gestita. Aggiungere come test in `tests/` (deterministico, offline).

## Gruppo B — `app/telephony/bridge.py` + `app/config.py` — turn-taking/audio [misti]
> Dipendenza d'ordine: la **strumentazione va per prima** — senza misurare non sai se la taratura funziona.
- [ ] **Strumentazione [abilitante].** Loggare il timestamp del primo audio del turno utente e/o gli
  eventi VAD (`activity_start/end`) + l'evento `interrupted`. *Prova che serve:* oggi non sai
  rispondere a "quanti ms tra l'ultimo audio utente e il primo token dell'agente?".
- [ ] **Taratura `VAD_SILENCE_MS`** (500 → 350-400, via env). Test [PROB]: 5 chiamate, frase breve di
  chiusura, misura l'intervallo dai log. *Successo:* mediana < ~2s senza spezzare le frasi con pause.
- [ ] **Taratura `SILENCE_PROMPT_S`** (16s è lungo). Test [PROB]: taci dopo una domanda dell'agente.
  *Successo:* "è ancora in linea?" arriva prima, senza interrompere chi sta solo pensando.
- [ ] **Troncamento del saluto (barge-in spurio).** Test [PROB]: resta in silenzio durante il saluto;
  se si tronca *lo stesso* → barge-in spurio. *Successo:* saluto integro su linea pulita.
- [ ] **Doppio `end_call`** (minore). *Successo:* un solo `end_call` in chiusura.
- [ ] *(piano B)* VAD locale (Silero) con `disabled:True`, **solo se** le tarature non bastano.

## Gruppo D — Hardening / SRE — deploy + config Cloud Run [misti]
- [ ] **Segreti `TWILIO_*` in Secret Manager** (ora env in chiaro).
- [ ] **Validazione firma webhook Twilio.** Test [DET]: POST a `/twiml` senza firma (curl);
  *Successo:* il backend la rifiuta.
- [ ] **Rate limiting anti-abuso.**
- [ ] **Cold start / prima chiamata.** Test [DET-ish]: servizio freddo → 1ª chiamata vs 2ª a caldo;
  *Successo:* nessuna penalità sensibile sulla prima. Rimedio: `--min-instances 1` o warmup.
- [ ] **Tetto durata massima chiamata** (prod < 10 min del trial).
- [ ] **Riconnessione WebSocket** se Gemini cade *(vive in `bridge.py`, stesso file del Gruppo B)*.
- [ ] **Recupero lead su caduta chiamata** (caller ID → lead parziale).
- [ ] **Osservabilità**: logging strutturato + alert.

## Gruppo E — Valore committente — costruzione di prodotto
- [ ] Notifica lead in tempo reale al committente (riusa `delivery`).
- [ ] Storico / cruscotto chiamate (esito, dati, trascrizione).
- [ ] Integrazione CRM GoHighLevel/LeadConnector.
- [ ] Consegna evoluta: link a pagina preventivo (oltre l'SMS).
- [ ] Canale WhatsApp oltre l'SMS.

## Gruppo F — Tenant edilizia — ultimo: dopo la spina dorsale conversazionale
- [ ] Motore prezzi **parametrico edile** (stima/forbice) dietro l'interfaccia `PriceEngine`.
- [ ] Disambiguazione / fuzzy-match listino (vocabolario chiuso + sinonimi).

## Guardrail di produzione (trasversali — memoria `guardrail-produzione`)
- [ ] Totale detto = totale calcolato (verifica su trascrizione).
- [ ] Readback non saltabile → confluisce nel Gruppo A.
