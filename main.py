import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import xml.etree.ElementTree as ET
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter

# JSON payload example
json_payload = {
    "invoice_number": "INV-2023-001",
    "issue_date": "20230815",
    "due_date": "20230915",
    "currency": "EUR",
    "seller": {
        "name": "Tech Solutions Ltd",
        "address": "123 Business Rd, London, UK",
        "tax_id": "GB123456789"
    },
    "buyer": {
        "name": "Digital Innovations Inc",
        "address": "456 Tech Street, Berlin, Germany",
        "tax_id": "DE987654321"
    },
    "items": [
        {
            "description": "Web Development Service",
            "quantity": 10,
            "unit_price": 150.00,
            "tax_rate": 20.0
        },
        {
            "description": "Cloud Hosting",
            "quantity": 3,
            "unit_price": 75.00,
            "tax_rate": 20.0
        }
    ],
    "payment_terms": "Net 30 days"
}

def generate_pdf(invoice_data, output_filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Header
    story.append(Paragraph("INVOICE", styles['Title']))
    story.append(Spacer(1, 12))
    
    # Seller/Buyer Info
    seller_info = f"""Seller:<br/>
    {invoice_data['seller']['name']}<br/>
    {invoice_data['seller']['address']}<br/>
    VAT ID: {invoice_data['seller']['tax_id']}"""
    
    buyer_info = f"""Buyer:<br/>
    {invoice_data['buyer']['name']}<br/>
    {invoice_data['buyer']['address']}<br/>
    VAT ID: {invoice_data['buyer']['tax_id']}"""
    
    info_table = Table([
        [Paragraph(seller_info, styles['Normal']), 
         Paragraph(buyer_info, styles['Normal'])]
    ], colWidths=[250, 250])
    story.append(info_table)
    story.append(Spacer(1, 24))
    
    # Invoice Details
    details_data = [
        ['Invoice Number:', invoice_data['invoice_number']],
        ['Issue Date:', invoice_data['issue_date']],
        ['Due Date:', invoice_data['due_date']],
        ['Currency:', invoice_data['currency']]
    ]
    details_table = Table(details_data, colWidths=[100, 400])
    story.append(details_table)
    story.append(Spacer(1, 24))
    
    # Items Table
    items_header = ['Description', 'Quantity', 'Unit Price', 'Total']
    items_data = [items_header]
    
    total = 0
    for item in invoice_data['items']:
        row_total = item['quantity'] * item['unit_price']
        total += row_total
        items_data.append([
            item['description'],
            str(item['quantity']),
            f"{item['unit_price']:.2f}",
            f"{row_total:.2f}"
        ])
    
    items_table = Table(items_data)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(items_table)
    story.append(Spacer(1, 24))
    
    # Total
    total_text = f"Total Amount: {invoice_data['currency']} {total:.2f}"
    story.append(Paragraph(total_text, styles['Heading2']))
    
    doc.build(story)
    buffer.seek(0)
    
    # Embed ZUGFeRD XML
    reader = PdfReader(buffer)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    
    # Add XML attachment
    xml_data = generate_zugferd_xml(invoice_data)
    writer.add_attachment("ZUGFeRD-invoice.xml", xml_data)
    
    with open(output_filename, "wb") as f:
        writer.write(f)

def generate_zugferd_xml(invoice_data):
    ns = {
        'rsm': "urn:ferd:CrossIndustryDocument:invoice:1p0",
        'ram': "urn:ferd:ram:xsd:103",
        'udt': "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:15"
    }
    
    root = ET.Element('{urn:ferd:CrossIndustryDocument:invoice:1p0}CrossIndustryDocument', {
        'xmlns:rsm': ns['rsm'],
        'xmlns:ram': ns['ram'],
        'xmlns:udt': ns['udt']
    })
    
    # Header
    header = ET.SubElement(root, 'rsm:Header')
    ET.SubElement(header, 'ram:ID').text = invoice_data['invoice_number']
    ET.SubElement(header, 'ram:Name').text = "Commercial Invoice"
    
    # Trade Agreement
    trade_agreement = ET.SubElement(root, 'rsm:SupplyChainTradeTransaction')
    applicable_header = ET.SubElement(trade_agreement, 'ram:ApplicableSupplyChainTradeAgreement')
    
    seller = ET.SubElement(applicable_header, 'ram:SellerTradeParty')
    ET.SubElement(seller, 'ram:Name').text = invoice_data['seller']['name']
    ET.SubElement(seller, 'ram:TaxID').text = invoice_data['seller']['tax_id']
    
    buyer = ET.SubElement(applicable_header, 'ram:BuyerTradeParty')
    ET.SubElement(buyer, 'ram:Name').text = invoice_data['buyer']['name']
    ET.SubElement(buyer, 'ram:TaxID').text = invoice_data['buyer']['tax_id']
    
    # Line Items
    for item in invoice_data['items']:
        line_item = ET.SubElement(trade_agreement, 'ram:IncludedSupplyChainTradeLineItem')
        ET.SubElement(line_item, 'ram:AssociatedDocumentLineDocument/ram:LineID').text = "1"
        ET.SubElement(line_item, 'ram:SpecifiedSupplyChainTradeDelivery/ram:BilledQuantity').text = str(item['quantity'])
        ET.SubElement(line_item, 'ram:SpecifiedSupplyChainTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount').text = f"{item['unit_price']:.2f}"
        ET.SubElement(line_item, 'ram:SpecifiedTradeProduct/ram:Name').text = item['description']
    
    # Totals
    total = sum(item['quantity'] * item['unit_price'] for item in invoice_data['items'])
    applicable_trade_settlement = ET.SubElement(trade_agreement, 'ram:ApplicableSupplyChainTradeSettlement')
    ET.SubElement(applicable_trade_settlement, 'ram:InvoiceCurrencyCode').text = invoice_data['currency']
    ET.SubElement(applicable_trade_settlement, 'ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:LineTotalAmount').text = f"{total:.2f}"
    
    xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return xml_str

if __name__ == "__main__":
    # Generate PDF with embedded ZUGFeRD XML
    generate_pdf(json_payload, "zugferd_invoice.pdf")
    
    # Save JSON payload
    with open("invoice_payload.json", "w") as f:
        json.dump(json_payload, f, indent=2)