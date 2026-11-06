#!/usr/bin/env bash
# Mounts Server A's ERP backup share at /mnt/erpbackup for the nightly Borg backup. Idempotent.
#   sudo bash mount-backup.sh
# Same pattern as nextcloud/mount-backup.sh. The credentials file /root/.smb-erpbackup (root, 0600)
# is piped in from Server A beforehand, so the password is never on a command line, in a log or in chat:
#   ssh satcom-a "type C:\ProgramData\satcom\erpbackup-cifs-cred" | ssh satcom-erp-nat "sudo sh -c 'umask 077; tr -d \"\r\" > /root/.smb-erpbackup'"
# SMB 3.1.1 with encryption (seal): the share requires it.
set -euo pipefail
CRED=/root/.smb-erpbackup
MNT=/mnt/erpbackup
SRC='//192.168.1.85/ErpBackup$'
OPTS="credentials=$CRED,vers=3.1.1,seal,uid=0,gid=0,file_mode=0600,dir_mode=0700,_netdev,nofail,x-systemd.mount-timeout=30"

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
[ -s "$CRED" ] || { echo "$CRED missing - pipe it in from Server A first"; exit 1; }
chmod 600 "$CRED"; chown root:root "$CRED"
command -v mount.cifs >/dev/null || { apt-get update -q; DEBIAN_FRONTEND=noninteractive apt-get install -y -q cifs-utils; }
mkdir -p "$MNT"
# If Server A is down at boot the share is not mounted: the bare mount point is immutable, so the
# backup then FAILS instead of quietly writing into the VM's own disk. Mounting over it works.
if ! findmnt -n "$MNT" >/dev/null; then chattr +i "$MNT"; fi
sed -i "\| $MNT cifs |d" /etc/fstab
echo "$SRC $MNT cifs $OPTS 0 0" >> /etc/fstab
systemctl daemon-reload
findmnt -n "$MNT" >/dev/null || mount "$MNT"
findmnt -n -o SOURCE,FSTYPE,OPTIONS "$MNT" | sed -E 's/(credentials|password)=[^,]*/\1=***/g'
t="$MNT/.write-test-$$"; echo ok > "$t" && rm -f "$t" && echo "write test: ok"
df -h --output=size,avail "$MNT" | tail -1
