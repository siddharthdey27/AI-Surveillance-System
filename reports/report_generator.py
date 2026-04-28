"""
reports/report_generator.py
---------------------------
Generates incident report PDFs using ReportLab.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_report(job_id, alert_history, snapshots, filename="unknown", duration_frames=0):
    """
    Generate a PDF incident report.

    Returns the path to the generated PDF file.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
    )

    pdf_path = str(OUTPUT_DIR / f"incident_report_{job_id[:8]}.pdf")

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=25*mm, bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=22, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"),
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"],
        fontSize=14, spaceBefore=16, spaceAfter=8,
        textColor=colors.HexColor("#16213e"),
    )
    body_style = styles["BodyText"]

    elements = []

    # Title
    elements.append(Paragraph("AI Surveillance Incident Report", title_style))
    elements.append(Spacer(1, 4*mm))

    # Metadata
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_data = [
        ["Job ID:", job_id[:16] + "..."],
        ["Source File:", filename],
        ["Generated:", now],
        ["Total Alerts:", str(len(alert_history))],
        ["Snapshots:", str(len(snapshots))],
    ]
    meta_table = Table(meta_data, colWidths=[100, 350])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8*mm))

    # Summary
    elements.append(Paragraph("Summary Statistics", heading_style))

    type_counts = {}
    for a in alert_history:
        et = a.get("event_type", "Unknown")
        type_counts[et] = type_counts.get(et, 0) + 1

    if type_counts:
        summary_data = [["Event Type", "Count"]]
        for et, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            summary_data.append([et, str(count)])

        summary_table = Table(summary_data, colWidths=[250, 100])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
    else:
        elements.append(Paragraph("No detections recorded.", body_style))

    elements.append(Spacer(1, 8*mm))

    # Detection Log
    elements.append(Paragraph("Detection Log", heading_style))

    if alert_history:
        log_data = [["#", "Event", "Video Time", "Confidence"]]
        for i, a in enumerate(alert_history[:100], 1):
            log_data.append([
                str(i),
                a.get("event_type", ""),
                a.get("video_timestamp", ""),
                f"{a.get('confidence', 0):.2%}",
            ])

        log_table = Table(log_data, colWidths=[30, 150, 100, 80])
        log_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f0f5"), colors.white]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(log_table)
    else:
        elements.append(Paragraph("No alerts recorded during this session.", body_style))

    elements.append(Spacer(1, 8*mm))

    # Snapshots
    if snapshots:
        elements.append(Paragraph("Captured Snapshots", heading_style))
        for i, snap_path in enumerate(snapshots[:20]):
            if os.path.exists(snap_path):
                try:
                    img = Image(snap_path, width=4.5*inch, height=3.4*inch)
                    img.hAlign = "CENTER"
                    elements.append(img)
                    elements.append(Paragraph(
                        f"Snapshot {i+1}: {Path(snap_path).stem}",
                        ParagraphStyle("SnapCaption", parent=body_style, fontSize=8, alignment=1),
                    ))
                    elements.append(Spacer(1, 4*mm))
                except Exception as e:
                    logger.warning("Failed to embed snapshot %s: %s", snap_path, e)

    # Footer
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"Generated by AI Surveillance System on {now}",
        ParagraphStyle("Footer", parent=body_style, fontSize=8, textColor=colors.grey, alignment=1),
    ))

    doc.build(elements)
    logger.info("Report generated: %s", pdf_path)
    return pdf_path
