# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Context
- Primary languages: Python, YAML, Markdown
- Prefer Read + Glob for exploration before making changes

---

## Comandi principali

```bash
# Procedura guidata (aggiunta anno, aggiornamento anno, verifica, ripubblicazione)
python guida.py

# Verifica coerenza AdE <-> CSV <-> DB (Excel in Dati/verifiche/, exit 2 se anomalie)
python verifica.py --anni 2024

# Sincronizzazione sviluppo -> produzione (scambio tabelle atomico)
python sync.py --stato        # confronto, nessuna modifica
python sync.py                # DB + file (richiede sezione sync: in config.yaml)
python sync.py --rollback     # torna alla versione precedente
python sync.py --pulisci      # elimina tabelle *__old e release vecchie

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
python etl.py --anni 2024 --replace   # aggiorna un anno nel CSV senza perdere gli altri
python report.py --anno 2024
python estrai_scelte_categorie.py
python db_updater.py
python forecast.py
```

## Architettura della pipeline

```
cinque_per_mille.py        →  dati_XXXX.xlsx (per anno, in Dati/)
scarica_categorie.py       →  ANNO_CATEGORIA_ammessi.xlsx + esclusi.xlsx (in Dati/CATEGORIA/)
etl.py                     →  enti_5x1000_norm.csv  (~210 MB, ~1M righe, in Dati/)
report.py                  →  report_ANNO.xlsx       (multi-foglio, in Dati/)
estrai_scelte_categorie.py →  scelte_categorie.xlsx  (pivot scelte per categoria, in Dati/)
gsheets.py                 →  upload su Google Sheets (per Looker Studio)
db_updater.py              →  aggiornamento MySQL del sito 5x1000.almagioni.com
forecast.py                →  site/public/data/forecast.json
```

**`guida.py`** è il punto d'ingresso consigliato per aggiungere o aggiornare un anno. Per un singolo anno: archivia i file correnti in `_archivio/<anno>_<ts>/` (grezzi, Excel estratti, copia del CSV), riscarica da zero, esegue due controlli bloccanti (estratto vs versione precedente e CSV grezzi AdE; dopo l'ETL gli altri anni del CSV devono restare identici) e ripristina l'archivio se qualcosa fallisce prima della pubblicazione. Pubblica con `db_updater.sostituisci_anno()` (DELETE+INSERT in un'unica transazione, ROLLBACK su errore o conteggio enti diverso dagli attesi), poi `finalizza_ciclo`, forecast e `verifica.py`. Lock in `Dati/.stato/guida.lock`.

**`sync.py`** porta i dati da sviluppo (sottodominio Plesk, DB `DEV_DB_*`) a produzione (`PROD_DB_*`). Copia le tabelle `enti, categoria_ammissioni, ripartizioni, runts, pipeline_runs, dataset_files` in `<tabella>__new` su produzione a blocchi per chiave primaria, verifica conteggi e totali per anno, copia i file scaricabili in una nuova release (`dataset_files.percorso` riscritto, SHA-256 ricontrollato), poi esegue un unico `RENAME TABLE` atomico (`t -> t__old, t__new -> t`), svuota `nlq_cache` e sostituisce `forecast.json`. Blocca se lo schema differisce o se un anno presente in produzione manca in sviluppo. Non tocca mai `leads` e `nlq_rate_limit`. Stato dell'ultima sync in `Dati/.stato/sync_ultimo.json`. Si esegue via SSH sul server dalla root di sviluppo (`<home>/dev5x1000.almagioni.com`); la produzione è la cartella sorella `<home>/5x1000.almagioni.com` e i percorsi `sync:` in `config.yaml` sono relativi alla root (release in `Dati/_release/` di produzione, unica posizione servita da `api.php`). Procedura operativa: `PROCEDURA_AGGIORNAMENTO.md`.

**`pipeline.py`** è l'orchestratore: esegue tutti gli step in sequenza, fa le domande upfront e passa i parametri ai singoli script via subprocess. I passi completati in modalità `--ciclo` sono tracciati con file sentinella `.done` in `Dati/.stato/`.

### Flag `--replace` di `etl.py`

In modalità `--ciclo` la pipeline chiama `etl.py --anni ANNO --replace` per ogni anno. Il flag `--replace` rimuove prima dal CSV le righe dell'anno indicato (in streaming, chunk per chunk) e poi le riscrive, garantendo che `enti_5x1000_norm.csv` rimanga integro anche in caso di ri-elaborazione. Senza `--replace`, una chiamata con `--anni` sovrascrive il CSV perdendo tutti gli altri anni.

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

`estrai_scelte_categorie.py` legge gli stessi file per-categoria e produce un pivot Excel `Dati/scelte_categorie.xlsx` con scelte espresse, generiche e degli esclusi per categoria e anno (dal 2019). Viene registrato nel catalogo `dataset_files` da `db_updater.py` con `tipo='scelte'` ed è scaricabile dalla pagina Download del sito. **Nota**: per i DB esistenti eseguire la migration in `site/db_schema.sql` (`ALTER TABLE dataset_files MODIFY COLUMN tipo ENUM(...,'scelte')`)..

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
- Il callback `--aggiorna-db` in `etl.py` converte `RUNTS_DATA_ISCRIZIONE` da `dd/mm/yyyy` a `yyyy-mm-dd` (MySQL DATE) e i booleani da stringa a 0/1 prima dell'INSERT, allineandosi al comportamento di `db_updater._aggiorna_enti`.
