# 5 per Mille — Pipeline dati

Pipeline Python per scaricare, normalizzare e analizzare i dati dei beneficiari del **5 per mille** pubblicati dall'**Agenzia delle Entrate**, dal 2006 al 2024.

Produce un dataset normalizzato di circa **1 milione di righe** arricchito con i dati del **Registro Unico Nazionale del Terzo Settore (RUNTS)**, pronto per Looker Studio, Power BI, QlikView o qualsiasi strumento di analisi.

---

## Cosa fa

| Script | Funzione |
|---|---|
| `cinque_per_mille.py` | Scarica i file PDF/CSV dall'elenco complessivo AdE e li converte in Excel per anno |
| `scarica_categorie.py` | Scarica e converte i dati **per categoria** (ammessi/esclusi separati) |
| `etl.py` | Normalizza tutti i dati annuali in uno schema unificato e fa il join con il RUNTS |
| `gsheets.py` | Carica il dataset normalizzato su Google Sheets per Looker Studio |

---

## Schema del dataset normalizzato

Il file `Dati/enti_5x1000_norm.csv` prodotto da `etl.py` ha queste colonne:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `ANNO` | int | Anno di riferimento (2006–2024) |
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

Senza flag aggiuntivi lo script e' interattivo (come prima). Con `--source` e `--anni` diventa completamente non-interattivo, adatto all'esecuzione schedulata.

I file vengono salvati in sottocartelle `2006/`, `2007/`, …, `2024/` e convertiti in `dati_ANNO.xlsx` da copiare nella cartella `Dati/`.

### 1b. Scaricare i dati per categoria (ammessi/esclusi)

Per lavorare a livello di singola categoria (con file ammessi e esclusi separati), si usa un file Excel con l'elenco dei link alle pagine delle categorie:

```bash
# Download + estrazione (tutte le righe del file)
python scarica_categorie.py --input categorie.xlsx

# Solo anno 2024
python scarica_categorie.py --input categorie.xlsx --anni 2024

# Solo download (senza creare gli Excel)
python scarica_categorie.py --input categorie.xlsx --no-extract

# Solo estrazione (file gia' scaricati)
python scarica_categorie.py --input categorie.xlsx --no-download

# Estrai da PDF invece che da CSV
python scarica_categorie.py --input categorie.xlsx --source pdf
```

Il file Excel di input deve avere le colonne: **Categoria**, **Link**, **Anno**. Per ogni riga lo script:
1. Crea la cartella `{anno}/{categoria}/`
2. Scarica tutti i PDF e CSV dalla pagina
3. Classifica i file in "ammessi" e "esclusi"
4. Crea `{ANNO}_{CATEGORIA}_ammessi.xlsx` e `{ANNO}_{CATEGORIA}_esclusi.xlsx`

### 2. Normalizzare i dati (ETL)

```bash
# Tutto (tutti gli anni, con merge RUNTS, genera solo CSV)
python etl.py --no-excel

# Solo anni recenti
python etl.py --anni 2020,2021,2022,2023,2024 --no-excel

# Senza RUNTS
python etl.py --no-runts --no-excel

# Con output Excel (lento per ~1M righe)
python etl.py
```

Output: `Dati/enti_5x1000_norm.csv` (~210 MB)

### 3. Caricare su Google Sheets (per Looker Studio)

Prima di tutto, [crea le credenziali GCP](#setup-google-sheets):

```bash
python gsheets.py --sheet-id TUO_SHEET_ID
```

Il dataset è diviso per anno (un foglio per anno) per rispettare i limiti di Google Sheets.

---

## Configurazione (`config.yaml`)

Il file `config.yaml` nella root del progetto permette di modificare i parametri principali **senza toccare il codice Python**: URL per anno, timeout di download, formattazione Excel, percorsi cartelle.

Se il file non esiste o una chiave manca, gli script usano i valori di default interni. Il file e' commentato in italiano ed e' pensato per essere leggibile anche da chi non programma.

Priorita' dei valori: **flag CLI > config.yaml > default nel codice**.

> Richiede `PyYAML` (`pip install pyyaml`). Senza PyYAML gli script funzionano normalmente con i default.

---

## Struttura cartelle

```
5x1000/
├── cinque_per_mille.py   # Download + conversione PDF/CSV → Excel (elenco complessivo)
├── scarica_categorie.py  # Download + conversione per categoria (ammessi/esclusi)
├── etl.py                # ETL: normalizzazione + merge RUNTS
├── gsheets.py            # Export su Google Sheets
├── config.yaml           # Configurazione esterna (modificabile senza codice)
├── requirements.txt
│
├── Dati/                 # Excel per anno + output normalizzato (non in repo)
│   ├── dati_2006.xlsx
│   ├── ...
│   ├── dati_2024.xlsx
│   └── enti_5x1000_norm.csv   # ← output principale di etl.py
│
├── Runts/                # File RUNTS (da scaricare manualmente, non in repo)
│   └── *.xlsx
│
├── 2006/ … 2024/         # File grezzi scaricati dall'AdE (non in repo)
│   ├── *.pdf
│   └── *.csv
│
├── _EXAMPLE/             # File di esempio per testing
│   └── dati_2006_ESEMPIO.xlsx
│
└── log/                  # Log delle esecuzioni (non in repo)
```

---

## Setup Google Sheets

Per caricare i dati su Google Sheets (sorgente dati per Looker Studio):

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) e crea un progetto
2. Abilita **Google Sheets API** e **Google Drive API**
3. Vai in **IAM → Account di servizio** → Crea account (es. `etl-5x1000`)
4. Clicca sull'account → **Chiavi** → **Aggiungi chiave** → JSON
5. Salva il file come `credentials.json` nella root del progetto
6. Crea un Google Sheet vuoto, copia l'ID dall'URL:
   `https://docs.google.com/spreadsheets/d/`**`[QUESTO_È_L_ID]`**`/edit`
7. Condividi il foglio con l'email del service account (campo `client_email` in `credentials.json`) con permesso **Editor**
8. Lancia:
   ```bash
   python gsheets.py --sheet-id TUO_SHEET_ID
   ```

> `credentials.json` non va mai committato — è già in `.gitignore`.

---

## Fonti dati

- **Agenzia delle Entrate** — elenchi beneficiari 5 per mille:
  [agenziaentrate.gov.it](https://www.agenziaentrate.gov.it)
- **RUNTS** — Registro Unico Nazionale del Terzo Settore:
  [registroterzoettore.gov.it](https://www.registroterzoettore.gov.it)

I dati sono pubblici e di proprietà dell'Amministrazione pubblica italiana.

---

## Licenza

[MIT](LICENSE) — vedi file LICENSE.

I **dati** scaricati dall'Agenzia delle Entrate e dal RUNTS sono soggetti alle rispettive condizioni di utilizzo delle fonti originali.
