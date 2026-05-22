#!/usr/bin/env python3
"""
5 per Mille - Download e conversione dati PER CATEGORIA.

A differenza di cinque_per_mille.py (che lavora per "elenco complessivo"
per anno), questo script lavora a livello di singola categoria, partendo
da un file Excel con l'elenco dei link alle pagine di ciascuna categoria.

Produce file Excel separati per ammessi e esclusi:
  {ANNO}_{CATEGORIA}_ammessi.xlsx
  {ANNO}_{CATEGORIA}_esclusi.xlsx

Uso:
    python scarica_categorie.py --input categorie.xlsx
    python scarica_categorie.py --input categorie.xlsx --anni 2024 --no-extract
    python scarica_categorie.py --input categorie.xlsx --no-download --source pdf
    python scarica_categorie.py --help

Requisiti:
    pip install -r requirements.txt
    pip install pandas   (per leggere il file Excel di input)
"""

import sys
import os
import re
import glob
import shutil
import logging
import argparse

import pandas as pd

from urllib.parse import urlparse, unquote

# Importa utility da cinque_per_mille.py (stesso progetto)
from cinque_per_mille import (
    find_download_links,
    download_file,
    clean_cell,
    detect_csv_params,
    extract_data_from_csv,
    extract_header_from_pdf,
    extract_data_from_pdf,
    create_excel,
    _apply_config,
    _apply_excel_config,
    HEADERS,
)

from common import get_logger, load_config

try:
    import requests
    HAS_WEB = True
except ImportError:
    HAS_WEB = False


# ============================================================================
# NAMING FILE
# ============================================================================

