#!/usr/bin/env python3
"""
guida.py — Procedura guidata per aggiornare il dataset 5x1000.

    python guida.py

Menu:
  1. Aggiungi un nuovo anno       (link AdE -> download -> ETL -> pubblicazione -> verifica)
  2. Aggiorna un anno esistente   (nuovo download AdE -> ETL -> pubblicazione -> verifica)
  3. Verifica dati                (AdE <-> CSV normalizzato <-> DB del sito)
  4. Ripubblica un anno sul sito  (solo DB + derivati, dai dati locali già elaborati)
  5. Sincronizza sviluppo -> produzione (vedi sync.py)

Garanzie di robustezza:
- Prima di riscaricare un anno, i file attuali (grezzi AdE, Excel estratti, CSV
  normalizzato) vengono spostati/copiati in _archivio/<anno>_<timestamp>/.
  La cartella dell'anno viene così ricostruita da zero: nessun file vecchio con
  nome diverso resta a duplicare le righe.
- Due controlli bloccanti prima di toccare il DB: dopo l'estrazione (confronto
  con la versione precedente e con i CSV grezzi AdE) e dopo l'ETL (gli altri
  anni del CSV devono restare identici).
- Se qualcosa fallisce prima della pubblicazione, i file precedenti vengono
  ripristinati dall'archivio.
- Il DB viene aggiornato in un'unica transazione per anno (DELETE+INSERT+COMMIT):
  il sito vede i dati vecchi fino al COMMIT, un errore fa ROLLBACK.
- Al termine viene eseguita la verifica completa dell'anno (Excel in Dati/verifiche/).
"""

from __future__ import annotations

import datetime
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

import pipeline as _pl  # noqa: E402  (riuso run_step, PYTHON, file .done)
import verifica as _ver  # noqa: E402

log = logging.getLogger("guida")

DATI = ROOT / ((load_config(ROOT) or {}).get("percorsi", {}) or {}).get("dati", "Dati")
CSV_NORM = DATI / "enti_5x1000_norm.csv"
ARCHIVIO = ROOT / "_archivio"
LOCK = DATI / ".stato" / "guida.lock"
CONFIG_YAML = ROOT / "config.yaml"

SOGLIA_DELTA = 0.05        # variazione oltre la quale chiedere conferma (5%)
SPAZIO_MIN_GB = 2.0

ETICHETTE_DEFAULT = {      # usate se categorie.xlsx non ha un anno di riferimento
    "ETS_ONLUS": "Enti del Terzo Settore",
    "Ricerca_scientifica": "Ricerca scientifica",
    "Ricerca_sanitaria": "Ricerca sanitaria",
    "Comuni": "Attività svolte dai comuni",
    "ASD": "Associazioni sportive dilettantistiche",
    "Beni_culturali": "Enti dei beni culturali e paesaggistici",
    "Aree_protette": "Enti gestori delle aree protette",
}


class Interrotto(Exception):
    """Errore bloccante: la procedura si ferma e ripristina i file."""


# ============================================================================
# UTILITÀ
# ============================================================================

def titolo(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def fase(t: str) -> None:
    print()
    log.info(f"--- {t} ---")


def chiedi(prompt: str, default: str | None = None) -> str:
    suff = f" [{default}]" if default else ""
    r = input(f"{prompt}{suff}: ").strip()
    return r or (default or "")


def _cfg() -> dict:
    return load_config(ROOT) or {}


def _anni_configurati() -> list[int]:
    return sorted((int(a) for a in (_cfg().get("url_anni") or {})), reverse=True)


def _input_categorie() -> Path:
    return ROOT / (_cfg().get("pipeline", {}) or {}).get("input_categorie", "categorie.xlsx")


def _source() -> str:
    d = _pl._carica_ciclo_defaults(str(ROOT)) or {}
    return d.get("source", "pdf") if d.get("source") in ("pdf", "csv") else "pdf"


def _timeout(step: str) -> int:
    t = (_cfg().get("pipeline", {}) or {}).get("step_timeouts", {}) or {}
    return int(t.get(step, 3600))


def _esegui(label: str, cmd: list[str], step: str) -> bool:
    ok, _ = _pl.run_step(label, cmd, str(ROOT), timeout=_timeout(step))
    return ok


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}" if v % 1 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _delta(a, b) -> float | None:
    if a in (None, 0) or b is None:
        return None
    return (b - a) / a


