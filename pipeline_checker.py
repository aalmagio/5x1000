"""
Pipeline Checker — analisi dello stato dei file scaricati/elaborati.

Determina per ogni step e ogni anno se i file sono:
  - "ok"       → presenti e aggiornati
  - "mancante" → non ancora scaricati/elaborati
  - "stale"    → presenti ma obsoleti (input più recente dell'output)

Uso standalone:
    python pipeline_checker.py
    python pipeline_checker.py --anni 2024,2023
    python pipeline_checker.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
from datetime import datetime, timezone
from typing import Optional

# Anni per i quali esiste un URL sull'AdE (2006–2024)
ANNI_DISPONIBILI = list(range(2006, 2025))

# Slug canonici delle categorie (valori di SLUG_NORMALIZE in scarica_categorie.py)
CANONICAL_SLUGS = [
    "ASD",
    "ETS_ONLUS",
    "Ricerca_scientifica",
    "Ricerca_sanitaria",
    "Comuni",
    "Beni_culturali",
    "Aree_protette",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mtime_iso(path: pathlib.Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _age_days(path: pathlib.Path) -> float:
    age_secs = datetime.now(tz=timezone.utc).timestamp() - path.stat().st_mtime
    return round(age_secs / 86400, 1)


def _load_pipeline_cfg(root_dir: pathlib.Path) -> dict:
    cfg_path = root_dir / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg
    except Exception:
        return {}


def _resolve_dati_dir(root_dir: pathlib.Path, cfg: dict) -> pathlib.Path:
    dati_rel = cfg.get("percorsi", {}).get("dati", "Dati")
    return root_dir / dati_rel


# ---------------------------------------------------------------------------
# Step 1 — download (dati_ANNO.xlsx)
# ---------------------------------------------------------------------------

def scan_download(dati_dir: pathlib.Path, anni: Optional[list[int]] = None) -> dict:
    """
    Scansiona i file dati_ANNO.xlsx in dati_dir.

    Se anni è None controlla tutti gli anni per cui esiste un URL (2006-2024).
    Restituisce: { anno: { "status": "ok"|"mancante", ... } }
    """
    anni_da_verificare = sorted(anni) if anni else ANNI_DISPONIBILI
    result = {}
    for anno in anni_da_verificare:
        f = dati_dir / f"dati_{anno}.xlsx"
        if f.exists():
            result[anno] = {
                "status": "ok",
                "file": f"dati_{anno}.xlsx",
                "mtime": _mtime_iso(f),
                "age_days": _age_days(f),
            }
        else:
            result[anno] = {"status": "mancante"}
    return result


def missing_anni_download(scan: dict) -> list[int]:
    """Anni con status != 'ok' dal risultato di scan_download."""
    return sorted(a for a, s in scan.items() if s["status"] != "ok")


# ---------------------------------------------------------------------------
# Step 2 — categorie (ANNO_SLUG_ammessi/esclusi.xlsx)
# ---------------------------------------------------------------------------

def scan_categorie(dati_dir: pathlib.Path, anni: Optional[list[int]] = None) -> dict:
    """
    Scansiona i file per categoria in dati_dir/SLUG/.

    Restituisce: { anno: { slug: { "ammessi": "ok"|"mancante", "esclusi": "ok"|"mancante" } } }
    """
    # Determina anni da verificare
    if anni:
        anni_da_verificare = sorted(anni)
    else:
        # Auto-scoperta: anni trovati nei file già presenti
        anni_set: set[int] = set()
        for slug in CANONICAL_SLUGS:
            slug_dir = dati_dir / slug
            if slug_dir.exists():
                for f in slug_dir.glob("*_ammessi.xlsx"):
                    m = re.match(r"(\d{4})_", f.name)
                    if m:
                        anni_set.add(int(m.group(1)))
        anni_da_verificare = sorted(anni_set)

    result: dict = {}
    for anno in anni_da_verificare:
        result[anno] = {}
        for slug in CANONICAL_SLUGS:
            slug_dir = dati_dir / slug
            ammessi = slug_dir / f"{anno}_{slug}_ammessi.xlsx"
            esclusi  = slug_dir / f"{anno}_{slug}_esclusi.xlsx"
            entry: dict = {
                "ammessi": "ok" if ammessi.exists() else "mancante",
                "esclusi":  "ok" if esclusi.exists()  else "mancante",
            }
            if ammessi.exists():
                entry["ammessi_mtime"] = _mtime_iso(ammessi)
            if esclusi.exists():
                entry["esclusi_mtime"] = _mtime_iso(esclusi)
            result[anno][slug] = entry
    return result


def missing_anni_categorie(scan: dict) -> list[int]:
    """Anni che hanno almeno un file ammessi mancante."""
    anni = []
    for anno, cats in scan.items():
        if any(v["ammessi"] == "mancante" for v in cats.values()):
            anni.append(anno)
    return sorted(anni)


# ---------------------------------------------------------------------------
# Step 3 — ETL (enti_5x1000_norm.csv)
# ---------------------------------------------------------------------------

def check_etl(dati_dir: pathlib.Path) -> dict:
    """
    Controlla se enti_5x1000_norm.csv è aggiornato rispetto ai dati_*.xlsx.

    status: "ok" | "mancante" | "stale"
    """
    csv_path = dati_dir / "enti_5x1000_norm.csv"

    if not csv_path.exists():
        return {"status": "mancante"}

    csv_mtime = csv_path.stat().st_mtime
    input_files = list(dati_dir.glob("dati_[0-9][0-9][0-9][0-9].xlsx"))

    if not input_files:
        return {
            "status": "ok",
            "csv_mtime": _mtime_iso(csv_path),
            "csv_age_days": _age_days(csv_path),
            "note": "nessun file dati trovato — CSV potrebbe essere vuoto",
        }

    newest_input = max(input_files, key=lambda f: f.stat().st_mtime)
    if newest_input.stat().st_mtime > csv_mtime:
        return {
            "status": "stale",
            "csv_mtime": _mtime_iso(csv_path),
            "motivo": f"{newest_input.name} è più recente del CSV normalizzato",
        }

    return {
        "status": "ok",
        "csv_mtime": _mtime_iso(csv_path),
        "csv_age_days": _age_days(csv_path),
        "n_file_input": len(input_files),
    }


# ---------------------------------------------------------------------------
# Analisi completa
# ---------------------------------------------------------------------------

def full_analysis(
    root_dir: str,
    anni: Optional[list[int]] = None,
) -> dict:
    """
    Analisi completa dello stato dei file della pipeline.

    Restituisce un dizionario con:
      - stato per ogni step
      - anni mancanti per download e categorie
      - lista degli step che è necessario (ri)eseguire
    """
    root = pathlib.Path(root_dir)
    cfg = _load_pipeline_cfg(root)
    dati_dir = _resolve_dati_dir(root, cfg)

    dl_scan  = scan_download(dati_dir, anni)
    cat_scan = scan_categorie(dati_dir, anni)
    etl_info = check_etl(dati_dir)

    anni_mancanti_dl  = missing_anni_download(dl_scan)
    anni_mancanti_cat = missing_anni_categorie(cat_scan)

    # Step necessari
    steps_necessari: list[str] = []
    if anni_mancanti_dl:
        steps_necessari.append("download")
    if anni_mancanti_cat:
        steps_necessari.append("categorie")
    if etl_info["status"] in ("mancante", "stale") or anni_mancanti_dl or anni_mancanti_cat:
        steps_necessari.append("etl")

    # Statistiche di riepilogo
    n_anni_dl_ok      = sum(1 for s in dl_scan.values()  if s["status"] == "ok")
    n_anni_cat_ok     = sum(
        1 for anno, cats in cat_scan.items()
        if all(v["ammessi"] == "ok" for v in cats.values())
    )

    return {
        "dati_dir":             str(dati_dir),
        "analizzato_at":        datetime.now(timezone.utc).isoformat(),
        "anni_richiesti":       sorted(anni) if anni else None,
        "riepilogo": {
            "download":  f"{n_anni_dl_ok}/{len(dl_scan)} anni presenti",
            "categorie": f"{n_anni_cat_ok}/{len(cat_scan)} anni completi",
            "etl":       etl_info["status"],
        },
        "download":             {str(k): v for k, v in dl_scan.items()},
        "categorie":            {str(k): v for k, v in cat_scan.items()},
        "etl":                  etl_info,
        "anni_mancanti_download":   anni_mancanti_dl,
        "anni_mancanti_categorie":  anni_mancanti_cat,
        "steps_necessari":          steps_necessari,
    }


# ---------------------------------------------------------------------------
# CLI standalone
# ---------------------------------------------------------------------------

def _parse_args():
    p = argparse.ArgumentParser(description="Analisi stato file pipeline 5x1000")
    p.add_argument("--anni",  type=str, default=None,
                   help="Anni da verificare, separati da virgola (es. 2023,2024)")
    p.add_argument("--json",  action="store_true", help="Output in formato JSON")
    p.add_argument("--root",  type=str, default=None,
                   help="Cartella root del progetto (default: cartella di questo script)")
    return p.parse_args()


def main():
    args = _parse_args()
    root_dir = args.root or os.path.dirname(os.path.abspath(__file__))
    anni = [int(a.strip()) for a in args.anni.split(",") if a.strip()] if args.anni else None

    analysis = full_analysis(root_dir, anni)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return

    # Output human-readable
    print(f"\n{'='*60}")
    print("  ANALISI STATO PIPELINE — 5 PER MILLE")
    print(f"{'='*60}")
    print(f"  Cartella dati:  {analysis['dati_dir']}")
    print(f"  Analizzato:     {analysis['analizzato_at']}")
    print()

    r = analysis["riepilogo"]
    print(f"  Download:   {r['download']}")
    print(f"  Categorie:  {r['categorie']}")
    print(f"  ETL:        {r['etl']}")
    print()

    if analysis["anni_mancanti_download"]:
        print(f"  Anni mancanti (download):   {analysis['anni_mancanti_download']}")
    if analysis["anni_mancanti_categorie"]:
        print(f"  Anni mancanti (categorie):  {analysis['anni_mancanti_categorie']}")

    if analysis["steps_necessari"]:
        print(f"\n  Step da eseguire: {analysis['steps_necessari']}")
        cmd_anni = ",".join(str(a) for a in sorted(
            set(analysis["anni_mancanti_download"] + analysis["anni_mancanti_categorie"])
        ))
        if cmd_anni:
            print(f"  Suggerimento:     python pipeline.py --smart --anni {cmd_anni}")
        else:
            print(f"  Suggerimento:     python pipeline.py --smart")
    else:
        print("\n  Tutto aggiornato. Nessuno step necessario.")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
