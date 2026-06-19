# Wizard vocale telefonico

Agente vocale telefonico che guida il cliente nella scelta del prodotto e gli
recapita un preventivo. Vedi [piano-wizard-vocale.md](piano-wizard-vocale.md)
per il piano completo e [CLAUDE.md](CLAUDE.md) per stato e roadmap.

## Requisiti
- Python 3.12+

## Setup
```bash
python -m venv .venv
# Windows PowerShell:   .venv\Scripts\Activate.ps1
# Git Bash/macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Provare il motore prezzi (senza telefonia)
```bash
pytest -q
```

## Struttura
Vedi [CLAUDE.md](CLAUDE.md) → Architettura.
