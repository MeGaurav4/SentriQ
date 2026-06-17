# Import Feature - Testing Guide

## Files

| File | What it does | OS |
|------|-------------|-----|
| `data/test_params_linux.xlsx` | Imports server parameter values for 6 Linux servers | Linux |
| `data/test_params_windows.xlsx` | Imports server parameter values for 6 Windows servers | Windows |
| `data/test_baselines_linux.xlsx` | Sets expected (baseline) values for Linux server types (Web, APP, DB) | Linux |
| `data/test_baselines_windows.xlsx` | Sets expected (baseline) values for Windows server types (Web, APP, DB) | Windows |

## Prerequisites

1. App is running and accessible in browser.
2. Parameter definitions exist in the database. Run this once:
   ```bash
   source venv/bin/activate
   python scripts/seed_data.py
   ```
   This creates the required parameter definitions, seeds 12 test servers, and generates the Excel files.

## Step-by-Step

### 1. Import Server Parameters

1. Open the app in your browser (default: `http://localhost:8000`).
2. Click **Import** in the top navigation bar.
3. You will see two tabs: **Parameter Import** and **Baseline Import**.
4. Make sure you are on the **Parameter Import** tab.

#### Linux:
1. Select **Linux** as OS Family.
2. Click "Choose File" and select `data/test_params_linux.xlsx`.
3. Click **Upload Parameters**.
4. You should see an "Import Result" card showing:
   - Total rows: 6
   - Success count, 0 errors

#### Windows:
1. Select **Windows** as OS Family.
2. Click "Choose File" and select `data/test_params_windows.xlsx`.
3. Click **Upload Parameters**.
4. Result should show: 6 rows, success count, 0 errors.

### 2. Verify Servers Were Created

1. Click **Dashboard** in the navigation bar.
2. You should see 12 servers listed (web-lnx-01 through db-win-02).

### 3. Import Baselines

1. Click **Import** again.
2. Switch to the **Baseline Import** tab.

#### Linux:
1. Select **Linux** as OS Family.
2. Select `data/test_baselines_linux.xlsx`.
3. Click **Upload Baselines**.
4. Result should show: 3 rows, success count, 0 errors.

#### Windows:
1. Select **Windows** as OS Family.
2. Select `data/test_baselines_windows.xlsx`.
3. Click **Upload Baselines**.
4. Result should show: 3 rows, success count, 0 errors.

### 4. Run a Scan

1. Click **Dashboard** in the navigation bar.
2. Click the **Scan Now** button.
3. After the scan (takes a few seconds), the page refreshes.
4. Servers with parameter values that differ from their baseline will show as **WARNING** or **CRITICAL**.

### 5. View Baselines

1. Click **Baselines** in the navigation bar.
2. You will see all the baseline configurations grouped by (server_type, os_family).
3. You can edit, delete, or create new baselines from this page.

### 6. View Parameters

1. Click **Parameters** in the navigation bar.
2. You can filter by All / Linux / Windows.
3. Each parameter definition is listed with its category, type, and severity.
4. You can toggle active/inactive, edit, or delete parameters.

## Understanding the Results

### How Status Is Determined

Each server's status is computed by comparing its actual parameter values (imported via Excel) against the expected baseline values for its server type and OS family.

- **OK**: All parameter values match their baselines.
- **WARNING**: One or more parameters differ from baseline (non-critical).
- **CRITICAL**: One or more parameters flagged as critical differ from baseline.

### Example Walkthrough

**Compliant server (`web-lnx-01`):**

```
CPU=8  (baseline: 8)   ✓ match
Memory_GB=31.14  (baseline: 31.14)   ✓ match
→ Status: OK (all values match)
```

**Non-compliant server (`web-lnx-02`):**

```
CPU=4  (baseline: 8)  ✗ lower than expected
Memory_GB=15.75  (baseline: 31.14)  ✗ lower than expected
→ Status: WARNING (2 parameters differ from baseline)
```

**Server detail page breakdown (`/server/web-lnx-02`):**
1. **Status summary cards** at top: CRITICAL 0, WARNING 2, OK (No Baseline) 3
2. **Drifted Parameters** table: lists each parameter that differs — shows Expected (Baseline) vs Actual (Current), with severity badge
3. **All Parameters** table: complete list of every parameter value currently collected for this server
4. **Scan History**: timestamps of past collector snapshots (only populated when JSON drops arrive from the legacy collector system)

### Common Scenarios

| Scenario | Why It Happens | What to Do |
|----------|---------------|------------|
| Server shows WARNING, CPU shows "8 vs 4" | Baseline expects 8 cores, server only has 4 | Investigate if server was downgraded or baseline is wrong |
| Server shows WARNING, SENDMAIL "active vs inactive" | Mail service stopped compared to baseline | Check if service should be running |
| Server shows OK | All values match baseline exactly | No action needed |
| "OK (No Baseline)" count > 0 | Some parameters (like IP, OS version) have data but no baseline configured | This is normal for metadata fields; only parameters critical to your environment need baselines |

## Running on Different Platforms

### Linux (bare metal)
```bash
# Start the app
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, seed data
source venv/bin/activate
python scripts/seed_data.py

# Open http://localhost:8000 in browser
```

### Windows 11 (Docker Desktop)
```bash
# Files are already in the data/ directory
# Copy them to your Windows machine

# Start app via Docker
docker compose up --build

# Seed data inside the container
docker compose exec app python scripts/seed_data.py

# Open http://localhost:8000
```

### Production
1. Upload the Excel files through the Import page.
2. Parameter definitions may already exist from the collector system. If not, create them manually via Parameters page or run `scripts/seed_data.py`.
3. Servers do NOT need to pre-exist — parameter import auto-creates them from Hostname, IP, Server_Type, and OS columns.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "parameter 'XYZ' not found for OS 'linux'" | The column name in the Excel doesn't match any parameter definition. Check Parameters page for correct names. |
| Import succeeds but 0 parameters imported | The column headers don't match any parameter definitions (case-insensitive). Check spelling. |
| Servers not showing on Dashboard | Run a Scan first, or the import may have failed. Check Import History section on Import page for error details. |
| Docker: "connection refused" | Make sure PostgreSQL container is healthy: `docker compose ps` |
