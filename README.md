# SentriQ
> Web-based configuration drift detection platform for server fleets

## Overview
A web-based configuration drift detection platform for server fleets. Import server parameter data and baseline configurations from Excel, define per-Data-Center override rules, run automated scans, and visualize compliance across the fleet via dashboards with charts, leaderboards, and drill-down views.

## Features
- Excel import for parameters and baselines (auto-creates servers + parameter definitions)
- Per-DC override rules (override baseline values per data center)
- Drift detection engine comparing current vs baseline with rule overrides
- Leaderboard page with KPIs, charts, filters, and drill-down
- Server detail page with drift findings and scan history
- Export to Excel (color-coded), CSV (Power BI-compatible), and HTML

## Tech Stack
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white) ![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=flat-square&logo=bootstrap&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

## Installation

```bash
git clone https://github.com/MeGaurav4/SentriQ.git
cd SentriQ
cp .env.example .env
# Edit .env with your DB credentials
docker compose up
```

Open http://localhost:8000

### Database migrations

SentriQ uses Alembic to track schema changes in version control. After updating `app/models.py`, generate a new migration and apply it:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Usage

1. **Seed test data** — `python scripts/seed_data.py`
2. **Import parameters** — Upload `data/test_params_*.xlsx` via Parameters page
3. **Import baselines** — Upload `data/test_baselines_*.xlsx` via Baselines page
4. **Run drift scan** — Triggered automatically or via API
5. **View results** — Leaderboard shows top-drifted servers; drill into Server Detail

## Testing

```bash
pip install -r requirements.txt
pytest tests/
```

## Roadmap
- Authentication / user roles
- Real-time drift alerts via webhook
- Multi-tenant fleet isolation

## License
MIT — see [LICENSE](./LICENSE).