"""Retrieval-only validation endpoints; no model inference occurs here."""

from fastapi import APIRouter, HTTPException

from app.core.database import LocalSessionLocal
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService


router = APIRouter()
service = RetrievalValidationService()


@router.post("/validate", status_code=201)
async def validate_retrieval(request: RetrievalValidationRequest):
    db = LocalSessionLocal()
    try:
        retrieval = service.retrieve(db, request)
        return service.persist_validation_run(db, request, retrieval)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        db.close()