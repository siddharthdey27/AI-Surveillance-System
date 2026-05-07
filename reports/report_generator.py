"""
reports/report_generator.py
---------------------------
Generates professional incident report PDFs using ReportLab.

Sections
--------
1. Cover / Executive Summary
2. Violence Segments  — timestamps where violence was actually detected
3. Other Incidents    — weapons, fire, smoke
4. Full Detection Log — every alert in chronological order
5. Captured Snapshots — embedded JPEG frames from moments of detection
"""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colour palette ─────────────────────────────────────────────────────────────
C_DARK       = "#0f0c29"
C_MID        = "#1a1a2e"
C_ACCENT     = "#00d4ff"
C_RED        = "#ef4444"
C_ORANGE     = "#f59e0b"
C_GREEN      = "#22c55e"
C_GREY_LIGHT = "#f4f6f8"
C_GREY_MID   = "#e2e8f0"
C_TEXT_DIM   = "#64748b"


def _severity_colour(event_type: str) -> str:
    """Return a hex colour for the event type row."""
    et = event_type.lower()
    if "violence" in et:
        return "#fef2f2"   # light red
    if "gun" in et or "knife" in et or "weapon" in et:
        return "#fff7ed"   # light orange
    if "fire" in et or "smoke" in et:
        return "#fefce8"   # light yellow
    return "#f0fdf4"       # light green


