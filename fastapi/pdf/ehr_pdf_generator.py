"""
pdf/ehr_pdf_generator.py — Professional Medical EHR PDF Generator.

Reads all live data from ./data/:
  - firstREC.txt  → latest vitals
  - secondREC.txt → patient notes / clinical history
  - ecg_data.json → ECG waveform (rendered as chart)
  - approved_xray_*.jpg → X-ray images (most recent)
"""
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

DATA_DIR = "./data"

# ── Colour palette ─────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#0D2B55")
TEAL      = colors.HexColor("#0E9F8A")
LIGHT_BLUE= colors.HexColor("#E8F4FD")
LIGHT_GREY= colors.HexColor("#F5F7FA")
MID_GREY  = colors.HexColor("#8FA3BC")
DARK_GREY = colors.HexColor("#333333")
RED       = colors.HexColor("#E53935")
WHITE     = colors.white
PAGE_W, PAGE_H = A4


# ── Header / Footer ────────────────────────────────────────────────────────

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = PAGE_W, PAGE_H

    # Top navy bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)

    # Logo text
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(15*mm, h - 12*mm, "HealthAI")
    canvas.setFont("Helvetica", 8)
    canvas.drawString(15*mm, h - 16*mm, "Electronic Health Record System")

    # Record label right side
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawRightString(w - 15*mm, h - 11*mm, "CONFIDENTIAL MEDICAL RECORD")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 15*mm, h - 15*mm, f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M')}")

    # Teal accent line under header
    canvas.setFillColor(TEAL)
    canvas.rect(0, h - 19*mm, w, 1*mm, fill=1, stroke=0)

    # Bottom footer
    canvas.setFillColor(LIGHT_GREY)
    canvas.rect(0, 0, w, 12*mm, fill=1, stroke=0)
    canvas.setFillColor(MID_GREY)
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.drawCentredString(w / 2, 4*mm, "This record is system-generated for clinical reference only. Not a substitute for professional medical advice.")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 15*mm, 4*mm, f"Page {doc.page}")
    canvas.drawString(15*mm, 4*mm, "HealthAI Medical RAG System")

    canvas.restoreState()


# ── Data readers ───────────────────────────────────────────────────────────

def _read_vitals() -> dict:
    path = os.path.join(DATA_DIR, "firstREC.txt")
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, "r") as f:
        for line in f:
            if ":" in line:
                key, _, val = line.strip().partition(":")
                key = key.strip().lower().replace(" ", "_")
                numeric = val.strip().split(" ")[0]
                try:
                    result[key] = float(numeric)
                except ValueError:
                    result[key] = val.strip()
    return result


def _read_notes() -> list[dict]:
    path = os.path.join(DATA_DIR, "secondREC.txt")
    if not os.path.exists(path):
        return []
    notes = []
    current = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATE:"):
                if current:
                    notes.append(current)
                current = {"date": line.replace("DATE:", "").strip()}
            elif line.startswith("TIME:"):
                current["time"] = line.replace("TIME:", "").strip()
            elif line.startswith("ADDED INFORMATION:"):
                current["info"] = line.replace("ADDED INFORMATION:", "").strip()
    if current and "info" in current:
        notes.append(current)
    return notes


def _read_ecg() -> list[float]:
    path = os.path.join(DATA_DIR, "ecg_data.json")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f).get("ecg", [])


def _find_xrays() -> list[str]:
    if not os.path.exists(DATA_DIR):
        return []
    files = sorted(
        [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.startswith("approved_xray_") and f.endswith(".jpg")],
        reverse=True  # most recent first
    )
    return files[:3]  # max 3 X-rays


