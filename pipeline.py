#!/usr/bin/env python3
"""
5 per Mille - Pipeline completa.

Orchestratore che esegue in sequenza i 5 step della pipeline:
  1. cinque_per_mille.py  — download elenco complessivo + estrazione Excel
  2. scarica_categorie.py — download per categoria + estrazione Excel
  3. etl.py               — normalizzazione, merge RUNTS, export CSV/Excel
  4. report.py            — report Excel multi-foglio (stile ASSIF/Bedogni)
  5. gsheets.py           — upload su Google Sheets

Le domande vengono poste all'inizio e i parametri passati ai singoli script.

Uso:
    python pipeline.py                                  # interattivo
    python pipeline.py --anni 2024                      # solo anno 2024
    python pipeline.py --skip-download --skip-gsheets   # solo estrazione + ETL
    python pipeline.py --only categorie,etl             # solo step specifici
    python pipeline.py --help
"""

import json
import os
import signal
import sys
import time
import argparse
import subprocess
import logging
import datetime
import shutil


# ============================================================================
# Carica variabili d'ambiente da .env (se presente)
# ============================================================================

def _load_dotenv(root_dir):
    env_path = os.path.join(root_dir, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            # Rimuove eventuale prefisso 'export '
            if line.startswith("export "):
                line = line[7:]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_dotenv(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

STEPS_ALL = ["metadata", "download", "categorie", "etl", "report", "gsheets"]

DEFAULT_INPUT = "categorie.xlsx"

# Percorso file lock manutenzione — creato all'avvio della pipeline,
# rimosso al termine (anche in caso di eccezione).
# Il path può essere sovrascritto da PIPELINE_LOCK_PATH in .env
_DEFAULT_LOCK_FILENAME = "pipeline.lock"

# Python eseguibile: stesso interprete che sta eseguendo questo script.
# sys.executable può essere '' in ambienti embedded/CGI/PHP; fallback robusto.
PYTHON = sys.executable or shutil.which("python3") or shutil.which("python") or "python3"


def _load_pipeline_config(root_dir):
    """Carica la sezione 'pipeline' da config.yaml."""
    config_path = os.path.join(root_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("pipeline", {})
    except Exception:
        return {}


# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(root_dir):
    """Configura logging su file e console."""
    log_dir = os.path.join(root_dir, "log")
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"pipeline_{stamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


# ============================================================================
# DOMANDE INTERATTIVE
# ============================================================================

def ask_yes_no(prompt, default="s"):
    """Chiede una conferma si/no."""
    suffix = " [S/n]: " if default == "s" else " [s/N]: "
    while True:
        resp = input(prompt + suffix).strip().lower()
        if not resp:
            return default == "s"
        if resp in ("s", "si", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False


def ask_choice(prompt, choices, default=None):
    """Chiede di scegliere tra opzioni."""
    print(prompt)
    for i, c in enumerate(choices, 1):
        marker = " (default)" if c == default else ""
        print(f"  {i}. {c}{marker}")
    while True:
        resp = input(f"Scelta [1-{len(choices)}]: ").strip()
        if not resp and default:
            return default
        try:
            idx = int(resp) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass


# ============================================================================
# ESECUZIONE STEP
# ============================================================================

_DEFAULT_STEP_TIMEOUT = 3600  # fallback se non configurato


def run_step(name, cmd, root_dir, timeout=None):
    """
    Esegue un comando subprocess per uno step della pipeline.
    Restituisce (success: bool, duration_secs: float).
    Il timeout (secondi) è configurabile; il processo viene ucciso alla scadenza.
    """
    if timeout is None:
        timeout = _DEFAULT_STEP_TIMEOUT

    logging.info(f"\n{'='*60}")
    logging.info(f"STEP: {name}")
    logging.info(f"Comando: {' '.join(cmd)}")
    logging.info(f"Timeout: {timeout}s")
    logging.info(f"{'='*60}")

    start = time.time()
    proc = None
    try:
        proc = subprocess.Popen(cmd, cwd=root_dir)
        proc.wait(timeout=timeout)
        elapsed = time.time() - start
        if proc.returncode == 0:
            logging.info(f"[OK] {name} completato in {elapsed:.0f}s")
            return True, elapsed
        else:
            logging.error(f"[ERRORE] {name} fallito (exit code {proc.returncode})")
            return False, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        logging.error(f"[TIMEOUT] {name} interrotto dopo {elapsed:.0f}s (limite: {timeout}s)")
        if proc is not None:
            try:
                proc.kill()
                proc.wait()
                logging.info(f"Processo {proc.pid} terminato forzatamente.")
            except Exception as kill_exc:
                logging.warning(f"Impossibile terminare il processo: {kill_exc}")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"[ERRORE] {name}: {e}")
        if proc is not None:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
        return False, elapsed


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="5 per Mille - Pipeline completa (download > estrazione > ETL > GSheets)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Esempi:
  %(prog)s                                      # interattivo
  %(prog)s --anni 2024                          # solo anno 2024
  %(prog)s --skip-download                      # salta download, solo estrazione + ETL + GSheets
  %(prog)s --skip-download --skip-gsheets       # solo estrazione + ETL
  %(prog)s --only categorie,etl,report          # solo step specifici

Step disponibili: download, categorie, etl, report, gsheets
""",
    )
    parser.add_argument(
        "--anni", type=str, default=None,
        help="Anni da elaborare, separati da virgola (es. 2023,2024)",
    )
    parser.add_argument(
        "--source", choices=["csv", "pdf"], default="pdf",
        help="Fonte dati per estrazione: 'pdf' (default) o 'csv'",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help=f"File Excel con link categorie (default: {DEFAULT_INPUT} o da config.yaml)",
    )
    parser.add_argument(
        "--skip-metadata", action="store_true",
        help="Salta il scraping metadati da AdE (date aggiornamenti file)",
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Salta la fase di download in entrambi gli script",
    )
    parser.add_argument(
        "--skip-gsheets", action="store_true",
        help="Salta l'upload su Google Sheets",
    )
    parser.add_argument(
        "--sheet-id", type=str, default=None,
        help="ID del Google Sheet (o da config.yaml)",
    )
    parser.add_argument(
        "--only", type=str, default=None,
        help="Esegui solo step specifici, separati da virgola (es. etl,gsheets)",
    )
    parser.add_argument(
        "--no-runts", action="store_true",
        help="Salta il merge RUNTS in etl.py",
    )
    parser.add_argument(
        "--no-excel-etl", action="store_true",
        help="Non genera il file Excel in etl.py (solo CSV)",
    )
    parser.add_argument(
        "--anno-confronto", type=int, default=None,
        help="Anno per il confronto YoY nel report (default: anno-1)",
    )
    parser.add_argument(
        "--no-confronto", action="store_true",
        help="Non calcolare il confronto YoY nel report",
    )
    parser.add_argument(
        "--skip-report", action="store_true",
        help="Salta la generazione del report Excel",
    )
    parser.add_argument(
        "--smart", action="store_true",
        help=(
            "Analizza i file già presenti e salta automaticamente gli step/anni "
            "già aggiornati. Download e categorie vengono eseguiti solo per gli "
            "anni mancanti; ETL solo se l'output è obsoleto."
        ),
    )
    parser.add_argument(
        "--anni-download", type=str, default=None,
        help="Override esplicito degli anni da scaricare (liste complete). "
             "Se omesso, usa --anni (o smart mode se attivo).",
    )
    parser.add_argument(
        "--anni-categorie", type=str, default=None,
        help="Override esplicito degli anni da scaricare (per categoria). "
             "Se omesso, usa --anni (o smart mode se attivo).",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help=(
            "Azzera tutti i dati prima di partire: svuota la cartella Dati/ "
            "e le tabelle DB (enti, dataset_files, pipeline_runs). "
            "Richiede conferma interattiva a meno che non sia passato --force."
        ),
    )
    parser.add_argument(
        "--reset-db", action="store_true",
        help="Come --reset ma solo per il DB (non tocca i file su disco).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Salta la conferma interattiva richiesta da --reset / --reset-db.",
    )
    parser.add_argument(
        "--report-only", action="store_true",
        help=(
            "Scorciatoia: esegui solo lo step 'report' (equivalente a --only report). "
            "Utile per rigenerare il report Excel senza riscaricare o rielaborare i dati."
        ),
    )
    parser.add_argument(
        "--per-anno", action="store_true",
        help=(
            "Esegui la pipeline un anno alla volta, dal più recente al più vecchio. "
            "Per ogni anno: download → ETL → aggiornamento DB, poi passa all'anno successivo. "
            "Report e GSheets vengono eseguiti una sola volta alla fine."
        ),
    )
    parser.add_argument(
        "--ciclo", action="store_true",
        help=(
            "Modalità ciclo incrementale (sito sempre attivo, nessuna manutenzione). "
            "FASE 1: scarica tutti gli anni mancanti (elenco complessivo + categorie). "
            "FASE 2: elabora anno per anno (ETL + DB via UPSERT). "
            "Usa file .done per tracciare step già completati e non ripeterli. "
            "GSheets saltato; report eseguito una sola volta alla fine se richiesto."
        ),
    )
    parser.add_argument(
        "--max-retry", type=int, default=3, metavar="N",
        help=(
            "Numero massimo di tentativi totali (default: 3). "
            "Se dopo un run restano anni non elaborati, la pipeline riparte "
            "automaticamente in smart-mode per completare i pendenti."
        ),
    )
    return parser.parse_args()


# ============================================================================
# RESET
# ============================================================================

def reset_tutto(root_dir: str, solo_db: bool = False, force: bool = False) -> bool:
    """
    Azzera tutti i dati della pipeline.
    - File: svuota Dati/ (solo_db=False)
    - DB:   DELETE FROM enti, dataset_files, pipeline_runs

    Ritorna True se il reset è completato, False se annullato dall'utente.
    """
    dati_dir = os.path.join(root_dir, "Dati")
    log_dir  = os.path.join(root_dir, "log")
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"reset_{ts}.log")

    # Logging dedicato
    reset_logger = logging.getLogger("reset")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    reset_logger.addHandler(fh)
    reset_logger.setLevel(logging.INFO)

    print("\n" + "=" * 60)
    print("  RESET — 5 per Mille")
    print("=" * 60)
    if not solo_db:
        print(f"  ⚠  Verranno CANCELLATI tutti i file in: {dati_dir}")
    print("  ⚠  Verranno svuotate le tabelle DB:")
    print("       enti · dataset_files · pipeline_runs")
    print("=" * 60)

    if not force:
        risposta = input("\nConfermi il reset? Questa operazione è irreversibile. [s/N] ").strip().lower()
        if risposta not in ("s", "si", "sì", "y", "yes"):
            print("Reset annullato.")
            return False

    # ── 1. File ──────────────────────────────────────────────────────────────
    if not solo_db:
        if os.path.isdir(dati_dir):
            reset_logger.info(f"Cancellazione cartella Dati/: {dati_dir}")
            shutil.rmtree(dati_dir)
            reset_logger.info("Cartella Dati/ eliminata.")
        os.makedirs(dati_dir, exist_ok=True)
        reset_logger.info("Cartella Dati/ ricreata vuota.")
        print("✓ Cartella Dati/ svuotata.")

    # ── 2. DB ─────────────────────────────────────────────────────────────────
    try:
        import pymysql
    except ImportError:
        msg = "pymysql non installato — reset DB saltato."
        reset_logger.warning(msg)
        print(f"⚠  {msg}")
    else:
        db_cfg = {
            "host":     os.getenv("SITE_DB_HOST", "localhost"),
            "port":     int(os.getenv("SITE_DB_PORT", "3306")),
            "user":     os.getenv("SITE_DB_USER", ""),
            "password": os.getenv("SITE_DB_PASSWORD", ""),
            "database": os.getenv("SITE_DB_NAME", ""),
            "charset":  "utf8mb4",
            "autocommit": True,
        }
        if not db_cfg["user"] or not db_cfg["database"]:
            msg = "Credenziali DB non configurate (SITE_DB_USER/SITE_DB_NAME) — reset DB saltato."
            reset_logger.warning(msg)
            print(f"⚠  {msg}")
        else:
            try:
                conn = pymysql.connect(**db_cfg)
                with conn:
                    cur = conn.cursor()
                    for tabella in ("enti", "dataset_files", "pipeline_runs"):
                        cur.execute(f"DELETE FROM `{tabella}`")
                        n = cur.rowcount
                        reset_logger.info(f"DELETE FROM {tabella}: {n} righe cancellate.")
                        print(f"✓ Tabella {tabella}: {n} righe cancellate.")
            except Exception as exc:
                reset_logger.error(f"Errore reset DB: {exc}")
                print(f"✗ Errore reset DB: {exc}")

    reset_logger.info("Reset completato.")
    print(f"\n✓ Reset completato. Log: {log_path}\n")
    return True


# ============================================================================
# MANUTENZIONE — file lock
# ============================================================================

def _lock_path(root_dir: str) -> str:
    """Restituisce il percorso del file lock (da env o default)."""
    return os.environ.get(
        "PIPELINE_LOCK_PATH",
        os.path.join(root_dir, _DEFAULT_LOCK_FILENAME),
    )


def manutenzione_attiva(root_dir: str, anni=None, steps=None) -> None:
    """
    Crea il file lock della manutenzione.
    Se il file esiste già (pipeline già in corso), avverte ma non blocca
    (due run paralleli sono scoraggiati ma non impossibili).
    """
    path = _lock_path(root_dir)
    payload = {
        "avviato_il": datetime.datetime.now().isoformat(),
        "pid":        os.getpid(),
        "anni":       anni or [],
        "steps":      steps or [],
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        logging.info(f"[MANUTENZIONE] Attivata — lock: {path}")
    except OSError as e:
        logging.warning(f"[MANUTENZIONE] Impossibile creare lock: {e}")


def manutenzione_disattiva(root_dir: str) -> None:
    """Rimuove il file lock, concludendo la manutenzione."""
    path = _lock_path(root_dir)
    try:
        if os.path.isfile(path):
            os.remove(path)
            logging.info("[MANUTENZIONE] Disattivata.")
    except OSError as e:
        logging.warning(f"[MANUTENZIONE] Impossibile rimuovere lock: {e}")


# ============================================================================
# FILE SENTINELLA .done  (modalità --ciclo)
# ============================================================================

def _stato_dir(root_dir: str) -> str:
    """Cartella dove vengono scritti i file .done."""
    d = os.path.join(root_dir, "Dati", ".stato")
    os.makedirs(d, exist_ok=True)
    return d


def _done_path(root_dir: str, anno: int, step: str) -> str:
    return os.path.join(_stato_dir(root_dir), f"{anno}_{step}.done")


def _is_done(root_dir: str, anno: int, step: str) -> bool:
    return os.path.isfile(_done_path(root_dir, anno, step))


def _mark_done(root_dir: str, anno: int, step: str) -> None:
    with open(_done_path(root_dir, anno, step), "w") as f:
        f.write(datetime.datetime.now().isoformat())
    logging.debug(f"[CICLO] {anno}/{step} → .done")


def _clear_done(root_dir: str, anno: int, step: str) -> None:
    p = _done_path(root_dir, anno, step)
    if os.path.isfile(p):
        os.remove(p)


# ============================================================================
# ESECUZIONE STEP (helper estraibile per retry e per-anno)
# ============================================================================

def _build_step_cmds(
    steps, anni, args, root_dir,
    skip_download_completo, skip_download_categorie,
    smart_anni_download, smart_anni_categorie,
    report_anni, sheet_id, input_path, source,
    _timeout_fn,
):
    """
    Ritorna un dict ordinato {step_name: (label, cmd, timeout)} per gli step
    richiesti. Tutti i parametri sono già risolti da main().
    """
    cmds = {}

    if "download" in steps:
        cmd = [PYTHON, "cinque_per_mille.py", "--source", source]
        _anni_dl = smart_anni_download if smart_anni_download is not None else anni
        if _anni_dl:
            cmd += ["--anni", _anni_dl]
        if skip_download_completo:
            cmd.append("--no-download")
        label = (
            "Estrazione (elenco complessivo)"
            if skip_download_completo
            else "Download + Estrazione (elenco complessivo)"
        )
        cmds["download"] = (label, cmd, _timeout_fn("download"))

    if "categorie" in steps:
        cmd = [PYTHON, "scarica_categorie.py", "--input", input_path, "--source", source]
        _anni_cat = smart_anni_categorie if smart_anni_categorie is not None else anni
        if _anni_cat:
            cmd += ["--anni", _anni_cat]
        if skip_download_categorie:
            cmd.append("--no-download")
        label = (
            "Estrazione (per categoria)"
            if skip_download_categorie
            else "Download + Estrazione (per categoria)"
        )
        cmds["categorie"] = (label, cmd, _timeout_fn("categorie"))

    if "etl" in steps:
        cmd = [PYTHON, "etl.py"]
        if anni:
            cmd += ["--anni", anni]
        if getattr(args, "no_runts", False):
            cmd.append("--no-runts")
        if getattr(args, "no_excel_etl", False):
            cmd.append("--no-excel")
        cmd.append("--aggiorna-db")
        cmds["etl"] = ("ETL (normalizzazione + export + DB per-anno)", cmd, _timeout_fn("etl"))

    if "report" in steps and report_anni:
        cmd = [PYTHON, "report.py", "--anno", report_anni]
        if getattr(args, "no_confronto", False):
            cmd.append("--no-confronto")
        cmds["report"] = ("Report Excel (stile ASSIF)", cmd, _timeout_fn("report"))

    if "gsheets" in steps:
        cmd = [PYTHON, "gsheets.py"]
        if sheet_id:
            cmd += ["--sheet-id", sheet_id]
        if anni:
            cmd += ["--anni", anni]
        cmds["gsheets"] = ("Upload Google Sheets", cmd, _timeout_fn("gsheets"))

    return cmds


def _esegui_steps(cmds: dict, root_dir: str) -> dict:
    """
    Esegue la lista di step (da _build_step_cmds) e restituisce
    results = {step_name: (ok, durata_secs)}.
    """
    results = {}
    for step_name, (label, cmd, timeout) in cmds.items():
        ok, dur = run_step(label, cmd, root_dir, timeout=timeout)
        results[step_name] = (ok, dur)
    return results


# ============================================================================
# MODALITÀ CICLO
# ============================================================================

_CICLO_DEFAULTS_FILE = "ciclo_defaults.yaml"


def _ciclo_defaults_path(root_dir: str) -> str:
    return os.path.join(root_dir, _CICLO_DEFAULTS_FILE)


def _controlla_aggiornamento_elenco(root_dir: str, anno: int) -> bool:
    """
    Confronta i nomi dei file attesi dalla pagina AdE con quelli presenti in {anno}/.
    Se trova file online che non esistono localmente → invalida download.done e etl.done
    e restituisce True.  In caso di errore di rete o di importazione restituisce False
    (comportamento sicuro: non forza un re-download inutile).
    """
    try:
        import requests as _req
        from cinque_per_mille import (
            find_download_links, sanitize_filename, YEAR_URLS, HEADERS,
        )
    except ImportError as e:
        logging.debug(f"[CICLO] check_elenco({anno}): import fallito ({e})")
        return False

    url = YEAR_URLS.get(anno)
    if not url:
        return False

    try:
        session = _req.Session()
        session.headers.update(HEADERS)
        links = find_download_links(url, session)
        nomi_online: set[str] = set()
        for ext in ("pdf", "csv"):
            for idx, u in enumerate(links.get(ext, []), 1):
                nomi_online.add(sanitize_filename(u, idx, ext))

        if not nomi_online:
            return False

        local_folder = os.path.join(root_dir, str(anno))
        local_files = set(os.listdir(local_folder)) if os.path.isdir(local_folder) else set()
        nuovi = sorted(nomi_online - local_files)

        if nuovi:
            logging.info(
                f"[CICLO] {anno}/download: file aggiornati su AdE → {nuovi}\n"
                f"[CICLO] {anno}/download: invalido .done, rieseguo download e ETL"
            )
            _clear_done(root_dir, anno, "download")
            _clear_done(root_dir, anno, "etl")
            return True

        logging.debug(f"[CICLO] check_elenco({anno}): nessun file nuovo ({len(nomi_online)} trovati online)")
        return False

    except Exception as e:
        logging.warning(f"[CICLO] check_elenco({anno}): errore rete ({e}) — skip check, mantengo .done")
        return False


def _controlla_aggiornamento_categorie(root_dir: str, anno: int, input_path: str) -> bool:
    """
    Confronta i nomi dei file di categoria attesi (da categorie.xlsx + pagine AdE)
    con i file presenti in {anno}/{slug}/.
    Se trova file nuovi → invalida categorie.done e etl.done, restituisce True.
    In caso di errore restituisce False (skip sicuro).
    """
    if not os.path.isfile(input_path):
        return False

    try:
        import requests as _req
        from scarica_categorie import (
            load_links,
            smart_filename as _smart_fn,
            _is_direct_file_url,
            _detect_file_ext,
            find_download_links as _find_links,
            HEADERS as _CAT_HEADERS,
        )
    except ImportError as e:
        logging.debug(f"[CICLO] check_categorie({anno}): import fallito ({e})")
        return False

    try:
        entries = [r for r in load_links(input_path) if int(r["anno"]) == anno]
    except Exception as e:
        logging.warning(f"[CICLO] check_categorie({anno}): errore lettura links ({e})")
        return False

    if not entries:
        return False

    session = _req.Session()
    session.headers.update(_CAT_HEADERS)
    nuovi_totali: list[str] = []

    for entry in entries:
        slug = entry["slug"]
        url  = entry["url"]
        local_folder = os.path.join(root_dir, str(anno), slug)
        local_files  = set(os.listdir(local_folder)) if os.path.isdir(local_folder) else set()
        try:
            nomi_online: set[str] = set()
            if _is_direct_file_url(url):
                ext = _detect_file_ext(url, session) or "csv"
                nomi_online.add(_smart_fn(url, 1, ext))
            else:
                links = _find_links(url, session)
                for ext in ("pdf", "csv"):
                    for idx, u in enumerate(links.get(ext, []), 1):
                        nomi_online.add(_smart_fn(u, idx, ext))

            nuovi = sorted(nomi_online - local_files)
            if nuovi:
                nuovi_totali.extend(f"{slug}/{n}" for n in nuovi)
        except Exception as e:
            logging.debug(f"[CICLO] check_categorie({anno}/{slug}): {e}")

    if nuovi_totali:
        logging.info(
            f"[CICLO] {anno}/categorie: file aggiornati su AdE → {nuovi_totali}\n"
            f"[CICLO] {anno}/categorie: invalido .done, rieseguo download e ETL"
        )
        _clear_done(root_dir, anno, "categorie")
        _clear_done(root_dir, anno, "etl")
        return True

    logging.debug(f"[CICLO] check_categorie({anno}): nessun file nuovo")
    return False


def _carica_ciclo_defaults(root_dir: str) -> dict | None:
    """
    Legge ciclo_defaults.yaml.
    Ritorna il dict di configurazione, o None se il file non esiste.
    """
    path = _ciclo_defaults_path(root_dir)
    if not os.path.isfile(path):
        return None
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.warning(f"[CICLO] Impossibile leggere {path}: {e}")
        return None


def _salva_ciclo_defaults(root_dir: str, cfg: dict) -> None:
    path = _ciclo_defaults_path(root_dir)
    try:
        import yaml
        header = (
            "# Configurazione automatica della modalità --ciclo.\n"
            "# Generato al primo lancio interattivo; modificabile a mano.\n"
            "# Cancella questo file per rifare la configurazione guidata.\n\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logging.info(f"[CICLO] Configurazione salvata in {path}")
        print(f"\n  ✓ Salvato in {path}")
        print("  Per riconfigurare: cancella il file e rilancia oppure editalo direttamente.\n")
    except Exception as e:
        logging.warning(f"[CICLO] Impossibile salvare {path}: {e}")


def _chiedi_e_salva_ciclo_defaults(root_dir: str, source_cli: str) -> dict:
    """
    Configurazione interattiva del ciclo (solo al primo lancio).
    Chiede all'utente tutti i parametri, li salva e li ritorna.
    """
    print("\n" + "─" * 60)
    print("  PRIMA CONFIGURAZIONE CICLO")
    print("  Le risposte saranno salvate per i lanci successivi (cron, script…).")
    print("─" * 60)

    # Anni
    print("\nAnni da elaborare (es. 2024  oppure  2022,2023,2024)")
    resp = input("Invio = TUTTI gli anni disponibili: ").strip()
    anni_def = resp if resp and resp.lower() != "tutti" else None

    # Fonte dati
    sorgenti = ("pdf", "web")
    print(f"\nFonte dati: pdf  web")
    resp = input(f"Scelta [{source_cli}]: ").strip().lower()
    source_def = resp if resp in sorgenti else source_cli

    # Report finale
    do_report = ask_yes_no("\nGenerare report Excel al termine del ciclo?", default="n")
    no_confront = False
    if do_report:
        no_confront = not ask_yes_no("Includere confronto con anno precedente?", default="s")

    cfg = {
        "anni":         anni_def,
        "source":       source_def,
        "report":       do_report,
        "no_confronto": no_confront,
    }
    _salva_ciclo_defaults(root_dir, cfg)
    return cfg


def _anni_ciclo(root_dir: str, anni_arg: str | None) -> list[int]:
    """Restituisce la lista anni da processare (recente → antico)."""
    if anni_arg:
        return sorted(
            [int(a.strip()) for a in anni_arg.split(",") if a.strip()],
            reverse=True,
        )
    from pipeline_checker import ANNI_DISPONIBILI
    return sorted(ANNI_DISPONIBILI, reverse=True)


def _esegui_ciclo(args, root_dir: str, anni: str | None, source: str,
                  input_path: str, _timeout_fn, log_file: str) -> None:
    """
    Modalità ciclo incrementale:

    FASE 1 — Download (tutti gli anni, solo se mancanti)
      Per ogni anno (recente → antico):
        1a. Scarica elenco complessivo  → se non .done
        1b. Scarica categorie           → se non .done

    FASE 2 — Elaborazione (anno per anno)
      Per ogni anno (recente → antico):
        2a. ETL                         → se non .done
        2b. Aggiorna DB (UPSERT)        → se ETL appena fatto

    FASE 3 — Finalizzazione (una sola volta)
        3a. Ricalcola ripartizioni + runts + registra pipeline_run
        3b. Report (se richiesto)

    Nessuna manutenzione attivata: UPSERT garantisce sempre dati coerenti.
    """
    import pathlib

    pcfg     = _load_pipeline_config(root_dir)
    dati_dir = pathlib.Path(pcfg.get("dati_dir", os.path.join(root_dir, "Dati")))
    csv_path = dati_dir / "enti_5x1000_norm.csv"

    # ------------------------------------------------------------------
    # Carica (o crea) la configurazione del ciclo
    # ------------------------------------------------------------------
    defaults = _carica_ciclo_defaults(root_dir)

    if defaults is None:
        if sys.stdin.isatty():
            # Prima esecuzione interattiva: chiedi e salva
            defaults = _chiedi_e_salva_ciclo_defaults(root_dir, source)
        else:
            # Stdin non disponibile (cron/script) e nessun file → usa built-in
            logging.warning(
                f"[CICLO] {_CICLO_DEFAULTS_FILE} non trovato e stdin non interattivo. "
                "Uso default built-in (tutti gli anni, source=pdf, no report). "
                f"Per configurare: lancia 'python pipeline.py --ciclo' in modo interattivo."
            )
            defaults = {"anni": None, "source": "pdf", "report": False, "no_confronto": False}

    # CLI args espliciti hanno sempre la precedenza sui defaults salvati
    anni_eff   = anni   if anni   is not None else defaults.get("anni")
    source_eff = source if source != "pdf"    else defaults.get("source", "pdf")
    do_report  = bool(defaults.get("report", False))
    no_confront = bool(defaults.get("no_confronto", False))

    logging.info(
        f"[CICLO] Config: anni={anni_eff or 'tutti'}  source={source_eff}  "
        f"report={do_report}  no_confronto={no_confront}"
    )

    anni_iter   = _anni_ciclo(root_dir, anni_eff)
    total_start = time.time()
    results: dict = {}

    logging.info(f"\n{'='*60}")
    logging.info(f"MODALITÀ CICLO — {len(anni_iter)} anni ({anni_iter[-1]}–{anni_iter[0]})")
    logging.info(f"Sito rimane attivo durante l'elaborazione (UPSERT)")
    logging.info(f"{'='*60}")

    # ------------------------------------------------------------------
    # FASE 0: Metadata (scraping date AdE)
    # ------------------------------------------------------------------
    if not getattr(args, "skip_metadata", False):
        logging.info("\n[CICLO] ── FASE 0: Metadata ──")
        anni_str = ",".join(str(a) for a in anni_iter) if anni_iter else ""
        cmd = [PYTHON, "ade_metadata_scraper.py"]
        if anni_str:
            cmd.extend(["--anni", anni_str])
        ok, dur = run_step("Scraping metadati AdE", cmd, root_dir, timeout=_timeout_fn("metadata"))
        results["metadata"] = (ok, dur)
        if not ok:
            logging.warning("[CICLO] Metadata fallito, continuo con i download...")
    else:
        logging.info("\n[CICLO] ── FASE 0: Metadata — SALTATO (--skip-metadata)")

    # ------------------------------------------------------------------
    # FASE 1: Download
    # ------------------------------------------------------------------
    logging.info("\n[CICLO] ── FASE 1: Download ──")

    for anno in anni_iter:
        # 1a. Elenco complessivo
        if _is_done(root_dir, anno, "download"):
            # Controlla se AdE ha pubblicato file nuovi/diversi rispetto a quelli locali.
            # Se sì, il check invalida il .done e il blocco sottostante rieseguirà il download.
            _controlla_aggiornamento_elenco(root_dir, anno)

        if _is_done(root_dir, anno, "download"):
            logging.info(f"[CICLO] {anno}/download → già fatto, skip")
        else:
            cmd = [PYTHON, "cinque_per_mille.py", "--source", source_eff, "--anni", str(anno), "--yes"]
            ok, dur = run_step(f"Download elenco {anno}", cmd, root_dir,
                               timeout=_timeout_fn("download"))
            results[f"download_{anno}"] = (ok, dur)
            if ok:
                _mark_done(root_dir, anno, "download")
            else:
                logging.warning(f"[CICLO] {anno}/download fallito — continuo con gli altri anni")

        # 1b. Categorie
        if _is_done(root_dir, anno, "categorie"):
            # Stessa logica: verifica se ci sono file di categoria nuovi su AdE.
            _controlla_aggiornamento_categorie(root_dir, anno, input_path)

        if _is_done(root_dir, anno, "categorie"):
            logging.info(f"[CICLO] {anno}/categorie → già fatto, skip")
        elif not os.path.isfile(input_path):
            logging.warning(f"[CICLO] {anno}/categorie → file input non trovato, skip")
        else:
            cmd = [PYTHON, "scarica_categorie.py",
                   "--input", input_path, "--source", source_eff, "--anni", str(anno)]
            ok, dur = run_step(f"Categorie {anno}", cmd, root_dir,
                               timeout=_timeout_fn("categorie"))
            results[f"categorie_{anno}"] = (ok, dur)
            if ok:
                _mark_done(root_dir, anno, "categorie")
            else:
                logging.warning(f"[CICLO] {anno}/categorie fallito — continuo")

    # ------------------------------------------------------------------
    # FASE 2: Elaborazione anno per anno
    # ------------------------------------------------------------------
    logging.info("\n[CICLO] ── FASE 2: Elaborazione ──")

    anni_db: list[int] = []

    for anno in anni_iter:
        if _is_done(root_dir, anno, "etl"):
            logging.info(f"[CICLO] {anno}/etl → già fatto, skip")
            anni_db.append(anno)
            continue

        # ETL per questo anno (--aggiorna-db NON usato qui: usiamo UPSERT custom)
        cmd = [PYTHON, "etl.py", "--anni", str(anno)]
        if getattr(args, "no_runts", False):
            cmd.append("--no-runts")
        if getattr(args, "no_excel_etl", False):
            cmd.append("--no-excel")

        ok, dur = run_step(f"ETL {anno}", cmd, root_dir, timeout=_timeout_fn("etl"))
        results[f"etl_{anno}"] = (ok, dur)

        if not ok:
            logging.warning(f"[CICLO] {anno}/etl fallito — DB non aggiornato per questo anno")
            continue

        # Verifica che l'ETL abbia davvero prodotto righe per questo anno nel CSV.
        # (L'ETL esce con 0 anche se crasha su un anno specifico.)
        righe_anno = 0
        if csv_path.exists():
            try:
                import pandas as _pd
                _sample = _pd.read_csv(csv_path, usecols=["ANNO"], dtype=str)
                righe_anno = int((_sample["ANNO"].str.strip() == str(anno)).sum())
            except Exception:
                pass
        if righe_anno == 0:
            logging.error(
                f"[CICLO] {anno}/etl: exit 0 ma 0 righe nel CSV → ETL interno fallito, "
                f"controlla il log ETL. DB non aggiornato, .done non scritto."
            )
            results[f"etl_{anno}"] = (False, dur)
            continue

        # Aggiorna DB via UPSERT (sito sempre attivo)
        logging.info(f"[CICLO] {anno} → aggiornamento DB (UPSERT, {righe_anno:,} righe)...")
        try:
            from db_updater import aggiorna_anno_ciclo
            ok_db = aggiorna_anno_ciclo(anno=anno, csv_path=csv_path, dati_dir=dati_dir)
            if ok_db:
                _mark_done(root_dir, anno, "etl")
                anni_db.append(anno)
                logging.info(f"[CICLO] {anno} → DB aggiornato")
            else:
                logging.warning(f"[CICLO] {anno} → DB non aggiornato (configurazione mancante?)")
        except Exception as _e:
            logging.warning(f"[CICLO] {anno} → DB update fallito: {_e}")

    # ------------------------------------------------------------------
    # FASE 3: Finalizzazione
    # ------------------------------------------------------------------
    logging.info("\n[CICLO] ── FASE 3: Finalizzazione ──")

    if anni_db:
        try:
            from db_updater import finalizza_ciclo
            ok_fin = finalizza_ciclo(
                anni_processati=anni_db,
                csv_path=csv_path,
                dati_dir=dati_dir,
                t_inizio=total_start,
            )
            results["finalizzazione"] = (ok_fin, 0)
            if ok_fin:
                logging.info("[CICLO] Finalizzazione completata (ripartizioni, runts, pipeline_run)")
        except Exception as _e:
            logging.warning(f"[CICLO] Finalizzazione fallita: {_e}")
            results["finalizzazione"] = (False, 0)

    # Report (opzionale, una sola volta — guidato dal defaults salvato)
    if do_report and anni_db:
        report_anno_str = str(max(anni_db))
        cmd = [PYTHON, "report.py", "--anno", report_anno_str]
        if no_confront:
            cmd.append("--no-confronto")
        ok, dur = run_step(f"Report {report_anno_str}", cmd, root_dir,
                           timeout=_timeout_fn("report"))
        results[f"report_{report_anno_str}"] = (ok, dur)

    # ------------------------------------------------------------------
    # Riepilogo
    # ------------------------------------------------------------------
    total_elapsed = time.time() - total_start
    all_ok = all(ok for ok, _ in results.values()) if results else True
    failed = [s for s, (ok, _) in results.items() if not ok]

    print()
    logging.info("=" * 60)
    logging.info("RIEPILOGO CICLO")
    logging.info("=" * 60)
    for step_name, (ok, dur) in results.items():
        logging.info(f"  {step_name:<45} [{'OK' if ok else 'ERRORE'}] ({dur:.0f}s)")
    logging.info(f"\nAnni DB aggiornati: {anni_db}")
    logging.info(f"Tempo totale: {total_elapsed:.0f}s")
    if all_ok:
        logging.info("Ciclo completato con successo!")
    else:
        logging.warning(f"Ciclo completato con errori in: {failed}")
    logging.info(f"Log completo: {log_file}")
    logging.info("=" * 60)

    sys.exit(0 if all_ok else 1)


# ============================================================================
# MAIN
# ============================================================================

def main():
    args = parse_args()

    root_dir = os.path.dirname(os.path.abspath(__file__))

    # ── Reset (se richiesto) ─────────────────────────────────────────────────
    if args.reset or args.reset_db:
        eseguito = reset_tutto(
            root_dir,
            solo_db=args.reset_db and not args.reset,
            force=args.force,
        )
        if not eseguito:
            sys.exit(0)
        # Se non è stato passato anche un altro flag operativo, termina qui
        # (il reset da solo non avvia la pipeline)
        operativo = (
            args.anni or args.only or args.skip_download is False
            or getattr(args, "smart", False)
        )
        if not operativo and not args.anni:
            print("Reset completato. Passa --anni o altri flag per avviare la pipeline.")
            sys.exit(0)

    # --report-only è una scorciatoia per --only report
    if args.report_only and not args.only:
        args.only = "report"

    log_file = setup_logging(root_dir)

    # Carica config pipeline
    pcfg = _load_pipeline_config(root_dir)

    # Timeout per step (secondi) — da config.yaml o default
    _step_timeouts_cfg = pcfg.get("step_timeouts", {})
    def _timeout(step_name):
        return int(_step_timeouts_cfg.get(step_name, _DEFAULT_STEP_TIMEOUT))

    print("\n" + "=" * 60)
    print("  5 PER MILLE - PIPELINE COMPLETA")
    print("=" * 60)

    # ---- Determina step da eseguire ----
    if args.only:
        steps = [s.strip().lower() for s in args.only.split(",")]
        invalid = [s for s in steps if s not in STEPS_ALL]
        if invalid:
            logging.error(f"Step non validi: {invalid}. Disponibili: {STEPS_ALL}")
            sys.exit(1)
    else:
        steps = list(STEPS_ALL)
        if args.skip_download:
            steps = [s for s in steps if s != "download"]
        if args.skip_gsheets:
            steps = [s for s in steps if s != "gsheets"]
        if args.skip_report:
            steps = [s for s in steps if s != "report"]

    logging.info(f"Step da eseguire: {steps}")

    # ---- Parametri comuni ----
    anni = args.anni
    source = args.source
    input_file = args.input or pcfg.get("input_categorie", DEFAULT_INPUT)
    sheet_id = args.sheet_id or pcfg.get("sheet_id")

    # Se non ci sono anni da CLI, chiedi interattivamente (non in --ciclo: gestisce da solo)
    if not anni and sys.stdin.isatty() and not args.ciclo:
        resp = input("\nAnni da elaborare (es. 2023,2024 o 'tutti'): ").strip()
        if resp and resp.lower() != "tutti":
            anni = resp

    # Chiedi separatamente per i due tipi di download
    skip_download_completo = args.skip_download
    skip_download_categorie = args.skip_download

    if sys.stdin.isatty() and not args.skip_download and not args.ciclo:
        if "download" in steps:
            if not ask_yes_no("\nScaricare le LISTE COMPLETE dall'AdE? (cinque_per_mille.py)"):
                skip_download_completo = True
        if "categorie" in steps:
            if not ask_yes_no("Scaricare i dati PER CATEGORIA? (scarica_categorie.py)"):
                skip_download_categorie = True

    # Se gsheets e' negli step, chiedi se eseguirlo e l'eventuale sheet_id
    if "gsheets" in steps and sys.stdin.isatty() and not args.ciclo:
        if not ask_yes_no("\nEseguire l'upload su Google Sheets? (gsheets.py)", default="n"):
            steps = [s for s in steps if s != "gsheets"]
        elif not sheet_id:
            sheet_id = input("ID del Google Sheet (lascia vuoto per crearne uno nuovo): ").strip()
            if not sheet_id:
                sheet_id = None

    # Se report e' negli step, determina anni per il report
    report_anni = None
    if "report" in steps:
        if args.anno_confronto:
            # Flag esplicito --anno-confronto
            anni_list = sorted([a.strip() for a in anni.split(",") if a.strip()]) if anni else []
            a = anni_list[-1] if anni_list else None
            if a:
                report_anni = f"{a},{args.anno_confronto}"
        elif anni:
            anni_list = sorted([a.strip() for a in anni.split(",") if a.strip()])
            ultimo = anni_list[-1]  # anno piu' recente

            if args.no_confronto:
                report_anni = ultimo
            elif len(anni_list) == 1:
                # Un solo anno: confronto con anno-1 (default di report.py)
                report_anni = ultimo
            elif sys.stdin.isatty() and not args.ciclo:
                # Piu' anni e modalita' interattiva: chiedi quale anno per il report
                penultimo = anni_list[-2]
                default_choice = f"{ultimo},{penultimo}"
                print(f"\nAnni per il report (dati disponibili: {','.join(anni_list)}):")
                print(f"  {ultimo},{penultimo}  → report {ultimo} con confronto {penultimo} (default)")
                print(f"  {ultimo}       → report {ultimo} con confronto {int(ultimo)-1} (anno-1)")
                print(f"  no         → salta il report")
                resp = input(f"Scelta [{default_choice}]: ").strip()
                if resp.lower() == "no":
                    report_anni = None
                elif resp:
                    report_anni = resp
                else:
                    report_anni = default_choice
            else:
                # Non interattivo (o --ciclo) con piu' anni: usa il piu' recente
                report_anni = ultimo
        elif sys.stdin.isatty() and not args.ciclo:
            # Nessun --anni specificato, chiedi tutto da zero
            print("\nAnni per il report:")
            print("  2024,2023  → report 2024, confronto con 2023")
            print("  2024       → report 2024, confronto con 2023 (anno-1)")
            print("  no         → salta il report")
            resp = input("Scelta: ").strip()
            if resp.lower() == "no":
                report_anni = None
            elif resp:
                report_anni = resp

    # Verifica file input categorie
    input_path = os.path.join(root_dir, input_file) if not os.path.isabs(input_file) else input_file
    if "categorie" in steps and not os.path.isfile(input_path):
        logging.error(f"File categorie non trovato: {input_path}")
        logging.error("Specifica il percorso con --input o in config.yaml (pipeline.input_categorie)")
        if "categorie" in steps:
            steps.remove("categorie")
            logging.warning("Step 'categorie' rimosso dalla pipeline")

    # ---- Override espliciti anni per step specifici ----
    smart_anni_download  = args.anni_download   # None = usa anni originali / smart
    smart_anni_categorie = args.anni_categorie
    _skip_etl_smart      = False

    if args.smart:
        try:
            from pipeline_checker import full_analysis
            anni_list = [int(a.strip()) for a in anni.split(",") if a.strip()] if anni else None
            check = full_analysis(root_dir, anni_list)

            logging.info("\n[SMART] Analisi file esistenti:")
            logging.info(f"  Download:   {check['riepilogo']['download']}")
            logging.info(f"  Categorie:  {check['riepilogo']['categorie']}")
            logging.info(f"  ETL:        {check['riepilogo']['etl']}")

            # Download: scarica solo gli anni mancanti (solo se non c'è override esplicito)
            if "download" in steps and smart_anni_download is None:
                mancanti = check["anni_mancanti_download"]
                if not mancanti:
                    logging.info("[SMART] Step 'download' saltato: tutti gli anni già presenti.")
                    steps = [s for s in steps if s != "download"]
                else:
                    smart_anni_download = ",".join(str(a) for a in mancanti)
                    logging.info(f"[SMART] Download solo per anni mancanti: {mancanti}")

            # Categorie: elabora solo gli anni con file mancanti (solo se non c'è override esplicito)
            if "categorie" in steps and smart_anni_categorie is None:
                mancanti_cat = check["anni_mancanti_categorie"]
                if not mancanti_cat:
                    logging.info("[SMART] Step 'categorie' saltato: tutti gli anni già presenti.")
                    steps = [s for s in steps if s != "categorie"]
                else:
                    smart_anni_categorie = ",".join(str(a) for a in mancanti_cat)
                    logging.info(f"[SMART] Categorie solo per anni mancanti: {mancanti_cat}")

            # ETL: salta se CSV è aggiornato e non ci sono nuovi input
            if "etl" in steps and check["etl"]["status"] == "ok":
                if not check["anni_mancanti_download"] and not check["anni_mancanti_categorie"]:
                    logging.info("[SMART] Step 'etl' saltato: CSV normalizzato aggiornato.")
                    steps = [s for s in steps if s != "etl"]

        except Exception as _e:
            logging.warning(f"[SMART] Analisi non riuscita ({_e}), eseguo tutto normalmente.")

    # ---- Riepilogo ----
    logging.info(f"\nConfigurazione pipeline:")
    logging.info(f"  Root:       {root_dir}")
    logging.info(f"  Step:       {steps}")
    logging.info(f"  Anni:       {anni or 'tutti'}")
    logging.info(f"  Fonte:      {source}")
    if "download" in steps:
        logging.info(f"  Download:   {'solo estrazione' if skip_download_completo else 'download + estrazione'} (liste complete)")
    if "categorie" in steps:
        logging.info(f"  Categorie:  {'solo estrazione' if skip_download_categorie else 'download + estrazione'} (per categoria)")
        logging.info(f"  Input cat:  {input_path}")
    if "report" in steps:
        if report_anni:
            parts = [p.strip() for p in report_anni.split(",")]
            if len(parts) >= 2:
                logging.info(f"  Report:     anno {parts[0]}, confronto con {parts[1]}")
            elif args.no_confronto:
                logging.info(f"  Report:     anno {parts[0]}, senza confronto YoY")
            else:
                logging.info(f"  Report:     anno {parts[0]}, confronto con anno-1")
        else:
            logging.info(f"  Report:     saltato (nessun anno)")
    if "gsheets" in steps:
        logging.info(f"  Sheet ID:   {sheet_id or '(nuovo)'}")

    # ================================================================
    # MODALITÀ CICLO — gestita separatamente, senza manutenzione
    # ================================================================
    if args.ciclo:
        _esegui_ciclo(args, root_dir, anni, source, input_path, _timeout, log_file)
        return  # _esegui_ciclo chiama sys.exit internamente

    # ================================================================
    # MANUTENZIONE: attiva prima di qualsiasi step (solo modalità normale)
    # ================================================================
    anni_list_maint = [a.strip() for a in anni.split(",") if a.strip()] if anni else []
    manutenzione_attiva(root_dir, anni=anni_list_maint, steps=steps)

    total_start = time.time()
    results     = {}
    all_ok      = False
    failed: list = []

    try:
        # ============================================================
        # MODALITÀ PER-ANNO
        # ============================================================
        if args.per_anno:
            # Step per-anno (download + categorie + etl)
            steps_per_anno = [s for s in steps if s in ("download", "categorie", "etl")]
            # Step una-tantum dopo il loop (report + gsheets)
            steps_finali   = [s for s in steps if s in ("report", "gsheets")]

            # Determina lista anni da elaborare (ordine: recente → antico)
            if anni:
                anni_iter = sorted(
                    [int(a.strip()) for a in anni.split(",") if a.strip()],
                    reverse=True,
                )
            else:
                # Anni già scaricati in Dati/
                import pathlib as _pl
                _dati = _pl.Path(pcfg.get("dati_dir", os.path.join(root_dir, "Dati")))
                anni_iter = sorted(
                    [int(f.stem.split("_")[1]) for f in _dati.glob("dati_[0-9]*.xlsx")],
                    reverse=True,
                )
                if not anni_iter:
                    logging.warning("[PER-ANNO] Nessun dati_YYYY.xlsx trovato; uso anni 2006-2024")
                    anni_iter = sorted(range(2006, 2025), reverse=True)

            logging.info(f"\n[PER-ANNO] Anni da elaborare ({len(anni_iter)}): {anni_iter}")

            for anno_i in anni_iter:
                anno_s = str(anno_i)
                logging.info(f"\n{'─'*60}")
                logging.info(f"[PER-ANNO] Anno {anno_i}")
                logging.info(f"{'─'*60}")

                cmds_anno = _build_step_cmds(
                    steps       = steps_per_anno,
                    anni        = anno_s,
                    args        = args,
                    root_dir    = root_dir,
                    skip_download_completo  = skip_download_completo,
                    skip_download_categorie = skip_download_categorie,
                    smart_anni_download     = smart_anni_download,
                    smart_anni_categorie    = smart_anni_categorie,
                    report_anni = None,        # report gestito dopo
                    sheet_id    = sheet_id,
                    input_path  = input_path,
                    source      = source,
                    _timeout_fn = _timeout,
                )
                res_anno = _esegui_steps(cmds_anno, root_dir)
                for k, v in res_anno.items():
                    results[f"{k}_{anno_i}"] = v

            # Step finali (report + gsheets) — una sola volta
            if steps_finali:
                cmds_fin = _build_step_cmds(
                    steps       = steps_finali,
                    anni        = anni,
                    args        = args,
                    root_dir    = root_dir,
                    skip_download_completo  = skip_download_completo,
                    skip_download_categorie = skip_download_categorie,
                    smart_anni_download     = smart_anni_download,
                    smart_anni_categorie    = smart_anni_categorie,
                    report_anni = report_anni,
                    sheet_id    = sheet_id,
                    input_path  = input_path,
                    source      = source,
                    _timeout_fn = _timeout,
                )
                res_fin = _esegui_steps(cmds_fin, root_dir)
                results.update(res_fin)

        else:
            # ============================================================
            # MODALITÀ NORMALE CON RETRY AUTOMATICO
            # ============================================================
            max_retry   = max(1, args.max_retry)
            tentativi   = 0

            # Parametri correnti (possono cambiare tra un retry e l'altro)
            _steps               = list(steps)
            _smart_dl            = smart_anni_download
            _smart_cat           = smart_anni_categorie

            while tentativi < max_retry:
                tentativi += 1
                if tentativi > 1:
                    logging.info(f"\n{'='*60}")
                    logging.info(f"[RETRY {tentativi}/{max_retry}] Riprovo gli step pendenti...")
                    logging.info(f"{'='*60}")

                cmds = _build_step_cmds(
                    steps       = _steps,
                    anni        = anni,
                    args        = args,
                    root_dir    = root_dir,
                    skip_download_completo  = skip_download_completo,
                    skip_download_categorie = skip_download_categorie,
                    smart_anni_download     = _smart_dl,
                    smart_anni_categorie    = _smart_cat,
                    report_anni = report_anni,
                    sheet_id    = sheet_id,
                    input_path  = input_path,
                    source      = source,
                    _timeout_fn = _timeout,
                )
                res_tento = _esegui_steps(cmds, root_dir)
                # Aggiorna results (l'ultimo tentativo vince per step già visti)
                results.update(res_tento)

                # ---- Verifica se ci sono ancora pendenze ----
                if tentativi >= max_retry:
                    break  # ultimo tentativo: non controllare

                try:
                    from pipeline_checker import full_analysis
                    anni_chk = [int(a.strip()) for a in anni.split(",") if a.strip()] if anni else None
                    chk = full_analysis(root_dir, anni_chk)
                    mancanti_dl  = chk.get("anni_mancanti_download", [])
                    mancanti_cat = chk.get("anni_mancanti_categorie", [])
                    etl_ok       = chk.get("etl", {}).get("status") == "ok"

                    if not mancanti_dl and not mancanti_cat and etl_ok:
                        logging.info("[RETRY] Pipeline completa: nessuna pendenza rilevata.")
                        break

                    logging.warning(
                        f"[RETRY] Pendenze: download={mancanti_dl}, "
                        f"categorie={mancanti_cat}, etl={'ok' if etl_ok else 'NON OK'}"
                    )
                    # Prossimo tentativo: solo step mancanti (smart)
                    _steps = []
                    if mancanti_dl:
                        _steps.append("download")
                        _smart_dl = ",".join(str(a) for a in mancanti_dl)
                    if mancanti_cat:
                        _steps.append("categorie")
                        _smart_cat = ",".join(str(a) for a in mancanti_cat)
                    if not etl_ok:
                        _steps.append("etl")
                    # report e gsheets solo se erano presenti originalmente
                    if not _steps:
                        break   # nessuno step da ripetere

                except Exception as _chk_e:
                    logging.warning(f"[RETRY] Analisi pendenze non riuscita ({_chk_e}), stop retry.")
                    break

        # ================================================================
        # RIEPILOGO FINALE
        # ================================================================
        total_elapsed = time.time() - total_start
        all_ok = all(ok for ok, _ in results.values()) if results else True
        failed = [s for s, (ok, _) in results.items() if not ok]

        print()
        logging.info("=" * 60)
        logging.info("RIEPILOGO PIPELINE")
        logging.info("=" * 60)
        for step_name, (ok, dur) in results.items():
            status = "OK" if ok else "ERRORE"
            logging.info(f"  {step_name:<45} [{status}] ({dur:.0f}s)")
        logging.info(f"\nTempo totale: {total_elapsed:.0f}s")
        if all_ok:
            logging.info("Pipeline completata con successo!")
        else:
            logging.warning(f"Pipeline completata con errori in: {failed}")
        logging.info(f"Log completo: {log_file}")
        logging.info("=" * 60)

        # ----------------------------------------------------------------
        # Aggiornamento DB sito
        # ----------------------------------------------------------------
        try:
            from db_updater import aggiorna_db_sito
            import pathlib
            _cfg      = _load_pipeline_config(root_dir)
            _dati_dir = pathlib.Path(_cfg.get("dati_dir", os.path.join(root_dir, "Dati")))
            _csv_path = _dati_dir / "enti_5x1000_norm.csv"
            _anni_list = [int(a) for a in anni.split(",") if a.strip()] if anni else []
            _db_status = "ok" if all_ok else "parziale"
            _note      = f"Errori in: {failed}" if not all_ok else ""
            ok_db = aggiorna_db_sito(
                anni_processati = _anni_list,
                steps_eseguiti  = list(steps),
                csv_path        = _csv_path,
                dati_dir        = _dati_dir,
                status          = _db_status,
                note            = _note,
                t_inizio        = total_start,
            )
            if ok_db:
                logging.info("DB sito aggiornato (run registrato, file catalogo aggiornato).")
            else:
                logging.info("Aggiornamento DB sito saltato (non configurato o errore).")
        except Exception as _e:
            logging.warning(f"Aggiornamento DB sito non riuscito: {_e}")

    finally:
        # ================================================================
        # MANUTENZIONE: disattiva SEMPRE (anche in caso di crash/SIGTERM)
        # ================================================================
        manutenzione_disattiva(root_dir)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
