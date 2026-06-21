# Roadmap — da MVP a prodotto in produzione

> Wizard vocale telefonico per impresa edile (EdilMillennium).
> Documento complementare al "Piano d'azione" iniziale.
> _Redatto sabato, giugno 2026. Le voci sono ordinate per **priorità reale**,
> non per urgenza percepita: la localizzazione geografica e il numero italiano,
> che istintivamente sembrano prioritari, sono in realtà raffinature tardive._

---

## Stato attuale (punto di partenza)

Cosa è già in piedi e funziona:
- **MVP completo nelle sue parti**: chiamata → agente vocale → conversazione →
  raccolta → SMS con preventivo. Validato l'happy path (ordine pizze + preventivo).
- **Backend su Cloud Run** (non più ngrok+locale → eliminato il salto di rete
  più costoso; la latenza residua dipende ora dalla *region*).
- **Numero Twilio USA** in trial.
- **SMS del preventivo funzionante anche in trial**, con limite di **5 messaggi/giorno**.
- **Google Cloud** con Vertex abilitato, modello Gemini Live native-audio.

Problemi noti già osservati (→ vanno in Priorità 1):
- Parole dell'agente **troncate** (pipeline audio in uscita / barge-in).
- `end_call` che scatta **troppo facilmente**.
- Tenuta della conversazione incerta su input inattesi.

---

## Avanzamento diagnostico — aggiornato dom 21/6/2026

> Stato del lavoro sulla Priorità 1, in coerenza col metodo "prima i dati, poi il codice".

**Fatto (solo diagnosi, nessuna modifica al codice):**
- Analizzate dai log Cloud Run le ultime chiamate reali → i problemi di P1 sono confermati
  e precisati (lista aggiornata sotto).
- Affondo sulle "parole troncate": letto `app/telephony/bridge.py`. **Meccanismo individuato** —
  sull'evento `interrupted` di Gemini il bridge invia `clear` a Twilio → l'audio dell'agente
  viene tagliato *davvero* (non è solo la trascrizione). **Causa a monte:** la VAD non è
  configurata (`_live_config` non imposta `automatic_activity_detection`) → barge-in spurio
  su audio sporco. Residuo: il bridge **non logga** `interrupted`, quindi manca la prova diretta.

**Lista problemi noti — precisata (aggiorna i tre punti qui sopra):**
- **Parole troncate** = barge-in spurio (VAD di default troppo sensibile) → `clear`.
- **`end_call` troppo facile** (incluso un doppio `end_call` in chiusura).
- **Totale anticipato prima della conferma** del cliente (vive nel prompt).
- **Agente muto dopo la conferma** su ordini complessi (vive nel prompt).
- **`voci` malformate** passate a `calcola_preventivo` (lista di stringhe → nessun totale).
- Tenuta su input inattesi / "indovina" su ASR sporco.
- **Annuncio SMS "a vuoto":** l'agente promette «riceverà il riepilogo via messaggio»
  anche quando il cliente **non ordina nulla / cambia idea** → ma l'SMS non parte (manca
  `last_quote` in `bridge.py`), quindi promessa non mantenuta. Vive nel prompt: la procedura
  di chiusura (`prompt.md`) annuncia il riepilogo in modo **incondizionato**, e presuppone
  sempre un ordine. Fix = congedo senza promessa di SMS nel caso "nessun ordine".

**Prossimo passo diagnostico (lettura, non modifica):** leggere `app/agent/runtime.py`
(prompt "conferma→calcolo" + `dispatch_tool_call`) per chiudere la mappa.

**Test di validazione → RIMANDATI a lun 22/6.** Oggi nessun test. I fix andranno raccolti
in **un solo batch** + un giro di test, non a spizzichi.

---

## Principio di ordinamento

Un agente che tronca le frasi o chiude le chiamate a caso è **inutilizzabile**,
per quanto sia ben localizzato e conforme. Quindi:

