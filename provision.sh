#!/usr/bin/env bash
# Provisions the ERPNext demo VM (satcom-erp) after the Ubuntu autoinstall. Idempotent.
#   sudo bash provision.sh            (compose.yml must sit next to this file)
# 1. Docker from Docker's apt repo, address pools clear of the office LAN and VM-NAT.
# 2. Firewall: SSH from the host side only; ERPNext's port 8080 only from the VM-NAT host (B),
#    which is where the LAN-facing port proxy lives. Docker-published ports bypass ufw's INPUT
#    rules, so 8080 is filtered in the DOCKER-USER chain (same pattern as satcom-files).
# 3. /opt/erpnext: compose.yml + .env (random passwords, root-only, kept on rerun), then
#    `docker compose up -d`. The create-site job builds the site "frontend" with the ERPNext app.
set -euo pipefail

SSH_SOURCES=("192.168.1.0/24" "172.20.90.1/32")
WEB_SOURCES=("172.20.90.1/32")
APP_DIR=/opt/erpnext
ERPNEXT_VERSION_DEFAULT=v16.50.0

log() { echo "[$(date '+%H:%M:%S')] $*"; }
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
here=$(cd "$(dirname "$0")" && pwd)

grep -q '^precedence ::ffff:0:0/96  100' /etc/gai.conf 2>/dev/null || echo 'precedence ::ffff:0:0/96  100' >> /etc/gai.conf
echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

# ---------------------------------------------------------------- 1. Docker
if ! command -v docker >/dev/null; then
  log "installing Docker"
  apt-get update -q
  apt-get install -y -q ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
fi
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "bip": "10.249.0.1/24",
  "default-address-pools": [{ "base": "10.250.0.0/16", "size": 24 }],
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" }
}
EOF
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
systemctl restart docker
log "docker $(docker --version | awk '{print $3}' | tr -d ,)"

# ---------------------------------------------------------------- 2. firewall
apt-get install -y -q ufw
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
for s in "${SSH_SOURCES[@]}"; do ufw allow from "$s" to any port 22 proto tcp comment 'ssh' >/dev/null; done
rules=""
for s in "${WEB_SOURCES[@]}"; do
  rules+="-A DOCKER-USER -i eth0 -p tcp -s $s -m conntrack --ctorigdstport 8080 --ctdir ORIGINAL -j RETURN"$'\n'
done
python3 - "$rules" <<'PY'
import re, sys
p = '/etc/ufw/after.rules'
s = open(p).read()
s = re.sub(r'\n# BEGIN SATCOM DOCKER-USER.*?# END SATCOM DOCKER-USER\n', '\n', s, flags=re.S)
block = ("\n# BEGIN SATCOM DOCKER-USER\n*filter\n:DOCKER-USER - [0:0]\n"
         "-A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN\n"
         + sys.argv[1] +
         "-A DOCKER-USER -i eth0 -m conntrack --ctstate NEW -j DROP\n"
         "-A DOCKER-USER -j RETURN\nCOMMIT\n# END SATCOM DOCKER-USER\n")
open(p, 'w').write(s.rstrip('\n') + '\n' + block)
PY
ufw --force enable >/dev/null
systemctl restart docker
log "ufw: $(ufw status | head -1)"

# ---------------------------------------------------------------- 3. ERPNext
mkdir -p "$APP_DIR"
install -m 0644 "$here/compose.yml" "$APP_DIR/compose.yml"
if [ ! -f "$APP_DIR/.env" ]; then
  umask 077
  {
    echo "ERPNEXT_VERSION=$ERPNEXT_VERSION_DEFAULT"
    echo "DB_ROOT_PASSWORD=$(openssl rand -hex 16)"
    echo "ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)"
  } > "$APP_DIR/.env"
  log "wrote $APP_DIR/.env (root-only)"
fi
chmod 600 "$APP_DIR/.env"
cd "$APP_DIR"
docker compose pull -q
docker compose up -d
log "containers started; the site is built by create-site (several minutes) - follow: docker compose logs -f create-site"
