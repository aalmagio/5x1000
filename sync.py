#!/usr/bin/env python3
"""
sync.py — Sincronizzazione dati dal sito di SVILUPPO al sito di PRODUZIONE.

Flusso: gli aggiornamenti (guida.py / pipeline) si fanno in sviluppo; quando i
dati sono verificati, questo strumento li porta in produzione con un fermo
di circa un secondo.

    python sync.py                 # sincronizzazione guidata (DB + file)
    python sync.py --solo-db       # solo tabelle (eseguibile anche da remoto)
    python sync.py --stato         # confronto sviluppo/produzione, nessuna modifica
    python sync.py --rollback      # torna alla versione precedente alla sync
    python sync.py --pulisci       # elimina le tabelle *__old / *__new e le release vecchie

Strategia (scambio tabelle):
  1. Controlli: connessioni, privilegi, schema identico, nessun anno che sparisce.
  2. Copia di ogni tabella da sviluppo in <tabella>__new su produzione, a blocchi
     ordinati per chiave primaria (il sito di produzione continua a funzionare).
  3. Verifica di <tabella>__new: conteggi e totali per anno uguali a sviluppo.
  4. File scaricabili copiati in una nuova cartella di release su produzione;
     dataset_files__new punta ai nuovi percorsi (gli SHA-256 vengono ricontrollati).
  5. Conferma, poi UN SOLO `RENAME TABLE` atomico:
        t -> t__old, t__new -> t   (per tutte le tabelle insieme)
  6. Svuotamento nlq_cache, sostituzione atomica di forecast.json, controllo finale.
  Le tabelle *__old e la release precedente restano per il rollback.

Tabelle MAI toccate: leads, nlq_rate_limit (dati generati dal sito di produzione).

Configurazione (.env):
  DEV_DB_HOST/PORT/USER/PASSWORD/NAME   (se assenti: SITE_DB_*)
  PROD_DB_HOST/PORT/USER/PASSWORD/NAME  (obbligatori)
Configurazione (config.yaml, sezione sync:) per la parte file:
  dev_dati, prod_release_dir, dev_forecast, prod_forecast, release_da_tenere
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from common import ask_yes_no, get_logger, load_config, load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT)

log = logging.getLogger("sync")

# Ordine = ordine di copia. Le tabelle grandi per prime, i cataloghi per ultimi.
TABELLE = ["enti", "categoria_ammissioni", "ripartizioni", "runts", "pipeline_runs", "dataset_files"]
CACHE_DA_SVUOTARE = ["nlq_cache"]
MAI_TOCCARE = {"leads", "nlq_rate_limit"}
VISTE = ["v_multi_categoria", "v_conflitti_categoria", "v_ultimo_aggiornamento", "v_statistiche_categorie"]
SUFF_NEW, SUFF_OLD, SUFF_TMP = "__new", "__old", "__tmp"
BLOCCO = 10_000
SOGLIA_DELTA = 0.05
STATO = ROOT / "Dati" / ".stato" / "sync_ultimo.json"

# Tabelle con colonna `anno`: verifica conteggi e totali per anno
CONTROLLI_ANNO = {
    "enti": "SUM(COALESCE(importo_totale,0))",
    "categoria_ammissioni": "SUM(COALESCE(importo_totale,0))",
    "ripartizioni": "SUM(COALESCE(importo_totale,0))",
}


class Errore(Exception):
    """Errore bloccante: la sincronizzazione si ferma senza toccare la produzione."""


# ============================================================================
# CONNESSIONI
# ============================================================================

def _params(prefisso: str, fallback: str | None = None) -> dict:
    def g(k, default=""):
        v = os.getenv(f"{prefisso}_{k}")
        if (v is None or v == "") and fallback:
            v = os.getenv(f"{fallback}_{k}")
        return v if v not in (None, "") else default
    return {
        "host": g("HOST", "localhost"), "port": int(g("PORT", "3306")),
        "user": g("USER"), "password": g("PASSWORD"), "database": g("NAME"),
        "charset": "utf8mb4", "autocommit": True,
    }


def connetti(ruolo: str):
    import pymysql
    p = _params("DEV_DB", "SITE_DB") if ruolo == "dev" else _params("PROD_DB")
    if not p["user"] or not p["database"]:
        chiavi = "DEV_DB_* (o SITE_DB_*)" if ruolo == "dev" else "PROD_DB_*"
        raise Errore(f"credenziali {ruolo} mancanti: imposta {chiavi} nel file .env")
    conn = pymysql.connect(**p)
    conn.descr = f"{p['user']}@{p['host']}:{p['port']}/{p['database']}"
    conn.ident = (p["host"], p["port"], p["database"])
    return conn


def q1(conn, sql, args=None):
    with conn.cursor() as c:
        c.execute(sql, args)
        r = c.fetchone()
    return r[0] if r else None


def qall(conn, sql, args=None):
    with conn.cursor() as c:
        c.execute(sql, args)
        return c.fetchall()


def esegui(conn, sql, args=None):
    with conn.cursor() as c:
        c.execute(sql, args)


def esiste(conn, tabella: str) -> bool:
    return bool(q1(conn, "SELECT COUNT(*) FROM information_schema.tables "
                         "WHERE table_schema = DATABASE() AND table_name = %s", (tabella,)))


def colonne(conn, tabella: str) -> list[tuple]:
    """(nome, tipo, nullable, default) in ordine; usato per confrontare gli schemi."""
    return [tuple(r) for r in qall(conn, """
        SELECT column_name, column_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s
        ORDER BY ordinal_position""", (tabella,))]


def chiave_primaria(conn, tabella: str) -> str:
    pk = [r[0] for r in qall(conn, """
        SELECT column_name FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE() AND table_name = %s AND constraint_name = 'PRIMARY'
        ORDER BY ordinal_position""", (tabella,))]
    if len(pk) != 1:
        raise Errore(f"{tabella}: serve una chiave primaria su una sola colonna (trovate: {pk})")
    return pk[0]


def checksum(conn, tabella: str):
    return qall(conn, f"CHECKSUM TABLE `{tabella}`")[0][1]


def catalogo_file(conn) -> set:
    """Contenuto logico del catalogo file, indipendente dai percorsi."""
    return {tuple(r) for r in qall(conn, "SELECT anno, tipo, categoria, formato, nome_file, sha256 "
                                         "FROM dataset_files")}


def per_anno(conn, tabella: str) -> dict[int, tuple[int, float]]:
    expr = CONTROLLI_ANNO[tabella]
    return {int(a): (int(n), round(float(s or 0), 2))
            for a, n, s in qall(conn, f"SELECT anno, COUNT(*), {expr} FROM `{tabella}` GROUP BY anno")}


# ============================================================================
# CONFIG FILE
# ============================================================================

def cfg_sync() -> dict:
    return (load_config(ROOT) or {}).get("sync", {}) or {}


def cfg_file() -> dict | None:
    """Percorsi della parte file; None se non configurati."""
    c = cfg_sync()
    chiavi = ("dev_dati", "prod_release_dir", "dev_forecast", "prod_forecast")
    if not all(c.get(k) for k in chiavi):
        return None
    # Percorsi relativi = relativi alla root del progetto (cartella di sync.py)
    out = {k: (ROOT / c[k]).resolve() if not Path(c[k]).is_absolute() else Path(c[k]) for k in chiavi}
    out["release_da_tenere"] = int(c.get("release_da_tenere", 2))
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ============================================================================
# FASE 1 — CONTROLLI
# ============================================================================

def controlla(dev, prod, con_file: bool) -> dict:
    """Controlli preliminari. Solleva Errore se qualcosa blocca. Ritorna il piano."""
    if dev.ident == prod.ident:
        raise Errore(f"sviluppo e produzione puntano allo stesso database ({prod.descr})")

    # Privilegi: CREATE/INSERT/ALTER/DROP su produzione
    probe = "_sync_probe"
    try:
        esegui(prod, f"DROP TABLE IF EXISTS `{probe}`")
        esegui(prod, f"CREATE TABLE `{probe}` (id INT PRIMARY KEY) ENGINE=InnoDB")
        esegui(prod, f"INSERT INTO `{probe}` VALUES (1)")
        esegui(prod, f"RENAME TABLE `{probe}` TO `{probe}2`")
        esegui(prod, f"DROP TABLE `{probe}2`")
    except Exception as e:
        raise Errore(f"privilegi insufficienti su produzione (servono CREATE, INSERT, ALTER, DROP): {e}")

    piano = {"copiare": [], "identiche": [], "avvisi": []}
    for t in TABELLE:
        if not esiste(dev, t):
            raise Errore(f"tabella {t} assente in sviluppo")
        if not esiste(prod, t):
            raise Errore(f"tabella {t} assente in produzione: allinea prima lo schema (site/db_schema.sql)")
        if colonne(dev, t) != colonne(prod, t):
            raise Errore(f"schema di {t} diverso tra sviluppo e produzione: "
                         f"applica in produzione le stesse migration di sviluppo")
        chiave_primaria(prod, t)
        n_dev = q1(dev, f"SELECT COUNT(*) FROM `{t}`")
        if t in ("enti", "categoria_ammissioni") and n_dev == 0:
            raise Errore(f"{t} è vuota in sviluppo: sincronizzazione annullata")
        if t == "dataset_files":
            uguali = catalogo_file(dev) == catalogo_file(prod)
        else:
            uguali = checksum(dev, t) == checksum(prod, t)
        piano["identiche" if uguali else "copiare"].append(t)

    # Con --solo-db il catalogo file non si copia: punterebbe ai file di sviluppo
    if not con_file and "dataset_files" in piano["copiare"]:
        piano["avvisi"].append("dataset_files diversa ma file non sincronizzati (--solo-db): "
                               "la tabella NON verrà copiata per non puntare a file di sviluppo")
        piano["copiare"].remove("dataset_files")

    # Anni: nessun anno deve sparire, variazioni forti segnalate
    for t in ("enti", "categoria_ammissioni"):
        a_dev, a_prod = per_anno(dev, t), per_anno(prod, t)
        spariti = sorted(set(a_prod) - set(a_dev))
        if spariti:
            raise Errore(f"{t}: anni presenti in produzione e assenti in sviluppo: {spariti}")
        for anno in sorted(a_dev):
            if anno in a_prod and a_prod[anno][0]:
                d = (a_dev[anno][0] - a_prod[anno][0]) / a_prod[anno][0]
                if abs(d) > SOGLIA_DELTA:
                    piano["avvisi"].append(f"{t} {anno}: righe {a_prod[anno][0]:,} -> {a_dev[anno][0]:,} ({d:+.1%})")
    return piano


def stampa_confronto(dev, prod) -> None:
    print(f"\n  Sviluppo:   {dev.descr}\n  Produzione: {prod.descr}\n")
    print(f"  {'TABELLA':<24}{'SVILUPPO':>14}{'PRODUZIONE':>14}  STATO")
    for t in TABELLE + CACHE_DA_SVUOTARE:
        nd = q1(dev, f"SELECT COUNT(*) FROM `{t}`") if esiste(dev, t) else None
        np_ = q1(prod, f"SELECT COUNT(*) FROM `{t}`") if esiste(prod, t) else None
        stato = ""
        if t in TABELLE and nd is not None and np_ is not None:
            uguali = (catalogo_file(dev) == catalogo_file(prod)) if t == "dataset_files"                 else checksum(dev, t) == checksum(prod, t)
            stato = "identica" if uguali else "DIVERSA"
        print(f"  {t:<24}{(f'{nd:,}' if nd is not None else '-'):>14}"
              f"{(f'{np_:,}' if np_ is not None else '-'):>14}  {stato}")
    a_dev, a_prod = per_anno(dev, "enti"), per_anno(prod, "enti")
    diversi = [a for a in sorted(set(a_dev) | set(a_prod), reverse=True) if a_dev.get(a) != a_prod.get(a)]
    if diversi:
        print(f"\n  Anni di 'enti' diversi:")
        print(f"  {'ANNO':<6}{'ENTI DEV':>12}{'ENTI PROD':>12}{'IMPORTO DEV':>20}{'IMPORTO PROD':>20}")
        for a in diversi:
            d, p = a_dev.get(a, (0, 0)), a_prod.get(a, (0, 0))
            print(f"  {a:<6}{d[0]:>12,}{p[0]:>12,}{d[1]:>20,.2f}{p[1]:>20,.2f}")
    else:
        print("\n  Tabella enti: tutti gli anni coincidono.")


# ============================================================================
# FASE 2 — COPIA IN TABELLE __new
# ============================================================================

def copia_tabella(dev, prod, t: str) -> int:
    """Copia dev.t in prod.t__new a blocchi ordinati per chiave primaria."""
    nuova = t + SUFF_NEW
    pk = chiave_primaria(prod, t)
    cols = [c[0] for c in colonne(prod, t)]
    lista = ", ".join(f"`{c}`" for c in cols)
    ins = f"INSERT INTO `{nuova}` ({lista}) VALUES ({', '.join(['%s'] * len(cols))})"

    esegui(prod, f"DROP TABLE IF EXISTS `{nuova}`")
    esegui(prod, f"CREATE TABLE `{nuova}` LIKE `{t}`")

    totale = q1(dev, f"SELECT COUNT(*) FROM `{t}`")
    copiate, ultimo, t0 = 0, None, time.time()
    while True:
        if ultimo is None:
            righe = qall(dev, f"SELECT {lista} FROM `{t}` ORDER BY `{pk}` LIMIT %s", (BLOCCO,))
        else:
            righe = qall(dev, f"SELECT {lista} FROM `{t}` WHERE `{pk}` > %s ORDER BY `{pk}` LIMIT %s",
                         (ultimo, BLOCCO))
        if not righe:
            break
        prod.begin()
        with prod.cursor() as c:
            c.executemany(ins, righe)
        prod.commit()
        copiate += len(righe)
        ultimo = righe[-1][cols.index(pk)]
        if totale:
            el = time.time() - t0
            print(f"\r    {t}: {copiate:,}/{totale:,} ({copiate / totale:.0%}, {el:.0f}s)", end="", flush=True)
    print()
    return copiate


def verifica_new(dev, prod, t: str) -> None:
    nuova = t + SUFF_NEW
    nd = q1(dev, f"SELECT COUNT(*) FROM `{t}`")
    nn = q1(prod, f"SELECT COUNT(*) FROM `{nuova}`")
    if nd != nn:
        raise Errore(f"{nuova}: {nn:,} righe copiate, attese {nd:,}")
    if t in CONTROLLI_ANNO:
        expr = CONTROLLI_ANNO[t]
        a_dev = per_anno(dev, t)
        a_new = {int(a): (int(n), round(float(s or 0), 2))
                 for a, n, s in qall(prod, f"SELECT anno, COUNT(*), {expr} FROM `{nuova}` GROUP BY anno")}
        if a_dev != a_new:
            diff = [a for a in set(a_dev) | set(a_new) if a_dev.get(a) != a_new.get(a)]
            raise Errore(f"{nuova}: conteggi/importi per anno diversi da sviluppo negli anni {sorted(diff)}")


# ============================================================================
# FASE 3 — FILE
# ============================================================================

def prepara_file(prod, fc: dict, release: Path) -> int:
    """
    Copia i file del catalogo (dataset_files__new, ancora con i percorsi di sviluppo)
    nella cartella di release di produzione e riscrive `percorso`.
    I file sono copiati in release/<percorso relativo a dev_dati>.
    """
    righe = qall(prod, f"SELECT id, percorso, sha256 FROM `dataset_files{SUFF_NEW}`")
    dev_dati = fc["dev_dati"].resolve()
    n = 0
    for rid, percorso, sha in righe:
        src = Path(percorso)
        if not src.is_file():
            raise Errore(f"file del catalogo assente in sviluppo: {src}")
        try:
            rel = src.resolve().relative_to(dev_dati)
        except ValueError:
            raise Errore(f"file fuori da dev_dati ({dev_dati}): {src}")
        dst = release / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + ".part")
        shutil.copy2(src, tmp)
        if sha and sha256(tmp) != sha:
            tmp.unlink()
            raise Errore(f"SHA-256 diverso dopo la copia: {rel} (il file in sviluppo è cambiato dopo la registrazione?)")
        os.replace(tmp, dst)
        esegui(prod, f"UPDATE `dataset_files{SUFF_NEW}` SET percorso = %s WHERE id = %s", (str(dst), rid))
        n += 1
        print(f"\r    file copiati: {n}/{len(righe)}", end="", flush=True)
    print()
    return n


def sostituisci_forecast(fc: dict) -> None:
    src, dst = fc["dev_forecast"], fc["prod_forecast"]
    if not src.is_file():
        log.warning(f"forecast.json di sviluppo assente ({src}): non sostituito")
        return
    json.loads(src.read_text(encoding="utf-8"))   # deve essere JSON valido
    if dst.is_file():
        shutil.copy2(dst, dst.with_suffix(".json.prev"))
    tmp = dst.with_suffix(".json.part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    log.info(f"forecast.json sostituito ({dst})")


# ============================================================================
# FASE 4 — SCAMBIO
# ============================================================================

def scambia(prod, tabelle: list[str]) -> None:
    """Un solo RENAME TABLE atomico: t -> t__old, t__new -> t."""
    for t in tabelle:
        esegui(prod, f"DROP TABLE IF EXISTS `{t}{SUFF_OLD}`")
    parti = []
    for t in tabelle:
        parti += [f"`{t}` TO `{t}{SUFF_OLD}`", f"`{t}{SUFF_NEW}` TO `{t}`"]
    t0 = time.time()
    esegui(prod, "RENAME TABLE " + ", ".join(parti))
    log.info(f"RENAME TABLE atomico eseguito in {(time.time() - t0) * 1000:.0f} ms ({len(tabelle)} tabelle)")


def controllo_finale(dev, prod, tabelle: list[str]) -> list[str]:
    problemi = []
    for t in tabelle:
        nd, np_ = q1(dev, f"SELECT COUNT(*) FROM `{t}`"), q1(prod, f"SELECT COUNT(*) FROM `{t}`")
        if nd != np_:
            problemi.append(f"{t}: {np_:,} righe in produzione, {nd:,} in sviluppo")
        elif t in CONTROLLI_ANNO and per_anno(dev, t) != per_anno(prod, t):
            problemi.append(f"{t}: totali per anno diversi da sviluppo")
    for v in VISTE:
        if esiste(prod, v):
            try:
                qall(prod, f"SELECT * FROM `{v}` LIMIT 1")
            except Exception as e:
                problemi.append(f"vista {v} non interrogabile: {e}")
    return problemi


def salva_stato(d: dict) -> None:
    STATO.parent.mkdir(parents=True, exist_ok=True)
    STATO.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def leggi_stato() -> dict | None:
    return json.loads(STATO.read_text(encoding="utf-8")) if STATO.is_file() else None


# ============================================================================
# COMANDI
# ============================================================================

def cmd_stato() -> int:
    dev, prod = connetti("dev"), connetti("prod")
    try:
        stampa_confronto(dev, prod)
        s = leggi_stato()
        if s:
            print(f"\n  Ultima sync: {s.get('eseguita_il')} - tabelle {', '.join(s.get('tabelle', []))}")
            vecchie = [t for t in TABELLE if esiste(prod, t + SUFF_OLD)]
            print(f"  Rollback disponibile: {'sì (' + ', '.join(vecchie) + ')' if vecchie else 'no'}")
    finally:
        dev.close(); prod.close()
    return 0


def cmd_sync(solo_db: bool, si: bool) -> int:
    fc = None if solo_db else cfg_file()
    if not solo_db and fc is None:
        raise Errore("sezione sync: di config.yaml incompleta (dev_dati, prod_release_dir, dev_forecast, "
                     "prod_forecast). Configurala oppure usa --solo-db")

    dev, prod = connetti("dev"), connetti("prod")
    t_inizio = time.time()
    create: list[str] = []
    try:
        print("\n=== 1. Controlli ===")
        stampa_confronto(dev, prod)
        piano = controlla(dev, prod, con_file=fc is not None)
        if fc:
            if not fc["prod_release_dir"].parent.is_dir():
                raise Errore(f"cartella di produzione inesistente: {fc['prod_release_dir'].parent} "
                             "(sync.py va eseguito sul server, dalla root di sviluppo)")
            fc["prod_release_dir"].mkdir(parents=True, exist_ok=True)
            prova = fc["prod_release_dir"] / ".sync_probe"
            try:
                prova.write_text("ok"); prova.unlink()
            except OSError as e:
                raise Errore(f"impossibile scrivere in {fc['prod_release_dir']}: {e}")
        print(f"\n  Da copiare: {', '.join(piano['copiare']) or 'nessuna'}")
        print(f"  Identiche (saltate): {', '.join(piano['identiche']) or 'nessuna'}")
        for a in piano["avvisi"]:
            print(f"  [!] {a}")
        if not piano["copiare"]:
            print("\n  Produzione già allineata a sviluppo: nulla da fare.")
            return 0
        if piano["avvisi"] and not si and not ask_yes_no("\n  Proseguo nonostante gli avvisi?", default="n"):
            return 1

        print("\n=== 2. Copia in tabelle di appoggio (produzione resta online) ===")
        for t in piano["copiare"]:
            create.append(t)
            copia_tabella(dev, prod, t)
            verifica_new(dev, prod, t)
            log.info(f"{t}{SUFF_NEW}: copia verificata")

        release = None
        if fc and "dataset_files" in piano["copiare"]:
            print("\n=== 3. File scaricabili ===")
            release = fc["prod_release_dir"] / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                n = prepara_file(prod, fc, release)
            except BaseException:
                shutil.rmtree(release, ignore_errors=True)
                raise
            log.info(f"{n} file copiati in {release}")

        print("\n=== 4. Scambio ===")
        print(f"  Tabelle pronte e verificate: {', '.join(piano['copiare'])}")
        if not si:
            nome = prod.ident[2]
            r = input(f"  Per confermare lo scambio in PRODUZIONE digita il nome del database ({nome}): ").strip()
            if r != nome:
                raise Errore("conferma non data: produzione invariata")
        scambia(prod, piano["copiare"])
        create = []   # da qui le __new sono diventate le tabelle live
        for c in CACHE_DA_SVUOTARE:
            if esiste(prod, c):
                esegui(prod, f"DELETE FROM `{c}`")
        if fc:
            sostituisci_forecast(fc)

        stato_prec = leggi_stato() or {}
        salva_stato({
            "eseguita_il": datetime.datetime.now().isoformat(timespec="seconds"),
            "tabelle": piano["copiare"],
            "release": str(release) if release else stato_prec.get("release"),
            "release_precedente": stato_prec.get("release") if release else stato_prec.get("release_precedente"),
            "durata_s": int(time.time() - t_inizio),
        })

        print("\n=== 5. Controllo finale ===")
        problemi = controllo_finale(dev, prod, piano["copiare"])
        if problemi:
            for p in problemi:
                print(f"  [X] {p}")
            print("  Valuta il rollback: python sync.py --rollback")
            return 2
        print(f"  Produzione allineata a sviluppo in {(time.time() - t_inizio) / 60:.1f} minuti.")
        print("  Versione precedente conservata (tabelle *__old): python sync.py --rollback per tornare indietro,")
        print("  python sync.py --pulisci per liberare spazio quando sei sicuro.")
        return 0

    except BaseException:
        # Produzione non è stata toccata: rimuovo solo le tabelle di appoggio create in questo run
        for t in create:
            try:
                esegui(prod, f"DROP TABLE IF EXISTS `{t}{SUFF_NEW}`")
            except Exception:
                pass
        raise
    finally:
        dev.close(); prod.close()


def cmd_rollback(si: bool) -> int:
    prod = connetti("prod")
    try:
        s = leggi_stato() or {}
        tab = [t for t in (s.get("tabelle") or TABELLE) if esiste(prod, t + SUFF_OLD)]
        if not tab:
            raise Errore("nessuna tabella *__old in produzione: rollback non disponibile")
        print(f"  Rollback delle tabelle: {', '.join(tab)}")
        if not si and not ask_yes_no("  Ripristino la versione precedente in produzione?", default="n"):
            return 1
        for t in tab:
            esegui(prod, f"DROP TABLE IF EXISTS `{t}{SUFF_TMP}`")
        parti = []
        for t in tab:
            parti += [f"`{t}` TO `{t}{SUFF_TMP}`", f"`{t}{SUFF_OLD}` TO `{t}`", f"`{t}{SUFF_TMP}` TO `{t}{SUFF_OLD}`"]
        esegui(prod, "RENAME TABLE " + ", ".join(parti))
        for c in CACHE_DA_SVUOTARE:
            if esiste(prod, c):
                esegui(prod, f"DELETE FROM `{c}`")
        fc = cfg_file()
        if fc:
            prev = fc["prod_forecast"].with_suffix(".json.prev")
            if prev.is_file():
                tmp = fc["prod_forecast"].with_suffix(".json.part")
                shutil.copy2(fc["prod_forecast"], tmp)
                os.replace(prev, fc["prod_forecast"])
                os.replace(tmp, prev)
        s["rollback_il"] = datetime.datetime.now().isoformat(timespec="seconds")
        s["release"], s["release_precedente"] = s.get("release_precedente"), s.get("release")
        salva_stato(s)
        print("  Rollback eseguito. Le tabelle appena sostituite sono ora in *__old "
              "(rieseguire --rollback le rimette in linea).")
        return 0
    finally:
        prod.close()


def cmd_pulisci(si: bool) -> int:
    prod = connetti("prod")
    try:
        tab = [t + s for t in TABELLE for s in (SUFF_OLD, SUFF_NEW, SUFF_TMP) if esiste(prod, t + s)]
        fc = cfg_file()
        s = leggi_stato() or {}
        da_tenere = {s.get("release"), s.get("release_precedente")}
        rel_vecchie = []
        if fc and fc["prod_release_dir"].is_dir():
            tutte = sorted(p for p in fc["prod_release_dir"].iterdir() if p.is_dir())
            tenute = set(str(p) for p in tutte[-fc["release_da_tenere"]:]) | {x for x in da_tenere if x}
            rel_vecchie = [p for p in tutte if str(p) not in tenute]
        print(f"  Tabelle da eliminare: {', '.join(tab) or 'nessuna'}")
        print(f"  Release file da eliminare: {', '.join(p.name for p in rel_vecchie) or 'nessuna'}")
        if not tab and not rel_vecchie:
            return 0
        print("  Dopo la pulizia il rollback non sarà più possibile.")
        if not si and not ask_yes_no("  Procedo?", default="n"):
            return 1
        for t in tab:
            esegui(prod, f"DROP TABLE `{t}`")
        for p in rel_vecchie:
            shutil.rmtree(p)
        print("  Pulizia completata.")
        return 0
    finally:
        prod.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Sincronizzazione sviluppo -> produzione (scambio tabelle)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--stato", action="store_true", help="Confronto sviluppo/produzione, nessuna modifica")
    g.add_argument("--rollback", action="store_true", help="Ripristina la versione precedente alla sync")
    g.add_argument("--pulisci", action="store_true", help="Elimina tabelle *__old/*__new e release vecchie")
    ap.add_argument("--solo-db", action="store_true", help="Sincronizza solo le tabelle (no file)")
    ap.add_argument("--si", action="store_true", help="Nessuna conferma interattiva (uso da script)")
    args = ap.parse_args()

    _, log_file = get_logger("sync", ROOT)
    try:
        if args.stato:
            return cmd_stato()
        if args.rollback:
            return cmd_rollback(args.si)
        if args.pulisci:
            return cmd_pulisci(args.si)
        return cmd_sync(args.solo_db, args.si)
    except Errore as e:
        log.error(f"SINCRONIZZAZIONE FERMATA: {e}")
        print("  La produzione non è stata modificata.")
        return 1
    except KeyboardInterrupt:
        log.error("Interrotto: le tabelle di appoggio sono state rimosse, produzione invariata.")
        return 1
    finally:
        print(f"\n  Log: {log_file}")


if __name__ == "__main__":
    sys.exit(main())
