from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIG
# ============================================================
DATA_DIR = Path(r"C:\Python\5x1000\Dati")
OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_ENTI = OUTPUT_DIR / "enti.csv"
OUTPUT_ENTI_CATEGORIA = OUTPUT_DIR / "enti_categoria.csv"


# ============================================================
# MAPPE COLONNE PER ANNO
# ============================================================
YEAR_CONFIGS: dict[str, dict[str, Any]] = {
    "2006": {
        "file": "dati_2006.xlsx",
        "sheet": "2006",
        "rename": {
            "CATEGORIA - VOLONTARIATO / ASD": "CATEGORIA - VOLONTARIATO",
            "RICERCA SCIENTIFICA": "CATEGORIA - RICERCA SCIENTIFICA",
            "RICERCA SANITARIA": "CATEGORIA - RICERCA SANITARIA",
            "COMUNI": "CATEGORIA - COMUNI",
        },
    },
    "2007": {
        "file": "dati_2007.xlsx",
        "sheet": "2007",
        "rename": {
            "CATEGORIA - VOLONTARIATO/ ASD": "CATEGORIA - VOLONTARIATO",
            "RICERCA SCIENTIFICA": "CATEGORIA - RICERCA SCIENTIFICA",
            "RICERCA SANITARIA": "CATEGORIA - RICERCA SANITARIA",
        },
    },
    "2008": {
        "file": "dati_2008.xlsx",
        "sheet": "2008",
        "rename": {
            "ASD": "CATEGORIA - ASD",
            "RICERCA SCIENTIFICA": "CATEGORIA - RICERCA SCIENTIFICA",
            "RICERCA SANITARIA": "CATEGORIA - RICERCA SANITARIA",
        },
    },
    "2009": {
        "file": "dati_2009.xlsx",
        "sheet": "2009",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2010": {
        "file": "dati_2010.xlsx",
        "sheet": "2010",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2011": {
        "file": "dati_2011.xlsx",
        "sheet": "2011",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2012": {
        "file": "dati_2012.xlsx",
        "sheet": "2012",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Mibac": "CATEGORIA - Mibac",
            "Mibac*": "MIBAC",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2013": {
        "file": "dati_2013.xlsx",
        "sheet": "2013",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Mibac": "CATEGORIA - Mibac",
            "Mibac *": "MIBAC",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2014": {
        "file": "dati_2014.xlsx",
        "sheet": "2014",
        "rename": {
            "BENEFICIARIO": "DENOMINAZIONE",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Mibac": "CATEGORIA - Mibac",
            "Mibac*": "MIBAC",
            "Totale": "IMPORTO TOTALE",
        },
    },
    "2015": {
        "file": "dati_2015.xlsx",
        "sheet": "2015",
        "rename": {
            "PROV": "PROVINCIA",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Mibac": "CATEGORIA - Mibac",
            "IMPORTO (EURO) - IMPORTO DELLE SCELTE ESPRESSE": "Importo (EURO) - per scelte espresse",
            "IMPORTO PROPORZIONALE PER LE SCELTE GENERICHE": "per scelte generiche",
        },
    },
    "2016": {
        "file": "dati_2016.xlsx",
        "sheet": "2016",
        "rename": {
            "PROV": "PROVINCIA",
            "CATEGORIA - Volontariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca Scientifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca Sanitaria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "MIBAC": "CATEGORIA - Mibac",
            "IMPORTO (EURO) - IMPORTO DELLE SCELTE ESPRESSE": "Importo (EURO) - per scelte espresse",
            "IMPORTO PROPORZIONALE PER LE SCELTE GENERICHE": "per scelte generiche",
        },
    },
    "2017": {
        "file": "dati_2017.xlsx",
        "sheet": "2017",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "Volon­ tariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scient­ ifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanita­ ria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Beni culturali e paesa­ ggistici": "CATEGORIA - Mibac",
            "Enti Gestori aree protette": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo totale": "IMPORTO TOTALE",
        },
    },
    "2018": {
        "file": "dati_2018.xlsx",
        "sheet": "2018",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "Volon­ tariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scient­ ifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanita­ ria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Beni culturali e paesa­ ggistici": "CATEGORIA - Mibac",
            "Enti Gestori aree protette": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo totale": "IMPORTO TOTALE",
        },
    },
    "2019": {
        "file": "dati_2019.xlsx",
        "sheet": "2019",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "Volon­ tariato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scient­ ifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanita­ ria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Beni culturali e paesa­ ggistici": "CATEGORIA - Mibac",
            "Enti Gestori aree protette": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo totale": "IMPORTO TOTALE",
        },
    },
    "2020": {
        "file": "dati_2020.xlsx",
        "sheet": "2020",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "Volo­ ntari­ ato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scien­ tifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanit­ aria": "CATEGORIA - RICERCA SANITARIA",
            "Com­ uni": "CATEGORIA - COMUNI",
            "Beni cultu­ rali e paes­ aggis­ tici": "CATEGORIA - Mibac",
            "Enti Gestori aree prote­ tte": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo proporzionale per ripartizione importi inferiori a 100 euro": "Importo proporzionale per ripartizione importi inferiori a 100 euro",
            "Importo Totale Erogabile": "IMPORTO TOTALE",
        },
    },
    "2021": {
        "file": "dati_2021.xlsx",
        "sheet": "2021",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "Volo­ ntari­ ato": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scien­ tifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanit­ aria": "CATEGORIA - RICERCA SANITARIA",
            "Comuni": "CATEGORIA - COMUNI",
            "Beni cultu­ rali e paes­ aggis­ tici": "CATEGORIA - Mibac",
            "Enti Gestori aree prote­ tte": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo proporzionale per ripartizione importi inferiori a 100 euro": "Importo proporzionale per ripartizione importi inferiori a 100 euro",
            "Importo Totale Erogabile": "IMPORTO TOTALE",
        },
    },
    "2022": {
        "file": "dati_2022.xlsx",
        "sheet": "2022",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "ETS e ONLUS": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scien­ tifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanit­ aria": "CATEGORIA - RICERCA SANITARIA",
            "Com­ uni": "CATEGORIA - COMUNI",
            "Beni cultu­ rali e paes­ aggis­ tici": "CATEGORIA - Mibac",
            "Enti Gestori aree prote­ tte": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo proporzionale per ripartizione importi inferiori a 100 euro": "Importo proporzionale per ripartizione importi inferiori a 100 euro",
            "Importo Totale Erogabile": "IMPORTO TOTALE",
        },
    },
    "2023": {
        "file": "dati_2023.xlsx",
        "sheet": "2023",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "ETS e ONLUS": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scien­ tifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanit­ aria": "CATEGORIA - RICERCA SANITARIA",
            "Com­ uni": "CATEGORIA - COMUNI",
            "Beni cultu­ rali e paes­ aggis­ tici": "CATEGORIA - Mibac",
            "Enti Gestori aree prote­ tte": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo proporzionale per ripartizione importi inferiori a 100 euro": "Importo proporzionale per ripartizione importi inferiori a 100 euro",
            "Importo Totale Erogabile": "IMPORTO TOTALE",
        },
    },
    "2024": {
        "file": "dati_2024.xlsx",
        "sheet": "2024",
        "rename": {
            "Codice fiscale": "CODICE FISCALE",
            "Denominazione": "DENOMINAZIONE",
            "Regione": "REGIONE",
            "PR": "PROVINCIA",
            "Comune": "COMUNE",
            "ETS e ONLUS": "CATEGORIA - VOLONTARIATO",
            "ASD": "CATEGORIA - ASD",
            "Ricerca scien­ tifica": "CATEGORIA - RICERCA SCIENTIFICA",
            "Ricerca sanit­ aria": "CATEGORIA - RICERCA SANITARIA",
            "Com­ uni": "CATEGORIA - COMUNI",
            "Beni cultu­ rali e paes­ aggis­ tici": "CATEGORIA - Mibac",
            "Enti Gestori aree prote­ tte": "CATEGORIA - AREE PROTETTE",
            "Numero scelte": "NUMERO SCELTE",
            "Importo delle scelte espresse": "Importo (EURO) - per scelte espresse",
            "Importo proporzionale per le scelte generiche": "per scelte generiche",
            "Importo proporzionale per ripartizione importi inferiori a 100 euro": "Importo proporzionale per ripartizione importi inferiori a 100 euro",
            "Importo Totale Erogabile": "IMPORTO TOTALE",
        },
    },
}


