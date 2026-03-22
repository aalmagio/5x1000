#!/usr/bin/env python3
"""
forecast.py — Analisi predittiva / trend forecasting per dati 5×1000.

Usa regressione lineare (numpy.polyfit) su serie storica per proiettare:
  - numero di scelte espresse per categoria (anno +1, +2)
  - importo totale stimato per categoria

Output: site/public/data/forecast.json

Uso:
    python forecast.py [--anni 2] [--csv percorso/file.csv]
"""

import argparse
import json
import logging
import os
import pathlib
import sys

import numpy as np
import pandas as pd

log = logging.getLogger("forecast")


def load_env(root: pathlib.Path) -> None:
    env_file = root / ".env"
    if not env_file.is_file():
        return
    with open(env_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if k and not os.environ.get(k):
                os.environ[k] = v


def load_data_csv(csv_path: pathlib.Path) -> pd.DataFrame:
    log.info("Carico dati da CSV: %s", csv_path)
    return pd.read_csv(csv_path, low_memory=False)


def load_data_db() -> pd.DataFrame:
    log.info("Carico dati da DB MySQL")
    import pymysql  # noqa: PLC0415

    conn = pymysql.connect(
        host=os.getenv("SITE_DB_HOST", "localhost"),
        port=int(os.getenv("SITE_DB_PORT", "3306")),
        db=os.getenv("SITE_DB_NAME", ""),
        user=os.getenv("SITE_DB_USER", ""),
        passwd=os.getenv("SITE_DB_PASSWORD", ""),
        charset="utf8mb4",
    )
    df = pd.read_sql(
        "SELECT anno, categoria_principale, n_scelte, importo_totale FROM enti",
        conn,
    )
    conn.close()
    return df


def linear_forecast(anni: list, valori: list, n_future: int = 2) -> dict:
    """
    Regressione lineare su (anni, valori).
    Restituisce coefficienti, proiezioni e intervallo di confidenza al 95%.
    """
    x = np.array(anni, dtype=float)
    y = np.array(valori, dtype=float)

    coeffs = np.polyfit(x, y, 1)
    p = np.poly1d(coeffs)

    residuals = y - p(x)
    ddof = min(2, max(1, len(residuals) - 1))
    std_err = float(np.std(residuals, ddof=ddof))

    var_y = float(np.var(y))
    r2 = float(1 - np.var(residuals) / var_y) if var_y > 0 else 0.0

    anno_max = int(max(anni))
    proiezioni = []
    for i in range(1, n_future + 1):
        anno_futuro = anno_max + i
        val = float(p(anno_futuro))
        proiezioni.append({
            "anno": anno_futuro,
            "valore": round(max(val, 0), 2),
            "intervallo_inf": round(max(val - 1.96 * std_err, 0), 2),
            "intervallo_sup": round(max(val + 1.96 * std_err, 0), 2),
        })

    return {
        "coeff_slope": round(float(coeffs[0]), 4),
        "coeff_intercept": round(float(coeffs[1]), 4),
        "std_err": round(std_err, 2),
        "r2": round(r2, 4),
        "proiezioni": proiezioni,
    }


def run(root: pathlib.Path, csv_path: pathlib.Path | None = None, n_future: int = 2) -> dict:
    if csv_path and csv_path.is_file():
        df = load_data_csv(csv_path)
    else:
        default_csv = root / "Dati" / "enti_5x1000_norm.csv"
        if default_csv.is_file():
            df = load_data_csv(default_csv)
        else:
            df = load_data_db()

    # Normalizzazione colonne
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["anno", "categoria_principale"])
    df["anno"] = df["anno"].astype(int)
    df["n_scelte"] = pd.to_numeric(df.get("n_scelte", 0), errors="coerce").fillna(0)
    df["importo_totale"] = pd.to_numeric(df.get("importo_totale", 0), errors="coerce").fillna(0)

    categorie = sorted(df["categoria_principale"].dropna().unique())

    # Aggregato globale
    globale_agg = (
        df.groupby("anno")
        .agg(tot_scelte=("n_scelte", "sum"), tot_importo=("importo_totale", "sum"))
        .reset_index()
        .sort_values("anno")
    )
    anni_globale = globale_agg["anno"].tolist()

    risultati: dict = {
        "generato_il": pd.Timestamp.now().isoformat(timespec="seconds"),
        "anni_storici": anni_globale,
        "disclaimer": (
            "Le proiezioni sono stime statistiche basate sulla regressione lineare "
            "dei dati storici disponibili. I valori futuri reali possono variare "
            "significativamente per effetto di cambiamenti normativi, economici o sociali. "
            "Gli intervalli di confidenza al 95% indicano l'incertezza del modello "
            "ma non garantiscono il verificarsi dei valori previsti."
        ),
        "globale": {
            "scelte": linear_forecast(anni_globale, globale_agg["tot_scelte"].tolist(), n_future),
            "importo": linear_forecast(anni_globale, globale_agg["tot_importo"].tolist(), n_future),
            "storico": [
                {
                    "anno": int(r.anno),
                    "tot_scelte": int(r.tot_scelte),
                    "tot_importo": round(float(r.tot_importo), 2),
                }
                for r in globale_agg.itertuples()
            ],
        },
        "per_categoria": {},
    }

    for cat in categorie:
        sub = (
            df[df["categoria_principale"] == cat]
            .groupby("anno")
            .agg(tot_scelte=("n_scelte", "sum"), tot_importo=("importo_totale", "sum"))
            .reset_index()
            .sort_values("anno")
        )
        anni = sub["anno"].tolist()
        if len(anni) < 3:
            log.debug("Categoria '%s' ha solo %d anni – saltata", cat, len(anni))
            continue

        risultati["per_categoria"][cat] = {
            "scelte": linear_forecast(anni, sub["tot_scelte"].tolist(), n_future),
            "importo": linear_forecast(anni, sub["tot_importo"].tolist(), n_future),
            "storico": [
                {
                    "anno": int(r.anno),
                    "tot_scelte": int(r.tot_scelte),
                    "tot_importo": round(float(r.tot_importo), 2),
                }
                for r in sub.itertuples()
            ],
        }
        log.debug(
            "Categoria '%s': %d anni, R²=%.3f (importo)",
            cat,
            len(anni),
            risultati["per_categoria"][cat]["importo"]["r2"],
        )

    return risultati


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    ap = argparse.ArgumentParser(description="Genera proiezioni trend 5×1000 via regressione lineare")
    ap.add_argument("--anni", type=int, default=2, help="Anni da proiettare (default: 2)")
    ap.add_argument("--csv", default=None, help="Percorso CSV normalizzato (default: Dati/enti_5x1000_norm.csv)")
    ap.add_argument("--out", default=None, help="File output JSON (default: site/public/data/forecast.json)")
    args = ap.parse_args()

    root = pathlib.Path(__file__).parent
    load_env(root)

    csv_path = pathlib.Path(args.csv) if args.csv else None
    log.info("Avvio forecast 5×1000 (proiezione %d anni)", args.anni)
    risultati = run(root, csv_path=csv_path, n_future=args.anni)

    out_path = pathlib.Path(args.out) if args.out else root / "site" / "public" / "data" / "forecast.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(risultati, fh, ensure_ascii=False, indent=2)

    n_cat = len(risultati["per_categoria"])
    log.info("Forecast completato: %d categorie → %s", n_cat, out_path)
