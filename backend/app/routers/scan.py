"""
Getting ingredient text into Pona.

DESIGN DECISION: OCR output is never checked automatically.

/scan/ocr extracts text and hands it back for the user to review. It does
not call the matcher, and there is deliberately no endpoint that goes from
photo straight to a result.

The reason is that OCR fails by silently dropping words. A glare spot over
MILK produces a clean-looking string with no milk in it; the matcher then
correctly finds no dairy in the text it was given, and Pona reports "no
triggers found" to someone with a milk allergy. Every layer behaves
correctly and the user gets hurt.

Putting a human between the read and the verdict breaks that chain, and it
costs one tap. The person holding the packet can see whether the text
matches it.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.ml.ocr import extract_text, OCRUnavailable, tesseract_available

router = APIRouter()

# Refuse oversized uploads rather than dragging a phone-sized image
# through preprocessing.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("/capabilities")
async def capabilities():
    """
    What input methods actually work right now.

    The UI uses this to decide what to offer. Showing a camera button that
    cannot work is worse than not showing one.
    """
    return {
        "paste": True,
        "ocr": tesseract_available(),
        "photo": False,   # ingredient recognition from a food photo
        "url": False,     # recipe page scraping
    }


@router.post("/ocr")
async def scan_ocr(file: UploadFile = File(...)):
    """
    Read text from a photo of an ingredient label.

    Returns the text plus the evidence needed to judge it. `reliable: false`
    means the client MUST NOT treat a lack of findings as a clean result —
    the read has holes in it.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image is larger than 10MB. Try a smaller photo.",
        )

    try:
        result = extract_text(raw)
    except OCRUnavailable as e:
        # 503, not 500: the service is fine, this capability just isn't
        # installed. And never an empty string, which would read downstream
        # as a label containing no allergens.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read that image: {e}",
        ) from e

    return result.to_dict()


class URLScanRequest(BaseModel):
    url: str


@router.post("/photo")
async def scan_photo(file: UploadFile = File(...)):
    """Ingredient recognition from a photo of food. Not built."""
    raise HTTPException(
        status_code=501,
        detail="Recognising ingredients from a photo of food isn't supported yet. "
               "Photograph the ingredient label instead, or paste the text.",
    )


@router.post("/url")
async def scan_url(body: URLScanRequest):
    """Extract ingredients from a recipe page. Not built."""
    raise HTTPException(
        status_code=501,
        detail="Reading recipes from a URL isn't supported yet. "
               "Paste the ingredient list instead.",
    )
