from __future__ import annotations

import csv
import io
from datetime import datetime, timezone


def build_report_csv(summary: dict[str, object], decision: dict[str, object], predictive: list[dict[str, object]], simulation: dict[str, object] | None = None) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "metric", "value"])
    writer.writerow(["executive", "generated_at", datetime.now(timezone.utc).isoformat()])
    writer.writerow(["executive", "average_oee", summary.get("average_oee", 0)])
    writer.writerow(["executive", "trend_direction", summary.get("trend_direction", "stable")])
    writer.writerow(["financial", "revenue_loss", summary.get("financial", {}).get("revenue_loss", 0)])
    writer.writerow(["decision", "priority", decision.get("priority", "LOW")])
    writer.writerow(["decision", "recommended_action", decision.get("recommended_action") or decision.get("action", "")])
    writer.writerow(["decision", "estimated_savings", decision.get("estimated_savings", 0)])

    for loss in summary.get("top_losses", []) or []:
        writer.writerow(["top_loss", loss.get("loss_category", "unknown"), loss.get("impact", 0)])
    for anomaly in summary.get("anomalies", []) or []:
        writer.writerow(["anomaly", anomaly.get("machine", "unknown"), anomaly.get("anomaly_type", "unknown")])
    for item in predictive:
        writer.writerow(["machine_risk", item.get("machine", "unknown"), item.get("failure_risk", 0)])
    if simulation:
        writer.writerow(["simulation", "projected_oee", simulation.get("projected_oee", 0)])
        writer.writerow(["simulation", "revenue_saved", simulation.get("revenue_saved", 0)])

    return buffer.getvalue()


def build_report_pdf(summary: dict[str, object], decision: dict[str, object], predictive: list[dict[str, object]], simulation: dict[str, object] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Operations Executive Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Operations Intelligence Engine", styles["Title"]),
        Paragraph("AI-powered Operations Control Tower", styles["Heading2"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
        Spacer(1, 16),
    ]

    story.append(_table("Executive Summary", [
        ["Average OEE", f"{summary.get('average_oee', 0)}%"],
        ["Trend", str(summary.get("trend_direction", "stable"))],
        ["Revenue Loss", summary.get("financial", {}).get("formatted", "$0")],
        ["Decision Priority", str(decision.get("priority", "LOW"))],
        ["Recommended Action", str(decision.get("recommended_action") or decision.get("action", ""))],
    ]))
    story.append(Spacer(1, 12))

    top_losses = [["Loss", "Impact"]] + [
        [loss.get("loss_category", "unknown"), f"${float(loss.get('impact', 0)):,.0f}"]
        for loss in summary.get("top_losses", []) or []
    ]
    story.append(_table("Top Losses", top_losses))
    story.append(Spacer(1, 12))

    risk_rows = [["Machine", "Severity", "Risk", "Remaining Hours"]] + [
        [
            item.get("machine", "unknown"),
            item.get("severity", "LOW"),
            item.get("failure_risk", 0),
            item.get("remaining_hours", 0),
        ]
        for item in predictive[:8]
    ]
    story.append(_table("Predictive Risk", risk_rows))

    if simulation:
        story.append(Spacer(1, 12))
        story.append(_table("Simulation Outcome", [
            ["Action", simulation.get("action", "")],
            ["Current OEE", simulation.get("current_oee", 0)],
            ["Projected OEE", simulation.get("projected_oee", 0)],
            ["Revenue Saved", simulation.get("formatted_revenue_saved", "$0")],
            ["Decision", simulation.get("decision", "Monitor")],
        ]))

    doc.build(story)
    return buffer.getvalue()


def _table(title: str, rows: list[list[object]]):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, Table, TableStyle

    styles = getSampleStyleSheet()
    table = Table(rows, colWidths=[170, 310])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return Table([[Paragraph(title, styles["Heading3"])], [table]], colWidths=[480])
