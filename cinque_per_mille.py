#!/usr/bin/env python3
"""
5 per Mille - Download e conversione dati dall'Agenzia delle Entrate.

Scarica i file PDF/CSV dalle pagine ufficiali dell'Agenzia delle Entrate,
li organizza in cartelle per anno e li converte in file Excel.

Uso:
    python cinque_per_mille.py [percorso_root]

Requisiti:
    pip install -r requirements.txt
"""

import sys
import os
import re
import glob
import csv
import logging
import datetime
import pdfplumber
from io import StringIO
from urllib.parse import urljoin, urlparse, unquote
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

YEAR_URLS = {
    2025: "https://www.agenziaentrate.gov.it/portale/elenco-permanente-delle-onlus-accreditate-per-il-2025",
    2024: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari",
    2023: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari-2023",
    2022: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-degli-enti-ammessi-in-una-o-piu-categorie-di-beneficiari",
    2021: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-degli-enti-ammessi-in-una-o-pi%C3%B9-categorie-di-beneficiari",
    2020: "https://www.agenziaentrate.gov.it/portale/web/guest/elenco-5x1000-2020-enti-ammessi-categorie-di-beneficiari",
    2019: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari-2019",
    2018: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-beneficiari-2018",
    2017: "https://www.agenziaentrate.gov.it/portale/archivio/archivioschedeadempimento/schede-adempimento-2017/agevolazioni-2017/iscrizione-elenchi-5-per-mille-2017/elenchi-5xmille2017/elenco-completo-beneficiari-5xmille2017",
    2016: "https://www.agenziaentrate.gov.it/portale/archivio/archivioschedeadempimento/schede-adempimento-2016/richiedere-2016/iscrizione-elenchi-5-per-mille-2016/elenchi-5xmille2016/elenco-enti-ammessi-categorie-beneficiari",
    2015: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2015/richiedere-2015/iscrizione-elenchi-5-per-mille-2015/elenchi-5xmille2015/elenco-complessivo-beneficiari-5xmille2015",
    2014: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2014/richiedere-2014/iscrizione-elenchi-5-per-mille-2014/elenchi-5xmille2014/elenco-complessivo-beneficiari-5xmille2014",
    2013: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2013/richiedere-2013/contributo-5xmille2013/elenchi-5xmille2013/elenco-complessivo-beneficiari-5xmille2013",
    2012: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2012/richiedere-2012/contributo-5-per-mille-2012/elenchi-2012/elenco-complessivo-beneficiari",
    2011: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2011/richiedere-2011/contributo-del-5-per-mille-2011/elenchi-2011/elenco-complessivo-beneficiari-2011",
    2010: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivioschedeadempimento/schede-adempimento-2010/richiedere-2010/iscrizione-elenchi-5-per-mille/elenchi/elenco-complessivo-beneficiari-5permille2010",
    2009: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivio-5permille/5-per-mille-anni-precedenti/contributo-5-per-mille-2009/elenchi-5xmille2009/elenco-complessivo-beneficiari-5xmille2009",
    2008: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivio-5permille/5-per-mille-anni-precedenti/contributo-5-per-mille-2008/elenchi-5xmille2008/elenco-complessivo-beneficiari-5xmille2008",
    2007: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivio-5permille/5-per-mille-anni-precedenti/contributo-5-per-mille-2007/elenchi-5xmille2007/elenchi-complessivi-5xmille2007",
    2006: "https://www.agenziaentrate.gov.it/portale/web/guest/archivio/archivio-5permille/5-per-mille-anni-precedenti/contributo-5-per-mille-2006/elenchi-5xmille2006/elenco-complessivo-beneficiari-5xmille2006",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(root_dir):
    """Configura il logging su file e console."""
    log_file = os.path.join(root_dir, f"cinque_per_mille_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info(f"Log salvato in: {log_file}")
    return log_file

# ============================================================================
# DOWNLOAD
# ============================================================================

def find_download_links(page_url, session):
    """
    Scarica la pagina e cerca tutti i link a file PDF e CSV.
    Restituisce dict {"pdf": [urls], "csv": [urls]}.
    """
    logging.info(f"  Scarico pagina: {page_url}")
    try:
        resp = session.get(page_url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"  Errore nel scaricare la pagina: {e}")
        return {"pdf": [], "csv": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    links = {"pdf": [], "csv": []}

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        href_lower = href.lower()

        # Filtra solo link a file PDF o CSV
        is_pdf = href_lower.endswith(".pdf") or ".pdf" in href_lower
        is_csv = href_lower.endswith(".csv") or ".csv" in href_lower

        if not is_pdf and not is_csv:
            # Controlla anche il testo del link
            link_text = a_tag.get_text(strip=True).lower()
            if "pdf" in link_text and ("elenco" in link_text or "beneficiari" in link_text or "parte" in link_text):
                is_pdf = True
            elif "csv" in link_text and ("elenco" in link_text or "beneficiari" in link_text or "parte" in link_text):
                is_csv = True

        if is_pdf or is_csv:
            full_url = urljoin(page_url, href)
            file_type = "pdf" if is_pdf else "csv"
            if full_url not in links[file_type]:
                links[file_type].append(full_url)
                link_text = a_tag.get_text(strip=True)[:80]
                logging.info(f"    Trovato {file_type.upper()}: {link_text}")

    logging.info(f"  Totale link trovati: {len(links['pdf'])} PDF, {len(links['csv'])} CSV")
    return links


def download_file(url, dest_path, session):
    """Scarica un file da URL e lo salva in dest_path. Restituisce True se riuscito."""
    filename = os.path.basename(dest_path)
    if os.path.exists(dest_path):
        size = os.path.getsize(dest_path)
        logging.info(f"    File gia' presente ({size:,} bytes), salto: {filename}")
        return True

    logging.info(f"    Scarico: {filename}...")
    try:
        resp = session.get(url, headers=HEADERS, timeout=120, stream=True)
        resp.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size = os.path.getsize(dest_path)
        logging.info(f"    Salvato: {filename} ({size:,} bytes)")
        return True
    except requests.RequestException as e:
        logging.error(f"    Errore nel download di {filename}: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def sanitize_filename(url, index, ext):
    """Genera un nome file pulito dall'URL, con indice progressivo."""
    parsed = urlparse(url)
    basename = os.path.basename(unquote(parsed.path))
    if basename and len(basename) < 200:
        # Pulisci il nome
        basename = re.sub(r'[^\w\-\.\(\) ]', '_', basename)
        if not basename.lower().endswith(f".{ext}"):
            basename += f".{ext}"
        return basename
    return f"file_{index:02d}.{ext}"


def download_year(year, root_dir, session):
    """Scarica tutti i file per un anno. Restituisce il numero di file scaricati."""
    url = YEAR_URLS.get(year)
    if not url:
        logging.warning(f"[{year}] Nessun URL configurato")
        return 0

    logging.info(f"[{year}] Inizio download")
    folder = os.path.join(root_dir, str(year))
    os.makedirs(folder, exist_ok=True)

    links = find_download_links(url, session)
    total_pdf = len(links["pdf"])
    total_csv = len(links["csv"])

    if total_pdf == 0 and total_csv == 0:
        logging.warning(f"[{year}] Nessun file trovato nella pagina. Potrebbe essere necessario verificare manualmente.")
        return 0

    downloaded = 0
    for ext in ["pdf", "csv"]:
        for idx, file_url in enumerate(links[ext], 1):
            filename = sanitize_filename(file_url, idx, ext)
            dest = os.path.join(folder, filename)
            if download_file(file_url, dest, session):
                downloaded += 1

    logging.info(f"[{year}] Download completato: {downloaded} file scaricati in {folder}")
    return downloaded

# ============================================================================
# PDF EXTRACTION (dal vecchio script)
# ============================================================================

def clean_cell(value):
    if value is None:
        return ""
    value = str(value).strip()
    value = re.sub(r'\n+', ' ', value)
    value = re.sub(r'\s{2,}', ' ', value)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    # Compatta testo spaziato tipo "L O M B A R D I A" -> "LOMBARDIA"
    # Cerca sequenze di 3+ caratteri singoli separati da spazio
    value = re.sub(
        r'(?<![A-Za-z0-9])([A-Za-z0-9])((?:\s[A-Za-z0-9]){2,})(?![A-Za-z0-9])',
        lambda m: m.group(0).replace(' ', ''),
        value,
    )
    return value


def extract_header_from_pdf(pdf_path):
    """Estrae l'intestazione dal primo PDF."""
    try:
        pdf = pdfplumber.open(pdf_path)
        tables = pdf.pages[0].extract_tables()
        pdf.close()
    except Exception as e:
        logging.error(f"  Errore nel leggere intestazione da {pdf_path}: {e}")
        return None, None, 0

    if not tables or not tables[0]:
        return None, None, 0

    table = tables[0]
    row1 = table[0]
    num_cols = len(row1)

    # Verifica se c'e' una seconda riga di sotto-intestazione
    if len(table) >= 2 and table[1][0] is None:
        row2 = table[1]
        header = []
        for i in range(num_cols):
            top = clean_cell(row1[i]) if i < len(row1) else ""
            bottom = clean_cell(row2[i]) if i < len(row2) else ""
            if top and bottom:
                header.append(f"{top} - {bottom}")
            elif top:
                header.append(top)
            elif bottom:
                header.append(bottom)
            else:
                header.append(f"Colonna_{i+1}")
    else:
        header = [clean_cell(c) for c in row1]

    # Firma per riconoscere intestazioni ripetute
    signature = [c for c in [clean_cell(c) for c in row1] if c][:3]
    return header, signature, num_cols


def is_header_row(row, header_signature):
    cleaned = [clean_cell(c) for c in row]
    row_sig = [c for c in cleaned if c][:3]
    return row_sig == header_signature


def extract_data_from_pdf(pdf_path, header_signature, num_cols):
    rows = []
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        logging.error(f"  Errore nell'aprire {pdf_path}: {e}")
        return rows

    for page_idx, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception as e:
            logging.warning(f"  Errore pagina {page_idx + 1} di {os.path.basename(pdf_path)}: {e}")
            continue

        for table in tables:
            for row in table:
                cleaned = [clean_cell(c) for c in row]

                if is_header_row(row, header_signature):
                    continue

                if all(c == "" for c in cleaned):
                    continue

                # Sotto-intestazione
                if cleaned[0] == "" and any(c != "" for c in cleaned[4:]):
                    non_empty = [c for c in cleaned if c]
                    if all(len(c) < 40 for c in non_empty) and len(non_empty) <= num_cols // 2:
                        continue

                while len(cleaned) < num_cols:
                    cleaned.append("")
                cleaned = cleaned[:num_cols]
                rows.append(cleaned)

    pdf.close()
    return rows

# ============================================================================
# CSV EXTRACTION
# ============================================================================

def detect_csv_params(file_path):
    """Rileva delimitatore e encoding di un file CSV."""
    # Prova encoding
    for enc in ["utf-8", "latin-1", "cp1252", "iso-8859-15"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                sample = f.read(4096)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        enc = "latin-1"
        with open(file_path, "r", encoding=enc) as f:
            sample = f.read(4096)

    # Rileva delimitatore
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"  # Default per dati italiani

    return enc, delimiter


def extract_data_from_csv(csv_path):
    """
    Legge un file CSV e restituisce (header, rows).
    Gestisce i vari formati dell'Agenzia delle Entrate.
    """
    enc, delimiter = detect_csv_params(csv_path)
    logging.info(f"    CSV: encoding={enc}, delimitatore='{delimiter}'")

    rows = []
    header = None

    with open(csv_path, "r", encoding=enc, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row_idx, row in enumerate(reader):
            cleaned = [clean_cell(c) for c in row]

            # Salta righe vuote
            if all(c == "" for c in cleaned):
                continue

            # Prima riga non vuota = intestazione
            if header is None:
                header = cleaned
                continue

            # Salta intestazioni ripetute (stessa prima cella dell'header)
            if cleaned[:3] == header[:3]:
                continue

            rows.append(cleaned)

    return header, rows

# ============================================================================
# EXCEL CREATION
# ============================================================================

def create_excel(header, all_rows, output_path, year):
    wb = Workbook()
    ws = wb.active
    ws.title = str(year)

    header_font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5496")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    data_font = Font(name="Arial", size=10)
    data_align = Alignment(vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    for col_idx, col_name in enumerate(header, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    for row_idx, row_data in enumerate(all_rows, 2):
        for col_idx, value in enumerate(row_data, 1):
            if col_idx <= len(header):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = data_align

    for col_idx in range(1, len(header) + 1):
        max_len = len(str(header[col_idx - 1]))
        for row in ws.iter_rows(min_row=2, max_row=min(50, ws.max_row), min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 45)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{ws.max_row}"

    wb.save(output_path)


def process_folder_pdf(folder_path, year):
    """Processa i PDF di una cartella e genera un Excel."""
    pdf_files = sorted(glob.glob(os.path.join(folder_path, "*.pdf")))
    if not pdf_files:
        return False

    logging.info(f"  Trovati {len(pdf_files)} file PDF")

    header, signature, num_cols = None, None, 0
    for pdf_path in pdf_files:
        header, signature, num_cols = extract_header_from_pdf(pdf_path)
        if header:
            logging.info(f"  Intestazione ({num_cols} colonne): {header[:5]}...")
            break

    if not header:
        logging.error(f"  Impossibile determinare l'intestazione dai PDF")
        return False

    all_rows = []
    for pdf_path in pdf_files:
        pdf_name = os.path.basename(pdf_path)
        rows = extract_data_from_pdf(pdf_path, signature, num_cols)
        logging.info(f"  {pdf_name}: {len(rows)} righe")
        all_rows.extend(rows)

    if not all_rows:
        logging.warning(f"  Nessun dato estratto dai PDF")
        return False

    # Filtra righe con codice fiscale vuoto
    before = len(all_rows)
    all_rows = [r for r in all_rows if r[0].strip()]
    dropped = before - len(all_rows)
    if dropped:
        logging.info(f"  Rimosse {dropped} righe con codice fiscale vuoto")

    output_path = os.path.join(folder_path, f"dati_{year}.xlsx")
    create_excel(header, all_rows, output_path, year)
    logging.info(f"  => Creato: dati_{year}.xlsx ({len(all_rows)} righe)")
    return True


def process_folder_csv(folder_path, year):
    """Processa i CSV di una cartella e genera un Excel."""
    csv_files = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
    if not csv_files:
        return False

    logging.info(f"  Trovati {len(csv_files)} file CSV")

    all_rows = []
    master_header = None

    for csv_path in csv_files:
        csv_name = os.path.basename(csv_path)
        header, rows = extract_data_from_csv(csv_path)

        if header and master_header is None:
            master_header = header
            logging.info(f"  Intestazione ({len(header)} colonne): {header[:5]}...")

        # Normalizza il numero di colonne
        if master_header:
            target_cols = len(master_header)
            for row in rows:
                while len(row) < target_cols:
                    row.append("")
                del row[target_cols:]

        logging.info(f"  {csv_name}: {len(rows)} righe")
        all_rows.extend(rows)

    if not master_header or not all_rows:
        logging.warning(f"  Nessun dato estratto dai CSV")
        return False

    # Filtra righe con codice fiscale vuoto
    before = len(all_rows)
    all_rows = [r for r in all_rows if r[0].strip()]
    dropped = before - len(all_rows)
    if dropped:
        logging.info(f"  Rimosse {dropped} righe con codice fiscale vuoto")

    output_path = os.path.join(folder_path, f"dati_{year}.xlsx")
    create_excel(master_header, all_rows, output_path, year)
    logging.info(f"  => Creato: dati_{year}.xlsx ({len(all_rows)} righe)")
    return True

# ============================================================================
# INTERFACCIA INTERATTIVA
# ============================================================================

def ask_yes_no(prompt, default="s"):
    """Chiede una conferma si/no."""
    suffix = " [S/n]: " if default == "s" else " [s/N]: "
    while True:
        answer = input(prompt + suffix).strip().lower()
        if answer == "":
            return default == "s"
        if answer in ("s", "si", "sì", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Rispondi s o n.")


def ask_years(available_years, label="Aggiorna"):
    """Chiede quali anni elaborare."""
    print(f"\nAnni disponibili: {min(available_years)}-{max(available_years)}")
    print(f"  [1] {label} tutti gli anni")
    print(f"  [2] Scegli quali anni")
    print()

    while True:
        choice = input("Scelta [1/2]: ").strip()
        if choice == "1":
            return sorted(available_years)
        if choice == "2":
            while True:
                raw = input("Inserisci gli anni separati da virgola (es. 2020,2021,2022): ").strip()
                try:
                    years = [int(y.strip()) for y in raw.split(",") if y.strip()]
                    invalid = [y for y in years if y not in available_years]
                    if invalid:
                        print(f"  Anni non validi: {invalid}. Riprova.")
                        continue
                    if not years:
                        print("  Nessun anno inserito. Riprova.")
                        continue
                    return sorted(years)
                except ValueError:
                    print("  Formato non valido. Usa numeri separati da virgola.")
        print("  Scelta non valida, inserisci 1 o 2.")


def ask_source(year, has_pdf, has_csv):
    """Chiede se usare PDF o CSV per una cartella con entrambi."""
    print(f"\n  [{year}] Sono presenti sia file PDF che CSV.")
    print("    [1] Usa i CSV (piu' veloce, ma senza importi totali)")
    print("    [2] Usa i PDF (piu' lento, dati completi)")
    while True:
        choice = input("    Scelta [1/2]: ").strip()
        if choice == "1":
            return "csv"
        if choice == "2":
            return "pdf"
        print("    Scelta non valida.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    root_dir = os.path.abspath(root_dir)
    os.makedirs(root_dir, exist_ok=True)

    log_file = setup_logging(root_dir)
    logging.info(f"Directory root: {root_dir}")
    logging.info(f"Python: {sys.version}")

    available_years = sorted(YEAR_URLS.keys())

    # ---- FASE 1: DOWNLOAD ----
    print("\n" + "=" * 60)
    print("  5 PER MILLE - Download e conversione dati")
    print("=" * 60)

    if not HAS_WEB:
        print("\n⚠  Le librerie 'requests' e 'beautifulsoup4' non sono installate.")
        print("   Il download non e' disponibile. Installa con:")
        print("   pip install requests beautifulsoup4")
        print("   Procedo solo con la conversione dei file gia' presenti.\n")
        do_download = False
    else:
        do_download = ask_yes_no("\nVuoi aggiornare i file scaricandoli dal sito dell'Agenzia delle Entrate?")

    if do_download:
        years_to_download = ask_years(available_years, label="Scarica")
        logging.info(f"Anni da scaricare: {years_to_download}")

        session = requests.Session()
        total_files = 0

        for year in years_to_download:
            count = download_year(year, root_dir, session)
            total_files += count

        session.close()
        logging.info(f"\nDownload completato: {total_files} file totali")

    # ---- FASE 2: CONVERSIONE EXCEL ----
    if not ask_yes_no("\nVuoi procedere alla creazione dei file Excel?"):
        logging.info("Conversione Excel saltata dall'utente.")
        print(f"\nLog completo: {log_file}")
        return

    # Trova le cartelle che hanno effettivamente file da elaborare
    years_with_data = []
    for year in available_years:
        folder = os.path.join(root_dir, str(year))
        if not os.path.isdir(folder):
            continue
        pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
        csv_files = glob.glob(os.path.join(folder, "*.csv"))
        if pdf_files or csv_files:
            years_with_data.append(year)

    if not years_with_data:
        logging.warning("Nessuna cartella con dati da elaborare.")
        print(f"\nLog completo: {log_file}")
        return

    years_to_extract = ask_years(years_with_data, label="Elabora")
    logging.info(f"Anni da elaborare: {years_to_extract}")

    print()
    processed = 0
    errors = 0

    for year in years_to_extract:
        folder = os.path.join(root_dir, str(year))
        if not os.path.isdir(folder):
            continue

        pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
        csv_files = glob.glob(os.path.join(folder, "*.csv"))

        if not pdf_files and not csv_files:
            logging.info(f"[{year}] Cartella vuota, salto")
            continue

        logging.info(f"[{year}] Elaborazione ({len(pdf_files)} PDF, {len(csv_files)} CSV)")

        # Scegli la fonte dati
        has_pdf = len(pdf_files) > 0
        has_csv = len(csv_files) > 0

        if has_pdf and has_csv:
            source = ask_source(year, has_pdf, has_csv)
        elif has_csv:
            source = "csv"
        else:
            source = "pdf"

        logging.info(f"[{year}] Fonte dati: {source.upper()}")

        try:
            if source == "csv":
                success = process_folder_csv(folder, year)
            else:
                success = process_folder_pdf(folder, year)

            if success:
                processed += 1
            else:
                errors += 1
        except Exception as e:
            logging.error(f"[{year}] Errore imprevisto: {e}")
            errors += 1

    print("\n" + "=" * 60)
    logging.info(f"Completato: {processed} cartelle elaborate, {errors} errori")
    print(f"Log completo: {log_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
