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

def registra_file_output(
    path: "Path | str",
    anno: "int | None" = None,
    tipo: str = "report",
    categoria: "str | None" = None,
    db_config: "dict | None" = None,
) -> bool:
    """
    Registra (o aggiorna) un singolo file nel catalogo ``dataset_files``.

    Utile per script stand-alone (es. ``report.py``) che generano file
    senza passare dall'intera pipeline.

    Parametri
    ---------
    path       : percorso al file generato
    anno       : anno di riferimento (None = file multi-anno)
    tipo       : 'report' | 'normalizzato' | 'completo' | 'categoria'
    categoria  : slug categoria (solo se tipo='categoria')
    db_config  : override configurazione DB (vedi _db_config)
    """
    try:
        import pymysql
    except ImportError:
        logger.warning("db_updater: pymysql non installato – registrazione file saltata")
        return False

    cfg = _db_config(db_config)
    if not cfg["user"] or not cfg["database"]:
        logger.warning("db_updater: SITE_DB_USER/SITE_DB_NAME non configurati – saltato")
        return False

    path = Path(path)
    if not path.exists():
        logger.warning(f"db_updater: file non trovato: {path}")
        return False

    ext = path.suffix.lstrip(".")
    if ext not in ("csv", "xlsx"):
        logger.warning(f"db_updater: formato non supportato ({ext}) per {path.name}")
        return False

    try:
        conn = pymysql.connect(**cfg)
        with conn:
            cur = conn.cursor()
            _upsert_file(cur, anno, tipo, categoria, ext, path)
        logger.info(f"db_updater: file registrato nel catalogo: {path.name}")
        return True
    except Exception as exc:
        logger.error(f"db_updater: errore registrazione file – {exc}", exc_info=True)
        return False


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

            # 4. Aggiorna la tabella enti se il CSV esiste.
            # Viene eseguito anche quando ETL è saltato (smart mode) ma
            # la tabella enti è vuota o si vuole un reimport completo.
            if csv_path and csv_path.exists():
                # Controlla se la tabella è vuota: in quel caso importa sempre
                cur.execute("SELECT COUNT(*) FROM enti")
                row = cur.fetchone()
                count_enti = row[0] if row else 0
                force = (count_enti == 0)

                if "etl" in steps_eseguiti or force:
                    if force and "etl" not in steps_eseguiti:
                        logger.info("db_updater: tabella enti vuota – reimport completo dal CSV")
                    _aggiorna_enti(cur, csv_path, pd, anni_processati)
                    logger.info(
                        f"db_updater: tabella enti aggiornata per anni "
                        f"{anni_processati if anni_processati else 'tutti'}"
                    )
                    # 4b. Aggiorna tabella runts con denominazioni canoniche
                    try:
                        _aggiorna_runts(cur, csv_path, pd)
                        logger.info("db_updater: tabella runts aggiornata")
                    except Exception as exc_r:
                        logger.warning(f"db_updater: aggiornamento runts saltato – {exc_r}")

                    # 4c. Ricalcola ripartizioni aggregate (per categoria/regione)
                    try:
                        _aggiorna_ripartizioni(cur, anni_processati)
                        logger.info("db_updater: tabella ripartizioni aggiornata")
                    except Exception as exc_rip:
                        logger.warning(f"db_updater: aggiornamento ripartizioni saltato – {exc_rip}")

            # 4d. Popola categoria_ammissioni dai file per-categoria
            if dati_dir and dati_dir.exists():
                try:
                    n_cat = _aggiorna_categoria_ammissioni(cur, dati_dir)
                    logger.info(f"db_updater: categoria_ammissioni: {n_cat} righe aggiornate")
                except Exception as exc_cat:
                    logger.warning(f"db_updater: categoria_ammissioni saltato – {exc_cat}")

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
# Aggiornamento tabella categoria_ammissioni
# Legge i file *_ammessi.xlsx e *_esclusi.xlsx da ogni sottocartella di
# dati_dir e popola la tabella con (anno, categoria, cod_fiscale, stato).
# ---------------------------------------------------------------------------

# Alias colonna codice fiscale (case-insensitive)
_CF_ALIASES    = {"codice fiscale", "cf", "codice_fiscale", "cod. fiscale", "c.f."}
# Alias colonna denominazione
_DENOM_ALIASES = {"denominazione", "beneficiario", "ente", "nome"}