def generate_report(
    job_id: str,
    alert_history: list,
    snapshots: list,
    filename: str = "unknown",
    duration_frames: float = 0,
    violence_timeline: list = None,
) -> str:
    """
    Generate a PDF incident report.

    Parameters
    ----------
    job_id           : unique job identifier
    alert_history    : list of alert dicts {event_type, video_timestamp, confidence, message}
    snapshots        : list of JPEG snapshot file paths
    filename         : original video filename
    duration_frames  : progress value (0-1) used to estimate duration
    violence_timeline: list of {frame, ts, prob} dicts (optional)

    Returns the path to the generated PDF.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, HRFlowable, KeepTogether,
    )

    W, H = A4
    pdf_path = str(OUTPUT_DIR / f"incident_report_{job_id[:8]}.pdf")

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=22*mm, bottomMargin=18*mm,
    )

    # ── Styles ─────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def _style(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=styles[parent], **kw)

    S = {
        "title":   _style("T",  "Title",    fontSize=24, textColor=colors.HexColor(C_DARK),
                          spaceAfter=2, leading=28),
        "sub":     _style("Su", "Normal",   fontSize=10, textColor=colors.HexColor(C_TEXT_DIM),
                          spaceAfter=0),
        "h2":      _style("H2", "Heading2", fontSize=13, textColor=colors.HexColor(C_MID),
                          spaceBefore=14, spaceAfter=6, leading=16),
        "h3":      _style("H3", "Heading3", fontSize=10, textColor=colors.HexColor(C_TEXT_DIM),
                          spaceBefore=8, spaceAfter=4, leading=13),
        "body":    styles["BodyText"],
        "small":   _style("Sm", "Normal",   fontSize=8, textColor=colors.HexColor(C_TEXT_DIM)),
        "caption": _style("Ca", "Normal",   fontSize=8, textColor=colors.HexColor(C_TEXT_DIM),
                          alignment=TA_CENTER),
        "mono":    _style("Mo", "Normal",   fontSize=9, fontName="Courier",
                          textColor=colors.HexColor(C_DARK)),
        "alert":   _style("Al", "Normal",   fontSize=9, textColor=colors.HexColor(C_RED),
                          fontName="Helvetica-Bold"),
        "footer":  _style("Fo", "Normal",   fontSize=7.5, alignment=TA_CENTER,
                          textColor=colors.HexColor(C_TEXT_DIM)),
    }

    # ── Shared table style helpers ──────────────────────────────────────────────
    def _header_style(bg=C_MID):
        return [
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor(bg)),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor(C_GREY_MID)),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]

    # ── Derived stats ───────────────────────────────────────────────────────────
    now_str     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_alerts = len(alert_history)

    type_counts: dict = {}
    for a in alert_history:
        et = a.get("event_type", "Unknown")
        type_counts[et] = type_counts.get(et, 0) + 1

    violence_alerts = [a for a in alert_history if "violence" in a.get("event_type", "").lower()]
    weapon_alerts   = [a for a in alert_history
                       if any(k in a.get("event_type", "").lower() for k in ("gun", "knife", "weapon"))]
    fire_alerts     = [a for a in alert_history
                       if any(k in a.get("event_type", "").lower() for k in ("fire", "smoke"))]

    if len(violence_alerts) > 0:
        threat_level = "HIGH"
        threat_colour = C_RED
    elif len(weapon_alerts) > 0 or len(fire_alerts) > 0:
        threat_level = "MEDIUM"
        threat_colour = C_ORANGE
    elif total_alerts > 0:
        threat_level = "LOW"
        threat_colour = C_ORANGE
    else:
        threat_level = "NONE"
        threat_colour = C_GREEN

    elements = []

    # ══════════════════════════════════════════════════════════════════════════
    # 1. COVER BANNER
    # ══════════════════════════════════════════════════════════════════════════
    banner_data = [[
        Paragraph("AI SURVEILLANCE", _style("BT", "Normal", fontSize=20, textColor=colors.white,
                                            fontName="Helvetica-Bold", leading=24)),
        Paragraph("INCIDENT REPORT", _style("BT2", "Normal", fontSize=20, textColor=colors.white,
                                             fontName="Helvetica-Bold", leading=24)),
    ]]
    banner = Table(banner_data, colWidths=[doc.width / 2] * 2)
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(C_DARK)),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    elements.append(banner)
    elements.append(Spacer(1, 6*mm))

    # Threat-level pill
    pill_data = [[Paragraph(
        f"THREAT LEVEL: {threat_level}",
        _style("PL", "Normal", fontSize=11, fontName="Helvetica-Bold",
               textColor=colors.white, alignment=TA_CENTER),
    )]]
    pill = Table(pill_data, colWidths=[doc.width])
    pill.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(threat_colour)),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS",(0, 0), (-1, -1), 4),
    ]))
    elements.append(pill)
    elements.append(Spacer(1, 8*mm))

    # ── Meta table ─────────────────────────────────────────────────────────────
    meta = [
        ["Job ID",        job_id[:16] + ("..." if len(job_id) > 16 else "")],
        ["Source File",   filename],
        ["Generated At",  now_str],
        ["Total Alerts",  str(total_alerts)],
        ["Violence Alerts", str(len(violence_alerts))],
        ["Weapon Alerts", str(len(weapon_alerts))],
        ["Fire/Smoke Alerts", str(len(fire_alerts))],
        ["Snapshots Captured", str(len(snapshots))],
    ]
    meta_tbl = Table([[Paragraph(k, S["h3"]), Paragraph(v, S["mono"])] for k, v in meta],
                     colWidths=[55*mm, doc.width - 55*mm])
    meta_tbl.setStyle(TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor(C_GREY_MID)),
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor(C_GREY_LIGHT)),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 10*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. VIOLENCE SEGMENTS  (only frames where is_violent was True)
    # ══════════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("Violence Segments", S["h2"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(C_RED),
                               spaceAfter=4))

    if violence_alerts:
        # Build continuous segments: group consecutive timestamps < 5s apart
        def _ts_to_sec(ts: str) -> float:
            """'HH:MM:SS' → float seconds."""
            try:
                parts = ts.split(":")
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            except Exception:
                return 0.0

        sorted_v = sorted(violence_alerts, key=lambda a: _ts_to_sec(a.get("video_timestamp", "0:0:0")))
        segments = []
        seg_start = None
        seg_end   = None
        seg_confs = []
        SEG_GAP   = 5.0   # seconds: gap larger than this starts a new segment

        for a in sorted_v:
            ts_sec = _ts_to_sec(a.get("video_timestamp", "0:0:0"))
            conf   = a.get("confidence", 0.0)
            if seg_start is None:
                seg_start, seg_end, seg_confs = ts_sec, ts_sec, [conf]
            elif ts_sec - seg_end <= SEG_GAP:
                seg_end = ts_sec
                seg_confs.append(conf)
            else:
                segments.append((seg_start, seg_end, seg_confs))
                seg_start, seg_end, seg_confs = ts_sec, ts_sec, [conf]
        if seg_start is not None:
            segments.append((seg_start, seg_end, seg_confs))

        def _sec_to_ts(s: float) -> str:
            h = int(s) // 3600
            m = (int(s) % 3600) // 60
            sec = int(s) % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"

        seg_data = [["#", "Start", "End", "Duration", "Avg Conf", "Peak Conf"]]
        for i, (s, e, confs) in enumerate(segments, 1):
            dur  = e - s
            avg_c = sum(confs) / len(confs)
            pk_c  = max(confs)
            seg_data.append([
                str(i),
                _sec_to_ts(s),
                _sec_to_ts(e),
                f"{dur:.0f}s",
                f"{avg_c:.1%}",
                f"{pk_c:.1%}",
            ])

        seg_tbl = Table(seg_data, colWidths=[18, 52, 52, 46, 50, 50])
        ts = _header_style(C_RED[1:] and C_RED)   # red header
        ts += [
            ("BACKGROUND",    (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
            ("TEXTCOLOR",     (0, 1), (-1, -1), colors.HexColor(C_DARK)),
        ]
        seg_tbl.setStyle(TableStyle(ts))
        elements.append(seg_tbl)

        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Found <b>{len(segments)}</b> distinct violence segment(s) "
            f"across <b>{len(violence_alerts)}</b> detected frames.",
            S["small"],
        ))
    else:
        elements.append(Paragraph(
            "✓  No violence was detected in this video.",
            _style("NV", "Normal", fontSize=10, textColor=colors.HexColor(C_GREEN),
                   fontName="Helvetica-Bold"),
        ))

    elements.append(Spacer(1, 8*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. OTHER INCIDENTS (weapons / fire / smoke)
    # ══════════════════════════════════════════════════════════════════════════
    other_alerts = [a for a in alert_history
                    if "violence" not in a.get("event_type", "").lower()]

    if other_alerts:
        elements.append(Paragraph("Other Detected Incidents", S["h2"]))
        elements.append(HRFlowable(width="100%", thickness=1,
                                   color=colors.HexColor(C_ORANGE), spaceAfter=4))

        oth_data = [["#", "Event Type", "Video Timestamp", "Confidence"]]
        for i, a in enumerate(other_alerts, 1):
            oth_data.append([
                str(i),
                a.get("event_type", ""),
                a.get("video_timestamp", ""),
                f"{a.get('confidence', 0):.1%}",
            ])
        oth_tbl = Table(oth_data, colWidths=[20, 120, 90, 70])
        ts2 = _header_style(C_ORANGE)
        ts2 += [
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor(C_GREY_LIGHT), colors.white]),
        ]
        oth_tbl.setStyle(TableStyle(ts2))
        elements.append(oth_tbl)
        elements.append(Spacer(1, 8*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. FULL DETECTION LOG (all alerts, paginated to 200)
    # ══════════════════════════════════════════════════════════════════════════
    if alert_history:
        elements.append(Paragraph("Full Detection Log", S["h2"]))
        elements.append(HRFlowable(width="100%", thickness=1,
                                   color=colors.HexColor(C_ACCENT), spaceAfter=4))

        log_data = [["#", "Event", "Video Time", "Confidence"]]
        for i, a in enumerate(alert_history[:200], 1):
            log_data.append([
                str(i),
                a.get("event_type", ""),
                a.get("video_timestamp", ""),
                f"{a.get('confidence', 0):.1%}",
            ])

        log_tbl = Table(log_data, colWidths=[20, 120, 90, 70])
        ts3 = _header_style(C_MID)

        # Alternating row backgrounds + highlight violence rows
        style_cmds = ts3[:]
        for row_i, a in enumerate(alert_history[:200], 1):
            bg = _severity_colour(a.get("event_type", ""))
            style_cmds.append(("BACKGROUND", (0, row_i), (-1, row_i), colors.HexColor(bg)))

        log_tbl.setStyle(TableStyle(style_cmds))
        elements.append(log_tbl)
        if len(alert_history) > 200:
            elements.append(Paragraph(
                f"(Showing first 200 of {len(alert_history)} total alerts)",
                S["small"],
            ))
        elements.append(Spacer(1, 8*mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 5. CAPTURED SNAPSHOTS
    # ══════════════════════════════════════════════════════════════════════════
    valid_snaps = [s for s in snapshots if os.path.exists(s)]
    if valid_snaps:
        elements.append(PageBreak())
        elements.append(Paragraph("Captured Snapshots", S["h2"]))
        elements.append(HRFlowable(width="100%", thickness=1,
                                   color=colors.HexColor(C_ACCENT), spaceAfter=6))
        elements.append(Paragraph(
            "The frames below were automatically captured at the moment each threat was detected.",
            S["small"],
        ))
        elements.append(Spacer(1, 4*mm))

        IMG_W = 4.6 * inch
        IMG_H = 3.45 * inch  # 4:3

        for i, snap_path in enumerate(valid_snaps[:30]):
            snap_name = Path(snap_path).stem   # e.g. "Violence_00-01-23"
            try:
                img = Image(snap_path, width=IMG_W, height=IMG_H)
                img.hAlign = "CENTER"
                caption_para = Paragraph(
                    f"<b>Snapshot {i+1}:</b> {snap_name.replace('_', '  ')}",
                    S["caption"],
                )
                block = KeepTogether([img, Spacer(1, 2*mm), caption_para, Spacer(1, 6*mm)])
                elements.append(block)
            except Exception as e:
                logger.warning("Failed to embed snapshot %s: %s", snap_path, e)

    # ── Footer ─────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5,
                               color=colors.HexColor(C_GREY_MID), spaceAfter=4))
    elements.append(Paragraph(
        f"Generated by AI Surveillance System  ·  {now_str}  ·  Job {job_id[:8]}",
        S["footer"],
    ))

    doc.build(elements)
    logger.info("Report generated: %s  (%d alerts, %d snapshots)", pdf_path, total_alerts, len(valid_snaps))
    return pdf_path
