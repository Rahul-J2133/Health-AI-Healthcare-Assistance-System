"""
routers/ehr.py — /generate-pdf endpoint.
Reads all live data from ./data/ before generating the EHR PDF.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from config import get_settings
from pdf.ehr_pdf_generator import create_ehr_pdf

router = APIRouter()


@router.get("/generate-pdf")
def generate_ehr(
    name: str = Query(...),
    age: str = Query(...),
    gender: str = Query(...),
):
    s = get_settings()
    os.makedirs(s.pdf_output_dir, exist_ok=True)

    pdf_path = Path(s.pdf_output_dir) / f"ehr_{uuid.uuid4().hex}.pdf"
    create_ehr_pdf(str(pdf_path), name=name, age=age, gender=gender)

    return FileResponse(
        path=str(pdf_path),
        filename=f"EHR_{name.replace(' ', '_')}.pdf",
        media_type="application/pdf",
    )