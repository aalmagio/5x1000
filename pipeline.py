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

    # Se non ci sono anni da CLI, chiedi interattivamente
    if not anni and sys.stdin.isatty():
        resp = input("\nAnni da elaborare (es. 2023,2024 o 'tutti'): ").strip()
        if resp and resp.lower() != "tutti":
            anni = resp

    # Chiedi separatamente per i due tipi di download
    skip_download_completo = args.skip_download
    skip_download_categorie = args.skip_download

    if sys.stdin.isatty() and not args.skip_download:
        if "download" in steps:
            if not ask_yes_no("\nScaricare le LISTE COMPLETE dall'AdE? (cinque_per_mille.py)"):
                skip_download_completo = True
        if "categorie" in steps:
            if not ask_yes_no("Scaricare i dati PER CATEGORIA? (scarica_categorie.py)"):
                skip_download_categorie = True

    # Se gsheets e' negli step ma non c'e' sheet_id, chiedi
    if "gsheets" in steps and not sheet_id and sys.stdin.isatty():
        sheet_id = input("\nID del Google Sheet (lascia vuoto per crearne uno nuovo): ").strip()
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
            elif sys.stdin.isatty():
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
                # Non interattivo con piu' anni: usa il piu' recente
                report_anni = ultimo
        elif sys.stdin.isatty():
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

    # ---- Esecuzione step ----
    results = {}
    total_start = time.time()

    # STEP 1: Download elenco complessivo + estrazione
    if "download" in steps:
        cmd = [PYTHON, "cinque_per_mille.py", "--source", source]
        _anni_dl = smart_anni_download if smart_anni_download is not None else anni
        if _anni_dl:
            cmd += ["--anni", _anni_dl]
        if skip_download_completo:
            cmd.append("--no-download")
        step_label = "Estrazione (elenco complessivo)" if skip_download_completo else "Download + Estrazione (elenco complessivo)"
        ok, dur = run_step(step_label, cmd, root_dir, timeout=_timeout("download"))
        results["download"] = (ok, dur)

    # STEP 2: Download categorie + estrazione
    if "categorie" in steps:
        cmd = [PYTHON, "scarica_categorie.py", "--input", input_path, "--source", source]
        _anni_cat = smart_anni_categorie if smart_anni_categorie is not None else anni
        if _anni_cat:
            cmd += ["--anni", _anni_cat]
        if skip_download_categorie:
            cmd.append("--no-download")
        step_label = "Estrazione (per categoria)" if skip_download_categorie else "Download + Estrazione (per categoria)"
        ok, dur = run_step(step_label, cmd, root_dir, timeout=_timeout("categorie"))
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
        ok, dur = run_step("ETL (normalizzazione + export)", cmd, root_dir, timeout=_timeout("etl"))
        results["etl"] = (ok, dur)

    # STEP 4: Report Excel
    if "report" in steps:
        if report_anni:
            cmd = [PYTHON, "report.py", "--anno", report_anni]
            if args.no_confronto:
                cmd.append("--no-confronto")
            ok, dur = run_step("Report Excel (stile ASSIF)", cmd, root_dir, timeout=_timeout("report"))
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
        ok, dur = run_step("Upload Google Sheets", cmd, root_dir, timeout=_timeout("gsheets"))
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

    # ---- Aggiornamento DB sito ----
    try:
        from db_updater import aggiorna_db_sito
        import pathlib
        _cfg = _load_pipeline_config(root_dir)
        _dati_dir = pathlib.Path(_cfg.get("dati_dir", os.path.join(root_dir, "Dati")))
        _csv_path = _dati_dir / "enti_5x1000_norm.csv"
        _anni_list = [int(a) for a in anni.split(",") if a.strip()] if anni else []
        _db_status = "ok" if all_ok else "parziale"
        _note = f"Errori in: {failed}" if not all_ok else ""
        ok_db = aggiorna_db_sito(
            anni_processati=_anni_list,
            steps_eseguiti=steps,
            csv_path=_csv_path,
            dati_dir=_dati_dir,
            status=_db_status,
            note=_note,
            t_inizio=total_start,
        )
        if ok_db:
            logging.info("DB sito aggiornato con successo.")
        else:
            logging.info("Aggiornamento DB sito saltato (non configurato o errore).")
    except Exception as _e:
        logging.warning(f"Aggiornamento DB sito non riuscito: {_e}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
