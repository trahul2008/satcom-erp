#!/usr/bin/env bash
# Nightly ERPNext backup (systemd: satcom-erp-backup.timer, 00:30 IST). Installed as
# /usr/local/sbin/satcom-erp-backup by install-backup.sh; source of truth is this file.
#  1. bench --site frontend backup --with-files (database, public + private files, site config)
#  2. copies the set out of the container to /var/backups/erpnext/<timestamp>/ with SHA256SUMS;
#     sets older than 14 days are removed here and inside the container
#  3. Borg archive of that folder into /mnt/erpbackup/borg on Server A (share ErpBackup$),
#     repository pruned to 30 days
# Every run logs one result line to /var/log/satcom-erp-backup.log (and the journal); the last
# success is in /var/backups/erpnext/LAST_SUCCESS. Exits non-zero on any failure.
set -euo pipefail
COMPOSE_DIR=/opt/erpnext
LOCAL=/var/backups/erpnext
MNT=/mnt/erpbackup
export BORG_REPO=$MNT/borg
export BORG_PASSCOMMAND="cat /root/.borg-erp-pass"
export BORG_RELOCATED_REPO_ACCESS_IS_OK=no BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=no
LOG=/var/log/satcom-erp-backup.log
KEEP_LOCAL_DAYS=14
KEEP_REMOTE=30d
BENCH_BACKUPS=/home/frappe/frappe-bench/sites/frontend/private/backups

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; logger -t satcom-erp-backup -- "$*"; }
fail() { log "FAIL: $*"; exit 1; }
trap 'fail "line $LINENO: $BASH_COMMAND"' ERR

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
start=$(date +%s)
cd "$COMPOSE_DIR"

# 1. bench backup
out=$(docker compose exec -T backend bench --site frontend backup --with-files 2>&1) || fail "bench backup: $(echo "$out" | tail -3)"
ts=$(echo "$out" | grep -oE '[0-9]{8}_[0-9]{6}-frontend-database' | head -1 | cut -d- -f1)
[ -n "$ts" ] || fail "no backup timestamp in bench output"

# 2. copy out, checksum, verify the gzip
dest="$LOCAL/$ts"; mkdir -p "$dest"; chmod 700 "$LOCAL"
for f in site_config_backup.json database.sql.gz files.tar private-files.tar; do
    docker compose cp "backend:$BENCH_BACKUPS/$ts-frontend-$f" "$dest/" >/dev/null
done
(cd "$dest" && sha256sum ./* > SHA256SUMS && gzip -t ./*database.sql.gz)
chmod -R go-rwx "$dest"
size_local=$(du -sb "$dest" | cut -f1)

# 3. Borg to Server A (only onto the real share: the bare mount point is immutable)
findmnt -n -t cifs "$MNT" >/dev/null || mount "$MNT" || true
findmnt -n -t cifs "$MNT" >/dev/null || fail "$MNT is not mounted (Server A share ErpBackup\$)"
borg create --compression zstd,6 "::erp-$ts" "$dest" 2>>"$LOG"
borg prune --keep-within "$KEEP_REMOTE" --glob-archives 'erp-*' 2>>"$LOG"
borg compact 2>>"$LOG"
archives=$(borg list --short | wc -l)
repo_size=$(du -sb "$BORG_REPO" | cut -f1)

# local retention: copied sets here, bench's own files in the container
find "$LOCAL" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_LOCAL_DAYS" -exec rm -rf {} +
docker compose exec -T backend find "$BENCH_BACKUPS" -type f -mtime +"$KEEP_LOCAL_DAYS" -delete

echo "$ts $(date '+%F %T')" > "$LOCAL/LAST_SUCCESS"
log "OK $ts set=$((size_local / 1024)) KiB repo=$((repo_size / 1024)) KiB archives=$archives took=$(( $(date +%s) - start ))s"
