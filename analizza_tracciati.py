#!/usr/bin/env python3
"""
analizza_tracciati.py — Evoluzione dei tracciati PDF/CSV 5x1000

Compara le intestazioni dei file Excel (elenco generale e per-categoria)
negli ultimi N anni e produce un report Excel multi-foglio:

  - Un foglio per dataset (elenco generale + ogni categoria):
    matrice campo × anno con marcatura nuovi/rimossi/rinominati
  - "Variazioni": riepilogo tabellare di ogni cambiamento
  - "Confronto_Categorie": stessa categoria, stesso anno, campi a confronto

Uso:
    python analizza_tracciati.py
    python analizza_tracciati.py --dati Dati --anni 5
    python analizza_tracciati.py --output report_tracciati.xlsx
"""

import argparse
import difflib
import sys
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter
except ImportError:
    print("Richiesto openpyxl: pip install openpyxl")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

CATEGORIE_SLUG = [
    "ETS_ONLUS",
    "ASD",
    "Ricerca_scientifica",
    "Ricerca_sanitaria",
    "Comuni",
    "Beni_culturali",
    "Aree_protette",
]

C_HEADER   = "2F5496"
C_PRESENT  = "D6E4BC"
C_ABSENT   = "F2F2F2"
C_NEW      = "C6EFCE"
C_REMOVED  = "FFC7CE"
C_RENAMED  = "FFEB9C"

# ---------------------------------------------------------------------------
# Lettura intestazioni
# ---------------------------------------------------------------------------

