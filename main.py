from fastapi import FastAPI, Response
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from io import BytesIO

app = FastAPI()

# Define a model to accept data from Retool
class InvoiceData(BaseModel):
    customer_name: str
    items: list[dict]  # Each item should be a dict with 'description' and 'price'
    total_amount: float

@app.post("/make-pdf")
def make_invoice_pdf(data: InvoiceData):
    # Create a buffer to hold the PDF data
    buf = BytesIO()
    c = canvas.Canvas(buf)

    # Add content to the PDF
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, 800, "Invoice")  # Title

    # Customer Info
    c.setFont("Helvetica", 12)
    c.drawString(100, 770, f"Customer Name: {data.customer_name}")

    # Itemized List
    y = 740
    for item in data.items:
        c.drawString(100, y, f"{item['description']}: ${item['price']}")
        y -= 20  # Move down for each item

    # Total Amount
    c.drawString(100, y - 20, f"Total: ${data.total_amount}")

    # Finalize the PDF
    c.showPage()
    c.save()

    # Return the PDF as a response
    pdf_bytes = buf.getvalue()
    buf.close()

    return Response(pdf_bytes, media_type="application/pdf")
