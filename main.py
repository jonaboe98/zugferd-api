from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF for embedding XML
import lxml.etree as ET  # For XML validation
import requests
import subprocess

app = FastAPI()

# ✅ Root Endpoint to Fix 404 Not Found
@app.get("/")
def read_root():
    return {"message": "ZUGFeRD Invoice API is running!"}

# ✅ Define invoice data structure
class Item(BaseModel):
    description: str
    price: float

class InvoiceData(BaseModel):
    customer_name: str
    vat_number: str  # EU VAT number
    country_code: str  # e.g., "DE", "FR", "ES"
    items: List[Item]
    total_amount: float
    invoice_number: str
    invoice_date: str

# ✅ 1️⃣ Validate VAT Number
def validate_vat_number(vat_number: str, country_code: str) -> bool:
    """
    Validates a VAT number using the EU VIES VAT API.
    """
    url = f"https://ec.europa.eu/taxation_customs/vies/vatService.do?ms={country_code}&vat={vat_number}"
    response = requests.get(url)
    
    return response.status_code == 200 and "valid" in response.text

# ✅ 2️⃣ Generate ZUGFeRD XML
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    root = ET.Element("Invoice")
    ET.SubElement(root, "InvoiceNumber").text = invoice.invoice_number
    ET.SubElement(root, "InvoiceDate").text = invoice.invoice_date
    ET.SubElement(root, "CustomerName").text = invoice.customer_name

    items_element = ET.SubElement(root, "Items")
    for item in invoice.items:
        item_element = ET.SubElement(items_element, "Item")
        ET.SubElement(item_element, "Description").text = item.description
        ET.SubElement(item_element, "Price").text = str(item.price)

    ET.SubElement(root, "TotalAmount").text = str(invoice.total_amount)
    return ET.tostring(root, pretty_print=True, encoding="utf-8").decode()

# ✅ 3️⃣ Validate XML with Official ZUGFeRD Schema
def validate_zugferd_xml(xml_string: str) -> bool:
    SCHEMA_FILE = "zugferd_2p1.xsd"  # Download this file from the official ZUGFeRD site
    schema = ET.XMLSchema(ET.parse(SCHEMA_FILE))
    xml_doc = ET.fromstring(xml_string.encode("utf-8"))
    return schema.validate(xml_doc)

# ✅ 4️⃣ Generate PDF with Embedded XML
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, 800, "Invoice")
    c.setFont("Helvetica", 12)
    c.drawString(100, 770, f"Invoice Number: {invoice.invoice_number}")
    c.drawString(100, 750, f"Invoice Date: {invoice.invoice_date}")
    c.drawString(100, 730, f"Customer Name: {invoice.customer_name}")

    y = 700
    for item in invoice.items:
        c.drawString(100, y, f"{item.description}: ${item.price:.2f}")
        y -= 20

    c.drawString(100, y - 20, f"Total: ${invoice.total_amount:.2f}")
    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    pdf = fitz.open("pdf", pdf_buffer.getvalue())
    xml_data = generate_zugferd_xml(invoice)
    pdf.embfile_add("ZUGFeRD-invoice.xml", xml_data.encode(), desc="ZUGFeRD XML")
    
    final_pdf = BytesIO()
    pdf.save(final_pdf)
    pdf.close()
    final_pdf.seek(0)

    return final_pdf.getvalue()

# ✅ 5️⃣ Validate PDF/A-3 with VeraPDF
def validate_pdfa3(pdf_bytes: bytes) -> bool:
    with open("temp_invoice.pdf", "wb") as f:
        f.write(pdf_bytes)
    result = subprocess.run(["verapdf", "temp_invoice.pdf"], capture_output=True, text=True)
    return "Passed" in result.stdout

# ✅ 6️⃣ API Endpoint for Compliance Checking & Invoice Generation
@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    # VAT Validation
    if not validate_vat_number(data.vat_number, data.country_code):
        raise HTTPException(status_code=400, detail="❌ Invalid VAT number")

    # ZUGFeRD XML Validation
    xml_data = generate_zugferd_xml(data)
    if not validate_zugferd_xml(xml_data):
        raise HTTPException(status_code=400, detail="❌ Invalid ZUGFeRD XML")

    # PDF Generation & PDF/A-3 Validation
    pdf_bytes = generate_pdf_with_zugferd(data)
    if not validate_pdfa3(pdf_bytes):
        raise HTTPException(status_code=400, detail="❌ PDF is NOT PDF/A-3 compliant")

    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=validated-invoice.pdf"}
    )
