from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from typing import List
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF
import lxml.etree as ET
from datetime import datetime

app = FastAPI()

# ✅ Validated Data Models
class Item(BaseModel):
    description: str
    price: float
    quantity: float = 1.0  # Required for line item calculation

class InvoiceData(BaseModel):
    customer_name: str
    customer_address: str  # New required field
    country_code: str
    vat_id: str  # New required field
    invoice_number: str
    invoice_date: str
    due_date: str  # New required field
    items: List[Item]
    total_amount: float
    tax_amount: float  # Should be calculated as total_amount * 0.19

# ✅ ZUGFeRD 2.1 XML Generator (Compliant Structure)
def generate_zugferd_xml(invoice: InvoiceData) -> str:
    NSMAP = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance"
    }

    root = ET.Element("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice",
                     nsmap=NSMAP,
                     attrib={"{" + NSMAP["xsi"] + "}schemaLocation": 
                            "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100 ../ZUGFeRD2p1.xsd"})

    # ➡️ 1. Document Context (Mandatory)
    context = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocumentContext")
    guideline = ET.SubElement(context, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(guideline, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = "urn:zugferd.de:2p1:basic"

    # ➡️ 2. Document Header (Extended)
    header = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocument")
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = invoice.invoice_number
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}TypeCode").text = "380"  # Invoice code
    ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}Name").text = "RECHNUNG"
    
    issue_date = ET.SubElement(header, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}IssueDateTime")
    ET.SubElement(issue_date, "{urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100}DateTimeString", 
                 format="102").text = invoice.invoice_date.replace("-", "")

    # ➡️ 3. Supply Chain Details (Seller + Buyer)
    transaction = ET.SubElement(root, "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}SupplyChainTradeTransaction")
    
    # Seller Information (Your Company)
    agreement = ET.SubElement(transaction, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ApplicableHeaderTradeAgreement")
    seller = ET.SubElement(agreement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}SellerTradeParty")
    ET.SubElement(seller, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}Name").text = "Your Company Name"
    ET.SubElement(seller, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}SpecifiedLegalOrganization").text = "Your Company Legal Info"
    
    # Buyer Information
    buyer = ET.SubElement(agreement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}BuyerTradeParty")
    ET.SubElement(buyer, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}Name").text = invoice.customer_name
    postal = ET.SubElement(buyer, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}PostalTradeAddress")
    ET.SubElement(postal, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}LineOne").text = invoice.customer_address
    ET.SubElement(postal, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}CountryID").text = invoice.country_code

    # ➡️ 4. Line Items with VAT
    for idx, item in enumerate(invoice.items, start=1):
        line_item = ET.SubElement(transaction, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}IncludedSupplyChainTradeLineItem")
        ET.SubElement(line_item, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}AssociatedDocumentLineDocument").text = str(idx)
        
        product = ET.SubElement(line_item, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}SpecifiedTradeProduct")
        ET.SubElement(product, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}Name").text = item.description
        
        agreement = ET.SubElement(line_item, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}SpecifiedLineTradeAgreement")
        price = ET.SubElement(agreement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}NetPriceProductTradePrice")
        ET.SubElement(price, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ChargeAmount").text = f"{item.price:.2f}"

    # ➡️ 5. Tax Summary (German VAT 19%)
    settlement = ET.SubElement(transaction, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ApplicableHeaderTradeSettlement")
    ET.SubElement(settlement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}TaxCurrencyCode").text = "EUR"
    
    tax = ET.SubElement(settlement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ApplicableTradeTax")
    ET.SubElement(tax, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}CalculatedAmount").text = f"{invoice.tax_amount:.2f}"
    ET.SubElement(tax, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}TypeCode").text = "VAT"
    ET.SubElement(tax, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}BasisAmount").text = f"{invoice.total_amount - invoice.tax_amount:.2f}"
    ET.SubElement(tax, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}CategoryCode").text = "S"
    ET.SubElement(tax, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}RateApplicablePercent").text = "19.00"

    # ➡️ 6. Payment Terms
    payment_terms = ET.SubElement(settlement, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}SpecifiedTradePaymentTerms")
    due_date = ET.SubElement(payment_terms, "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}DueDateDateTime")
    ET.SubElement(due_date, "{urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100}DateTimeString", 
                 format="102").text = invoice.due_date.replace("-", "")

    return ET.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True).decode()

# ✅ PDF/A-3 Generation with Valid Embedding
def generate_pdf_with_zugferd(invoice: InvoiceData) -> bytes:
    # Create basic PDF
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    
    # Metadata
    c.setTitle("ZUGFeRD Invoice")
    c.setAuthor("Your Company")
    c.setSubject(f"Invoice {invoice.invoice_number}")
    
    # Content
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
    
    c.drawString(100, y-30, f"Net Total: €{(invoice.total_amount - invoice.tax_amount):.2f}")
    c.drawString(100, y-50, f"VAT (19%): €{invoice.tax_amount:.2f}")
    c.drawString(100, y-70, f"Grand Total: €{invoice.total_amount:.2f}")
    
    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    # Process with PyMuPDF
    pdf = fitz.open("pdf", pdf_buffer.getvalue())
    xml_data = generate_zugferd_xml(invoice)

    # ➡️ Critical Compliance Steps
    pdf.set_pdfa_metadata(
        part=3,
        conformance="B",
        output_intent="sRGB",
        creator="Your Company",
        title=f"Invoice {invoice.invoice_number}"
    )
    
    pdf.embfile_add(
        "ZUGFeRD-invoice.xml",
        xml_data.encode(),
        filename="/ZUGFeRD-invoice.xml",  # Required path format
        uf="/ZUGFeRD-invoice.xml",
        desc="ZUGFeRD 2.1 Basic Invoice",
        mime="text/xml"  # Must be exact MIME type
    )

    final_pdf = BytesIO()
    pdf.save(final_pdf)
    pdf.close()
    return final_pdf.getvalue()

# ✅ API Endpoint with Validation
@app.post("/generate-validated-invoice")
def generate_validated_invoice(data: InvoiceData):
    try:
        # Validate tax calculation
        expected_tax = round(data.total_amount * 0.19, 2)
        if abs(data.tax_amount - expected_tax) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Tax amount mismatch. Expected €{expected_tax:.2f} for 19% VAT"
            )

        pdf_bytes = generate_pdf_with_zugferd(data)
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{data.invoice_number}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "OK", "standard": "ZUGFeRD 2.1 Basic"}