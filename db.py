#!/usr/bin/env python3
"""
db.py — Factory centralizzata per la connessione MySQL del sito 5×1000.

Configurazione tramite variabili d'ambiente (o file .env):
  SITE_DB_HOST      default: localhost
  SITE_DB_PORT      default: 3306
  SITE_DB_USER      obbligatorio
  SITE_DB_PASSWORD  obbligatorio
  SITE_DB_NAME      obbligatorio

Uso:
    from db import get_connection, db_available

    if not db_available():
        logging.warning("DB non configurato, skip.")
    else:
        conn = get_connection()
        with conn:
            ...
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _db_params(override: dict | None = None) -> dict:
    """Restituisce il dict di connessione pymysql basato su env vars."""
    cfg = {
        "host":       os.getenv("SITE_DB_HOST", "localhost"),
        "port":       int(os.getenv("SITE_DB_PORT", "3306")),
        "user":       os.getenv("SITE_DB_USER", ""),
        "password":   os.getenv("SITE_DB_PASSWORD", ""),
        "database":   os.getenv("SITE_DB_NAME", ""),
        "charset":    "utf8mb4",
        "autocommit": True,
    }
    if override:
        cfg.update(override)
    return cfg


def db_available(override: dict | None = None) -> bool:
    """
    Restituisce True se pymysql è installato e le credenziali minime
    (SITE_DB_USER e SITE_DB_NAME) sono configurate.
    """
    try:
        import pymysql  # noqa: F401
    except ImportError:
        return False
    cfg = _db_params(override)
    return bool(cfg["user"] and cfg["database"])


def get_connection(override: dict | None = None):
    """
    Apre e restituisce una connessione pymysql.

    Solleva ImportError se pymysql non è installato,
    RuntimeError se le credenziali non sono configurate,
    pymysql.Error in caso di errore di connessione.
    """
    try:
        import pymysql
    except ImportError as exc:
        raise ImportError(
            "pymysql non installato. Installa con: pip install pymysql"
        ) from exc

    cfg = _db_params(override)
    if not cfg["user"] or not cfg["database"]:
        raise RuntimeError(
            "Credenziali DB non configurate. "
            "Imposta SITE_DB_USER e SITE_DB_NAME in .env o come variabili d'ambiente."
        )

    return pymysql.connect(**cfg)
