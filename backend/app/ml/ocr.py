"""
Read ingredient text from a photo of a label.

THE FAILURE MODE THIS MODULE IS BUILT AROUND

OCR does not fail loudly. It fails by returning *less* text, confidently.
If a glare spot swallows the word MILK, Tesseract returns a clean-looking
string with no milk in it, the matcher finds no dairy, and Pona reports
"no triggers found" to someone with a milk allergy.

That is the same shape as every other bug this project has had: silently
reporting all-clear on something that was never actually checked. Accuracy
alone does not fix it, because no OCR engine is perfect on curved, glossy,
low-contrast packaging held at an angle.

So this module never returns just text. It returns text plus the evidence
needed to decide whether to trust it, and the caller is expected to refuse
a clean result on a poor read. The user reviews the extracted text before
anything is checked against their profile.
"""

import re
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image, ImageOps, ImageFilter

try:
    import pytesseract
    from pytesseract import Output
    _PYTESSERACT = True
except ImportError:  # pragma: no cover
    _PYTESSERACT = False


# Below this mean per-word confidence, treat the read as unreliable.
# Tesseract reports 0-100 per word. Real labels shot on a phone usually
# land in the 70s-80s; anything under 60 is typically glare, blur or an
# angle problem and the text will have holes in it.
LOW_CONFIDENCE = 60.0

# A label with almost no words means we photographed the wrong thing, or
# the crop missed the ingredient panel.
MIN_WORDS = 5

# Phrases that must be followed by something. A label ending on "MAY" or
# "MAY CONTAIN" has been cut off mid-warning, and what was cut off is
# exactly the allergen list.
_DANGLING_TAIL = re.compile(
    r"\b(may|may\s+contain|may\s+also|contains?|traces?\s+of|and|or|with|"
    r"produced\s+in|manufactured\s+in)\s*$",
    re.IGNORECASE,
)


def _completeness_warnings(text: str) -> List[str]:
    """
    Look for evidence that text was DROPPED, which confidence cannot see.

    Mean per-word confidence answers "how sure am I about what I read".
    It says nothing about what was missed, because a word that was never
    detected contributes nothing to the mean. Measured on a deliberately
    degraded label, Tesseract reported 93.7% confidence while silently
    dropping PEANUTS from the middle of the list and truncating the
    may-contain clause.

    These checks look at the shape of the text instead. An ingredient
    panel is a closed structure: brackets balance, and it ends on a
    terminator rather than mid-phrase. When that structure is broken,
    something is missing even if every surviving word is crisp.

    Heuristics, not proof. Text can still go missing with the structure
    intact - which is why the user reviews the text before anything is
    matched. This is the second line of defence, not the first.
    """
    out = []
    if not text:
        return out

    if text.count("(") != text.count(")"):
        out.append(
            "A bracket is left open, so ingredients listed inside it are "
            "probably missing."
        )

    stripped = text.rstrip()
    if _DANGLING_TAIL.search(stripped):
        out.append(
            "The text stops mid-sentence, right where an allergen warning "
            "would follow. The end of the label was almost certainly cut off."
        )
    elif stripped and stripped[-1] not in ".;:)":
        out.append(
            "The text doesn't end cleanly, which usually means the end of "
            "the label was cut off."
        )

    return out


class OCRUnavailable(RuntimeError):
    """Tesseract is not installed. Raised instead of returning empty text."""


@dataclass
class OCRResult:
    text: str
    confidence: float           # mean per-word confidence, 0-100
    word_count: int
    reliable: bool              # False => do NOT report a clean result
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 1),
            "word_count": self.word_count,
            "reliable": self.reliable,
            "warnings": self.warnings,
        }


def tesseract_available() -> bool:
    """Is the Tesseract binary actually installed and callable?"""
    if not _PYTESSERACT:
        return False
    if shutil.which("tesseract"):
        return True
    # Windows installers commonly land outside PATH.
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        try:
            if Image and shutil.os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                return True
        except Exception:
            pass
    return False


# Tesseract's page segmentation mode matters enormously on photographs.
# Measured on 20 real Open Food Facts panel photos:
#
#   psm 3 (the default)          56.5% allergen recall   <- what shipped
#   psm 6 + downscale            63.0%
#   psm 11 + downscale           67.4%
#   all three merged             71.7%
#
# Each pass fails differently - psm 6 assumes one uniform block, psm 11
# hunts sparse text - so merging recovers words no single pass finds.
# Precision drops (more junk words), which costs little here because the
# matcher only reacts to terms it recognises, and the user reviews the
# text before anything is checked.
_PASSES = [
    ("downscale", 6),
    ("downscale", 11),
    ("sharpen", 6),
]


