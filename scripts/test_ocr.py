#!/usr/bin/env python3
"""Test OCR and MRZ extraction on a document."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_ocr(image_path: str):
    """Test OCR extraction."""
    print(f"\n=== Testing OCR on: {image_path} ===\n")

    from app.services import ocr_service

    if image_path.lower().endswith(".pdf"):
        print("Extracting text from PDF...")
        text = ocr_service.extract_text_from_pdf(image_path)
    else:
        print("Extracting text from image...")
        text = ocr_service.extract_text(image_path)

    if text:
        print(f"Extracted text ({len(text)} chars):")
        print("-" * 50)
        print(text[:500])
        if len(text) > 500:
            print("... (truncated)")
        print("-" * 50)
    else:
        print("ERROR: No text extracted!")

    return text


def test_mrz(image_path: str):
    """Test MRZ extraction."""
    print(f"\n=== Testing MRZ on: {image_path} ===\n")

    from app.services import mrz_service

    # For PDFs, we need to convert to image first
    if image_path.lower().endswith(".pdf"):
        print("Converting PDF to image first...")
        try:
            from pdf2image import convert_from_path
            import tempfile

            images = convert_from_path(image_path, dpi=300, first_page=1, last_page=1)
            if images:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                images[0].save(tmp.name, "PNG")
                image_path = tmp.name
                print(f"PDF converted to: {image_path}")
            else:
                print("ERROR: PDF conversion returned no images!")
                return None
        except ImportError:
            print("ERROR: pdf2image not installed!")
            return None
        except Exception as e:
            print(f"ERROR converting PDF: {e}")
            return None

    print("Extracting MRZ...")
    mrz_data = mrz_service.extract_mrz(image_path)

    if mrz_data:
        print("MRZ Data extracted:")
        print("-" * 50)
        for key, value in mrz_data.items():
            print(f"  {key}: {value}")
        print("-" * 50)
    else:
        print("ERROR: No MRZ data extracted!")

    return mrz_data


def test_face(image_path: str):
    """Test face extraction."""
    print(f"\n=== Testing Face Detection on: {image_path} ===\n")

    from app.services import face_service

    # For PDFs, we need to convert to image first
    if image_path.lower().endswith(".pdf"):
        print("Converting PDF to image first...")
        try:
            from pdf2image import convert_from_path
            import tempfile

            images = convert_from_path(image_path, dpi=300, first_page=1, last_page=1)
            if images:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                images[0].save(tmp.name, "PNG")
                image_path = tmp.name
                print(f"PDF converted to: {image_path}")
            else:
                print("ERROR: PDF conversion returned no images!")
                return None
        except ImportError:
            print("ERROR: pdf2image not installed!")
            return None
        except Exception as e:
            print(f"ERROR converting PDF: {e}")
            return None

    print("Extracting face...")
    face_embedding = face_service.extract_face(image_path)

    if face_embedding is not None:
        print(f"Face embedding extracted! Shape: {face_embedding.shape}")
    else:
        print("ERROR: No face detected!")

    return face_embedding


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ocr.py <path_to_document>")
        print("\nExample:")
        print("  python scripts/test_ocr.py ./uploads/verifications/.../document.pdf")
        sys.exit(1)

    doc_path = sys.argv[1]

    if not Path(doc_path).exists():
        print(f"ERROR: File not found: {doc_path}")
        sys.exit(1)

    # Run all tests
    text = test_ocr(doc_path)
    mrz = test_mrz(doc_path)
    face = test_face(doc_path)

    print("\n=== SUMMARY ===")
    print(f"OCR Text: {'OK' if text else 'FAILED'}")
    # MRZ is OK if we extracted any name data, even if checksum validation failed
    mrz_ok = mrz and (mrz.get('first_name') or mrz.get('last_name'))
    mrz_status = 'OK (validated)' if mrz and mrz.get('valid') else ('OK (needs review)' if mrz_ok else 'FAILED')
    print(f"MRZ Data: {mrz_status}")
    print(f"Face Detection: {'OK' if face is not None else 'FAILED'}")
