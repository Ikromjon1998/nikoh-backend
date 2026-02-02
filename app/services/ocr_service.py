"""OCR service for document text extraction."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy loading of heavy dependencies
_reader: Any = None


def _get_reader():
    """Get or initialize EasyOCR reader (lazy loading)."""
    global _reader
    if _reader is None:
        try:
            import easyocr

            logger.info("Initializing EasyOCR reader...")
            _reader = easyocr.Reader(["en", "ru", "uz"], gpu=False)
            logger.info("EasyOCR reader initialized successfully")
        except ImportError:
            logger.warning("EasyOCR not installed, OCR features disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            return None
    return _reader


def extract_text(image_path: str) -> str:
    """
    Extract all text from an image using EasyOCR.

    Args:
        image_path: Path to the image file

    Returns:
        Extracted text as a single string
    """
    reader = _get_reader()
    if reader is None:
        return ""

    try:
        if not Path(image_path).exists():
            logger.error(f"Image file not found: {image_path}")
            return ""

        results = reader.readtext(image_path)
        # Results are list of (bbox, text, confidence)
        texts = [result[1] for result in results]
        return " ".join(texts)
    except Exception as e:
        logger.error(f"Error extracting text from {image_path}: {e}")
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Convert PDF pages to images and extract text.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text from all pages
    """
    try:
        from pdf2image import convert_from_path

        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return ""

        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=200)

        all_text = []
        reader = _get_reader()
        if reader is None:
            return ""

        for i, image in enumerate(images):
            # Save temporary image
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                image.save(tmp.name, "PNG")
                text = extract_text(tmp.name)
                all_text.append(text)
                # Clean up temp file
                Path(tmp.name).unlink(missing_ok=True)

        return " ".join(all_text)
    except ImportError:
        logger.warning("pdf2image not installed, PDF extraction disabled")
        return ""
    except Exception as e:
        logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""


def detect_document_type(text: str) -> str | None:
    """
    Guess document type from extracted text.

    Args:
        text: Extracted text from document

    Returns:
        Document type or None if unknown
    """
    text_lower = text.lower()

    # Passport indicators
    passport_keywords = [
        "passport",
        "pasport",
        "паспорт",
        "nationality",
        "гражданство",
        "date of birth",
        "дата рождения",
        "mrz",
        "p<",
    ]
    if any(kw in text_lower for kw in passport_keywords):
        return "passport"

    # Residence permit indicators
    residence_keywords = [
        "residence permit",
        "вид на жительство",
        "permanent resident",
        "временное проживание",
        "разрешение на проживание",
    ]
    if any(kw in text_lower for kw in residence_keywords):
        return "residence_permit"

    # Divorce certificate indicators
    divorce_keywords = [
        "divorce",
        "развод",
        "расторжение брака",
        "свидетельство о расторжении",
        "dissolution of marriage",
    ]
    if any(kw in text_lower for kw in divorce_keywords):
        return "divorce_certificate"

    # Diploma indicators
    diploma_keywords = [
        "diploma",
        "диплом",
        "degree",
        "степень",
        "university",
        "университет",
        "bachelor",
        "master",
        "бакалавр",
        "магистр",
    ]
    if any(kw in text_lower for kw in diploma_keywords):
        return "diploma"

    # Employment indicators
    employment_keywords = [
        "employment",
        "трудовой",
        "справка с места работы",
        "certificate of employment",
        "работодатель",
        "employer",
    ]
    if any(kw in text_lower for kw in employment_keywords):
        return "employment_proof"

    return None


def extract_dates_from_text(text: str) -> list[str]:
    """
    Extract date-like patterns from text.

    Args:
        text: Text to search for dates

    Returns:
        List of date strings found
    """
    import re

    # Common date patterns
    patterns = [
        r"\d{2}[./]\d{2}[./]\d{4}",  # DD/MM/YYYY or DD.MM.YYYY
        r"\d{4}[./]\d{2}[./]\d{2}",  # YYYY/MM/DD or YYYY.MM.DD
        r"\d{2}\s+\w+\s+\d{4}",  # DD Month YYYY
        r"\d{1,2}\s+\w+\s+\d{4}",  # D Month YYYY
    ]

    dates = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)

    return dates


def extract_names_from_text(text: str) -> dict[str, str | None]:
    """
    Try to extract name fields from text.

    Args:
        text: Text to search for names

    Returns:
        Dict with possible first_name and last_name
    """
    import re

    result = {"first_name": None, "last_name": None}

    # Look for common patterns
    # "Name: John" or "Имя: Иван"
    name_patterns = [
        r"(?:name|имя|исм)[:\s]+([A-Za-zА-Яа-яЎўҚқҒғҲҳ]+)",
        r"(?:surname|фамилия|фамилияси)[:\s]+([A-Za-zА-Яа-яЎўҚқҒғҲҳ]+)",
        r"(?:given name|имя)[:\s]+([A-Za-zА-Яа-яЎўҚқҒғҲҳ]+)",
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if "surname" in pattern.lower() or "фамилия" in pattern.lower():
                result["last_name"] = match.group(1)
            else:
                result["first_name"] = match.group(1)

    return result
