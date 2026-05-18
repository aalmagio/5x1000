#!/usr/bin/env python3
"""
5 per Mille - ETL: normalizzazione, merge RUNTS, export.

Legge tutti i dati_XXXX.xlsx dalla cartella Dati/, normalizza lo schema
(che cambia ogni anno), arricchisce con i dati RUNTS e produce:
  - enti_5x1000_norm.csv   : dataset normalizzato completo
  - enti_5x1000_norm.xlsx  : stessa cosa in Excel

Schema output:
  ANNO, COD_FISCALE, DENOMINAZIONE, REGIONE, PROVINCIA, COMUNE,
  CAT_VOLONTARIATO, CAT_ASD, CAT_RICERCA_SCI, CAT_RICERCA_SAN,
  CAT_COMUNI, CAT_BENI_CULT, CAT_AREE_PROT, CAT_ETS_ONLUS,
  CATEGORIA_PRINCIPALE, N_SCELTE, IMPORTO_ESPRESSO, IMPORTO_GENERICO,
  IMPORTO_TOTALE,
  [RUNTS_SEZIONE, RUNTS_SEDE_COMUNE, RUNTS_SEDE_PROV, RUNTS_5X1000,
   RUNTS_DATA_ISCRIZIONE]  <- presenti solo se RUNTS trovato

Uso:
    python etl.py [--root CARTELLA] [--runts FILE_XLSX] [--out CARTELLA_OUTPUT]
    python etl.py                          # usa defaults

Requisiti:
    pip install pandas xlsxwriter openpyxl
"""

import os
import re
import sys
import math
import argparse
import logging
import datetime
from pathlib import Path

import pandas as pd

from common import load_config, apply_excel_config, get_logger, EXCEL_CONFIG

# ============================================================================
# CONFIGURAZIONE DEFAULT
# ============================================================================

DEFAULT_ROOT = Path(__file__).parent
DEFAULT_DATI = DEFAULT_ROOT / "Dati"
DEFAULT_RUNTS = DEFAULT_ROOT / "Runts"
DEFAULT_OUT = DEFAULT_ROOT / "Dati"

# Configurazione ETL
ETL_CONFIG = {
    "chunk_size": 50_000,
}


def _apply_config(cfg: dict) -> None:
    """Applica i valori di config.yaml a EXCEL_CONFIG e ETL_CONFIG."""
    apply_excel_config(cfg)
    etl_cfg = cfg.get("etl", {})
    if etl_cfg.get("chunk_size"):
        ETL_CONFIG["chunk_size"] = int(etl_cfg["chunk_size"])


# ============================================================================
# UTILITY: NORMALIZZAZIONE NOMI REGIONE
# ============================================================================

# Mappa raw (maiuscolo) → display (20 regioni ufficiali italiane).
# Speculare alla funzione normalize_regione() in api.php.
# Forme senza trattino (Emilia Romagna, Friuli Venezia Giulia) per coerenza
# con il dataset AdE che non usa mai il trattino in questi nomi.
_REGIONE_NORM_MAP: dict[str, str] = {
    "ABRUZZO":                             "Abruzzo",
    "BASILICATA":                          "Basilicata",
    "CALABRIA":                            "Calabria",
    "CAMPANIA":                            "Campania",
    # Emilia Romagna — senza trattino (forma usata dall'AdE)
    "EMILIA-ROMAGNA":                      "Emilia Romagna",
    "EMILIA ROMAGNA":                      "Emilia Romagna",
    "EMILIAROMAGNA":                       "Emilia Romagna",   # PDF senza spazi
    # Friuli — senza trattino
    "FRIULI-VENEZIA GIULIA":               "Friuli Venezia Giulia",
    "FRIULI VENEZIA GIULIA":               "Friuli Venezia Giulia",
    "FRIULIVENEZIAGIULIA":                 "Friuli Venezia Giulia",   # PDF senza spazi
    "FRIULI V.G.":                         "Friuli Venezia Giulia",
    "FRIULI V.G":                          "Friuli Venezia Giulia",
    "LAZIO":                               "Lazio",
    "LIGURIA":                             "Liguria",
    "LOMBARDIA":                           "Lombardia",
    "MARCHE":                              "Marche",
    "MOLISE":                              "Molise",
    "PIEMONTE":                            "Piemonte",
    "PUGLIA":                              "Puglia",
    "SARDEGNA":                            "Sardegna",
    "SICILIA":                             "Sicilia",
    "TOSCANA":                             "Toscana",
    "UMBRIA":                              "Umbria",
    "VALLE D'AOSTA":                       "Valle d'Aosta",
    "VALLE D'AOSTA/VALLEE D'AOSTE":        "Valle d'Aosta",
    "VALLED'AOSTA":                        "Valle d'Aosta",   # PDF "Valled ' Aosta" compact
    "VENETO":                              "Veneto",
    # Province autonome / TAA → raggruppate nella regione ufficiale
    "TRENTO":                              "Trentino-Alto Adige",
    "BOLZANO":                             "Trentino-Alto Adige",
    "TRENTINO-ALTO ADIGE":                 "Trentino-Alto Adige",
    "TRENTINO ALTO ADIGE":                 "Trentino-Alto Adige",
    "TRENTINO ALTO ADIGE (BOLZANO)":       "Trentino-Alto Adige",
    "TRENTINO ALTO ADIGE (TRENTO)":        "Trentino-Alto Adige",
    "TRENTINO-ALTO ADIGE (BOLZANO)":       "Trentino-Alto Adige",
    "TRENTINO-ALTO ADIGE (TRENTO)":        "Trentino-Alto Adige",
    "TAA BOLZANO":                         "Trentino-Alto Adige",
    "TAA TRENTO":                          "Trentino-Alto Adige",
    "PROVINCIA AUTONOMA DI TRENTO":        "Trentino-Alto Adige",
    "PROVINCIA AUTONOMA DI BOLZANO":       "Trentino-Alto Adige",
    "PROVINCIA AUTONOMA TRENTO":           "Trentino-Alto Adige",
    "PROVINCIA AUTONOMA BOLZANO":          "Trentino-Alto Adige",
    "ALTO ADIGE":                          "Trentino-Alto Adige",
    "P.A. TRENTO":                         "Trentino-Alto Adige",
    "P.A. BOLZANO":                        "Trentino-Alto Adige",
}


