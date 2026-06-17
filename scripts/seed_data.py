import os
import sys
import uuid
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openpyxl import Workbook
from app.db import engine, get_session
from app.models import Server
from sqlalchemy import select, MetaData

LINUX_PARAMS = {
    "CPU": ("system", "string", "warning"),
    "Memory_GB": ("system", "string", "warning"),
    "Swap_GB": ("system", "string", "warning"),
    "App_Users": ("system", "string", "info"),
    "Web_Instances": ("system", "string", "info"),
    "DB_Instances": ("system", "string", "info"),
    "SENTINEL_VERSION": ("security", "string", "critical"),
    "SENTINEL_STATUS": ("security", "string", "critical"),
    "NTP_SERVERS": ("system", "string", "warning"),
    "NTP_SYNC_STATUS": ("system", "string", "critical"),
    "SYSLOG_30134": ("system", "string", "warning"),
    "NAMESERVERS": ("network", "string", "warning"),
    "SENDMAIL": ("system", "string", "info"),
    "DC_SERVICE": ("system", "string", "info"),
    "XAGT": ("security", "string", "warning"),
    "BindPlane": ("system", "string", "warning"),
}

WINDOWS_PARAMS = {
    "CPU": ("system", "string", "warning"),
    "Memory_GB": ("system", "string", "warning"),
    "SENTINEL_VERSION": ("security", "string", "critical"),
    "SENTINEL_STATUS": ("security", "string", "critical"),
    "NTP_SERVERS": ("system", "string", "warning"),
    "NTP_SYNC_STATUS": ("system", "string", "critical"),
    "SYSLOG_30134": ("system", "string", "warning"),
    "DNS": ("network", "string", "warning"),
    "BindPlane": ("system", "string", "warning"),
    "Local_Group_Policy": ("security", "string", "critical"),
}

LINUX_PARAM_HEADERS = ["Hostname", "IP", "Server_Type", "OS", "CPU", "Memory_GB", "Swap_GB", "App_Users", "Web_Instances", "DB_Instances", "SENTINEL_VERSION", "SENTINEL_STATUS", "NTP_SERVERS", "NTP_SYNC_STATUS", "SYSLOG_30134", "NAMESERVERS", "SENDMAIL", "DC_SERVICE", "XAGT", "BindPlane"]

WINDOWS_PARAM_HEADERS = ["Hostname", "IP", "Server_Type", "OS", "CPU", "Memory_GB", "SENTINEL_VERSION", "SENTINEL_STATUS", "NTP_SERVERS", "NTP_SYNC_STATUS", "SYSLOG_30134", "DNS", "BindPlane", "Local_Group_Policy"]

