# SentriQ — Configuration Drift Detection

SentriQ is a web-based configuration drift detection tool for server fleets. Import parameters and baselines via Excel, run curated drift detection against defined rules, and export findings. No collectors, no agents — purely Excel-driven.

---

## Quick Start

### Docker

```bash
docker compose up --build
```

Opens at http://localhost:8000. PostgreSQL runs alongside the app in a container.

### Ubuntu / Bare Metal

```bash
# 1. Install PostgreSQL
sudo apt update && sudo apt install postgresql postgresql-client libpq-dev -y
sudo systemctl enable --now postgresql

# 2. Create database and user
sudo -u postgres psql <<'SQL'
CREATE USER sq_user WITH PASSWORD 'sentriq2026';
CREATE DATABASE sentriq OWNER sq_user;
\c sentriq
CREATE SCHEMA sq_schema AUTHORIZATION sq_user;
\q
SQL

# 3. Configure environment
cp .env.example .env   # edit DB_URL to match your setup

# 4. Set up Python
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 5. Start the app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### First Run

The app auto-creates all required database tables on first startup. Navigate to http://localhost:8000 and start by importing parameters and baselines via the **Import** page.

---

## Architecture

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│   Browser    │────→│    FastAPI Server    │────→│  PostgreSQL  │
│  (Web UI)    │     │    (port 8000)       │     │  (sq_schema) │
└──────────────┘     └──────────────────────┘     └──────────────┘
                            │         │
                     ┌──────┘         └──────┐
                     ▼                       ▼
            ┌─────────────────┐    ┌──────────────────┐
            │   Import Layer  │    │   Export Layer   │
            │  parameter_     │    │  Excel / CSV /   │
            │  import.py      │    │  HTML            │
            │  baseline_      │    └──────────────────┘
            │  import.py      │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  Drift Engine   │
            │  run_curated_   │
            │  drift_         │
            │  detection()    │
            │         │       │
            │  Rules  │       │
            │  Engine │       │
            └─────────┴───────┘

Layers:
- Web UI: Jinja2 templates with Bootstrap, Chart.js, DataTables
- API: FastAPI routes (main.py), per-feature route modules
- Business Logic: drift_engine.py, services.py, parameter_import.py, baseline_import.py
- Data: PostgreSQL via SQLAlchemy ORM (models.py)
```

### Data Flow

1. **Import Parameters** — Upload a wide-format Excel file (columns = parameters, rows = servers). Auto-creates servers, parameter definitions, and parameter values.
2. **Import Baselines** — Upload a baseline Excel file defining expected values per (server_type, os_family).
3. **Configure Rules** — Define per-DC overrides that replace baseline values for specific parameters.
4. **Scan** — The drift engine compares current values against baselines (or rule overrides), generates a report with compliant/critical/warning counts.
5. **Export** — Download scan results as Excel or CSV or HTML.

---

## Codebase Map

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI application, route definitions, middleware, dashboard and server detail logic |
| `app/db.py` | SQLAlchemy engine setup and session factory |
| `app/models.py` | ORM models: Server, BaselineConfig, ParameterDefinition, ServerParameter, DriftReport, DriftFinding, Rule, ExcelImport, Region |
| `app/schemas.py` | Pydantic schemas for request/response validation |
| `app/services.py` | Business logic: CRUD for parameters, baselines, rules, servers |
| `app/drift_engine.py` | Core drift detection: compares server values vs baselines with rule overrides |
| `app/parameter_import.py` | Wide-format Excel parser for server parameter imports |
| `app/baseline_import.py` | Excel parser for baseline configuration imports |
| `app/excel_export.py` | Generates XLSX export of drift findings |
| `app/csv_export.py` | Generates CSV export of drift findings for Power BI |
| `app/template_setup.py` | Jinja2 template configuration |
| `app/routes/parameters.py` | /parameters CRUD routes |
| `app/routes/baselines.py` | /baseline CRUD routes with Delete All |
| `app/routes/imports.py` | /import routes for parameters and baselines Excel upload |
| `app/routes/rules.py` | /rules CRUD routes |
| `app/templates/` | Jinja2 HTML templates (base, index, server_detail, parameters, baselines, rules, import, help) |

---

## Database

PostgreSQL 15+, schema `sq_schema`, database `sentriq`.

| Table | Purpose |
|---|---|
| `servers` | Server inventory (hostname, IP, type, OS, DC, region) |
| `parameter_definitions` | Configurable parameter definitions (name, display_name, category, severity) |
| `server_parameters` | Append-only parameter values per server (supports vs_previous detection) |
| `baseline_configs` | Expected values per (server_type, os_family) |
| `rules` | Per-DC override rules that replace baseline expected values |
| `drift_reports` | Scan report summaries (timestamps, counts) |
| `drift_findings` | Individual drift findings per report per server |
| `excel_imports` | Audit log of all Excel imports |
| `regions` | Region name definitions |

Tables are auto-created on first startup. Schema changes require manual migration.

```bash
# Manual migration example
psql -U sq_user -d sentriq -c "ALTER TABLE sq_schema.servers ADD COLUMN IF NOT EXISTS dc VARCHAR(100)"
```

---

## Usage

### Leader Board (`/leaderboard`)

