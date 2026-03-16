"""
GET /api/v1/enti                      – lista paginata con filtri
GET /api/v1/enti/{codice_fiscale}     – storico completo di un ente
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from config import settings
from db import get_db, fetch_all, fetch_one

router = APIRouter(tags=["Enti"])

# Colonne restituibili (whitelist per sicurezza)
_COLONNE = (
    "anno", "cod_fiscale", "denominazione", "regione", "provincia", "comune",
    "categoria_principale", "cat_volontariato", "cat_asd", "cat_ets_onlus",
    "cat_ricerca_sci", "cat_ricerca_san", "cat_comuni", "cat_beni_cult",
    "cat_aree_prot", "n_scelte", "importo_espresso", "importo_generico",
    "importo_totale", "runts_denominazione", "runts_sezione",
    "runts_sede_comune", "runts_sede_prov", "runts_5x1000",
    "runts_data_iscrizione",
)


@router.get("/enti", summary="Ricerca enti con filtri multipli")
def get_enti(
    anno:       int | None     = Query(None, description="Anno (es. 2024)"),
    categoria:  str | None     = Query(None, description="Categoria principale"),
    regione:    str | None     = Query(None, description="Regione (es. LOMBARDIA)"),
    provincia:  str | None     = Query(None, description="Sigla provincia (es. MI)"),
    cf:         str | None     = Query(None, description="Codice fiscale esatto"),
    q:          str | None     = Query(None, description="Ricerca nel nome (LIKE)"),
    runts_only: bool           = Query(False, description="Solo enti iscritti RUNTS"),
    pagina:     int            = Query(1, ge=1, description="Numero pagina"),
    per_pagina: int            = Query(
        settings.page_size_default,
        ge=1,
        le=settings.page_size_max,
        description=f"Righe per pagina (max {settings.page_size_max})",
    ),
    db: Session = Depends(get_db),
):
    where_clauses = []
    params: dict = {}

    if anno:
        where_clauses.append("anno = :anno")
        params["anno"] = anno
    if categoria:
        where_clauses.append("categoria_principale = :categoria")
        params["categoria"] = categoria
    if regione:
        where_clauses.append("regione = :regione")
        params["regione"] = regione.upper()
    if provincia:
        where_clauses.append("provincia = :provincia")
        params["provincia"] = provincia.upper()
    if cf:
        where_clauses.append("cod_fiscale = :cf")
        params["cf"] = cf.upper()
    if q:
        where_clauses.append("denominazione LIKE :q")
        params["q"] = f"%{q}%"
    if runts_only:
        where_clauses.append("runts_5x1000 = 1")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Totale risultati (senza paginazione)
    count_row = fetch_one(
        db,
        f"SELECT COUNT(*) AS tot FROM enti {where_sql}",
        params,
    )
    totale = count_row["tot"] if count_row else 0

    # Dati paginati
    offset = (pagina - 1) * per_pagina
    params["limit"]  = per_pagina
    params["offset"] = offset

    rows = fetch_all(
        db,
        f"""
        SELECT {", ".join(_COLONNE)}
        FROM enti
        {where_sql}
        ORDER BY anno DESC, importo_totale DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    return {
        "totale":    totale,
        "pagina":    pagina,
        "per_pagina": per_pagina,
        "pagine":    -(-totale // per_pagina),  # ceil division
        "data":      rows,
    }


@router.get(
    "/enti/{codice_fiscale}",
    summary="Storico completo di un ente per codice fiscale",
)
def get_ente_storico(
    codice_fiscale: str,
    db: Session = Depends(get_db),
):
    cf = codice_fiscale.upper().strip()
    rows = fetch_all(
        db,
        f"""
        SELECT {", ".join(_COLONNE)}
        FROM enti
        WHERE cod_fiscale = :cf
        ORDER BY anno ASC
        """,
        {"cf": cf},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Ente non trovato")

    # Info ente dall'anno più recente
    latest = rows[-1]
    return {
        "cod_fiscale":        cf,
        "denominazione":      latest.get("denominazione"),
        "categoria":          latest.get("categoria_principale"),
        "runts_denominazione": latest.get("runts_denominazione"),
        "anni_presenti":      [r["anno"] for r in rows],
        "storico":            rows,
    }
