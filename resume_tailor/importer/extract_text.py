import pdfplumber
from pathlib import Path
from docx import Document


def extract_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file, preserving reading order."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


def extract_from_docx(docx_path: str) -> str:
    """Extract text from a DOCX file, preserving paragraph structure."""
    doc = Document(docx_path)
    text_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    return "\n".join(text_parts)


def extract_text(file_path: str) -> str:
    """Extract text from a resume file (PDF or DOCX).

    Args:
        file_path: Path to the resume file (PDF or DOCX)

    Returns:
        Extracted text as a string

    Raises:
        ValueError: If the file format is not supported
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_from_pdf(file_path)
    elif suffix in [".docx", ".doc"]:
        return extract_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .pdf, .docx, .doc")
