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

import os
import sys
import time
import argparse
import subprocess
import logging
import datetime


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

STEPS_ALL = ["download", "categorie", "etl", "report", "gsheets"]

DEFAULT_INPUT = "categorie.xlsx"

# Python eseguibile: stesso interprete che sta eseguendo questo script
PYTHON = sys.executable


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

def run_step(name, cmd, root_dir):
    """
    Esegue un comando subprocess per uno step della pipeline.
    Restituisce (success: bool, duration_secs: float).
    """
    logging.info(f"\n{'='*60}")
    logging.info(f"STEP: {name}")
    logging.info(f"Comando: {' '.join(cmd)}")
    logging.info(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=root_dir,
            timeout=3600,  # 1 ora max per step
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            logging.info(f"[OK] {name} completato in {elapsed:.0f}s")
            return True, elapsed
        else:
            logging.error(f"[ERRORE] {name} fallito (exit code {result.returncode})")
            return False, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        logging.error(f"[TIMEOUT] {name} interrotto dopo {elapsed:.0f}s")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"[ERRORE] {name}: {e}")
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
        "--source", choices=["csv", "pdf"], default="csv",
        help="Fonte dati per estrazione: 'csv' (default) o 'pdf'",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help=f"File Excel con link categorie (default: {DEFAULT_INPUT} o da config.yaml)",
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
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

def main():
    args = parse_args()

    root_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = setup_logging(root_dir)

    # Carica config pipeline
    pcfg = _load_pipeline_config(root_dir)

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

    # Se non ci sono anni da CLI, chiedi interattivamente
    if not anni and sys.stdin.isatty():
        resp = input("\nAnni da elaborare (es. 2023,2024 o 'tutti'): ").strip()
        if resp and resp.lower() != "tutti":
            anni = resp

    # Se gsheets e' negli step ma non c'e' sheet_id, chiedi
    if "gsheets" in steps and not sheet_id and sys.stdin.isatty():
        sheet_id = input("\nID del Google Sheet (lascia vuoto per crearne uno nuovo): ").strip()
        if not sheet_id:
            sheet_id = None

    # Verifica file input categorie
    input_path = os.path.join(root_dir, input_file) if not os.path.isabs(input_file) else input_file
    if "categorie" in steps and not os.path.isfile(input_path):
        logging.error(f"File categorie non trovato: {input_path}")
        logging.error("Specifica il percorso con --input o in config.yaml (pipeline.input_categorie)")
        if "categorie" in steps:
            steps.remove("categorie")
            logging.warning("Step 'categorie' rimosso dalla pipeline")

    # ---- Riepilogo ----
    logging.info(f"\nConfigurazione pipeline:")
    logging.info(f"  Root:       {root_dir}")
    logging.info(f"  Step:       {steps}")
    logging.info(f"  Anni:       {anni or 'tutti'}")
    logging.info(f"  Fonte:      {source}")
    if "categorie" in steps:
        logging.info(f"  Input cat:  {input_path}")
    if "gsheets" in steps:
        logging.info(f"  Sheet ID:   {sheet_id or '(nuovo)'}")

    # ---- Esecuzione step ----
    results = {}
    total_start = time.time()

    # STEP 1: Download elenco complessivo + estrazione
    if "download" in steps:
        cmd = [PYTHON, "cinque_per_mille.py", "--source", source]
        if anni:
            cmd += ["--anni", anni]
        if args.skip_download:
            cmd.append("--no-download")
        ok, dur = run_step("Download + Estrazione (elenco complessivo)", cmd, root_dir)
        results["download"] = (ok, dur)

    # STEP 2: Download categorie + estrazione
    if "categorie" in steps:
        cmd = [PYTHON, "scarica_categorie.py", "--input", input_path, "--source", source]
        if anni:
            cmd += ["--anni", anni]
        if args.skip_download:
            cmd.append("--no-download")
        ok, dur = run_step("Download + Estrazione (per categoria)", cmd, root_dir)
        results["categorie"] = (ok, dur)

    # STEP 3: ETL
    if "etl" in steps:
        cmd = [PYTHON, "etl.py"]
        if anni:
            cmd += ["--anni", anni]
        if args.no_runts:
            cmd.append("--no-runts")
        if args.no_excel_etl:
            cmd.append("--no-excel")
        ok, dur = run_step("ETL (normalizzazione + export)", cmd, root_dir)
        results["etl"] = (ok, dur)

    # STEP 4: Report Excel
    if "report" in steps:
        # Usa il primo anno dalla lista per il report
        report_anno = anni.split(",")[0].strip() if anni else None
        if report_anno:
            cmd = [PYTHON, "report.py", "--anno", report_anno]
            if args.anno_confronto:
                cmd += ["--anno-confronto", str(args.anno_confronto)]
            elif args.no_confronto:
                cmd.append("--no-confronto")
            ok, dur = run_step("Report Excel (stile ASSIF)", cmd, root_dir)
            results["report"] = (ok, dur)
        else:
            logging.warning("Report saltato: nessun anno specificato")

    # STEP 5: Google Sheets
    if "gsheets" in steps:
        cmd = [PYTHON, "gsheets.py"]
        if sheet_id:
            cmd += ["--sheet-id", sheet_id]
        if anni:
            cmd += ["--anni", anni]
        ok, dur = run_step("Upload Google Sheets", cmd, root_dir)
        results["gsheets"] = (ok, dur)

    # ---- Riepilogo finale ----
    total_elapsed = time.time() - total_start

    print()
    logging.info("=" * 60)
    logging.info("RIEPILOGO PIPELINE")
    logging.info("=" * 60)

    all_ok = True
    for step_name, (ok, dur) in results.items():
        status = "OK" if ok else "ERRORE"
        logging.info(f"  {step_name:<40} [{status}] ({dur:.0f}s)")
        if not ok:
            all_ok = False

    logging.info(f"\nTempo totale: {total_elapsed:.0f}s")

    if all_ok:
        logging.info("Pipeline completata con successo!")
    else:
        failed = [s for s, (ok, _) in results.items() if not ok]
        logging.warning(f"Pipeline completata con errori in: {failed}")

    logging.info(f"Log completo: {log_file}")
    logging.info("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
