# Ignition Admin Panel

A desktop GUI tool for quickly spinning up and managing **Inductive Automation Ignition** development gateways using **Docker Compose**.  
Easily restore backups, import projects and tags, and manage your development environment with a modern **PyQt5 interface**.

---

## Features

- **Spin up Ignition gateways** in either:
  - *Clean mode* (fresh start)
  - *Backup restore mode* (load from `.gwbk`)
- **Import and unzip projects** into the correct Ignition structure
- **Load tag exports** (`.json` or `.xml`)
- **Auto-generate Docker Compose and `.env` files** from GUI inputs
- **Hardened Docker provisioning** with persistent data volumes, optional module/JDBC mounts, and automatic detection of activation or license secrets
- **Ship Automation Gateway sidecars** with selectable config templates (default or telemetry-focused) so Ignition sandboxes can stream industrial data without manual YAML editing
- **Stream and view logs** (gateway + container) in real time
- **Tear down or purge Docker resources** with one click
- **Dark-themed, user-friendly PyQt5 interface**

---

## Directory Structure

To prevent wrapping on GitHub, the structure is shown inside a fixed-width block.

<div style="overflow-x: auto; white-space: nowrap;">

<pre>
ignition-admin-panel/
├── backups/                 # User-uploaded .gwbk gateway backups
│   └── myBaseline.gwbk
├── projects/                # Unzipped project folders (populated by GUI)
│   └── MyProject/           # e.g. contains Vision/, Perspective/, scripts/, etc.
├── tags/                    # User-uploaded tag exports (JSON or XML)
│   └── myTags.json
├── templates/               # Jinja2 templates for Compose & env
│   ├── docker-compose.yml.j2
│   └── .env.j2              # preferred as an env-file
├── generated/               # Rendered artifacts (overwritten each run)
│   ├── docker-compose.yml
│   └── .env                 # generated .env file if used
├── modules/                 # Optional third-party Ignition modules (.modl)
├── jdbc/                    # Optional third-party JDBC drivers (.jar)
├── secrets/                 # Optional activation-token / license-key files
├── src/                     # Application source code
│   ├── gui.py               # PyQt5 entrypoint & widgets
│   ├── compose_generator.py # Renders Jinja2 → generated/
│   ├── docker_manager.py    # Calls `docker compose up/down`, streams logs
│   ├── models.py            # Data classes for Backups/Projects/Tags
│   └── utils.py             # Helper functions (unzipping, file ops)
├── logs/                    # Captured container & panel logs
│   └── ignition-dev.log
├── requirements.txt         # Dependencies (PyQt5, Jinja2, docker-py, PyYAML, etc.)
└── README.md                # Overview & quickstart
</pre>

</div>

---

## Quickstart

1. Clone the repository:
   ```bash
   git clone (https://github.com/LopeWale/dev_ignition.git)
   cd ignition-admin-panel
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the GUI:
   ```bash
   python src/gui.py
   ```

---

## HTTP API (Preview)

The groundwork for the future web application now includes a FastAPI-powered service layer. It exposes environment lifecycle operations so the forthcoming SPA can provision gateways over HTTP.

1. Install dependencies (includes FastAPI, Uvicorn, and pytest for the new service):
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the API locally:
   ```bash
   uvicorn api.server:app --reload
   ```
3. Explore the interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs). Key endpoints:
   - `POST /api/environments` – render Compose and `.env` artifacts for a new gateway definition.
   - `GET /api/environments` – list provisioned environments and their generated file locations.
   - `GET /api/environments/{id}` – retrieve a detailed, sanitised view of an environment.
   - `POST /api/environments/{id}/actions/start` – launch the generated stack (optionally waiting for the gateway health check).
   - `POST /api/environments/{id}/actions/stop` – tear down the stack and mark the environment as stopped.
   - `DELETE /api/environments/{id}` – remove generated artifacts for a retired environment.
   - `GET /api/automation-gateway/templates` – inspect available Automation Gateway configuration templates exposed by the control plane.
   - `GET /api/automation-gateway/templates/{name}` – retrieve the selected template’s metadata and body for UI preview workflows.

Environment records track lifecycle status (`created`, `running`, `stopped`, `error`, etc.) alongside timestamps for the most
recent start/stop events so the upcoming SPA can surface stateful controls.


Generated files are written beneath `generated/environments/<id>/` so each environment remains isolated. Metadata is tracked in `generated/environments/registry.json` and excludes sensitive values like admin passwords.

---

## Advanced Docker configuration

- **Persistent gateway data** – The generated Compose file mounts Ignition's runtime data to `/data` by default, following the community recommendation for resilient upgrades and container rebuilds. [Reference](https://github.com/thirdgen88/ignition-docker/blob/main/docs/README.md#how-to-persist-gateway-data)
- **Drop-in modules** – Place signed `.modl` packages in the `modules/` folder (or point the UI at a custom directory) to bind-mount `/modules` and enable curated module sets with `GATEWAY_MODULES_ENABLED`. [Reference](https://github.com/thirdgen88/ignition-docker/blob/main/docs/README.md#how-to-enable-disable-default-modules)
- **Drop-in JDBC drivers** – Add JDBC `.jar` files to `jdbc/` to bind-mount `/jdbc` and automatically link custom drivers before gateway start-up. [Reference](https://github.com/thirdgen88/ignition-docker/blob/main/docs/README.md#how-to-integrate-third-party-jdbc-drivers)
- **Secrets-aware licensing** – Store activation tokens or license keys in `secrets/activation-token` and `secrets/license-key`. They will be mounted read-only and injected into the container via `IGNITION_ACTIVATION_TOKEN_FILE` / `IGNITION_LICENSE_KEY_FILE` so sensitive values stay out of Compose files.
- **Custom runtime identities** – Provide optional `IGNITION_UID` / `IGNITION_GID` values to match host ownership when bind-mounting data directories or secrets.
- **Cross-platform volume mounts** – Generated Compose files now emit long-form volume syntax and pre-create bind-mount directories so host paths resolve cleanly across Linux, macOS, and Windows workstations.
