from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

router = APIRouter()


@router.post("/photo")
async def scan_photo(file: UploadFile = File(...)):
    # TODO: pass image bytes to cv_model.predict_ingredients()
    return {"ingredients": [], "raw": ""}


@router.post("/ocr")
async def scan_ocr(file: UploadFile = File(...)):
    # TODO: pass image bytes to ocr.extract_text(), then nlp_model.normalize()
    return {"ingredients": [], "raw": ""}


class URLScanRequest(BaseModel):
    url: str


@router.post("/url")
async def scan_url(body: URLScanRequest):
    # TODO: scrape recipe page, extract ingredients, normalize
    return {"ingredients": [], "raw": ""}
