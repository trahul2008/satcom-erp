# ERPNext phase 1 build spec — purchase, stores, QR labels, incoming QC

Rules for working on ERPNext: `erpnext/CLAUDE.md`. Roadmap and status: `docs/plan-erpnext.md`.

**Where it runs:** the existing ERPNext v16.50.0 demo (stock `frappe/erpnext` image, frappe_docker compose) in VM `satcom-erp` on Server B, site `frontend`. This instance becomes the real system; there is no separate test site.
**How it's built:** configuration as code. Idempotent installer modules in `erpnext/` (same pattern as `satcom_factory_setup.py`), run with `bench --site frontend execute …`. Runtime logic lives in Server Scripts and Client Scripts whose source is kept as files in the repo and loaded by the installer. **No custom app, no custom image.**
**Source of decisions:** "ERPNext Process Decisions" doc, decision log up to 27 Oct 2026. Every rule here comes from a recorded decision. Anything marked **OPEN** is undecided: build it as a setting with the stated default, and don't pick a different rule.

---

## 0. Context

- Satcom Technologies Pvt Ltd (`STPL`) builds satellite-communication equipment (RF assemblies, antennas, fabricated parts) at one factory in Hyderabad. Work is **job-code driven**: every purchase, issue and production step belongs to a job code. Some products are also built for stock.
- **Accounts stay in Tally.** ERPNext must never become the books. Keep perpetual inventory off (so stock posts no GL entries); no Purchase Invoices or payments.
- **Only the factory holds stock.** HQ is only an asset location (later phase).
- **No dedicated staff yet.** One person may hold several roles. Design by role, never by person.
- **Approvers:** Vijay (primary) and Dileep (when Vijay is away). Both get the same approver role.

## 1. Before building: what's already on the site

The 2026-10-13 demo setup is already applied (`satcom_factory_setup.py`, `satcom_qr_labels.py`, `satcom_sample_data.py`). Phase 1 **builds on it**; don't redo or rename what exists.

| Already there | Phase 1 use |
|---|---|
| Setup wizard done; company Satcom Technologies Pvt Ltd (`STPL`), INR, FY Apr–Mar | Keep |
| Warehouses: Stores, Work In Progress, Finished Goods, Goods In Transit, Raw Material, Subcontractor (Job Work), Quality Hold, Scrap (all `- STPL`) | See §2.3 |
| Item groups: Finished Goods, Sub Assemblies, Packaging, Tools & Spares, Consumable (+ ERPNext defaults) | Reused in §2.4 |
| `satcom_qr` Barcode field (qrcode) + Server Scripts "Satcom QR label - <doctype>" on Item, Batch, Serial No, Warehouse, Work Order, Job Card | Reused for labels (§6) |
| Print formats "Satcom QR Label - <doctype>" (100 × 50 mm) | Reused; GRN batch print added (§6) |
| Stock Settings: negative stock off, serial/batch fields on rows | Keep |
| **Demo sample data** (control-panel story): suppliers Precision Metals / Bharat Electricals / Sunrise Powder Coaters, customer Demo Industries Ltd, items `RM-*`, `SA-ENCLOSURE-PAINTED`, `SRV-POWDER-COATING`, `FG-MCP-001`, workstations, operations, BOMs, a submitted opening-stock entry, draft POs, a draft work order, project "Panel Line Commissioning" with its 4 tasks, subcontracting BOM `SB-0001`, batch `WIRE-DEMO-0001` and its serial-and-batch bundle, the 3 auto-created item prices | **Remove before §2.1** (it breaks the item code rules and blocks switching perpetual inventory off). Approved by Rahul 2026-10-28. Back up; cancel submitted entries, then delete in dependency order; keep the delete as a module (`satcom_demo_cleanup.py`). For the demo opening-stock entry `MAT-STE-2026-00001` only, also delete its cancelled ledger rows (stock ledger, GL entries, serial-and-batch bundle, any repost entries), because v16 keeps them as live links that block deleting the batch and items (decided 2026-10-28, option C). **Don't reset document counters**, so old numbers are never reused. Keep the supplier groups, item groups and the "Assembly" operation, which ERPNext created at setup. |

