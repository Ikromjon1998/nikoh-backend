"""MRZ (Machine Readable Zone) extraction and parsing service for passports."""

import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_mrz(image_path: str) -> dict | None:
    """
    Extract and parse MRZ from passport image using OCR.

    Args:
        image_path: Path to the passport image

    Returns:
        Dict with extracted data or None if MRZ not found/invalid:
        {
            "valid": bool,
            "first_name": str,
            "last_name": str,
            "birth_date": date,
            "expiry_date": date,
            "nationality": str,
            "document_number": str,
            "sex": str,
            "country": str,
            "raw_mrz": str
        }
    """
    if not Path(image_path).exists():
        logger.error(f"Image file not found: {image_path}")
        return None

    try:
        # Use OCR to extract text from the image
        from app.services import ocr_service

        logger.info(f"Extracting text from passport image: {image_path}")
        text = ocr_service.extract_text(image_path)

        if not text:
            logger.warning("No text extracted from image")
            return None

        # Try to find MRZ lines in the extracted text
        mrz_text = _find_mrz_in_text(text)

        if not mrz_text:
            logger.info("No MRZ pattern found in extracted text")
            return None

        logger.info(f"Found MRZ text: {mrz_text[:50]}...")

        # Parse the MRZ
        return _parse_mrz_text(mrz_text)

    except Exception as e:
        logger.error(f"Error extracting MRZ from {image_path}: {e}")
        return None


def _find_mrz_in_text(text: str) -> str | None:
    """
    Find MRZ lines in OCR-extracted text.

    MRZ for passports (TD3 format) consists of 2 lines of 44 characters each.
    Line 1: P<COUNTRY_CODE<LAST_NAME<<FIRST_NAME<...
    Line 2: DOC_NUMBER<CHECK<NATIONALITY...
    """
    # Clean up the text - remove spaces between characters that OCR might have added
    lines = text.replace(" ", "").upper().split("\n")

    # Also try splitting by common separators
    if len(lines) < 2:
        lines = re.split(r'[\n\r]+', text.replace(" ", "").upper())

    # Look for lines that look like MRZ (contain < and are around 44 chars)
    mrz_candidates = []
    for line in lines:
        # Clean the line
        clean_line = re.sub(r'[^A-Z0-9<]', '', line)
        # MRZ lines are typically 44 characters for TD3 (passport)
        if len(clean_line) >= 40 and '<' in clean_line:
            mrz_candidates.append(clean_line)

    # Try to find two consecutive MRZ lines
    if len(mrz_candidates) >= 2:
        # Check if first line starts with P< (passport)
        for i, line in enumerate(mrz_candidates[:-1]):
            if line.startswith('P<') or line.startswith('P0<'):
                # Normalize to exactly 44 chars
                line1 = (line + '<' * 44)[:44]
                line2 = (mrz_candidates[i + 1] + '<' * 44)[:44]
                return line1 + '\n' + line2

    # Alternative: look for P< pattern anywhere
    full_text = text.replace(" ", "").replace("\n", "").upper()
    match = re.search(r'(P[<0][A-Z]{3}[A-Z<]{39})', full_text)
    if match:
        start = match.start()
        # Try to get 88 characters (two lines)
        mrz_block = re.sub(r'[^A-Z0-9<]', '', full_text[start:start + 100])
        if len(mrz_block) >= 88:
            line1 = mrz_block[:44]
            line2 = mrz_block[44:88]
            return line1 + '\n' + line2

    return None


def _parse_mrz_text(mrz_text: str) -> dict | None:
    """Parse MRZ text using the mrz library."""
    try:
        from mrz.checker.td3 import TD3CodeChecker

        # Clean and format the MRZ text
        lines = mrz_text.strip().split('\n')
        if len(lines) < 2:
            # Try splitting by length
            if len(mrz_text.replace('\n', '')) >= 88:
                clean = mrz_text.replace('\n', '').replace(' ', '')
                lines = [clean[:44], clean[44:88]]
            else:
                logger.warning("MRZ text doesn't have 2 lines")
                return None

        # Ensure each line is exactly 44 characters
        line1 = (lines[0].strip() + '<' * 44)[:44]
        line2 = (lines[1].strip() + '<' * 44)[:44]

        mrz_string = line1 + '\n' + line2
        logger.info(f"Parsing MRZ:\nLine1: {line1}\nLine2: {line2}")

        checker = TD3CodeChecker(mrz_string)

        # Even if not fully valid, try to extract data
        fields = checker.fields

        # Handle different mrz library versions - result might be bool or object
        try:
            is_valid = checker.result.valid if hasattr(checker.result, 'valid') else bool(checker.result)
        except Exception:
            is_valid = False

        result = {
            "valid": is_valid,
            "first_name": _clean_name(fields.name or ""),
            "last_name": _clean_name(fields.surname or ""),
            "birth_date": _parse_mrz_date(fields.birth_date),
            "expiry_date": _parse_mrz_date(fields.expiry_date),
            "nationality": fields.nationality or "",
            "document_number": fields.document_number or "",
            "sex": fields.sex or "",
            "country": fields.country or "",
            "raw_mrz": mrz_string,
        }

        # If validation failed but we got some data, still return it
        if not is_valid and (result["first_name"] or result["last_name"]):
            logger.warning(f"MRZ validation failed but data extracted: {result}")

        return result

    except ImportError:
        logger.warning("mrz library not installed")
        return _manual_parse_mrz(mrz_text)
    except Exception as e:
        logger.error(f"Error parsing MRZ text: {e}")
        # Try manual parsing as fallback
        return _manual_parse_mrz(mrz_text)


