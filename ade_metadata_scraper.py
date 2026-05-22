#!/usr/bin/env python3
"""
5 per Mille - Scraper metadati file da Agenzia delle Entrate.

Scrappa le pagine AdE per estrarre le date di ultimo aggiornamento dei file
e genera due CSV:
  1. ade_file_elenco_completo.csv  — file elenco complessivo per anno
  2. ade_file_categorie.csv        — file per categoria

Uso:
    python ade_metadata_scraper.py                      # tutti gli anni
    python ade_metadata_scraper.py --anni 2024,2023     # anni specifici
    python ade_metadata_scraper.py --only categorie     # solo categorie
    python ade_metadata_scraper.py --only elenco        # solo elenco complessivo
"""

import sys
import os
import re
import csv
import logging
import argparse
import datetime

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from common import get_logger, load_config
from cinque_per_mille import (
    _apply_config,
    HEADERS,
)


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# URL elenco complessivo per anno (da config.yaml)
ELENCO_URLS = {
    2025: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-degli-enti-ammessi-in-una-o-pi%C3%B9-categorie-di-beneficiari1",
    2024: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari",
    2023: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari-2023",
    2022: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-degli-enti-ammessi-in-una-o-piu-categorie-di-beneficiari",
    2021: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-degli-enti-ammessi-in-una-o-pi%C3%B9-categorie-di-beneficiari",
    2020: "https://www.agenziaentrate.gov.it/portale/web/guest/elenco-5x1000-2020-enti-ammessi-categorie-di-beneficiari",
    2019: "https://www.agenziaentrate.gov.it/portale/elenco-complessivo-dei-beneficiari-2019",
}

# URL categorie per anno
CATEGORIE_URLS = {
    2025: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-del-terzo-settore",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica2",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/elenchi-ammessi-ed-esclusi2#:~:text=Ricerca%20scientifica-,Ricerca%20sanitaria,-Attivit%C3%A0%20svolte%20dai",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/elenchi-ammessi-ed-esclusi2#:~:text=Attivit%C3%A0%20svolte%20dai%20comuni",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche1",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/enti-gestori-delle-aree-protette",
    },
    2024: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-del-terzo-settore-e-onlus-2024",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica-2024",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria-2024",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivit%C3%A0-svolte-dai-comuni-2024",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche-2024",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici-2024",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/enti-gestori-delle-aree-protette-2024",
    },
    2023: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-del-terzo-settore-e-onlus-2023",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica-2023",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria-2023",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivita-svolte-dai-comuni-2023",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche-2023",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici-2023",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/Enti-gestori-delle-aree-protette-2023",
    },
    2022: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-del-terzo-settore-e-onlus-23",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica-23",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivita-svolte-dai-comuni-23",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche-asd-23",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/beni-culturali-e-paesaggistici-23",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/documents/20143/4443043/5XM-AF2022+-+AREE+PROTETTE+-+AMMESSI.pdf/51ed59be-2418-4db3-39c5-61ab02064f31?t=1687459725347",
    },
    2021: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-volontariato-ammessi-esclusi-af-2021",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica-ammessi-esclusi-af-2021",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria-ammessi-esclusi-af-2021",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivit%C3%A0-svolte-dai-comuni-ammessi-esclusi-af-2021",
        "ASD": "https://www.agenziaentrate.gov.it/portale/asd-ammessi-esclusi-af-2021",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici-af-2021",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/enti-gestori-aree-protette-ammessi-esclusi-af-2021",
    },
    2020: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/ammessi-ed-esclusi-enti-del-volontariato-5x1000-2020",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica-ammessi-ed-esclusi-5x1000-2020",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria-ammessi-esclusi-5x1000-2020",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivita-svolte-dai-comuni-ammessi-esclusi-5x1000-2020",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche-ammessi-esclusi-5x1000-2020",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici-ammessi-esclusi-5x1000-2020",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/enti-gestori-delle-aree-protette-esclusi-ammessi-5x1000-2020",
    },
    2019: {
        "ETS_ONLUS": "https://www.agenziaentrate.gov.it/portale/enti-del-volontariato-2019",
        "Ricerca_scientifica": "https://www.agenziaentrate.gov.it/portale/ricerca-scientifica1",
        "Ricerca_sanitaria": "https://www.agenziaentrate.gov.it/portale/ricerca-sanitaria-2019",
        "Comuni": "https://www.agenziaentrate.gov.it/portale/attivit%C3%A0-svolte-dai-comuni-2019",
        "ASD": "https://www.agenziaentrate.gov.it/portale/associazioni-sportive-dilettantistiche-2019",
        "Beni_culturali": "https://www.agenziaentrate.gov.it/portale/enti-dei-beni-culturali-e-paesaggistici-2019",
        "Aree_protette": "https://www.agenziaentrate.gov.it/portale/enti-gestori-delle-aree-protette-2019",
    },
}


