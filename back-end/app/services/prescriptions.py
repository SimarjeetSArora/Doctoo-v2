"""Prescription numbers, the clinic's medicine list, and the prescription PDF."""

from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Clinic, Medicine, Patient, User, Visit
from app.services.auth import utcnow

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"

VITAL_LABELS = [
    ("bp", "BP"),
    ("pulse", "Pulse"),
    ("temperature_f", "Temp"),
    ("spo2", "SpO2"),
    ("respiratory_rate", "RR"),
    ("blood_sugar", "Sugar"),
    ("weight_kg", "Weight"),
    ("height_cm", "Height"),
]
UNITS = {
    "pulse": "/min",
    "temperature_f": " °F",
    "spo2": "%",
    "respiratory_rate": "/min",
    "blood_sugar": " mg/dL",
    "weight_kg": " kg",
    "height_cm": " cm",
}


def prescription_label(visit: Visit) -> str | None:
    """RX-2026-00042 (year the prescription was finished)."""
    if visit.prescription_number is None or visit.completed_at is None:
        return None
    return f"RX-{visit.completed_at.year}-{visit.prescription_number:05d}"


async def next_prescription_number(db: AsyncSession, clinic_id) -> int:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"rx:{clinic_id}"))))
    current = await db.scalar(
        select(func.max(Visit.prescription_number)).where(Visit.clinic_id == clinic_id)
    )
    return (current or 0) + 1


def medicine_key(name: str) -> str:
    return " ".join(name.lower().split())


async def remember_medicines(db: AsyncSession, clinic_id, names: list[str]) -> None:
    """Adds prescribed medicines to the clinic's suggestion list (or bumps their count)."""
    now = utcnow()
    for name in {medicine_key(n): " ".join(n.split()) for n in names}.items():
        key, display = name
        stmt = insert(Medicine).values(
            clinic_id=clinic_id, name=display, name_key=key, times_used=1, last_used_at=now
        )
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["clinic_id", "name_key"],
                set_={"times_used": Medicine.times_used + 1, "last_used_at": now},
            )
        )


def vitals_line(vitals: dict) -> str:
    parts = []
    if vitals.get("bp_systolic") and vitals.get("bp_diastolic"):
        vitals = {**vitals, "bp": f"{vitals['bp_systolic']}/{vitals['bp_diastolic']} mmHg"}
    for key, label in VITAL_LABELS:
        value = vitals.get(key)
        if value is None:
            continue
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        parts.append(f"{label}: {value}{UNITS.get(key, '')}")
    return "   ·   ".join(parts)


class _Pdf(FPDF):
    footer_text = ""

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("DejaVu", size=7)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, self.footer_text, align="L")
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="R")