def _manual_parse_mrz(mrz_text: str) -> dict | None:
    """Manually parse MRZ if the library fails."""
    try:
        lines = mrz_text.strip().split('\n')
        if len(lines) < 2:
            clean = mrz_text.replace('\n', '').replace(' ', '')
            if len(clean) >= 88:
                lines = [clean[:44], clean[44:88]]
            else:
                return None

        line1 = lines[0].strip()
        line2 = lines[1].strip()

        # Line 1 format: P<COUNTRY<SURNAME<<GIVEN_NAMES<...
        # Extract country (positions 2-5)
        country = line1[2:5].replace('<', '')

        # Extract names (after position 5)
        names_part = line1[5:]
        name_parts = names_part.split('<<')
        surname = name_parts[0].replace('<', ' ').strip() if name_parts else ""
        given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""

        # Line 2 format: DOC_NUMBER<CHECK<NATIONALITY<BIRTH<CHECK<SEX<EXPIRY<CHECK<...
        doc_number = line2[0:9].replace('<', '')
        nationality = line2[10:13].replace('<', '')
        birth_date_str = line2[13:19]
        sex = line2[20:21]
        expiry_date_str = line2[21:27]

        return {
            "valid": False,  # Manual parsing, needs verification
            "first_name": _clean_name(given_names),
            "last_name": _clean_name(surname),
            "birth_date": _parse_mrz_date(birth_date_str),
            "expiry_date": _parse_mrz_date(expiry_date_str),
            "nationality": nationality,
            "document_number": doc_number,
            "sex": sex,
            "country": country,
            "raw_mrz": mrz_text,
        }
    except Exception as e:
        logger.error(f"Manual MRZ parsing failed: {e}")
        return None


def _clean_name(name: str) -> str:
    """Clean name from MRZ format (replace < with space, capitalize)."""
    if not name:
        return ""
    # MRZ uses < as separator
    cleaned = name.replace("<", " ").strip()
    # Remove multiple spaces
    cleaned = " ".join(cleaned.split())
    # Title case
    return cleaned.title()


def _parse_mrz_date(date_str: str) -> date | None:
    """
    Parse MRZ date format (YYMMDD) to Python date.

    MRZ uses 2-digit year:
    - 00-30 -> 2000-2030
    - 31-99 -> 1931-1999
    """
    if not date_str or len(date_str) < 6:
        return None

    try:
        # Remove any non-digit characters
        date_str = "".join(c for c in date_str if c.isdigit())

        if len(date_str) < 6:
            return None

        year_2d = int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])

        # Convert 2-digit year to 4-digit
        if year_2d <= 30:
            year = 2000 + year_2d
        else:
            year = 1900 + year_2d

        return date(year, month, day)
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse MRZ date '{date_str}': {e}")
        return None


def validate_mrz_checksums(mrz_string: str) -> bool:
    """
    Verify MRZ checksums are correct.

    Args:
        mrz_string: Raw MRZ string (two lines for TD3 format)

    Returns:
        True if all checksums are valid
    """
    try:
        from mrz.checker.td3 import TD3CodeChecker

        checker = TD3CodeChecker(mrz_string)
        return checker.result.valid
    except ImportError:
        logger.warning("mrz library not installed, cannot validate checksums")
        return False
    except Exception as e:
        logger.error(f"Error validating MRZ checksums: {e}")
        return False


def parse_mrz_string(mrz_string: str) -> dict | None:
    """
    Parse an MRZ string directly (without image).

    Args:
        mrz_string: Raw MRZ string

    Returns:
        Parsed MRZ data or None
    """
    return _parse_mrz_text(mrz_string)


def get_country_name(country_code: str) -> str:
    """
    Convert ISO 3166-1 alpha-3 country code to full name.

    Args:
        country_code: 3-letter country code (e.g., "UZB")

    Returns:
        Country name or original code if not found
    """
    country_codes = {
        "UZB": "Uzbekistan",
        "KAZ": "Kazakhstan",
        "TJK": "Tajikistan",
        "KGZ": "Kyrgyzstan",
        "TKM": "Turkmenistan",
        "RUS": "Russia",
        "USA": "United States",
        "GBR": "United Kingdom",
        "DEU": "Germany",
        "FRA": "France",
        "TUR": "Turkey",
        "ARE": "United Arab Emirates",
        "KOR": "South Korea",
        "JPN": "Japan",
        "CHN": "China",
        # Add more as needed
    }
    return country_codes.get(country_code.upper(), country_code)
