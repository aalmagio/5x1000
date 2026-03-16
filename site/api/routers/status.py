"""
GET /api/v1/status        – stato generale e ultimo aggiornamento
GET /api/v1/anni          – elenco anni disponibili
GET /api/v1/categorie     – elenco categorie disponibili
GET /api/v1/statistiche   – aggregazioni per anno
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db, fetch_one, fetch_all

router = APIRouter(tags=["Status"])


@router.get("/status", summary="Stato del dataset e ultimo aggiornamento")
def get_status(db: Session = Depends(get_db)):
    last_run = fetch_one(
        db,
        """
        SELECT run_at, anni_processati, righe_totali, status
        FROM pipeline_runs
        WHERE status = 'ok'
        ORDER BY run_at DESC
        LIMIT 1
        """,
    )
    anni = fetch_all(db, "SELECT DISTINCT anno FROM enti ORDER BY anno DESC")
    return {
        "ultimo_aggiornamento": last_run["run_at"].isoformat() if last_run else None,
        "anni_disponibili":     [r["anno"] for r in anni],
        "righe_totali":         last_run["righe_totali"] if last_run else 0,
        "stato_pipeline":       last_run["status"] if last_run else "n/a",
    }


@router.get("/anni", summary="Anni disponibili nel dataset")
def get_anni(db: Session = Depends(get_db)):
    rows = fetch_all(db, "SELECT DISTINCT anno FROM enti ORDER BY anno DESC")
    return [r["anno"] for r in rows]


@router.get("/categorie", summary="Categorie disponibili")
def get_categorie():
    return [
        "volontariato",
        "asd",
        "ets_onlus",
        "ricerca_scientifica",
        "ricerca_sanitaria",
        "comuni",
        "beni_culturali",
        "aree_protette",
    ]


@router.get("/statistiche", summary="Aggregazioni per anno (e per regione/categoria)")
def get_statistiche(
    anno: int | None = None,
    db: Session = Depends(get_db),
):
    where = "WHERE anno = :anno" if anno else ""
    params = {"anno": anno} if anno else {}

    totali = fetch_one(
        db,
        f"""
        SELECT
          COUNT(*)              AS n_enti,
          SUM(n_scelte)         AS totale_scelte,
          SUM(importo_totale)   AS totale_importo,
          MIN(anno)             AS anno_min,
          MAX(anno)             AS anno_max
        FROM enti
        {where}
        """,
        params,
    )

    per_categoria = fetch_all(
        db,
        f"""
        SELECT
          categoria_principale,
          COUNT(*)            AS n_enti,
          SUM(n_scelte)       AS totale_scelte,
          SUM(importo_totale) AS totale_importo
        FROM enti
        {where}
        WHERE categoria_principale IS NOT NULL
        GROUP BY categoria_principale
        ORDER BY totale_importo DESC
        """,
        params,
    ) if not anno else fetch_all(
        db,
        """
        SELECT
          categoria_principale,
          COUNT(*)            AS n_enti,
          SUM(n_scelte)       AS totale_scelte,
          SUM(importo_totale) AS totale_importo
        FROM enti
        WHERE anno = :anno AND categoria_principale IS NOT NULL
        GROUP BY categoria_principale
        ORDER BY totale_importo DESC
        """,
        params,
    )

    per_regione = fetch_all(
        db,
        f"""
        SELECT
          regione,
          COUNT(*)            AS n_enti,
          SUM(n_scelte)       AS totale_scelte,
          SUM(importo_totale) AS totale_importo
        FROM enti
        {where}
        WHERE regione IS NOT NULL
        GROUP BY regione
        ORDER BY totale_importo DESC
        """,
        params,
    )

    return {
        "anno":          anno,
        "totali":        totali,
        "per_categoria": per_categoria,
        "per_regione":   per_regione,
    }
