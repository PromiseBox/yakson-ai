from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas import MedicationOcrResponse
from app.services.medication_ocr import OcrUnavailableError, OcrUploadError, analyze_medication_image

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/medications", response_model=MedicationOcrResponse, response_model_by_alias=True)
async def extract_medication_candidates(file: UploadFile = File(...)) -> MedicationOcrResponse:
    content = await file.read()
    try:
        return analyze_medication_image(file.filename, file.content_type, content)
    except OcrUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OcrUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
