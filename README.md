# ERPNext demo (satcom-erp) - 2026-10-13

Vanilla ERPNext v16 (frappe/erpnext image, MariaDB 11.8, Redis) via the official frappe_docker
compose file. A demo: **no replica, no failover, no backup job.**

- VM `satcom-erp` on Server B (Hyper-V): 6 vCPU, 12 GB, 200 GB dynamic disk, 172.20.90.11 on VM-NAT.
  Built by `scripts/New-ErpVM.ps1` (autoinstall in `autoinstall/`), then `provision.sh`.
- Reach it: `http://192.168.1.86:8081` from the office LAN (netsh portproxy + firewall rule
  "ERPNext demo (LAN)" on B, LAN-only). Plain HTTP - demo credentials only.
- SSH: alias `satcom-erp-nat` (via B). Files in `/opt/erpnext`; passwords in `/opt/erpnext/.env`
  (root-only): `sudo grep ADMIN_PASSWORD /opt/erpnext/.env`. Login user `Administrator`.
- Factory setup: `satcom_factory_setup.py` (idempotent), run with
  `docker compose cp` into the backend container, then
  `bench --site frontend execute erpnext.satcom_factory_setup.run`.
- After restarting `backend`, restart `frontend` too (nginx caches the backend's IP -> 502).
- QR labels: custom `QR Label` field (stock Barcode field, options `qrcode`) on Item, Batch, Serial No, Warehouse, Work Order, Job Card, filled with the record name by Server Scripts. Print format "Satcom QR Label - <doctype>" (100x50 mm) from `satcom_qr_labels.py`; choose Letterhead "No Letterhead" when printing.
  Serial No, Warehouse, Work Order, Job Card, filled with the record name by Server Scripts.
- Roles are tied to B: if B is down the demo is down. Do not add it to Set-FilesReplica.
