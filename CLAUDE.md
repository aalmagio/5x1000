# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Context
- Primary languages: Python, YAML, Markdown
- Prefer Read + Glob for exploration before making changes

---

## Comandi principali

```bash
# Pipeline completa interattiva
python pipeline.py

# Aggiornamento anno specifico (dati già scaricati)
python pipeline.py --anni 2024 --skip-download

# Solo step specifici
python pipeline.py --anni 2024 --only etl,report

# Modalità ciclo non-interattiva (tutti gli anni in sequenza)
python pipeline.py --ciclo --smart

# Singoli script
python cinque_per_mille.py --source csv --anni 2024
python scarica_categorie.py --input categorie.xlsx --anni 2024
python etl.py --anni 2024 --no-excel
python report.py --anno 2024
python db_updater.py
python forecast.py
```

## Architettura della pipeline

```
cinque_per_mille.py  →  dati_XXXX.xlsx (per anno, in Dati/)
scarica_categorie.py →  ANNO_CATEGORIA_ammessi.xlsx + esclusi.xlsx (in Dati/CATEGORIA/)
etl.py               →  enti_5x1000_norm.csv  (~210 MB, ~1M righe, in Dati/)
report.py            →  report_ANNO.xlsx       (multi-foglio, in Dati/)
gsheets.py           →  upload su Google Sheets (per Looker Studio)
db_updater.py        →  aggiornamento MySQL del sito 5x1000.almagioni.com
forecast.py          →  site/public/data/forecast.json
```

**`pipeline.py`** è l'orchestratore: esegue tutti gli step in sequenza, fa le domande upfront e passa i parametri ai singoli script via subprocess. I passi completati in modalità `--ciclo` sono tracciati con file sentinella `.done` in `Dati/.stato/`.

## Schema dati e modello entità

`etl.py` normalizza anni eterogenei (2006–oggi) in uno schema unificato. Le colonne chiave: `ANNO`, `COD_FISCALE`, `DENOMINAZIONE`, `REGIONE`, `PROVINCIA`, `COMUNE`, `CAT_*` (boolean per categoria), `CATEGORIA_PRINCIPALE`, `N_SCELTE`, `IMPORTO_ESPRESSO`, `IMPORTO_GENERICO`, `IMPORTO_TOTALE`, `SOTTO_SOGLIA` (bool: scelte>0 ma importo=0), colonne `RUNTS_*` (join su CF).

**Le 7 categorie** (con i rispettivi slug usati come chiavi):
- `ETS_ONLUS` / `Volontariato` (pre-2022: solo Volontariato)
- `ASD` (sport dilettantistico)
- `Ricerca_scientifica`
- `Ricerca_sanitaria`
- `Comuni`
- `Beni_culturali`
- `Aree_protette`

`report.py` legge i file `Dati/CATEGORIA/ANNO_CATEGORIA_ammessi.xlsx` e costruisce un dizionario `entities[cf]["categories"][cat_key]` con `status`, `n_scelte`, `totale_erogabile`, ecc. Da questo produce un workbook Excel multi-foglio: COMPLESSIVO → 7 categorie → Grafici → Sotto_Soglia → Status_Incrociato → Licenza.

## Normalizzazione slug categorie

`scarica_categorie.py` normalizza i nomi-file scaricati in slug canonici tramite `slugify()`. Usa prima un match esatto su `CATEGORY_SLUGS`, poi prefix-matching (chiavi più lunghe prima). Questo gestisce varianti come `Enti_gestori_delle_aree_protette_ammessi_pdf` → `Aree_protette`.

## Configurazione

`config.yaml` nella root sovrascrive i default del codice per percorsi, URL AdE per anno, timeout, formattazione Excel. Priorità: **flag CLI > config.yaml > default nel codice**. Richiede `PyYAML`; senza funziona con i default interni.

## File non in repo

- `Dati/` — output ETL e report (gitignored)
- `Runts/` — file RUNTS da scaricare manualmente da registroterzosettore.gov.it
- `20XX/` — file grezzi AdE per anno (gitignored)
- `credentials.json` — chiave service account Google (mai committare)
- `.env` — variabili d'ambiente per DB e pipeline (mai committare)
- `log/` — log esecuzioni

## Sito web (`site/`)

SPA Vue (Vite + Tailwind) + API REST PHP su Plesk/Apache. Per aggiornare il frontend:
```bash
cd site/frontend && npm run build
# poi committa site/public/assets/ e site/public/index.html
```

Il DB MySQL è aggiornato da `db_updater.py`. Lo schema è in `site/db_schema.sql`.

## Note operative

- `--smart` usa `pipeline_checker.py` per saltare anni/step già aggiornati — utile per cron e riprese dopo interruzione.
- `--reset` è distruttivo: cancella tutto in `Dati/` e svuota le tabelle DB. Usare solo con `--force`.
- Il RUNTS si aggiorna manualmente: scaricare il file da registroterzosettore.gov.it e salvarlo in `Runts/`. Il join avviene su `COD_FISCALE`; coverage attuale ~55%.
- `ciclo_defaults.yaml` persiste le scelte interattive della modalità `--ciclo` per esecuzioni successive non-interactive.
