#!/usr/bin/env bash
# deploy.sh — Aggiorna il sito 5x1000 dal repository e ricompila il frontend
#
# Uso:
#   chmod +x deploy.sh        # solo la prima volta
#   ./site/deploy.sh          # dalla root del repo
#   bash site/deploy.sh       # alternativa senza chmod
#
# Variabili d'ambiente opzionali:
#   BRANCH   — branch da cui fare pull (default: branch corrente)
#   SKIP_PULL — se impostata, salta il git pull (es. SKIP_PULL=1 ./site/deploy.sh)

set -euo pipefail

# ── Colori per output ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✓ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
fail()    { echo -e "${RED}✗ $*${NC}"; exit 1; }

# ── Root del repository ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

cd "$REPO_ROOT"
info "Repository: $REPO_ROOT"

# ── 1. Git pull ───────────────────────────────────────────────────────────────
if [[ -z "${SKIP_PULL:-}" ]]; then
    BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
    info "git pull origin $BRANCH"
    git pull origin "$BRANCH" || fail "git pull fallito"
    success "Codice aggiornato (branch: $BRANCH)"
else
    warn "SKIP_PULL impostata — git pull saltato"
fi

# ── 2. Node.js disponibile? ───────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    fail "Node.js non trovato. Installalo con: curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && apt-get install -y nodejs"
fi
NODE_VER=$(node --version)
info "Node.js $NODE_VER"

# ── 3. npm install (solo se package-lock.json è cambiato) ────────────────────
cd "$FRONTEND_DIR"
if git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -q "frontend/package-lock.json"; then
    info "package-lock.json modificato → npm ci"
    npm ci --prefer-offline || fail "npm ci fallito"
    success "Dipendenze aggiornate"
elif [[ ! -d node_modules ]]; then
    info "node_modules assente → npm ci"
    npm ci --prefer-offline || fail "npm ci fallito"
    success "Dipendenze installate"
else
    info "node_modules OK — npm install saltato"
fi

# ── 4. Build frontend ─────────────────────────────────────────────────────────
info "npm run build"
npm run build || fail "Build fallita"
success "Frontend compilato → $SCRIPT_DIR/public/"

# ── 5. Riepilogo ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deploy completato con successo!${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "  Branch : $(git rev-parse --abbrev-ref HEAD)"
echo -e "  Commit : $(git rev-parse --short HEAD) — $(git log -1 --format='%s')"
echo -e "  Build  : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
