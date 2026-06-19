# Piano d'azione — Wizard vocale telefonico con preventivo

> Documento di riferimento per il progetto: un agente vocale che il cliente finale
> chiama al telefono, che lo accompagna nella scelta del prodotto e gli consegna
> un preventivo via messaggio. Caso concreto: impresa edile.
>
> \_Redatto a giugno 2026. I nomi/versioni dei modelli cambiano in fretta:
> verifica sempre i model ID correnti prima di partire.\_

\---

## 1\. Obiettivo del prodotto

Il cliente finale chiama un numero, parla con una voce (modello linguistico) che:

1. lo guida nella scelta del prodotto/servizio facendo le domande giuste;
2. raccoglie i parametri che determinano il prezzo;
3. produce un preventivo;
4. glielo recapita via messaggio (link), insieme a un riepilogo.

Non è un IVR a menu ("premi 1"): è una conversazione naturale a voce.

\---

## 2\. Principio guida (il più importante di tutti)

**La tecnologia è la parte facile. Il vero collo di bottiglia è formalizzare la
logica di prezzo del committente.** Tutto il resto è ingegneria risolvibile.
Se dalla riunione esci con regole di prezzo esplicite → progetto fattibile.
Se esci con "dipende, lo vedo caso per caso" → hai scoperto il rischio prima di
esserti impegnato.

\---

## 3\. Architettura (i componenti e perché)

|Componente|Cosa fa|Scelta|
|-|-|-|
|**Telefonia**|Porta la chiamata dentro il sistema|Twilio (o SIP trunk) → WebRTC verso il modello|
|**Cervello conversazionale**|Parla col cliente, raccoglie i parametri (elicitazione), richiama i tool|Gemini Live API (native audio) su Google Cloud|
|**Motore di preventivazione**|Calcola il prezzo esatto dai parametri|Codice deterministico nel TUO backend (NON l'LLM, NON il RAG)|
|**Backend / orchestrazione**|Logica del wizard, prompt, motore prezzi, invio messaggio|Google Cloud Run|
|**Conoscenza prodotti (testo)**|Domande tecniche, descrizioni, FAQ|Testo nel prompt o RAG (solo per la parte NON numerica)|
|**Consegna**|Recapita il link al preventivo|WhatsApp (principale) + SMS (fallback)|

### Regola architetturale fondamentale: separazione dei ruoli

* **L'LLM conversa e raccoglie.** È bravissimo a capire e domandare.
* **Il codice calcola.** Il prezzo lo calcola un motore deterministico, mai il
modello. L'LLM lo richiama via **function calling**, riceve il numero, lo
comunica. Il numero non lo "pensa" mai il modello.

Perché: un preventivo dev'essere esatto, riproducibile, difendibile. Gli LLM
sbagliano i conti, arrotondano, inventano. Il RAG sui prezzi = disastro
(numero plausibile ma sbagliato, detto con sicurezza).

\---

## 4\. I punti delicati e come si risolvono

### 4.1 Cattura dell'email (il punto più fragile)

Lo speech-to-text confonde lettere/numeri simili, soprattutto su audio
telefonico a 8 kHz. **Soluzione: non catturare l'email a voce.**

* Si manda un messaggio (WhatsApp/SMS) al numero del chiamante con un **link**.
* Il cliente apre il link e **digita** la mail sulla tastiera → zero ambiguità.
* Bonus: hai una conferma esplicita e tracciabile del consenso.

Fallback se proprio serve a voce: readback con alfabeto fonetico
("m come Milano…"), normalizzazione ("chiocciola"→@), fuzzy-match del dominio
su whitelist (gmail.com, libero.it…), validazione deliverability prima dell'invio.

### 4.2 Il numero di telefono

Molto più facile dell'email: sono cifre, le rileggi per conferma.
Spesso ce l'hai già dal caller ID; chiedilo/confermalo comunque (a volte è
nascosto o il cliente vuole un altro numero).

