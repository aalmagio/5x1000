#!/usr/bin/env python3
"""
5 per Mille - Export su Google Sheets.

Carica enti_5x1000_norm.csv su Google Sheets per poi usarlo
come sorgente dati in Looker Studio.

Uso:
    python gsheets.py [--credentials FILE] [--sheet-id ID] [--out-csv FILE]

SETUP (da fare una sola volta):
  1. Vai su https://console.cloud.google.com
  2. Crea un nuovo progetto (es. "5x1000-data")
  3. Cerca "Google Sheets API" e abilitala
  4. Cerca "Google Drive API" e abilitala
  5. Vai in "IAM e amministrazione" → "Account di servizio"
  6. Crea un account di servizio (es. "etl-5x1000")
  7. Clicca sull'account creato → "Chiavi" → "Aggiungi chiave" → JSON
  8. Salva il file JSON in questa cartella come "credentials.json"
  9. Crea un Google Sheet e copia l'ID dall'URL:
       https://docs.google.com/spreadsheets/d/[QUESTO_E_L_ID]/edit
  10. Condividi il Google Sheet con l'email dell'account di servizio
      (la trovi nel credentials.json al campo "client_email")
      con permessi di "Editor"

Requisiti:
    pip install gspread pandas
"""

import os
import sys
import argparse
import logging
import math
from pathlib import Path

import pandas as pd

from common import get_logger, load_dotenv

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

DEFAULT_CREDENTIALS = Path(__file__).parent / "credentials.json"
DEFAULT_CSV = Path(__file__).parent / "Dati" / "enti_5x1000_norm.csv"

# Massimo righe per foglio Google Sheets (limite API: 10M celle)
# Con 25 colonne, 400k righe = 10M celle → dividiamo in più fogli se necessario
ROWS_PER_SHEET = 300_000

# Nome del file Google Sheets (viene creato se non esiste)
DEFAULT_SHEET_TITLE = "5x1000 - Dati Normalizzati"


# ============================================================================
# CARICAMENTO CREDENZIALI
# ============================================================================

def get_gspread_client(credentials_path: Path):
    """
    Crea e restituisce un client gspread autenticato via Service Account.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        logging.error(
            "Librerie mancanti. Installa con:\n"
            "    pip install gspread google-auth"
        )
        sys.exit(1)

    if not credentials_path.exists():
        logging.error(
            f"File credenziali non trovato: {credentials_path}\n"
            "Segui le istruzioni nel docstring di questo script per crearlo."
        )
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
    client = gspread.authorize(creds)
    logging.info("Autenticazione Google riuscita")
    return client


# ============================================================================
# SCRITTURA SU GOOGLE SHEETS
# ============================================================================

def clean_for_sheets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara il DataFrame per l'upload su Google Sheets:
    - Sostituisce NaN con stringa vuota
    - Converte booleani in SI/NO (più leggibile in Sheets/Looker)
    - Converte float senza decimali in int
    - Tronca stringhe troppo lunghe (limite cella Sheets: 50.000 char)
    """
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == bool:
            df[col] = df[col].map({True: "SI", False: "NO"})
        elif df[col].dtype == "object":
            df[col] = df[col].fillna("").astype(str).str[:1000]
        else:
            df[col] = df[col].fillna("")

    return df


def write_sheet(worksheet, df: pd.DataFrame, batch_size: int = 5000) -> None:
    """
    Scrive un DataFrame su un foglio Google Sheets in batch.
    Cancella i dati precedenti, ridimensiona il foglio e riscrive dall'inizio.
    """
    logging.info(f"  Pulizia foglio precedente...")
    worksheet.clear()

    df_clean = clean_for_sheets(df)
    headers = [list(df_clean.columns)]
    data = df_clean.values.tolist()

    # Ridimensiona il foglio per contenere tutti i dati (header + righe)
    needed_rows = len(data) + 1  # +1 per header
    needed_cols = len(df_clean.columns)
    worksheet.resize(rows=needed_rows, cols=needed_cols)
    logging.info(f"  Foglio ridimensionato: {needed_rows:,} righe x {needed_cols} colonne")

    # Scrivi header
    worksheet.update(values=headers, range_name="A1")
    logging.info(f"  Header scritto ({needed_cols} colonne)")

    # Scrivi dati in batch
    total_rows = len(data)
    n_batches = math.ceil(total_rows / batch_size)

    for i in range(n_batches):
        batch = data[i * batch_size : (i + 1) * batch_size]
        start_row = i * batch_size + 2  # +2 perche' la riga 1 e' header
        end_row = start_row + len(batch) - 1
        cell_range = f"A{start_row}"

        worksheet.update(values=batch, range_name=cell_range)
        pct = min(100, int((i + 1) * 100 / n_batches))
        logging.info(f"  Righe {start_row}-{end_row} ({pct}%)...")

    logging.info(f"  Scritte {total_rows:,} righe totali")