def _ecg_to_image(ecg: list[float]) -> io.BytesIO | None:
    if not ecg:
        return None
    fig, ax = plt.subplots(figsize=(10, 2.5))
    ax.plot(ecg, color="#E53935", linewidth=0.8)
    ax.set_facecolor("#FAFAFA")
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_xlabel("Samples", fontsize=8, color="#666")
    ax.set_ylabel("Amplitude", fontsize=8, color="#666")
    ax.tick_params(colors="#888", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDD")
    ax.spines["bottom"].set_color("#DDD")
    ax.grid(True, color="#EEE", linewidth=0.5)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Style helpers ──────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    return {
        "section_title": ParagraphStyle("ST", fontName="Helvetica-Bold", fontSize=11,
            textColor=WHITE, spaceAfter=0, spaceBefore=0, leftIndent=4),
        "field_label": ParagraphStyle("FL", fontName="Helvetica-Bold", fontSize=9,
            textColor=DARK_GREY, spaceAfter=2),
        "field_value": ParagraphStyle("FV", fontName="Helvetica", fontSize=9,
            textColor=DARK_GREY, spaceAfter=4),
        "note_date": ParagraphStyle("ND", fontName="Helvetica-Bold", fontSize=8,
            textColor=TEAL, spaceAfter=2),
        "note_text": ParagraphStyle("NT", fontName="Helvetica", fontSize=9,
            textColor=DARK_GREY, spaceAfter=6, leftIndent=8),
        "caption": ParagraphStyle("CAP", fontName="Helvetica-Oblique", fontSize=8,
            textColor=MID_GREY, alignment=TA_CENTER, spaceAfter=4),
        "normal": base["Normal"],
        "alert_normal": ParagraphStyle("AN", fontName="Helvetica", fontSize=9,
            textColor=DARK_GREY, spaceAfter=2),
    }


def _section_header(title: str, st) -> Table:
    """Navy background section header bar."""
    t = Table([[Paragraph(title, st["section_title"])]], colWidths=[PAGE_W - 30*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return t


def _vital_card(label: str, value: str, unit: str, normal_range: str, is_abnormal: bool, st) -> Table:
    colour = RED if is_abnormal else TEAL
    data = [
        [Paragraph(label, ParagraphStyle("VL", fontName="Helvetica", fontSize=7, textColor=MID_GREY))],
        [Paragraph(f"<font size=14 color='#{colour.hexval()[2:]}'><b>{value}</b></font> <font size=8 color='#888'>{unit}</font>", st["normal"])],
        [Paragraph(f"Normal: {normal_range}", ParagraphStyle("VN", fontName="Helvetica", fontSize=7, textColor=MID_GREY))],
    ]
    t = Table(data, colWidths=[38*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GREY),
        ("BOX",           (0, 0), (-1, -1), 0.5, colour),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LINEABOVE",     (0, 0), (-1, 0), 2, colour),
    ]))
    return t


# ── Main builder ───────────────────────────────────────────────────────────

def create_ehr_pdf(
    file_name: str,
    name: str = "Unknown",
    age: str = "—",
    gender: str = "—",
) -> None:

    st = _styles()
    vitals = _read_vitals()
    notes  = _read_notes()
    ecg    = _read_ecg()
    xrays  = _find_xrays()
    record_id = f"HR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ── Document setup ─────────────────────────────────────────────────────
    doc = BaseDocTemplate(
        file_name, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=24*mm, bottomMargin=18*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_header_footer)])

    content = []

    # ── Patient banner ─────────────────────────────────────────────────────
    banner_data = [[
        Paragraph(f"<font color='white'><b>{name}</b></font>", ParagraphStyle("BN", fontName="Helvetica-Bold", fontSize=16, textColor=WHITE)),
        Paragraph(
            f"<font color='white'><b>Age:</b> {age} &nbsp;&nbsp; <b>Gender:</b> {gender.title()} &nbsp;&nbsp; <b>Record No:</b> {record_id}</font>",
            ParagraphStyle("BI", fontName="Helvetica", fontSize=9, textColor=WHITE, alignment=TA_RIGHT)
        ),
    ]]
    banner = Table(banner_data, colWidths=[doc.width * 0.5, doc.width * 0.5])
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    content.append(banner)

    # Teal accent line
    accent = Table([[""]], colWidths=[doc.width])
    accent.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    content.append(accent)
    content.append(Spacer(1, 6*mm))

    # ── Section 1: Current Vitals ──────────────────────────────────────────
    content.append(_section_header("📊  Current Vitals", st))
    content.append(Spacer(1, 3*mm))

    def v(key, default="—"):
        val = vitals.get(key, default)
        return f"{val:.1f}" if isinstance(val, float) else str(val)

    def abnormal(key, lo, hi):
        val = vitals.get(key)
        return isinstance(val, float) and (val < lo or val > hi)

    vital_cards = [
        _vital_card("Body Temperature", v("body_temperature"), "°C",  "36.1–37.2°C",  abnormal("body_temperature", 36.1, 37.5), st),
        _vital_card("Heart Rate",       v("average_beats_per_minute"), "BPM", "60–100 BPM",   abnormal("average_beats_per_minute", 60, 100), st),
        _vital_card("SpO₂",            v("spo2_level"),         "%",   "95–100%",      abnormal("spo2_level", 95, 100), st),
        _vital_card("Humidity",         v("humidity"),           "%",   "30–70%",       abnormal("humidity", 30, 70), st),
        _vital_card("Room Temperature", v("room_temperature"),   "°C",  "18–26°C",      abnormal("room_temperature", 18, 26), st),
    ]
    cards_table = Table([vital_cards], colWidths=[40*mm] * 5, hAlign="LEFT")
    cards_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    content.append(cards_table)

    # Vitals recorded time
    recorded = f"{vitals.get('date', '')}  {vitals.get('time', '')}".strip()
    if recorded.strip():
        content.append(Spacer(1, 2*mm))
        content.append(Paragraph(f"<i>Last recorded: {recorded}</i>", ParagraphStyle("RC", fontName="Helvetica-Oblique", fontSize=7, textColor=MID_GREY)))

    content.append(Spacer(1, 5*mm))

    # ── Section 2: ECG ────────────────────────────────────────────────────
    content.append(_section_header("💓  Electrocardiogram (ECG)", st))
    content.append(Spacer(1, 3*mm))

    ecg_buf = _ecg_to_image(ecg)
    if ecg_buf:
        content.append(Image(ecg_buf, width=doc.width, height=55*mm))
        content.append(Paragraph("ECG waveform — AD8232 sensor reading", st["caption"]))
    else:
        content.append(Paragraph("No ECG data recorded.", st["field_value"]))

    content.append(Spacer(1, 5*mm))

    # ── Section 3: Radiology ──────────────────────────────────────────────
    content.append(_section_header("🩻  Radiology — Chest X-Ray", st))
    content.append(Spacer(1, 3*mm))

    if xrays:
        for xray_path in xrays:
            fname = os.path.basename(xray_path)
            ts_raw = fname.replace("approved_xray_", "").replace(".jpg", "")
            try:
                ts = datetime.strptime(ts_raw, "%Y%m%d_%H%M%S").strftime("%d %b %Y  %H:%M:%S")
            except Exception:
                ts = ts_raw
            content.append(Image(xray_path, width=doc.width * 0.6, height=70*mm, hAlign="CENTER"))
            content.append(Paragraph(f"Chest X-Ray — {ts} | AI Analysis: Pneumonia Detection Applied", st["caption"]))
            content.append(Spacer(1, 3*mm))
    else:
        content.append(Paragraph("No X-ray images on record.", st["field_value"]))

    content.append(Spacer(1, 5*mm))

    # ── Section 4: Clinical Notes ──────────────────────────────────────────
    content.append(_section_header("📝  Clinical Notes & Patient History", st))
    content.append(Spacer(1, 3*mm))

    if notes:
        for note in notes:
            date_str = f"{note.get('date', '')}  {note.get('time', '')}".strip()
            content.append(Paragraph(date_str, st["note_date"]))
            content.append(Paragraph(note.get("info", ""), st["note_text"]))
            # Divider
            div = Table([[""]], colWidths=[doc.width])
            div.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")), ("TOPPADDING", (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 3)]))
            content.append(div)
    else:
        content.append(Paragraph("No clinical notes recorded.", st["field_value"]))

    content.append(Spacer(1, 5*mm))

    # ── Section 5: Summary & Disclaimer ───────────────────────────────────
    content.append(_section_header("⚕️  Clinical Summary", st))
    content.append(Spacer(1, 3*mm))

    # Abnormal vitals summary
    abnormal_items = []
    checks = [
        ("body_temperature", 36.1, 37.5, "Body Temperature", "°C"),
        ("average_beats_per_minute", 60, 100, "Heart Rate", "BPM"),
        ("spo2_level", 95, 100, "SpO₂", "%"),
    ]
    for key, lo, hi, label, unit in checks:
        val = vitals.get(key)
        if isinstance(val, float) and (val < lo or val > hi):
            status = "LOW" if val < lo else "HIGH"
            abnormal_items.append(f"⚠ {label}: {val:.1f} {unit} ({status})")

    if abnormal_items:
        content.append(Paragraph("<b>Abnormal Values Detected:</b>", st["field_label"]))
        for item in abnormal_items:
            content.append(Paragraph(item, ParagraphStyle("AI", fontName="Helvetica", fontSize=9, textColor=RED, leftIndent=8, spaceAfter=3)))
        content.append(Spacer(1, 3*mm))
    else:
        content.append(Paragraph("✓ All recorded vitals are within normal reference ranges.", ParagraphStyle("OK", fontName="Helvetica", fontSize=9, textColor=TEAL, spaceAfter=4)))

    # Disclaimer box
    disclaimer_data = [[Paragraph(
        "<b>DISCLAIMER</b>  This Electronic Health Record is automatically generated by the HealthAI system "
        "based on IoT sensor readings and AI analysis. It is intended for informational and reference purposes "
        "only. This document does not constitute a formal medical diagnosis and must not replace the assessment "
        "of a qualified healthcare professional. All clinical decisions should be made by licensed practitioners.",
        ParagraphStyle("DIS", fontName="Helvetica", fontSize=8, textColor=DARK_GREY, leading=12)
    )]]
    disc_table = Table(disclaimer_data, colWidths=[doc.width])
    disc_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BLUE),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#B8D4EC")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    content.append(disc_table)

    # ── Build ──────────────────────────────────────────────────────────────
    doc.build(content)
    print(f"[EHR] PDF generated: {file_name}")