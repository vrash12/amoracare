import os
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from docx import Document
from PyPDF2 import PdfReader


# =========================
# SET TESSERACT PATH (WINDOWS ONLY)
# =========================
if os.name == "nt":  # Windows
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# =========================
# DOCX READER
# =========================
def read_docx(file_path):
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])


# =========================
# PDF TEXT EXTRACT (NORMAL PDF)
# =========================
def read_pdf_text(file_path):
    reader = PdfReader(file_path)
    text = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)

    return "\n".join(text)


# =========================
# IMAGE OCR
# =========================
def ocr_image(file_path):
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)


# =========================
# SCANNED PDF OCR
# =========================
def ocr_scanned_pdf(file_path):
    pages = convert_from_path(file_path)
    text = []

    for page in pages:
        text.append(pytesseract.image_to_string(page))

    return "\n".join(text)


# =========================
# MAIN ROUTER
# =========================
def read_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    # IMAGE FILES
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return ocr_image(file_path)

    # DOCX FILES
    elif ext == ".docx":
        return read_docx(file_path)

    # PDF FILES
    elif ext == ".pdf":
        text = read_pdf_text(file_path)

        # fallback to OCR if scanned PDF
        if not text.strip():
            text = ocr_scanned_pdf(file_path)

        return text

    else:
        raise ValueError(f"Unsupported file type: {ext}")


# =========================
# RUN TEST
# =========================
if __name__ == "__main__":
    file_path = "eric.PNG"  # change this to your file

    print("Processing:", file_path)
    result = read_file(file_path)

    print("\n========== OCR OUTPUT ==========\n")
    print(result)