- Executive summary of configuration drift across the fleet.
- KPI cards: Total Servers, Critical Findings, Warning Findings, Compliant Servers, Affected Servers.
- Charts: Compliance Breakdown (pie), Top Drifted Parameters, Drift Trend (line), and breakdowns by Data Center, Server Type, and OS Family.
- Filter dropdowns: Data Center, Server Type, OS Family, Parameter.
- Clickable charts — clicking a bar or segment sets the corresponding filter.
- Affected servers table below charts with drill-down links to server detail pages.

### Dashboard (`/`)

- Summary cards: total servers, % compliant, critical findings, changes in 24h.
- Server fleet table with search and sort (DataTables.js).
- Click any hostname to see server detail.
- **Scan Now** button triggers drift detection and generates exports.
- **Export HTML/CSV/Excel** buttons for downloading results.

### Parameters (`/parameters`)

- List all parameter definitions (name, display name, OS, category, type, severity, active status).
- **+ New Parameter** — manually add a parameter definition.
- **Edit** / **Toggle Active** / **Delete** per parameter.
- **Delete All** — removes all parameters, servers, and drift data (full reset).
- Filter by OS (All / Linux / Windows).

### Baselines (`/baselines`)

- List all baseline configurations (server type, OS family, parameter, expected value).
- **+ New Baseline** — manually add a baseline entry.
- **Edit** / **Delete** per baseline.
- **Delete All** — removes all baselines and drift reports.

### Rules (`/rules`)

- Define per-Data-Center overrides that replace baseline expected values during drift detection.
- Each rule specifies: Data Center name, Parameter, Expected Value.
- When a server belongs to a DC that has a rule for a parameter, the rule's expected value is used instead of the baseline value.
- Supports full CRUD: create, edit, delete rules.

**Example**: For DC "A", DNS servers should be "10.0.0.1" while NTP servers should be "10.0.0.2" — even if the baseline says otherwise.

### Import (`/import`)

Two import tabs:

- **Parameters** — Upload a wide-format .xlsx file. Columns represent parameter names (case-insensitive), rows represent servers. A "Hostname" column is required. Optional: IP, Server Type, OS, DC columns. Unknown parameters are auto-created as new parameter definitions.
- **Baselines** — Upload a .xlsx file with "server_type" and "os_family" columns. Parameter columns define expected values. Unknown parameters are auto-created.

Both imports trigger an automatic drift scan and generate exports.

### Server Detail (`/server/{hostname}`)

- Server info: hostname, type, OS, IP, last scanned, DC.
- **Edit DC** — inline edit to assign/change the server's data center.
- Drifted Parameters table (critical/warning severity).
- All Parameters table with current values.
- Scan History — last 10 scan results for this server.

---

## Drift Detection

### How It Works

1. Fetch all servers and their latest parameter values (using `ROW_NUMBER()` window function per server+parameter).
2. Fetch baselines grouped by (server_type, os_family).
3. Fetch rules grouped by (dc_name).
4. For each server:
   - Look up baselines matching its (server_type, os_family).
   - For each baseline parameter, check if a rule exists for the server's DC + parameter definition.
   - **If a rule exists**, use the rule's expected value for comparison.
   - **If no rule**, use the baseline's expected value.
5. Create drift findings for mismatches. Server is compliant only if all parameters match expected values.
6. Generate a report with counts (compliant, critical, warning, unreachable).

### Triggering Scans

- **Dashboard**: Click **Scan Now** button.
- **After Import**: Auto-triggered when importing parameters or baselines.
- **API**: `POST /scan`.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/` | Fleet dashboard |
| GET | `/leaderboard` | Leader Board with charts and KPIs |
| GET | `/api/leaderboard/stats` | Leader Board JSON data |
| GET | `/server/{hostname}` | Server detail page |
| POST | `/server/{hostname}/dc` | Update server DC field |
| GET | `/parameters` | Parameter definitions list |
| GET | `/baseline` | Baseline configurations list |
| GET | `/rules` | Rules list |
| GET | `/import` | Excel import page |
| POST | `/scan` | Trigger drift detection scan |
| GET | `/export/excel/{report_id}` | Download report as XLSX |
| GET | `/export/csv` | Download latest report as CSV |
| GET | `/export/dashboard` | Download dashboard as HTML |
| GET | `/health` | Health check |

---

## Configuration (`.env`)

| Variable | Required | Description |
|---|---|---|
| `DB_URL` | Yes | PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/db`) |
| `EXCEL_OUTPUT_PATH` | Yes | Directory for generated Excel exports |
| `CSV_OUTPUT_PATH` | Yes | File path for generated CSV exports |

---

## Export

- **Excel** — Full scan report with all findings, available via the Export Excel button on the dashboard or `GET /export/excel/{report_id}`.
- **CSV** — Power BI-compatible CSV export with drill-down columns: server, parameter, baseline value, current value, severity, drift type.
- **HTML** — Complete dashboard snapshot as a standalone HTML file.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `relation "sq_schema.servers" does not exist` | Tables not created. Run `python -c "from app.models import Base; from app.db import engine; Base.metadata.create_all(engine)"` |
| Import shows "0 success" | Ensure Excel has a "Hostname" column. Parameters not found are auto-created now. |
| Export Excel not showing | Run a scan (auto-scan runs after import, but manual scan generates the export) |
| Connection refused | Check PostgreSQL is running and `.env` credentials are correct |
| Port in use | Change port in `docker-compose.yml` or `docker run` command |
