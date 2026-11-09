# satcom-erp — rules for Claude

Satcom's ERPNext: configuration, phase specs and plans. Split out of `trahul2008/SatcomApp` on 2026-11-09 with its history; the workforce app and the Windows server scripts (failover, heartbeat, Nextcloud, alerting such as `Invoke-FilesHealth`) stay in SatcomApp. If a change needs something there, say so and stop: don't edit that repo from here.

**Infrastructure rules (carried over from SatcomApp):** production runs on two Windows Server 2022 hosts, Server A (192.168.1.85) and Server B (192.168.1.86); whichever holds `192.168.1.87` serves the workforce app. Anything that touches services, VMs, port proxies, firewall rules or failover on those hosts is live infrastructure: read the script's own help and ask Rahul before running or changing it. Never commit `.env` files, passwords, backups or `demo-credentials.txt`.

You're configuring ERPNext v16 for Satcom's factory. Business decisions are made by management and written into the phase spec (`SPEC_PHASE<n>.md`) before they reach you. Implement them faithfully; never decide them. Roadmap and status: `docs/plan-erpnext.md`.

## Where it runs
- VM `satcom-erp` on **Server B** (Hyper-V), 172.20.90.11 on `VM-NAT`. Built by `scripts/New-ErpVM.ps1` + `provision.sh`. Demo build of 2026-10-13 (now the real system). Nightly backup to Server A since 2026-11-06 (see `README.md`); **no replica, no failover yet.**
- Docker compose in `/opt/erpnext` (stock `frappe/erpnext:v16.50.0`, MariaDB 11.8). Site name **`frontend`**. Passwords in `/opt/erpnext/.env` (root-only).
- UI: `http://192.168.1.86:8081` from the office LAN (port proxy on B).
- SSH: alias `satcom-erp-nat` (ProxyJump via B). Off the office LAN, B is reached over Tailscale; Tailscale is for access only, never make anything depend on it.
- Run bench: `ssh satcom-erp-nat "cd /opt/erpnext && sudo docker compose exec -T backend bench --site frontend <command>"`.
- Run an installer module: copy it to the VM, `sudo docker compose cp <file>.py backend:/home/frappe/frappe-bench/apps/erpnext/erpnext/`, then `bench --site frontend execute erpnext.<module>.run`. Copies inside the container disappear when the container is recreated; that's fine, because the repo is the source and the configuration lives in the database.
- After restarting `backend`, restart `frontend` too (its nginx caches the backend IP → 502).

## How things are built: configuration as code
- Everything is created by **idempotent installer modules in the repo root**, each with `run()`. Running one twice must change nothing the second time.
- Runtime logic lives in **Server Scripts and Client Scripts**. Their source lives in repo files (`server_scripts/`, `client_scripts/`) and the installer writes them into ERPNext. If anything is changed in the UI, copy it back to the file in the same session.
- **No custom app, no custom image, no files added to the erpnext app's code** beyond the temporary installer copies above. Server Scripts run in Frappe's restricted sandbox: if a rule can't be done there, stop and explain the options.
- Names: custom fields `satcom_*`, roles `Satcom *`, other custom records start with "Satcom".

## Hard rules
- **Back up before every change run:** `bench --site frontend backup --with-files`. Copy the new backup files off the VM to Rahul's PC, outside the repo, and say where. Never commit backups, `.env` or passwords; never print secrets.
- **Never, without asking first:** `docker compose down -v`, `docker volume rm`, any `docker … prune`, pulling a new image or changing `ERPNEXT_VERSION`, `bench update`, `bench migrate`, `bench drop-site`, `bench restore`, `bench reinstall`, editing `compose.yml` or `provision.sh`, firewall/ufw/DOCKER-USER changes, anything on the Windows hosts or other VMs.
- **No accounting effects.** Accounts stay in Tally; perpetual inventory stays off; nothing you build may create GL entries.
- **Never invent a business rule.** If the spec is silent, unclear or contradicted by what's on the site, stop and ask. **OPEN** items are built as settings with the spec's default.
- **Deleting data:** demo and test records only (prefix `DEMO`, users `demo.*`, and the 2026-10-13 sample data once Rahul approves). The site becomes the real system: once Rahul says real data is going in, nothing is deleted without his explicit OK for that item.

## How to work
- Build the spec **section by section, in order.** After each section:
  1. run its installer twice (the second run must report no changes);
  2. run the phase check (`satcom_p<n>_check.verify`);
  3. tell Rahul in plain words what changed and where to see it in ERPNext;
  4. commit (clear message, e.g. `erpnext: indent approval workflow`), then `git pull --rebase` and push to the working branch `claude/erpnext-phase1-plan` (`git push origin HEAD:claude/erpnext-phase1-plan`). **Never push to main**; merging stays with Rahul;
  5. update `README.md` (how to run things) and `docs/plan-erpnext.md` (status, dated);
  6. wait for his OK before the next section.
- Keep `README.md` short and current. Put the history and decisions in `docs/plan-erpnext.md`.
