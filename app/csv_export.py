import csv
from pathlib import Path
from sqlalchemy import select
from app.db import get_session
from app.models import DriftReport, DriftFinding, Server


def generate_powerbi_csv(report_id, output_path):
    """
    Generates a fixed-schema CSV for Power BI.
    """
    with get_session() as session:
        report = session.execute(
            select(DriftReport).where(DriftReport.id == report_id)
        ).scalar_one()

        findings = session.execute(
            select(DriftFinding, Server)
            .join(Server, DriftFinding.server_id == Server.id)
            .where(DriftFinding.report_id == report_id)
        ).all()

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "report_id",
            "report_date",
            "server_name",
            "server_ip",
            "server_type",
            "os_family",
            "os_version",
            "category",
            "parameter_key",
            "baseline_value",
            "current_value",
            "previous_value",
            "drift_type",
            "severity",
            "first_detected_at",
            "resolved_at",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for finding, server in findings:
                writer.writerow(
                    [
                        str(report.id),
                        report.generated_at.isoformat(),
                        server.hostname,
                        server.ip_address,
                        server.server_type,
                        server.os_family,
                        server.os_version,
                        finding.category,
                        finding.parameter_key,
                        finding.baseline_value,
                        finding.current_value,
                        finding.previous_value,
                        finding.drift_type,
                        finding.severity,
                        finding.first_detected_at.isoformat()
                        if finding.first_detected_at
                        else "",
                        finding.resolved_at.isoformat() if finding.resolved_at else "",
                    ]
                )

        return output_path