def get_headers(xlsx_path: Path) -> list[str]:
    """Legge le intestazioni (prima riga non vuota) di un file Excel."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
            headers = [str(c).strip() if c is not None else "" for c in row]
            headers = [h for h in headers if h]
            if headers:
                wb.close()
                return headers
        wb.close()
    except Exception as e:
        print(f"  [WARN] {xlsx_path.name}: {e}")
    return []

# ---------------------------------------------------------------------------
# Analisi
# ---------------------------------------------------------------------------

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_renames(removed: list[str], added: list[str], threshold: float = 0.72) -> dict[str, str]:
    """Heuristica: accoppia campi rimossi/aggiunti con alta similarità."""
    renames: dict[str, str] = {}
    used: set[str] = set()
    for rem in removed:
        best_score, best_match = 0.0, None
        for add in added:
            if add in used:
                continue
            s = similarity(rem, add)
            if s > best_score:
                best_score, best_match = s, add
        if best_match and best_score >= threshold:
            renames[rem] = best_match
            used.add(best_match)
    return renames


def analizza_dataset(nome: str, headers_per_anno: dict[int, list[str]], anni: list[int]) -> dict:
    """
    Costruisce la matrice campo×anno e calcola le variazioni tra anni consecutivi.
    """
    anni_presenti = [a for a in anni if a in headers_per_anno]

    # Tutti i campi in ordine di prima apparizione
    all_fields: list[str] = []
    seen: set[str] = set()
    for anno in sorted(anni_presenti):
        for h in headers_per_anno[anno]:
            if h not in seen:
                all_fields.append(h)
                seen.add(h)

    # Matrice: campo → {anno: True/False}
    matrix: dict[str, dict[int, bool]] = {
        field: {anno: field in headers_per_anno.get(anno, []) for anno in anni}
        for field in all_fields
    }

    # Variazioni tra anni consecutivi
    variazioni = []
    for i in range(1, len(anni_presenti)):
        ap, ac = sorted(anni_presenti)[i - 1], sorted(anni_presenti)[i]
        hp = set(headers_per_anno.get(ap, []))
        hc = set(headers_per_anno.get(ac, []))
        added   = [h for h in headers_per_anno.get(ac, []) if h not in hp]
        removed = [h for h in headers_per_anno.get(ap, []) if h not in hc]
        renames = find_renames(removed, added)
        variazioni.append({
            "da": ap, "a": ac,
            "aggiunti": added, "rimossi": removed, "rinominati": renames,
            "n_da": len(hp), "n_a": len(hc),
        })

    return {
        "nome": nome,
        "anni": anni,
        "anni_presenti": anni_presenti,
        "all_fields": all_fields,
        "matrix": matrix,
        "variazioni": variazioni,
        "headers_per_anno": headers_per_anno,
    }

# ---------------------------------------------------------------------------
# Scrittura fogli
# ---------------------------------------------------------------------------

def _hdr_cell(ws, row, col, value):
    c = ws.cell(row, col, value)
    c.fill = PatternFill("solid", fgColor=C_HEADER)
    c.font = Font(color="FFFFFF", bold=True, size=9)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    return c


def write_matrix_sheet(wb, dataset: dict, anni: list[int]):
    """Foglio matrice: righe=campi, colonne=anni."""
    title = dataset["nome"][:31]
    ws = wb.create_sheet(title=title)

    f_present = PatternFill("solid", fgColor=C_PRESENT)
    f_absent  = PatternFill("solid", fgColor=C_ABSENT)
    f_new     = PatternFill("solid", fgColor=C_NEW)
    f_removed = PatternFill("solid", fgColor=C_REMOVED)
    f_renamed = PatternFill("solid", fgColor=C_RENAMED)
    align_c   = Alignment(horizontal="center", vertical="center")

    # Calcola mappa rinominate per colorazione
    rename_old: dict[str, int] = {}  # campo_vecchio → anno_rimozione
    rename_new: dict[str, int] = {}  # campo_nuovo   → anno_aggiunta
    for v in dataset["variazioni"]:
        for old, new in v["rinominati"].items():
            rename_old[old] = v["a"]
            rename_new[new] = v["a"]

    # Intestazione
    _hdr_cell(ws, 1, 1, "Campo")
    ws.column_dimensions["A"].width = 42
    for j, anno in enumerate(anni, 2):
        _hdr_cell(ws, 1, j, str(anno))
        ws.column_dimensions[get_column_letter(j)].width = 9

    # Righe
    for i, field in enumerate(dataset["all_fields"], 2):
        ws.cell(i, 1, field).font = Font(size=9)
        for j, anno in enumerate(anni, 2):
            present  = dataset["matrix"][field].get(anno, False)
            prev_idx = j - 3  # indice dell'anno precedente nella lista anni
            prev_anno = anni[prev_idx] if prev_idx >= 0 else None
            prev_present = dataset["matrix"][field].get(prev_anno) if prev_anno is not None else None

            c = ws.cell(i, j)
            c.alignment = align_c
            c.font = Font(size=9)

            if present:
                if field in rename_new and rename_new[field] == anno:
                    c.value, c.fill = "R↑", f_renamed
                elif prev_present is False:
                    c.value, c.fill = "+", f_new
                else:
                    c.value, c.fill = "✓", f_present
            else:
                if field in rename_old and rename_old[field] == anno:
                    c.value, c.fill = "R↓", f_renamed
                elif prev_present:
                    c.value, c.fill = "−", f_removed
                else:
                    c.value, c.fill = "", f_absent

    # Conteggio campi
    row_tot = len(dataset["all_fields"]) + 2
    ws.cell(row_tot, 1, "N° campi totali").font = Font(bold=True, size=9)
    for j, anno in enumerate(anni, 2):
        n = len(dataset["headers_per_anno"].get(anno, []))
        c = ws.cell(row_tot, j, n if n else "")
        c.font = Font(bold=True, size=9)
        c.alignment = Alignment(horizontal="center")

    # Legenda
    row_leg = row_tot + 2
    ws.cell(row_leg, 1, "Legenda").font = Font(bold=True, size=9)
    for k, (label, fill) in enumerate([
        ("✓  Presente", f_present),
        ("+  Campo aggiunto", f_new),
        ("−  Campo rimosso", f_removed),
        ("R↑ / R↓  Potenziale rinomina", f_renamed),
        ("   Assente / non disponibile", f_absent),
    ], 1):
        c = ws.cell(row_leg + k, 1, label)
        c.fill = fill
        c.font = Font(size=9)

    ws.freeze_panes = "B2"


def write_variazioni_sheet(wb, all_datasets: list[dict]):
    """Foglio riepilogo tabellare di tutte le variazioni."""
    ws = wb.create_sheet(title="Variazioni")

    cols = ["Dataset", "Da anno", "A anno", "Tipo", "Campo", "→ Rinominato in", "N° campi da", "N° campi a", "Δ"]
    for j, h in enumerate(cols, 1):
        _hdr_cell(ws, 1, j, h)

    f_new     = PatternFill("solid", fgColor=C_NEW)
    f_removed = PatternFill("solid", fgColor=C_REMOVED)
    f_renamed = PatternFill("solid", fgColor=C_RENAMED)

    row = 2
    for ds in all_datasets:
        for v in ds["variazioni"]:
            renamed_new_set = set(v["rinominati"].values())
            renamed_old_set = set(v["rinominati"].keys())

            for campo in v["aggiunti"]:
                if campo in renamed_new_set:
                    continue
                ws.cell(row, 1, ds["nome"])
                ws.cell(row, 2, v["da"])
                ws.cell(row, 3, v["a"])
                c = ws.cell(row, 4, "AGGIUNTO")
                c.fill = f_new
                c.font = Font(bold=True, size=9)
                ws.cell(row, 5, campo)
                ws.cell(row, 7, v["n_da"])
                ws.cell(row, 8, v["n_a"])
                ws.cell(row, 9, v["n_a"] - v["n_da"])
                row += 1

            for campo in v["rimossi"]:
                if campo in renamed_old_set:
                    continue
                ws.cell(row, 1, ds["nome"])
                ws.cell(row, 2, v["da"])
                ws.cell(row, 3, v["a"])
                c = ws.cell(row, 4, "RIMOSSO")
                c.fill = f_removed
                c.font = Font(bold=True, size=9)
                ws.cell(row, 5, campo)
                ws.cell(row, 7, v["n_da"])
                ws.cell(row, 8, v["n_a"])
                ws.cell(row, 9, v["n_a"] - v["n_da"])
                row += 1

            for old, new in v["rinominati"].items():
                ws.cell(row, 1, ds["nome"])
                ws.cell(row, 2, v["da"])
                ws.cell(row, 3, v["a"])
                c = ws.cell(row, 4, "RINOMINATO?")
                c.fill = f_renamed
                c.font = Font(bold=True, size=9)
                ws.cell(row, 5, old)
                ws.cell(row, 6, new)
                ws.cell(row, 7, v["n_da"])
                ws.cell(row, 8, v["n_a"])
                ws.cell(row, 9, v["n_a"] - v["n_da"])
                row += 1

    for col, w in zip("ABCDEFGHI", [22, 9, 9, 14, 40, 40, 11, 11, 6]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"


def write_confronto_categorie_sheet(wb, cat_datasets: list[dict], anni: list[int]):
    """Per ogni anno: matrice campo × categoria (solo ammessi)."""
    ws = wb.create_sheet(title="Confronto_Categorie")
    f_present = PatternFill("solid", fgColor=C_PRESENT)
    f_absent  = PatternFill("solid", fgColor=C_ABSENT)
    align_c   = Alignment(horizontal="center", vertical="center")

    row = 1
    for anno in sorted(anni, reverse=True):
        cat_con_dati = [ds for ds in cat_datasets if ds["headers_per_anno"].get(anno)]
        if not cat_con_dati:
            continue

        # Titolo anno
        c = ws.cell(row, 1, f"── Anno {anno} ──")
        c.font = Font(bold=True, size=11, color=C_HEADER)
        row += 1

        # Header categorie
        _hdr_cell(ws, row, 1, "Campo")
        ws.column_dimensions["A"].width = 42
        for j, ds in enumerate(cat_con_dati, 2):
            _hdr_cell(ws, row, j, ds["nome"])
            ws.column_dimensions[get_column_letter(j)].width = 16
        row += 1

        # Tutti i campi per quell'anno (ordine di prima apparizione)
        all_fields: list[str] = []
        seen: set[str] = set()
        for ds in cat_con_dati:
            for h in ds["headers_per_anno"].get(anno, []):
                if h not in seen:
                    all_fields.append(h)
                    seen.add(h)

        for field in all_fields:
            ws.cell(row, 1, field).font = Font(size=9)
            for j, ds in enumerate(cat_con_dati, 2):
                present = field in ds["headers_per_anno"].get(anno, [])
                c = ws.cell(row, j)
                c.value = "✓" if present else "—"
                c.fill = f_present if present else f_absent
                c.alignment = align_c
                c.font = Font(size=9)
            row += 1

        row += 2

    ws.freeze_panes = "B2"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Analisi evoluzione tracciati 5x1000",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python analizza_tracciati.py                        # ultimi 5 anni, output in Dati/
  python analizza_tracciati.py --anni 3               # ultimi 3 anni
  python analizza_tracciati.py --output report.xlsx   # percorso output custom
        """,
    )
    ap.add_argument("--dati",   default="Dati",                        help="Cartella Dati/ (default: Dati)")
    ap.add_argument("--anni",   type=int, default=5,                   help="Ultimi N anni da analizzare (default: 5)")
    ap.add_argument("--output", default="Dati/report_tracciati.xlsx",  help="File Excel di output")
    args = ap.parse_args()

    dati_dir = Path(args.dati)
    if not dati_dir.exists():
        print(f"Errore: cartella non trovata: {dati_dir}")
        sys.exit(1)

    # Anni disponibili dai file dati_XXXX.xlsx
    anni_disponibili = sorted(
        int(f.stem.split("_")[1])
        for f in dati_dir.glob("dati_[0-9]*.xlsx")
        if len(f.stem.split("_")) >= 2 and f.stem.split("_")[1].isdigit()
    )
    if not anni_disponibili:
        print(f"Nessun file dati_XXXX.xlsx trovato in {dati_dir}/")
        sys.exit(1)

    anni = anni_disponibili[-args.anni:]
    print(f"Anni analizzati: {anni}")
    print()

    all_datasets: list[dict] = []

    # --- Elenco generale ---
    print("=== Elenco generale ===")
    headers_generale: dict[int, list[str]] = {}
    for anno in anni:
        f = dati_dir / f"dati_{anno}.xlsx"
        if f.exists():
            h = get_headers(f)
            if h:
                headers_generale[anno] = h
                print(f"  {anno}: {len(h)} campi")
            else:
                print(f"  {anno}: vuoto/illeggibile")
        else:
            print(f"  {anno}: mancante")

    if headers_generale:
        all_datasets.append(analizza_dataset("Elenco_Generale", headers_generale, anni))

    # --- Categorie ---
    print()
    print("=== Categorie ===")
    cat_datasets: list[dict] = []
    for slug in CATEGORIE_SLUG:
        cat_dir = dati_dir / slug
        if not cat_dir.exists():
            print(f"  {slug}: cartella mancante")
            continue

        headers_cat: dict[int, list[str]] = {}
        for anno in anni:
            files = sorted(cat_dir.glob(f"{anno}_*_ammessi.xlsx"))
            if files:
                h = get_headers(files[0])
                if h:
                    headers_cat[anno] = h

        if headers_cat:
            anni_trovati = sorted(headers_cat.keys())
            print(f"  {slug}: {anni_trovati} — {[len(headers_cat[a]) for a in anni_trovati]} campi")
            ds = analizza_dataset(slug, headers_cat, anni)
            cat_datasets.append(ds)
            all_datasets.append(ds)
        else:
            print(f"  {slug}: nessun file ammessi trovato")

    if not all_datasets:
        print("\nNessun dato trovato. Verifica che Dati/ contenga i file xlsx.")
        sys.exit(1)

    # --- Output ---
    print()
    print(f"Scrittura report: {args.output}")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for ds in all_datasets:
        write_matrix_sheet(wb, ds, anni)
        print(f"  Foglio '{ds['nome']}': {len(ds['all_fields'])} campi unici")

    write_variazioni_sheet(wb, all_datasets)
    print(f"  Foglio 'Variazioni'")

    if cat_datasets:
        write_confronto_categorie_sheet(wb, cat_datasets, anni)
        print(f"  Foglio 'Confronto_Categorie'")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"\nReport salvato: {out}")


if __name__ == "__main__":
    main()
