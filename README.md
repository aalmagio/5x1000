# 5 per Mille — Pipeline dati + sito web

Pipeline Python per scaricare, normalizzare e analizzare i dati dei beneficiari del **5 per mille** pubblicati dall'**Agenzia delle Entrate**, dal 2006 ad oggi.

Produce un dataset normalizzato di circa **1 milione di righe** arricchito con i dati del **Registro Unico Nazionale del Terzo Settore (RUNTS)**, accessibile via sito web open data ([5x1000.almagioni.com](https://5x1000.almagioni.com)) e via API REST.

---

## Cosa fa

| Script | Funzione |
|---|---|
| **`pipeline.py`** | **Orchestratore**: esegue tutti gli step in sequenza con un solo comando |
| `cinque_per_mille.py` | Scarica i file PDF/CSV dall'elenco complessivo AdE e li converte in Excel per anno |
| `scarica_categorie.py` | Scarica e converte i dati **per categoria** (ammessi/esclusi separati) |
| `etl.py` | Normalizza tutti i dati annuali in uno schema unificato e fa il join con il RUNTS |
| `report.py` | Genera un report Excel multi-foglio stile ASSIF/Bedogni con classifiche, confronto YoY e aggregazioni regionali |
| `gsheets.py` | Carica il dataset normalizzato su Google Sheets per Looker Studio |
| `db_updater.py` | Aggiorna il database MySQL del sito web al termine della pipeline |
| `forecast.py` | Genera proiezioni trend via regressione lineare; output JSON per il sito |
| `pipeline_checker.py` | Analizza i file esistenti per la modalità `--smart` (salta step già aggiornati) |

---

## Schema del dataset normalizzato

Il file `Dati/enti_5x1000_norm.csv` prodotto da `etl.py` ha queste colonne:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `ANNO` | int | Anno di riferimento (2006–anno corrente) |
| `COD_FISCALE` | str | Codice fiscale (11 char, zero-padded se numerico) |
| `DENOMINAZIONE` | str | Nome dell'ente |
| `REGIONE` | str | Regione sede |
| `PROVINCIA` | str | Sigla provincia (2 char) |
| `COMUNE` | str | Comune sede |
| `CAT_VOLONTARIATO` | bool | Ente di volontariato |
| `CAT_ASD` | bool | Associazione Sportiva Dilettantistica |
| `CAT_ETS_ONLUS` | bool | ETS / ONLUS (dal 2022, sostituisce Volontariato) |
| `CAT_RICERCA_SCI` | bool | Ricerca scientifica |
| `CAT_RICERCA_SAN` | bool | Ricerca sanitaria |
| `CAT_COMUNI` | bool | Comuni |
| `CAT_BENI_CULT` | bool | Beni culturali / MIBAC |
| `CAT_AREE_PROT` | bool | Enti gestori aree protette |
| `CATEGORIA_PRINCIPALE` | str | Categoria derivata (priorità: ricerca > comuni > beni > asd > ets > vol) |
| `N_SCELTE` | int | Numero di scelte dei contribuenti |
| `IMPORTO_ESPRESSO` | float | Importo da scelte espresse (€) |
| `IMPORTO_GENERICO` | float | Importo da scelte generiche (€) |
| `IMPORTO_TOTALE` | float | Importo totale erogato (€) |
| `RUNTS_DENOMINAZIONE` | str | Nome nel RUNTS (se presente) |
| `RUNTS_SEZIONE` | str | Sezione RUNTS (ODV, APS, ecc.) |
| `RUNTS_SEDE_COMUNE` | str | Comune sede legale da RUNTS |
| `RUNTS_SEDE_PROV` | str | Provincia sede legale da RUNTS |
| `RUNTS_5X1000` | bool | Iscritto al 5x1000 nel RUNTS |
| `RUNTS_DATA_ISCRIZIONE` | str | Data iscrizione al RUNTS |

> **Nota sul RUNTS**: il file degli iscritti al RUNTS va scaricato manualmente da [registroterzosettore.it](https://www.registroterzoettore.gov.it) e salvato nella cartella `Runts/`. Il join avviene su `COD_FISCALE`. Il match attuale è circa il 55% delle righe (gli enti più vecchi non sono ancora nel RUNTS).

---

## Installazione

```bash
pip install -r requirements.txt
```

Per il solo download e conversione (senza ETL avanzato):
```bash
pip install pdfplumber openpyxl requests beautifulsoup4
```

---

## Utilizzo

### 0. Pipeline completa (consigliato)

```bash
# Pipeline completa interattiva
python pipeline.py

# Solo anno 2024, senza riscaricare
python pipeline.py --anni 2024 --skip-download

# Senza Google Sheets
python pipeline.py --anni 2024 --skip-download --skip-gsheets

# Solo ETL + aggiornamento DB sito
python pipeline.py --only etl,gsheets

# Con Sheet ID specifico
python pipeline.py --sheet-id 1ABC... --anni 2024
```

| Flag | Default | Descrizione |
|---|---|---|
| `--anni` | tutti | Anni da elaborare (es. `2023,2024`) |
| `--source` | `csv` | Fonte dati: `csv` o `pdf` |
| `--input` | da config | File Excel con link categorie |
| `--skip-download` | | Salta il download in tutti gli script |
| `--skip-gsheets` | | Salta l'upload su Google Sheets |
| `--sheet-id` | da config | ID del Google Sheet |
| `--only` | tutti | Step specifici: `download,categorie,etl,report,gsheets` |
| `--no-runts` | | Salta il merge RUNTS in etl.py |
| `--no-excel-etl` | | Non genera il file Excel in etl.py (solo CSV) |
| `--anno-confronto` | anno-1 | Anno per il confronto YoY nel report |
| `--no-confronto` | | Non calcolare il confronto anno precedente nel report |
| `--skip-report` | | Salta la generazione del report |
| `--smart` | | Salta automaticamente step/anni già aggiornati |

La pipeline esegue in ordine: **download** → **categorie** → **etl** → **report** → **gsheets** → **db** (aggiornamento sito).

### 1. Scaricare i dati dall'Agenzia delle Entrate

```bash
# Modalita' interattiva (chiede tutto passo passo)
python cinque_per_mille.py

# Batch: solo conversione CSV degli anni 2023 e 2024, senza download
python cinque_per_mille.py --no-download --source csv --anni 2023,2024

# Batch: download + conversione PDF di tutti gli anni
python cinque_per_mille.py --source pdf

# Solo download, senza conversione Excel
python cinque_per_mille.py --no-convert
```

| Flag | Default | Descrizione |
|---|---|---|
| `--root` | `.` | Cartella root del progetto |
| `--anni` | tutti | Anni da elaborare (es. `2020,2021,2024`) |
| `--source` | `ask` | Fonte dati: `pdf`, `csv`, o `ask` (chiede per ogni cartella) |
| `--no-download` | | Salta la fase di download dall'AdE |
| `--no-convert` | | Salta la fase di conversione in Excel |

I file vengono salvati in sottocartelle `2006/`, `2007/`, ..., `2024/` e convertiti in `dati_ANNO.xlsx`, copiati automaticamente nella cartella `Dati/`.

### 1b. Scaricare i dati per categoria (ammessi/esclusi)

```bash
# Download + estrazione (tutte le righe del file)
python scarica_categorie.py --input categorie.xlsx

# Solo anno 2024
python scarica_categorie.py --input categorie.xlsx --anni 2024

# Solo download (senza creare gli Excel)
python scarica_categorie.py --input categorie.xlsx --no-extract

# Solo estrazione (file gia' scaricati)
python scarica_categorie.py --input categorie.xlsx --no-download
```

Il file Excel di input deve avere le colonne: **Categoria**, **Link**, **Anno**. Per ogni riga lo script:
1. Crea la cartella `{anno}/{categoria}/`
2. Scarica tutti i PDF e CSV dalla pagina
3. Classifica i file in "ammessi" e "esclusi"
4. Crea `{ANNO}_{CATEGORIA}_ammessi.xlsx` e `{ANNO}_{CATEGORIA}_esclusi.xlsx`
5. Copia gli Excel in `Dati/{CATEGORIA}/`

### 2. Normalizzare i dati (ETL)

```bash
# Tutto (tutti gli anni, con merge RUNTS)
python etl.py --no-excel

# Solo anni recenti
python etl.py --anni 2022,2023,2024 --no-excel

# Senza RUNTS
python etl.py --no-runts --no-excel
```

Output: `Dati/enti_5x1000_norm.csv` (~210 MB)

### 3. Generare il report Excel (stile ASSIF/Bedogni)

```bash
# Report anno 2024 con confronto automatico 2023
python report.py --anno 2024

# Confronto con un anno specifico
python report.py --anno 2024 --anno-confronto 2023

# Output personalizzato
python report.py --anno 2024 --output mio_report.xlsx
```

Output: `Dati/report_{anno}.xlsx`

### 4. Caricare su Google Sheets (per Looker Studio)

Prima di tutto, [crea le credenziali GCP](#setup-google-sheets):

```bash
python gsheets.py --sheet-id TUO_SHEET_ID
```

### 5. Generare le proiezioni trend (forecast)

```bash
# Proiezione standard: storico fino all'anno scorso, +2 anni
python forecast.py

# Numero di anni da proiettare personalizzato
python forecast.py --anni 3

# Specificare manualmente l'ultimo anno completo dello storico
python forecast.py --anno-max 2024

# Da CSV anziché dal DB
python forecast.py --csv Dati/enti_5x1000_norm.csv

# File di output personalizzato
python forecast.py --out /percorso/forecast.json
```

Output: `site/public/data/forecast.json`

| Flag | Default | Descrizione |
|---|---|---|
| `--anni` | `2` | Numero di anni futuri da proiettare |
| `--anno-max` | `anno corrente - 1` | Ultimo anno incluso nello storico (esclude anni parziali) |
| `--csv` | DB MySQL | CSV normalizzato di input |
| `--out` | `site/public/data/forecast.json` | Percorso file JSON di output |

> **Nota**: per default viene escluso l'anno in corso, che contiene dati incompleti. Le proiezioni partono quindi dal primo anno senza dati definitivi (es. se i dati completi arrivano fino al 2024, le proiezioni coprono il 2025 e il 2026).

---

## Configurazione (`config.yaml`)

Il file `config.yaml` nella root permette di modificare URL, timeout, formattazione Excel e percorsi senza toccare il codice. Se manca, gli script usano i default interni.

Priorità: **flag CLI > config.yaml > default nel codice**

> Richiede `PyYAML` (`pip install pyyaml`). Senza PyYAML funziona normalmente con i default.

---

## Struttura cartelle

```
5x1000/
├── pipeline.py           # Orchestratore
├── cinque_per_mille.py   # Download + conversione PDF/CSV → Excel
├── scarica_categorie.py  # Download + conversione per categoria
├── etl.py                # ETL: normalizzazione + merge RUNTS
├── report.py             # Report Excel multi-foglio
├── gsheets.py            # Export su Google Sheets
├── db_updater.py         # Aggiornamento DB sito web
├── forecast.py           # Proiezioni trend via regressione lineare
├── pipeline_checker.py   # Analisi smart mode
├── config.yaml           # Configurazione esterna
├── requirements.txt
│
├── site/                 # Sito web (5x1000.almagioni.com)
│   ├── db_schema.sql     # Schema MySQL del sito
│   ├── public/           # Webroot (Apache/Plesk)
│   │   ├── index.html    # SPA Vue
│   │   ├── api.php       # API REST (PHP)
│   │   ├── admin.php     # Pannello admin
│   │   ├── .htaccess     # Vue Router + redirect download
│   │   ├── .env.example  # Variabili d'ambiente (copiare in .env)
│   │   ├── data/
│   │   │   └── forecast.json  # Proiezioni generate da forecast.py
│   │   └── assets/       # JS/CSS buildati da Vite
│   └── frontend/         # Sorgenti Vue (Vite + Tailwind)
│       ├── src/
│       ├── package.json
│       └── vite.config.js
│
├── Dati/                 # Output finale (non in repo)
│   ├── dati_2006.xlsx ... dati_2024.xlsx
│   ├── enti_5x1000_norm.csv      # ← output principale di etl.py
│   └── report_2024.xlsx          # ← output di report.py
│
├── Runts/                # File RUNTS (da scaricare manualmente, non in repo)
├── 2006/ ... /           # File grezzi AdE per anno (non in repo)
├── _EXAMPLE/             # File di esempio per testing
└── log/                  # Log esecuzioni (non in repo)
```

---

## Sito web

Il sito [5x1000.almagioni.com](https://5x1000.almagioni.com) espone i dati via:
- **Interfaccia web**: esplora enti, confronta anni, analisi per categoria, proiezioni trend
- **API REST** (`/api/v1/`): endpoint JSON per integrazioni esterne (documentazione su `/api-docs`)
- **Download** diretto dei dataset in CSV e Excel

### Deploy su Plesk (Apache + PHP)

```bash
# 1. Build frontend
cd site/frontend && npm run build
# I file compilati vanno automaticamente in site/public/assets/

# 2. Committa e pusha gli asset aggiornati
git add site/public/assets/ site/public/index.html
git commit -m "Build frontend"
git push

# 3. Su Plesk: copia site/public/ nel webroot del dominio
#    e crea site/public/.env con le credenziali DB
```

Il `.env` del sito deve contenere:
```
SITE_DB_HOST=localhost
SITE_DB_USER=...
SITE_DB_PASSWORD=...
SITE_DB_NAME=...
ADMIN_PASSWORD=...  # hash bcrypt
```

---

## Setup Google Sheets

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) e crea un progetto
2. Abilita **Google Sheets API** e **Google Drive API**
3. Vai in **IAM → Account di servizio** → Crea account (es. `etl-5x1000`)
4. Clicca sull'account → **Chiavi** → **Aggiungi chiave** → JSON
5. Salva come `credentials.json` nella root del progetto
6. Crea un Google Sheet vuoto, copia l'ID dall'URL
7. Condividi il foglio con l'email del service account con permesso **Editor**
8. Lancia: `python gsheets.py --sheet-id TUO_SHEET_ID`

> `credentials.json` non va mai committato — è già in `.gitignore`.

---

## Fonti dati

- **Agenzia delle Entrate** — elenchi beneficiari 5 per mille: [agenziaentrate.gov.it](https://www.agenziaentrate.gov.it)
- **RUNTS** — Registro Unico Nazionale del Terzo Settore: [registroterzoettore.gov.it](https://www.registroterzoettore.gov.it)

I dati sono pubblici e di proprietà dell'Amministrazione pubblica italiana.

---

## Licenza

[MIT](LICENSE) — vedi file LICENSE.

I **dati** scaricati dall'Agenzia delle Entrate e dal RUNTS sono soggetti alle rispettive condizioni di utilizzo delle fonti originali.

---

## Roadmap

### Analisi e metriche

- [ ] **Inoptato**: estendere l'analisi anche al numero di scelte (non solo agli importi)
- [ ] **Valore medio scelta espressa**: aggiungere la metrica per ente e per comparto, con possibile correlazione al reddito medio dei dichiaranti
- [ ] **KPI di comparto** (da aggiungere alle pagine per categoria):
  - Nr. totale scelte generiche
  - Valore medio scelta generica ed espressa
  - Valore medio redistribuito con le generiche
  - Nr. enti con 0 scelte / Nr. enti con 0 importo
  - % ONP del comparto sul totale ONP iscritte
  - % scelte al comparto sul totale scelte 5×mille
  - % incidenza generiche sul totale erogato

### Filtri e navigazione

- [ ] **Filtro stato ente**: tendina Iscritti / Ammessi / Esclusi
- [ ] **Filtro regione**: selezione a tendina (in aggiunta o in sostituzione del filtro testo libero)

### Visualizzazioni

- [ ] **Mappa geografica**: grafico coropleto regionale o provinciale per scelte e importi

### Lead generation

- [ ] **Email gate prima del download**: form leggero (nome + email) da completare prima di scaricare CSV/Excel; i dati vengono salvati per attività di lead nurturing
