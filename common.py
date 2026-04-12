#!/usr/bin/env python3
"""
common.py — Utilità condivise per tutta la pipeline 5×1000.

Centralizza:
  - load_config()     : carica config.yaml
  - get_logger()      : configura logging su file + console
  - ask_yes_no()      : prompt interattivo si/no
  - EXCEL_CONFIG      : stili Excel di default (sovrascrivibili da config.yaml)
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configurazione Excel (default; sovrascritta da apply_excel_config())
# ---------------------------------------------------------------------------

EXCEL_CONFIG: dict = {
    "header_font": "Arial",
    "header_size": 10,
    "header_bg": "#2F5496",
    "header_fg": "#FFFFFF",
    "data_font": "Arial",
    "data_size": 9,
    "data_size_download": 10,   # usato da cinque_per_mille.py
    "alt_row_bg": "#EEF2FF",
    "border_color": "#D9D9D9",
    "max_col_width": 40,
}

_COLOR_KEYS = {"header_bg", "header_fg", "alt_row_bg", "border_color"}


# ---------------------------------------------------------------------------
# Caricamento config.yaml
# ---------------------------------------------------------------------------

def load_config(root_dir: "str | Path") -> dict:
    """
    Carica config.yaml dalla root del progetto.
    Restituisce un dict vuoto se il file non esiste o PyYAML non è installato.
    """
    config_path = Path(root_dir) / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        logging.warning(
            "PyYAML non installato: config.yaml ignorato. "
            "Installa con: pip install pyyaml"
        )
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.warning(f"Errore nel leggere config.yaml: {e}")
        return {}


def apply_excel_config(cfg: dict) -> None:
    """
    Applica la sezione 'excel' di config.yaml a EXCEL_CONFIG.
    Chiamare dopo load_config().
    """
    excel_cfg = cfg.get("excel", {})
    if not excel_cfg:
        return

    # Mappa chiavi config.yaml → chiavi EXCEL_CONFIG
    # (alcune chiavi differiscono per motivi storici)
    yaml_to_key = {
        "header_font":       "header_font",
        "header_size":       "header_size",
        "header_bg":         "header_bg",
        "header_fg":         "header_fg",
        "data_font":         "data_font",
        "data_size_etl":     "data_size",
        "data_size_download":"data_size_download",
        "alt_row_bg":        "alt_row_bg",
        "border_color":      "border_color",
        "max_col_width":     "max_col_width",
    }
    for yaml_key, cfg_key in yaml_to_key.items():
        if yaml_key in excel_cfg:
            val = excel_cfg[yaml_key]
            if cfg_key in _COLOR_KEYS:
                val = str(val)
                if not val.startswith("#"):
                    val = f"#{val}"
            EXCEL_CONFIG[cfg_key] = val


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(module_name: str, root_dir: "str | Path") -> "tuple[logging.Logger, str]":
    """
    Configura il root logger (file + console) e restituisce (logger, log_file_path).

    Il file di log viene creato in <root_dir>/log/<module_name>_YYYYMMDD_HHMMSS.log.
    Se basicConfig è già stato chiamato (root logger ha handler), non riconfigura
    ma restituisce comunque il logger con il nome indicato.
    """
    root_dir = Path(root_dir)
    log_dir = root_dir / "log"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{module_name}_{stamp}.log"

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        logging.getLogger(module_name).info(f"Log: {log_file}")

    return logging.getLogger(module_name), str(log_file)


# ---------------------------------------------------------------------------
# Prompt interattivo
# ---------------------------------------------------------------------------

def ask_yes_no(prompt: str, default: str = "s") -> bool:
    """
    Chiede una conferma si/no. Restituisce True per sì, False per no.

    Args:
        prompt:  testo della domanda (senza suffisso [S/n])
        default: "s" (invio = sì) oppure "n" (invio = no)
    """
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


# ---------------------------------------------------------------------------
# .env loader (condiviso tra pipeline.py e forecast.py)
# ---------------------------------------------------------------------------

def load_dotenv(root_dir: "str | Path") -> None:
    """
    Carica variabili d'ambiente da <root_dir>/.env (se presente).
    Le variabili già presenti in os.environ non vengono sovrascritte.
    """
    env_path = Path(root_dir) / ".env"
    if not env_path.is_file():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
