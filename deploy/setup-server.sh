#!/bin/bash
# ============================================================
# CloudMcFly Company - Hetzner Server Setup Script
# Ausfuehren als root auf einem frischen Ubuntu 24.04 Server
# Usage: bash setup-server.sh
# ============================================================

set -euo pipefail

echo "=== CloudMcFly Company - Server Setup ==="
echo ""

# 1. System Update
echo "[1/6] System aktualisieren..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. Docker installieren (falls nicht vorhanden)
if ! command -v docker &> /dev/null; then
    echo "[2/6] Docker installieren..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "[2/6] Docker bereits installiert."
fi

# 3. Docker Compose Plugin pruefen
if ! docker compose version &> /dev/null; then
    echo "[2b/6] Docker Compose Plugin installieren..."
    apt-get install -y -qq docker-compose-plugin
else
    echo "[2b/6] Docker Compose bereits installiert."
fi

# 4. App-User anlegen
if ! id -u cloudmcfly &> /dev/null; then
    echo "[3/6] App-User 'cloudmcfly' anlegen..."
    useradd -m -s /bin/bash cloudmcfly
    usermod -aG docker cloudmcfly
else
    echo "[3/6] User 'cloudmcfly' existiert bereits."
fi

# 5. Projekt-Verzeichnis
APP_DIR="/home/cloudmcfly/app"
echo "[4/6] Projekt-Verzeichnis: $APP_DIR"
mkdir -p "$APP_DIR"
chown cloudmcfly:cloudmcfly "$APP_DIR"

# 6. Firewall (ufw)
echo "[5/6] Firewall konfigurieren..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw --force enable
    echo "   Firewall: SSH(22), HTTP(80), HTTPS(443) offen."
else
    echo "   ufw nicht installiert - uebersprungen."
fi

# 7. Swap (fuer kleine Server)
if [ ! -f /swapfile ]; then
    echo "[6/6] 2GB Swap anlegen (fuer kleine Server)..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
    echo "[6/6] Swap existiert bereits."
fi

echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "Naechste Schritte:"
echo "  1. Wechsle zum App-User:  su - cloudmcfly"
echo "  2. Clone das Repo:        cd ~/app && git clone <REPO_URL> ."
echo "  3. Erstelle .env:         cp .env.production .env && nano .env"
echo "  4. Starte die App:        docker compose up -d --build"
echo "  5. Pruefe Status:         docker compose ps"
echo "  6. Pruefe Logs:           docker compose logs -f app"
echo "  7. Teste Health:          curl http://localhost/health"
echo ""
