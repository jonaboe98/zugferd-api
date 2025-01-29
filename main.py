import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pikepdf
from lxml import etree

# Define filenames
PDF_FILENAME = "invoice.pdf"
XML_FILENAME = "invoice.xml"
OUTPUT_PDF = "invoice_zugferd.pdf"

# Invoice Data (Example)
INVOICE_NUMBER = "20240101"
SELLER_NAME = "Example Seller GmbH"
BUYER_NAME = "Client Name"
AMOUNT = "1000.00"
CURRENCY = "EUR"

# 1. Generate ZUGFeRD XML Invoice
def create_zugferd_xml(filename):
    nsmap = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    }

    root = etree.Element("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice", nsmap=nsmap)
    context = etree.SubElement(root, "rsm:ExchangedDocumentContext")
    guid = etree.SubElement(context, "ram:GuidelineSpecifiedDocumentContextParameter")
    etree.SubElement(guid, "ram:ID").text = "urn:factur-x:1.0:basic"

    transaction = etree.SubElement(root, "rsm:SupplyChainTradeTransaction")
    agreement = etree.SubElement(transaction, "ram:ApplicableHeaderTradeAgreement")

    seller = etree.SubElement(agreement, "ram:SellerTradeParty")
    etree.SubElement(seller, "ram:Name").text = SELLER_NAME

    buyer = etree.SubElement(agreement, "ram:BuyerTradeParty")
    etree.SubElement(buyer, "ram:Name").text = BUYER_NAME

    settlement = etree.SubElement(transaction, "ram:ApplicableHeaderTradeSettlement")
    monetary = etree.SubElement(settlement, "ram:SpecifiedTradeSettlementMonetarySummation")
    etree.SubElement(monetary, "ram:LineTotalAmount", currencyID=CURRENCY).text = AMOUNT

    xml_tree = etree.ElementTree(root)
    xml_tree.write(filename, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# 2. Generate PDF Invoice
def create_pdf_invoice(filename):
    c = canvas.Canvas(filename, pagesize=A4)
    c.drawString(100, 750, f"Invoice #{INVOICE_NUMBER}")
    c.drawString(100, 730, f"Seller: {SELLER_NAME}")
    c.drawString(100, 710, f"Buyer: {BUYER_NAME}")
    c.drawString(100, 690, f"Amount: {AMOUNT} {CURRENCY}")
    c.save()

# 3. Embed XML into PDF (PDF/A-3)
def embed_xml_to_pdf(pdf_path, xml_path, output_pdf):
    pdf = pikepdf.Pdf.open(pdf_path)
    pdf.attachments[XML_FILENAME] = pikepdf.Attachment(xml_path, description="ZUGFeRD Invoice XML")
    pdf.save(output_pdf)

# Run all steps
if __name__ == "__main__":
    print("Generating ZUGFeRD XML...")
    create_zugferd_xml(XML_FILENAME)

    print("Generating PDF Invoice...")
    create_pdf_invoice(PDF_FILENAME)

    print("Embedding XML into PDF...")
    embed_xml_to_pdf(PDF_FILENAME, XML_FILENAME, OUTPUT_PDF)

    print(f"ZUGFeRD Invoice created: {OUTPUT_PDF}")