# ============================================================================
# CONTROLLI PRELIMINARI E LOCK
# ============================================================================

def db_raggiungibile() -> tuple[bool, str]:
    from db import db_available, get_connection
    if not db_available():
        return False, "credenziali SITE_DB_* non configurate (.env assente o incompleto)"
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True, "ok"
    except Exception as e:
        return False, f"connessione fallita: {e}"


def controlli_preliminari(rete: bool) -> bool:
    ok = True
    libero = shutil.disk_usage(ROOT).free / 1024 ** 3
    if libero < SPAZIO_MIN_GB:
        print(f"  [!] Spazio libero su disco: {libero:.1f} GB (minimo consigliato {SPAZIO_MIN_GB} GB)")
        ok = ask_yes_no("  Procedere comunque?", default="n")
    if rete:
        try:
            import requests, bs4  # noqa: F401
        except ImportError:
            print("  [X] requests/beautifulsoup4 non installati: impossibile scaricare da AdE.")
            return False
    return ok


class Lock:
    """Impedisce due esecuzioni contemporanee della guida."""

    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        if LOCK.exists():
            print(f"\n  [!] Un'altra esecuzione risulta in corso:\n      {LOCK.read_text(encoding='utf-8')}")
            if not ask_yes_no("  Se sei certo che non sia attiva (es. crash precedente), sblocco e procedo?",
                              default="n"):
                raise Interrotto("esecuzione già in corso")
        LOCK.write_text(f"pid={os.getpid()} avvio={datetime.datetime.now():%d/%m/%Y %H:%M}",
                        encoding="utf-8")
        return self

    def __exit__(self, *exc):
        LOCK.unlink(missing_ok=True)
        return False


# ============================================================================
# ARCHIVIO (backup + ripristino)
# ============================================================================

