"""
Pipeline management API
=======================
POST /api/v1/pipeline/run        – avvia la pipeline in background
GET  /api/v1/pipeline/jobs       – lista job recenti (ultimi 20)
GET  /api/v1/pipeline/jobs/{id}  – stato e log di un job
DELETE /api/v1/pipeline/jobs/{id} – cancella un job dalla lista (solo se terminato)

Autenticazione: header  X-Pipeline-Key: <PIPELINE_API_KEY>
"""
from __future__ import annotations

import os
import sys
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])

# ---------------------------------------------------------------------------
# Job store in memoria
# ---------------------------------------------------------------------------

_jobs: Dict[str, dict] = {}
_jobs_lock = threading.Lock()
_MAX_JOBS = 20  # mantieni solo gli ultimi N job


def _prune_jobs():
    """Rimuovi i job più vecchi se si supera il limite."""
    if len(_jobs) <= _MAX_JOBS:
        return
    # Ordina per started_at e rimuovi i più vecchi
    sorted_ids = sorted(_jobs, key=lambda jid: _jobs[jid]["started_at"])
    for jid in sorted_ids[: len(_jobs) - _MAX_JOBS]:
        if _jobs[jid]["status"] != "running":
            del _jobs[jid]


# ---------------------------------------------------------------------------
# Modelli
# ---------------------------------------------------------------------------

class PipelineRunRequest(BaseModel):
    anni: Optional[str] = None          # es. "2023,2024" — anni target per ETL/report
    anni_download: Optional[str] = None # override anni da scaricare (liste complete)
    anni_categorie: Optional[str] = None# override anni da scaricare (per categoria)
    steps: Optional[List[str]] = None   # es. ["etl","gsheets"]
    skip_download: bool = False
    skip_gsheets: bool = True   # Google Sheets è opt-in: passa False per abilitare
    skip_report: bool = False
    no_runts: bool = False
    source: str = "csv"                 # "csv" | "pdf"
    smart: bool = True                  # analizza file esistenti e salta step già aggiornati
    gsheets_id: Optional[str] = None    # ID foglio Google esistente (vuoto = crea nuovo)


class JobSummary(BaseModel):
    job_id: str
    status: str            # running | completed | failed
    started_at: str
    finished_at: Optional[str]
    steps: List[str]
    anni: Optional[str]
    return_code: Optional[int]


class JobDetail(JobSummary):
    logs: str


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _check_api_key(key: Optional[str]):
    expected = settings.pipeline_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pipeline API non configurata: imposta PIPELINE_API_KEY.",
        )
    if key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key non valida.",
        )


# ---------------------------------------------------------------------------
# Runner in background thread
# ---------------------------------------------------------------------------

def _run_pipeline(job_id: str, cmd: List[str], root_dir: str):
    buf: List[str] = []

    def _append(line: str):
        with _jobs_lock:
            _jobs[job_id]["logs"] += line

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with _jobs_lock:
            _jobs[job_id]["pid"] = proc.pid

        for line in proc.stdout:
            _append(line)

        proc.wait()
        rc = proc.returncode
    except Exception as exc:
        _append(f"\n[ERRORE AVVIO] {exc}\n")
        rc = -1

    finished = datetime.now(timezone.utc).isoformat()
    with _jobs_lock:
        _jobs[job_id]["return_code"] = rc
        _jobs[job_id]["status"] = "completed" if rc == 0 else "failed"
        _jobs[job_id]["finished_at"] = finished


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/run",
    summary="Avvia la pipeline",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobSummary,
)
def run_pipeline(
    body: PipelineRunRequest,
    x_pipeline_key: Optional[str] = Header(default=None, alias="X-Pipeline-Key"),
):
    _check_api_key(x_pipeline_key)

    root_dir = settings.pipeline_root_dir

    # Costruisci comando
    cmd = [sys.executable, os.path.join(root_dir, "pipeline.py")]

    if body.anni:
        cmd += ["--anni", body.anni]
    if body.anni_download:
        cmd += ["--anni-download", body.anni_download]
    if body.anni_categorie:
        cmd += ["--anni-categorie", body.anni_categorie]
    if body.steps:
        cmd += ["--only", ",".join(body.steps)]
    if body.skip_download:
        cmd.append("--skip-download")
    if body.skip_gsheets:
        cmd.append("--skip-gsheets")
    if body.skip_report:
        cmd.append("--skip-report")
    if body.no_runts:
        cmd.append("--no-runts")
    if body.source and body.source != "csv":
        cmd += ["--source", body.source]
    if body.smart:
        cmd.append("--smart")
    if body.gsheets_id:
        cmd += ["--sheet-id", body.gsheets_id]

    job_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": started,
            "finished_at": None,
            "steps": body.steps or ["download", "categorie", "etl", "report", "gsheets"],
            "anni": body.anni,
            "return_code": None,
            "logs": "",
            "pid": None,
        }
        _prune_jobs()

    t = threading.Thread(target=_run_pipeline, args=(job_id, cmd, root_dir), daemon=True)
    t.start()

    return _job_summary(_jobs[job_id])


@router.get(
    "/jobs",
    summary="Lista job recenti",
    response_model=List[JobSummary],
)
def list_jobs(
    x_pipeline_key: Optional[str] = Header(default=None, alias="X-Pipeline-Key"),
):
    _check_api_key(x_pipeline_key)
    with _jobs_lock:
        sorted_jobs = sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)
    return [_job_summary(j) for j in sorted_jobs]


@router.get(
    "/jobs/{job_id}",
    summary="Dettaglio e log di un job",
    response_model=JobDetail,
)
def get_job(
    job_id: str,
    x_pipeline_key: Optional[str] = Header(default=None, alias="X-Pipeline-Key"),
):
    _check_api_key(x_pipeline_key)
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return {**_job_summary(job), "logs": job["logs"]}


@router.delete(
    "/jobs/{job_id}",
    summary="Rimuovi un job terminato dalla lista",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_job(
    job_id: str,
    x_pipeline_key: Optional[str] = Header(default=None, alias="X-Pipeline-Key"),
):
    _check_api_key(x_pipeline_key)
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job non trovato.")
        if job["status"] == "running":
            raise HTTPException(status_code=409, detail="Impossibile rimuovere un job in esecuzione.")
        del _jobs[job_id]


@router.get(
    "/analyze",
    summary="Analisi file esistenti — cosa manca o è obsoleto",
)
def analyze_pipeline(
    anni: Optional[str] = None,
    x_pipeline_key: Optional[str] = Header(default=None, alias="X-Pipeline-Key"),
):
    """
    Scansiona la cartella Dati/ e restituisce per ogni step/anno se i file sono
    presenti e aggiornati, mancanti, o obsoleti (stale).

    - **anni**: anni da verificare, separati da virgola (es. `2023,2024`).
      Se omesso, controlla tutti gli anni già presenti su disco.
    """
    _check_api_key(x_pipeline_key)
    try:
        import sys as _sys
        _sys.path.insert(0, settings.pipeline_root_dir)
        from pipeline_checker import full_analysis
        anni_list = [int(a.strip()) for a in anni.split(",") if a.strip()] if anni else None
        return full_analysis(settings.pipeline_root_dir, anni_list)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analisi fallita: {exc}")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _job_summary(j: dict) -> dict:
    return {
        "job_id":      j["job_id"],
        "status":      j["status"],
        "started_at":  j["started_at"],
        "finished_at": j["finished_at"],
        "steps":       j["steps"],
        "anni":        j["anni"],
        "return_code": j["return_code"],
    }