def _detect_cf_denom_cols(header: list[str]) -> tuple[int | None, int | None]:
    """
    Ritorna (indice_cf, indice_denom) nella lista header.
    Confronto case-insensitive e strip spazi.
    """
    cf_idx    = None
    denom_idx = None
    for i, col in enumerate(header):
        c = col.strip().lower()
        if cf_idx    is None and c in _CF_ALIASES:
            cf_idx    = i
        if denom_idx is None and c in _DENOM_ALIASES:
            denom_idx = i
    # Fallback parziale: cerca "fiscal" o "codice" per cf
    if cf_idx is None:
        for i, col in enumerate(header):
            c = col.strip().lower()
            if "fiscal" in c or ("codice" in c and cf_idx is None):
                cf_idx = i
                break
    return cf_idx, denom_idx


def _leggi_xlsx_ammissioni(path: Path) -> list[tuple[str, str | None]]:
    """
    Legge un file xlsx e restituisce lista di (cod_fiscale, denominazione).
    Richiede openpyxl (già dipendenza della pipeline).
    """
    try:
        import openpyxl
    except ImportError:
        logger.warning("db_updater: openpyxl non disponibile – categoria_ammissioni saltata")
        return []

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    # Prima riga = header
    raw_header = [str(c) if c is not None else "" for c in rows[0]]
    cf_idx, denom_idx = _detect_cf_denom_cols(raw_header)

    if cf_idx is None:
        logger.warning(f"db_updater: colonna CF non trovata in {path.name} (header={raw_header[:5]})")
        return []

    result = []
    for row in rows[1:]:
        if not row or cf_idx >= len(row):
            continue
        cf_raw = row[cf_idx]
        if cf_raw is None:
            continue
        cf = str(cf_raw).strip().upper()
        if not cf:
            continue
        denom = None
        if denom_idx is not None and denom_idx < len(row) and row[denom_idx] is not None:
            denom = str(row[denom_idx]).strip() or None
        result.append((cf, denom))
    return result