def smart_filename(url, index, ext):
    """
    Genera un nome file descrittivo dall'URL.
    Le URL dell'AdE hanno due formati:
    1) .../NomeDescrittivo.pdf/UUID?t=... → usa NomeDescrittivo.pdf
    2) .../5xm-af2024-ricscientifica-ammessi-csv → usa come nome + aggiunge .ext
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    segments = [s for s in path.split("/") if s]

    # Cerca il segmento descrittivo (contiene ammess/esclus e ha estensione file)
    for seg in segments:
        seg_lower = seg.lower()
        has_keyword = "ammess" in seg_lower or "esclus" in seg_lower
        has_ext = seg_lower.endswith(f".{ext}")
        if has_keyword and has_ext:
            # Pulisci il nome
            name = re.sub(r'[^\w\-\.\(\) ]', '_', seg)
            return name[:200]

    # Cerca segmento con keyword ma senza estensione (formato /d/guest/)
    for seg in segments:
        seg_lower = seg.lower()
        if "ammess" in seg_lower or "esclus" in seg_lower:
            name = re.sub(r'[^\w\-\.\(\) ]', '_', seg)
            if not name.lower().endswith(f".{ext}"):
                name += f".{ext}"
            return name[:200]

    # Fallback: basename dell'URL
    basename = segments[-1] if segments else f"file_{index:02d}"
    basename = re.sub(r'[^\w\-\.\(\) ]', '_', basename)
    if not basename.lower().endswith(f".{ext}"):
        basename += f".{ext}"
    return basename[:200]


# ============================================================================
# MAPPATURA CATEGORIE → SLUG
# ============================================================================

# Nomi canonici: ogni slug vecchio viene normalizzato al nome canonico
SLUG_NORMALIZE = {
    "Aree_protette": "Aree_protette",
    "ASD": "ASD",
    "Associazioni_Sportive_Dilettantistiche_ASD": "ASD",
    "Beni_culturali": "Beni_culturali",
    "Beni_culturali_e_paesaggistici": "Beni_culturali",
    "Comuni": "Comuni",
    "Enti_del_volontariato": "ETS_ONLUS",
    "ETS_ONLUS": "ETS_ONLUS",
    "Ricerca_sanitaria": "Ricerca_sanitaria",
    "Ricerca_scientifica": "Ricerca_scientifica",
    # Vecchi nomi extra
    "Volontariato": "ETS_ONLUS",
    "Enti_gestori_delle_aree_protette": "Aree_protette",
}

CATEGORY_SLUGS = {
    "enti del terzo settore e onlus": "ETS_ONLUS",
    "ricerca scientifica": "Ricerca_scientifica",
    "ricerca sanitaria": "Ricerca_sanitaria",
    "attivita' svolte dai comuni": "Comuni",
    "attivita svolte dai comuni": "Comuni",
    "attività svolte dai comuni": "Comuni",
    "associazioni sportive dilettantistiche": "ASD",
    "enti dei beni culturali e paesaggistici": "Beni_culturali",
    "enti gestori delle aree protette": "Aree_protette",
    # Categorie piu' vecchie
    "volontariato": "ETS_ONLUS",
}


def slugify(categoria):
    """Converte il nome categoria in uno slug canonico per il filesystem."""
    key = categoria.strip().lower()
    if key in CATEGORY_SLUGS:
        return CATEGORY_SLUGS[key]
    # Prova match per prefisso nelle chiavi lowercase (gestisce suffissi extra)
    for known_key in sorted(CATEGORY_SLUGS, key=len, reverse=True):
        if key.startswith(known_key):
            return CATEGORY_SLUGS[known_key]
    # Fallback: rimuovi caratteri speciali, sostituisci spazi
    slug = re.sub(r"[^\w\s-]", "", categoria.strip())
    slug = re.sub(r"[\s-]+", "_", slug)
    slug = slug[:50]
    # Normalizza al nome canonico se presente (exact match)
    if slug in SLUG_NORMALIZE:
        return SLUG_NORMALIZE[slug]
    # Prova match per prefisso nello slug generato
    for known_slug in sorted(SLUG_NORMALIZE, key=len, reverse=True):
        if slug.startswith(known_slug):
            return SLUG_NORMALIZE[known_slug]
    return slug


# ============================================================================
# LETTURA INPUT
# ============================================================================

def load_links(excel_path):
    """
    Legge il file Excel con (Categoria, Link, Anno).
    Restituisce una lista di dict con chiavi: anno, categoria, slug, url.
    """
    df = pd.read_excel(excel_path, dtype=str)

    # Normalizza nomi colonne (gestisce typo "Categora")
    col_map = {}
    for col in df.columns:
        cn = col.strip().lower()
        if cn in ("categoria", "categora"):
            col_map[col] = "categoria"
        elif cn == "link":
            col_map[col] = "link"
        elif cn == "anno":
            col_map[col] = "anno"
    df = df.rename(columns=col_map)

    if "categoria" not in df.columns or "link" not in df.columns or "anno" not in df.columns:
        logging.error(f"Il file deve avere le colonne: Categoria, Link, Anno. Trovate: {list(df.columns)}")
        sys.exit(1)

    entries = []
    for _, row in df.iterrows():
        cat = str(row["categoria"]).strip()
        url = str(row["link"]).strip()
        anno = str(row["anno"]).strip()
        if not cat or not url or not anno:
            continue
        entries.append({
            "anno": int(anno),
            "categoria": cat,
            "slug": slugify(cat),
            "url": url,
        })

    logging.info(f"Caricate {len(entries)} righe da {os.path.basename(excel_path)}")
    return entries


# ============================================================================
# DOWNLOAD PER CATEGORIA
# ============================================================================

def _is_direct_file_url(url):
    """
    Controlla se l'URL punta direttamente a un file PDF o CSV
    (non a una pagina HTML con link da estrarre).
    """
    parsed = urlparse(url)
    path_lower = unquote(parsed.path).lower()
    # Controlla estensione esplicita
    if path_lower.endswith(".pdf") or path_lower.endswith(".csv"):
        return True
    # Controlla pattern AdE tipo "/d/guest/...csv" o ".../NomeFile.pdf/UUID"
    segments = [s for s in path_lower.split("/") if s]
    for seg in segments:
        if seg.endswith(".pdf") or seg.endswith(".csv"):
            return True
        # Pattern con UUID dopo il nome file: NomeFile.pdf/abc-123-...
        if ".pdf" in seg or ".csv" in seg:
            return True
    return False


def _detect_file_ext(url, session):
    """
    Determina il tipo di file (pdf/csv) dall'URL o dal Content-Type.
    Restituisce 'pdf', 'csv' oppure None.
    """
    path_lower = unquote(urlparse(url).lower() if hasattr(urlparse(url), 'lower') else urlparse(url).path.lower())
    if ".pdf" in path_lower:
        return "pdf"
    if ".csv" in path_lower:
        return "csv"
    # In caso dubbio, fai un HEAD per controllare il Content-Type
    try:
        resp = session.head(url, headers=HEADERS, timeout=30, allow_redirects=True)
        ct = resp.headers.get("Content-Type", "").lower()
        if "pdf" in ct:
            return "pdf"
        if "csv" in ct or "text/plain" in ct or "octet-stream" in ct:
            return "csv"
    except Exception:
        pass
    return None


def download_category(anno, slug, page_url, root_dir, session):
    """
    Scarica tutti i PDF e CSV dalla pagina di una categoria.

    Se page_url punta direttamente a un file PDF o CSV, lo scarica
    direttamente senza tentare di analizzare la pagina HTML.

    Restituisce dict:
        {"downloaded": int, "errors": list[str]}
    dove errors contiene messaggi su link/file non funzionanti.
    """
    folder = os.path.join(root_dir, str(anno), slug)
    os.makedirs(folder, exist_ok=True)
    errors = []

    # --- Caso 1: Link diretto a un file PDF o CSV ---
    if _is_direct_file_url(page_url):
        ext = _detect_file_ext(page_url, session)
        if ext is None:
            ext = "csv"  # fallback
        logging.info(f"[{anno}/{slug}] Link diretto a {ext.upper()}: {page_url}")
        filename = smart_filename(page_url, 1, ext)
        dest = os.path.join(folder, filename)
        if download_file(page_url, dest, session):
            logging.info(f"[{anno}/{slug}] Scaricato: {filename}")
            return {"downloaded": 1, "errors": []}
        else:
            msg = f"[{anno}/{slug}] Download fallito: {filename} -- {page_url}"
            logging.warning(msg)
            return {"downloaded": 0, "errors": [msg]}

    # --- Caso 2: Pagina HTML con link da estrarre ---
    logging.info(f"[{anno}/{slug}] Scarico link da pagina: {page_url}")

    # Verifica che la pagina sia raggiungibile
    try:
        resp = session.get(page_url, headers=HEADERS, timeout=60, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        msg = f"[{anno}/{slug}] Pagina non raggiungibile: {page_url} -- {e}"
        logging.error(msg)
        errors.append(msg)
        return {"downloaded": 0, "errors": errors}

    # Controlla se la risposta e' in realta' un file binario (PDF/CSV)
    # nonostante l'URL non avesse un'estensione riconoscibile
    ct = resp.headers.get("Content-Type", "").lower()
    if "pdf" in ct or ("octet-stream" in ct and ".pdf" in page_url.lower()):
        logging.info(f"[{anno}/{slug}] La risposta e' un PDF diretto (Content-Type: {ct})")
        filename = smart_filename(page_url, 1, "pdf")
        dest = os.path.join(folder, filename)
        with open(dest, "wb") as f:
            f.write(resp.content)
        logging.info(f"[{anno}/{slug}] Salvato: {filename}")
        return {"downloaded": 1, "errors": []}
    if "csv" in ct or "text/plain" in ct:
        # Potrebbe essere un CSV diretto — verifica che non sia HTML
        if not resp.text.strip().startswith("<!") and not resp.text.strip().startswith("<html"):
            logging.info(f"[{anno}/{slug}] La risposta e' un CSV diretto (Content-Type: {ct})")
            filename = smart_filename(page_url, 1, "csv")
            dest = os.path.join(folder, filename)
            with open(dest, "wb") as f:
                f.write(resp.content)
            logging.info(f"[{anno}/{slug}] Salvato: {filename}")
            return {"downloaded": 1, "errors": []}

    links = find_download_links(page_url, session)

    total_pdf = len(links["pdf"])
    total_csv = len(links["csv"])

    if total_pdf == 0 and total_csv == 0:
        msg = f"[{anno}/{slug}] Nessun file trovato nella pagina: {page_url}"
        logging.warning(msg)
        errors.append(msg)
        return {"downloaded": 0, "errors": errors}

    downloaded = 0
    for ext in ["pdf", "csv"]:
        for idx, file_url in enumerate(links[ext], 1):
            filename = smart_filename(file_url, idx, ext)
            dest = os.path.join(folder, filename)
            if download_file(file_url, dest, session):
                downloaded += 1
            else:
                msg = f"[{anno}/{slug}] Download fallito: {filename} -- {file_url}"
                logging.warning(msg)
                errors.append(msg)

    logging.info(f"[{anno}/{slug}] Download completato: {downloaded} file ({total_pdf} PDF, {total_csv} CSV)")
    return {"downloaded": downloaded, "errors": errors}


# ============================================================================
# CLASSIFICAZIONE AMMESSI / ESCLUSI
# ============================================================================

def classify_files(folder, ext="csv"):
    """
    Classifica i file in una cartella in ammessi e esclusi,
    in base al nome del file.
    Restituisce {"ammessi": [paths], "esclusi": [paths]}.
    """
    all_files = sorted(glob.glob(os.path.join(folder, f"*.{ext}")))
    result = {"ammessi": [], "esclusi": []}

    for f in all_files:
        name = os.path.basename(f).lower()
        if "esclus" in name:
            result["esclusi"].append(f)
        elif "ammess" in name or "ammiss" in name:
            result["ammessi"].append(f)
        else:
            # Se non classificabile, trattalo come ammesso
            logging.warning(f"  File non classificabile, trattato come ammesso: {os.path.basename(f)}")
            result["ammessi"].append(f)

    return result


# ============================================================================
# ESTRAZIONE DATI → EXCEL
# ============================================================================

def extract_csv_group(csv_files, output_path, sheet_name):
    """
    Legge e unisce piu' file CSV, poi crea un Excel formattato.
    Restituisce il numero di righe estratte, o 0 se fallisce.
    """
    if not csv_files:
        return 0

     = []
    master_header = None

    for csv_path in csv_files:
        csv_name = os.path.basename(csv_path)
        header, rows = extract_data_from_csv(csv_path)

        if header and master_header is None:
            master_header = header
            logging.info(f"    Intestazione ({len(header)} colonne): {header[:5]}...")

        # Normalizza il numero di colonne
        if master_header:
            target_cols = len(master_header)
            for row in rows:
                while len(row) < target_cols:
                    row.append("")
                del row[target_cols:]

        logging.info(f"    {csv_name}: {len(rows)} righe")
        .extend(rows)

    if not master_header or not :
        return 0

    # Filtra righe con prima cella vuota
    before = len(all_rows)
    # Prima (generico, colonna 1):
    # all_rows = [r for r in all_rows if r[0].strip()]
    # Dopo (ETS: colonna 2; tutte le altre: colonna 1):
    is_ets = "ets" in output_path.lower() or "terzo_settore" in output_path.lower()
    col_idx = 1 if is_ets else 0
    all_rows = [r for r in all_rows if len(r) > col_idx and r[col_idx].strip()]
    
    dropped = before - len(all_rows)
    if dropped:
        logging.info(f"    Rimosse {dropped} righe con prima cella vuota")

    create_excel(master_header, all_rows, output_path, sheet_name)
    logging.info(f"    => {os.path.basename(output_path)}: {len(all_rows)} righe")
    return len(all_rows)


def extract_pdf_group(pdf_files, output_path, sheet_name):
    """
    Legge e unisce piu' file PDF, poi crea un Excel formattato.
    Restituisce il numero di righe estratte, o 0 se fallisce.
    """
    if not pdf_files:
        return 0

    # Estrai header dal primo PDF
    header, signature, num_cols = None, None, 0
    for pdf_path in pdf_files:
        header, signature, num_cols = extract_header_from_pdf(pdf_path)
        if header:
            logging.info(f"    Intestazione PDF ({num_cols} colonne): {header[:5]}...")
            break

    if not header:
        logging.error(f"    Impossibile determinare intestazione dai PDF")
        return 0

    all_rows = []
    for pdf_path in pdf_files:
        pdf_name = os.path.basename(pdf_path)
        rows = list(extract_data_from_pdf(pdf_path, signature, num_cols))
        logging.info(f"    {pdf_name}: {len(rows)} righe")
        all_rows.extend(rows)

    if not all_rows:
        return 0

    # Filtra righe con prima cella vuota
    before = len(all_rows)
    all_rows = [r for r in all_rows if r[0].strip()]
    dropped = before - len(all_rows)
    if dropped:
        logging.info(f"    Rimosse {dropped} righe con prima cella vuota")

    create_excel(header, all_rows, output_path, sheet_name)
    logging.info(f"    => {os.path.basename(output_path)}: {len(all_rows)} righe")
    return len(all_rows)


def extract_category(anno, slug, root_dir, source="csv"):
    """
    Estrae i dati dalla cartella di una categoria e crea i file Excel.
    source: "csv" (default, con fallback PDF) o "pdf".
    """
    folder = os.path.join(root_dir, str(anno), slug)
    if not os.path.isdir(folder):
        logging.warning(f"[{anno}/{slug}] Cartella non trovata: {folder}")
        return

    logging.info(f"[{anno}/{slug}] Estrazione dati (source={source})")

    # Classifica file per tipo (ammessi/esclusi) e formato (csv/pdf)
    csv_groups = classify_files(folder, "csv")
    pdf_groups = classify_files(folder, "pdf")

    for tipo in ("ammessi", "esclusi"):
        output_name = f"{anno}_{slug}_{tipo}.xlsx"
        output_path = os.path.join(folder, output_name)
        sheet_name = f"{tipo.capitalize()}"

        # Scegli la fonte
        use_csv = csv_groups[tipo] if source == "csv" else []
        use_pdf = pdf_groups[tipo] if source == "pdf" else []

        rows_extracted = 0

        if source == "csv" and use_csv:
            logging.info(f"  [{tipo}] Estrazione da {len(use_csv)} CSV")
            rows_extracted = extract_csv_group(use_csv, output_path, sheet_name)
        elif source == "csv" and not use_csv and pdf_groups[tipo]:
            # Fallback PDF
            logging.info(f"  [{tipo}] Nessun CSV, fallback su {len(pdf_groups[tipo])} PDF")
            rows_extracted = extract_pdf_group(pdf_groups[tipo], output_path, sheet_name)
        elif source == "pdf" and use_pdf:
            logging.info(f"  [{tipo}] Estrazione da {len(use_pdf)} PDF")
            rows_extracted = extract_pdf_group(use_pdf, output_path, sheet_name)
        elif source == "pdf" and not use_pdf and csv_groups[tipo]:
            # Fallback CSV
            logging.info(f"  [{tipo}] Nessun PDF, fallback su {len(csv_groups[tipo])} CSV")
            rows_extracted = extract_csv_group(csv_groups[tipo], output_path, sheet_name)
        else:
            logging.info(f"  [{tipo}] Nessun file da estrarre")

        if rows_extracted == 0 and (use_csv or use_pdf or csv_groups[tipo] or pdf_groups[tipo]):
            logging.warning(f"  [{tipo}] Estrazione fallita: 0 righe")

    # Copia gli Excel estratti in Dati/{slug}/
    dati_cat_dir = os.path.join(root_dir, "Dati", slug)
    xlsx_files = glob.glob(os.path.join(folder, f"{anno}_{slug}_*.xlsx"))
    if xlsx_files:
        os.makedirs(dati_cat_dir, exist_ok=True)
        for xlsx in xlsx_files:
            dest = os.path.join(dati_cat_dir, os.path.basename(xlsx))
            shutil.copy2(xlsx, dest)
            logging.info(f"  Copiato in Dati/{slug}/{os.path.basename(xlsx)}")


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="5 per Mille - Download e conversione per CATEGORIA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Esempi:
  %(prog)s --input categorie.xlsx                         # download + estrazione
  %(prog)s --input categorie.xlsx --anni 2024             # solo anno 2024
  %(prog)s --input categorie.xlsx --no-extract            # solo download
  %(prog)s --input categorie.xlsx --no-download           # solo estrazione
  %(prog)s --input categorie.xlsx --source pdf            # estrai da PDF
""",
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="File Excel con colonne (Categoria, Link, Anno)",
    )
    parser.add_argument(
        "--root", type=str, default=".",
        help="Cartella root per download e output (default: directory corrente)",
    )
    parser.add_argument(
        "--anni", type=str, default=None,
        help="Filtro anni, separati da virgola (es. 2023,2024)",
    )
    parser.add_argument(
        "--source", choices=["csv", "pdf"], default="csv",
        help="Fonte dati per estrazione: 'csv' (default) o 'pdf'",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Salta il download, procedi solo con l'estrazione",
    )
    parser.add_argument(
        "--no-extract", action="store_true",
        help="Salta l'estrazione, procedi solo con il download",
    )
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

