#!/usr/bin/env python3
"""
verifica.py — Controlli di coerenza tra i dati AdE e quelli pubblicati.

Per ogni anno confronta quattro livelli dell'elenco complessivo:
  GREZZI   CSV originali AdE in <anno>/*.csv (se presenti)
  ESTRATTO Dati/dati_<anno>.xlsx (output di cinque_per_mille.py, da PDF o CSV)
  CSV      Dati/enti_5x1000_norm.csv filtrato per anno (output di etl.py)
  DB       tabella `enti` del sito

e due livelli per le categorie:
  FILE     Dati/<CAT>/<anno>_<CAT>_{ammessi,esclusi}.xlsx
  DB       tabella `categoria_ammissioni`

Metriche: righe, CF distinti, somma scelte, somma importo totale; poi dettaglio
per singolo CF (mancanti, in eccesso, importi/scelte diversi).
Output: Dati/verifiche/verifica_<timestamp>.xlsx con le anomalie in giallo.

Uso:
    python verifica.py                       # tutti gli anni
    python verifica.py --anni 2024,2023
    python verifica.py --anni 2024 --no-db   # solo file locali
Exit code: 0 nessuna anomalia, 2 anomalie trovate, 1 errore.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import logging
import os
import sys
import warnings
from pathlib import Path

import pandas as pd

from common import get_logger, load_config, load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT)

log = logging.getLogger("verifica")

# Tolleranze
TOLL_IMPORTO_CF = 0.01     # euro, per singolo CF
TOLL_IMPORTO_TOT = 1.00    # euro, sugli aggregati (somme di float)
MAX_DETTAGLIO = 5000       # righe di dettaglio per (anno, confronto)

LIVELLI = ("GREZZI", "ESTRATTO", "CSV", "DB")


def _dati_dir() -> Path:
    cfg = load_config(ROOT) or {}
    return ROOT / (cfg.get("percorsi", {}) or {}).get("dati", "Dati")


# ============================================================================
# LETTURA LIVELLI -> DataFrame standard [COD_FISCALE, DENOMINAZIONE, N_SCELTE, IMPORTO_TOTALE]
# ============================================================================

_STD_COLS = ["COD_FISCALE", "DENOMINAZIONE", "N_SCELTE", "IMPORTO_TOTALE"]


def _std(df: pd.DataFrame) -> pd.DataFrame:
    out = df[_STD_COLS].copy()
    out["COD_FISCALE"] = out["COD_FISCALE"].astype(str).str.strip().str.upper()
    out = out[out["COD_FISCALE"].str.len() > 0]
    out = out[~out["COD_FISCALE"].isin(["NAN", "NONE"])]
    out["N_SCELTE"] = pd.to_numeric(out["N_SCELTE"], errors="coerce")
    out["IMPORTO_TOTALE"] = pd.to_numeric(out["IMPORTO_TOTALE"], errors="coerce")
    return out


def leggi_estratto(anno: int, dati_dir: Path | None = None) -> pd.DataFrame | None:
    """Dati/dati_<anno>.xlsx normalizzato con la stessa logica di etl.py."""
    from etl import normalize_year
    path = (dati_dir or _dati_dir()) / f"dati_{anno}.xlsx"
    if not path.is_file():
        return None
    # stesso motore di lettura di etl.py, per non introdurre differenze di conversione
    df_raw = pd.read_excel(path, dtype=str)
    return _std(normalize_year(df_raw.dropna(how="all"), anno))


def leggi_grezzi(anno: int) -> pd.DataFrame | None:
    """CSV originali AdE in <anno>/*.csv, letti come fa cinque_per_mille.py."""
    from cinque_per_mille import extract_data_from_csv
    from etl import normalize_year
    files = sorted(glob.glob(str(ROOT / str(anno) / "*.csv")))
    if not files:
        return None
    header, all_rows = None, []
    for f in files:
        h, rows = extract_data_from_csv(f)
        if h and header is None:
            header = h
        all_rows.extend(rows)
    if not header or not all_rows:
        return None
    n = len(header)
    all_rows = [(r + [""] * n)[:n] for r in all_rows]
    all_rows = [r for r in all_rows if str(r[0]).strip()]
    df_raw = pd.DataFrame(all_rows, columns=header)
    return _std(normalize_year(df_raw, anno))


def leggi_csv_norm(anni: list[int], csv_path: Path | None = None) -> dict[int, pd.DataFrame]:
    """enti_5x1000_norm.csv letto a chunk, solo gli anni richiesti."""
    csv_path = csv_path or (_dati_dir() / "enti_5x1000_norm.csv")
    if not csv_path.is_file():
        return {}
    anni_s = {str(a) for a in anni}
    parts: dict[int, list] = {a: [] for a in anni}
    for chunk in pd.read_csv(csv_path, dtype=str, usecols=["ANNO"] + _STD_COLS,
                             chunksize=200_000, low_memory=False):
        chunk = chunk[chunk["ANNO"].str.strip().isin(anni_s)]
        for a, g in chunk.groupby(chunk["ANNO"].str.strip()):
            parts[int(a)].append(g)
    return {a: _std(pd.concat(p)) for a, p in parts.items() if p}


def conta_righe_csv_per_anno(csv_path: Path | None = None) -> dict[int, int]:
    """Numero di righe per anno nel CSV normalizzato (per controllare --replace)."""
    csv_path = csv_path or (_dati_dir() / "enti_5x1000_norm.csv")
    if not csv_path.is_file():
        return {}
    counts: dict[int, int] = {}
    for chunk in pd.read_csv(csv_path, dtype=str, usecols=["ANNO"], chunksize=500_000):
        for a, n in chunk["ANNO"].str.strip().value_counts().items():
            try:
                counts[int(a)] = counts.get(int(a), 0) + int(n)
            except ValueError:
                pass
    return counts


def _db_conn():
    from db import get_connection, db_available
    if not db_available():
        return None
    return get_connection()


def leggi_db_enti(conn, anno: int) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cod_fiscale, denominazione, n_scelte, importo_totale "
            "FROM enti WHERE anno = %s", (anno,))
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=_STD_COLS)
    df["IMPORTO_TOTALE"] = df["IMPORTO_TOTALE"].astype(float)
    return _std(df)


# ============================================================================
# CATEGORIE
# ============================================================================

_CAT_COLS = ["CATEGORIA", "COD_FISCALE", "DENOMINAZIONE", "STATO", "IMPORTO_TOTALE"]


def leggi_categorie_file(anno: int, dati_dir: Path | None = None) -> pd.DataFrame:
    """Righe attese in categoria_ammissioni, lette con lo stesso codice del caricamento DB."""
    from db_updater import righe_categoria_anno
    attese: dict[tuple, tuple] = {}
    for _xlsx, batch in righe_categoria_anno(dati_dir or _dati_dir(), anno):
        for r in batch:
            # r = (anno, cat, cf, denom, stato, n_scelte, esp, gen, tot, sotto, erog)
            # stessa semantica dell'UPSERT: l'ultima riga per (cat, cf) vince
            attese[(r[1], r[2])] = (r[1], r[2], r[3], r[4], r[8])
    return pd.DataFrame(list(attese.values()), columns=_CAT_COLS)


def leggi_categorie_db(conn, anno: int) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT categoria, cod_fiscale, denominazione, stato, importo_totale "
            "FROM categoria_ammissioni WHERE anno = %s", (anno,))
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=_CAT_COLS)
    df["IMPORTO_TOTALE"] = pd.to_numeric(df["IMPORTO_TOTALE"], errors="coerce").astype(float)
    return df


def categorie_attese_mancanti(anno: int, dati_dir: Path | None = None) -> list[str]:
    """Categorie elencate in categorie.xlsx per l'anno senza file *_ammessi.xlsx in Dati/."""
    cfg = load_config(ROOT) or {}
    input_path = ROOT / (cfg.get("pipeline", {}) or {}).get("input_categorie", "categorie.xlsx")
    if not input_path.is_file():
        return []
    from scarica_categorie import load_links
    dati_dir = dati_dir or _dati_dir()
    mancanti = []
    for e in load_links(str(input_path)):
        if e["anno"] != anno:
            continue
        if not list((dati_dir / e["slug"]).glob(f"{anno}_*_ammessi.xlsx")):
            mancanti.append(e["slug"])
    return sorted(set(mancanti))


# ============================================================================
# CONFRONTI
# ============================================================================

def metriche(df: pd.DataFrame | None) -> dict | None:
    if df is None:
        return None
    dedup = df.drop_duplicates("COD_FISCALE", keep="last")
    return {
        "righe": int(len(df)),
        "cf_distinti": int(len(dedup)),
        "duplicati": int(len(df) - len(dedup)),
        "n_scelte": float(dedup["N_SCELTE"].sum(skipna=True)),
        "importo_totale": round(float(dedup["IMPORTO_TOTALE"].sum(skipna=True)), 2),
    }


def confronta_cf(anno: int, nome: str, sx: pd.DataFrame, dx: pd.DataFrame) -> list[dict]:
    """Dettaglio per CF tra due livelli (dedup keep=last, come il caricamento DB)."""
    a = sx.drop_duplicates("COD_FISCALE", keep="last").set_index("COD_FISCALE")
    b = dx.drop_duplicates("COD_FISCALE", keep="last").set_index("COD_FISCALE")
    out = []

    def _row(cf, tipo, vs, vd, denom):
        out.append({"ANNO": anno, "CONFRONTO": nome, "COD_FISCALE": cf,
                    "DENOMINAZIONE": denom, "ANOMALIA": tipo,
                    "VALORE_SX": vs, "VALORE_DX": vd})

    for cf in a.index.difference(b.index):
        _row(cf, "solo a sinistra", a.at[cf, "IMPORTO_TOTALE"], None, a.at[cf, "DENOMINAZIONE"])
    for cf in b.index.difference(a.index):
        _row(cf, "solo a destra", None, b.at[cf, "IMPORTO_TOTALE"], b.at[cf, "DENOMINAZIONE"])

    comuni = a.index.intersection(b.index)
    ja = a.loc[comuni, ["N_SCELTE", "IMPORTO_TOTALE", "DENOMINAZIONE"]]
    jb = b.loc[comuni, ["N_SCELTE", "IMPORTO_TOTALE"]]
    d_imp = (ja["IMPORTO_TOTALE"].fillna(0) - jb["IMPORTO_TOTALE"].fillna(0)).abs()
    for cf in d_imp[d_imp > TOLL_IMPORTO_CF].index:
        _row(cf, "importo diverso", ja.at[cf, "IMPORTO_TOTALE"], jb.at[cf, "IMPORTO_TOTALE"],
             ja.at[cf, "DENOMINAZIONE"])
    d_sc = (ja["N_SCELTE"].fillna(0) - jb["N_SCELTE"].fillna(0)).abs()
    for cf in d_sc[d_sc > 0].index:
        _row(cf, "scelte diverse", ja.at[cf, "N_SCELTE"], jb.at[cf, "N_SCELTE"],
             ja.at[cf, "DENOMINAZIONE"])
    return out


def _esito_metriche(ms: dict, md: dict) -> tuple[bool, str]:
    diffs = []
    if ms["cf_distinti"] != md["cf_distinti"]:
        diffs.append(f"CF {ms['cf_distinti']:,} vs {md['cf_distinti']:,}")
    if abs(ms["n_scelte"] - md["n_scelte"]) > 0:
        diffs.append(f"scelte {ms['n_scelte']:,.0f} vs {md['n_scelte']:,.0f}")
    if abs(ms["importo_totale"] - md["importo_totale"]) > TOLL_IMPORTO_TOT:
        diffs.append(f"importo {ms['importo_totale']:,.2f} vs {md['importo_totale']:,.2f}")
    return (not diffs), "; ".join(diffs)


def verifica_anno(anno: int, csv_df: pd.DataFrame | None, conn, dettaglio: bool = True) -> dict:
    """Esegue tutti i controlli per un anno. Ritorna un dict con livelli, confronti, categorie, dettaglio."""
    log.info(f"[{anno}] verifica in corso...")
    livelli = {
        "GREZZI": leggi_grezzi(anno),
        "ESTRATTO": leggi_estratto(anno),
        "CSV": csv_df,
        "DB": leggi_db_enti(conn, anno) if conn else None,
    }
    met = {k: metriche(v) for k, v in livelli.items()}

    confronti, det = [], []
    for sx, dx in (("GREZZI", "ESTRATTO"), ("ESTRATTO", "CSV"), ("CSV", "DB")):
        if met[sx] is None or met[dx] is None:
            confronti.append({"ANNO": anno, "CONFRONTO": f"{sx} -> {dx}", "ESITO": "NON ESEGUITO",
                              "DETTAGLIO": f"livello {sx if met[sx] is None else dx} non disponibile"})
            continue
        ok, txt = _esito_metriche(met[sx], met[dx])
        confronti.append({"ANNO": anno, "CONFRONTO": f"{sx} -> {dx}",
                          "ESITO": "OK" if ok else "DIFFERENZE", "DETTAGLIO": txt})
        if dettaglio and not ok:
            righe = confronta_cf(anno, f"{sx} -> {dx}", livelli[sx], livelli[dx])
            if len(righe) > MAX_DETTAGLIO:
                righe = righe[:MAX_DETTAGLIO] + [{"ANNO": anno, "CONFRONTO": f"{sx} -> {dx}",
                                                  "ANOMALIA": f"... troncato a {MAX_DETTAGLIO} righe"}]
            det.extend(righe)

    for k, m in met.items():
        if m and m["duplicati"]:
            confronti.append({"ANNO": anno, "CONFRONTO": f"{k}: CF duplicati", "ESITO": "DIFFERENZE",
                              "DETTAGLIO": f"{m['duplicati']:,} righe con CF ripetuto"})

    # --- Categorie ---
    cat_rows = []
    mancanti = categorie_attese_mancanti(anno)
    if mancanti:
        confronti.append({"ANNO": anno, "CONFRONTO": "Categorie: file mancanti", "ESITO": "DIFFERENZE",
                          "DETTAGLIO": ", ".join(mancanti)})
    cat_file = leggi_categorie_file(anno)
    cat_db = leggi_categorie_db(conn, anno) if conn else None
    if not cat_file.empty or (cat_db is not None and not cat_db.empty):
        gf = cat_file.groupby(["CATEGORIA", "STATO"]).agg(
            N_FILE=("COD_FISCALE", "size"), IMP_FILE=("IMPORTO_TOTALE", "sum"))
        if cat_db is not None:
            gd = cat_db.groupby(["CATEGORIA", "STATO"]).agg(
                N_DB=("COD_FISCALE", "size"), IMP_DB=("IMPORTO_TOTALE", "sum"))
            g = gf.join(gd, how="outer").fillna(0).reset_index()
        else:
            g = gf.reset_index()
        for r in g.itertuples(index=False):
            row = {"ANNO": anno, "CATEGORIA": r.CATEGORIA, "STATO": r.STATO,
                   "N_FILE": int(r.N_FILE), "IMP_FILE": round(float(r.IMP_FILE), 2)}
            if cat_db is not None:
                row.update({"N_DB": int(r.N_DB), "IMP_DB": round(float(r.IMP_DB), 2)})
                ok = row["N_FILE"] == row["N_DB"] and abs(row["IMP_FILE"] - row["IMP_DB"]) <= TOLL_IMPORTO_TOT
                row["ESITO"] = "OK" if ok else "DIFFERENZE"
            else:
                row["ESITO"] = "DB NON VERIFICATO"
            cat_rows.append(row)

        if cat_db is not None and dettaglio and any(r["ESITO"] != "OK" for r in cat_rows):
            k = ["CATEGORIA", "COD_FISCALE"]
            m = cat_file.merge(cat_db, on=k, how="outer", suffixes=("_F", "_D"), indicator="ORIGINE")
            for r in m.itertuples(index=False):
                tipo = None
                imp_f = 0.0 if pd.isna(r.IMPORTO_TOTALE_F) else float(r.IMPORTO_TOTALE_F)
                imp_d = 0.0 if pd.isna(r.IMPORTO_TOTALE_D) else float(r.IMPORTO_TOTALE_D)
                if r.ORIGINE == "left_only":
                    tipo = "solo nei file"
                elif r.ORIGINE == "right_only":
                    tipo = "solo nel DB"
                elif r.STATO_F != r.STATO_D:
                    tipo = f"stato diverso ({r.STATO_F} / {r.STATO_D})"
                elif abs(imp_f - imp_d) > TOLL_IMPORTO_CF:
                    tipo = "importo diverso"
                if tipo:
                    det.append({"ANNO": anno, "CONFRONTO": f"CATEGORIA {r.CATEGORIA}: FILE -> DB",
                                "COD_FISCALE": r.COD_FISCALE,
                                "DENOMINAZIONE": r.DENOMINAZIONE_F if isinstance(r.DENOMINAZIONE_F, str) else r.DENOMINAZIONE_D,
                                "ANOMALIA": tipo, "VALORE_SX": r.IMPORTO_TOTALE_F, "VALORE_DX": r.IMPORTO_TOTALE_D})

    n_anomalie = sum(1 for c in confronti if c["ESITO"] == "DIFFERENZE") + \
        sum(1 for c in cat_rows if c["ESITO"] == "DIFFERENZE")
    return {"anno": anno, "metriche": met, "confronti": confronti,
            "categorie": cat_rows, "dettaglio": det, "n_anomalie": n_anomalie}


# ============================================================================
# EXCEL
# ============================================================================

def scrivi_excel(risultati: list[dict], out_path: Path, note: list[str]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    giallo = PatternFill("solid", fgColor="FFFF00")
    head_fill = PatternFill("solid", fgColor="2F5496")
    head_font = Font(bold=True, color="FFFFFF", name="Arial", size=10)

    def _sheet(wb, title, cols, rows, esito_col=None):
        ws = wb.create_sheet(title)
        ws.append(cols)
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
        for r in rows:
            ws.append([r.get(c) for c in cols])
            if esito_col and r.get(esito_col) not in ("OK", None):
                for c in ws[ws.max_row]:
                    c.fill = giallo
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(max(len(c) + 2, 14), 60)
        ws.freeze_panes = "A2"
        return ws

    wb = Workbook()
    wb.remove(wb.active)

    riep = [c for r in risultati for c in r["confronti"]]
    _sheet(wb, "Riepilogo", ["ANNO", "CONFRONTO", "ESITO", "DETTAGLIO"], riep, "ESITO")

    liv = []
    for r in risultati:
        for k in LIVELLI:
            m = r["metriche"][k]
            liv.append({"ANNO": r["anno"], "LIVELLO": k, **({k2.upper(): v for k2, v in m.items()}
                                                            if m else {"RIGHE": "non disponibile"})})
    _sheet(wb, "Livelli", ["ANNO", "LIVELLO", "RIGHE", "CF_DISTINTI", "DUPLICATI",
                           "N_SCELTE", "IMPORTO_TOTALE"], liv)

    _sheet(wb, "Categorie", ["ANNO", "CATEGORIA", "STATO", "N_FILE", "N_DB",
                             "IMP_FILE", "IMP_DB", "ESITO"],
           [c for r in risultati for c in r["categorie"]], "ESITO")

    _sheet(wb, "Dettaglio_CF", ["ANNO", "CONFRONTO", "COD_FISCALE", "DENOMINAZIONE",
                                "ANOMALIA", "VALORE_SX", "VALORE_DX"],
           [d for r in risultati for d in r["dettaglio"]])

    ws = wb.create_sheet("Note")
    for n in note:
        ws.append([n])
        ws[ws.max_row][0].alignment = Alignment(wrap_text=True)
    ws.column_dimensions["A"].width = 120

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


# ============================================================================
# ENTRY POINT
# ============================================================================

NOTE = [
    "Verifica generata da verifica.py il {ts}.",
    "GREZZI = CSV originali AdE nella cartella <anno>/ (non disponibile per gli anni pubblicati solo in PDF).",
    "ESTRATTO = Dati/dati_<anno>.xlsx; CSV = Dati/enti_5x1000_norm.csv; DB = tabella enti del sito.",
    "Le metriche sono calcolate sui CF distinti (ultima occorrenza), come avviene nel caricamento DB.",
    "Tolleranze: importo per CF 0,01 euro; importo aggregato 1,00 euro; scelte nessuna tolleranza.",
    "Dettaglio_CF: 'solo a sinistra' = CF presente nel primo livello del confronto e assente nel secondo.",
    "Le categorie sono confrontate tra i file Excel estratti e la tabella categoria_ammissioni; "
    "i PDF/CSV grezzi di categoria non sono riletti.",
    "Righe gialle = differenze da esaminare: non sono state corrette automaticamente.",
]


def esegui(anni: list[int], usa_db: bool = True, dettaglio: bool = True,
           out_path: Path | None = None) -> tuple[Path, list[dict]]:
    """Esegue la verifica e scrive l'Excel. Ritorna (percorso_excel, risultati)."""
    conn = None
    if usa_db:
        try:
            conn = _db_conn()
            if conn is None:
                log.warning("DB non configurato: verifico solo i file locali")
        except Exception as e:
            log.warning(f"Connessione DB fallita ({e}): verifico solo i file locali")
            conn = None

    log.info(f"Lettura CSV normalizzato per {len(anni)} anni...")
    csv_by_anno = leggi_csv_norm(anni)

    risultati = []
    try:
        for anno in sorted(anni, reverse=True):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                risultati.append(verifica_anno(anno, csv_by_anno.get(anno), conn, dettaglio))
    finally:
        if conn:
            conn.close()

    ts = datetime.datetime.now()
    out_path = out_path or (_dati_dir() / "verifiche" / f"verifica_{ts:%Y%m%d_%H%M}.xlsx")
    note = [n.format(ts=f"{ts:%d/%m/%Y %H:%M}") for n in NOTE]
    if conn is None and usa_db:
        note.insert(1, "ATTENZIONE: DB non raggiungibile, livello DB non verificato.")
    scrivi_excel(risultati, out_path, note)
    return out_path, risultati


def stampa_riepilogo(risultati: list[dict]) -> None:
    print()
    print(f"{'ANNO':<6}{'CONFRONTO':<34}{'ESITO':<14}DETTAGLIO")
    print("-" * 100)
    for r in risultati:
        for c in r["confronti"]:
            print(f"{c['ANNO']:<6}{c['CONFRONTO']:<34}{c['ESITO']:<14}{c.get('DETTAGLIO', '')}")
        nd = sum(1 for c in r["categorie"] if c["ESITO"] == "DIFFERENZE")
        if r["categorie"]:
            senza_db = all(c["ESITO"] == "DB NON VERIFICATO" for c in r["categorie"])
            esito = "NON ESEGUITO" if senza_db else ("DIFFERENZE" if nd else "OK")
            txt = ("livello DB non disponibile" if senza_db
                   else f"{nd} combinazioni categoria/stato con differenze" if nd else "")
            print(f"{r['anno']:<6}{'Categorie FILE -> DB':<34}{esito:<14}{txt}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica coerenza dati AdE ↔ CSV ↔ DB")
    ap.add_argument("--anni", default=None, help="Anni separati da virgola (default: tutti)")
    ap.add_argument("--no-db", action="store_true", help="Non interrogare il DB del sito")
    ap.add_argument("--no-dettaglio", action="store_true", help="Solo aggregati, senza dettaglio per CF")
    ap.add_argument("--output", default=None, help="Percorso Excel di output")
    args = ap.parse_args()

    get_logger("verifica", ROOT)
    if args.anni:
        anni = [int(a) for a in args.anni.split(",") if a.strip()]
    else:
        cfg = load_config(ROOT) or {}
        anni = sorted(int(a) for a in (cfg.get("url_anni") or {}).keys())
    try:
        out, ris = esegui(anni, usa_db=not args.no_db, dettaglio=not args.no_dettaglio,
                          out_path=Path(args.output) if args.output else None)
    except Exception as e:
        log.error(f"Verifica fallita: {e}", exc_info=True)
        return 1
    stampa_riepilogo(ris)
    n = sum(r["n_anomalie"] for r in ris)
    log.info(f"Report: {out}")
    log.info("Nessuna anomalia nei livelli verificati." if n == 0 else f"{n} controlli con differenze: vedi le righe gialle.")
    return 0 if n == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
