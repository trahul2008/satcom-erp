# ERPNext (satcom-erp)

Vanilla ERPNext v16 (frappe/erpnext image, MariaDB 11.8, Redis) via the official frappe_docker
compose file. Built 2026-10-13 as a demo; becoming the real factory system (phase 1 in progress,
`SPEC_PHASE1.md`, status in `docs/plan-erpnext.md`, rules in `CLAUDE.md`).
**No replica, no failover, no backup job yet.**

- VM `satcom-erp` on Server B (Hyper-V): 6 vCPU, 12 GB, 200 GB dynamic disk, 172.20.90.11 on VM-NAT.
  Built by `scripts/New-ErpVM.ps1` (autoinstall in `autoinstall/`), then `provision.sh`.
- Reach it: `http://192.168.1.86:8081` from the office LAN (netsh portproxy + firewall rule
  "ERPNext demo (LAN)" on B, LAN-only). Plain HTTP.
- SSH: alias `satcom-erp-nat` (via B). Files in `/opt/erpnext`; passwords in `/opt/erpnext/.env`
  (root-only): `sudo grep ADMIN_PASSWORD /opt/erpnext/.env`. Login user `Administrator`.
- After restarting `backend`, restart `frontend` too (nginx caches the backend's IP -> 502).
- Roles are tied to B: if B is down ERPNext is down. Do not add it to Set-FilesReplica.

## Nightly backup
`satcom-erp-backup.timer` in the VM, 00:30 IST: bench backup, 14 days in `/var/backups/erpnext`, Borg to Server A `D:\ErpBackup` (30 days). Log `/var/log/satcom-erp-backup.log`; run now with `sudo systemctl start satcom-erp-backup.service`. Setup, rollback and restore: `docs/plan-erpnext.md` (Go-live, Backups); files in `backup/`, `scripts/Set-ErpBackupShare.ps1`.

## Backup before every change run
`bench --site frontend backup --with-files` in the backend container; the four files land in
`sites/frontend/private/backups/<ts>-frontend-*`. Copy them off the VM (`docker compose cp` to a
temp dir, then `tar` over ssh) to `D:\ERPNext-Backups\<ts>-<label>\` on Rahul's PC with a
`SHA256SUMS`. The site-config file holds the DB password: never into the repo.

## Running an installer module
```
scp <module>.py satcom-erp-nat:/tmp/
ssh satcom-erp-nat "cd /opt/erpnext && sudo docker compose cp /tmp/<module>.py backend:/home/frappe/frappe-bench/apps/erpnext/erpnext/ && sudo docker compose exec -T backend bench --site frontend execute erpnext.<module>.run"
```
Every module is idempotent: a second run reports `0 changes`.

From §2.4 on, `satcom_p1_foundation.py` reads Server/Client Script sources from `/tmp/satcom_scripts` in the backend container: copy `server_scripts` and `client_scripts` there first (`docker compose cp`). Edit scripts only in those files, then rerun the installer. `satcom_p1_purchase_orders.py` (§4) also reads `print_formats` (the PO print format) and `assets` (the letterhead logo) from the same place: copy those two folders there as well.

| Module | What | Status |
|---|---|---|
| `satcom_factory_setup.py` | Company, warehouses, item groups, settings, `satcom_qr` fields + scripts | applied 10-13 |
| `satcom_qr_labels.py` | "Satcom QR Label - <doctype>" 100x50 mm print formats (print with "No Letterhead") | applied 10-13 |
| `satcom_sample_data.py` | Demo sample data | **retired**, removed 10-28 |
| `satcom_demo_cleanup.py` | Removes the sample data; `run` with `--kwargs "{'dry_run': 1}"` first (rolls back), `report` is read-only | applied 10-28 |
| `satcom_p1_foundation.py` | Spec §2: 2.1 settings, 2.2 roles, 2.3 warehouses (Rejected, Repair RMA; Raw Material disabled), 2.4 item codes (groups with prefixes, RES/CAP/IND/HWR templates, numbering + rules scripts). 2.5 job codes (Project fields, J-/S-/extension naming scripts). 2.2 roles (Role Profiles "Satcom Approver/Indenter/Purchase/Stores/QC") and `demo.*@example.com` users (no password: set one in User to sign in as them) | in progress |
| `satcom_p1_purchase.py` | Spec §3: indent Job field, "Satcom Indent Approval" workflow, approval and approver-only cancel guards, reject/cancel reason dialogs, notifications; run after `satcom_p1_foundation.py` | applied 11-06 |
| `satcom_p1_purchase_orders.py` | Spec §4: single DocType "Satcom Settings" (quotation threshold Rs 3,00,000, minimum 3 quotations, basis net total before tax, concession needs approver off; set once, never overwritten); PO table "Supplier Quotations Compared" (supplier filled in), "Quotation Rule Waived" + reason (approvers only); "Satcom PO Approval" workflow with approval guard and reject-reason dialog; quotation rule checked on approval; job on every PO row except tools; letterhead "Satcom Technologies" (default), the two company Addresses, Company GSTIN (Tax ID) and CIN; print format "Satcom PO" (PO default); **last step sets Buying Settings "Purchase Order Required" = Yes**, so a GRN then needs a PO. Run after the three modules above (copy `server_scripts/`, `client_scripts/`, `print_formats/` and `assets/` to `/tmp/satcom_scripts` first) | **built 11-18, not run on the site yet** (backup first; see `docs/plan-erpnext.md` §4) |
| `satcom_p1_receipt_qc.py` | Spec §5: GRN vendor documents, job per row and on each serial/batch, Quality Hold only, submit guard; "Standard checks" QI template on Satcom items; QI job and inspection level; "QC Release" stock entry type and rejected-material dispositions; report "Satcom Pending QC". Run after `satcom_p1_foundation.py` (copy `server_scripts/` and `client_scripts/` to `/tmp/satcom_scripts` in the container first) | built 11-09 |
| `satcom_p1_check.py` | `verify` prints PASS/FAIL for what's built so far (read-only; needs `satcom_p1_foundation.py` copied into the container too); `create_demo` writes the DEMO scenario so far (customer, suppliers, jobs, items, indents through the workflow, supplier quotations and POs through the quotation rule and the PO workflow, GRN from a PO, QC release, inspections, dispositions) and prints PASS/FAIL for each block it tries; `cleanup` cancels and removes all of it (ledger rows of the DEMO vouchers too) and puts back the counters those records used | in progress |