# ============================================================
# COLONNE STANDARD DELLO STAGING
# ============================================================
STANDARD_COLUMNS = [
    "CODICE FISCALE",
    "DENOMINAZIONE",
    "REGIONE",
    "PROVINCIA",
    "COMUNE",
    "CATEGORIA - VOLONTARIATO",
    "CATEGORIA - ASD",
    "CATEGORIA - RICERCA SCIENTIFICA",
    "CATEGORIA - RICERCA SANITARIA",
    "CATEGORIA - COMUNI",
    "CATEGORIA - Mibac",
    "CATEGORIA - AREE PROTETTE",
    "NUMERO SCELTE",
    "Importo (EURO) - per scelte espresse",
    "per scelte generiche",
    "Importo proporzionale per ripartizione importi inferiori a 100 euro",
    "IMPORTO TOTALE",
    "ANNO",
]


# ============================================================
# UTILITY
# ============================================================
def collapse_spaces(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_text_upper(value: Any) -> str | None:
    text = collapse_spaces(value)
    return text.upper() if text else None


def clean_number(value: Any) -> float:
    if pd.isna(value):
        return 0.0

    text = str(value).strip()
    if text == "" or text == "-":
        return 0.0

    # gestisce formati tipo 1.234,56 o 1234.56
    text = text.replace("\xa0", "")
    text = text.replace("€", "")
    text = text.replace(" ", "")

    # se c'è sia punto che virgola, assumiamo it-IT
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def clean_codice_fiscale(value: Any) -> str | None:
    text = collapse_spaces(value)
    if not text:
        return None

    text = text.upper()

    # se è numerico puro, pad a 11 cifre
    if re.fullmatch(r"\d+", text):
        return text.zfill(11)

    # altrimenti lascia testo pulito
    return text


def normalize_match_key(value: Any) -> str | None:
    """
    Campo 'duro' per matching:
    - trim
    - uppercase
    - spazi multipli -> uno
    - rimozione spazi finali
    - rimozione spazi interni solo se la stringa sembra 'troppo spezzata'
      secondo una logica simile al Qlik
    """
    text = collapse_spaces(value)
    if not text:
        return None

    text = text.upper()
    compact = text.replace(" ", "")

    if len(text) == 0:
        return None

    ratio = len(compact) / len(text)
    space_count = text.count(" ")

    if ratio >= 0.6:
        if space_count >= len(text) / 4:
            return compact
        return text

    return text


def strip_accents(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


# ============================================================
# ESTRAZIONE / STAGING
# ============================================================
def load_year(year: str, cfg: dict[str, Any]) -> pd.DataFrame:
    file_path = DATA_DIR / cfg["file"]
    sheet_name = cfg["sheet"]

    df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=object)
    df = df.rename(columns=cfg["rename"])
    df["ANNO"] = int(year)
    df = ensure_columns(df, STANDARD_COLUMNS)
    return df


def build_enti_working() -> pd.DataFrame:
    frames = []
    for year in sorted(YEAR_CONFIGS.keys()):
        print(f"Carico anno {year}...")
        frames.append(load_year(year, YEAR_CONFIGS[year]))
    return pd.concat(frames, ignore_index=True)


# ============================================================
# TRASFORMAZIONE FINALE ENTI
# ============================================================
def build_enti(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()

    out["CODICE FISCALE"] = df["CODICE FISCALE"].apply(clean_codice_fiscale)
    out["DENOMINAZIONE"] = df["DENOMINAZIONE"].apply(clean_text_upper)
    out["REGIONE"] = df["REGIONE"].apply(clean_text_upper)
    out["PROVINCIA"] = df["PROVINCIA"].apply(clean_text_upper)
    out["COMUNE"] = df["COMUNE"].apply(clean_text_upper)

    out["ETS e ONLUS"] = df["CATEGORIA - VOLONTARIATO"].apply(clean_text_upper)
    out["CATEGORIA - ASD"] = df["CATEGORIA - ASD"].apply(clean_text_upper)
    out["CATEGORIA - RICERCA SCIENTIFICA"] = df["CATEGORIA - RICERCA SCIENTIFICA"].apply(clean_text_upper)
    out["CATEGORIA - RICERCA SANITARIA"] = df["CATEGORIA - RICERCA SANITARIA"].apply(clean_text_upper)
    out["CATEGORIA - COMUNI"] = df["CATEGORIA - COMUNI"].apply(clean_text_upper)
    out["CATEGORIA - BENI CULTURALI"] = df["CATEGORIA - Mibac"].apply(clean_text_upper)
    out["CATEGORIA - AREE PROTETTE"] = df["CATEGORIA - AREE PROTETTE"].apply(clean_text_upper)

    out["NUMERO SCELTE"] = df["NUMERO SCELTE"].apply(clean_number).round().astype("Int64")
    out["Per scelte espresse"] = df["Importo (EURO) - per scelte espresse"].apply(clean_number)
    out["Per scelte generiche"] = df["per scelte generiche"].apply(clean_number)
    out["Ripartizione importi > 100€"] = df["Importo proporzionale per ripartizione importi inferiori a 100 euro"].apply(clean_number)
    out["IMPORTO TOTALE"] = df["IMPORTO TOTALE"].apply(clean_number)
    out["ANNO"] = df["ANNO"].apply(clean_number).round().astype("Int64")

    # normalizzazioni aggiuntive stile Qlik
    out["COMUNE_NORMALIZZATO"] = out["COMUNE"].apply(normalize_match_key)
    out["DENOMINAZIONE_NORMALIZZATA"] = out["DENOMINAZIONE"].apply(normalize_match_key)
    out["REGIONE_NORMALIZZATA"] = out["REGIONE"].apply(normalize_match_key)

    # eventuali chiavi ancora più dure per matching
    out["DENOMINAZIONE_MATCH_KEY"] = out["DENOMINAZIONE_NORMALIZZATA"].apply(strip_accents)
    out["COMUNE_MATCH_KEY"] = out["COMUNE_NORMALIZZATO"].apply(strip_accents)
    out["REGIONE_MATCH_KEY"] = out["REGIONE_NORMALIZZATA"].apply(strip_accents)

    return out


# ============================================================
# ENTI_CATEGORIA IN FORMATO LUNGO
# ============================================================
def has_text(value: Any) -> bool:
    return collapse_spaces(value) is not None


def build_enti_categoria(enti: pd.DataFrame) -> pd.DataFrame:
    category_map = {
        "ETS e ONLUS": "VOLONTARIATO",
        "CATEGORIA - ASD": "ASD",
        "CATEGORIA - RICERCA SCIENTIFICA": "RICERCA SCIENTIFICA",
        "CATEGORIA - RICERCA SANITARIA": "RICERCA SANITARIA",
        "CATEGORIA - BENI CULTURALI": "BENI CULTURALI",
        "CATEGORIA - AREE PROTETTE": "AREE PROTETTE",
        "CATEGORIA - COMUNI": "COMUNI",
    }

    rows: list[pd.DataFrame] = []

    base_cols = [
        "CODICE FISCALE",
        "DENOMINAZIONE",
        "REGIONE",
        "PROVINCIA",
        "COMUNE",
        "ANNO",
        "NUMERO SCELTE",
        "Per scelte espresse",
        "Per scelte generiche",
        "Ripartizione importi > 100€",
        "IMPORTO TOTALE",
    ]

    for source_col, categoria_label in category_map.items():
        mask = enti[source_col].apply(has_text)
        tmp = enti.loc[mask, base_cols].copy()
        tmp["CATEGORIA"] = categoria_label
        rows.append(tmp)

    result = pd.concat(rows, ignore_index=True).drop_duplicates()
    return result


# ============================================================
# QUALITY CHECKS MINIMI
# ============================================================
def quality_checks(enti: pd.DataFrame) -> None:
    print("\n--- QUALITY CHECKS ---")
    print(f"Righe totali: {len(enti):,}")
    print(f"Codici fiscali null: {enti['CODICE FISCALE'].isna().sum():,}")
    print(f"Denominazioni null: {enti['DENOMINAZIONE'].isna().sum():,}")
    print(f"Anni presenti: {sorted(enti['ANNO'].dropna().unique().tolist())}")
    print(f"Importo totale complessivo: {enti['IMPORTO TOTALE'].sum():,.2f}")


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    enti_working = build_enti_working()
    enti = build_enti(enti_working)
    enti_categoria = build_enti_categoria(enti)

    quality_checks(enti)

    enti.to_csv(OUTPUT_ENTI, index=False, encoding="utf-8-sig")
    enti_categoria.to_csv(OUTPUT_ENTI_CATEGORIA, index=False, encoding="utf-8-sig")

    print("\nFile generati:")
    print(f"- {OUTPUT_ENTI}")
    print(f"- {OUTPUT_ENTI_CATEGORIA}")


if __name__ == "__main__":
    main()