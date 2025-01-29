from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF
import lxml.etree as ET

app = FastAPI()

# Example Pydantic models
class Item(BaseModel):
    description: str
    price: float
    quantity: float = 1.0

class InvoiceData(BaseModel):
    # ...
    invoice_number: str
    invoice_date: str
    due_date: str
    items: List[Item]
    total_amount: float
    tax_amount: float
    # etc...

def generate_zugferd_xml(invoice: InvoiceData) -> str:
    # ... Build XML ...
    return some_xml_string

def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    # 1) Create a PDF in memory with ReportLab
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    c.drawString(72, 800, f"Invoice No. {invoice.invoice_number}")
    # add lines, totals, etc.
    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    # 2) Open with PyMuPDF
    pdf_doc = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")

    # 3) Generate ZUGFeRD XML bytes
    xml_data = generate_zugferd_xml(invoice).encode("utf-8")

    # 4) Embed (NO 'uf' arg!)
    pdf_doc.embfile_add(
        "ZUGFeRD-invoice.xml",
        xml_data,
        afrelationship="Data",
        desc="ZUGFeRD 2.1 Basic Invoice",
        mime="text/xml"
    )

    # 5) Set metadata
    pdf_doc.set_metadata({
        "title": f"Invoice {invoice.invoice_number}",
        "author": "Your Company",
        "creator": "Your Company",
        "subject": f"Invoice {invoice.invoice_number}",
        "keywords": "ZUGFeRD, Invoice, PDF/A-3"
    })

    # 6) Load ICC profile
    with open("sRGB.icc", "rb") as f:
        icc_profile = f.read()

    # 7) Save as PDF/A-3
    final_pdf = BytesIO()
    pdf_doc.save(
        final_pdf,
        incremental=False,
        deflate=True,
        pdfa=fitz.PDF_A_3B,
        icc_profile=icc_profile
    )
    pdf_doc.close()
    final_pdf.seek(0)

    return final_pdf.getvalue()

@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    try:
        # Validate tax, etc.
        pdf_bytes = generate_pdf_with_zugferd(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{data.invoice_number}.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "OK", "standard": "ZUGFeRD 2.1 Basic"}
