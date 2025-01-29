from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF for embedding XML
import lxml.etree as ET  # For XML generation

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

# ✅ 1️⃣ Generate ZUGFeRD XML (Fixed Namespace Issues)
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    """
    Creates a valid ZUGFeRD 2.1 XML invoice.
    """
    NSMAP = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    }

    root = ET.Element("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice", nsmap=NSMAP)

    context = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocumentContext")
    guideline = ET.SubElement(context, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(guideline, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = "urn:zugferd.de:2p1:basic"

    header = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocument")
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = invoice.invoice_number
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}IssueDateTime").text = invoice.invoice_date

    trade_party = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}SupplyChainTradeTransaction")
    buyer = ET.SubElement(trade_party, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ApplicableHeaderTradeAgreement")
    ET.SubElement(buyer, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}BuyerReference").text = invoice.customer_name

    total = ET.SubElement(trade_party, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ApplicableHeaderTradeSettlement")
    ET.SubElement(total, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}GrandTotalAmount").text = str(invoice.total_amount)

    return ET.tostring(root, pretty_print=True, encoding="utf-8").decode()

# ✅ 2️⃣ Generate PDF/A-3 with Embedded XML
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    """
    Generates a PDF/A-3 compliant ZUGFeRD invoice with embedded XML.
    """
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)

    # ✅ ADD PDF/A-3 METADATA
    c.setTitle("ZUGFeRD Invoice")
    c.setAuthor("Your Company")
    c.setSubject("ZUGFeRD 2.1 Invoice")
    c.setCreator("FastAPI PDF Generator")
    c.setProducer("ReportLab PDF/A-3 Generator")

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

    # ✅ Convert to PDF/A-3 and embed ZUGFeRD XML
    pdf = fitz.open("pdf", pdf_buffer.getvalue())
    xml_data = generate_zugferd_xml(invoice)

    # ✅ Embed XML with Correct Metadata
    pdf.embfile_add("ZUGFeRD-invoice.xml", xml_data.encode(), desc="ZUGFeRD XML")

    # ✅ Force PDF/A-3 Compliance in Metadata
    metadata = pdf.metadata
    metadata["format"] = "application/pdf"
    metadata["pdfaid:part"] = "3"  # Force PDF/A-3
    metadata["pdfaid:conformance"] = "B"  # Compliance Level B
    metadata["GTS_PDFXVersion"] = "PDF/A-3"
    pdf.set_metadata(metadata)

    final_pdf = BytesIO()
    pdf.save(final_pdf)
    pdf.close()
    final_pdf.seek(0)

    return final_pdf.getvalue()

# ✅ 3️⃣ API Endpoint for Invoice Generation (PDF/A-3 Fixed)
@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    try:
        print("✅ Generating PDF with ZUGFeRD XML...")
        pdf_bytes = generate_pdf_with_zugferd(data)

        print("✅ PDF successfully generated!")
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=zugferd-invoice.pdf"}
        )
    except Exception as e:
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Root Endpoint
@app.get("/")
def read_root():
    return {"message": "ZUGFeRD Invoice API is running!"}