### 4.3 Falsi positivi / input ambigui (il test che farà il committente)

Il rischio grave: l'agente mappa **in silenzio** un termine ambiguo sulla voce
sbagliata del listino e produce un prezzo. **Regola d'oro: nel dubbio, conferma
o chiedi — mai indovinare.**

* **Vocabolario chiuso:** l'agente confronta l'input con l'insieme *finito* delle
voci di listino. Match netto → procede. Ambiguo/sotto soglia → disambigua.
* **Readback prima del calcolo:** "quindi rifacimento bagno, 8 mq, finiture
medie — confermo?" Intercetta l'errore prima che diventi prezzo.
* **Via di fuga esplicita:** per casi fuori standard → "lo valuta un nostro
tecnico, la facciamo richiamare". Ammettere di non sapere > inventare.
* **L'architettura protegge:** se il prezzo lo calcola il motore deterministico,
un termine non riconosciuto NON può generare un prezzo — al massimo chiede.
* **Terminologia regionale/dialettale edile** (enorme in Italia): raccoglila e
inseriscila come sinonimi nel layer di matching.

### 4.4 Quanto è vincolante il preventivo

In edilizia il preventivo definitivo richiede spesso un sopralluogo. Valuta col
committente se il wizard debba produrre una **stima preliminare / forbice di
prezzo** ("indicativamente tra X e Y, definitivo dopo sopralluogo") invece di una
cifra secca. Più onesto e molto più robusto da implementare.

### 4.5 Regole WhatsApp (diverse dall'SMS!)

WhatsApp non è SMS. Per messaggi business-initiated servono:

* **Template approvato** da Meta (categoria *Utility* per il preventivo:
approvazione più morbida, costo intermedio).
* **Opt-in documentato:** il "sì, mandamelo su WhatsApp" detto a voce può valere,
ma va registrato (fonte, timestamp, scopo, identificativo). La trascrizione
della chiamata è già la tua prova.
* **Account WhatsApp Business verificato** (via Twilio/Infobip): richiede Business
Verification + privacy policy URL. **Tempi di verifica: 1–6 settimane → avviare
per tempo.** Per questo: SMS come fallback per non restare bloccati al lancio.

\---

## 5\. La riunione col committente (vale più di tutta la tecnologia)

Domande, dalla più decisiva in giù:

1. **Esiste un listino? In che forma?** Excel strutturato / PDF / "a memoria"?
→ **Fatti dare 3-4 preventivi reali già fatti**: valgono più di mille
descrizioni astratte, mostrano i parametri veri.
2. **Quali parametri muovono il prezzo, e quanto pesa ciascuno?** Quantità (mq,
ml), materiale/finitura, stato di partenza (demolizione sì/no), accessibilità
cantiere… Distingui i parametri che cambiano il prezzo *di poco* da quelli che
lo cambiano *di molto*: contano i secondi.
3. **Quanti "prodotti" diversi vende, da quale partiamo?** → spingi per
**partire da UN solo tipo di lavoro** ben definito e standardizzabile.
Allargare dopo è facile; partire largo = non consegnare mai.
4. **Quanto deve essere vincolante il numero?** Cifra impegnativa o stima con
riserva di sopralluogo? (Quasi sempre: forbice/stima.)
5. **Cosa succede ai casi fuori standard?** Serve una via di fuga pulita
("la richiamiamo").
6. **Ogni quanto cambia il listino?** I prezzi materiali si muovono → chi
aggiorna i dati e come.
7. **Chi tiene aggiornata la base dati dopo la consegna?** → leva commerciale
tua: la manutenzione del listino può essere parte del contratto.

Filo conduttore: **trasformare il suo "lo so per esperienza" in regole esplicite.**

\---

## 6\. Stack concreto dell'MVP