def render_prescription_pdf(
    visit: Visit, patient: Patient, doctor: User, clinic: Clinic, zone: ZoneInfo, age: int | None
) -> bytes:
    pdf = _Pdf(format="A4")
    pdf.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
    # Names and notes in Hindi/Marathi (Devanagari) or Punjabi (Gurmukhi) use Noto fonts, with
    # text shaping so letters join correctly.
    for family, file in (("NotoDeva", "NotoSansDevanagari"), ("NotoGuru", "NotoSansGurmukhi")):
        pdf.add_font(family, "", str(FONTS / f"{file}-Regular.ttf"))
        pdf.add_font(family, "B", str(FONTS / f"{file}-Bold.ttf"))
    pdf.set_fallback_fonts(["NotoDeva", "NotoGuru"], exact_match=False)
    pdf.set_text_shaping(True)
    pdf.set_margins(16, 14, 16)
    pdf.set_auto_page_break(True, margin=20)
    pdf.footer_text = "Generated with Doctoo · This is a computer-generated prescription."
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    dark, grey = (20, 20, 20), (110, 110, 110)

    # ---- Letterhead ----
    pdf.set_text_color(*dark)
    pdf.set_font("DejaVu", "B", 17)
    pdf.cell(width * 0.6, 8, clinic.name, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(width * 0.4, 8, doctor.full_name, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", size=8.5)
    pdf.set_text_color(*grey)
    address = ", ".join(p for p in (clinic.address, clinic.city, clinic.state, clinic.pincode) if p)
    contact = "   ".join(p for p in (clinic.phone, clinic.email) if p)
    for line in (address, contact, f"GSTIN: {clinic.gstin}" if clinic.gstin else ""):
        if line:
            pdf.cell(width, 4.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_draw_color(30, 30, 30)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)

    # ---- Patient and prescription details ----
    finished = visit.completed_at or utcnow()
    local = finished.astimezone(zone)
    age_gender = ", ".join(
        p for p in (f"{age} y" if age is not None else "", (patient.gender or "").title()) if p
    )
    pdf.set_text_color(*dark)

    def labelled(label: str, value: str, cell_width: float, bold: bool = False) -> None:
        pdf.set_font("DejaVu", size=8)
        pdf.set_text_color(*grey)
        pdf.cell(16, 6, label)
        pdf.set_font("DejaVu", "B" if bold else "", 9.5)
        pdf.set_text_color(*dark)
        pdf.cell(cell_width - 16, 6, value)

    # Patient on its own line (names can be long), then mobile / date / prescription number.
    pdf.set_font("DejaVu", size=8)
    pdf.set_text_color(*grey)
    pdf.cell(16, 6, "Patient")
    pdf.set_font("DejaVu", "B", 10.5)
    pdf.set_text_color(*dark)
    pdf.multi_cell(
        width - 16,
        6,
        patient.full_name + (f"   ({age_gender})" if age_gender else ""),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    third = width / 3
    labelled("Mobile", patient.phone, third)
    labelled("Date", local.strftime("%d %b %Y, %I:%M %p").replace(" 0", " "), third + 8)
    labelled("Rx no.", prescription_label(visit) or "Draft", third - 8)
    pdf.ln(7)
    if patient.notes:
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(170, 60, 0)
        pdf.multi_cell(width, 4.5, f"Alerts: {patient.notes}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*dark)
    vitals = vitals_line(visit.vitals or {})
    if vitals:
        pdf.ln(1)
        pdf.set_font("DejaVu", size=8.5)
        pdf.multi_cell(width, 4.5, vitals, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    def section(title: str, text: str | None) -> None:
        if not text:
            return
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.set_text_color(*dark)
        pdf.cell(width, 5.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", size=9.5)
        pdf.multi_cell(width, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1.5)

    section("Complaints", visit.complaints)
    section("Examination", visit.examination)
    section("Diagnosis", visit.diagnosis)

    # ---- Medicines ----
    if visit.items:
        pdf.ln(1)
        pdf.set_font("DejaVu", "B", 18)
        pdf.cell(width, 9, "℞", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", size=9)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        with pdf.table(
            col_widths=(6, 40, 16, 18, 14, 30),
            text_align=("RIGHT", "LEFT", "CENTER", "LEFT", "LEFT", "LEFT"),
            line_height=5.5,
            first_row_as_headings=True,
            headings_style=FontFace(emphasis="BOLD", fill_color=(242, 242, 242)),
            borders_layout="HORIZONTAL_LINES",
            padding=1.5,
        ) as table:
            header = table.row()
            for heading in ("#", "Medicine", "Dose (M-A-N)", "When", "Duration", "Instructions"):
                header.cell(heading)
            for number, item in enumerate(visit.items, start=1):
                row = table.row()
                row.cell(str(number))
                row.cell(item.medicine)
                row.cell(item.dose)
                row.cell(item.timing or "")
                row.cell(item.duration or "")
                row.cell(item.instructions or "")
        pdf.ln(3)

    section("Advice", visit.advice)
    if visit.follow_up_date:
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.cell(
            width,
            6,
            f"Follow-up on {visit.follow_up_date.strftime('%a, %d %b %Y')}",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    # ---- Signature ----
    pdf.ln(12)
    pdf.set_x(pdf.w - pdf.r_margin - 60)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_line_width(0.2)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9.5)
    pdf.cell(60, 6, doctor.full_name, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def pdf_filename(visit: Visit, patient: Patient) -> str:
    label = prescription_label(visit) or "prescription-draft"
    name = "-".join(patient.full_name.split()).lower()
    return f"{label}-{name}.pdf"


def content_disposition(kind: str, filename: str) -> str:
    """Download header that also works for non-English file names (RFC 6266 / 5987)."""
    ascii_name = filename.encode("ascii", "ignore").decode().replace("-.pdf", ".pdf") or "file.pdf"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
