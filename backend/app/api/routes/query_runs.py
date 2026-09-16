import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.core.database import LocalSessionLocal
from app.models.research_outputs import Claim, ClaimEvidence, MissingnessEvent, QueryRun, QueryRunChunk, QueryRunExport
from app.services.provenance_service import ProvenanceService

router = APIRouter()
provenance_service = ProvenanceService()


class QueryRunSourceInput(BaseModel):
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    pid: Optional[str] = None
    title: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    excerpt: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None
    citation: Optional[Any] = None
    citation_text: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    provenance_json: Optional[dict[str, Any]] = None
    provenance_status: Optional[str] = None
    citation_status: Optional[str] = None


class QueryRunCreateRequest(BaseModel):
    query_id: Optional[str] = None
    prompt: str
    mode: Optional[str] = None
    model: Optional[str] = None
    response: Optional[str] = None
    caveats: Optional[list[str] | str] = None
    failed_or_partial: bool = False
    failure_reason: Optional[str] = None
    export_status: Optional[str] = None
    sources: list[QueryRunSourceInput] = []
    source_metadata: list[dict[str, Any]] = []
    citations: list[Any] = []
    page_ranges: list[Any] = []


class QueryRunClaimRequest(BaseModel):
    claim_text: str
    selected_chunk_ids: Optional[list[str]] = None
    caveats: Optional[str] = None


class QueryRunMissingnessRequest(BaseModel):
    reviewer_note: Optional[str] = None
    evidence_note: Optional[str] = None
    scope_note: Optional[str] = None
    follow_up_action: Optional[str] = None


def stringify_caveats(caveats: Optional[list[str] | str]) -> Optional[str]:
    if caveats is None:
      return None
    if isinstance(caveats, str):
      return caveats
    return " ".join(item for item in caveats if item).strip() or None


def build_citation_text(citation: Any) -> Optional[str]:
    if not citation:
        return None
    if isinstance(citation, str):
        return citation

    parts = [
        citation.get("title"),
        f"PID: {citation['pid']}" if citation.get("pid") else None,
        f"Page: {citation['page']}" if citation.get("page") else None,
        citation.get("section"),
        citation.get("public_url") or citation.get("publicUrl"),
    ]
    normalized = [part for part in parts if part]
    return " | ".join(normalized) if normalized else None


def serialize_run_chunk(chunk: QueryRunChunk) -> dict[str, Any]:
    source_metadata = chunk.source_metadata_json or {}
    return {
        "id": chunk.id,
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "page_range": chunk.page_range,
        "rank": chunk.rank,
        "score": chunk.score,
        "citation_text": chunk.citation_text,
        "provenance_json": chunk.provenance_json,
        "source_metadata": source_metadata,
        "provenance_available": chunk.provenance_json is not None,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
    }