# ============================================================================
# SCRAPER HELPER
# ============================================================================

def extract_date_from_text(text):
    """Estrae una data dal testo nel formato GG/MM/YYYY."""
    if not text:
        return None

    # Prova pattern: GG/MM/YYYY oppure GG giugno YYYY, ecc.
    # Pattern con numeri: GG.MM.YYYY oppure GG/MM/YYYY
    patterns = [
        r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})',  # GG/MM/YYYY
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            day, month, year = match.groups()
            try:
                # Valida la data
                datetime.datetime(int(year), int(month), int(day))
                return f"{int(day):02d}/{int(month):02d}/{year}"
            except ValueError:
                continue

    return None


def scrape_elenco_completo(anno, url, session):
    """
    Scrappa la pagina dell'elenco complessivo e estrae i file con le loro date.
    Restituisce lista di dict: {"parte": int, "formato": str, "nome_file": str, "data": str}
    """
    logging.info(f"[{anno}] Scraping elenco complessivo: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logging.warning(f"[{anno}] Errore nel fetch della pagina: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    files = []

    # Cerca link PDF e CSV nella pagina
    # Pattern tipico: "5x1000-AF2024 ... - agg. DD.MM.YYYY"
    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True)
        href = link.get("href", "")

        # Estrai nome file e data dal testo del link
        if "5x1000" in text.lower() or "5XM" in text or "5X1000" in text:
            # Estrai data dal testo
            date_str = extract_date_from_text(text)
            if not date_str:
                # Prova a estrarre da attributi della pagina
                date_str = None

            # Determina il formato
            if ".pdf" in href.lower() or "pdf" in text.lower():
                fmt = "PDF"
            elif ".csv" in href.lower() or "csv" in text.lower():
                fmt = "CSV"
            else:
                fmt = "PDF"  # default

            # Estrai numero parte se presente
            parte_match = re.search(r'[^\d]([1-7])[^\d]|P(?:0)?([1-7])', text)
            parte = int(parte_match.group(1) or parte_match.group(2)) if parte_match else None

            files.append({
                "nome_file": text[:100],
                "formato": fmt,
                "data": date_str,
                "parte": parte,
            })

    logging.info(f"[{anno}] Trovati {len(files)} file")
    return files


def scrape_categoria(anno, categoria, url, session):
    """
    Scrappa una pagina di categoria e estrae i file con le loro date.
    Restituisce lista di dict: {"tipo": "ammessi"|"esclusi", "nome_file": str, "data": str}
    """
    logging.info(f"[{anno}/{categoria}] Scraping: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logging.warning(f"[{anno}/{categoria}] Errore nel fetch: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    files = []

    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True)
        href = link.get("href", "")

        # Filtra link pertinenti (PDF/CSV, ammessi/esclusi)
        text_lower = text.lower()
        if not any(x in text_lower for x in ["pdf", "csv", "ammess", "esclus"]):
            continue

        # Estrai data
        date_str = extract_date_from_text(text)

        # Determina tipo (ammessi/esclusi)
        if "esclus" in text_lower:
            tipo = "esclusi"
        else:
            tipo = "ammessi"

        files.append({
            "nome_file": text[:100],
            "tipo": tipo,
            "data": date_str,
        })

    logging.info(f"[{anno}/{categoria}] Trovati {len(files)} file")
    return files


# ============================================================================
# SALVATAGGIO CSV
# ============================================================================

