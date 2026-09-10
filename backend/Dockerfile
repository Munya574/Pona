# Pona API
#
# Tesseract is installed here rather than assumed. Label OCR is a real
# feature, and /scan/capabilities reports it as unavailable when the binary
# is missing, so a deploy without it silently loses the camera button.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# tesseract-ocr        : the OCR engine
# tesseract-ocr-eng    : English language data (not included in the base pkg)
# libgl1, libglib2.0-0 : Pillow runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Fail the build rather than the first user request if OCR is broken.
RUN tesseract --version && python -c "\
from app.ml.ocr import tesseract_available; \
assert tesseract_available(), 'Tesseract not reachable from Python'; \
print('OCR ready')"

EXPOSE 8000

# Hosts inject the port they want; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