def format_sheet_header(worksheet, n_cols: int) -> None:
    """Applica formattazione base all'header (bold, sfondo blu, freeze)."""
    try:
        import gspread.utils
        worksheet.freeze(rows=1)
        header_range = f"A1:{gspread.utils.rowcol_to_a1(1, n_cols)}"
        worksheet.format(header_range, {
            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.60},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "horizontalAlignment": "CENTER",
        })
    except Exception as e:
        logging.warning(f"  Formattazione header saltata: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    root_dir = Path(__file__).parent
    get_logger("gsheets", root_dir)  # configura root logger

    parser = argparse.ArgumentParser(
        description="Carica i dati 5x1000 normalizzati su Google Sheets"
    )
    parser.add_argument(
        "--credentials", type=Path, default=DEFAULT_CREDENTIALS,
        help=f"Percorso al file credentials.json (default: {DEFAULT_CREDENTIALS})"
    )
    parser.add_argument(
        "--sheet-id", type=str, default=None,
        help="ID del Google Sheet esistente. Se omesso, viene creato un nuovo sheet."
    )
    parser.add_argument(
        "--sheet-title", type=str, default=DEFAULT_SHEET_TITLE,
        help=f"Titolo del Google Sheet da creare (default: '{DEFAULT_SHEET_TITLE}')"
    )
    parser.add_argument(
        "--csv", type=Path, default=DEFAULT_CSV,
        help=f"CSV normalizzato da caricare (default: {DEFAULT_CSV})"
    )
    parser.add_argument(
        "--anni", type=str, default=None,
        help="Filtra anni da caricare (es. '2020,2021,2022')"
    )
    parser.add_argument(
        "--batch-size", type=int, default=5000,
        help="Righe per batch API (default: 5000)"
    )
    args = parser.parse_args()

    # --- Carica CSV ---
    if not args.csv.exists():
        logging.error(f"CSV non trovato: {args.csv}\nEsegui prima: python etl.py")
        sys.exit(1)

    logging.info(f"Carico CSV: {args.csv}...")
    df = pd.read_csv(args.csv, dtype=str, low_memory=False)
    logging.info(f"  {len(df):,} righe, {len(df.columns)} colonne")

    if args.anni:
        anni_filter = [str(a.strip()) for a in args.anni.split(",")]
        df = df[df["ANNO"].isin(anni_filter)]
        logging.info(f"  Filtrati anni {anni_filter}: {len(df):,} righe")

    # --- Autenticazione Google ---
    client = get_gspread_client(args.credentials)

    # --- Apri o crea lo Spreadsheet ---
    if args.sheet_id:
        spreadsheet = client.open_by_key(args.sheet_id)
        logging.info(f"Sheet aperto: '{spreadsheet.title}' (ID: {args.sheet_id})")
    else:
        spreadsheet = client.create(args.sheet_title)
        logging.info(f"Sheet creato: '{args.sheet_title}' (ID: {spreadsheet.id})")
        logging.info(
            f"\n*** Salva questo ID per le prossime esecuzioni: ***\n"
            f"    --sheet-id {spreadsheet.id}\n"
            f"URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit\n"
        )

    # --- Decidi quanti fogli servono ---
    total_rows = len(df)
    n_sheets_needed = math.ceil(total_rows / ROWS_PER_SHEET)
    logging.info(f"Righe totali: {total_rows:,} → servono {n_sheets_needed} foglio/i")

    if n_sheets_needed == 1:
        # Un solo foglio: usa il primo
        worksheets = spreadsheet.worksheets()
        ws = worksheets[0]
        ws.update_title("Dati")

        logging.info(f"Scrittura su foglio 'Dati'...")
        write_sheet(ws, df, args.batch_size)
        format_sheet_header(ws, len(df.columns))

    else:
        # Più fogli: uno per ogni blocco di anni o per chunk
        # Strategia: dividi per anno (più utile in Looker Studio)
        anni_disponibili = sorted(df["ANNO"].unique())
        logging.info(f"Dataset grande - divido per anno: {anni_disponibili}")

        existing_sheets = {ws.title: ws for ws in spreadsheet.worksheets()}

        for idx, anno in enumerate(anni_disponibili):
            df_anno = df[df["ANNO"] == str(anno)]
            sheet_name = str(anno)

            if sheet_name in existing_sheets:
                ws = existing_sheets[sheet_name]
            elif idx == 0:
                ws = spreadsheet.worksheets()[0]
                ws.update_title(sheet_name)
            else:
                ws = spreadsheet.add_worksheet(title=sheet_name, rows=1, cols=1)

            logging.info(f"Anno {anno}: {len(df_anno):,} righe → foglio '{sheet_name}'")
            write_sheet(ws, df_anno, args.batch_size)
            format_sheet_header(ws, len(df_anno.columns))

    # --- Stampa URL finale ---
    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit"
    logging.info(f"\n{'='*60}")
    logging.info(f"Upload completato!")
    logging.info(f"URL Google Sheet: {sheet_url}")
    logging.info(f"ID: {spreadsheet.id}")
    logging.info(
        f"\nPer aggiornare in futuro:\n"
        f"    python gsheets.py --sheet-id {spreadsheet.id}"
    )
    logging.info("="*60)


if __name__ == "__main__":
    main()
