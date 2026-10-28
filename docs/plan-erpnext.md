# ERPNext plan

PLANNING.md item 9 points here (same pattern as `docs/plan-nextcloud.md`). Keep it up to date: tick items with a date when done.

**Goal:** ERPNext v16 runs the factory's purchase, stores, production tracking with QR codes, QC, dispatch paperwork, warranty and asset register. Accounts and GST invoicing stay in Tally. Decisions come from management and are recorded in the "ERPNext Process Decisions" doc; each phase gets a spec (`erpnext/SPEC_PHASE<n>.md`) built only from recorded decisions.

**Where:** the 2026-10-13 demo VM `satcom-erp` on Server B (Docker, site `frontend`) becomes the real system. Build method: configuration as code (installer modules + Server/Client Scripts in `erpnext/`), no custom app. Rules: `erpnext/CLAUDE.md`.

## Phase 0 — groundwork (before phase 1)
- [x] Access check from the dev PC (2026-10-28): 9 containers up, ERPNext 16.50.0 / Frappe 16.51.0, site `frontend`, `server_script_enabled` = 1.
- [x] Pre-change backup routine works (2026-10-28): `D:\ERPNext-Backups\20261028_130708-phase0\` with SHA256SUMS (holds the site config with the DB password: keep private).
- [x] Inventory of what's on the site (2026-10-28); Rahul approved removing the 2026-10-13 sample data. Findings folded into the spec: perpetual inventory was on, valuation is FIFO, Projects can only be named by series, "Size" attribute already exists, QI-rejected action was Stop, no company address/GSTIN/CIN or letterhead.
- [x] `PLANNING.md` item 9 → this file (2026-10-28).

## Phase 1 — purchase, stores, QR labels, incoming QC
Spec: `erpnext/SPEC_PHASE1.md`. Roles, warehouses, item code scheme, job codes (`J-26-0042`, `-01` extensions, `S-26-0007` stock builds), indents and POs with Vijay/Dileep approval, the Rs. 3 lakh quotation rule, GRN into Quality Hold, QR labels per piece / per lot, QC release, failed-material disposition, issues only against job codes, four reports.
- [ ] Built section by section; acceptance check (spec §10) passes.
- [ ] Open items still to be decided are listed in spec §11.

## Phase 2 — production, testing and FAT
- Standard BOM per product, maintained by the project in-charge; a job that needs changes gets its own copy.
- Work orders for fabrication, sub-assemblies and final assembly; material issued against the work order.
- Job work: some fabrication sent out per job, with the vendor's test results attached on return.
- In-process QC after fabrication: tests vary by customer, added per job and recorded.
- Assembly records the serial of every serialised component in each finished unit (traceability both ways).
- Internal testing by the in-house QC engineer: test reports uploaded with comments against the unit's serial; a failed unit is reworked and gets a rework code; the QC engineer approves retest and final release.
- FAT only when the customer requires it: the project/product in-charge uploads the FAT document; on failure, rework or replace with a new serial linked to the old one.
- **Needed before the spec:** fabrication stages, one real product's BOM, the QC engineer's test lists and pass limits.

## Phase 3 — dispatch, warranty, sales quotations, service
- Delivery Note with DC and packing list prints; ERPNext alerts accounts when a unit is ready; the accountant enters the Tally invoice and e-way bill numbers (and scans) in ERPNext; accounts authorise release.
- Warranty: 12 months from acceptance or 13 months from delivery, whichever ends first; extended 2–3 years when the PO requires it. Delivery and acceptance dates per serial; end date calculated; warranty certificate printed from the delivery with the four wording fixes.
- Sales quotations: Aditya prepares, Vijay or Dileep approves before sending; standard T&C templates.
- Service and repairs (RMA): returned units into `Repair RMA - STPL`, claim looked up by serial, repair/replace decision.
- **Needed before the spec:** the delivery-based limit for extended warranties (e.g. 24 months from acceptance or 25 from delivery?); who handles RMA; whether to add the optional certificate clauses (return shipping, warranty on repaired items, how to claim).

## Phase 4 — asset register
- ERPNext Assets replace the tag spreadsheet; keep the existing `SAT-00001` tag IDs, sites (HQ, Factory) and rooms; custodian, movements, status, last verified.
- Threshold: ERP decision (27 Oct) is Rs. 10,000 and above plus all IT and test equipment, smaller items allowed. **Conflict to resolve:** the asset tagging standard (v2.1) tags at Rs. 5,000. Pick one before migrating.
- Calibration and maintenance schedules for test instruments (D20); reminders to custodians (D31).

## Go-live readiness — before real data goes in (can run alongside phase 2)
Server work under the root `CLAUDE.md`; reuse the Nextcloud patterns (`docs/plan-nextcloud.md`).
- [ ] **Backups:** nightly `bench backup --with-files` copied off the VM to Server A (`D:`), retention, a tested restore, an alert when the backup is older than 26 h.
- [ ] **Redundancy:** decide Hyper-V Replica B → A with a failover script (same as `satcom-files`), or backups only.
- [ ] **Network:** move to `VM-LAN` at 192.168.1.91 (MAC reserved) when Ethernet 4 is cabled, or keep VM-NAT + port proxy.
- [ ] **Publishing:** HTTPS name (e.g. `erp.satcomindia.in`, to be decided) through nginx on both servers, office DNS zone, Let's Encrypt via `Update-SatcomCertificate.ps1`; retire plain HTTP on 8081.
- [ ] **Sign-in:** Google Workspace (Frappe social login) for office staff, local accounts with 2FA for the rest; real users and roles.
- [ ] **Email:** Workspace SMTP relay, as for the workforce app and Nextcloud. Before turning it on, review the standard Notifications that are enabled (e.g. "Material Request Receipt Notification") so nothing unexpected starts mailing people.
- [ ] **Data:** item master built with the code scheme, suppliers, customers, opening stock from a physical count (D4).
- [ ] **UPS with clean shutdown** (already open for Nextcloud) protects the ERP database too.

## Later
Customer download of test reports (needs public exposure); Tally integration (invoices, PBG and other bank guarantees); employee data shared with the workforce app; SMS alerts.