def normalize_regione(val) -> str:
    """Normalizza il nome regione al formato display standard.

    Strategie applicate in ordine:
    1. Rimuove trattini/dash iniziali non-standard (artefatti PDF: "‐ Calabria").
    2. Lookup esatto nella mappa (chiave uppercase).
    3. Lookup compatto: rimuove tutti gli spazi interni e riprova.
       Cattura varianti split da PDF ("Emiliaromag Na", "Friuliveneziag Iulia", …).
    4. Fallback: title-case del valore ripulito.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    # Rimuovi trattini/dash iniziali (standard U+002D e non-standard U+2010‥U+2015)
    s = re.sub(r'^[\-\u2010-\u2015\s]+', '', s).strip()
    key = s.upper()
    if key in ("", "NAN", "NONE"):
        return ""
    # 1. Lookup esatto
    result = _REGIONE_NORM_MAP.get(key)
    if result:
        return result
    # 2. Lookup compatto (rimuove spazi: cattura split da estrazione PDF)
    result = _REGIONE_NORM_MAP.get(key.replace(" ", ""))
    if result:
        return result
    # 3. Fallback title-case
    return s.title()


# ============================================================================
# UTILITY: NORMALIZZAZIONE NOMI COLONNA
# ============================================================================

# Valori provincia da trattare come "non disponibile" → stringa vuota
_PROV_NULL_VALUES = {"N/D", "ND", "RIF", "N.D.", "//", "/", "-", "NA", "XX", "?", "???"}


def normalize_provincia(raw: str) -> str:
    """
    Normalizza la sigla provincia:
    - Uppercase, strip spazi interni
    - Valori non validi (N/D, RIF, ecc.) → stringa vuota
    - Lunghezza > 2 → prende le prime 2 lettere se sono tutte alpha, altrimenti vuoto
    - Risultato finale: 2 caratteri alpha oppure stringa vuota
    """
    v = str(raw).strip().upper()
    v = re.sub(r"\s+", "", v)          # "M I" → "MI"
    if v in ("", "NAN", "NONE"):
        return ""
    if v in _PROV_NULL_VALUES:
        return ""
    if len(v) > 2:
        candidate = v[:2]
        return candidate if candidate.isalpha() else ""
    return v if v.isalpha() else ""


def ncol(col: str) -> str:
    """
    Normalizza il nome di una colonna:
    rimuove soft-hyphens (\xad) e lo spazio che li segue (sono word-break hints
    in tabelle PDF/Excel bilingui), poi collassa trattini e spazi; lowercase.

    Esempi:
      "Volon\xad tariato"          -> "volontariato"
      "Volo\xad ntari\xad ato"     -> "volontariato"
      "Ricerca scient\xad ifica"   -> "ricerca scientifica"
      "Beni cultu\xad rali..."     -> "beni culturali..."
    """
    s = str(col)
    s = re.sub(r"\xad\s*", "", s)    # soft-hyphen + spazio seguente → niente
    s = re.sub(r"[\-\s]+", " ", s)   # trattini e spazi → spazio singolo
    return s.strip().lower()


def build_col_index(df: pd.DataFrame) -> dict[str, str]:
    """Restituisce {ncol(colonna): colonna_originale} per un DataFrame."""
    return {ncol(c): c for c in df.columns}


# ============================================================================
# UTILITY: PARSING NUMERI ITALIANI
# ============================================================================

def parse_importo(val) -> float | None:
    """
    Converte un importo in formato italiano ("1.234.567,89") in float.
    Restituisce None se il valore è vuoto o non parsabile.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if s in ("", "-", "NaN", "nan"):
        return None
    # Rimuovi simboli di valuta e spazi
    s = re.sub(r"[€\s]", "", s)
    # Formato italiano: punti come separatore migliaia, virgola come decimale
    # Rimuovi i punti di migliaia, sostituisci virgola con punto
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_intero(val) -> int | None:
    """Converte numero scelte (può avere punti/virgole/spazi come migliaia)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    # Rimuovi spazi interni prima di togliere i separatori di migliaia
    # es. "3 46.183" → "346183"
    s = str(val).strip().replace(" ", "").replace(".", "").replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return None


# ============================================================================
# UTILITY: NORMALIZZAZIONE CODICE FISCALE
# ============================================================================

def normalize_cf(val) -> str:
    """
    Normalizza il codice fiscale:
    - Rimuovi apici/virgolette (artefatto CSV per forzare testo)
    - Strip spazi e uppercase
    - Se numerico, padding a 11 cifre con zero a sinistra
    - Mantiene i CF alfanumerici (persone fisiche) com'è
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip().upper()
    # Rimuovi apici e virgolette (es. "'01234567890'" da CSV)
    s = s.strip("'\"")
    # Rimuovi ".0" finale (da Excel che legge come float)
    s = re.sub(r"\.0+$", "", s)
    # Se è puramente numerico, padda a 11 cifre
    if re.fullmatch(r"\d+", s):
        s = s.zfill(11)
    return s


# ============================================================================
# UTILITY: RILEVAZIONE FLAG CATEGORIA
# ============================================================================