> **L'esperienza conversazionale viene prima dell'ottimizzazione geografica.**
> **Il valore per il committente viene prima della raffinatura tecnica.**
> **La normativa è trasversale: si decide presto perché condiziona tutto il resto.**

---

## PRIORITÀ 0 — Prerequisito bloccante

### Upgrade dell'account Twilio
Non è "tecnica", ma sblocca metà della lista. Il trial limita: 5 SMS/giorno,
messaggio "trial" prima della voce, tetto di 10 min/chiamata, niente WhatsApp,
solo numeri verificati possono chiamare (→ il committente non può provare
liberamente in demo).
- Richiede: profilo cliente + dati fiscali + documento + carta. ~5–10 min ma
  con i documenti pronti.
- **Da avviare con anticipo** (come il Regulatory Bundle e WhatsApp): è un
  *lead time*, non un lavoro istantaneo.

---

## PRIORITÀ 1 — Robustezza conversazionale (senza questo non c'è prodotto)

Sono i problemi già visti. In ordine di intervento:

1. **Stringere le condizioni di `end_call`** — chiudere solo su segnale esplicito
   (saluto utente / preventivo inviato), eventualmente con conferma. Dare *meno*
   libertà sulla chiusura fa sembrare l'agente *più* intelligente.
2. **Rivedere il prompt di sistema** — come gestire l'inaspettato, chiedere
   chiarimenti invece di bloccarsi, non trattare ogni pausa come fine chiamata.
3. **Diagnosticare le parole troncate** — quasi certamente pipeline audio in
   uscita (buffering Gemini→backend→Twilio) o **barge-in troppo aggressivo**
   (rumore/eco scambiato per voce utente → l'agente si zittisce a metà parola).
4. **Tarare la rilevazione di fine-turno** — il timing con cui l'agente decide
   che l'utente ha finito.
5. **Gestione "chiedi-non-indovinare"** — di fronte ad audio degradato (segnale
   scarso) o input ambiguo, ripetere/confermare invece di ragionare su una
   trascrizione sbagliata. È anche la difesa contro la cattiva rete lato cliente.

> Nota: questi problemi NON si risolvono cambiando modello. Vivono
> nell'orchestrazione, non nel "cervello".

---

## PRIORITÀ 2 — Valore per il committente (il vero motivo per cui paga)

Al committente non interessa la voce dell'AI: gli interessa **ricevere lead
qualificati e non perderne**. Questo è probabilmente il cuore del prodotto.

- **Notifica in tempo reale**: appuntamento fissato / lead qualificato →
  avviso immediato al committente (email / WhatsApp / SMS), così non gli sfugge.
- **Storico / cruscotto**: tutte le chiamate con esito, dati raccolti,
  trascrizione, consultabili.
- **Integrazione CRM (leva strategica)**: il loro sito gira su
  **GoHighLevel / LeadConnector** (già un CRM). Scrivere i lead *lì dentro*,
  nello stesso posto dei form del sito, evita che gestisca due flussi separati.
  È una delle cose che **alza di più il prezzo** del prodotto.

Implica ridefinire il "successo" di una chiamata: non più "preventivo inviato"
ma **"lead qualificato + sopralluogo fissato (o richiamata programmata)"**.

---

## PRIORITÀ 3 — Normativa (trasversale, da decidere PRESTO)

Non è il "punto 4": è un vincolo che condiziona *come* costruisci Priorità 2 e 5,
quindi va deciso prima di costruirle, non dopo.

### AI Act — trasparenza (tocca subito il design)
- L'agente DEVE dichiarare di essere un'AI in apertura. È una riga del prompt
  iniziale, da mettere fin da ora, non un adempimento astratto.

### GDPR
- Informativa pronunciata dall'agente; base giuridica / consenso.
- Decisione su **cosa** si conserva e **per quanto** (voce? trascrizione? dati?).
- **Opt-in registrato** (fonte, timestamp, scopo) — la trascrizione è già la prova.
- Accordo di trattamento col committente: **tu sei Responsabile del trattamento**,
  lui è Titolare.

> **Confine di responsabilità:** non sei il consulente legale del committente.
> Lui deve avere il suo riferimento legale; tu non ti assumi la sua compliance.
> Il tuo compito è **costruire lo strumento perché la compliance sia possibile**
> (informativa, consenso, gestione dati corretta). È anche argomento di vendita:
> il loro sito ha la privacy policy che punta ancora a `example.com`.

---

## PRIORITÀ 4 — Numero italiano + localizzazione

### Numero italiano (3 strade — vedi anche Piano d'azione)
- **Deviazione di chiamata** (consigliata per partire): il committente tiene il
  suo numero e devia verso il Twilio. Rapida, reversibile, nessun porting,
  **aggira il Regulatory Bundle**.
- **Porting** verso Twilio: definitivo ma con tempi/pratiche; il numero lascia
  l'operatore attuale (problema se lo usano anche per altro).
- **Numero nuovo dedicato** all'agente (italiano su Twilio → richiede Regulatory
  Bundle: documenti + indirizzo + approvazione, lead time da mettere in conto).
