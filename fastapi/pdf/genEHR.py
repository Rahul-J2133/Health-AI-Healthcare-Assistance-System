"""
pdf/genEHR.py — Fetch images from ImageKit and sensor data from ThingSpeak,
merge them by nearest timestamp, and render a full EHR PDF.

FIXES applied:
  1. fetch_images(): imagekit.list_files() returns an SDK response object,
     not a plain dict. Changed response.get('response', []) to
     getattr(response, 'list', []) which is the correct attribute name.
  2. merge_data(): replaced exact timestamp equality matching with a
     nearest-neighbour match within a ±5 minute tolerance window, since
     ImageKit filenames and ThingSpeak entries are generated independently
     and will almost never share an exact timestamp.
  3. ImageKit is now initialised via the shared singleton in
     services/imagekit_client.py (all three keys present).
"""
from datetime import datetime, timedelta
import requests
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

from config import get_settings
from services.imagekit_client import get_imagekit

ECG_FOLDER = "/ecg_plots/"
XRAY_FOLDER = "/xray_plots/"
ECG_PREFIX = "ecg_plot_"
XRAY_PREFIX = "approved_xray_"
TIMESTAMP_MATCH_TOLERANCE = timedelta(minutes=5)


# ── Image fetching ─────────────────────────────────────────────────────────

def fetch_images(folder_path: str, prefix: str) -> list[dict]:
    """
    List files in an ImageKit folder and parse timestamps from filenames.

    FIX: The original code called response.get('response', []) on the SDK
    response object, which always returned [] because SDK responses are
    objects, not dicts. The correct attribute is response.list.
    """
    imagekit = get_imagekit()
    response = imagekit.list_files({
        "path": folder_path,
        "sort": "ASC_CREATED",
    })

    # FIX: use getattr to safely access the .list attribute
    files = getattr(response, "list", []) or []
    images = []

    for file in files:
        name = getattr(file, "name", "")
        if not name.startswith(prefix):
            continue
        timestamp_str = name.replace(prefix, "").split(".")[0]
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            images.append({
                "url": getattr(file, "url", ""),
                "timestamp": timestamp,
            })
        except ValueError:
            continue

    return images


# ── Sensor data fetching ───────────────────────────────────────────────────

def fetch_sensor_data() -> list[dict]:
    """Fetch the latest 100 readings from ThingSpeak."""
    s = get_settings()
    url = f"https://api.thingspeak.com/channels/{s.thingspeak_channel_id}/feeds.json"
    params = {"api_key": s.thingspeak_read_api_key, "results": 100}
    response = requests.get(url, params=params)
    response.raise_for_status()

    data = []
    for feed in response.json().get("feeds", []):
        try:
            timestamp = datetime.strptime(feed["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            data.append({
                "timestamp": timestamp,
                "body_temperature": feed.get("field1"),
                "humidity": feed.get("field2"),
                "room_temperature": feed.get("field3"),
                "spo2": feed.get("field4"),
                "beats_per_minute": feed.get("field5"),
            })
        except (TypeError, ValueError):
            continue

    return data


# ── Merge ──────────────────────────────────────────────────────────────────

def _nearest(images: list[dict], target: datetime):
    """
    FIX: Return the image entry whose timestamp is closest to `target`
    within TIMESTAMP_MATCH_TOLERANCE, or None if nothing qualifies.
    The original used exact equality (==) which never matched in practice.
    """
    candidates = [
        img for img in images
        if abs(img["timestamp"] - target) <= TIMESTAMP_MATCH_TOLERANCE
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda img: abs(img["timestamp"] - target))


def merge_data(ecg_images: list, xray_images: list, sensor_data: list) -> list[dict]:
    combined = []
    for reading in sensor_data:
        ts = reading["timestamp"]
        ecg = _nearest(ecg_images, ts)
        xray = _nearest(xray_images, ts)
        combined.append({
            "timestamp": ts,
            "ecg_image": ecg["url"] if ecg else None,
            "xray_image": xray["url"] if xray else None,
            "sensor_data": reading,
        })
    return combined


# ── PDF generation ─────────────────────────────────────────────────────────

def create_ehr_pdf(
    file_name: str,
    entries: list[dict],
    name: str = "John Doe",
    age: str = "45",
    gender: str = "Male",
) -> None:
    doc = SimpleDocTemplate(
        file_name, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=50,
    )
    styles = getSampleStyleSheet()
    content = []

    title_style = ParagraphStyle(
        "EHRTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        textColor=colors.HexColor("#333333"),
        alignment=1,
        spaceAfter=20,
    )
    content.append(Paragraph("Electronic Health Record", title_style))

    patient_data = [
        ["Patient Name:", name],
        ["Age:", age],
        ["Gender:", gender],
        ["Medical Record No:", "12345"],
    ]
    pt = Table(patient_data, colWidths=[120, 300])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    content.append(pt)
    content.append(Spacer(1, 12))

    for idx, entry in enumerate(entries):
        content.append(Spacer(1, 20))
        ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        content.append(Paragraph(f"<b>Recorded At:</b> {ts}", styles["Normal"]))
        content.append(Spacer(1, 10))

        if entry.get("ecg_image"):
            content.append(Paragraph("<b>ECG Reading:</b>", styles["Normal"]))
            content.append(Image(entry["ecg_image"], width=400, height=200))
            content.append(Spacer(1, 10))

        if entry.get("xray_image"):
            content.append(Paragraph("<b>Radiology Scan (X-Ray):</b>", styles["Normal"]))
            content.append(Image(entry["xray_image"], width=400, height=300))
            content.append(Spacer(1, 10))

        sensor = entry["sensor_data"]
        sensor_rows = [
            ["Body Temperature", f"{sensor.get('body_temperature', 'N/A')} °C"],
            ["Humidity", f"{sensor.get('humidity', 'N/A')} %"],
            ["Room Temperature", f"{sensor.get('room_temperature', 'N/A')} °C"],
            ["SpO2", f"{sensor.get('spo2', 'N/A')} %"],
            ["Beats Per Minute", f"{sensor.get('beats_per_minute', 'N/A')} BPM"],
        ]
        st = Table(sensor_rows, colWidths=[140, 280])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        content.append(st)

        if (idx + 1) % 3 == 0:
            content.append(PageBreak())

    doc.build(content)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ecg_images = fetch_images(ECG_FOLDER, ECG_PREFIX)
    xray_images = fetch_images(XRAY_FOLDER, XRAY_PREFIX)
    sensor_data = fetch_sensor_data()
    entries = merge_data(ecg_images, xray_images, sensor_data)
    create_ehr_pdf("ehr_report_final.pdf", entries, name="Alice Smith", age="30", gender="Female")
    print("EHR PDF generated: ehr_report_final.pdf")