* **Modello:** Gemini Live API native audio. A giugno 2026 il punto di partenza
per nuovi progetti è `gemini-3.1-flash-live-preview` (migliore su precisione
numerica e function calling da voce — i due punti critici del progetto; 90+
lingue). **Ma è Preview** (no SLA, può cambiare). Alternativa GA stabile:
`gemini-2.5-flash-native-audio`. Per un test di fattibilità → 3.1 va bene.
**Il modello è una stringa: cambiarlo non tocca telefonia/backend/motore.**
* **Telefonia:** Twilio (partner già integrato con Live API su WebRTC, insieme a
LiveKit, Daily, Voximplant).
* **Backend:** Google Cloud Run (FastAPI).
* **Punto di partenza:** la **demo di riferimento Google "Gemini Live Telephony"**
(Twilio + FastAPI + ADK). Non è una scorciatoia usa-e-getta: è lo **scheletro
del prodotto di produzione**. Ti regala l'idraulica (WebSocket, streaming audio,
barge-in) che è IDENTICA in produzione; tu ci metti sopra la tua IP.

### Cosa è "idraulica" (uguale in produzione) vs "prodotto" (la tua IP)

* **Idraulica (dalla demo):** ponte WebSocket Twilio↔Gemini, streaming bidirezionale,
barge-in, encoding audio. Standard, noiosa, o funziona o no.
* **Prodotto (lo scrivi tu):** prompt del wizard, elicitazione parametri, motore
preventivi deterministico, integrazione listino, readback, invio link
WhatsApp/SMS. Qui vive il valore e qui impari a fare il prodotto vero.

\---

## 7\. Dove vive ogni cosa: cloud-config, locale, deploy

Il lavoro si divide in **tre luoghi**, non due. Distinguerli evita confusione su
cosa si "configura" e cosa si "pusha".

|Luogo|Cosa ci vive|Come ci si interviene|
|-|-|-|
|**Configurazione cloud** (console/CLI, una tantum)|Numero Twilio + voice webhook; progetto Google Cloud, abilitazione Vertex AI/Gemini, service account e credenziali; verifica account WhatsApp + template Meta; secret/API key nel Secret Manager|A mano nelle dashboard o via CLI. **Non è codice versionato, non si "pusha".** Si fa una volta (o di rado).|
|**Sviluppo locale** (codice in git — la tua IP)|Backend FastAPI, ponte WebSocket Twilio↔Gemini; motore preventivi deterministico + listino; prompt del wizard, elicitazione, readback; logica invio link SMS/WhatsApp|Scrivi e **testi in locale**. È il "prodotto" del §6. Iterato di continuo.|
|**Deploy (push)**|Lo stesso codice locale impacchettato in container|`gcloud run deploy` → Cloud Run espone un URL HTTPS pubblico. Quell'URL va nel voice webhook di Twilio (riga 1).|

### Il ciclo di sviluppo (non deployare a ogni modifica)

Mentre sviluppi NON serve un deploy in Cloud Run per ogni prova: giri il backend
in locale ed esponi `localhost` con un **tunnel** (es. `ngrok`). Twilio chiama il
tunnel → arriva al tuo PC.

> scrivi in locale → testi in locale (tunnel) → quando funziona → `deploy` in
> Cloud Run → punti il webhook Twilio all'URL di Cloud Run

Unica cosa che va fatta **a monte**: la configurazione cloud (riga 1). Senza numero
Twilio e API Gemini abilitate non parte nulla. Tutto il resto è il loop
locale → deploy.

\---

## 8\. Ordine di montaggio dell'MVP

L'obiettivo del primo giorno NON è il modello perfetto: è **un numero che squilla
e un agente che risponde.**