- → Domanda al committente: "il numero sul sito lo usate solo per i preventivi
  o anche per altro? Tutte le chiamate all'agente o solo alcune?"

### Localizzazione tecnica
- **Cloud Run** → region europea: `europe-west8` (Milano) o `europe-west1` (Belgio).
- **Modello Gemini** → **VERIFICATO (21/6/2026):** `gemini-live-2.5-flash-native-audio`
  (GA, rilascio 12/12/2025) **è servito da `europe-west8` (Milano)** — confermato sul campo
  con handshake `live.connect` (`probe_live_region.py`), `us-central1` come controllo. Quindi
  region EU = **guadagno di latenza reale** (l'audio non gira per gli USA) + **data residency
  UE** per l'audio (rilevante per il GDPR, P3). Nota: la *preview*
  (`...-preview-native-audio-09-2025`) era solo us-central1 e va in deprecazione → non confonderla con la GA.
- Promemoria: il guadagno di latenza grosso (ngrok) è **già stato realizzato**
  passando a Cloud Run. Questo è rifinitura.

> La latenza non cambia la *qualità del ragionamento* (il modello è lo stesso
> ovunque), ma migliora *fluidità e timing* dei turni — che in una telefonata
> contano per la qualità percepita.

---

## PRIORITÀ 5 — Sicurezza (cantiere che cresce col resto)

Quattro fronti distinti, non "una cosa":
1. **Segreti**: chiavi Twilio/Google fuori dal codice, in **Secret Manager**
   (Google Cloud), non in `.env` committati o in chiaro.
2. **Autenticazione webhook**: validare la **firma di Twilio** sulle richieste in
   ingresso al backend — verificare che vengano davvero da Twilio, non da un
   impostore.
3. **Anti-abuso**: rate limiting contro chi chiama in massa per bruciare credito
   o intasare il servizio.
4. **Sicurezza dati**: cifratura, controllo accessi, retention (si lega al GDPR).

---

## PRIORITÀ 6 — Affidabilità e recupero errori

In demo riattacchi tu ordinatamente; in produzione no.
- **Reattività alla prima chiamata (cold start) — DA VERIFICARE** → sospetto che, dopo un
  periodo di inattività, la **prima** chiamata risponda con diversi secondi di ritardo.
  Ipotesi da controllare prima di intervenire: (a) **Cloud Run** che scala a zero → avvio a
  freddo del container (i log mostrano `Shutting down` / `Started server process`); rimedio
  tipico = `--min-instances 1`. (b) **Warmup della sessione Gemini Live**. Verificare quale
  delle due (o entrambe). Impatta la prima impressione (P1), oltre all'affidabilità.
- **Caduta chiamata a metà** → recupero del lead via **caller ID** (richiamo
  automatico o salvataggio del lead parziale: "interrotta, numero X, chiedeva
  del tetto"). Trasforma un problema di rete in lead recuperabile.
- **Gemini non risponde in tempo** → comportamento dignitoso ("mi perdoni, può
  ripetere?") invece di silenzio morto; riconnessione del WebSocket.
- **Backend giù** → osservabilità, logging, alert.
- **Chiusura conversazione**: timeout di silenzio + chiusura intenzionale +
  tetto di durata massima (in produzione più corto dei 10 min del trial).

---

## TRASVERSALI CONTINUI (non si "chiudono", accompagnano tutto)

### Costi e modello di pricing verso il committente
- Sapere quanto costa una **chiamata completa** (Gemini + Twilio + messaggi)
  per costruirci sopra un prezzo con margine.
- Ordine di grandezza attuale: Gemini ~15–25 cent/chiamata da 10 min;
  + Twilio (centesimi/min) + messaggio. Stima generosa tutto incluso:
  ~30–50 cent/chiamata completata.
- Modello di ricavo: **canone/licenza + manutenzione + margine sul consumo**
  (i minuti li paghi tu e li ribalti).
- Rifare il conto sul modello effettivo scelto per la produzione (i preview
  possono cambiare prezzo).

### Manutenzione del funnel/listino nel tempo
- Chi aggiorna domande, servizi, prezzi-ancora quando cambiano?
- Se solo tu (nel codice) → dipendenza → **leva commerciale**: manutenzione a
  contratto.
- Se vuoi che lo tocchi il committente → serve un minimo di pannello.

### Documentazione ufficiale Gemini Live (consultarla SEMPRE)
Quando si affrontano i problemi che emergono dai test, **consultare prima la documentazione
ufficiale di Google su Gemini Live API**: contiene best practice e indicazioni di
troubleshooting (VAD/activity detection, gestione interruzioni, audio, sessione, timing dei
turni). Il progetto usa **Vertex AI**, quindi verificare la versione pertinente (Vertex) oltre
a quella Gemini API. Regola: non reinventare una soluzione prima di aver letto cosa raccomanda
il fornitore.

---

## Decisioni da prendere CON il committente (in riunione)

1. **Scopo dell'agente**: appuntamento per sopralluogo, oppure prezzo al telefono?
   E se prezzo → indicativo o definitivo? (Quasi certo: qualificazione +
   appuntamento; il preventivo vero è post-sopralluogo, come dice il loro sito.)
2. **Questione prezzo**: rischio della "forbice" (contraddice la loro promessa
   "nessuna sorpresa"). Proposta: **ancorare alle offerte già pubbliche**
   (es. tetto da 4.500€) + rimando al sopralluogo. Decisione commerciale **sua**.
3. **Quali servizi**: partire SOLO dal tetto (standardizzato, prezzo-civetta
   pubblico) o tutti e 6? → consigliato partire dal tetto, allargare dopo.
4. **Il numero**: solo preventivi o anche altro? Tutte le chiamate o solo alcune?
   → determina deviazione vs porting vs numero dedicato.
5. **CRM**: i lead devono finire nel loro GoHighLevel/LeadConnector?
6. **Funnel di qualificazione**: per ogni servizio, "quali 3-4 cose chiedi sempre
   nella prima chiamata per capire se vale un sopralluogo?" → estrai il FUNNEL,
   non il LISTINO.

---

## Ordine consigliato di esecuzione (sintesi)

1. **Robustezza conversazionale** (P1) — senza, non hai un prodotto.
2. **Cruscotto + notifiche al committente** (P2) — è il valore per lui.
   In **parallelo**: impianto **GDPR/AI Act** (P3), perché condiziona come
   costruisci P2 e P5.
3. **Upgrade Twilio + numero italiano** (P0 + P4).
4. **Region / latenza** (P4) — ottimizzazione.
5. **Sicurezza** (P5) — cresce insieme al resto.
6. **Affidabilità / recupero errori** (P6) — prima del go-live reale.
- **Trasversali** (costi/pricing, manutenzione funnel): sempre presenti.

> La localizzazione geografica — istintivamente il "punto 2" — è in realtà tra
> le ultime: è raffinatura, non sostanza. La sostanza è far reggere la
> conversazione e dare valore al committente.
