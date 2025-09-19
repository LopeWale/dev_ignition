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