def main():
    args = parse_args()

    root_dir = os.path.abspath(args.root)
    os.makedirs(root_dir, exist_ok=True)

    # Configurazione
    cfg = load_config(root_dir)
    _apply_config(cfg)
    _apply_excel_config(cfg)

    _, log_file = get_logger("scarica_categorie", root_dir)
    logging.info(f"Directory root: {root_dir}")

    if cfg:
        logging.info("Configurazione caricata da config.yaml")

    # Verifica file input
    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        logging.error(f"File input non trovato: {input_path}")
        sys.exit(1)

    # Carica elenco link
    entries = load_links(input_path)
    if not entries:
        logging.error("Nessuna riga valida nel file input")
        sys.exit(1)

    # Filtro anni
    if args.anni:
        try:
            anni_filter = set(int(a.strip()) for a in args.anni.split(",") if a.strip())
            entries = [e for e in entries if e["anno"] in anni_filter]
            logging.info(f"Filtro anni: {sorted(anni_filter)} -> {len(entries)} righe")
        except ValueError:
            logging.error(f"Formato anni non valido: '{args.anni}'")
            sys.exit(1)

    if not entries:
        logging.warning("Nessuna riga da elaborare dopo il filtro anni")
        return

    # Riepilogo
    anni = sorted(set(e["anno"] for e in entries), reverse=True)
    categorie = sorted(set(e["slug"] for e in entries))
    logging.info(f"Anni: {anni}")
    logging.info(f"Categorie: {categorie}")
    logging.info(f"Totale operazioni: {len(entries)}")

    # Ordina dal più recente al più vecchio (coerente con etl.py)
    entries = sorted(entries, key=lambda e: e["anno"], reverse=True)

    # ---- FASE 1: DOWNLOAD ----
    all_errors = []

    if not args.no_download:
        if not HAS_WEB:
            logging.error("Libreria 'requests' non installata. Impossibile scaricare.")
            logging.error("Installa con: pip install requests beautifulsoup4")
        else:
            logging.info("\n--- FASE 1: DOWNLOAD ---")
            session = requests.Session()
            total_files = 0

            for entry in entries:
                result = download_category(
                    entry["anno"], entry["slug"], entry["url"],
                    root_dir, session,
                )
                total_files += result["downloaded"]
                all_errors.extend(result["errors"])

            session.close()
            logging.info(f"Download completato: {total_files} file totali")
    else:
        logging.info("Download saltato (--no-download)")

    # ---- FASE 2: ESTRAZIONE ----
    if not args.no_extract:
        logging.info("\n--- FASE 2: ESTRAZIONE ---")
        for entry in entries:
            extract_category(
                entry["anno"], entry["slug"],
                root_dir, source=args.source,
            )
        logging.info("Estrazione completata")
    else:
        logging.info("Estrazione saltata (--no-extract)")

    # ---- REPORT LINK NON FUNZIONANTI ----
    if all_errors:
        logging.warning(f"\n{'='*60}")
        logging.warning(f"ATTENZIONE: {len(all_errors)} problema/i riscontrato/i:")
        logging.warning(f"{'='*60}")
        for i, err in enumerate(all_errors, 1):
            logging.warning(f"  {i}. {err}")
        logging.warning(f"{'='*60}")
        logging.warning("Correggi i link nel file Excel e rilancia lo script.")

    logging.info(f"\nLog completo: {log_file}")


if __name__ == "__main__":
    main()