def _downscale(img: Image.Image) -> Image.Image:
    """
    Cap the long edge, then autocontrast.

    A modern phone photo is ~4000px wide while the text occupies a small
    part of it. Tesseract does measurably better on a 2000px version: less
    JPEG noise amplified, and character sizes closer to what it expects.
    """
    img = img.convert("L").copy()
    img.thumbnail((2000, 2000), Image.LANCZOS)
    return ImageOps.autocontrast(img)


def _preprocess(img: Image.Image) -> Image.Image:
    """
    Standard cleanup that measurably helps on packaging photos.

    Greyscale removes colour noise from printed backgrounds, autocontrast
    recovers text shot in poor light, and a mild sharpen helps small print.
    Deliberately conservative: aggressive thresholding looks better on a
    flat scan and destroys text on a curved wrapper.
    """
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    if min(img.size) < 1000:
        scale = 1000 / min(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    return img.filter(ImageFilter.SHARPEN)


def _tidy(text: str) -> str:
    """Join the line breaks Tesseract inserts mid-list, collapse whitespace."""
    text = text.replace("|", "I")           # common misread in all-caps text
    text = re.sub(r"-\s*\n\s*", "", text)   # de-hyphenate across line breaks
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def extract_text(image_bytes: bytes) -> OCRResult:
    """
    Pull ingredient text out of a label photo.

    Raises OCRUnavailable if Tesseract is not installed — deliberately,
    rather than returning empty text that would read downstream as a label
    with no allergens in it.
    """
    if not tesseract_available():
        raise OCRUnavailable(
            "Tesseract OCR is not installed. Install it and retry:\n"
            "  Windows:  choco install tesseract\n"
            "  macOS:    brew install tesseract\n"
            "  Linux:    apt install tesseract-ocr"
        )

    import io

    source = Image.open(io.BytesIO(image_bytes))

    # Run every pass and keep the one that read the most, but merge in
    # words the other passes found. A single pass on a real photograph
    # misses roughly a third of the allergens; the passes fail on
    # different things, so together they do markedly better.
    best_words, best_confs = [], []
    extra = []
    for prep_name, psm in _PASSES:
        prep = _downscale if prep_name == "downscale" else _preprocess
        try:
            data = pytesseract.image_to_data(
                prep(source), output_type=Output.DICT, config=f"--psm {psm}"
            )
        except Exception:
            continue

        ws, cs = [], []
        for word, conf in zip(data["text"], data["conf"]):
            word = word.strip()
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                continue
            # Tesseract uses -1 for non-text regions.
            if word and conf >= 0:
                ws.append(word)
                cs.append(conf)

        if len(ws) > len(best_words):
            extra.append(best_words)
            best_words, best_confs = ws, cs
        else:
            extra.append(ws)

    words, confs = best_words, best_confs

    # Append words the winning pass missed. Order is lost for these, so
    # they land at the end - fine, because matching is per-ingredient and
    # the user reviews the text anyway.
    seen = {w.lower() for w in words}
    merged_extra = []
    for ws in extra:
        for w in ws:
            if w.lower() not in seen:
                seen.add(w.lower())
                merged_extra.append(w)

    text = _tidy(" ".join(words))
    if merged_extra:
        text = _tidy(text + " " + " ".join(merged_extra))
    confidence = sum(confs) / len(confs) if confs else 0.0

    warnings = []
    if not words:
        warnings.append("No text could be read from this image.")
    elif len(words) < MIN_WORDS:
        warnings.append(
            f"Only {len(words)} words were readable. Make sure the ingredient "
            f"list itself is in frame."
        )
    if words and confidence < LOW_CONFIDENCE:
        warnings.append(
            f"The text came out blurry (confidence {confidence:.0f}%). Words are "
            f"probably missing, so this reading cannot be trusted on its own."
        )
    if words and "ingredient" not in text.lower():
        warnings.append(
            "The word 'ingredients' wasn't found, so this may not be the "
            "ingredient panel."
        )

    # Evidence of DROPPED text, which confidence is blind to.
    completeness = _completeness_warnings(text)
    warnings.extend(completeness)

    # "reliable" means "trustworthy as a COMPLETE reading", so a structural
    # sign of missing text disqualifies it however crisp the surviving
    # words were.
    reliable = (
        bool(words)
        and confidence >= LOW_CONFIDENCE
        and len(words) >= MIN_WORDS
        and not completeness
    )

    return OCRResult(
        text=text,
        confidence=confidence,
        word_count=len(words),
        reliable=reliable,
        warnings=warnings,
    )