def save_elenco_csv(root_dir, all_files):
    """Salva i file dell'elenco complessivo in CSV."""
    output_path = os.path.join(root_dir, "ade_file_elenco_completo.csv")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["anno", "parte", "formato", "nome_file", "data_aggiornamento"]
        )
        writer.writeheader()

        for row in all_files:
            writer.writerow(row)

    logging.info(f"Salvato: {output_path} ({len(all_files)} righe)")
    return output_path


def save_categorie_csv(root_dir, all_files):
    """Salva i file delle categorie in CSV."""
    output_path = os.path.join(root_dir, "ade_file_categorie.csv")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["anno", "categoria", "tipo_file", "nome_file", "data_aggiornamento"]
        )
        writer.writeheader()

        for row in all_files:
            writer.writerow(row)

    logging.info(f"Salvato: {output_path} ({len(all_files)} righe)")
    return output_path


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scrappa metadati file da Agenzia delle Entrate",
    )
    parser.add_argument(
        "--anni", type=str, default=None,
        help="Anni da scrapare (default: tutti), separati da virgola",
    )
    parser.add_argument(
        "--root", type=str, default=".",
        help="Directory root (default: corrente)",
    )
    parser.add_argument(
        "--only", choices=["elenco", "categorie"], default=None,
        help="Scrappa solo elenco complessivo o solo categorie",
    )
    args = parser.parse_args()

    if not HAS_WEB:
        logging.error("Richieste requests e beautifulsoup4. Installa con: pip install requests beautifulsoup4")
        sys.exit(1)

    root_dir = os.path.abspath(args.root)
    os.makedirs(root_dir, exist_ok=True)

    cfg = load_config(root_dir)
    _apply_config(cfg)
    # Aggiorna ELENCO_URLS con url_anni da config.yaml
    url_anni_cfg = cfg.get("url_anni", {}) if cfg else {}
    for _anno, _url in url_anni_cfg.items():
        ELENCO_URLS[int(_anno)] = str(_url)

    _, log_file = get_logger("ade_metadata_scraper", root_dir)

    # Determina anni da scrapare
    if args.anni:
        anni = [int(a.strip()) for a in args.anni.split(",")]
    else:
        anni = sorted(ELENCO_URLS.keys(), reverse=True)

    logging.info(f"Anni: {anni}")

    session = requests.Session()

    try:
        # ---- ELENCO COMPLESSIVO ----
        if args.only != "categorie":
            logging.info("\n=== ELENCO COMPLESSIVO ===")
            elenco_rows = []

            for anno in anni:
                if anno not in ELENCO_URLS:
                    logging.warning(f"[{anno}] URL non configurato")
                    continue

                files = scrape_elenco_completo(anno, ELENCO_URLS[anno], session)

                for f in files:
                    elenco_rows.append({
                        "anno": anno,
                        "parte": f.get("parte", ""),
                        "formato": f.get("formato", ""),
                        "nome_file": f.get("nome_file", ""),
                        "data_aggiornamento": f.get("data", ""),
                    })

            if elenco_rows:
                save_elenco_csv(root_dir, elenco_rows)
            else:
                logging.warning("Nessun file trovato per elenco complessivo")

        # ---- CATEGORIE ----
        if args.only != "elenco":
            logging.info("\n=== CATEGORIE ===")
            categorie_rows = []

            for anno in anni:
                if anno not in CATEGORIE_URLS:
                    logging.warning(f"[{anno}] URL categorie non configurati")
                    continue

                for categoria, url in CATEGORIE_URLS[anno].items():
                    files = scrape_categoria(anno, categoria, url, session)

                    for f in files:
                        categorie_rows.append({
                            "anno": anno,
                            "categoria": categoria,
                            "tipo_file": f.get("tipo", ""),
                            "nome_file": f.get("nome_file", ""),
                            "data_aggiornamento": f.get("data", ""),
                        })

            if categorie_rows:
                save_categorie_csv(root_dir, categorie_rows)
            else:
                logging.warning("Nessun file trovato per categorie")

    finally:
        session.close()

    logging.info(f"\nLog completo: {log_file}")


if __name__ == "__main__":
    main()