## 2. Foundation

### 2.1 Settings
- Company: **switch Enable Perpetual Inventory off** (it is on; ERPNext allows the switch once the demo's opening stock entry is cancelled by the cleanup). Confirm no GL entries remain active afterwards.
- Stock Settings: keep the valuation method as it is, **FIFO** (**OPEN**; management and accounts confirm before go-live, painful to change later). Inward serials and batches come from each item's series (§2.4); v16 has no separate "auto-create on inward" setting.
- Buying Settings: supplier naming by supplier name; "PO required" / "Purchase Receipt required" off; **maintain same rate off** (demo set it on; POs must allow the approved quotation's rate).

### 2.2 Roles
Two custom roles (`Satcom Approver`, `Satcom Indenter`); everything else standard.

| Satcom role | ERPNext roles | Who today |
|---|---|---|
| Approver | Satcom Approver + Purchase Manager + Stock User | Vijay, Dileep |
| Indenter / project in-charge | Satcom Indenter + Projects User + Purchase User | production / project in-charges (also create job codes; maintain BOMs from phase 2) |
| Purchase | Purchase User | whoever handles purchase |
| Stores | Stock User + Item Manager | stores in-charge (also creates item codes) |
| QC | Quality Manager + Stock User | QC engineer |
| Accounts | (phase 3) | accountant |

- A user can hold several roles. Every workflow transition into an approved state has **Allow Self Approval = 0**, so nobody approves their own document.
- Create test users that each hold several roles, plus two approver users, to exercise the workflows. Name them `demo.*` so they're easy to remove.

### 2.3 Warehouses (factory only)
Map the decided list onto what exists; add only what's missing. Don't rename existing warehouses.

| Decided role | Warehouse |
|---|---|
| Main store | `Stores - STPL` (existing) |
| QC hold (received, not yet released) | `Quality Hold - STPL` (existing) |
| Rejected (failed QC, awaiting disposition) | **new** `Rejected - STPL` |
| Production WIP | `Work In Progress - STPL` (existing) |
| Finished goods | `Finished Goods - STPL` (existing) |
| Repair / RMA | **new** `Repair RMA - STPL` (used from phase 3) |
| Job-work vendors | `Subcontractor (Job Work) - STPL` (existing; one per vendor later if needed) |
| Scrapped material | `Scrap - STPL` (existing) |
| `Raw Material - STPL`, `Goods In Transit - STPL` | Not used by the Satcom flow. After the demo cleanup, disable `Raw Material` (it will be empty). Leave Goods In Transit (ERPNext uses it for transfers). |

Rack/bin locations: **OPEN** (D10); don't build.

### 2.4 Item code scheme
Every item code = 3-letter category prefix + specs or a running number. Codes never change and are never reused. Uppercase letters, digits and hyphens only; max 20 characters.

| Prefix | Item Group | Code type | Example |
|---|---|---|---|
| RES | Resistors | Specs | RES-10K-0603 |
| CAP | Capacitors | Specs | CAP-100N-0603 |
| IND | Inductors | Specs | IND-10U-0805 |
| HWR | Fasteners and Hardware | Specs | HWR-M3X10-SS |
| ICS | ICs and Semiconductors | Number | ICS-0045 |
| RFC | RF Components | Number | RFC-0102 |
| CON | Connectors | Number | CON-0031 |
| CBL | Cables and Wire (UOM Meter) | Number | CBL-0007 |
| PCB | Bare PCBs | Number | PCB-0008 |
| MEC | Fabricated and Machined Parts | Number | MEC-0012 |
| ENC | Enclosures and Racks | Number | ENC-0004 |
| CNS | Consumable (existing group) | Number | CNS-0019 |
| PKG | Packaging (existing group) | Number | PKG-0006 |
| TOL | Tools & Spares (existing group) | Number | TOL-0010 |
| SAS | Sub Assemblies (existing group) | Number | SAS-0015 |
| FGD | Finished Goods (existing group) | Number | FGD-0003 |

- Custom fields on Item Group: `satcom_prefix` (Data), `satcom_code_type` (Select: Specs / Number), `satcom_part_no_required` (Check: "Part No required"; on for every Satcom group except HWR, CNS, PKG and TOL, whose screws, solder, boxes and hand tools usually have no manufacturer part number or drawing). Groups without a prefix (ERPNext defaults like Products, Services) are not used for new items.
- **Specs codes:** one item **template** per specs group, code = prefix (`RES`), with Item Attributes whose values carry abbreviations. RES: Resistance (10K, 4K7, 100R…), Package (0402, 0603, 0805, 1206, THT). CAP: Capacitance (100N, 10U, 22P…), Package, Voltage (16V, 50V…). IND: Inductance, Package. HWR: **Thread Size** (M3X10…; a new attribute, because ERPNext's default "Size" holds clothing sizes XS–XL and stays untouched), Material (SS, MS, ZN…). Attribute names are plain words (Resistance, Package, Voltage, Inductance, Thread Size, Material), like item group names, not "Satcom …". Item Variant Settings must produce `RES-10K-0603`. Seed a few values only; stores adds more.
- **Number codes:** a Server Script (Item, Before Insert) fills `item_code` = `<PREFIX>-NNNN` with the next free number for that prefix when it's blank or equals the prefix. If the form insists on an item code, relax it (Property Setter) and enforce in the validate script, or have a Client Script put the prefix in. Verify the real UI flow.
- **Validation** (Server Script, Item, Before Save): code matches `^[A-Z0-9-]{1,20}$` and starts with its group's prefix; duplicate guard on manufacturer part number (block with a message naming the existing code).
- Custom fields on Item: `satcom_mpn` (Manufacturer Part No), `satcom_manufacturer`, `satcom_drawing_no`, `satcom_drawing_rev`.
- Required on new items (validate script): description, stock UOM, item group with a prefix, `satcom_mpn` or `satcom_drawing_no` (not for templates, and only in groups with Part No required; in the other groups the MPN is optional, and the duplicate-MPN guard still applies when one is entered), and **exactly one of** Has Serial No / Has Batch No (D6: every item is labelled, per piece by default, per lot when bought in lots).
- Series (set by the validate script if blank): serial `<ITEM_CODE>-.#####` (→ `RFC-0102-00057`); batch `<ITEM_CODE>-B.####` (→ `CON-0031-B0012`) with "Automatically create new batch" on.
- Item's "Inspection Required before Purchase" stays off (QC happens at release, §5). QC sets each item's default Quality Inspection Template.

### 2.5 Job codes (Project)
Job code = **Project**, created by production/project in-charges.

Customers: a Customer Order job needs a Customer record. Until phase 3 (when sales owns the customer master), the **Satcom Indenter** profile may create Customers too (name, type Company, GSTIN and billing address if known); no other customer fields are used in phase 1. Every role that picks a job on indents, POs, GRNs or issues gets read access to Project (and Customer, read only).

Custom fields on Project:
- `satcom_job_type` (Select, required): Customer Order / Stock Build / Extension
- `satcom_job_title` (Data, required): the human description (the name becomes the code)
- `satcom_parent_job` (Link Project; required for Extension; must be a Customer Order or Stock Build)
- `satcom_customer_po_no`, `satcom_customer_po_date` and standard `customer` (required for Customer Order)
- `satcom_incoming_inspection` (Select: Standard checks / 100% inspection / Sampling as per customer; default Standard checks)
- `satcom_certificates_required` (Check): supplier test certificates mandatory for this job's receipts
- `satcom_qc_notes` (Small Text): customer QC requirements in words

Naming: v16 Projects are named by a naming series (`PROJ-.####`) and Projects Settings has no other option. A Server Script (Project, Before Insert) sets the series per job type, so ERPNext's own counter does the numbering:
- Customer Order → series `J-.YY.-.####` → `J-26-0042` (YY = calendar year of creation)
- Stock Build → series `S-.YY.-.####` → `S-26-0007`
- Extension → series `<parent>-.##` → `J-26-0042-01`, `-02` … (a counter per parent)
- `project_name` = the code too, so lists and links show it; the description stays in `satcom_job_title`.

Prove this works for all three types before building on it. If v16 won't let a Server Script set the series this way, stop and report the options. Don't fall back to free-typed names.

## 3. Indents (Material Request, type Purchase)

- Header field `satcom_job` (Link Project), required unless **every** row is in group TOL (tools bought outside a job; assumption, see §11). Copy it into each row's standard `project`.
- The item grid shows stock in hand and projected qty per row, so the approver sees existing stock before approving.
- **Workflow "Satcom Indent Approval":** Draft → Pending Approval (Satcom Indenter) → Approved (Satcom Approver; submits the document) or Rejected (Satcom Approver; reason required). Every indent needs approval, no value limit (decision 27 Oct; may change when staff join, so keep the rule easy to edit).
- **Cancelling an approved indent:** only a Satcom Approver, with a reason (the same Rejection Reason field, or a Cancel Reason field), and only while no PO line refers to it. An indenter who needs a change asks an approver to cancel, then raises a new indent.
- Rejecting: clicking Reject asks for the reason in a dialog and saves it, so the approver doesn't have to type, save and then reject.
- Notifications: approvers when an indent reaches Pending Approval; the indenter on Approved/Rejected. **Outgoing email from ERPNext isn't set up yet**; use ERPNext's in-app notifications now and add email in the go-live phase.

## 4. Quotations and purchase orders

### 4.1 Quotation rule (decision 27 Oct, corrected)
- Settings: a custom **single DocType "Satcom Settings"** holding `quotation_threshold` (Currency, default 300000), `min_quotations` (Int, default 3, **OPEN**), `threshold_basis` (Select: Net total before tax / Grand total; default Net total, **OPEN**), `concession_needs_approver` (Check, default off, **OPEN**; see §5.3).
- POs **under** the threshold need no comparison. POs **at or above** it need at least `min_quotations` Supplier Quotations from different suppliers, linked on the PO (child table `satcom_quotations` → Supplier Quotation, supplier filled automatically), unless waived.
- **Waiver:** `satcom_quote_waived` + required `satcom_waiver_reason`; only a Satcom Approver may set it (check the role server-side). Enforced when the PO moves to Approved.
- Use the standard Request for Quotation → Supplier Quotation flow to collect quotes.

### 4.2 PO approval
- **Workflow "Satcom PO Approval":** Draft → Pending Approval (Purchase or Indenter) → Approved (Satcom Approver; submitted) or Rejected (reason required). Every PO needs approval.
- Job code flows from indent rows (`project`) into PO rows. A PO row without a job code only for TOL items.
- PO print format with a new letterhead **"Satcom Technologies"** (make it the default; the two generic ERPNext letterheads stay but aren't used). Details, from the warranty certificate footer:
  - Logo: `erpnext/assets/satcom-logo.png` (cropped from a scan; replace with the original logo file when Rahul has it).
  - Registered office: 403, Bhanu Enclave, 7-1-638/1, Sunder Nagar, Erragadda, Hyderabad - 500 038. Ph: +91-40-2371 0333, Fax: +91-40-2371 3444, info@satcomindia.in, www.satcomindia.in
  - Factory: Plot No 12, EMC-TGIIC, Maheshwaram, Rangareddy District, Telangana 501 359
  - CIN: U32204TG1999PTC033193 · GSTIN: 36AAECS9513M1ZW
  - Also create the two Address records (Registered office = billing, Factory = shipping) and set GSTIN/CIN on the Company. POs show the factory as the delivery address.
- Job code on each PO row.

## 5. Goods receipt (GRN) and incoming QC

### 5.1 GRN = Purchase Receipt
- Stores creates it against the PO. **Interim (decision 6 Nov: build QC before §4):** until §4 is live, a GRN may be made without a PO (supplier, items, job per row). When §4 goes live, Buying Settings "Purchase Order Required" switches to Yes and GRNs must come from a PO. Required custom fields: `satcom_vendor_invoice_no`, `satcom_vendor_invoice_date`, `satcom_vendor_dc_no`, `satcom_vendor_dc_date`; at least one attachment (invoice/DC scan) before submit.
- **All accepted quantity lands in `Quality Hold - STPL`** (default on the GRN; other target warehouses blocked).
- Submitting creates serials/batches from the item series. Each Serial No and Batch records the job it was received for: `satcom_received_for_job` (Link Project), from the GRN row's `project`.
- If the row's job has `satcom_certificates_required`, the row needs `satcom_cert_attached` (Check) and a certificate attachment before the material can be released (§5.2).

### 5.2 QC release (decision 27 Oct: QC confirms first)
- **QC Release** = Stock Entry, Material Transfer from Quality Hold, with Inspection Required on; one Quality Inspection per row (per serial/batch where practical, per row with a sample size otherwise).
  - Accepted → `Stores - STPL`. Rejected → `Rejected - STPL`.
- Inspection level comes from the job (`satcom_incoming_inspection`): show it on the inspection; 100% sets sample size = full qty. No job, or a stock build: Standard checks (the item's default template, written by QC). Until QC writes per-group templates, install one starter template "Standard checks" (visual damage, part no / MPN matches, qty matches DC, packaging and ESD intact, documents received) and set it as the default on every Satcom item group's items; QC edits it in the UI.
- Only Quality Manager submits Quality Inspections.
- Stock Settings "Action if Quality Inspection is rejected" is **Stop**, which would block a QC Release that sends rejected rows to `Rejected - STPL`. Set it to **Warn**, and enforce the real rule in a Server Script on Stock Entry (Before Submit): a row whose inspection is **Rejected** may only go to `Rejected - STPL`, and a row going to `Stores - STPL` must have an **Accepted** inspection. On Purchase Receipts nothing is inspected (all of it lands in Quality Hold), so Warn changes nothing there.
- A "Pending QC" view: everything in Quality Hold, oldest first, with GRN no, supplier, job and days waiting.

### 5.3 Failed material (QC confirms, then stores decides)
Field on Stock Entry `satcom_disposition` (Select: Return to Vendor / Scrap / Use under Concession), required for any movement **out of** `Rejected - STPL`. Every disposition records who decided and why (reason required).
- **Return to Vendor:** standard Purchase Return against the GRN, from Rejected.
- **Scrap:** transfer Rejected → `Scrap - STPL` (or Material Issue); reason required.
- **Use under Concession:** transfer Rejected → Stores; reason required. Stores decides. If Satcom Settings `concession_needs_approver` is on, also require `satcom_concession_approved_by` set by a Satcom Approver.

## 6. QR labels

- Every serial number gets its own label; every batch gets one lot label (D6).
- QR content = the serial or batch ID only (`RFC-0102-00057`): **reuse the existing `satcom_qr` field and Server Scripts**, which already fill it with the record name.
- Keep the existing "Satcom QR Label - Serial No" / "- Batch" formats; add to them the GRN no, receipt date and job code (`satcom_received_for_job`).
- **New: "Satcom GRN Labels"** on Purchase Receipt: one label per serial and one per batch on that GRN, in row order, so stores prints a whole delivery in one go. Use the same server-side QR rendering the existing formats get (check the PDF really contains the QR images, as `satcom_qr_labels.render_check` does).
- Label size: existing 100 × 50 mm. **OPEN**: printer and label size not chosen yet. Keep sizes in one CSS block in mm so it's a one-line change.

## 7. Stores issues against job codes (D12)

- Everything enters and leaves through stores; material reaches production only against a job code.
- Phase 1 issue = Stock Entry (Material Transfer) Stores → Work In Progress, header `satcom_job` required (copied to rows' `project`). Phase 2 moves issues onto work orders; keep the checks reusable.
- **Cross-job issue** (allowed with approval, 27 Oct): if any serial/batch issued has `satcom_received_for_job` different from the issue's job, the entry needs `satcom_cross_job_approved_by` set by a Satcom Approver, plus a reason.
- Tools (TOL) may be issued to a person instead of a job: job may be blank when every row is TOL and `satcom_issued_to` (Link User) is set.

## 8. Reports and workspace

Non-standard Query/Script Reports created by the installer:
1. **Job Material Status:** per job: indented, approved, ordered, received, in Quality Hold, released, issued; highlights shortfalls.
2. **Pending Approvals:** indents and POs waiting, with age and value.
3. **Pending QC:** §5.2.
4. **Rejected Stock:** items in Rejected without a disposition, with age.

Workspace **"Satcom Purchase & Stores"**: shortcuts to new Indent, PO, GRN, QC Release, Issue to Job, the four reports, Stock Balance, Stock Ledger, Stock Ageing, Serial No Ledger, Batch-wise Balance History.

## 9. How to build it

- Installer modules in `erpnext/`, one per area, each idempotent with a `run()`: e.g. `satcom_p1_foundation.py`, `satcom_p1_purchase.py`, `satcom_p1_receipt_qc.py`, `satcom_p1_labels.py`, `satcom_p1_reports.py`, plus `satcom_demo_cleanup.py` and `satcom_p1_check.py`.
- Server Script and Client Script **source lives in repo files** (e.g. `erpnext/server_scripts/<name>.py`, `erpnext/client_scripts/<name>.js`); the installer creates or updates the record from the file. Never edit them only in the UI: if a quick UI fix is made, copy it back to the file in the same session.
- Server Scripts run in Frappe's restricted sandbox (no imports, limited API). If a rule can't be done there, stop and explain. Don't work around it by putting files into the erpnext app.
- Custom fields `satcom_*`; custom roles `Satcom *`; custom DocTypes, scripts, workflows, reports and print formats prefixed "Satcom". Master data that users see as ordinary words (item groups, item attributes, warehouses) keeps plain names.
- Rerunning any installer must change nothing the second time.

## 10. Acceptance check

`satcom_p1_check.py`: `create_demo()` builds the scenario with records prefixed `DEMO` (and `demo.*` users); `verify()` runs each step and prints PASS/FAIL per line; `cleanup()` removes it all. Scenario:
1. Items `RES-10K-0603` (variant, batch), `RFC-0001` (serial, MPN set), `MEC-0001` (drawing no, serial), `TOL-0001`. A second item with RFC-0001's MPN is blocked; a bad code is blocked.
2. Jobs `J-26-0001` (Customer Order, 100% inspection, certificates required), extension `J-26-0001-01`, stock build `S-26-0001`; names come out exactly so.
3. Indent for J-26-0001: approver approves; indenter can't approve own; rejection needs a reason.
4. PO of Rs. 4,00,000 net: blocked with fewer than 3 quotations from different suppliers; passes with 3; passes with fewer when an approver waives with a reason; a non-approver can't waive. A Rs. 50,000 PO needs none.
5. GRN with invoice/DC fields and an attachment; everything lands in Quality Hold; serials `RFC-0001-00001…` and batch `RES-10K-0603-B0001` created with `satcom_received_for_job` set.
6. "Satcom GRN Labels" prints one label per serial and per batch, each QR holding the right ID.
7. QC Release is blocked without inspections and, for this job, without the certificate; with them, accepted → Stores, rejected → Rejected.
8. From Rejected: Scrap needs a reason; Concession needs a reason (and an approver when the setting is on); Return to Vendor creates a purchase return.
9. Issue to J-26-0001 works; issuing those serials to S-26-0001 needs approver sign-off; issue without a job is blocked (except TOL to a person).
10. Reports show the scenario correctly. No GL entries exist for any of it.

## 11. Open items (built as settings/defaults; not decided)

| Item | Default used | Who decides |
|---|---|---|
| Number of supplier quotations at or above Rs. 3 lakh | 3 | Vijay / Dileep |
| Threshold basis (before/after GST) | Net total before tax | Vijay / Dileep |
| Concessions need approver sign-off | Off (stores decides) | Vijay / Dileep |
| Tools bought/issued without a job code | Allowed (assumed) | Vijay / Dileep |
| Stock valuation method | FIFO (as set today) | Management + accounts, before go-live |
| Original logo file for the letterhead | Scan crop in `erpnext/assets/` | Rahul |
| Label printer and size | 100 × 50 mm (existing) | Rahul |
| Rack/bin locations (D10) | Not built | Stores |
| Indent self-approval below a value | None | Management, once staff join |

## 12. Not in phase 1
BOMs and work orders, in-process QC, testing, FAT, dispatch, warranty, RMA, sales quotations, asset register, publishing/HTTPS/Google sign-in, backups beyond the pre-change backup, Tally, PBG. See `docs/plan-erpnext.md`.
