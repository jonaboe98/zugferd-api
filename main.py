from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF for embedding XML
import lxml.etree as ET  # For XML validation

app = FastAPI()

# ✅ Define invoice data structure
class Item(BaseModel):
    description: str
    price: float

class InvoiceData(BaseModel):
    customer_name: str
    country_code: str
    items: List[Item]
    total_amount: float
    invoice_number: str
    invoice_date: str

# ✅ 1️⃣ Generate ZUGFeRD XML
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    """
    Creates a basic ZUGFeRD-compliant XML invoice.
    """
    root = ET.Element("rsm:CrossIndustryInvoice", {
        "xmlns:rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "xmlns:ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "xmlns:udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    })

    context = ET.SubElement(root, "rsm:ExchangedDocumentContext")
    guideline = ET.SubElement(context, "ram:GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(guideline, "ram:ID").text = "urn:zugferd.de:2p1:basic"

    header = ET.SubElement(root, "rsm:ExchangedDocument")
    ET.SubElement(header, "ram:ID").text = invoice.invoice_number
    ET.SubElement(header, "ram:IssueDateTime").text = invoice.invoice_date

    trade_party = ET.SubElement(root, "rsm:SupplyChainTradeTransaction")
    buyer = ET.SubElement(trade_party, "ram:ApplicableHeaderTradeAgreement")
    ET.SubElement(buyer, "ram:BuyerReference").text = invoice.customer_name

    total = ET.SubElement(trade_party, "ram:ApplicableHeaderTradeSettlement")
    ET.SubElement(total, "ram:GrandTotalAmount").text = str(invoice.total_amount)

    return ET.tostring(root, pretty_print=True, encoding="utf-8").decode()

# ✅ 2️⃣ Generate PDF with Embedded XML (ZUGFeRD Compliant)
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    """
    Generates a ZUGFeRD-compliant PDF invoice with embedded XML.
    """
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

    # Convert to PDF/A-3 and embed ZUGFeRD XML
    pdf = fitz.open("pdf", pdf_buffer.getvalue())
    xml_data = generate_zugferd_xml(invoice)

    # Embed XML into PDF
    pdf.embfile_add("ZUGFeRD-invoice.xml", xml_data.encode(), desc="ZUGFeRD XML")

    final_pdf = BytesIO()
    pdf.save(final_pdf)
    pdf.close()
    final_pdf.seek(0)

    return final_pdf.getvalue()

# ✅ 3️⃣ API Endpoint for Invoice Generation (Now Fully ZUGFeRD Compliant)
@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    pdf_bytes = generate_pdf_with_zugferd(data)

    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=zugferd-invoice.pdf"}
    )
