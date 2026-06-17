# Docker Setup on Windows 11

Run Drift Guard on Windows using Docker Desktop. No Python or PostgreSQL needed locally.

## Prerequisites

- Windows 11 Pro/Enterprise/Education (with Hyper-V and WSL 2).
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/).

## 1. Install Docker Desktop

1. Download Docker Desktop from the official site.
2. Run the installer — ensure **Use WSL 2 instead of Hyper-V** is checked.
3. Restart when prompted.
4. After restart, Docker Desktop starts automatically. Wait for the whale icon in the system tray to stop animating.
5. Open PowerShell or CMD and verify:
   ```powershell
   docker --version
   docker compose version
   ```

## 2. Obtain the Code

Unzip the codebase archive into a folder named `sentriq`. Open PowerShell or CMD in that folder.

## 3. Configure Environment

Copy or create `.env` (use Notepad or any text editor):

```
DB_URL=postgresql://sq_user:sentriq2026@db:5432/sentriq
```

> **Note:** The DB host is `db` (the Docker service name), not `localhost`.

## 4. Start the Application

```powershell
docker compose up --build
```

First run takes 2-5 minutes (downloads base images, installs dependencies).

Expected output:
```
db_1   | database system is ready to accept connections
app_1  | INFO:     Started server process [1]
app_1  | INFO:     Waiting for application startup.
app_1  | INFO:     Application startup complete.
app_1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 5. Open the Dashboard

Browse to http://localhost:8000.

## 6. Stop the Application

```powershell
docker compose down
```

Data persists in the `pgdata` Docker volume. Start again with `docker compose up --build`.

## 7. View Logs

```powershell
docker compose logs -f
```

## 8. Reset Everything

```powershell
docker compose down -v   # destroys database volume
docker compose up --build
```

## Troubleshooting on Windows

| Problem | Likely Fix |
|---|---|
| `docker: command not found` | Docker Desktop not installed or not running. |
| Port 8000 in use | Change the host port in `docker-compose.yml`: `"8001:8000"`. |
| Port 5432 in use | The DB binds to 127.0.0.1:5432 inside Docker only. If you have a local PostgreSQL, stop it first or change the DB port mapping. |
| Permission denied on data/ | `data/` must exist; create it if Docker cannot mount it. |
| WSL 2 update required | Run `wsl --update` from PowerShell (Admin). |
