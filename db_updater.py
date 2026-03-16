"""
db_updater.py
=============
Aggiorna il database MySQL del sito dopo ogni esecuzione della pipeline.

Configurazione tramite variabili d'ambiente (o file .env):
  SITE_DB_HOST      default: localhost
  SITE_DB_PORT      default: 3306
  SITE_DB_USER      obbligatorio
  SITE_DB_PASSWORD  obbligatorio
  SITE_DB_NAME      obbligatorio

Uso dalla pipeline:
    from db_updater import aggiorna_db_sito
    aggiorna_db_sito(
        anni_processati=[2024, 2025],
        steps_eseguiti=["download", "etl", "report"],
        csv_path=Path("Dati/enti_5x1000_norm.csv"),
        dati_dir=Path("Dati"),
        status="ok",
        t_inizio=time.time(),
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurazione DB (env vars con fallback)
# ---------------------------------------------------------------------------

def _db_config(override: dict | None = None) -> dict:
    """Restituisce il dict di connessione pymysql."""
    cfg = {
        "host":     os.getenv("SITE_DB_HOST", "localhost"),
        "port":     int(os.getenv("SITE_DB_PORT", "3306")),
        "user":     os.getenv("SITE_DB_USER", ""),
        "password": os.getenv("SITE_DB_PASSWORD", ""),
        "database": os.getenv("SITE_DB_NAME", ""),
        "charset":  "utf8mb4",
        "autocommit": True,
    }
    if override:
        cfg.update(override)
    return cfg


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------

def aggiorna_db_sito(
    anni_processati: list[int],
    steps_eseguiti: list[str],
    csv_path: Path | str,
    dati_dir: Path | str,
    status: str = "ok",
    note: str = "",
    t_inizio: float | None = None,
    db_config: dict | None = None,
) -> bool:
    """
    Aggiorna il database del sito dopo un run della pipeline.

    Parametri
    ---------
    anni_processati : lista anni elaborati, es. [2024, 2025]
    steps_eseguiti  : lista step eseguiti, es. ["download","etl","report"]
    csv_path        : Path al CSV normalizzato principale
    dati_dir        : Path alla cartella Dati/
    status          : "ok" | "error" | "parziale"
    note            : messaggio libero (es. errore parziale)
    t_inizio        : timestamp float (time.time()) inizio pipeline
    db_config       : override configurazione DB

    Restituisce True se completato senza errori.
    """
    try:
        import pymysql
    except ImportError:
        logger.warning("db_updater: pymysql non installato – aggiornamento DB saltato")
        return False

    try:
        import pandas as pd
    except ImportError:
        logger.warning("db_updater: pandas non disponibile – aggiornamento DB saltato")
        return False

    cfg = _db_config(db_config)
    if not cfg["user"] or not cfg["database"]:
        logger.warning(
            "db_updater: SITE_DB_USER / SITE_DB_NAME non configurati – saltato"
        )
        return False

    csv_path = Path(csv_path) if csv_path else None
    dati_dir = Path(dati_dir) if dati_dir else None
    t0 = time.time()

    try:
        conn = pymysql.connect(**cfg)
        with conn:
            cur = conn.cursor()

            # 1. Conta righe nel CSV senza caricarlo tutto in memoria
            righe_totali = 0
            if csv_path and csv_path.exists():
                with open(csv_path, "r", encoding="utf-8", errors="replace") as fh:
                    righe_totali = sum(1 for _ in fh) - 1  # sottrai header

            # 2. Registra il run nella tabella pipeline_runs
            durata = int(t0 - t_inizio) if t_inizio else None
            cur.execute(
                """
                INSERT INTO pipeline_runs
                  (run_at, anni_processati, steps_eseguiti, righe_totali,
                   status, note, durata_secondi)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    datetime.now(),
                    json.dumps([int(a) for a in anni_processati]),
                    json.dumps(list(steps_eseguiti)),
                    righe_totali,
                    status,
                    note or None,
                    durata,
                ),
            )
            run_id = cur.lastrowid
            logger.info(f"db_updater: pipeline_run #{run_id} registrato ({status})")

            # 3. Aggiorna il catalogo dei file scaricabili
            if dati_dir and dati_dir.exists():
                _aggiorna_files(cur, dati_dir)
                logger.info("db_updater: dataset_files aggiornati")

            # 4. Aggiorna la tabella enti (solo se ETL è stato eseguito)
            if "etl" in steps_eseguiti and csv_path and csv_path.exists():
                _aggiorna_enti(cur, csv_path, pd, anni_processati)
                logger.info(
                    f"db_updater: tabella enti aggiornata per anni {anni_processati}"
                )

        logger.info(f"db_updater: completato in {time.time() - t0:.1f}s")
        return True

    except Exception as exc:
        logger.error(f"db_updater: errore durante l'aggiornamento – {exc}", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Aggiornamento catalogo file
# ---------------------------------------------------------------------------

# Mappa nomi directory categoria → slug per il DB
_CAT_SLUG = {
    "VOLONTARIATO": "volontariato",
    "ASD":          "asd",
    "ETS_ONLUS":    "ets_onlus",
    "RICERCA_SCI":  "ricerca_scientifica",
    "RICERCA_SAN":  "ricerca_sanitaria",
    "COMUNI":       "comuni",
    "BENI_CULT":    "beni_culturali",
    "AREE_PROT":    "aree_protette",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _upsert_file(cur, anno, tipo, categoria, formato, path: Path) -> None:
    if not path.exists():
        return
    size_mb = round(path.stat().st_size / 1_048_576, 2)
    sha = _sha256(path)
    cur.execute(
        """
        INSERT INTO dataset_files
          (anno, tipo, categoria, formato, percorso, nome_file,
           dimensione_mb, sha256, aggiornato_il)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
          percorso       = VALUES(percorso),
          nome_file      = VALUES(nome_file),
          dimensione_mb  = VALUES(dimensione_mb),
          sha256         = VALUES(sha256),
          aggiornato_il  = NOW()
        """,
        (anno, tipo, categoria, formato, str(path), path.name, size_mb, sha),
    )


def _aggiorna_files(cur, dati_dir: Path) -> None:
    # Dataset completo (CSV)
    _upsert_file(cur, None, "completo", None, "csv", dati_dir / "enti_5x1000_norm.csv")
    _upsert_file(cur, None, "completo", None, "xlsx", dati_dir / "enti_5x1000_norm.xlsx")

    # File per anno (dati_YYYY.xlsx)
    for f in sorted(dati_dir.glob("dati_*.xlsx")):
        try:
            anno = int(f.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        _upsert_file(cur, anno, "normalizzato", None, "xlsx", f)

    # Report per anno (report_YYYY.xlsx)
    for f in sorted(dati_dir.glob("report_*.xlsx")):
        try:
            anno = int(f.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        _upsert_file(cur, anno, "report", None, "xlsx", f)

    # File per categoria + anno
    for cat_dir in sorted(dati_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_slug = _CAT_SLUG.get(cat_dir.name.upper(), cat_dir.name.lower())
        for f in sorted(cat_dir.glob("*_ammessi.xlsx")):
            try:
                anno = int(f.stem.split("_")[0])
            except (IndexError, ValueError):
                continue
            _upsert_file(cur, anno, "categoria", cat_slug, "xlsx", f)


# ---------------------------------------------------------------------------
# Aggiornamento tabella enti
# ---------------------------------------------------------------------------

# Mapping esatto colonne CSV uppercase → colonne DB lowercase
_COL_MAP = {
    "ANNO":                  "anno",
    "COD_FISCALE":           "cod_fiscale",
    "DENOMINAZIONE":         "denominazione",
    "REGIONE":               "regione",
    "PROVINCIA":             "provincia",
    "COMUNE":                "comune",
    "CAT_VOLONTARIATO":      "cat_volontariato",
    "CAT_ASD":               "cat_asd",
    "CAT_ETS_ONLUS":         "cat_ets_onlus",
    "CAT_RICERCA_SCI":       "cat_ricerca_sci",
    "CAT_RICERCA_SAN":       "cat_ricerca_san",
    "CAT_COMUNI":            "cat_comuni",
    "CAT_BENI_CULT":         "cat_beni_cult",
    "CAT_AREE_PROT":         "cat_aree_prot",
    "CATEGORIA_PRINCIPALE":  "categoria_principale",
    "N_SCELTE":              "n_scelte",
    "IMPORTO_ESPRESSO":      "importo_espresso",
    "IMPORTO_GENERICO":      "importo_generico",
    "IMPORTO_TOTALE":        "importo_totale",
    "RUNTS_DENOMINAZIONE":   "runts_denominazione",
    "RUNTS_SEZIONE":         "runts_sezione",
    "RUNTS_SEDE_COMUNE":     "runts_sede_comune",
    "RUNTS_SEDE_PROV":       "runts_sede_prov",
    "RUNTS_5X1000":          "runts_5x1000",
    "RUNTS_DATA_ISCRIZIONE": "runts_data_iscrizione",
}

_CHUNK_SIZE = 5_000  # righe per batch INSERT


def _aggiorna_enti(cur, csv_path: Path, pd, anni: list[int]) -> None:
    """
    Cancella e reinserisce le righe della tabella `enti` per gli anni indicati.
    Usa bulk INSERT a chunks per limitare il consumo di memoria.
    """
    anni_int = [int(a) for a in anni]
    cols_db  = list(_COL_MAP.values())
    ph_row   = "(" + ",".join(["%s"] * len(cols_db)) + ")"
    insert_sql = (
        f"INSERT INTO enti ({','.join(cols_db)}) VALUES {ph_row}"
    )

    # Cancella solo gli anni da rielaborare (preserva gli altri)
    placeholders = ",".join(["%s"] * len(anni_int))
    cur.execute(f"DELETE FROM enti WHERE anno IN ({placeholders})", anni_int)
    logger.info(f"db_updater: cancellate righe anni {anni_int} da tabella enti")

    anni_set    = set(anni_int)
    total_ins   = 0

    for chunk in pd.read_csv(
        csv_path,
        dtype=str,
        chunksize=_CHUNK_SIZE,
        low_memory=False,
    ):
        # Rinomina colonne CSV → DB
        chunk = chunk.rename(columns=_COL_MAP)

        # Filtra solo gli anni richiesti
        if "anno" in chunk.columns:
            chunk = chunk[
                chunk["anno"].fillna("").str.extract(r"(\d{4})")[0]
                .astype(float, errors="ignore")
                .astype("Int64", errors="ignore")
                .isin(anni_set)
            ]
        if chunk.empty:
            continue

        # Assicura che ci siano tutte le colonne (riempi mancanti con None)
        for col in cols_db:
            if col not in chunk.columns:
                chunk[col] = None

        # Sostituisci NaN con None (→ NULL in MySQL)
        chunk = chunk.where(chunk.notna(), None)

        rows = [tuple(row[c] for c in cols_db) for _, row in chunk.iterrows()]
        cur.executemany(insert_sql, rows)
        total_ins += len(rows)

    logger.info(f"db_updater: inserite {total_ins:,} righe in tabella enti")