LINUX_SERVERS = [
    ["web-lnx-01", "10.20.0.21", "Web", "RHEL 9.7", "8", "31.14", "7.50", "tomcat", "3", "1", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
    ["web-lnx-02", "10.20.0.22", "Web", "RHEL 8.8", "4", "15.75", "4.00", "apache", "2", "0", "24.2.2.18", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22", "active", "active", "inactive", "running"],
    ["app-lnx-01", "10.20.10.11", "APP", "Ubuntu 22.04", "16", "62.50", "2.00", "deploy", "1", "0", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "inactive", "active", "active", "stopped"],
    ["app-lnx-02", "10.20.10.12", "APP", "Ubuntu 20.04", "8", "31.14", "4.00", "appuser", "0", "0", "24.2.2.16", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22", "active", "inactive", "active", "running"],
    ["db-lnx-01", "10.20.20.31", "DB", "RHEL 9.7", "32", "127.82", "8.00", "oracle", "0", "3", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
    ["db-lnx-02", "10.20.20.32", "DB", "RHEL 8.8", "16", "62.50", "4.00", "mysql", "0", "2", "24.2.2.19", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
]

WINDOWS_SERVERS = [
    ["web-win-01", "10.20.0.51", "Web", "Windows Server 2022", "8", "32.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
    ["web-win-02", "10.20.0.52", "Web", "Windows Server 2019", "4", "16.00", "24.2.2.18", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22", "running", "Configured"],
    ["app-win-01", "10.20.10.61", "APP", "Windows Server 2022", "16", "64.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
    ["app-win-02", "10.20.10.62", "APP", "Windows Server 2019", "8", "32.00", "24.2.2.19", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "stopped", "Not Configured"],
    ["db-win-01", "10.20.20.71", "DB", "Windows Server 2022", "32", "128.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
    ["db-win-02", "10.20.20.72", "DB", "Windows Server 2019", "16", "64.00", "24.2.2.18", "On", "10.95.231.96", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22", "running", "Configured"],
]

BASELINE_LINUX = [
    ["Web", "linux", "8", "31.14", "7.50", "tomcat", "3", "1", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
    ["APP", "linux", "16", "62.50", "2.00", "deploy", "1", "0", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
    ["DB", "linux", "32", "127.82", "8.00", "oracle", "0", "3", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "active", "active", "active", "running"],
]

BASELINE_WINDOWS = [
    ["Web", "windows", "8", "32.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
    ["APP", "windows", "16", "64.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
    ["DB", "windows", "32", "128.00", "24.2.2.20", "On", "10.95.231.96;10.95.14.29", "SYNCED", "*.* @10.95.14.55:30134", "10.95.13.22;10.95.208.17", "running", "Configured"],
]

BASELINE_LINUX_HEADERS = ["server_type", "os_family"] + list(LINUX_PARAMS.keys())
BASELINE_WINDOWS_HEADERS = ["server_type", "os_family"] + list(WINDOWS_PARAMS.keys())

def seed_parameter_definitions():
    metadata = MetaData(schema="sq_schema")
    metadata.reflect(bind=engine, only=["parameter_definitions"])
    t = metadata.tables["sq_schema.parameter_definitions"]
    with engine.begin() as conn:
        existing = {(row.name, row.os_family) for row in conn.execute(select(t.c.name, t.c.os_family))}
        insert_rows = []
        for name, (cat, dt, sev) in LINUX_PARAMS.items():
            if (name, "linux") not in existing:
                insert_rows.append({"id": uuid.uuid4(), "name": name, "display_name": name.replace("_", " "), "os_family": "linux", "category": cat, "data_type": dt, "is_active": True, "sort_order": 0, "default_severity": sev})
        for name, (cat, dt, sev) in WINDOWS_PARAMS.items():
            if (name, "windows") not in existing:
                insert_rows.append({"id": uuid.uuid4(), "name": name, "display_name": name.replace("_", " "), "os_family": "windows", "category": cat, "data_type": dt, "is_active": True, "sort_order": 0, "default_severity": sev})
        if insert_rows:
            conn.execute(t.insert(), insert_rows)
            print(f"Seeded {len(insert_rows)} parameter definitions")
        else:
            print("Parameter definitions already exist")

def seed_servers():
    with get_session() as session:
        existing = {row.hostname.lower() for row in session.query(Server).all()}
        count = 0
        for data in LINUX_SERVERS:
            hn = data[0].lower()
            if hn not in existing:
                s = Server(id=uuid.uuid4(), hostname=data[0], ip_address=data[1], server_type=data[2].lower(), os_family="linux", os_version=data[3], last_seen=datetime.now(timezone.utc))
                session.add(s)
                count += 1
        for data in WINDOWS_SERVERS:
            hn = data[0].lower()
            if hn not in existing:
                s = Server(id=uuid.uuid4(), hostname=data[0], ip_address=data[1], server_type=data[2].lower(), os_family="windows", os_version=data[3], last_seen=datetime.now(timezone.utc))
                session.add(s)
                count += 1
        session.commit()
        print(f"Seeded {count} new servers (total: {len(LINUX_SERVERS) + len(WINDOWS_SERVERS)})")

def make_excel(headers, rows, path):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)
    print(f"Created: {path}")

def main():
    os.makedirs("data", exist_ok=True)
    seed_parameter_definitions()
    seed_servers()
    make_excel(LINUX_PARAM_HEADERS, LINUX_SERVERS, "data/test_params_linux.xlsx")
    make_excel(WINDOWS_PARAM_HEADERS, WINDOWS_SERVERS, "data/test_params_windows.xlsx")
    make_excel(BASELINE_LINUX_HEADERS, BASELINE_LINUX, "data/test_baselines_linux.xlsx")
    make_excel(BASELINE_WINDOWS_HEADERS, BASELINE_WINDOWS, "data/test_baselines_windows.xlsx")
    print("\nDone. Files in data/:")
    for f in sorted(os.listdir("data")):
        if f.startswith("test_") and f.endswith(".xlsx"):
            print(f"  data/{f}")

if __name__ == "__main__":
    main()
