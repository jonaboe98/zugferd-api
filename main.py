from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF
import lxml.etree as ET

# -----------------------------------------
# 1) Pydantic Models
# -----------------------------------------
class Item(BaseModel):
    description: str
    price: float
    quantity: float = 1.0

class InvoiceData(BaseModel):
    customer_name: str
    customer_address: str
    country_code: str
    vat_id: str
    invoice_number: str
    invoice_date: str
    due_date: str
    items: List[Item]
    total_amount: float
    tax_amount: float

# -----------------------------------------
# 2) Generate ZUGFeRD XML
# -----------------------------------------
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    NSMAP = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance"
    }

    root = ET.Element(
        "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice",
        nsmap=NSMAP,
        attrib={
            "{" + NSMAP["xsi"] + "}schemaLocation": (
                "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100 ../ZUGFeRD2p1.xsd"
            )
        },
    )

    # 1. Document Context
    context = ET.SubElement(root, "{rsm}ExchangedDocumentContext")
    guideline = ET.SubElement(context, "{ram}GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(guideline, "{ram}ID").text = "urn:zugferd.de:2p1:basic"

    # 2. Document Header
    header = ET.SubElement(root, "{rsm}ExchangedDocument")
    ET.SubElement(header, "{ram}ID").text = invoice.invoice_number
    ET.SubElement(header, "{ram}TypeCode").text = "380"  # Invoice code
    ET.SubElement(header, "{ram}Name").text = "RECHNUNG"

    issue_date = ET.SubElement(header, "{ram}IssueDateTime")
    ET.SubElement(issue_date, "{udt}DateTimeString", format="102").text = invoice.invoice_date.replace("-", "")

    # 3. Supply Chain (Seller + Buyer)
    transaction = ET.SubElement(root, "{rsm}SupplyChainTradeTransaction")

    agreement = ET.SubElement(transaction, "{ram}ApplicableHeaderTradeAgreement")
    seller = ET.SubElement(agreement, "{ram}SellerTradeParty")
    ET.SubElement(seller, "{ram}Name").text = "Your Company Name"
    ET.SubElement(seller, "{ram}SpecifiedLegalOrganization").text = "Your Company Legal Info"

    buyer = ET.SubElement(agreement, "{ram}BuyerTradeParty")
    ET.SubElement(buyer, "{ram}Name").text = invoice.customer_name
    postal = ET.SubElement(buyer, "{ram}PostalTradeAddress")
    ET.SubElement(postal, "{ram}LineOne").text = invoice.customer_address
    ET.SubElement(postal, "{ram}CountryID").text = invoice.country_code

    # 4. Line Items
    for idx, item in enumerate(invoice.items, start=1):
        line_item = ET.SubElement(transaction, "{ram}IncludedSupplyChainTradeLineItem")
        ET.SubElement(line_item, "{ram}AssociatedDocumentLineDocument").text = str(idx)
        
        product = ET.SubElement(line_item, "{ram}SpecifiedTradeProduct")
        ET.SubElement(product, "{ram}Name").text = item.description
        
        line_agreement = ET.SubElement(line_item, "{ram}SpecifiedLineTradeAgreement")
        price = ET.SubElement(line_agreement, "{ram}NetPriceProductTradePrice")
        ET.SubElement(price, "{ram}ChargeAmount").text = f"{item.price:.2f}"

    # 5. Tax Summary
    settlement = ET.SubElement(transaction, "{ram}ApplicableHeaderTradeSettlement")
    ET.SubElement(settlement, "{ram}TaxCurrencyCode").text = "EUR"
    
    tax = ET.SubElement(settlement, "{ram}ApplicableTradeTax")
    ET.SubElement(tax, "{ram}CalculatedAmount").text = f"{invoice.tax_amount:.2f}"
    ET.SubElement(tax, "{ram}TypeCode").text = "VAT"
    net_amount = invoice.total_amount - invoice.tax_amount
    ET.SubElement(tax, "{ram}BasisAmount").text = f"{net_amount:.2f}"
    ET.SubElement(tax, "{ram}CategoryCode").text = "S"
    ET.SubElement(tax, "{ram}RateApplicablePercent").text = "19.00"

    # 6. Payment Terms
    payment_terms = ET.SubElement(settlement, "{ram}SpecifiedTradePaymentTerms")
    due_date = ET.SubElement(payment_terms, "{ram}DueDateDateTime")
    ET.SubElement(due_date, "{udt}DateTimeString", format="102").text = invoice.due_date.replace("-", "")

    return ET.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True).decode()

