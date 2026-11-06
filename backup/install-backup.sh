#!/usr/bin/env bash
# Installs the nightly ERPNext backup in the satcom-erp VM. Idempotent; no compose.yml change.
#   sudo bash install-backup.sh        (from a folder holding this file, satcom-erp-backup.sh, mount-backup.sh)
# Needs, piped in from Server A first (see scripts/Set-ErpBackupShare.ps1):
#   /root/.smb-erpbackup  (SMB credentials)      /root/.borg-erp-pass  (Borg passphrase)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
[ -s /root/.borg-erp-pass ] || { echo "/root/.borg-erp-pass missing - pipe it in from Server A first"; exit 1; }
chmod 600 /root/.borg-erp-pass; chown root:root /root/.borg-erp-pass

command -v borg >/dev/null || { apt-get update -q; DEBIAN_FRONTEND=noninteractive apt-get install -y -q borgbackup; }
bash "$here/mount-backup.sh"

install -m 0750 "$here/satcom-erp-backup.sh" /usr/local/sbin/satcom-erp-backup
cat > /etc/systemd/system/satcom-erp-backup.service <<'EOF'
[Unit]
Description=Satcom ERPNext nightly backup (bench backup + Borg to Server A)
After=docker.service network-online.target mnt-erpbackup.mount
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/satcom-erp-backup
Nice=10
IOSchedulingClass=idle
EOF
cat > /etc/systemd/system/satcom-erp-backup.timer <<'EOF'
[Unit]
Description=Satcom ERPNext nightly backup at 00:30 IST (outside 09:00-18:00, before Nextcloud's 02:00)

[Timer]
OnCalendar=*-*-* 00:30:00 Asia/Kolkata
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now satcom-erp-backup.timer

export BORG_REPO=/mnt/erpbackup/borg BORG_PASSCOMMAND="cat /root/.borg-erp-pass"
if ! borg info >/dev/null 2>&1; then
    borg init --encryption=repokey-blake2
    echo "borg repository created at $BORG_REPO (repokey: the key is in the repo, the passphrase on Server A)"
else
    echo "borg repository at $BORG_REPO exists"
fi
systemctl list-timers satcom-erp-backup.timer --no-pager | head -3
