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
- [x] §1 demo cleanup (2026-10-28): `satcom_demo_cleanup.py`, 41 changes, rerun 0. Backups `D:\ERPNext-Backups\20261028_134403-pre-cleanup\` and `…135119-post-cleanup\`. Afterwards 0 GL / 0 stock ledger rows, Stock Balance empty.
- [x] §2.1 settings (2026-10-28): `satcom_p1_foundation.py` switched perpetual inventory off and maintain-same-rate off (rerun 0 changes); valuation stays FIFO; `satcom_p1_check.verify` 11/11 PASS. Backup `…135203-pre-2.1\`.
- [x] §2.2 roles (2026-10-30): roles `Satcom Approver`, `Satcom Indenter`; one Role Profile per Satcom role; 5 demo users; installer 12 changes, rerun 0; `verify` 24/24 PASS. Backup `…20261030_132537-pre-2.2\`.
- [x] §2.3 warehouses (2026-10-30): added `Rejected - STPL` and `Repair RMA - STPL`; `Raw Material - STPL` disabled after checking it had no stock, ledger rows, item defaults or child warehouses; installer 3 changes, rerun 0; `verify` 35/35 PASS. Backup `…20261030_132933-pre-2.3\`.
- [x] §2.4 item code scheme (2026-10-30 to 11-05): 11 new item groups and prefixes on 16; Item part fields; attributes and RES/CAP/IND/HWR templates; scripts `Satcom Item - number` (Before Insert), `Satcom Item - rules` (Before Save), client script `Satcom Item`. Rerun 0 changes; 19 server-side trials as demo.stores; form walkthrough as demo.stores (numbered item, RES variant, duplicate MPN); `verify` 72/72 PASS. Backups `…20261030_162536-pre-2.4\`, `…20261105_135644-pre-2.4-finish\`.
- [ ] §2.5 job codes onward.
- [ ] Built section by section; acceptance check (spec §10) passes.

Technical decisions (made within the spec, demo data only; Rahul delegated these 2026-10-28):
- 2026-10-28, cleanup: cancelling `MAT-STE-2026-00001` also queued 6 Repost Item Valuation entries (one per item and warehouse, because `item_based_reposting` is on). They have no voucher fields, so they were matched as "created by this cancel, for the demo items" and deleted with the voucher's 12 SLE, 4 GL, 1 bundle and 1 bundle row.
- 2026-10-28, cleanup: `frappe.delete_doc` steps a naming series back when it deletes the last-numbered record, which reset 5 counters (MAT-STE, MFG-WO, PROJ, PUR-ORD, TASK) to 0. Put back by hand to the phase 0 values, and the module now keeps every counter itself.
- 2026-10-30, §2.2: each Satcom role in the spec table is a **Role Profile** of the same name (v16 lets a user hold several profiles), so giving someone a Satcom role is one pick and profile edits flow to every holder. Users with profiles get their roles only from the profiles. Accounts profile waits for phase 3.
- 2026-10-30, §2.2: demo users are `demo.approver1/2`, `demo.indenter` (Indenter + Purchase), `demo.stores` (Stores + QC), `demo.allroles` (all five, for self-approval tests), all `@example.com`, no password and no welcome email. The check uses them server-side; to try them in the UI, set a password on the User.
- 2026-10-30, §2.3: `Rejected - STPL` has v16's "Is Rejected Warehouse" flag on. It only keeps Pick Lists (and sales-order / subcontracting warehouse defaults) from using it, and blocks no stock entry, so QC Release (§5.2) can still move stock in and out.
- 2026-10-30, §2.4 sandbox: Server Scripts get read-only `frappe.db.sql` (SELECT only), `get_all` without permission checks, no `re` module, no `str.format` (an "unsafe attribute"), and comprehensions / generator expressions can't see the script's top-level names. So numbering is one SELECT using MariaDB `REGEXP '^PREFIX-[0-9]{4}$'` over items **and deleted items** (codes never reused), and the code check is a plain loop.
- 2026-10-30, §2.4: all four specs templates are batch-tracked (bought in lots; the spec states it only for RES); stores can change a template on its Inventory tab. Variants copy the template description (ERPNext adds the attribute values) but not its serial / batch series; the rules script gives each variant its own (`RES-10K-0603-B.####`). Templates carry no series.
- 2026-10-30, §2.4: a specs group may hold only its template (code = prefix) and that template's variants; a plain item there is blocked with "use Create > Single Variant". Picking Cables and Wire defaults the unit to Meter on the form (not enforced).
- 2026-10-30, §2.4: Item's quick-entry dialog is off, so "+ Add Item" opens the full form with the part fields and the client script. Item Code stays mandatory on the form; picking a number group puts the prefix there and the Before Insert script replaces it with the next number. If the item name is still the bare prefix it becomes the code.
- 2026-11-05, §2.4 (from the form walkthrough): the Part Identification section sits after Item Attributes on the Details tab (inserted after Description it landed on the Accounting tab). The Description and Serial Nos / Batches sections are no longer collapsible, because both hold required inputs.
- 2026-11-05, §2.4: `satcom_p1_check.cleanup` deletes DEMO items (name or MPN starting DEMO) **and their Deleted Document rows**, so test runs don't burn real numbers (the walkthrough's RFC-0001 is free again).
- 2026-11-05: `http://192.168.1.86:8081` doesn't answer from the office LAN (B's port proxy; not touched). The walkthrough used a dev-only SSH tunnel to `127.0.0.1:18081`. The VM has rebooted without a clean shutdown 6 times since 10-29 (latest 11-05 13:35); containers came back each time. The site's `host_name` is `https://erp.satcomindia.in`, which doesn't resolve yet.
- 2026-10-28: `satcom_factory_setup.py` now sets maintain-same-rate **off**, so rerunning it can't undo §2.1. `satcom_sample_data.py` is marked retired. `satcom_qr_labels.render_check` still names demo records; it will be updated in §6.
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
