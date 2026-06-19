"""Runtime conversazionale: tool del modello, system instruction, dispatch.

Qui vive il collegamento tra l'LLM (che conversa) e il motore prezzi (che calcola):
- `QUOTE_TOOL`: la function declaration esposta a Gemini (function calling).
- `build_system_instruction`: prompt del tenant + listino con i codici validi.
- `dispatch_tool_call`: esegue la chiamata del modello sul motore deterministico.
"""
from __future__ import annotations

from app.pricing.engine import PriceEngine, UnknownItemError
from app.tenancy.models import Tenant

# Function declaration (vocabolario chiuso: il modello deve usare i `code` del listino).
QUOTE_TOOL = {
    "name": "calcola_preventivo",
    "description": (
        "Calcola il prezzo TOTALE ESATTO dell'ordine a partire dalle voci scelte dal "
        "cliente. Usa SEMPRE questa funzione per dare un totale: non calcolare mai i "
        "prezzi a mente. Usa esclusivamente i codici (`code`) del listino fornito."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "voci": {
                "type": "array",
                "description": "Le voci ordinate dal cliente.",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Codice esatto della voce di listino.",
                        },
                        "quantity": {
                            "type": "number",
                            "description": "Quantità richiesta.",
                        },
                    },
                    "required": ["code", "quantity"],
                },
            }
        },
        "required": ["voci"],
    },
}

# Tool per chiudere la chiamata. Condizioni STRETTE: l'agente non deve chiudere
# per pause, silenzi o assensi isolati (causa principale di chiusure premature).
END_CALL_TOOL = {
    "name": "end_call",
    "description": (
        "Termina la telefonata. USA QUESTA FUNZIONE SOLO se TUTTE queste condizioni "
        "sono vere: (1) hai già comunicato il totale dell'ordine, OPPURE il cliente ha "
        "detto esplicitamente di voler chiudere; (2) hai chiesto 'Desidera altro?' e il "
        "cliente ha risposto di no; (3) ti sei congedato con una frase di saluto. "
        "NON chiamarla MAI dopo una semplice pausa, un silenzio, un 'ok' o un 'sì' "
        "isolato, né se non sei sicuro che il cliente abbia finito."
    ),
    "parameters": {"type": "object", "properties": {}},
}

# Tutti i tool esposti al modello.
TOOLS = [QUOTE_TOOL, END_CALL_TOOL]

# Messaggio iniettato all'avvio per far salutare l'agente per primo.
GREETING_TRIGGER = (
    "[La chiamata è appena iniziata. Saluta per primo il cliente, presentati in una "
    "frase come assistente vocale automatico, e chiedi cosa desidera ordinare.]"
)

# Messaggi iniettati dal watchdog di silenzio (Blocco B).
SILENCE_PROMPT_TRIGGER = (
    "[Il cliente è in silenzio da qualche secondo. Chiedi con garbo se è ancora in "
    "linea o se desidera altro. NON chiudere la chiamata.]"
)
SILENCE_HANGUP_TRIGGER = (
    "[Il cliente non risponde da troppo tempo. Salutalo gentilmente e concludi la chiamata.]"
)


def build_system_instruction(tenant: Tenant, engine: PriceEngine) -> str:
    """Prompt del tenant + listino (raggruppato per categoria) coi codici validi."""
    base = tenant.prompt_path.read_text(encoding="utf-8")

    by_category: dict[str, list[dict]] = {}
    for item in engine.list_items():
        by_category.setdefault(item.get("category", "Altro"), []).append(item)

    sezioni = []
    for categoria, voci in by_category.items():
        righe = "\n".join(
            f"- {it['code']}: {it['name']} ({float(it['unit_price']):.2f} EUR)" for it in voci
        )
        sezioni.append(f"### {categoria}\n{righe}")
    listino = "\n".join(sezioni)

    return (
        f"{base}\n\n"
        "## Listino disponibile (è l'UNICO che puoi offrire)\n"
        "Usa ESATTAMENTE questi codici (`code`) quando chiami `calcola_preventivo`:\n"
        f"{listino}\n"
    )


def dispatch_tool_call(name: str, args: dict, engine: PriceEngine) -> dict:
    """Esegue una function call del modello sul motore deterministico.

    Ritorna sempre un dict (mai un'eccezione verso il modello): in caso di voce
    non a listino, restituisce un errore parlante così l'agente chiede invece di
    inventare (§4.3 del piano).
    """
    if name == "end_call":
        return {"status": "ok"}
    if name != "calcola_preventivo":
        return {"error": f"Funzione sconosciuta: {name}"}

    voci = args.get("voci", []) or []
    try:
        quote = engine.quote(voci)
    except UnknownItemError as exc:
        return {
            "error": f"Voce non presente nel listino: {exc}. "
            "Chiedi al cliente di scegliere tra le voci disponibili."
        }
    except (KeyError, ValueError, TypeError) as exc:
        return {"error": f"Selezione non valida: {exc}"}

    return {
        "currency": quote.currency,
        "total": quote.total,
        "lines": [
            {
                "description": line.description,
                "quantity": line.quantity,
                "subtotal": line.subtotal,
            }
            for line in quote.lines
        ],
    }


def format_order_sms(quote_result: dict, business_name: str) -> str:
    """Costruisce il testo dell'SMS di riepilogo dal risultato di `calcola_preventivo`."""
    currency = quote_result.get("currency", "EUR")
    righe = [
        f"- {float(line['quantity']):g}x {line['description']}: {float(line['subtotal']):.2f} {currency}"
        for line in quote_result.get("lines", [])
    ]
    totale = float(quote_result.get("total", 0))
    corpo = "\n".join(righe)
    return f"{business_name} - Riepilogo ordine:\n{corpo}\nTotale: {totale:.2f} {currency}\nGrazie!"