# -----------------------------------------
# 3) Generate PDF/A-3 With Embedded XML
# -----------------------------------------
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    """
    Generates a PDF from scratch, embeds the ZUGFeRD XML as an attachment,
    and enforces PDF/A-3 conformance using PyMuPDF.
    """
    # 3.1) First create a "regular" PDF in memory with ReportLab
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    
    # Basic content
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 800, "Invoice")
    c.setFont("Helvetica", 12)
    c.drawString(100, 770, f"Invoice Number: {invoice.invoice_number}")
    c.drawString(100, 750, f"Date: {invoice.invoice_date}")
    c.drawString(100, 730, f"Customer: {invoice.customer_name}")

    y = 700
    for item in invoice.items:
        c.drawString(100, y, f"{item.description} - {item.quantity}x €{item.price:.2f}")
        y -= 20

    net_total = invoice.total_amount - invoice.tax_amount
    c.drawString(100, y - 30, f"Net Total: €{net_total:.2f}")
    c.drawString(100, y - 50, f"VAT (19%): €{invoice.tax_amount:.2f}")
    c.drawString(100, y - 70, f"Grand Total: €{invoice.total_amount:.2f}")

    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    # 3.2) Open the PDF with PyMuPDF for further processing
    pdf_doc = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")

    # 3.3) Generate the ZUGFeRD XML
    xml_data = generate_zugferd_xml(invoice).encode("utf-8")

    # 3.4) Embed the XML into the PDF
    pdf_doc.embfile_add(
        "ZUGFeRD-invoice.xml",
        xml_data,
        filename="/ZUGFeRD-invoice.xml",  # In PDF/A-3, a leading slash is customary
        uf="/ZUGFeRD-invoice.xml",
        desc="ZUGFeRD 2.1 Basic Invoice",
        mime="text/xml"
    )

    # 3.5) Set PDF metadata (title, author, subject, etc.)
    pdf_doc.set_metadata({
        "title": f"Invoice {invoice.invoice_number}",
        "author": "Your Company",
        "creator": "Your Company",
        "subject": f"Invoice {invoice.invoice_number}",
        "keywords": "ZUGFeRD, Invoice, PDF/A-3"
    })

    # 3.6) Load an ICC color profile (required for PDF/A). 
    #      Make sure you have "sRGB.icc" in your working directory or provide its path.
    #      If you do NOT embed an ICC profile, many validators will reject PDF/A conformance.
    with open("sRGB.icc", "rb") as f:
        icc_profile = f.read()

    # 3.7) Save the final PDF as PDF/A-3B
    #      This enforces conformance, includes embedded files, and ensures output is a proper PDF/A-3.
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

# -----------------------------------------
# 4) FastAPI Endpoint
# -----------------------------------------
app = FastAPI()

@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    """
    Validate the invoice data, generate a PDF/A-3 with embedded ZUGFeRD XML,
    and return it as a downloadable PDF file.
    """
    try:
        # Optional: Validate the tax amount (19% assumption)
        expected_tax = round(data.total_amount * 0.19, 2)
        if abs(data.tax_amount - expected_tax) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Tax amount mismatch. Expected €{expected_tax:.2f} for 19% VAT"
            )

        # Generate the PDF/A-3 + embedded XML
        pdf_bytes = generate_pdf_with_zugferd(data)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="invoice_{data.invoice_number}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "OK", "standard": "ZUGFeRD 2.1 Basic"}
