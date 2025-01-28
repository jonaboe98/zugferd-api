from fastapi import FastAPI, Response
from reportlab.pdfgen import canvas
from io import BytesIO

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/make-pdf")
def make_pdf():
    # Create a buffer to hold the PDF data
    buf = BytesIO()
    
    # Create a PDF canvas
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Hello PDF World!")  # Add text to the PDF
    c.showPage()  # Finalize the current page
    c.save()  # Save the PDF data to the buffer

    # Retrieve the PDF data as bytes
    pdf_bytes = buf.getvalue()
    buf.close()

    # Return the PDF as a response
    return Response(pdf_bytes, media_type="application/pdf")
