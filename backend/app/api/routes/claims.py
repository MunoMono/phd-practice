import csv
import io
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.core.database import LocalSessionLocal
from app.models.document import DocumentChunk
from app.models.research_outputs import Claim, ClaimEvidence
from app.services.provenance_service import ProvenanceService

router = APIRouter()
provenance_service = ProvenanceService()

SupportLevel = Literal["supported", "partially_supported", "unresolved", "unsupported"]
ReviewerStatus = Literal["draft", "in_review", "ready_for_supervisor_review", "needs_evidence"]


class ClaimCreateRequest(BaseModel):
    claim_text: str
    support_level: SupportLevel = "unresolved"
    caveats: Optional[str] = None
    reviewer_status: ReviewerStatus = "draft"


class ClaimUpdateRequest(BaseModel):
    claim_text: Optional[str] = None
    support_level: Optional[SupportLevel] = None
    caveats: Optional[str] = None
    reviewer_status: Optional[ReviewerStatus] = None


class ClaimEvidenceCreateRequest(BaseModel):
    chunk_id: str
    document_id: Optional[str] = None
    page_range: Optional[str] = None
    citation_text: Optional[str] = None
    provenance_json: Optional[dict[str, Any]] = None


def serialize_evidence(evidence: ClaimEvidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "claim_id": evidence.claim_id,
        "chunk_id": evidence.chunk_id,
        "document_id": evidence.document_id,
        "page_range": evidence.page_range,
        "citation_text": evidence.citation_text,
        "provenance_json": evidence.provenance_json,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }


def serialize_claim(claim: Claim, include_evidence: bool = False) -> dict[str, Any]:
    evidence_rows = claim.evidence or []
    payload = {
        "id": claim.id,
        "claim_id": claim.claim_id,
        "claim_text": claim.claim_text,
        "support_level": claim.support_level,
        "caveats": claim.caveats,
        "reviewer_status": claim.reviewer_status,
        "evidence_count": len(evidence_rows),
        "evidence_chunk_ids": [row.chunk_id for row in evidence_rows],
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }
    if include_evidence:
        payload["evidence"] = [serialize_evidence(row) for row in evidence_rows]
    return payload


def build_citation_text(citation: dict[str, Any]) -> str:
    return " | ".join(
        part
        for part in [
            str(citation.get("title") or "Untitled chunk citation"),
            f"PID: {citation['pid']}" if citation.get("pid") else None,
            f"Page: {citation['page']}" if citation.get("page") else None,
            citation.get("public_url"),
        ]
        if part
    )


def get_claim_or_404(db, claim_id: str) -> Claim:
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


def get_export_payload(db) -> list[dict[str, Any]]:
    claims = db.query(Claim).order_by(Claim.created_at.asc()).all()
    export_rows: list[dict[str, Any]] = []

    for claim in claims:
        evidence_rows = claim.evidence or []
        has_evidence = len(evidence_rows) > 0
        downgraded = claim.support_level == "supported" and not has_evidence
        support_level = "unresolved" if downgraded else claim.support_level
        caveat_parts = [claim.caveats.strip()] if claim.caveats else []
        if downgraded:
            caveat_parts.append("Export downgraded because no evidence chunk is attached.")

        export_rows.append(
            {
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text,
                "support_level": support_level,
                "reviewer_status": claim.reviewer_status,
                "caveats": " ".join(part for part in caveat_parts if part).strip() or None,
                "evidence_count": len(evidence_rows),
                "evidence_chunk_ids": [row.chunk_id for row in evidence_rows],
                "evidence": [serialize_evidence(row) for row in evidence_rows],
                "was_downgraded_on_export": downgraded,
            }
        )

    return export_rows


@router.get("")
@router.get("/")
async def list_claims():
    db = LocalSessionLocal()
    try:
        claims = db.query(Claim).order_by(Claim.created_at.asc()).all()
        return {
            "count": len(claims),
            "claims": [serialize_claim(claim) for claim in claims],
        }
    finally:
        db.close()


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_claim(request: ClaimCreateRequest):
    db = LocalSessionLocal()
    try:
        claim = Claim(
            claim_id=f"claim-{uuid.uuid4().hex[:12]}",
            claim_text=request.claim_text,
            support_level=request.support_level,
            caveats=request.caveats,
            reviewer_status=request.reviewer_status,
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)
        return serialize_claim(claim, include_evidence=True)
    finally:
        db.close()


