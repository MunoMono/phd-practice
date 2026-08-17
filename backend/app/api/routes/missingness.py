import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.core.database import LocalSessionLocal
from app.models.document import Document, DocumentChunk
from app.models.research_outputs import MissingnessEvent

router = APIRouter()

MissingnessType = Literal[
    "documentary",
    "descriptive",
    "retrieval",
    "institutional",
    "historiographic",
    "computational",
]

MissingnessStatus = Literal["open", "reviewing", "triaged", "resolved"]


class MissingnessCreateRequest(BaseModel):
    type: MissingnessType
    query_or_entity_or_field: str
    evidence: str
    query_id: Optional[str] = None
    source_document_id: Optional[str] = None
    source_chunk_id: Optional[str] = None
    status: MissingnessStatus = "open"
    reviewer_note: Optional[str] = None


class MissingnessUpdateRequest(BaseModel):
    status: Optional[MissingnessStatus] = None
    reviewer_note: Optional[str] = None


def serialize_event(event: MissingnessEvent) -> dict:
    return {
        "id": event.id,
        "event_id": event.event_id,
        "type": event.type,
        "query_or_entity_or_field": event.query_or_entity_or_field,
        "evidence": event.evidence,
        "query_id": event.query_id,
        "source_document_id": event.source_document_id,
        "source_chunk_id": event.source_chunk_id,
        "status": event.status,
        "reviewer_note": event.reviewer_note,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


def calculate_metadata_coverage(
    total_documents: int,
    documents_with_title: int,
    documents_with_pid: int,
    documents_with_filename: int,
    documents_with_publication_year: int,
) -> int:
    if not total_documents:
        return 0

    filled_fields = (
        documents_with_title
        + documents_with_pid
        + documents_with_filename
        + documents_with_publication_year
    )
    return round((filled_fields / (total_documents * 4)) * 100)


@router.get("/summary")
async def get_missingness_summary():
    db = LocalSessionLocal()
    try:
        total_documents = db.query(func.count(Document.id)).scalar() or 0
        documents_with_title = db.query(func.count(Document.id)).filter(Document.title.isnot(None), Document.title != "").scalar() or 0
        documents_with_pid = db.query(func.count(Document.id)).filter(Document.pid.isnot(None), Document.pid != "").scalar() or 0
        documents_with_filename = db.query(func.count(Document.id)).filter(Document.filename.isnot(None), Document.filename != "").scalar() or 0
        documents_with_publication_year = db.query(func.count(Document.id)).filter(Document.publication_year.isnot(None)).scalar() or 0
        metadata_score = calculate_metadata_coverage(
            total_documents,
            documents_with_title,
            documents_with_pid,
            documents_with_filename,
            documents_with_publication_year,
        )

        retrieved_document_count = db.query(func.count(func.distinct(DocumentChunk.document_id))).scalar() or 0

        counts_by_type = {
            row[0]: row[1]
            for row in db.query(MissingnessEvent.type, func.count(MissingnessEvent.id)).group_by(MissingnessEvent.type).all()
        }
        counts_by_status = {
            row[0]: row[1]
            for row in db.query(MissingnessEvent.status, func.count(MissingnessEvent.id)).group_by(MissingnessEvent.status).all()
        }

        institutional_gap_count = counts_by_type.get("institutional", 0)

        entity_table_exists = db.execute(select(func.to_regclass("public.entities"))).scalar()

        if entity_table_exists:
            entity_count = db.execute(text("SELECT COUNT(*) FROM entities")).scalar() or 0
            entity_presence_label = f"{entity_count} entity records available"
            provisional_fields = []
        else:
            entity_presence_label = "Provisional: entity persistence not yet available in this phase"
            provisional_fields = ["entity_presence_label"]

        completeness_cards = [
            {
                "label": "Local metadata coverage",
                "value": f"{metadata_score}%",
                "note": f"Title, PID, source filename, and publication year across {total_documents} local documents.",
            },
            {
                "label": "Local documents with chunks",
                "value": f"{retrieved_document_count}/{total_documents} documents with chunks" if total_documents else "0/0 documents with chunks",
                "note": "Local document representation in DocumentChunk. This is not frozen-corpus retrieval coverage.",
            },
            {
                "label": "Entity registry",
                "value": entity_presence_label,
                "note": "No records are currently stored in the local entity registry when this value is zero.",
            },
            {
                "label": "Institutional missingness events",
                "value": str(institutional_gap_count),
                "note": "Persisted MissingnessEvent rows of type institutional. Check event evidence and reviewer notes before interpretation.",
            },
        ]

        return {
            "metadata_completeness_score": metadata_score,
            "retrieval_coverage": {
                "documents_with_chunks": retrieved_document_count,
                "total_documents": total_documents,
                "label": f"{retrieved_document_count}/{total_documents} documents with chunks" if total_documents else "0/0 documents with chunks",
            },
            "entity_presence_label": entity_presence_label,
            "institutional_gap_count": institutional_gap_count,
            "counts_by_type": counts_by_type,
            "counts_by_status": counts_by_status,
            "provisional_fields": provisional_fields,
            "completeness_cards": completeness_cards,
        }
    finally:
        db.close()


@router.get("/events")
async def list_missingness_events(
    type: Optional[MissingnessType] = Query(default=None),
    status: Optional[MissingnessStatus] = Query(default=None),
    source_document_id: Optional[str] = Query(default=None),
):
    db = LocalSessionLocal()
    try:
        query = db.query(MissingnessEvent)

        if type:
            query = query.filter(MissingnessEvent.type == type)
        if status:
            query = query.filter(MissingnessEvent.status == status)
        if source_document_id:
            query = query.filter(MissingnessEvent.source_document_id == source_document_id)

        events = query.order_by(MissingnessEvent.created_at.desc()).all()
        return {
            "count": len(events),
            "events": [serialize_event(event) for event in events],
        }
    finally:
        db.close()


@router.post("/events", status_code=201)
async def create_missingness_event(request: MissingnessCreateRequest):
    db = LocalSessionLocal()
    try:
        event = MissingnessEvent(
            event_id=f"miss-{uuid.uuid4().hex[:12]}",
            type=request.type,
            query_or_entity_or_field=request.query_or_entity_or_field,
            evidence=request.evidence,
            query_id=request.query_id,
            source_document_id=request.source_document_id,
            source_chunk_id=request.source_chunk_id,
            status=request.status,
            reviewer_note=request.reviewer_note,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return serialize_event(event)
    finally:
        db.close()


@router.patch("/events/{event_id}")
async def update_missingness_event(event_id: str, request: MissingnessUpdateRequest):
    db = LocalSessionLocal()
    try:
        event = db.query(MissingnessEvent).filter(MissingnessEvent.event_id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Missingness event not found")

        if request.status is not None:
            event.status = request.status
        if request.reviewer_note is not None:
            event.reviewer_note = request.reviewer_note

        db.commit()
        db.refresh(event)
        return serialize_event(event)
    finally:
        db.close()