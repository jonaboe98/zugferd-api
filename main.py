from fastapi import FastAPI, Response
from reportlab.pdfgen import canvas
from io import BytesIO

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the PDF Generator API!"}

@app.get("/make-pdf")
def make_pdf():
    # Create a buffer to hold the PDF data
    buf = BytesIO()
    
    # Create a PDF canvas
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Welcome to Zugferd API!")
    c.showPage()  # Finalize the current page
    c.save()  # Save the PDF data to the buffer

    # Retrieve the PDF data as bytes
    pdf_bytes = buf.getvalue()
    buf.close()

    # Return the PDF as a response
    return Response(pdf_bytes, media_type="application/pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
