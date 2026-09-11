"""
Locate the Open Food Facts export.

The 13GB CSV moves around: sometimes it sits flat in data/raw/, sometimes
extraction nests it inside a folder of the same name, and the download is
a .gz that may or may not have been unpacked yet. Hard-coding one path
means every script breaks whenever the file is re-downloaded.

This resolves it once, and fails with an actionable message rather than a
FileNotFoundError naming a path that was never right.
"""

from pathlib import Path

RAW = Path(__file__).parent.parent / "data" / "raw"
NAME = "en.openfoodfacts.org.products.csv"

CANDIDATES = [
    RAW / NAME,                 # flat
    RAW / NAME.removesuffix(".csv") / NAME,   # nested in a same-named folder
    RAW / "openfoodfacts" / NAME,
]


def find_off_csv() -> Path:
    """Return the OFF export path, or raise with instructions."""
    for p in CANDIDATES:
        if p.exists() and p.stat().st_size > 1_000_000:
            return p

    # Point at the .gz if it's there but wasn't unpacked - the most likely
    # reason someone hits this.
    gz = list(RAW.glob("*.products.csv.gz"))
    hint = (
        f"\nFound a compressed export at {gz[0].name} - extract it first."
        if gz else
        "\nDownload it from https://world.openfoodfacts.org/data (the CSV export)."
    )
    searched = "\n  ".join(str(c) for c in CANDIDATES)
    raise FileNotFoundError(
        f"Open Food Facts export not found. Looked in:\n  {searched}{hint}"
    )
