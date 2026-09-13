from io import BytesIO
from pathlib import PurePath


MAX_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}


class DocumentProcessingError(ValueError):
    """A safe, user-facing document processing failure."""


def extract_text(filename: str, content: bytes, max_file_size: int = MAX_FILE_SIZE) -> str:
    extension = PurePath(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentProcessingError("This file type is not supported.")
    if not content:
        raise DocumentProcessingError("This file is empty.")
    if len(content) > max_file_size:
        raise DocumentProcessingError("This file is too large. Please upload a file under 10 MB.")

    if extension in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentProcessingError("This text file could not be decoded as UTF-8.") from error
    elif extension == ".pdf":
        text = _extract_pdf_text(content)
    else:
        text = _extract_image_text(content)

    cleaned_text = "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()
    if not cleaned_text:
        raise DocumentProcessingError("Could not find readable text in this file.")
    return cleaned_text


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise DocumentProcessingError("PDF support is not installed. Install the project dependencies first.") from error

    try:
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
        return _extract_scanned_pdf_text(content)
    except Exception as error:
        raise DocumentProcessingError("This PDF could not be read. It may be corrupted or scanned.") from error


def _extract_scanned_pdf_text(content: bytes) -> str:
    try:
        import pymupdf
        import pytesseract
        from PIL import Image
    except ImportError as error:
        raise DocumentProcessingError(
            "This PDF appears to be scanned. OCR support is not installed; install the project dependencies first."
        ) from error

    try:
        document = pymupdf.open(stream=content, filetype="pdf")
        pages: list[str] = []
        for page in document:
            pixels = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pixels.width, pixels.height], pixels.samples)
            pages.append(pytesseract.image_to_string(image))
        return "\n".join(pages)
    except Exception as error:
        raise DocumentProcessingError(
            "NoticeFlow couldn't read this scanned PDF clearly. Try a higher-resolution PDF or image."
        ) from error


def _extract_image_text(content: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as error:
        raise DocumentProcessingError("Image text extraction is not installed. Install the project dependencies first.") from error

    try:
        return pytesseract.image_to_string(Image.open(BytesIO(content)))
    except Exception as error:
        raise DocumentProcessingError("Could not read this image clearly. Try a higher-resolution screenshot.") from error