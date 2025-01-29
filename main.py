import json
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pikepdf
from lxml import etree

# Define file names
PDF_FILENAME = "invoice.pdf"
XML_FILENAME = "invoice.xml"
OUTPUT_PDF = "invoice_zugferd.pdf"
INPUT_JSON = "invoice_data.json"

# 1. Load Invoice Data from JSON
def load_invoice_data(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)

# 2. Generate ZUGFeRD XML Invoice
def create_zugferd_xml(invoice_data, filename):
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
    etree.SubElement(seller, "ram:Name").text = invoice_data["seller"]["name"]

    buyer = etree.SubElement(agreement, "ram:BuyerTradeParty")
    etree.SubElement(buyer, "ram:Name").text = invoice_data["buyer"]["name"]

    settlement = etree.SubElement(transaction, "ram:ApplicableHeaderTradeSettlement")
    monetary = etree.SubElement(settlement, "ram:SpecifiedTradeSettlementMonetarySummation")
    etree.SubElement(monetary, "ram:LineTotalAmount", currencyID=invoice_data["currency"]).text = str(invoice_data["total_amount"])
    etree.SubElement(monetary, "ram:TaxTotalAmount", currencyID=invoice_data["currency"]).text = str(invoice_data["total_vat"])
    etree.SubElement(monetary, "ram:GrandTotalAmount", currencyID=invoice_data["currency"]).text = str(invoice_data["grand_total"])

    xml_tree = etree.ElementTree(root)
    xml_tree.write(filename, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# 3. Generate PDF Invoice
def create_pdf_invoice(invoice_data, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    c.drawString(100, 750, f"Invoice #{invoice_data['invoice_number']}")
    c.drawString(100, 730, f"Issue Date: {invoice_data['issue_date']}")
    c.drawString(100, 710, f"Seller: {invoice_data['seller']['name']}")
    c.drawString(100, 690, f"Buyer: {invoice_data['buyer']['name']}")
    c.drawString(100, 670, f"Total: {invoice_data['grand_total']} {invoice_data['currency']}")

    y = 650
    for item in invoice_data["line_items"]:
        c.drawString(100, y, f"{item['description']} - {item['quantity']} x {item['unit_price']} {invoice_data['currency']} (VAT {item['vat_rate']}%)")
        y -= 20

    c.drawString(100, y - 20, f"Payment Details: {invoice_data['payment_details']['bank_name']}")
    c.drawString(100, y - 40, f"IBAN: {invoice_data['payment_details']['iban']}")
    c.drawString(100, y - 60, f"BIC: {invoice_data['payment_details']['bic']}")
    c.drawString(100, y - 80, f"Reference: {invoice_data['payment_details']['reference']}")
    c.save()

# 4. Embed XML into PDF (PDF/A-3)
def embed_xml_to_pdf(pdf_path, xml_path, output_pdf):
    pdf = pikepdf.Pdf.open(pdf_path)
    pdf.attachments[XML_FILENAME] = pikepdf.Attachment(xml_path, description="ZUGFeRD Invoice XML")
    pdf.save(output_pdf)

# Run all steps
if __name__ == "__main__":
    print("Loading invoice data from JSON...")
    invoice_data = load_invoice_data(INPUT_JSON)

    print("Generating ZUGFeRD XML...")
    create_zugferd_xml(invoice_data, XML_FILENAME)

    print("Generating PDF Invoice...")
    create_pdf_invoice(invoice_data, PDF_FILENAME)

    print("Embedding XML into PDF...")
    embed_xml_to_pdf(PDF_FILENAME, XML_FILENAME, OUTPUT_PDF)

    print(f"✅ ZUGFeRD Invoice created: {OUTPUT_PDF}")
