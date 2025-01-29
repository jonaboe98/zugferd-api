from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF
import lxml.etree as ET

app = FastAPI()

# ✅ Invoice Data Models
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

# ✅ ZUGFeRD XML Generator
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    NSMAP = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    }

    root = ET.Element("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice", nsmap=NSMAP)

    # Document Context
    context = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocumentContext")
    guideline = ET.SubElement(context, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(guideline, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = "urn:zugferd.de:2p1:basic"

    # Header Information
    header = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocument")
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = invoice.invoice_number
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}IssueDateTime").text = invoice.invoice_date

    # Trade Party Details
    trade_party = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}SupplyChainTradeTransaction")
    buyer = ET.SubElement(trade_party, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ApplicableHeaderTradeAgreement")
    ET.SubElement(buyer, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}BuyerReference").text = invoice.customer_name

    # Payment Total
    total = ET.SubElement(trade_party, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ApplicableHeaderTradeSettlement")
    ET.SubElement(total, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}GrandTotalAmount").text = str(invoice.total_amount)

    return ET.tostring(root, pretty_print=True, encoding="utf-8").decode()

# ✅ PDF Generation with Embedded XML
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    # Create basic PDF with ReportLab
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    
    # PDF Metadata
    c.setTitle("ZUGFeRD Invoice")
    c.setAuthor("Your Company")
    c.setSubject("ZUGFeRD 2.1 Invoice")
    c.setCreator("FastAPI PDF Generator")
    
    # Invoice Content
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, 800, "Invoice")
    c.setFont("Helvetica", 12)
    c.drawString(100, 770, f"Invoice Number: {invoice.invoice_number}")
    c.drawString(100, 750, f"Invoice Date: {invoice.invoice_date}")
    c.drawString(100, 730, f"Customer: {invoice.customer_name}")

    # Items List
    y = 700
    for item in invoice.items:
        c.drawString(100, y, f"{item.description}: ${item.price:.2f}")
        y -= 20

    c.drawString(100, y - 20, f"Total: ${invoice.total_amount:.2f}")
    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    # Embed ZUGFeRD XML using PyMuPDF
    pdf = fitz.open("pdf", pdf_buffer.getvalue())
    xml_data = generate_zugferd_xml(invoice)

    # ✅ Critical Fix: Use set_xml_metadata instead of DocumentMetadata
    xmp_metadata = """<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
    <x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='Adobe XMP Core 5.6-c125 79.164274, 2022/07/18-18:10:59'>
      <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
        <rdf:Description rdf:about=''
          xmlns:pdfaid='http://www.aiim.org/pdfa/ns/id/'
          xmlns:xmp='http://ns.adobe.com/xap/1.0/'>
          <pdfaid:part>3</pdfaid:part>
          <pdfaid:conformance>B</pdfaid:conformance>
          <xmp:CreatorTool>FastAPI PDF Generator</xmp:CreatorTool>
        </rdf:Description>
      </rdf:RDF>
    </x:xmpmeta>
    <?xpacket end='w'?>"""

    pdf.set_xml_metadata(xmp_metadata)  # ✅ Fixed line
    pdf.embfile_add("ZUGFeRD-invoice.xml", xml_data.encode(), desc="ZUGFeRD XML")

    # Save final PDF
    final_pdf = BytesIO()
    pdf.save(final_pdf)
    pdf.close()
    return final_pdf.getvalue()

# ✅ API Endpoint
@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    try:
        pdf_bytes = generate_pdf_with_zugferd(data)
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=zugferd-invoice.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "OK", "version": "2.1"}