1. **Far squillare.** Metti in piedi la demo Google così com'è e falla rispondere
sul tuo numero di test. (Telefonia + modello che chiacchiera.)
2. **Function calling verso un listino FINTO.** Crea un mini-motore preventivi con
un listino inventato da te. L'agente raccoglie i parametri → chiama la function
→ riceve il prezzo → lo comunica. (Qui nasce il prodotto.)
3. **Readback + via di fuga.** L'agente ricapitola i parametri prima di dare il
prezzo; gestisce input ambigui chiedendo invece di indovinare.
4. **Consegna del link.** A fine conversazione manda il messaggio (prima SMS, è
immediato; WhatsApp dopo, quando l'account è verificato) con il link al
form/preventivo.

A fine giornata: un giro completo, anche grezzo. → poi si sostituisce il listino
finto con quello vero del committente.

\---

## 9\. Da MVP a produzione (hardening, non riscrittura)

Stessa architettura, si **indurisce** quello che c'è — non si cambia rotta:

* Gestione errori (chiamata che cade, audio interrotto, modello che non capisce).
* Logging, retry, osservabilità (le piattaforme/Google hanno simulation testing
e agent evaluation per validare prima del go-live).
* Sicurezza, controllo accessi, retention dati.
* Scalabilità (concorrenza chiamate).
* Decisione esplicita **modello Preview vs GA** (3.1 preview vs 2.5 GA stabile).
* WhatsApp: completare verifica account + template approvati.
* Eventuale **number porting** del numero aziendale esistente del committente
(oppure numero nuovo dedicato da Twilio = immediato).

\---

## 10\. Note commerciali (il prodotto deve essere TUO)

Usare infrastruttura di terzi (Twilio, Google, Cloud) **non** significa rivendere
un servizio altrui: è come è fatto il 99% del software (Netflix gira su AWS).
La differenza tra "rivendere" e "prodotto mio" sta in **dove vive la IP e da chi
dipende il cliente**.

* La tua IP: orchestrazione, prompt, motore preventivi integrato col listino,
flusso conversazionale. Tutto nel tuo backend.
* Consegni un sistema funzionante (un numero che risponde), non un login a un SaaS.
* Il cliente dipende da te per manutenzione, aggiornamenti listino, evoluzioni.
* Modello di ricavo: licenza/canone + manutenzione + margine sul consumo (i minuti
LLM li paghi tu e li ribalti).
* **Evitare il white-label puro** di una piattaforma (es. reseller SaaS): fragile,
il cliente può scoprire che se lo comprava da solo.

\---

## 11\. Note normative (da non dimenticare)

* **Disclosure AI:** se il flusso è *inbound* (è il cliente a chiamare) il carico
regolatorio è leggero, ma in molte giurisdizioni va comunque dichiarato all'inizio
che si parla con un'AI. Default prudente: dichiararlo.
* **WhatsApp opt-in + template:** vedi §4.5. Opt-in documentato obbligatorio.
* **GDPR:** l'opt-in va registrato (fonte, timestamp, scopo); raccogliere solo i
dati necessari; definire retention; privacy policy.

\---

## 12\. Riferimenti utili (verificare, possono cambiare)

* Gemini Live API (Google Cloud / Vertex AI / Google AI Studio) — model overview,
capabilities, pricing.
* Demo "Gemini Live Telephony" (Twilio + FastAPI + ADK) — punto di partenza MVP.
* Partner telefonia integrati su WebRTC: Twilio, LiveKit, Daily, Voximplant.
* WhatsApp Business Platform — policy messaggistica, template, opt-in.
* Provider WhatsApp/SMS: Twilio, Infobip.

\---

## Checklist rapida di partenza

* \[ ] Riunione: ottenere listino + 3-4 preventivi reali + parametri di prezzo
* \[ ] Decidere: cifra vincolante o stima/forbice
* \[ ] Scegliere UN tipo di lavoro per la prima versione
* \[ ] Far squillare la demo Google sul numero di test
* \[ ] Function calling verso listino finto
* \[ ] Readback + gestione input ambigui
* \[ ] Invio link via SMS (poi WhatsApp)
* \[ ] Avviare verifica account WhatsApp Business (tempi 1–6 settimane!)
* \[ ] Sostituire listino finto con quello reale
* \[ ] Hardening per produzione