class Archivio:
    """
    Sposta i file correnti di un anno in _archivio/<anno>_<ts>/ e li sa ripristinare.
    Un manifest.json descrive cosa è stato spostato, per un eventuale ripristino manuale.
    """

    def __init__(self, anno: int):
        self.anno = anno
        self.dir = ARCHIVIO / f"{anno}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
        self.spostati: list[tuple[str, str]] = []   # (originale, archiviato)
        self.copiati: list[tuple[str, str]] = []
        self.completo = False   # True solo se l'archiviazione è andata a buon fine per intero

    def _file_anno_in_dati(self) -> list[Path]:
        out = []
        f = DATI / f"dati_{self.anno}.xlsx"
        if f.is_file():
            out.append(f)
        for d in DATI.iterdir():
            if d.is_dir() and not d.name.startswith(".") and d.name != "verifiche":
                out.extend(sorted(d.glob(f"{self.anno}_*.xlsx")))
        return out

    def _salva_manifest(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "manifest.json").write_text(json.dumps({
            "anno": self.anno, "spostati": self.spostati, "copiati": self.copiati,
            "nota": "Per ripristinare a mano: riportare ogni 'archiviato' nel percorso 'originale'.",
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def archivia(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        grezzi = ROOT / str(self.anno)
        targets = ([grezzi] if grezzi.is_dir() else []) + self._file_anno_in_dati()
        for p in targets:
            dest = self.dir / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            self.spostati.append((str(p), str(dest)))
        if CSV_NORM.is_file():
            dest = self.dir / CSV_NORM.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CSV_NORM, dest)
            self.copiati.append((str(CSV_NORM), str(dest)))
        self._salva_manifest()
        self.completo = True
        log.info(f"Archivio creato: {self.dir} ({len(self.spostati)} elementi spostati, "
                 f"{len(self.copiati)} copiati)")

    def ripristina(self) -> None:
        log.warning(f"Ripristino dei file precedenti da {self.dir} ...")
        # 1. rimuovi quanto prodotto dal run interrotto — solo se l'archiviazione era
        #    completa: altrimenti ciò che si trova al posto originale è ancora l'originale.
        if self.completo:
            nuovi = ROOT / str(self.anno)
            if nuovi.is_dir():
                shutil.rmtree(nuovi)
            for p in self._file_anno_in_dati():
                p.unlink()
        # 2. riporta gli originali
        for orig, arch in self.spostati:
            Path(orig).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(arch, orig)
        for orig, arch in self.copiati:
            shutil.copy2(arch, orig)
        log.warning("Ripristino completato: i file locali sono tornati allo stato precedente.")


# ============================================================================
# MODIFICA CONFIGURAZIONE (config.yaml + categorie.xlsx)
# ============================================================================

def _backup_file(p: Path) -> None:
    if p.is_file():
        d = ARCHIVIO / "config"
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d / f"{p.stem}_{datetime.datetime.now():%Y%m%d_%H%M%S}{p.suffix}")


def registra_url_anno(anno: int, url: str) -> None:
    """Inserisce/aggiorna `  <anno>: "<url>"` sotto url_anni: senza riscrivere il resto del file."""
    _backup_file(CONFIG_YAML)
    righe = CONFIG_YAML.read_text(encoding="utf-8").splitlines(keepends=True)
    nuova = f'  {anno}: "{url}"\n'
    for i, r in enumerate(righe):
        if r.strip().startswith(f"{anno}:") and r.startswith("  "):
            righe[i] = nuova
            break
    else:
        idx = next((i for i, r in enumerate(righe) if r.rstrip() == "url_anni:"), None)
        if idx is None:
            raise Interrotto("sezione 'url_anni:' non trovata in config.yaml")
        # salta eventuali righe di commento subito dopo url_anni:
        j = idx + 1
        while j < len(righe) and righe[j].lstrip().startswith("#"):
            j += 1
        righe.insert(j, nuova)
    CONFIG_YAML.write_text("".join(righe), encoding="utf-8")
    if int(anno) not in {int(a) for a in (_cfg().get("url_anni") or {})}:
        raise Interrotto("config.yaml scritto ma l'anno non risulta leggibile: controlla il file")
    log.info(f"config.yaml: url_anni[{anno}] registrato")


def registra_link_categorie(anno: int, righe: list[tuple[str, str]]) -> None:
    """Aggiunge righe (etichetta, url, anno) al primo foglio di categorie.xlsx."""
    from openpyxl import load_workbook
    path = _input_categorie()
    _backup_file(path)
    wb = load_workbook(path)
    ws = wb.worksheets[0]
    for etichetta, url in righe:
        ws.append([etichetta, url, anno])
    try:
        wb.save(path)
    except PermissionError:
        raise Interrotto(f"{path.name} è aperto in Excel: chiudilo e riprova")
    log.info(f"{path.name}: aggiunte {len(righe)} righe per l'anno {anno}")


def link_categorie(anno: int) -> list[dict]:
    from scarica_categorie import load_links
    p = _input_categorie()
    return [e for e in load_links(str(p)) if e["anno"] == anno] if p.is_file() else []


def etichette_categorie() -> dict[str, str]:
    """slug -> etichetta, prese dall'anno più recente di categorie.xlsx."""
    from scarica_categorie import load_links
    p = _input_categorie()
    if not p.is_file():
        return dict(ETICHETTE_DEFAULT)
    entries = load_links(str(p))
    if not entries:
        return dict(ETICHETTE_DEFAULT)
    ultimo = max(e["anno"] for e in entries)
    out = {e["slug"]: e["categoria"] for e in entries if e["anno"] == ultimo}
    for k, v in ETICHETTE_DEFAULT.items():
        out.setdefault(k, v)
    return out


# ============================================================================
# CONTROLLI SU AdE (rete)
# ============================================================================

def _sessione():
    import requests
    from cinque_per_mille import HEADERS, _apply_config
    _apply_config(_cfg())
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def conta_link(url: str, session) -> tuple[int, int]:
    """(n_pdf, n_csv) trovati alla pagina; (1,0)/(0,1) se è un link diretto a file."""
    from cinque_per_mille import find_download_links
    from scarica_categorie import _is_direct_file_url
    if _is_direct_file_url(url):
        return (1, 0) if url.lower().split("?")[0].endswith(".pdf") else (0, 1)
    links = find_download_links(url, session)
    return len(links.get("pdf", [])), len(links.get("csv", []))


def novita_elenco(anno: int, session) -> dict:
    """Confronta i nomi file online (elenco complessivo) con quelli locali."""
    from cinque_per_mille import find_download_links, sanitize_filename
    url = (_cfg().get("url_anni") or {}).get(anno)
    if not url:
        return {"errore": "URL non configurato"}
    logging.disable(logging.INFO)          # niente log dello scraper dentro la tabella
    try:
        links = find_download_links(str(url), session)
    except Exception as e:
        return {"errore": str(e)}
    finally:
        logging.disable(logging.NOTSET)
    online = {sanitize_filename(u, i, ext)
              for ext in ("pdf", "csv") for i, u in enumerate(links.get(ext, []), 1)}
    cartella = ROOT / str(anno)
    locali = {p.name for p in cartella.iterdir() if p.is_file()} if cartella.is_dir() else set()
    return {"online": len(online), "locali": len(locali - {f"dati_{anno}.xlsx"}),
            "nuovi": sorted(online - locali)}


def chiedi_link_categorie(anno: int, gia_presenti: set[str], session) -> list[tuple[str, str]]:
    """Chiede i link delle categorie mancanti per l'anno. Invio = salta la categoria."""
    etich = etichette_categorie()
    righe = []
    print("\n  Link delle pagine AdE per categoria (Invio per saltare una categoria):")
    for slug, label in etich.items():
        if slug in gia_presenti:
            continue
        while True:
            url = chiedi(f"  - {label}")
            if not url:
                break
            if not url.startswith("http"):
                print("    Link non valido (deve iniziare con http).")
                continue
            n_pdf, n_csv = conta_link(url, session)
            print(f"    trovati {n_pdf} PDF e {n_csv} CSV")
            if n_pdf + n_csv == 0 and not ask_yes_no("    Nessun file trovato. Registro comunque il link?",
                                                     default="n"):
                continue
            righe.append((label, url))
            break
    return righe


# ============================================================================
# FOTOGRAFIA DEI DATI (prima / dopo)
# ============================================================================

def fotografia(anno: int) -> dict:
    """Metriche locali di un anno: estratto, grezzi, categorie (per categoria/stato)."""
    est = _ver.leggi_estratto(anno, DATI)
    grz = _ver.leggi_grezzi(anno)
    cat = _ver.leggi_categorie_file(anno, DATI)
    cat_cnt = (cat.groupby(["CATEGORIA", "STATO"]).size().to_dict() if not cat.empty else {})
    return {"estratto": _ver.metriche(est), "grezzi": _ver.metriche(grz), "categorie": cat_cnt,
            "mancanti": _ver.categorie_attese_mancanti(anno, DATI)}


def confronta_fotografie(anno: int, prima: dict | None, dopo: dict) -> list[str]:
    """Stampa il confronto e ritorna l'elenco degli avvisi (vuoto = tutto regolare)."""
    avvisi = []
    e1 = (prima or {}).get("estratto") or {}
    e2 = dopo["estratto"]
    print(f"\n  {'Elenco complessivo':<28}{'prima':>18}{'dopo':>18}{'delta':>10}")
    for k in ("righe", "cf_distinti", "duplicati", "n_scelte", "importo_totale"):
        d = _delta(e1.get(k), e2.get(k))
        print(f"  {k:<28}{_fmt(e1.get(k)):>18}{_fmt(e2.get(k)):>18}"
              f"{(f'{d:+.1%}' if d is not None else ''):>10}")
        if k in ("cf_distinti", "importo_totale") and d is not None and abs(d) > SOGLIA_DELTA:
            avvisi.append(f"{k} varia del {d:+.1%} rispetto alla versione precedente")
    if e2.get("duplicati"):
        avvisi.append(f"{e2['duplicati']:,} righe con CF duplicato nell'estratto")

    g = dopo.get("grezzi")
    if g:
        ok, txt = _ver._esito_metriche(g, e2)
        print(f"\n  CSV grezzi AdE -> estratto: {'coerenti' if ok else 'DIFFERENZE: ' + txt}")
        if not ok:
            avvisi.append(f"estratto diverso dai CSV grezzi AdE ({txt})")

    c1 = (prima or {}).get("categorie") or {}
    c2 = dopo["categorie"]
    if c1 or c2:
        print(f"\n  {'Categoria / stato':<40}{'prima':>12}{'dopo':>12}")
        for key in sorted(set(c1) | set(c2)):
            a, b = c1.get(key), c2.get(key)
            print(f"  {key[0] + ' / ' + key[1]:<40}{_fmt(a):>12}{_fmt(b):>12}")
            if a and not b:
                avvisi.append(f"categoria {key[0]}/{key[1]} presente prima e ora assente")
            elif a and b and abs((b - a) / a) > SOGLIA_DELTA * 2:
                avvisi.append(f"categoria {key[0]}/{key[1]}: {a:,} -> {b:,} enti")
    if dopo["mancanti"]:
        avvisi.append(f"categorie in {_input_categorie().name} senza file estratto: "
                      f"{', '.join(dopo['mancanti'])}")
    return avvisi


# ============================================================================
# FLUSSO DI ELABORAZIONE DI UN ANNO
# ============================================================================

def elabora_anno(anno: int, nuovo: bool, db_ok: bool) -> bool:
    source = _source()
    input_cat = _input_categorie()
    cat_links = link_categorie(anno)

    titolo(f"ELABORAZIONE ANNO {anno} ({'nuovo' if nuovo else 'aggiornamento'})")
    print(f"""
  Passi previsti:
    1. Archivio dei file attuali in {ARCHIVIO.name}/ (ripristinabili)
    2. Download elenco complessivo AdE ed estrazione (fonte: {source})
    3. Download categorie ({len(cat_links)} link in {input_cat.name})
    4. Controllo 1: confronto con versione precedente e CSV grezzi AdE
    5. ETL dell'anno nel CSV normalizzato (--replace)
    6. Controllo 2: gli altri anni del CSV devono restare identici
    7. Excel derivati (report_{anno}.xlsx, scelte_categorie.xlsx)
    8. Pubblicazione DB in transazione {'' if db_ok else '(DB NON RAGGIUNGIBILE: sarà saltata)'}
    9. Ripartizioni, RUNTS, catalogo file, forecast
   10. Verifica finale -> Dati/verifiche/""")
    if not ask_yes_no("\n  Avvio la procedura?", default="s"):
        return False

    t0 = time.time()
    fase("Fotografia dello stato attuale")
    prima = None if nuovo else fotografia(anno)
    righe_csv_prima = _ver.conta_righe_csv_per_anno(CSV_NORM)

    arch = Archivio(anno)
    try:
        fase("1. Archivio")
        arch.archivia()

        fase("2. Download + estrazione elenco complessivo")
        if not _esegui(f"Download elenco {anno}",
                       [_pl.PYTHON, "cinque_per_mille.py", "--source", source,
                        "--anni", str(anno), "--yes"], "download"):
            raise Interrotto("download/estrazione elenco complessivo fallito")
        if not (DATI / f"dati_{anno}.xlsx").is_file():
            raise Interrotto(f"Dati/dati_{anno}.xlsx non prodotto: nessun file scaricato da AdE?")

        fase("3. Download + estrazione categorie")
        if cat_links:
            if not _esegui(f"Categorie {anno}",
                           [_pl.PYTHON, "scarica_categorie.py", "--input", str(input_cat),
                            "--source", source, "--anni", str(anno)], "categorie"):
                raise Interrotto("download/estrazione categorie fallito")
        else:
            log.warning(f"Nessun link categoria per il {anno} in {input_cat.name}: passo saltato")

        fase("4. Controllo 1 - dati estratti")
        dopo = fotografia(anno)
        if not dopo["estratto"] or dopo["estratto"]["cf_distinti"] == 0:
            raise Interrotto("l'estratto non contiene enti con codice fiscale")
        avvisi = confronta_fotografie(anno, prima, dopo)
        if avvisi:
            print("\n  [!] Da verificare:")
            for a in avvisi:
                print(f"      - {a}")
            if not ask_yes_no("\n  Proseguo con l'ETL nonostante gli avvisi?", default="n"):
                raise Interrotto("fermato dall'utente dopo il controllo 1")
        else:
            print("\n  Controllo 1 superato.")

        fase("5. ETL")
        if not _esegui(f"ETL {anno}", [_pl.PYTHON, "etl.py", "--anni", str(anno), "--replace"], "etl"):
            raise Interrotto("ETL fallito")

        fase("6. Controllo 2 - integrità del CSV normalizzato")
        righe_csv_dopo = _ver.conta_righe_csv_per_anno(CSV_NORM)
        alterati = [a for a in righe_csv_prima
                    if a != anno and righe_csv_prima[a] != righe_csv_dopo.get(a)]
        if alterati:
            raise Interrotto(f"l'ETL ha modificato le righe di altri anni: {alterati}")
        n_anno = righe_csv_dopo.get(anno, 0)
        if n_anno == 0:
            raise Interrotto(f"nessuna riga {anno} nel CSV dopo l'ETL (vedi log etl)")
        print(f"  Righe {anno} nel CSV: {righe_csv_prima.get(anno, 0):,} -> {n_anno:,}; "
              f"altri {len(righe_csv_prima) - (anno in righe_csv_prima)} anni invariati.")
        if n_anno != dopo["estratto"]["righe"]:
            print(f"  [!] righe CSV ({n_anno:,}) diverse dalle righe estratte con CF "
                  f"({dopo['estratto']['righe']:,})")
            if not ask_yes_no("  Proseguo?", default="n"):
                raise Interrotto("fermato dall'utente dopo il controllo 2")

    except (Interrotto, KeyboardInterrupt, Exception) as e:
        motivo = "interruzione manuale" if isinstance(e, KeyboardInterrupt) else str(e)
        log.error(f"PROCEDURA FERMATA: {motivo}")
        if not isinstance(e, (Interrotto, KeyboardInterrupt)):
            log.debug("dettaglio", exc_info=True)
        arch.ripristina()
        print(f"\n  Nessuna modifica al DB. File precedenti ripristinati.\n"
              f"  Archivio conservato in: {arch.dir}")
        return False

    # ---- Da qui i file locali sono nuovi e validati: niente più ripristino automatico ----
    fase("7. Excel derivati")
    if not _esegui(f"Report {anno}", [_pl.PYTHON, "report.py", "--anno", str(anno)], "report"):
        log.warning("report.py fallito: proseguo (rigenerabile con python report.py --anno ...)")
    if not _esegui("Pivot scelte per categoria", [_pl.PYTHON, "estrai_scelte_categorie.py"], "report"):
        log.warning("estrai_scelte_categorie.py fallito: proseguo")

    _pl._mark_done(str(ROOT), anno, "download")
    _pl._mark_done(str(ROOT), anno, "categorie")

    pubblicato = False
    if db_ok and ask_yes_no(f"\n  Dati locali pronti. Pubblico l'anno {anno} sul sito?", default="s"):
        pubblicato = pubblica_anno(anno, t0)
    elif not db_ok:
        print("\n  DB non raggiungibile da questa macchina: pubblicazione non eseguita.\n"
              "  Quando il DB è raggiungibile usa il menu 4 (Ripubblica un anno).")

    fase("10. Verifica finale")
    out, ris = _ver.esegui([anno], usa_db=db_ok)
    _ver.stampa_riepilogo(ris)
    n = sum(r["n_anomalie"] for r in ris)

    titolo(f"RIEPILOGO ANNO {anno}")
    print(f"  Dati locali:   aggiornati")
    print(f"  Pubblicazione: {'eseguita' if pubblicato else 'NON eseguita'}")
    print(f"  Verifica:      {'nessuna anomalia' if n == 0 else f'{n} controlli con differenze'} -> {out}")
    print(f"  Archivio:      {arch.dir}")
    print(f"  Durata:        {(time.time() - t0) / 60:.1f} minuti")
    return pubblicato and n == 0


def pubblica_anno(anno: int, t0: float | None = None) -> bool:
    """Passi 8-9: DB in transazione, finalizzazione, forecast."""
    from db_updater import sostituisci_anno, finalizza_ciclo
    t0 = t0 or time.time()

    fase("8. Pubblicazione DB (transazione)")
    csv_anno = _ver.leggi_csv_norm([anno], CSV_NORM).get(anno)
    if csv_anno is None or csv_anno.empty:
        log.error(f"Nessuna riga {anno} nel CSV normalizzato: niente da pubblicare")
        return False
    attesi = int(csv_anno["COD_FISCALE"].nunique())
    ok, info = sostituisci_anno(anno, CSV_NORM, DATI, attesi_enti=attesi)
    if not ok:
        print("\n  [X] Pubblicazione fallita: ROLLBACK eseguito, il sito mostra ancora i dati precedenti.\n"
              "      I dati locali sono aggiornati: puoi riprovare con il menu 4.")
        return False
    print(f"  enti {info['enti_prima']:,} -> {info['enti_dopo']:,}; "
          f"categoria_ammissioni {info['cat_prima']:,} -> {info['cat_dopo']:,}")
    _pl._mark_done(str(ROOT), anno, "etl")

    fase("9. Ripartizioni, RUNTS, catalogo file, forecast")
    if not finalizza_ciclo([anno], CSV_NORM, DATI, t_inizio=t0):
        log.warning("Finalizzazione con errori (ripartizioni/runts/catalogo): vedi log db_updater")
    if not _esegui("Forecast", [_pl.PYTHON, "forecast.py"], "report"):
        log.warning("forecast.py fallito")
    return True


# ============================================================================
# VOCI DI MENU
# ============================================================================

def menu_aggiungi(db_ok: bool) -> None:
    titolo("AGGIUNGI UN NUOVO ANNO")
    configurati = _anni_configurati()
    suggerito = str(max(configurati) + 1) if configurati else ""
    try:
        anno = int(chiedi("  Anno di riferimento (anno finanziario AdE)", suggerito))
    except ValueError:
        print("  Anno non valido.")
        return
    if anno in configurati:
        print(f"  Il {anno} è già configurato: usa 'Aggiorna un anno esistente'.")
        return
    if not controlli_preliminari(rete=True):
        return

    session = _sessione()
    while True:
        url = chiedi("  Link della pagina AdE 'elenco complessivo' dell'anno")
        if not url:
            return
        if not url.startswith("http"):
            print("  Link non valido.")
            continue
        n_pdf, n_csv = conta_link(url, session)
        print(f"  Trovati {n_pdf} PDF e {n_csv} CSV")
        if n_pdf + n_csv > 0:
            break
        print("  Nessun file trovato: controlla il link (deve essere la pagina con l'elenco dei file).")

    gia = {e["slug"] for e in link_categorie(anno)}
    cat_righe = chiedi_link_categorie(anno, gia, session)

    print(f"\n  Riepilogo: anno {anno}, elenco complessivo {n_pdf} PDF/{n_csv} CSV, "
          f"{len(cat_righe)} nuovi link categoria")
    if not ask_yes_no("  Registro in config.yaml e categorie.xlsx?", default="s"):
        return
    registra_url_anno(anno, url)
    if cat_righe:
        registra_link_categorie(anno, cat_righe)

    with Lock():
        elabora_anno(anno, nuovo=True, db_ok=db_ok)


def menu_aggiorna(db_ok: bool) -> None:
    titolo("AGGIORNA UN ANNO ESISTENTE")
    anni = _anni_configurati()
    if not controlli_preliminari(rete=True):
        return

    if ask_yes_no("  Controllo su AdE quali anni hanno file nuovi? (circa 1-2 s per anno)", default="s"):
        session = _sessione()
        print(f"\n  {'ANNO':<6}{'FILE ONLINE':>12}{'FILE LOCALI':>12}{'NUOVI SU AdE':>14}")
        for a in anni:
            n = novita_elenco(a, session)
            if "errore" in n:
                print(f"  {a:<6}  errore: {n['errore']}")
            else:
                flag = "  <-- novità" if n["nuovi"] else ""
                print(f"  {a:<6}{n['online']:>12}{n['locali']:>12}{len(n['nuovi']):>14}{flag}")

    try:
        anno = int(chiedi("\n  Anno da aggiornare"))
    except ValueError:
        print("  Anno non valido.")
        return
    if anno not in anni:
        print(f"  Il {anno} non è configurato: usa 'Aggiungi un nuovo anno'.")
        return

    presenti = link_categorie(anno)
    print(f"\n  Link categoria registrati per il {anno}: {len(presenti)}")
    for e in presenti:
        print(f"    - {e['categoria']}: {e['url']}")
    if len(presenti) < len(ETICHETTE_DEFAULT) and ask_yes_no(
            "  Aggiungo link per le categorie mancanti?", default="n"):
        nuove = chiedi_link_categorie(anno, {e["slug"] for e in presenti}, _sessione())
        if nuove:
            registra_link_categorie(anno, nuove)

    with Lock():
        elabora_anno(anno, nuovo=False, db_ok=db_ok)


def menu_verifica(db_ok: bool) -> None:
    titolo("VERIFICA DATI")
    anni = _anni_configurati()
    r = chiedi(f"  Anni da verificare (es. 2024,2023; Invio = tutti {min(anni)}-{max(anni)})")
    try:
        sel = [int(a) for a in r.split(",") if a.strip()] if r else anni
    except ValueError:
        print("  Formato non valido.")
        return
    dettaglio = ask_yes_no("  Includere il dettaglio per codice fiscale?", default="s")
    if not db_ok:
        print("  DB non raggiungibile: verifico solo GREZZI/ESTRATTO/CSV.")
    print(f"  Stima: circa 2-3 minuti per anno (lettura completa dei file).")
    out, ris = _ver.esegui(sel, usa_db=db_ok, dettaglio=dettaglio)
    _ver.stampa_riepilogo(ris)
    n = sum(x["n_anomalie"] for x in ris)
    print(f"  {'Nessuna anomalia' if n == 0 else f'{n} controlli con differenze (righe gialle)'}")
    print(f"  Report: {out}")


def menu_ripubblica(db_ok: bool) -> None:
    titolo("RIPUBBLICA UN ANNO SUL SITO")
    if not db_ok:
        print("  DB non raggiungibile: operazione impossibile da questa macchina.")
        return
    try:
        anno = int(chiedi("  Anno da ripubblicare"))
    except ValueError:
        return
    print("  Il DB dell'anno verrà sostituito con i dati del CSV normalizzato e dei file categoria locali.")
    if not ask_yes_no("  Procedo?", default="n"):
        return
    with Lock():
        ok = pubblica_anno(anno)
        out, ris = _ver.esegui([anno], usa_db=True)
        _ver.stampa_riepilogo(ris)
        print(f"  Pubblicazione: {'eseguita' if ok else 'NON eseguita'} - Report verifica: {out}")


# ============================================================================
# MAIN
# ============================================================================

def menu_sync(db_ok: bool) -> None:
    titolo("SINCRONIZZA SVILUPPO -> PRODUZIONE")
    import sync as _sync
    solo_db = _sync.cfg_file() is None
    if solo_db:
        print("  Sezione sync: di config.yaml non configurata: sincronizzo solo il DB (non i file).")
    try:
        _sync.cmd_sync(solo_db=solo_db, si=False)
    except _sync.Errore as e:
        print(f"\n  Sincronizzazione fermata: {e}\n  La produzione non è stata modificata.")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    _, log_file = get_logger("guida", ROOT)

    titolo("5x1000 - PROCEDURA GUIDATA")
    db_ok, db_msg = db_raggiungibile()
    print(f"  DB del sito: {'raggiungibile' if db_ok else 'NON raggiungibile - ' + db_msg}")
    anni = _anni_configurati()
    if anni:
        print(f"  Anni configurati: {min(anni)}-{max(anni)}")

    voci = {
        "1": ("Aggiungi un nuovo anno", menu_aggiungi),
        "2": ("Aggiorna un anno esistente (nuovi file AdE)", menu_aggiorna),
        "3": ("Verifica dati (AdE <-> CSV <-> DB)", menu_verifica),
        "4": ("Ripubblica un anno sul sito (dai dati locali)", menu_ripubblica),
        "5": ("Sincronizza sviluppo -> produzione", menu_sync),
        "0": ("Esci", None),
    }
    while True:
        print()
        for k, (label, _) in voci.items():
            print(f"  {k}. {label}")
        scelta = chiedi("\n  Cosa vuoi fare?")
        if scelta == "0" or scelta == "":
            break
        if scelta not in voci:
            continue
        try:
            voci[scelta][1](db_ok)
        except Interrotto as e:
            print(f"\n  Operazione annullata: {e}")
        except KeyboardInterrupt:
            print("\n  Operazione interrotta.")
    print(f"\n  Log: {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
