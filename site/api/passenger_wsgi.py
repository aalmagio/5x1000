"""
Passenger WSGI entry point per Plesk.

FastAPI è un'app ASGI, ma Plesk Passenger usa WSGI.
Usiamo a2wsgi per il bridge ASGI → WSGI.

Prerequisito: aggiungere a2wsgi in requirements.txt (già incluso).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import app
from a2wsgi import ASGIMiddleware

# Passenger cerca la variabile 'application' come callable WSGI
application = ASGIMiddleware(app)