def is_flag(val) -> bool:
    """
    True se il valore indica una presenza (X, x, SI, sì, ecc.).
    False per NaN, None, stringa vuota, '-'.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().lower()
    return s in ("x", "si", "sì", "yes", "y", "1", "true", "•", "*")


def col_to_bool_series(df: pd.DataFrame, col_orig: str | None) -> pd.Series:
    """Restituisce una Series booleana da una colonna flag (o tutti False se None)."""
    if col_orig is None or col_orig not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col_orig].apply(is_flag)


# ============================================================================
# LOGICA DI NORMALIZZAZIONE PER ANNO
# ============================================================================

# Mappa dal nome normalizzato al campo target.
# Il match usa ncol() sia sulla chiave che sul nome colonna effettivo.

# Campi identità (stesso in tutti gli anni, nomi diversi)
CF_ALIASES = {"codice fiscale", "cf"}
DENOM_ALIASES = {"denominazione", "beneficiario"}
REGIONE_ALIASES = {"regione"}
PROV_ALIASES = {"provincia", "prov", "pr"}
COMUNE_ALIASES = {"comune"}

# Campi categoria (flag)
CAT_VOL_ALIASES = {
    "categoria volontariato / asd",   # 2006-2007 (combinato)
    "categoria volontariato/ asd",    # variante 2007
    "categoria volontariato",         # 2008-2016
    "volontariato",                   # 2017-2021
}
CAT_ETS_ALIASES = {"ets e onlus"}     # 2022-2024 (sostituisce volontariato)
CAT_ASD_ALIASES = {"asd"}
CAT_SCI_ALIASES = {"ricerca scientifica", "ricerca scient ifica"}
CAT_SAN_ALIASES = {"ricerca sanitaria", "ricerca sanit aria"}
CAT_COM_ALIASES = {"comuni", "com uni"}
CAT_BENI_ALIASES = {
    "mibac", "mibac (1)",
    "beni culturali e paesa ggistici",
    "beni cultu rali e paes aggis tici",
    "beni culturali e paesaggistici",
}
CAT_AREE_ALIASES = {
    "enti gestori aree protette",
    "enti gestori aree prote tte",
}

# Campi numerici
# Gli anni più vecchi usano nomi colonna diversi per il numero di scelte:
#   "N. Scelte" → ncol → "n. scelte"
#   "N Scelte"  → "n scelte"
#   "Preferenze" → "preferenze"
N_SCELTE_ALIASES = {
    "numero scelte",
    "n. scelte",
    "n scelte",
    "numero di scelte",
    "preferenze",
    "n preferenze",
    "numero preferenze",
}
IMP_ESP_ALIASES = {
    "importo (euro) per scelte espresse",
    "importo (euro) importo delle scelte espresse",
    "importo delle scelte espresse",
}
IMP_GEN_ALIASES = {
    "per scelte generiche",
    "importo proporzionale per le scelte generiche",
}
IMP_RIP_ALIASES = {
    # AdE ha varianti leggermente diverse per anno
    "importo proporzionale per ripartizione importi inferiori a 100 euro",
    "importo proporzionale per ripartizione importi inferiori a euro 100",
    "importo proporzionale per ripartizione",
    "importo per ripartizione importi inferiori a 100 euro",
    "importo per ripartizione",
    "importo ripartizione",
    "ripartizione importi inferiori",
}
IMP_TOT_ALIASES = {
    "importo totale",
    "totale",
    "importo totale erogabile",
}


def find_col(col_index: dict, aliases: set) -> str | None:
    """
    Cerca il nome originale della colonna nel col_index usando le aliases.
    Restituisce il nome originale o None.
    Usa match esatto sul nome normalizzato.
    """
    for alias in aliases:
        if alias in col_index:
            return col_index[alias]
    return None


def find_col_partial(col_index: dict, aliases: set) -> str | None:
    """
    Come find_col ma cerca anche corrispondenza parziale
    (il nome normalizzato *contiene* l'alias).
    Utile per varianti con spazi extra da soft-hyphens.
    """
    # Prima prova match esatto
    result = find_col(col_index, aliases)
    if result:
        return result
    # Poi prova match parziale
    for alias in aliases:
        for norm_name, orig_name in col_index.items():
            if alias in norm_name or norm_name in alias:
                return orig_name
    return None


def normalize_year(df: pd.DataFrame, anno: int) -> pd.DataFrame:
    """
    Normalizza un DataFrame annuale nello schema unificato.
    Restituisce un DataFrame con le colonne standard.
    """
    ci = build_col_index(df)

    # --- Colonne identità ---
    cf_col = find_col(ci, CF_ALIASES)
    denom_col = find_col(ci, DENOM_ALIASES)
    reg_col = find_col(ci, REGIONE_ALIASES)
    prov_col = find_col(ci, PROV_ALIASES)
    comune_col = find_col(ci, COMUNE_ALIASES)

    # --- Colonne categoria ---
    # Nota: 2022-2024 usano ETS e ONLUS al posto di Volontariato
    cat_ets_col = find_col(ci, CAT_ETS_ALIASES)
    cat_vol_col = find_col(ci, CAT_VOL_ALIASES) if cat_ets_col is None else None
    cat_asd_col = find_col(ci, CAT_ASD_ALIASES)
    cat_sci_col = find_col_partial(ci, CAT_SCI_ALIASES)
    cat_san_col = find_col_partial(ci, CAT_SAN_ALIASES)
    cat_com_col = find_col_partial(ci, CAT_COM_ALIASES)
    cat_beni_col = find_col_partial(ci, CAT_BENI_ALIASES)
    cat_aree_col = find_col_partial(ci, CAT_AREE_ALIASES)

    # --- Colonne numeriche ---
    n_scelte_col = find_col_partial(ci, N_SCELTE_ALIASES)
    imp_esp_col  = find_col_partial(ci, IMP_ESP_ALIASES)
    imp_gen_col  = find_col_partial(ci, IMP_GEN_ALIASES)
    imp_rip_col  = find_col_partial(ci, IMP_RIP_ALIASES)
    imp_tot_col  = find_col_partial(ci, IMP_TOT_ALIASES)

    # Warn se colonne critiche mancano
    if cf_col is None:
        logging.warning(f"  [{anno}] Colonna CODICE FISCALE non trovata! Colonne: {list(df.columns)}")
    if imp_tot_col is None:
        logging.warning(f"  [{anno}] Colonna IMPORTO TOTALE non trovata")

    # --- Costruzione DataFrame normalizzato ---
    out = pd.DataFrame(index=df.index)

    out["ANNO"] = anno

    out["COD_FISCALE"] = (
        df[cf_col].apply(normalize_cf) if cf_col else ""
    )
    out["DENOMINAZIONE"] = (
        df[denom_col].astype(str).str.strip() if denom_col else ""
    )
    out["REGIONE"] = (
        df[reg_col].astype(str).str.strip().apply(normalize_regione) if reg_col else ""
    )
    out["PROVINCIA"] = (
        df[prov_col].astype(str).apply(normalize_provincia)
        if prov_col else ""
    )
    out["COMUNE"] = (
        df[comune_col].astype(str).str.strip().str.upper() if comune_col else ""
    )

    # Categorie booleane
    # In 2006-2007 il campo vol/asd è combinato: lo mettiamo in entrambi
    if cat_ets_col:
        # 2022+: ETS e ONLUS → sia CAT_ETS_ONLUS che CAT_VOLONTARIATO
        ets_series = col_to_bool_series(df, cat_ets_col)
        out["CAT_VOLONTARIATO"] = ets_series
        out["CAT_ETS_ONLUS"] = ets_series
    elif cat_vol_col:
        vol_series = col_to_bool_series(df, cat_vol_col)
        # Se la colonna è quella combinata VOL/ASD (2006-2007)
        col_norm = ncol(cat_vol_col)
        if "asd" in col_norm:
            out["CAT_VOLONTARIATO"] = vol_series
            out["CAT_ASD"] = pd.Series(False, index=df.index)  # non distinguibile
        else:
            out["CAT_VOLONTARIATO"] = vol_series
        out["CAT_ETS_ONLUS"] = pd.Series(False, index=df.index)
    else:
        out["CAT_VOLONTARIATO"] = pd.Series(False, index=df.index)
        out["CAT_ETS_ONLUS"] = pd.Series(False, index=df.index)

    if "CAT_ASD" not in out.columns:
        out["CAT_ASD"] = col_to_bool_series(df, cat_asd_col)

    out["CAT_RICERCA_SCI"] = col_to_bool_series(df, cat_sci_col)
    out["CAT_RICERCA_SAN"] = col_to_bool_series(df, cat_san_col)
    out["CAT_COMUNI"] = col_to_bool_series(df, cat_com_col)
    out["CAT_BENI_CULT"] = col_to_bool_series(df, cat_beni_col)
    out["CAT_AREE_PROT"] = col_to_bool_series(df, cat_aree_col)

    # Categoria principale (priorità: ricerca > comuni > beni > aree > asd > ets > vol)
    def get_cat_principale(row) -> str:
        if row["CAT_RICERCA_SCI"]:
            return "Ricerca scientifica"
        if row["CAT_RICERCA_SAN"]:
            return "Ricerca sanitaria"
        if row["CAT_COMUNI"]:
            return "Comuni"
        if row["CAT_BENI_CULT"]:
            return "Beni culturali"
        if row["CAT_AREE_PROT"]:
            return "Enti gestori aree protette"
        if row["CAT_ASD"]:
            return "ASD"
        if row["CAT_ETS_ONLUS"] or row["CAT_VOLONTARIATO"]:
            # ETS/ONLUS (2022+) e Volontariato (pre-2022) sono la stessa categoria
            # con nome cambiato per legge: usiamo un'unica label storica unificata
            return "Volontariato / ETS"
        return "Non specificata"

    cat_cols = ["CAT_RICERCA_SCI", "CAT_RICERCA_SAN", "CAT_COMUNI",
                "CAT_BENI_CULT", "CAT_AREE_PROT", "CAT_ASD",
                "CAT_ETS_ONLUS", "CAT_VOLONTARIATO"]
    out["CATEGORIA_PRINCIPALE"] = out[cat_cols].apply(get_cat_principale, axis=1)

    # Numerici
    out["N_SCELTE"] = (
        df[n_scelte_col].apply(parse_intero) if n_scelte_col else None
    )
    out["IMPORTO_ESPRESSO"] = (
        df[imp_esp_col].apply(parse_importo) if imp_esp_col else None
    )
    out["IMPORTO_GENERICO"] = (
        df[imp_gen_col].apply(parse_importo) if imp_gen_col else None
    )
    out["IMPORTO_RIPARTIZIONE"] = (
        df[imp_rip_col].apply(parse_importo) if imp_rip_col else None
    )
    out["IMPORTO_TOTALE"] = (
        df[imp_tot_col].apply(parse_importo) if imp_tot_col else None
    )

    return out


# ============================================================================
# LOAD DATI 5x1000
# ============================================================================

def process_streaming(
    dati_dir: Path,
    out_csv: Path,
    df_runts: "pd.DataFrame | None",
    anni_filter: "list[int] | None" = None,
    on_anno_done: "callable | None" = None,
    append: bool = False,
) -> dict:
    """
    Processa i file anno per anno in modalità streaming (dal più recente al più vecchio):
    normalizza ogni anno, fa il join RUNTS, e scrive nel CSV riga per riga.
    Questo evita di tenere tutto il dataset in RAM simultaneamente.

    on_anno_done(anno, df_norm): callback opzionale chiamato dopo ogni anno.
    append=True: se il CSV esiste già, scrive in append senza header (usato con --replace).
    Restituisce statistiche aggregate.
    """
    files = sorted(dati_dir.glob("dati_[0-9][0-9][0-9][0-9].xlsx"), reverse=True)
    if not files:
        logging.error(f"Nessun file dati_XXXX.xlsx trovato in {dati_dir}")
        sys.exit(1)

    stats = {
        "total_rows": 0,
        "anni": [],
        "cat_counts": {},
        "importo_per_anno": {},
        "runts_matches": 0,
    }

    # append=True (usato con --replace): il CSV esiste già con gli altri anni,
    # si fa append senza header. Altrimenti si ricrea da zero.
    first_write = not (append and out_csv.exists())

    for f in files:
        anno = int(f.stem.split("_")[1])
        if anni_filter and anno not in anni_filter:
            continue

        logging.info(f"[{anno}] Carico {f.name}...")
        try:
            df_raw = pd.read_excel(f, dtype=str)
            df_raw = df_raw.dropna(how="all")
            df_norm = normalize_year(df_raw, anno)

            before = len(df_norm)
            df_norm = df_norm[df_norm["COD_FISCALE"].str.len() > 0]
            dropped = before - len(df_norm)
            if dropped:
                logging.info(f"  [{anno}] Rimosse {dropped} righe senza CF")

            # Merge RUNTS (left join)
            if df_runts is not None:
                df_norm = df_norm.merge(df_runts, on="COD_FISCALE", how="left")
                matches = df_norm["RUNTS_SEZIONE"].notna().sum() if "RUNTS_SEZIONE" in df_norm.columns else 0
                stats["runts_matches"] += int(matches)

            # Scrivi nel CSV (append)
            mode = "w" if first_write else "a"
            header = first_write
            df_norm.to_csv(out_csv, mode=mode, header=header, index=False, encoding="utf-8-sig")
            first_write = False

            # Aggiorna stats
            n = len(df_norm)
            stats["total_rows"] += n
            stats["anni"].append(anno)

            for cat, cnt in df_norm["CATEGORIA_PRINCIPALE"].value_counts().items():
                stats["cat_counts"][cat] = stats["cat_counts"].get(cat, 0) + int(cnt)

            imp_sum = df_norm["IMPORTO_TOTALE"].sum()
            stats["importo_per_anno"][anno] = float(imp_sum) if pd.notna(imp_sum) else 0.0

            logging.info(f"  [{anno}] {n:,} righe -> CSV")

            # Callback per-anno (es. aggiornamento DB immediato)
            if on_anno_done is not None:
                try:
                    on_anno_done(anno, df_norm)
                except Exception as cb_exc:
                    logging.warning(f"  [{anno}] on_anno_done callback errore: {cb_exc}")

        except Exception as e:
            logging.error(f"  [{anno}] ERRORE: {e}")
            import traceback
            logging.debug(traceback.format_exc())

    return stats


def load_all_years(dati_dir: Path) -> "pd.DataFrame":
    """
    Carica TUTTI gli anni in un unico DataFrame (uso interno/test).
    Per grandi dataset usa process_streaming() invece.
    """
    import pandas as pd
    files = sorted(dati_dir.glob("dati_[0-9][0-9][0-9][0-9].xlsx"), reverse=True)
    frames = []
    for f in files:
        anno = int(f.stem.split("_")[1])
        logging.info(f"[{anno}] Carico {f.name}...")
        df_raw = pd.read_excel(f, dtype=str).dropna(how="all")
        df_norm = normalize_year(df_raw, anno)
        df_norm = df_norm[df_norm["COD_FISCALE"].str.len() > 0]
        logging.info(f"  {len(df_norm):,} righe")
        frames.append(df_norm)
    return pd.concat(frames, ignore_index=True)


# ============================================================================
# LOAD RUNTS
# ============================================================================

def load_runts(runts_dir: Path) -> pd.DataFrame | None:
    """
    Cerca un file RUNTS nella cartella e lo normalizza.
    Il file ha nomi colonna con _x000D_\\n (artifacts da Excel bilinguismo IT/DE).
    """
    files = sorted(runts_dir.glob("*.xlsx")) if runts_dir.is_dir() else []
    if not files:
        logging.warning(f"Nessun file RUNTS trovato in {runts_dir}")
        return None

    # Prende il più recente
    runts_file = files[-1]
    logging.info(f"[RUNTS] Carico {runts_file.name}...")

    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Workbook contains no default style", UserWarning)
        df = pd.read_excel(runts_file, dtype=str)
    logging.info(f"[RUNTS] {len(df):,} righe, {len(df.columns)} colonne")

    # Pulisce i nomi colonna (rimuove _x000D_\n e testo dopo \n)
    def clean_runts_col(col: str) -> str:
        col = col.replace("_x000D_", "").replace("\r", "")
        col = col.split("\n")[0].strip()
        return col

    df.columns = [clean_runts_col(c) for c in df.columns]
    logging.info(f"[RUNTS] Colonne: {list(df.columns)}")

    # Normalizza il CF
    cf_col = next((c for c in df.columns if "codice fiscale" in c.lower()), None)
    if not cf_col:
        logging.warning("[RUNTS] Colonna CF non trovata")
        return None

    df["COD_FISCALE"] = df[cf_col].apply(normalize_cf)

    # Rinomina colonne chiave
    rename_map: dict[str, str] = {}
    for col in df.columns:
        cn = col.lower()
        if "sezione" in cn:
            rename_map[col] = "RUNTS_SEZIONE"
        elif "comune sede" in cn:
            rename_map[col] = "RUNTS_SEDE_COMUNE"
        elif "provincia sede" in cn:
            rename_map[col] = "RUNTS_SEDE_PROV"
        elif cn in ("5x", "5x1000") or ("5x" in cn and "1000" in cn):
            rename_map[col] = "RUNTS_5X1000"
        elif "data iscrizione" in cn:
            rename_map[col] = "RUNTS_DATA_ISCRIZIONE"
        elif "denominazione" in cn:
            rename_map[col] = "RUNTS_DENOMINAZIONE"

    df = df.rename(columns=rename_map)

    # Seleziona solo le colonne utili
    keep = ["COD_FISCALE"] + [c for c in df.columns if c.startswith("RUNTS_")]
    df = df[[c for c in keep if c in df.columns]].copy()

    # Normalizza RUNTS_SEDE_PROV come le province AdE
    if "RUNTS_SEDE_PROV" in df.columns:
        df["RUNTS_SEDE_PROV"] = df["RUNTS_SEDE_PROV"].apply(normalize_provincia)

    # Normalizza RUNTS_5X1000 in booleano leggibile
    if "RUNTS_5X1000" in df.columns:
        df["RUNTS_5X1000"] = df["RUNTS_5X1000"].apply(
            lambda v: True if str(v).strip().lower() in ("si", "sì", "yes", "1", "true") else False
        )

    # Deduplica: tieni il più recente per CF (ordina per data iscrizione)
    if "RUNTS_DATA_ISCRIZIONE" in df.columns:
        df = df.sort_values("RUNTS_DATA_ISCRIZIONE", ascending=False)

    df = df.drop_duplicates(subset=["COD_FISCALE"], keep="first")
    logging.info(f"[RUNTS] {len(df):,} enti unici dopo deduplicazione")
    return df


# ============================================================================
# MERGE
# ============================================================================

def merge_runts(df_5x: pd.DataFrame, df_runts: pd.DataFrame) -> pd.DataFrame:
    """Left join tra dati 5x1000 e RUNTS su COD_FISCALE."""
    df = df_5x.merge(df_runts, on="COD_FISCALE", how="left")
    matched = df["RUNTS_SEZIONE"].notna().sum() if "RUNTS_SEZIONE" in df.columns else 0
    total = len(df_5x)
    logging.info(f"[MERGE] {matched:,}/{total:,} righe con match RUNTS ({100*matched/total:.1f}%)")
    return df


# ============================================================================
# EXPORT CSV
# ============================================================================

def export_csv(df: pd.DataFrame, out_path: Path) -> None:
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    size_mb = out_path.stat().st_size / 1_048_576
    logging.info(f"CSV salvato: {out_path} ({size_mb:.1f} MB, {len(df):,} righe)")


def strip_anni_from_csv(csv_path: Path, anni: "list[int]") -> int:
    """
    Rimuove dal CSV esistente tutte le righe degli anni indicati,
    riscrivendo il file in streaming (chunk per chunk) per contenere l'uso RAM.
    Restituisce il numero di righe rimosse.
    Operazione no-op se il file non esiste.
    """
    if not csv_path.exists():
        return 0

    anni_str = {str(a) for a in anni}
    tmp_path = csv_path.with_suffix(".tmp")
    removed = 0

    try:
        reader = pd.read_csv(csv_path, dtype=str, chunksize=ETL_CONFIG["chunk_size"],
                             encoding="utf-8-sig", on_bad_lines="warn")
        first = True
        for chunk in reader:
            mask = ~chunk["ANNO"].isin(anni_str)
            removed += (~mask).sum()
            chunk[mask].to_csv(tmp_path, mode="w" if first else "a",
                               header=first, index=False, encoding="utf-8-sig")
            first = False

        # Se il file era vuoto o tutte le righe erano degli anni rimossi,
        # tmp_path potrebbe non essere stato creato.
        if tmp_path.exists():
            tmp_path.replace(csv_path)
        else:
            csv_path.unlink()
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    logging.info(f"[replace] Rimosse {removed:,} righe per anni {anni} dal CSV esistente.")
    return removed


# ============================================================================
# EXPORT EXCEL (formattato, xlsxwriter)
# ============================================================================

def _xlsxwriter_formats(wb):
    """Crea e restituisce i formati riutilizzabili per xlsxwriter."""
    ec = EXCEL_CONFIG
    header_fmt = wb.add_format({
        "font_name": ec["header_font"], "bold": True, "font_size": ec["header_size"],
        "font_color": ec["header_fg"], "bg_color": ec["header_bg"],
        "align": "center", "valign": "vcenter", "text_wrap": True,
        "border": 1, "border_color": ec["border_color"],
    })
    data_fmt = wb.add_format({
        "font_name": ec["data_font"], "font_size": ec["data_size"],
        "border": 1, "border_color": ec["border_color"],
    })
    data_alt_fmt = wb.add_format({
        "font_name": ec["data_font"], "font_size": ec["data_size"],
        "bg_color": ec["alt_row_bg"],
        "border": 1, "border_color": ec["border_color"],
    })
    return header_fmt, data_fmt, data_alt_fmt


def _compute_col_widths(cols: list[str], sample: pd.DataFrame) -> list[int]:
    """Calcola la larghezza delle colonne da un campione di dati."""
    max_width = EXCEL_CONFIG.get("max_col_width", 40)
    widths = []
    for col in cols:
        max_len = len(col)
        if col in sample.columns:
            vals = sample[col].dropna().astype(str)
            if len(vals) > 0:
                max_len = max(max_len, int(vals.str.len().max()))
        widths.append(min(max_len + 2, max_width))
    return widths


def _setup_xlsxwriter_sheet(wb, ws, cols, col_widths, header_fmt):
    """Scrive header, imposta larghezze colonne su un foglio xlsxwriter."""
    for ci, width in enumerate(col_widths):
        ws.set_column(ci, ci, width)
    for ci, col_name in enumerate(cols):
        ws.write(0, ci, col_name, header_fmt)


def _finalize_xlsxwriter_sheet(ws, n_data_rows: int, n_cols: int):
    """Applica freeze panes e autofilter a un foglio completato."""
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, n_data_rows, n_cols - 1)


def export_excel(df: pd.DataFrame, out_path: Path) -> None:
    """
    Crea un Excel formattato con xlsxwriter da un DataFrame in memoria.
    Se il dataset supera il limite Excel di 1.048.575 righe dati,
    lo divide automaticamente in piu' fogli.
    """
    import xlsxwriter

    EXCEL_MAX_DATA_ROWS = 1_048_575

    cols = list(df.columns)
    n_cols = len(cols)
    total_rows = len(df)
    n_sheets = math.ceil(total_rows / EXCEL_MAX_DATA_ROWS) if total_rows > 0 else 1

    if n_sheets > 1:
        logging.info(
            f"  Dataset ({total_rows:,} righe) supera il limite Excel "
            f"({EXCEL_MAX_DATA_ROWS:,}) -> {n_sheets} fogli"
        )

    col_widths = _compute_col_widths(cols, df.head(200))

    wb = xlsxwriter.Workbook(str(out_path), {"constant_memory": True})
    header_fmt, data_fmt, data_alt_fmt = _xlsxwriter_formats(wb)

    for sheet_idx in range(n_sheets):
        start = sheet_idx * EXCEL_MAX_DATA_ROWS
        end = min(start + EXCEL_MAX_DATA_ROWS, total_rows)
        df_chunk = df.iloc[start:end]

        sheet_name = "5x1000_norm" if n_sheets == 1 else f"Parte_{sheet_idx + 1}"
        ws = wb.add_worksheet(sheet_name)
        _setup_xlsxwriter_sheet(wb, ws, cols, col_widths, header_fmt)

        values = df_chunk.values
        for ri in range(len(values)):
            fmt = data_alt_fmt if (ri % 2 == 0) else data_fmt
            for ci in range(n_cols):
                val = values[ri][ci]
                if pd.isna(val):
                    ws.write_blank(ri + 1, ci, None, fmt)
                else:
                    ws.write(ri + 1, ci, val, fmt)

        _finalize_xlsxwriter_sheet(ws, len(df_chunk), n_cols)
        logging.info(f"  Foglio '{sheet_name}': {len(df_chunk):,} righe")

    wb.close()
    size_mb = out_path.stat().st_size / 1_048_576
    logging.info(f"Excel salvato: {out_path} ({size_mb:.1f} MB, {n_sheets} foglio/i)")


def export_excel_from_csv(csv_path: Path, out_path: Path) -> None:
    """
    Crea un Excel formattato leggendo il CSV in streaming (senza caricare
    tutto in RAM). Usa xlsxwriter in constant_memory mode.
    Supporta multi-sheet per dataset che superano il limite Excel.
    """
    import xlsxwriter

    EXCEL_MAX_DATA_ROWS = 1_048_575
    CHUNK_SIZE = ETL_CONFIG.get("chunk_size", 50_000)

    # --- Prima passata: colonne e larghezze ---
    sample = pd.read_csv(csv_path, dtype=str, nrows=200, on_bad_lines="warn")
    cols = list(sample.columns)
    n_cols = len(cols)
    col_widths = _compute_col_widths(cols, sample)

    # Conta le righe totali per pianificare i fogli
    with open(csv_path, encoding="utf-8-sig") as f:
        total_rows = sum(1 for _ in f) - 1  # -1 per l'header

    n_sheets = math.ceil(total_rows / EXCEL_MAX_DATA_ROWS) if total_rows > 0 else 1
    if n_sheets > 1:
        logging.info(
            f"  Dataset ({total_rows:,} righe) supera il limite Excel "
            f"({EXCEL_MAX_DATA_ROWS:,}) -> {n_sheets} fogli"
        )

    # --- Crea workbook ---
    wb = xlsxwriter.Workbook(str(out_path), {"constant_memory": True})
    header_fmt, data_fmt, data_alt_fmt = _xlsxwriter_formats(wb)

    sheet_idx = 0
    sheet_row = 0  # riga dati corrente nel foglio (0-based)
    ws = None

    def start_new_sheet():
        nonlocal ws, sheet_idx, sheet_row
        name = "5x1000_norm" if n_sheets == 1 else f"Parte_{sheet_idx + 1}"
        ws = wb.add_worksheet(name)
        _setup_xlsxwriter_sheet(wb, ws, cols, col_widths, header_fmt)
        sheet_row = 0

    start_new_sheet()

    # --- Seconda passata: scrivi dati in streaming ---
    reader = pd.read_csv(csv_path, dtype=str, chunksize=CHUNK_SIZE, on_bad_lines="warn")

    for chunk in reader:
        values = chunk.values
        for ri in range(len(values)):
            # Nuovo foglio se necessario
            if sheet_row >= EXCEL_MAX_DATA_ROWS:
                _finalize_xlsxwriter_sheet(ws, sheet_row, n_cols)
                logging.info(f"  Foglio completato: {sheet_row:,} righe")
                sheet_idx += 1
                start_new_sheet()

            fmt = data_alt_fmt if (sheet_row % 2 == 0) else data_fmt
            excel_row = sheet_row + 1  # +1 per l'header

            for ci in range(n_cols):
                val = values[ri][ci]
                if pd.isna(val):
                    ws.write_blank(excel_row, ci, None, fmt)
                else:
                    ws.write(excel_row, ci, val, fmt)

            sheet_row += 1

    # Finalizza ultimo foglio
    if ws is not None:
        _finalize_xlsxwriter_sheet(ws, sheet_row, n_cols)
        logging.info(f"  Foglio completato: {sheet_row:,} righe")

    wb.close()
    size_mb = out_path.stat().st_size / 1_048_576
    logging.info(f"Excel salvato: {out_path} ({size_mb:.1f} MB, {sheet_idx + 1} foglio/i)")


# ============================================================================
# STATS DI RIEPILOGO
# ============================================================================

def print_stats(df: pd.DataFrame) -> None:
    """Stampa alcune statistiche rapide sul dataset normalizzato."""
    logging.info("\n" + "=" * 60)
    logging.info("RIEPILOGO DATASET NORMALIZZATO")
    logging.info("=" * 60)
    logging.info(f"  Righe totali:    {len(df):,}")
    logging.info(f"  Anni coperti:    {sorted(df['ANNO'].unique())}")
    logging.info(f"  Enti unici (CF): {df['COD_FISCALE'].nunique():,}")
    logging.info(f"  Enti unici (nome): {df['DENOMINAZIONE'].nunique():,}")

    logging.info("\n  Distribuzione per CATEGORIA_PRINCIPALE:")
    cat_counts = df["CATEGORIA_PRINCIPALE"].value_counts()
    for cat, cnt in cat_counts.items():
        logging.info(f"    {cat:<35} {cnt:>8,}")

    if "IMPORTO_TOTALE" in df.columns:
        totale_per_anno = df.groupby("ANNO")["IMPORTO_TOTALE"].sum()
        logging.info("\n  Importo totale per anno (€):")
        for anno, tot in totale_per_anno.items():
            logging.info(f"    {anno}: {tot:>18,.2f}")

    if "RUNTS_SEZIONE" in df.columns:
        n_match = df["RUNTS_SEZIONE"].notna().sum()
        logging.info(f"\n  Enti con match RUNTS: {n_match:,} su {len(df):,} righe")

    logging.info("=" * 60)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ETL 5x1000: normalizza e unifica i dati per anno"
    )
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT,
        help=f"Cartella root del progetto (default: {DEFAULT_ROOT})"
    )
    parser.add_argument(
        "--dati", type=Path, default=None,
        help="Cartella con i file dati_XXXX.xlsx (default: ROOT/Dati)"
    )
    parser.add_argument(
        "--runts", type=Path, default=None,
        help="Cartella con il file RUNTS (default: ROOT/Runts)"
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Cartella di output (default: ROOT/Dati)"
    )
    parser.add_argument(
        "--no-runts", action="store_true",
        help="Salta il merge con RUNTS"
    )
    parser.add_argument(
        "--no-excel", action="store_true",
        help="Non genera il file Excel (solo CSV)"
    )
    parser.add_argument(
        "--anni", type=str, default=None,
        help="Anni da processare, separati da virgola (es. 2020,2021,2022)"
    )
    parser.add_argument(
        "--replace", action="store_true",
        help="Prima di scrivere, rimuove dal CSV esistente le righe degli anni "
             "indicati con --anni (utile in modalità ciclo per aggiornare un anno "
             "senza ricostruire tutto il dataset)."
    )
    parser.add_argument(
        "--aggiorna-db", action="store_true",
        help=(
            "Aggiorna il DB del sito dopo ogni anno elaborato "
            "(richiede SITE_DB_* in .env). Ogni anno viene inserito "
            "nel DB non appena il suo ETL è completato."
        ),
    )
    args = parser.parse_args()

    root = args.root

    get_logger("etl", root)  # configura root logger

    # Carica configurazione esterna (se presente)
    cfg = load_config(root)
    _apply_config(cfg)
    if cfg:
        logging.info("Configurazione caricata da config.yaml")

    # Percorsi: CLI > config.yaml > default
    cfg_percorsi = cfg.get("percorsi", {})
    dati_dir = args.dati or (root / cfg_percorsi.get("dati", "Dati"))
    runts_dir = args.runts or (root / cfg_percorsi.get("runts", "Runts"))
    out_dir = args.out or (root / cfg_percorsi.get("dati", "Dati"))
    out_dir.mkdir(exist_ok=True)

    logging.info(f"Root:  {root}")
    logging.info(f"Dati:  {dati_dir}")
    logging.info(f"RUNTS: {runts_dir}")
    logging.info(f"Out:   {out_dir}")

    # --- Carica RUNTS prima (è piccolo) ---
    df_runts = None
    if not args.no_runts:
        df_runts = load_runts(runts_dir)
    else:
        logging.info("Merge RUNTS saltato (--no-runts)")

    # --- Filtro anni ---
    anni_filter = None
    if args.anni:
        anni_filter = [int(a.strip()) for a in args.anni.split(",")]
        logging.info(f"Filtro anni: {anni_filter}")

    # --- Processing streaming: anno per anno → CSV ---
    csv_path = out_dir / "enti_5x1000_norm.csv"
    logging.info(f"Output CSV: {csv_path}")

    # Callback per aggiornamento DB per-anno
    _db_anno_callback = None
    if args.aggiorna_db:
        try:
            import pymysql, os as _os
            _db_cfg = {
                "host":     _os.getenv("SITE_DB_HOST", "localhost"),
                "port":     int(_os.getenv("SITE_DB_PORT", "3306")),
                "user":     _os.getenv("SITE_DB_USER", ""),
                "password": _os.getenv("SITE_DB_PASSWORD", ""),
                "database": _os.getenv("SITE_DB_NAME", ""),
                "charset":  "utf8mb4",
                "autocommit": True,
            }
            if _db_cfg["user"] and _db_cfg["database"]:
                from db_updater import _COL_MAP, _parse_date_ita, _bool_to_int, _BOOL_COLS
                def _make_db_callback(db_cfg, col_map):
                    def _cb(anno: int, df: "pd.DataFrame") -> None:
                        import pymysql as _pm
                        cols_db = list(col_map.values())
                        ph_row  = "(" + ",".join(["%s"] * len(cols_db)) + ")"
                        ins_sql = f"INSERT INTO enti ({','.join(cols_db)}) VALUES {ph_row}"
                        def _to_none(v):
                            if v is None: return None
                            if isinstance(v, float) and v != v: return None
                            return v
                        try:
                            conn = _pm.connect(**db_cfg)
                            with conn:
                                cur = conn.cursor()
                                cur.execute("DELETE FROM enti WHERE anno = %s", (anno,))
                                logging.info(f"  [DB] Anno {anno}: righe precedenti cancellate.")
                                df_ins = df.rename(columns=col_map)
                                for col in cols_db:
                                    if col not in df_ins.columns:
                                        df_ins[col] = None
                                # Converti booleani stringa → 0/1
                                for col in _BOOL_COLS:
                                    if col in df_ins.columns:
                                        df_ins[col] = df_ins[col].apply(_bool_to_int)
                                # Converti date dd/mm/yyyy → yyyy-mm-dd per MySQL
                                if "runts_data_iscrizione" in df_ins.columns:
                                    df_ins["runts_data_iscrizione"] = df_ins["runts_data_iscrizione"].apply(_parse_date_ita)
                                rows = [
                                    tuple(_to_none(row[c]) for c in cols_db)
                                    for _, row in df_ins.iterrows()
                                ]
                                chunk_size = 5_000
                                for i in range(0, len(rows), chunk_size):
                                    cur.executemany(ins_sql, rows[i:i + chunk_size])
                                logging.info(f"  [DB] Anno {anno}: {len(rows):,} righe inserite.")
                        except Exception as exc:
                            logging.warning(f"  [DB] Anno {anno}: errore DB – {exc}")
                    return _cb
                _db_anno_callback = _make_db_callback(_db_cfg, _COL_MAP)
                logging.info("Aggiornamento DB per-anno: attivo.")
            else:
                logging.warning("--aggiorna-db: SITE_DB_USER / SITE_DB_NAME non configurati – saltato.")
        except ImportError as _ie:
            logging.warning(f"--aggiorna-db: dipendenza mancante ({_ie}) – saltato.")

    replace_mode = getattr(args, "replace", False)
    if replace_mode:
        if not anni_filter:
            logging.error("--replace richiede --anni: specifica gli anni da sostituire.")
            sys.exit(1)
        strip_anni_from_csv(csv_path, anni_filter)

    stats = process_streaming(dati_dir, csv_path, df_runts, anni_filter, _db_anno_callback,
                              append=replace_mode)

    # --- Stats riassuntive ---
    logging.info("\n" + "=" * 60)
    logging.info("RIEPILOGO ETL")
    logging.info("=" * 60)
    logging.info(f"  Righe totali:    {stats['total_rows']:,}")
    logging.info(f"  Anni coperti:    {stats['anni']}")
    logging.info(f"  Match RUNTS:     {stats['runts_matches']:,}")
    logging.info("\n  Categorie:")
    for cat, cnt in sorted(stats["cat_counts"].items(), key=lambda x: -x[1]):
        logging.info(f"    {cat:<35} {cnt:>8,}")
    logging.info("\n  Importo per anno (€):")
    for anno in sorted(stats["importo_per_anno"]):
        logging.info(f"    {anno}: {stats['importo_per_anno'][anno]:>18,.2f}")

    size_mb = csv_path.stat().st_size / 1_048_576 if csv_path.exists() else 0
    logging.info(f"\nCSV: {csv_path} ({size_mb:.1f} MB)")

    if not args.no_excel:
        logging.info("Generazione Excel dal CSV normalizzato...")
        xlsx_path = out_dir / "enti_5x1000_norm.xlsx"
        export_excel_from_csv(csv_path, xlsx_path)

    logging.info("\nETL completato.")


if __name__ == "__main__":
    main()
