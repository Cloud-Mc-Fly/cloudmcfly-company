#!/bin/bash
# ============================================================
# CloudMcFly Company - Update Script
# Ausfuehren als User 'cloudmcfly' im App-Verzeichnis
# Usage: bash deploy/update.sh
# ============================================================

set -euo pipefail

APP_DIR="/home/cloudmcfly/app"
cd "$APP_DIR"

echo "=== CloudMcFly Company - Update ==="

# 1. Pull latest code
echo "[1/3] Git pull..."
git pull origin main

# 2. Rebuild & restart
echo "[2/3] Docker rebuild & restart..."
docker compose up -d --build

# 3. Health check
echo "[3/3] Warte auf Health-Check..."
sleep 5

if curl -sf http://localhost/health > /dev/null 2>&1; then
    echo ""
    echo "=== Update erfolgreich! ==="
    curl -s http://localhost/health | python3 -m json.tool
else
    echo ""
    echo "!!! WARNUNG: Health-Check fehlgeschlagen!"
    echo "Logs pruefen: docker compose logs -f app"
fi