def serialize_query_run(run: QueryRun, include_chunks: bool = False) -> dict[str, Any]:
    payload = {
        "query_id": run.query_id,
        "prompt": run.prompt,
        "mode": run.mode,
        "model": run.model,
        "response": run.response,
        "caveats": run.caveats,
        "failed_or_partial": bool(run.failed_or_partial),
        "failure_reason": run.failure_reason,
        "retrieved_chunk_count": run.retrieved_chunk_count,
        "export_status": run.export_status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
    if include_chunks:
        chunks = run.chunks or []
        payload["chunks"] = [serialize_run_chunk(chunk) for chunk in chunks]
        payload["citations"] = [chunk.citation_text for chunk in chunks if chunk.citation_text]
        payload["page_ranges"] = [chunk.page_range for chunk in chunks if chunk.page_range]
        payload["source_metadata"] = [chunk.source_metadata_json or {} for chunk in chunks]
    return payload


def get_query_run_or_404(db, query_id: str) -> QueryRun:
    run = db.query(QueryRun).filter(QueryRun.query_id == query_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Query run not found")
    return run


def build_markdown_export(run: QueryRun) -> str:
    chunks = run.chunks or []
    source_lines = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.source_metadata_json or {}
        source_lines.extend([
            f"### Source {index}",
            f"- Chunk ID: {chunk.chunk_id}",
            f"- Document ID: {chunk.document_id or metadata.get('documentId') or 'Unavailable'}",
            f"- Page range: {chunk.page_range or 'Unavailable'}",
            f"- Rank: {chunk.rank if chunk.rank is not None else 'Unavailable'}",
            f"- Score: {chunk.score if chunk.score is not None else 'Unavailable'}",
            f"- Citation: {chunk.citation_text or 'Unavailable'}",
            f"- Provenance: {'Available' if chunk.provenance_json else 'Unavailable'}",
            "",
        ])

    if not source_lines:
        source_lines = ["No source chunks were persisted for this interrogation.", ""]

    return "\n".join([
        "# Retrieval trail memo",
        "",
        f"- Query ID: {run.query_id}",
        f"- Timestamp: {run.created_at.isoformat() if run.created_at else datetime.utcnow().isoformat()}",
        f"- Model: {run.model or 'Unavailable'}",
        f"- Failed/partial: {'yes' if run.failed_or_partial else 'no'}",
        f"- Retrieved chunk count: {run.retrieved_chunk_count}",
        "",
        "## Query",
        "",
        run.prompt,
        "",
        "## Answer",
        "",
        run.response or "No answer was returned.",
        "",
        "## Caveats",
        "",
        run.caveats or run.failure_reason or "None recorded.",
        "",
        "## Retrieved source stack",
        "",
        *source_lines,
        "## Provenance note",
        "",
        "Provenance availability is recorded per chunk. Missing provenance is preserved as unavailable, not dropped.",
        "",
    ])


def record_export(db, query_id: str, export_type: str, export_payload: str) -> None:
    db.add(QueryRunExport(query_id=query_id, export_type=export_type, export_payload=export_payload))


def build_run_chunk_payload(source: QueryRunSourceInput, metadata_fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    metadata = metadata_fallback.copy() if metadata_fallback else {}
    if source.chunk_id:
        metadata.setdefault("chunkId", source.chunk_id)
    if source.document_id:
        metadata.setdefault("documentId", source.document_id)
    if source.pid:
        metadata.setdefault("pid", source.pid)
    if source.title:
        metadata.setdefault("title", source.title)
    if source.page is not None:
        metadata.setdefault("page", source.page)
    if source.section is not None:
        metadata.setdefault("section", source.section)
    if source.excerpt is not None:
        metadata.setdefault("excerpt", source.excerpt)
    if source.score is not None:
        metadata.setdefault("score", source.score)

    citation_text = source.citation_text or build_citation_text(source.citation)
    provenance_json = source.provenance_json or source.provenance
    document_id = source.document_id or metadata.get("documentId")
    page_range = None
    if source.page is not None:
        page_range = str(source.page)
    elif metadata.get("page") is not None:
        page_range = str(metadata.get("page"))

    try:
        if source.chunk_id and not citation_text:
            citation = provenance_service.build_chunk_citation(source.chunk_id)
            if citation:
                citation_text = build_citation_text(citation)
        if source.chunk_id and provenance_json is None:
            provenance_chain = provenance_service.get_chunk_provenance(source.chunk_id)
            if provenance_chain and provenance_chain.get("error") != "Chunk not found":
                provenance_json = provenance_chain
    except Exception:
        provenance_json = provenance_json if provenance_json is not None else None

    metadata.setdefault("citationStatus", source.citation_status or ("loaded" if citation_text else "unavailable"))
    metadata.setdefault("provenanceStatus", source.provenance_status or ("loaded" if provenance_json else "unavailable"))

    return {
        "chunk_id": source.chunk_id or metadata.get("chunkId") or f"unavailable-{uuid.uuid4().hex[:8]}",
        "document_id": document_id,
        "page_range": page_range,
        "rank": source.rank,
        "score": source.score,
        "citation_text": citation_text,
        "provenance_json": provenance_json,
        "source_metadata_json": metadata,
    }


def build_missingness_evidence(run: QueryRun) -> str:
    evidence_parts = [
        f"Source interrogation run {run.query_id} marked failed/partial.",
        f"Retrieved chunk count: {run.retrieved_chunk_count}.",
    ]

    if run.model:
        evidence_parts.append(f"Model: {run.model}.")
    if run.failure_reason:
        evidence_parts.append(f"Failure reason: {run.failure_reason}.")
    if run.caveats:
        evidence_parts.append(f"Caveats: {run.caveats}.")

    return " ".join(part.strip() for part in evidence_parts if part).strip()


def build_missingness_event_values(run: QueryRun, request: QueryRunMissingnessRequest) -> dict[str, Any]:
    document_ids = list(dict.fromkeys(chunk.document_id for chunk in run.chunks if chunk.document_id))
    chunk_ids = list(dict.fromkeys(chunk.chunk_id for chunk in run.chunks if chunk.chunk_id))
    scope_note = request.scope_note or (
        "This records a limitation of the current digitised corpus and retrieval run only; "
        "it does not establish that evidence never existed or that the people concerned did not respond."
    )
    evidence_note = request.evidence_note or build_missingness_evidence(run)
    return {
        "type": "retrieval",
        "query_or_entity_or_field": run.prompt,
        "evidence": f"{evidence_note.strip()} Scope/limit: {scope_note.strip()}",
        "query_id": run.query_id,
        "source_document_id": document_ids[0] if document_ids else None,
        "source_chunk_id": chunk_ids[0] if chunk_ids else None,
        "source_document_ids_json": document_ids,
        "source_chunk_ids_json": chunk_ids,
        "status": "open",
        "reviewer_note": request.reviewer_note or "Created from failed/partial Source Interrogation run.",
        "follow_up_action": request.follow_up_action,
    }


@router.get("")
@router.get("/")
async def list_query_runs():
    db = LocalSessionLocal()
    try:
        runs = db.query(QueryRun).order_by(QueryRun.created_at.desc()).limit(50).all()
        return {
            "count": len(runs),
            "query_runs": [
                {
                    "query_id": run.query_id,
                    "prompt": run.prompt,
                    "model": run.model,
                    "retrieved_chunk_count": run.retrieved_chunk_count,
                    "failed_or_partial": bool(run.failed_or_partial),
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                }
                for run in runs
            ],
        }
    finally:
        db.close()


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_query_run(request: QueryRunCreateRequest):
    db = LocalSessionLocal()
    try:
        query_id = request.query_id or f"query-{uuid.uuid4().hex[:12]}"
        existing = db.query(QueryRun).filter(QueryRun.query_id == query_id).first()
        if existing:
            for chunk in list(existing.chunks or []):
                db.delete(chunk)
            existing.prompt = request.prompt
            existing.mode = request.mode
            existing.model = request.model
            existing.response = request.response
            existing.caveats = stringify_caveats(request.caveats)
            existing.failed_or_partial = request.failed_or_partial
            existing.failure_reason = request.failure_reason
            existing.export_status = request.export_status
            run = existing
        else:
            run = QueryRun(
                query_id=query_id,
                prompt=request.prompt,
                mode=request.mode,
                model=request.model,
                response=request.response,
                caveats=stringify_caveats(request.caveats),
                failed_or_partial=request.failed_or_partial,
                failure_reason=request.failure_reason,
                export_status=request.export_status,
            )
            db.add(run)

        sources = request.sources or []
        metadata_rows = request.source_metadata or []
        persisted_chunks = []
        for index, source in enumerate(sources):
            metadata_fallback = metadata_rows[index] if index < len(metadata_rows) else None
            chunk_payload = build_run_chunk_payload(source, metadata_fallback=metadata_fallback)
            persisted_chunks.append(QueryRunChunk(query_id=query_id, **chunk_payload))

        for chunk in persisted_chunks:
            db.add(chunk)

        run.retrieved_chunk_count = len(persisted_chunks)
        if run.retrieved_chunk_count == 0 and not run.failure_reason:
            run.failure_reason = "No supporting source chunks were returned."
            run.failed_or_partial = True

        db.commit()
        db.refresh(run)
        return serialize_query_run(run, include_chunks=True)
    finally:
        db.close()


@router.get("/{query_id}")
async def get_query_run(query_id: str):
    db = LocalSessionLocal()
    try:
        run = get_query_run_or_404(db, query_id)
        return serialize_query_run(run, include_chunks=True)
    finally:
        db.close()


@router.get("/{query_id}/export.json")
async def export_query_run_json(query_id: str):
    db = LocalSessionLocal()
    try:
        run = get_query_run_or_404(db, query_id)
        payload = json.dumps(serialize_query_run(run, include_chunks=True), indent=2) + "\n"
        record_export(db, query_id, "json", payload)
        run.export_status = "json"
        db.commit()
        return PlainTextResponse(
            payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{query_id}.json"'},
        )
    finally:
        db.close()


@router.get("/{query_id}/export.md")
async def export_query_run_markdown(query_id: str):
    db = LocalSessionLocal()
    try:
        run = get_query_run_or_404(db, query_id)
        payload = build_markdown_export(run)
        record_export(db, query_id, "markdown", payload)
        run.export_status = "markdown"
        db.commit()
        return PlainTextResponse(
            payload,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{query_id}.md"'},
        )
    finally:
        db.close()


@router.post("/{query_id}/create-claim", status_code=201)
async def create_claim_from_query_run(query_id: str, request: QueryRunClaimRequest):
    db = LocalSessionLocal()
    try:
        run = get_query_run_or_404(db, query_id)
        selected_chunk_ids = request.selected_chunk_ids or []
        evidence_rows = []
        if selected_chunk_ids:
            evidence_rows = db.query(QueryRunChunk).filter(
                QueryRunChunk.query_id == query_id,
                QueryRunChunk.chunk_id.in_(selected_chunk_ids),
            ).all()

        has_evidence = len(evidence_rows) > 0
        claim = Claim(
            claim_id=f"claim-{uuid.uuid4().hex[:12]}",
            claim_text=request.claim_text,
            support_level="partially_supported" if has_evidence else "unresolved",
            caveats=request.caveats,
            reviewer_status="draft" if has_evidence else "needs_evidence",
        )
        db.add(claim)
        db.flush()

        for evidence_row in evidence_rows:
            db.add(
                ClaimEvidence(
                    claim_id=claim.claim_id,
                    chunk_id=evidence_row.chunk_id,
                    document_id=evidence_row.document_id,
                    page_range=evidence_row.page_range,
                    citation_text=evidence_row.citation_text,
                    provenance_json=evidence_row.provenance_json,
                )
            )

        db.commit()
        db.refresh(claim)
        return {
            "claim_id": claim.claim_id,
            "query_id": run.query_id,
            "support_level": claim.support_level,
            "reviewer_status": claim.reviewer_status,
            "evidence_count": len(evidence_rows),
        }
    finally:
        db.close()


@router.post("/{query_id}/create-missingness-event", status_code=201)
async def create_missingness_event_from_query_run(query_id: str, request: QueryRunMissingnessRequest):
    db = LocalSessionLocal()
    try:
        run = get_query_run_or_404(db, query_id)

        if not run.failed_or_partial and run.retrieved_chunk_count > 0:
            raise HTTPException(
                status_code=400,
                detail="This query run is not marked as failed/partial and cannot be classified as retrieval missingness.",
            )

        event = MissingnessEvent(
            event_id=f"miss-{uuid.uuid4().hex[:12]}",
            **build_missingness_event_values(run, request),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        return {
            "id": event.id,
            "event_id": event.event_id,
            "query_id": event.query_id,
            "type": event.type,
            "query_or_entity_or_field": event.query_or_entity_or_field,
            "evidence": event.evidence,
            "source_document_id": event.source_document_id,
            "source_chunk_id": event.source_chunk_id,
            "source_document_ids": event.source_document_ids_json or [],
            "source_chunk_ids": event.source_chunk_ids_json or [],
            "status": event.status,
            "reviewer_note": event.reviewer_note,
            "follow_up_action": event.follow_up_action,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        }
    finally:
        db.close()