"""
GET /download/files           – catalogo file disponibili
GET /download/file/{id}       – scarica un file per ID
GET /download/csv/completo    – CSV completo (tutti gli anni)
GET /download/csv/{anno}      – CSV filtrato per anno (generato al volo)
GET /download/xlsx/{anno}     – Excel per anno (file pre-generato)
GET /download/report/{anno}   – report Excel ASSIF/Bedogni
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from config import settings
from db import get_db, fetch_all, fetch_one

router = APIRouter(prefix="/download", tags=["Download"])


@router.get("/files", summary="Catalogo di tutti i file scaricabili")
def list_files(
    anno:   int | None = None,
    tipo:   str | None = None,
    db: Session = Depends(get_db),
):
    where_clauses = ["1=1"]
    params: dict = {}
    if anno:
        where_clauses.append("anno = :anno")
        params["anno"] = anno
    if tipo:
        where_clauses.append("tipo = :tipo")
        params["tipo"] = tipo

    where_sql = "WHERE " + " AND ".join(where_clauses)
    rows = fetch_all(
        db,
        f"""
        SELECT id, anno, tipo, categoria, formato,
               nome_file, dimensione_mb, sha256, aggiornato_il
        FROM dataset_files
        {where_sql}
        ORDER BY anno DESC, tipo, categoria
        """,
        params,
    )
    return rows


@router.get("/file/{file_id}", summary="Scarica un file per ID")
def download_by_id(file_id: int, db: Session = Depends(get_db)):
    row = fetch_one(
        db,
        "SELECT percorso, nome_file, formato FROM dataset_files WHERE id = :id",
        {"id": file_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="File non trovato")

    path = Path(row["percorso"])
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="File presente nel catalogo ma non trovato sul server",
        )

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if row["formato"] == "xlsx"
        else "text/csv"
    )
    return FileResponse(
        path=str(path),
        filename=row["nome_file"],
        media_type=media_type,
    )


@router.get("/csv/completo", summary="Scarica il dataset CSV completo (~210 MB)")
def download_csv_completo(db: Session = Depends(get_db)):
    row = fetch_one(
        db,
        "SELECT percorso FROM dataset_files WHERE tipo='completo' AND formato='csv' LIMIT 1",
    )
    path = Path(row["percorso"]) if row else settings.dati_dir / "enti_5x1000_norm.csv"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset non ancora generato")

    return FileResponse(
        path=str(path),
        filename="enti_5x1000_norm.csv",
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="enti_5x1000_norm.csv"'
        },
    )


@router.get("/csv/{anno}", summary="Scarica CSV filtrato per anno (generato al volo)")
def download_csv_anno(anno: int, db: Session = Depends(get_db)):
    """
    Estrae dal CSV completo solo le righe dell'anno richiesto e le
    restituisce come stream, senza creare un file temporaneo su disco.
    """
    row = fetch_one(
        db,
        "SELECT percorso FROM dataset_files WHERE tipo='completo' AND formato='csv' LIMIT 1",
    )
    csv_full = Path(row["percorso"]) if row else settings.dati_dir / "enti_5x1000_norm.csv"

    if not csv_full.exists():
        raise HTTPException(status_code=404, detail="Dataset non ancora generato")

    def _stream():
        with open(csv_full, "r", encoding="utf-8", errors="replace") as fh:
            header = fh.readline()
            yield header
            for line in fh:
                # Le prime 4 cifre sono l'anno (colonna ANNO è la prima)
                if line.startswith(str(anno) + ","):
                    yield line

    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="enti_5x1000_{anno}.csv"'
        },
    )


@router.get("/xlsx/{anno}", summary="Scarica Excel normalizzato per anno")
def download_xlsx_anno(anno: int, db: Session = Depends(get_db)):
    row = fetch_one(
        db,
        "SELECT percorso, nome_file FROM dataset_files WHERE anno=:a AND tipo='normalizzato' AND formato='xlsx'",
        {"a": anno},
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"File Excel per anno {anno} non trovato")

    path = Path(row["percorso"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non trovato sul server")

    return FileResponse(
        path=str(path),
        filename=row["nome_file"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/report/{anno}", summary="Scarica report Excel ASSIF/Bedogni per anno")
def download_report_anno(anno: int, db: Session = Depends(get_db)):
    row = fetch_one(
        db,
        "SELECT percorso, nome_file FROM dataset_files WHERE anno=:a AND tipo='report' AND formato='xlsx'",
        {"a": anno},
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Report per anno {anno} non trovato")

    path = Path(row["percorso"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non trovato sul server")

    return FileResponse(
        path=str(path),
        filename=row["nome_file"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
