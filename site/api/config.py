"""Configurazione centralizzata tramite variabili d'ambiente."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Carica .env se presente nella stessa cartella
load_dotenv(Path(__file__).parent / ".env")


class Settings:
    # Database
    db_host:     str = os.getenv("SITE_DB_HOST", "localhost")
    db_port:     int = int(os.getenv("SITE_DB_PORT", "3306"))
    db_user:     str = os.getenv("SITE_DB_USER", "")
    db_password: str = os.getenv("SITE_DB_PASSWORD", "")
    db_name:     str = os.getenv("SITE_DB_NAME", "cinque_per_mille")

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    # Cartella Dati/ della pipeline (per download file)
    dati_dir: Path = Path(os.getenv("DATI_DIR", "Dati"))

    # CORS
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]

    # Paginazione default
    page_size_default: int = 50
    page_size_max:     int = 1000


settings = Settings()
