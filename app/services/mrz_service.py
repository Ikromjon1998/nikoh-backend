"""MRZ (Machine Readable Zone) extraction and parsing service for passports."""

import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_mrz(image_path: str) -> dict | None:
    """
    Extract and parse MRZ from passport image.

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
        from passporteye import read_mrz

        # Extract MRZ from image
        mrz_data = read_mrz(image_path)

        if mrz_data is None:
            logger.info(f"No MRZ found in image: {image_path}")
            return None

        # Get the MRZ object
        mrz = mrz_data.to_dict()

        if not mrz:
            return None

        # Parse the MRZ data
        return _parse_mrz_data(mrz)

    except ImportError:
        logger.warning("passporteye not installed, MRZ extraction disabled")
        return None
    except Exception as e:
        logger.error(f"Error extracting MRZ from {image_path}: {e}")
        return None


def _parse_mrz_data(mrz: dict) -> dict | None:
    """Parse raw MRZ data into structured format."""
    try:
        # Extract fields from MRZ
        raw_text = mrz.get("raw_text", "")

        # Try to parse with mrz library for validation
        try:
            from mrz.checker.td3 import TD3CodeChecker

            checker = TD3CodeChecker(raw_text)
            is_valid = checker.result.valid

            if is_valid:
                fields = checker.fields
                return {
                    "valid": True,
                    "first_name": _clean_name(fields.name or ""),
                    "last_name": _clean_name(fields.surname or ""),
                    "birth_date": _parse_mrz_date(fields.birth_date),
                    "expiry_date": _parse_mrz_date(fields.expiry_date),
                    "nationality": fields.nationality or "",
                    "document_number": fields.document_number or "",
                    "sex": fields.sex or "",
                    "country": fields.country or "",
                    "raw_mrz": raw_text,
                }
        except ImportError:
            logger.warning("mrz library not installed, using basic parsing")
        except Exception as e:
            logger.warning(f"MRZ validation failed: {e}, using basic parsing")

        # Fallback: basic parsing from passporteye output
        return {
            "valid": mrz.get("valid_score", 0) > 50,
            "first_name": _clean_name(mrz.get("names", "")),
            "last_name": _clean_name(mrz.get("surname", "")),
            "birth_date": _parse_mrz_date(mrz.get("date_of_birth", "")),
            "expiry_date": _parse_mrz_date(mrz.get("expiration_date", "")),
            "nationality": mrz.get("nationality", ""),
            "document_number": mrz.get("number", ""),
            "sex": mrz.get("sex", ""),
            "country": mrz.get("country", ""),
            "raw_mrz": raw_text,
        }

    except Exception as e:
        logger.error(f"Error parsing MRZ data: {e}")
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
    try:
        from mrz.checker.td3 import TD3CodeChecker

        checker = TD3CodeChecker(mrz_string)

        if not checker.result.valid:
            logger.warning("MRZ string validation failed")
            return None

        fields = checker.fields
        return {
            "valid": True,
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
    except ImportError:
        logger.warning("mrz library not installed")
        return None
    except Exception as e:
        logger.error(f"Error parsing MRZ string: {e}")
        return None


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
