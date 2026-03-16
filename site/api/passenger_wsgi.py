"""
Passenger WSGI entry point per Plesk.
Plesk cerca questo file nella document root dell'applicazione Python.

Setup Plesk:
  - Application mode: Python
  - Application root: /var/www/vhosts/tuodominio.it/site/api
  - WSGI entry point: passenger_wsgi.py
  - Startup file: passenger_wsgi.py
"""
import sys
from pathlib import Path

# Aggiungi la directory dell'app al path Python
sys.path.insert(0, str(Path(__file__).parent))

# Importa l'app FastAPI e crea l'interfaccia WSGI tramite uvicorn
from main import app  # noqa: E402

# Passenger usa la variabile 'application' come entry point WSGI
from uvicorn.middleware.wsgi import WSGIMiddleware  # noqa: E402

# FastAPI è ASGI: usiamo il bridge ASGI→WSGI di uvicorn
# (Passenger >= 6.0 supporta ASGI nativo – se disponibile usa application = app)
try:
    # Plesk Passenger >= 6 con supporto ASGI
    application = app
except Exception:
    application = WSGIMiddleware(app)