@router.get("/export.csv")
async def export_claims_csv():
    db = LocalSessionLocal()
    try:
        rows = get_export_payload(db)
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "claim_id",
                "claim_text",
                "support_level",
                "reviewer_status",
                "caveats",
                "evidence_count",
                "evidence_chunk_ids",
                "was_downgraded_on_export",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "claim_id": row["claim_id"],
                    "claim_text": row["claim_text"],
                    "support_level": row["support_level"],
                    "reviewer_status": row["reviewer_status"],
                    "caveats": row["caveats"] or "",
                    "evidence_count": row["evidence_count"],
                    "evidence_chunk_ids": ", ".join(row["evidence_chunk_ids"]),
                    "was_downgraded_on_export": str(row["was_downgraded_on_export"]).lower(),
                }
            )

        return PlainTextResponse(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="claim-evidence-matrix.csv"'},
        )
    finally:
        db.close()


@router.get("/export.md")
async def export_claims_markdown():
    db = LocalSessionLocal()
    try:
        rows = get_export_payload(db)
        blocks = []
        for row in rows:
            blocks.append(
                "\n".join(
                    [
                        f"## {row['claim_id']}",
                        f"- Claim: {row['claim_text']}",
                        f"- Support level: {row['support_level']}",
                        f"- Reviewer status: {row['reviewer_status']}",
                        f"- Evidence chunks: {', '.join(row['evidence_chunk_ids']) if row['evidence_chunk_ids'] else 'None attached'}",
                        f"- Caveats: {row['caveats'] or 'None'}",
                        f"- Export downgraded: {'yes' if row['was_downgraded_on_export'] else 'no'}",
                    ]
                )
            )

        content = "# Claim-evidence matrix\n\n" + "\n\n".join(blocks) + "\n"
        return PlainTextResponse(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="claim-evidence-matrix.md"'},
        )
    finally:
        db.close()


@router.get("/{claim_id}")
async def get_claim_detail(claim_id: str):
    db = LocalSessionLocal()
    try:
        claim = get_claim_or_404(db, claim_id)
        return serialize_claim(claim, include_evidence=True)
    finally:
        db.close()


@router.patch("/{claim_id}")
async def update_claim(claim_id: str, request: ClaimUpdateRequest):
    db = LocalSessionLocal()
    try:
        claim = get_claim_or_404(db, claim_id)

        if request.claim_text is not None:
            claim.claim_text = request.claim_text
        if request.support_level is not None:
            claim.support_level = request.support_level
        if request.caveats is not None:
            claim.caveats = request.caveats
        if request.reviewer_status is not None:
            claim.reviewer_status = request.reviewer_status

        db.commit()
        db.refresh(claim)
        return serialize_claim(claim, include_evidence=True)
    finally:
        db.close()


@router.post("/{claim_id}/evidence", status_code=201)
async def attach_claim_evidence(claim_id: str, request: ClaimEvidenceCreateRequest):
    db = LocalSessionLocal()
    try:
        claim = get_claim_or_404(db, claim_id)

        existing = db.query(ClaimEvidence).filter(
            ClaimEvidence.claim_id == claim.claim_id,
            ClaimEvidence.chunk_id == request.chunk_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Evidence chunk already attached to claim")

        chunk = db.query(DocumentChunk).filter(DocumentChunk.chunk_id == request.chunk_id).first()

        citation_text = request.citation_text
        provenance_json = request.provenance_json
        document_id = request.document_id or (chunk.document_id if chunk else None)
        page_range = request.page_range or (str(chunk.source_page) if chunk and chunk.source_page is not None else None)

        try:
            if not citation_text:
                citation = provenance_service.build_chunk_citation(request.chunk_id)
                if citation:
                    citation_text = build_citation_text(citation)
            if provenance_json is None:
                provenance_chain = provenance_service.get_chunk_provenance(request.chunk_id)
                if provenance_chain and provenance_chain.get("error") != "Chunk not found":
                    provenance_json = provenance_chain
        except Exception:
            provenance_json = provenance_json if provenance_json is not None else None

        evidence = ClaimEvidence(
            claim_id=claim.claim_id,
            chunk_id=request.chunk_id,
            document_id=document_id,
            page_range=page_range,
            citation_text=citation_text,
            provenance_json=provenance_json,
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        return serialize_evidence(evidence)
    finally:
        db.close()


@router.delete("/{claim_id}/evidence/{evidence_id}")
async def remove_claim_evidence(claim_id: str, evidence_id: int):
    db = LocalSessionLocal()
    try:
        get_claim_or_404(db, claim_id)
        evidence = db.query(ClaimEvidence).filter(
            ClaimEvidence.id == evidence_id,
            ClaimEvidence.claim_id == claim_id,
        ).first()
        if not evidence:
            raise HTTPException(status_code=404, detail="Claim evidence not found")

        db.delete(evidence)
        db.commit()
        return {"message": "Claim evidence removed", "evidence_id": evidence_id}
    finally:
        db.close()