def _aggiorna_categoria_ammissioni(cur, dati_dir: Path) -> int:
    """
    Popola la tabella `categoria_ammissioni` dai file *_ammessi.xlsx e
    *_esclusi.xlsx in ogni sottocartella di dati_dir.

    Strategia: UPSERT — aggiorna denominazione e stato se la coppia
    (anno, categoria, cod_fiscale) esiste già.

    Ritorna il numero totale di righe inserite/aggiornate.
    """
    totale = 0
    for cat_dir in sorted(dati_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_slug = _CAT_SLUG.get(cat_dir.name.upper(), cat_dir.name.lower())

        for stato in ("ammesso", "escluso"):
            pattern = f"*_{'ammessi' if stato == 'ammesso' else 'esclusi'}.xlsx"
            for xlsx in sorted(cat_dir.glob(pattern)):
                # Estrai anno dal nome file (es. "2024_ASD_ammessi.xlsx")
                try:
                    anno = int(xlsx.stem.split("_")[0])
                except (IndexError, ValueError):
                    logger.warning(f"db_updater: impossibile estrarre anno da {xlsx.name}")
                    continue

                righe = _leggi_xlsx_ammissioni(xlsx)
                if not righe:
                    continue

                batch = [
                    (anno, cat_slug, cf, denom, stato)
                    for cf, denom in righe
                ]

                cur.executemany(
                    """
                    INSERT INTO categoria_ammissioni
                      (anno, categoria, cod_fiscale, denominazione, stato)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      denominazione = COALESCE(VALUES(denominazione), denominazione),
                      stato         = VALUES(stato),
                      aggiornato_il = NOW()
                    """,
                    batch,
                )
                totale += len(batch)
                logger.info(
                    f"db_updater: categoria_ammissioni – {cat_slug}/{anno} "
                    f"{stato}: {len(batch)} righe"
                )

    return totale


# ---------------------------------------------------------------------------
# Aggiornamento tabella runts (denominazione canonica per CF)
# ---------------------------------------------------------------------------

def _aggiorna_runts(cur, csv_path: Path, pd) -> None:
    """
    Popola / aggiorna la tabella `runts` con una riga per codice fiscale.
    Strategia denominazione:
      - Se l'ente ha RUNTS_DENOMINAZIONE in almeno un anno → usa quella.
      - Altrimenti → usa la DENOMINAZIONE dell'anno più recente.
    Dati RUNTS (sezione, sede, data_iscrizione) presi dall'anno più recente
    con dati RUNTS disponibili.
    """
    cols_needed = {
        "ANNO", "COD_FISCALE", "DENOMINAZIONE",
        "RUNTS_DENOMINAZIONE", "RUNTS_SEZIONE",
        "RUNTS_SEDE_COMUNE", "RUNTS_SEDE_PROV",
        "RUNTS_5X1000", "RUNTS_DATA_ISCRIZIONE",
    }

    chunks = pd.read_csv(
        csv_path,
        dtype=str,
        chunksize=10_000,
        low_memory=False,
        usecols=lambda c: c in cols_needed,
    )
    all_rows = pd.concat(list(chunks), ignore_index=True)

    if "ANNO" in all_rows.columns:
        all_rows["ANNO"] = pd.to_numeric(all_rows["ANNO"], errors="coerce")

    # Riempi NaN con None-compatibili
    all_rows = all_rows.where(all_rows.notna(), other=None)

    result: dict[str, tuple] = {}

    for cf, group in all_rows.groupby("COD_FISCALE"):
        if not cf or str(cf) == "nan":
            continue
        group = group.sort_values("ANNO", ascending=False)

        # Righe con dati RUNTS
        runts_mask = (
            group["RUNTS_DENOMINAZIONE"].notna()
            & (group["RUNTS_DENOMINAZIONE"].astype(str).str.strip() != "")
        )
        runts_rows = group[runts_mask]

        if not runts_rows.empty:
            best = runts_rows.iloc[0]
            denom       = best.get("RUNTS_DENOMINAZIONE") or group.iloc[0].get("DENOMINAZIONE")
            sezione     = best.get("RUNTS_SEZIONE")        or None
            sede_comune = best.get("RUNTS_SEDE_COMUNE")   or None
            sede_prov   = best.get("RUNTS_SEDE_PROV")     or None
            raw_attivo  = str(best.get("RUNTS_5X1000", "0") or "0").strip()
            attivo      = 1 if raw_attivo in ("1", "True", "true") else 0
            data_isc    = best.get("RUNTS_DATA_ISCRIZIONE") or None
        else:
            best        = group.iloc[0]
            denom       = best.get("DENOMINAZIONE") or None
            sezione = sede_comune = sede_prov = data_isc = None
            attivo  = 0

        # Converti NaN / "nan" a None
        def _clean(v):
            if v is None:
                return None
            s = str(v).strip()
            return None if s in ("nan", "None", "") else s

        result[str(cf)] = (
            _clean(denom), _clean(sezione), _clean(sede_comune),
            _clean(sede_prov), attivo, _clean(data_isc),
        )

    upsert_sql = """
        INSERT INTO runts
          (cod_fiscale, denominazione, sezione, sede_comune, sede_prov,
           attivo_5x1000, data_iscrizione)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          denominazione   = VALUES(denominazione),
          sezione         = VALUES(sezione),
          sede_comune     = VALUES(sede_comune),
          sede_prov       = VALUES(sede_prov),
          attivo_5x1000   = VALUES(attivo_5x1000),
          data_iscrizione = VALUES(data_iscrizione),
          aggiornato_il   = NOW()
    """
    rows = [(cf,) + vals for cf, vals in result.items()]
    for i in range(0, len(rows), _CHUNK_SIZE):
        cur.executemany(upsert_sql, rows[i : i + _CHUNK_SIZE])

    logger.info(f"db_updater: {len(rows):,} righe upsert in tabella runts")


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

# Colonne booleane (TINYINT 0/1) che pandas scrive nel CSV come "True"/"False".
# Devono essere convertite in 1/0 prima dell'INSERT in MySQL, altrimenti
# la stringa "True" viene interpretata come 0 da MySQL → tutti i flag a 0.
_BOOL_COLS = frozenset({
    "cat_volontariato", "cat_asd", "cat_ets_onlus",
    "cat_ricerca_sci",  "cat_ricerca_san",
    "cat_comuni",       "cat_beni_cult", "cat_aree_prot",
    "runts_5x1000",
})


def _bool_to_int(v) -> int:
    """Converte 'True'/'False'/1/0/NaN → 1/0."""
    if v is None:
        return 0
    s = str(v).strip().lower()
    return 1 if s in ("true", "1", "yes", "sì", "si") else 0


def _aggiorna_enti(cur, csv_path: Path, pd, anni: list[int]) -> None:
    """
    Cancella e reinserisce le righe della tabella `enti` per gli anni indicati.
    Se `anni` è vuota, reimporta TUTTI gli anni presenti nel CSV.
    Usa bulk INSERT a chunks per limitare il consumo di memoria.
    """
    anni_int = [int(a) for a in anni]
    tutti    = len(anni_int) == 0          # lista vuota → tutti gli anni
    cols_db  = list(_COL_MAP.values())
    ph_row   = "(" + ",".join(["%s"] * len(cols_db)) + ")"
    insert_sql = (
        f"INSERT INTO enti ({','.join(cols_db)}) VALUES {ph_row}"
    )

    if tutti:
        cur.execute("DELETE FROM enti")
        logger.info("db_updater: cancellate TUTTE le righe da tabella enti (reimport completo)")
    else:
        placeholders = ",".join(["%s"] * len(anni_int))
        cur.execute(f"DELETE FROM enti WHERE anno IN ({placeholders})", anni_int)
        logger.info(f"db_updater: cancellate righe anni {anni_int} da tabella enti")

    anni_set  = set(anni_int)
    total_ins = 0

    for chunk in pd.read_csv(
        csv_path,
        dtype=str,
        chunksize=_CHUNK_SIZE,
        low_memory=False,
    ):
        # Rinomina colonne CSV → DB
        chunk = chunk.rename(columns=_COL_MAP)

        # Filtra solo gli anni richiesti (se non è reimport completo)
        if not tutti and "anno" in chunk.columns:
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

        # Converti colonne booleane da "True"/"False" stringa a 1/0 intero.
        # Pandas scrive i bool nel CSV come stringhe; MySQL TINYINT non
        # riconosce "True" come 1 e lo converte silenziosamente a 0.
        for col in _BOOL_COLS:
            if col in chunk.columns:
                chunk[col] = chunk[col].apply(_bool_to_int)

        # Sostituisci NaN con None (→ NULL in MySQL).
        def _to_none(v):
            if v is None:
                return None
            if isinstance(v, float) and v != v:   # NaN != NaN è sempre True
                return None
            return v

        rows = [tuple(_to_none(row[c]) for c in cols_db) for _, row in chunk.iterrows()]
        cur.executemany(insert_sql, rows)
        total_ins += len(rows)

    logger.info(f"db_updater: inserite {total_ins:,} righe in tabella enti")


# ---------------------------------------------------------------------------
# Aggiornamento tabella ripartizioni
# ---------------------------------------------------------------------------

_DDL_RIPARTIZIONI = """
CREATE TABLE IF NOT EXISTS `ripartizioni` (
  `id`               INT           NOT NULL AUTO_INCREMENT,
  `anno`             SMALLINT      NOT NULL,
  `categoria`        VARCHAR(50)   NOT NULL,
  `regione`          VARCHAR(100)           DEFAULT NULL
                     COMMENT 'NULL = totale nazionale',
  `n_enti`           INT           NOT NULL DEFAULT 0
                     COMMENT 'nr. enti beneficiari',
  `n_contribuenti`   INT           NOT NULL DEFAULT 0
                     COMMENT 'firme (scelte espresse)',
  `importo_espresso` DECIMAL(15,2)          DEFAULT NULL,
  `importo_generico` DECIMAL(15,2)          DEFAULT NULL,
  `importo_totale`   DECIMAL(15,2)          DEFAULT NULL,
  `aggiornato_il`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                     ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rip` (`anno`, `categoria`, `regione`),
  KEY `idx_rip_anno` (`anno`),
  KEY `idx_rip_cat`  (`anno`, `categoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_UPSERT_RIP = """
INSERT INTO ripartizioni
  (anno, categoria, regione, n_enti, n_contribuenti,
   importo_espresso, importo_generico, importo_totale)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  n_enti           = VALUES(n_enti),
  n_contribuenti   = VALUES(n_contribuenti),
  importo_espresso = VALUES(importo_espresso),
  importo_generico = VALUES(importo_generico),
  importo_totale   = VALUES(importo_totale),
  aggiornato_il    = NOW()
"""


def _aggiorna_ripartizioni(cur, anni: list[int]) -> None:
    """
    Ricalcola e aggiorna la tabella ripartizioni a partire dalla tabella enti.
    Produce due livelli di aggregazione per ogni (anno, categoria):
      - per regione  (granularità geografica)
      - nazionale    (regione = NULL)
    Va chiamata DOPO _aggiorna_enti().
    """
    cur.execute(_DDL_RIPARTIZIONI)

    anni_int = [int(a) for a in anni]
    tutti    = len(anni_int) == 0

    if tutti:
        cur.execute("DELETE FROM ripartizioni")
        anni_filter_sql = ""
        params_base: list = []
    else:
        ph = ",".join(["%s"] * len(anni_int))
        cur.execute(f"DELETE FROM ripartizioni WHERE anno IN ({ph})", anni_int)
        anni_filter_sql = f"WHERE anno IN ({ph}) AND categoria_principale IS NOT NULL"
        params_base = anni_int[:]

    # ── Per regione ──────────────────────────────────────────────────────────
    sql_reg = f"""
        SELECT anno, categoria_principale AS categoria, regione,
               COUNT(*)              AS n_enti,
               COALESCE(SUM(n_scelte), 0)          AS n_contribuenti,
               SUM(importo_espresso)               AS importo_espresso,
               SUM(importo_generico)               AS importo_generico,
               SUM(importo_totale)                 AS importo_totale
        FROM enti
        {anni_filter_sql if tutti else 'WHERE anno IN (' + ','.join(['%s']*len(anni_int)) + ') AND categoria_principale IS NOT NULL'}
        GROUP BY anno, categoria_principale, regione
    """
    cur.execute(sql_reg, params_base)
    rows_reg = cur.fetchall()
    if rows_reg:
        cur.executemany(_UPSERT_RIP, rows_reg)

    # ── Totali nazionali (regione = NULL) ─────────────────────────────────────
    sql_naz = f"""
        SELECT anno, categoria_principale AS categoria, NULL AS regione,
               COUNT(*)              AS n_enti,
               COALESCE(SUM(n_scelte), 0)          AS n_contribuenti,
               SUM(importo_espresso)               AS importo_espresso,
               SUM(importo_generico)               AS importo_generico,
               SUM(importo_totale)                 AS importo_totale
        FROM enti
        {anni_filter_sql if tutti else 'WHERE anno IN (' + ','.join(['%s']*len(anni_int)) + ') AND categoria_principale IS NOT NULL'}
        GROUP BY anno, categoria_principale
    """
    cur.execute(sql_naz, params_base)
    rows_naz = cur.fetchall()
    if rows_naz:
        cur.executemany(_UPSERT_RIP, rows_naz)

    logger.info(
        f"db_updater: ripartizioni aggiornate — "
        f"{len(rows_reg):,} righe per regione, {len(rows_naz):,} nazionali"
    )


# ---------------------------------------------------------------------------
# Esecuzione diretta: python db_updater.py [--anni 2023,2024]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, pathlib, sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Carica .env dalla root del progetto (stesso comportamento della pipeline)
    _env_file = pathlib.Path(__file__).parent / ".env"
    if _env_file.is_file():
        with open(_env_file, encoding="utf-8") as _fh:
            for _line in _fh:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip().strip("\"'")
                if _k and not os.environ.get(_k):
                    os.environ[_k] = _v

    ap = argparse.ArgumentParser(description="Reimporta il CSV nel DB del sito")
    ap.add_argument("--anni", default=None,
                    help="Anni da reimportare, es. 2023,2024 (default: tutti)")
    ap.add_argument("--csv", default=None,
                    help="Percorso al CSV normalizzato (default: Dati/enti_5x1000_norm.csv)")
    ap.add_argument("--dati-dir", default=None,
                    help="Cartella Dati/ (default: ./Dati)")
    args = ap.parse_args()

    root = pathlib.Path(__file__).parent
    dati_dir = pathlib.Path(args.dati_dir) if args.dati_dir else root / "Dati"
    csv_path = pathlib.Path(args.csv) if args.csv else dati_dir / "enti_5x1000_norm.csv"

    anni_list = []
    if args.anni:
        try:
            anni_list = [int(a.strip()) for a in args.anni.split(",") if a.strip()]
        except ValueError:
            logger.error("--anni deve contenere numeri, es. 2023,2024")
            sys.exit(1)

    ok = aggiorna_db_sito(
        anni_processati=anni_list,
        steps_eseguiti=["etl"],   # forza aggiornamento enti
        csv_path=csv_path,
        dati_dir=dati_dir,
        status="ok",
        note="Reimport manuale",
    )
    sys.exit(0 if ok else 1)
