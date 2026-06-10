# OCR pipeline for ingredient label reading
# Tool: Tesseract + custom post-processing


def extract_text(image_bytes: bytes) -> str:
    """Extract raw text from an ingredient label photo."""
    raise NotImplementedError
