from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Literal

router = APIRouter()


class SubstitutionRequest(BaseModel):
    ingredient: str
    context: Literal["baking", "cooking", "raw"]


class Substitution(BaseModel):
    name: str
    notes: str


class SubstitutionResponse(BaseModel):
    original: str
    substitutions: List[Substitution]


@router.post("/", response_model=SubstitutionResponse)
async def get_substitutions(request: SubstitutionRequest):
    # TODO: query FAISS substitution index via substitution.py
    return SubstitutionResponse(original=request.ingredient, substitutions=[])
