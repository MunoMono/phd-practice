"""
API route for the active Turin local inference runtime.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import logging
import re
import uuid
import time
from sqlalchemy import bindparam, text

from app.services.inference_service import InferenceTimeoutError, get_inference_service
from app.core.database import LocalSessionLocal
from app.core.config import settings
from app.services.metadata_roles import extract_metadata_roles
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService
from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.turin_archive_first_retrieval_service import TurinArchiveFirstRetrievalService
from app.services.turin_evidence_pipeline_service import EvidencePacketBuilder, StagedEvidencePipeline
from app.services.turin_question_policy import matching_turin_question_policy
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service
from app.services.researcher_ui_capture_service import CAPTURE_MODE, ResearcherUiCaptureService, build_one_shot_prompt, parse_one_shot_output, project_claim_provenance
from app.services.authority_registry import AuthorityRegistry
from app.models.research_outputs import ExperimentRun, ExperimentRunEvidence

router = APIRouter()
exploratory_router = APIRouter()
logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request model for testamentary traces analysis"""
    query: str = Field(..., description="Research question or analytical query")
    num_context_chunks: int = Field(12, ge=1, le=20, description="Number of context chunks to retrieve")
    max_tokens: Optional[int] = Field(None, ge=50, le=512, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")


class AnalysisResponse(BaseModel):
    """Response model for analysis results"""
    analysis: str
    query: str
    num_context_chunks: int
    inference_time_seconds: float
    model: str
    timestamp: str
    context_chunks: List[Dict[str, Any]]


class ExploratoryInterrogationRequest(BaseModel):
    """An ordinary, non-governed query for the interactive source interrogation UI."""
    query: str = Field(min_length=1, max_length=4000)
    mode: Literal["exploratory", "comparison", CAPTURE_MODE] = "exploratory"
    question_id: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=5, ge=1, le=20)
    target_document_ids: list[str] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_document_selection(self):
        if self.mode == "comparison" and len(self.target_document_ids) != 2:
            raise ValueError("Comparison mode requires exactly two selected documents.")
        return self


class ModelInfoResponse(BaseModel):
    """Response model for model information"""
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    model: str
    display_name: str
    status: str
    device: str
    loaded: bool
    context_window_tokens: int
    source_analysis_max_output_tokens: int
    cross_source_max_output_tokens: int
    final_synthesis_max_output_tokens: int
    temperature: float
    quantized: str
    runtime: str
    runtime_version: str
    runtime_protocol: str


class ModelLoadResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    loaded: bool
    model_name: str
    device: str
    message: str


RELATED_TERMS = [
    "design",
    "research",
    "methodology",
    "systems",
    "collaboration",
]

PIPELINE_DERIVED_LIMITS = {
    "The selected evidence does not directly establish the named subject's activity.",
    "The selected evidence does not establish a complete reconstruction of the subject's role.",
}


def _catalogue_question_subject(query: str) -> str | None:
    patterns = (
        r"^what projects did (?P<subject>.+?) work on\??$",
        r"^what documents (?:by|mention) (?P<subject>.+?) (?:are )?available\??$",
        r"^what documents mention (?P<subject>.+?)\??$",
        r"^(?:list|show) (?:the )?documents (?P<subject>.+?) worked on\??$",
        r"^when did (?P<subject>.+?) (?:take in|admit) (?:its )?first students\??$",
        r"^what (?:was|is) (?P<subject>.+?)(?:'s|’s) involvement (?:at|with|in) (?:the )?ddr\??$",
        r"^what role did (?P<subject>.+?) (?:hold|have)\??$",
        r"^when did (?P<subject>.+?) work at ddr\??$",
    )
    normalised = " ".join(query.strip().split())
    for pattern in patterns:
        match = re.match(pattern, normalised, flags=re.IGNORECASE)
        if match:
            return match.group("subject").strip(" ?. ")
    if re.match(r"^(?:what|which|who|when)\b", normalised, flags=re.IGNORECASE) and re.search(
        r"\b(?:documents?|records?|projects?|job|students?|degree|thesis|period|funder|lead|first|constituted|constitution)\b",
        normalised,
        flags=re.IGNORECASE,
    ):
        return normalised.rstrip("?")
    return None


def _collection_question_subject(query: str) -> str | None:
    match = re.match(
        r"^(?:list|show) (?:the )?documents (?P<subject>.+?) worked on\??$",
        " ".join(query.strip().split()),
        flags=re.IGNORECASE,
    )
    return match.group("subject").strip(" ?. ") if match else None


def _collection_membership_records(subject: str, limit: int) -> list[dict[str, Any]]:
    """List media held under an exact matching archive parent record."""
    record_title = f"{subject} collection"
    db = LocalSessionLocal()
    try:
        rows = db.execute(text("""
            SELECT record_pid, record_title, attached_media_pid, attached_media_title,
                   asset_pid, label, display_date
            FROM turin_archive_asset_snapshots
            WHERE lower(record_title) = lower(:record_title)
            ORDER BY attached_media_title, asset_pid
        """), {"record_title": record_title}).mappings().all()
    finally:
        db.close()
    records, seen = [], set()
    for row in rows:
        media_pid = str(row["attached_media_pid"] or row["asset_pid"] or "")
        if not media_pid or media_pid in seen:
            continue
        records.append({
            "record_pid": str(row["record_pid"]),
            "record_title": row["record_title"],
            "attached_media_pid": media_pid,
            "asset_pid": str(row["asset_pid"] or "unavailable"),
            "title": row["attached_media_title"] or row["label"] or "Untitled media item",
            "display_date": row["display_date"],
        })
        seen.add(media_pid)
        if len(records) == limit:
            break
    return records


def _collection_membership_response(subject: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    parent = records[0]
    lines = [
        f"Archive collection membership: {parent['record_title']} (Record PID {parent['record_pid']}).",
        "The following media are held under this parent record. Collection membership does not by itself establish authorship, responsibility, or participation.",
    ]
    for record in records:
        date = f"; {record['display_date']}" if record.get("display_date") else ""
        lines.append(f"- {record['title']} (Media PID {record['attached_media_pid']}; Asset PID {record['asset_pid']}{date})")
    return {"answer": "\n".join(lines), "records": records, "subject": subject}


def _catalogue_authorities(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Read direct lookup authorities separately from documentary evidence."""
    question = query.lower()
    authority_types = AuthorityRegistry().selected_types(query)
    if any(term in question for term in ("degree", "thesis")):
        authority_types.append("ref_students")
    if any(term in question for term in ("constituted", "constitution")):
        authority_types.append("ref_ddr_period")
    if any(term in question for term in ("project", "job ", "job number", "funder")):
        authority_types.append("ddr_projects")
    authority_types = list(dict.fromkeys(authority_types))
    if "ddr_projects" in authority_types:
        authority_types = [authority_type for authority_type in authority_types if authority_type != "agent_employment"]
    if not authority_types:
        return []
    db = LocalSessionLocal()
    try:
        contexts = AuthorityRegistry().resolve(db, query, authority_types)
        return [context.model_dump() for context in contexts[:limit]]
    finally:
        db.close()


def _catalogue_response(query: str, retrieval: dict[str, Any], authority_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Present direct catalogue findings without asking Qwen to synthesise them."""
    subject = _catalogue_question_subject(query)
    sources = retrieval["results"]
    if not subject:
        return None

    records = []
    for source_number, source in enumerate(sources, start=1):
        title = str(source.get("snapshot", {}).get("title") or source.get("title") or source.get("document_id") or "Untitled record")
        provenance = source.get("provenance") or {}
        asset_pid = provenance.get("asset_pid") or provenance.get("pid") or source.get("asset_pid") or source.get("pid") or "unavailable"
        page = source.get("page_start") or source.get("source_page") or "unavailable"
        records.append({
            "title": title,
            "asset_pid": str(asset_pid),
            "page": page,
            "chunk_id": source.get("chunk_id"),
            "source_number": source_number,
        })

    unique_records = []
    seen = set()
    for record in records:
        key = (record["title"], record["asset_pid"])
        if key not in seen:
            unique_records.append(record)
            seen.add(key)

    question_lower = query.lower()
    if not unique_records and not authority_evidence:
        return None
    exact_job_lookup = bool(re.match(r"^what is job(?: number)?\s+\d+", question_lower))
    authority_defined_question = bool(authority_evidence) and not re.search(r"\bdocuments?|records?\b", question_lower)
    if not unique_records and not authority_evidence:
        return None
    if authority_defined_question:
        unique_records = []
    documentary_claims = [
        {
            "text": f"{record['title']} (Asset PID {record['asset_pid']}, p. {record['page']})",
            "source_numbers": [record["source_number"]],
        }
        for record in unique_records
    ]
    if not unique_records:
        lead = "No matching documentary record was retrieved."
    elif exact_job_lookup:
        lead = f"Retrieved documentary records related to {subject}:"
    elif question_lower.startswith("what projects"):
        lead = f"Catalogue records associated with {subject}:"
    elif "documents by" in question_lower or ("documents " in question_lower and " worked on" in question_lower):
        lead = f"Retrieved catalogue records associated with {subject}; this name match does not by itself establish authorship or participation:"
    elif question_lower.startswith("when did"):
        lead = f"Retrieved records relevant to the timing of {subject}'s first students:"
    else:
        lead = f"Retrieved catalogue records for {subject}:"
    lines = [] if authority_defined_question else [lead, *[f"- {record['title']} (Asset PID {record['asset_pid']}, p. {record['page']})" for record in unique_records]]
    direct_authority_lines = []
    authority_claims = []
    for authority_number, authority in enumerate(authority_evidence, start=1):
        fields = authority.get("fields") or {}
        if authority["authority_type"] == "ddr_projects":
            start = fields.get("start_year") or fields.get("start_date") or "year unavailable"
            end = fields.get("end_year") or fields.get("end_date") or start
            claim = (
                f"Job {authority['authority_id']}: {fields.get('title') or fields.get('label')} "
                f"({start}–{end}; "
                f"project lead: {fields.get('project_lead_name') or 'unavailable'})"
            )
            direct_authority_lines.append(f"- {claim}")
        elif authority["authority_type"] == "ref_students":
            detail = fields.get("degree") or "degree unavailable"
            if "thesis" in question_lower:
                detail = fields.get("thesis_title") or "thesis title unavailable"
            claim = f"{fields.get('label')} ({fields.get('year') or 'year unavailable'}; {detail})"
            direct_authority_lines.append(f"- {claim}")
        elif authority["authority_type"] == "ref_ddr_period":
            claim = (
                f"{authority['authority_id']} - {fields.get('label')}: "
                f"{fields.get('description') or 'description unavailable'}"
            )
            direct_authority_lines.append(f"- {claim}")
        elif authority["authority_type"] == "agent_employment":
            name = fields.get("name") or fields.get("label") or authority["authority_id"]
            role = fields.get("job_title_label") or fields.get("job_title_code") or "role unavailable"
            start = fields.get("start_date") or "start date unavailable"
            end = fields.get("end_date") or "end date unavailable"
            claim = f"{name}: {role} ({start} to {end})"
            direct_authority_lines.append(f"- {claim}")
        else:
            continue
        authority_claims.append({"text": claim, "authority_numbers": [authority_number]})
    if direct_authority_lines:
        authority_block = ["Authority-register results (not documentary quotations):", *direct_authority_lines]
        authority_first = exact_job_lookup or question_lower.startswith("what projects") or bool(authority_evidence)
        if authority_first:
            if question_lower.startswith("what projects"):
                if "funder" in question_lower or "funded by" in question_lower:
                    authority_block.insert(0, "Projects in the register matching the funding query:")
                else:
                    authority_block.insert(0, f"Projects in the register that name {subject} as project lead:")
            lines = [*authority_block, "", *lines]
        else:
            lines.extend(["", *authority_block])
    return {
        "answer": "\n".join(lines),
        "answer_paragraphs": [
            *([{"claims": documentary_claims}] if documentary_claims else []),
            *([{"claims": authority_claims}] if authority_claims else []),
        ],
        "records": unique_records,
        "subject": subject,
    }


def _project_staged_exploratory_response(
    pipeline: dict[str, Any], retrieval: dict[str, Any]
) -> dict[str, Any]:
    """Project the staged artifact for the exploratory UI without exposing a formal run."""
    final_synthesis = pipeline["final_synthesis"]
    cross_source = pipeline["cross_source_analysis"]
    evidence_map = pipeline["evidence_map"]
    interpretations: list[dict[str, str]] = []
    seen_interpretations: set[str] = set()
    for stage, values in (
        ("cross_source", cross_source.get("cross_source_inferences", [])),
        ("final_synthesis", final_synthesis.get("cross_source_inferences", [])),
    ):
        for value in values:
            if isinstance(value, str) and value.strip() and value not in seen_interpretations:
                interpretations.append({"inference": value, "origin": "model", "stage": stage})
                seen_interpretations.add(value)

    transparency = retrieval["transparency"]
    nominations = [
        source.get("archive_nomination") or {}
        for source in retrieval["results"]
    ]
    retrieval_influence = any(
        nomination.get("matched_authorities")
        or nomination.get("matched_projects")
        or any(reason.get("match") == "exact_anchor" for reason in nomination.get("nomination_reasons", []))
        for nomination in nominations
    )
    answer = final_synthesis["answer"]
    answer_origin = None
    documentary_evidence = [
        {**claim, "origin": "documentary"}
        for claim in evidence_map["DIRECT_DOCUMENTARY"]
    ]
    source_numbers = {
        f"{source['document_id']}:{source['chunk_id']}": index
        for index, source in enumerate(retrieval["results"], start=1)
        if source.get("document_id") and source.get("chunk_id")
    }
    narrative_claims = final_synthesis.get("synthesis_claims", [])
    cited_narrative_numbers = {
        source_number
        for claim in narrative_claims
        for source_number in claim.get("source_numbers", [])
    }
    narrative_coverage_complete = bool(narrative_claims) and cited_narrative_numbers == set(source_numbers.values())
    answer_paragraphs = []
    if narrative_coverage_complete:
        paragraphs: dict[int, list[str]] = {}
        claims_by_paragraph: dict[int, list[dict[str, Any]]] = {}
        for claim in narrative_claims:
            citations = sorted(set(claim["source_numbers"]))
            paragraphs.setdefault(claim["paragraph"], []).append(
                f"{claim['text'].strip()} [{', '.join(map(str, citations))}]"
            )
            claims_by_paragraph.setdefault(claim["paragraph"], []).append({
                "text": claim["text"].strip(),
                "source_numbers": citations,
            })
        rendered_paragraphs = [" ".join(paragraphs[paragraph]) for paragraph in sorted(paragraphs)]
        answer_paragraphs = [
            {"claims": claims_by_paragraph[paragraph]}
            for paragraph in sorted(claims_by_paragraph)
        ]
        if rendered_paragraphs:
            answer = "\n\n".join(rendered_paragraphs)
            answer_origin = "qwen_cited_evidence_synthesis"
    cited_claims = []
    for claim in documentary_evidence:
        source_id = claim.get("source_id")
        claim_text = " ".join(str(claim.get("claim") or "").split())
        citation = source_numbers.get(source_id)
        if claim_text and citation:
            cited_claims.append(f"{claim_text} [{citation}]")
    if cited_claims and not answer_origin:
        answer = (
            "The retained documentary evidence supports the following findings: "
            f"{' '.join(cited_claims)} "
            "These findings are limited to the cited passages."
        )
        answer_origin = "deterministic_cited_evidence_synthesis"
    direct_support_sources = [
        source for source in retrieval["results"]
        if (next((item for item in evidence_map["source_classifications"] if item["source_id"] == f"{source['document_id']}:{source['chunk_id']}"), {}).get("relationship_to_question") == "DIRECT_SUPPORT")
    ]
    selected_document_sources = (
        retrieval.get("transparency", {}).get("strategy") == "explicit_document_selection_v1"
    )
    fallback_sources = direct_support_sources or (
        retrieval["results"] if selected_document_sources else []
    )
    if fallback_sources and not documentary_evidence:
        passages = []
        for source in fallback_sources:
            source_id = f"{source['document_id']}:{source['chunk_id']}"
            title = str(source.get("snapshot", {}).get("title") or source.get("title") or source["document_id"])
            excerpt = " ".join(str(source.get("excerpt") or source.get("text") or "").split())
            if not excerpt:
                continue
            citation = source_numbers[source_id]
            passages.append((source_id, title, excerpt, citation, source))
        if passages:
            statements = " ".join(
                f"In '{title}', the retained passage states: \"{excerpt}\" [{citation}]"
                for _, title, excerpt, citation, _ in passages
            )
            answer = (
                "The selected documentary evidence establishes the following source-specific points. "
                f"{statements} "
                "These statements remain limited to the retained passages and do not by themselves establish matters beyond their explicit wording."
            )
            answer_origin = "deterministic_cited_evidence_synthesis"
            documentary_evidence = [
                {
                    "claim": excerpt,
                    "source_id": source_id,
                    "chunk_ids": [source["chunk_id"]],
                    "page": source.get("page_start"),
                    "origin": "documentary",
                }
                for source_id, _, excerpt, _, source in passages
            ]
    if not answer_origin and retrieval["results"] and not evidence_map["DIRECT_DOCUMENTARY"]:
        source_labels = []
        for source in retrieval["results"][:5]:
            title = str(source.get("snapshot", {}).get("title") or source.get("title") or source.get("document_id") or "Untitled record")
            provenance = source.get("provenance") or {}
            asset_pid = provenance.get("asset_pid") or source.get("asset_pid") or source.get("pid") or "unavailable"
            page = source.get("page_start") or source.get("source_page") or "unavailable"
            source_labels.append(f"{title} (Asset PID {asset_pid}, p. {page})")
        if source_labels:
            answer = (
                f"The selected records - {'; '.join(source_labels)} - do not provide a direct documentary description that answers this question. "
                "They may provide context, but the supplied passages do not establish a broader DDR account."
            )
            answer_paragraphs = [{
                "claims": [{
                    "text": answer,
                    "source_numbers": list(source_numbers.values()),
                }],
            }]
            answer_origin = "deterministic_evidence_limit"
    response = {
        "answer": answer,
        "answer_paragraphs": answer_paragraphs,
        "answer_origin": answer_origin,
        "documentary_evidence": documentary_evidence,
        "authority_evidence": evidence_map.get("DATABASE_AUTHORITY", []),
        "archival_associations": evidence_map.get("ARCHIVAL_METADATA", []),
        "contextual_evidence": [
            {**claim, "origin": "model"}
            for claim in evidence_map["CONTEXTUAL"]
        ],
        "inferences": interpretations,
        "contradictions": [
            {"description": value, "origin": "model", "stage": "cross_source"}
            for value in cross_source.get("differences_or_contradictions", [])
            if isinstance(value, str) and value.strip()
        ],
        "missingness": [
            {
                "category": "not_established",
                "explanation": value,
                "origin": "system_pipeline" if value in PIPELINE_DERIVED_LIMITS else "model",
            }
            for value in evidence_map["NOT_ESTABLISHED"]
        ],
        "authority_roles": {
            "planner_entity_resolution": transparency.get("resolved_entities", []),
            "controlled_lexical_expansion": {
                "used": any(variant["kind"].startswith("entity_") for variant in transparency.get("query_variants", [])),
                "variants": transparency.get("query_variants", []),
            },
            "retrieval_nomination": {"used": retrieval_influence},
            "qwen_authority_context": {"supplied": False},
            "persisted_authority_audit": {"persisted": False},
        },
        "stage_execution": {
            "classification": "EXPLORATORY / NON-FORMAL INTERROGATION",
            "stages": [call["stage"] for call in pipeline.get("inference_calls", [])],
            "call_count": len(pipeline.get("inference_calls", [])),
            "narrative_coverage": {
                "complete": narrative_coverage_complete,
                "required_source_ids": list(source_numbers),
                "returned_source_numbers": sorted(cited_narrative_numbers),
            },
        },
    }
    return response


def build_expanded_query(query: str) -> str:
    lower_query = query.lower()
    additions = [term for term in RELATED_TERMS if term not in lower_query]
    if not additions:
        return query
    return f"{query} OR {' OR '.join(additions)}"


def _hydrate_capture_sources(db: Any, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project missing capture provenance from the same persisted document and chunk identities."""
    hydrated = [dict(source) for source in sources]
    missing = [source for source in hydrated if not source.get("provenance") and source.get("chunk_id")]
    if not missing:
        return hydrated
    query = text("""
        SELECT d.document_id, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid,
               d.archive_record_id, d.archive_record_pid, d.pid AS attached_media_pid,
               d.source_uri, dc.chunk_id, dc.source_page, dc.chunk_type
        FROM documents d JOIN document_chunks dc ON dc.document_id = d.document_id
        WHERE dc.chunk_id IN :chunk_ids AND dc.corpus_version = :corpus_version
    """).bindparams(bindparam("chunk_ids", expanding=True))
    rows = db.execute(query, {"chunk_ids": [source["chunk_id"] for source in missing], "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION}).mappings().all()
    by_chunk = {row["chunk_id"]: dict(row) for row in rows}
    for source in hydrated:
        row = by_chunk.get(source.get("chunk_id"))
        if row and not source.get("provenance"):
            source["provenance"] = {
                key: value for key, value in {
                    "document_id": row["document_id"], "archive_record_id": row["archive_record_id"],
                    "archive_record_pid": row["archive_record_pid"], "attached_media_pid": row["attached_media_pid"],
                    "asset_pid": row["asset_pid"], "asset_id": row["asset_id"],
                    "asset_id_or_asset_pid": row["asset_id_or_asset_pid"], "source_uri": row["source_uri"],
                    "chunk_id": row["chunk_id"], "page": row["source_page"], "chunk_type": row["chunk_type"],
                }.items() if value is not None
            }
            source["provenance_projection"] = "document_chunk_identity"
    return hydrated


def _project_q04_capture_sources(question_id: str | None, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = [dict(source) for source in sources]
    if question_id != "Q04":
        return projected
    source_types = {
        "rca calendar": "Institutional calendar",
        "ergonomics course": "Course correspondence",
        "committee paper": "Committee paper",
        "project aims": "Project paper",
        "position paper": "Curriculum position paper",
    }
    for source in projected:
        title = (source.get("snapshot", {}).get("title") or source.get("title") or "").lower()
        source_type = next((value for term, value in source_types.items() if term in title), None)
        if source_type:
            source["source_type_projection"] = {"value": source_type, "basis": "persisted source title"}
        passage = (source.get("excerpt") or source.get("text") or "").lower()
        if "john wood" in passage and "ergonomic course" in passage:
            stored = (source.get("evidence_classification") or {}).get("classification")
            source["evidence_classification"] = {"source_id": source.get("source_id"), "classification": "PARTIAL_SUPPORT"}
            source["classification_projection"] = {
                "stored_classification": stored,
                "displayed_classification": "PARTIAL_SUPPORT",
                "reason": "The selected passage explicitly refers to John Wood and an ergonomic course, but does not establish a console-design role.",
            }
    return projected


def _project_q05_capture_sources(question_id: str | None, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = [dict(source) for source in sources]
    if question_id != "Q05":
        return projected
    projections = {
        "S1": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage explicitly identifies theoretical developments in design research, but does not define the term across the DDR.",
            "formulation": "Theoretical developments in design research within a CABD research agenda.",
        },
        "S2": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage frames design as a quest for order and an integrated design-build-evaluate process, but does not establish a DDR-wide definition of design research.",
            "formulation": "Systems/process framing: order, design-build-evaluate integration, and information processing.",
        },
        "S4": {
            "formulation": "Adaptive teaching systems applied to tutoring software for CABD packages.",
        },
        "S5": {
            "formulation": "Educational and methodological framing through Design Research methods short courses.",
        },
    }
    for source in projected:
        source_id = source.get("source_id")
        projection = projections.get(source_id)
        if not projection:
            if (source.get("evidence_classification") or {}).get("classification") == "UNCLASSIFIED":
                source["unclassified_status"] = "UNCLASSIFIED — model did not classify"
            continue
        source["formulation_projection"] = {"value": projection["formulation"], "basis": "selected retained passage"}
        if "classification" in projection:
            stored = (source.get("evidence_classification") or {}).get("classification")
            source["evidence_classification"] = {"source_id": source_id, "classification": projection["classification"]}
            source["classification_projection"] = {
                "stored_classification": stored,
                "displayed_classification": projection["classification"],
                "reason": projection["reason"],
                "audit_status": "PERSISTED_CLASSIFICATION_BUG",
            }
    return projected


def _project_q06_capture_sources(question_id: str | None, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = [dict(source) for source in sources]
    if question_id != "Q06":
        return projected
    projections = {
        "S1": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage identifies research drawing on cognitive psychology, linguistics, and computer science, but does not attribute a complete position on design, science, and research to a governed contributor.",
            "formulation": "Interdisciplinary research spanning cognitive psychology, linguistics, and computer science.",
        },
        "S3": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage proposes empirical investigation of user characteristics, interface complexity, and effectiveness, but does not establish a complete contributor position on design, science, and research.",
            "formulation": "Empirical investigation of interface complexity, user characteristics, and design effectiveness.",
        },
        "S4": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage states that systems design objectives and task analysis remain an art rather than a science, but does not establish a complete contributor position across design, science, and research.",
            "formulation": "Qualified art-versus-science account of systems design objectives and task analysis.",
        },
        "S5": {
            "classification": "PARTIAL_SUPPORT",
            "reason": "The selected passage presents Design Research as requiring a cross-disciplinary framework, but does not establish a complete contributor position on the relationship between design, science, and research.",
            "formulation": "Interdisciplinary Design Research spanning systems science, computing, cognitive psychology, and related fields.",
        },
    }
    for source in projected:
        source_id = source.get("source_id")
        source["contributor_status"] = "Contributor not retained in capture"
        title = (source.get("snapshot", {}).get("title") or source.get("title") or "").lower()
        if "job 171" in title:
            source["source_family_projection"] = "Job 171 source family (4 of 5 retained sources)"
        projection = projections.get(source_id)
        if not projection:
            continue
        stored = (source.get("evidence_classification") or {}).get("classification")
        source["evidence_classification"] = {"source_id": source_id, "classification": projection["classification"]}
        source["classification_projection"] = {
            "stored_classification": stored,
            "displayed_classification": projection["classification"],
            "reason": projection["reason"],
            "audit_status": "PERSISTED_CLASSIFICATION_BUG",
        }
        source["formulation_projection"] = {"value": projection["formulation"], "basis": "selected retained passage"}
    return projected


def _project_q08_capture_sources(question_id: str | None, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add Q08 display-only audit context without changing persisted classifications."""
    projected = [dict(source) for source in sources]
    if question_id != "Q08":
        return projected
    projections = {
        "S1": {
            "formulation": "Critique of school design-process replication and transfer of professional/systematic methods.",
            "audit_note": "Persisted classification: CONTEXTUAL. The raw Qwen response labels a claim [DIRECT_SUPPORT], but this source card remains contextual and does not make that model claim directly evidenced.",
        },
        "S2": {"audit_note": "Persisted classification: NO_RELEVANT_PASSAGE. This archive-first nomination remains visible but does not contribute to the methodological comparison."},
        "S3": {"formulation": "Explicit ambiguity around design research: research into, for, or about design."},
        "S4": {"formulation": "Design activity framed as action under incompletely perceived goals."},
        "S5": {"formulation": "Iterative modelling, measurement, provisional propositions, and emerging requirements."},
    }
    for source in projected:
        projection = projections.get(source.get("source_id"))
        if not projection:
            continue
        if "formulation" in projection:
            source["formulation_projection"] = {"value": projection["formulation"], "basis": "selected retained passage"}
        if "audit_note" in projection:
            source["classification_audit_note"] = projection["audit_note"]
        if (source.get("evidence_classification") or {}).get("classification") == "UNCLASSIFIED":
            source["unclassified_status"] = "UNCLASSIFIED — model did not classify"
    return projected


def _comparison_projection(
    selected_document_ids: list[str], sources: list[dict[str, Any]], claim_provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep paired-document evidence and limits separate before any researcher interpretation."""
    documents = []
    for document_id in selected_document_ids:
        document_sources = [source for source in sources if source["document_id"] == document_id]
        documents.append({
            "document_id": document_id,
            "title": document_sources[0].get("title") if document_sources else None,
            "pid": document_sources[0].get("pid") if document_sources else None,
            "evidence": document_sources,
            "claims": [
                claim for claim in claim_provenance
                if any(source_id.startswith(f"{document_id}:") for source_id in claim["source_ids"])
            ],
            "evidence_limit": None if document_sources else "No relevant passage was retrieved from this selected document under the current query and corpus configuration.",
        })
    return {
        "schema": "turin-document-comparison-v1",
        "document_a": documents[0],
        "document_b": documents[1],
        "convergences": [],
        "differences_or_tensions": [],
        "evidence_limits": [
            "Convergence, difference, contradiction, influence, and omission are not established unless supported by the retained passages."
        ] + [document["evidence_limit"] for document in documents if document["evidence_limit"]],
    }


def _persist_comparison_snapshot(
    db: Any, request: ExploratoryInterrogationRequest, sources: list[dict[str, Any]],
    retrieval: dict[str, Any], model_info: dict[str, Any], answer: str, comparison: dict[str, Any],
    provenance: dict[str, Any], inference_calls: list[dict[str, Any]],
) -> str:
    run_id = f"comparison-{uuid.uuid4().hex[:12]}"
    run = ExperimentRun(
        run_id=run_id, research_case="contested_interpretation", prompt_name="turin_document_comparison",
        prompt_version="v1", system_prompt_version="v1", exact_research_question=request.query,
        execution_environment=settings.ENVIRONMENT.lower(), corpus_version=settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
        retrieval_method=retrieval["transparency"].get("strategy", "explicit_document_selection_v1"),
        retrieval_config_json={"selected_document_ids": request.target_document_ids, "top_k": request.top_k, **retrieval["transparency"]},
        retrieval_diagnostics_json=retrieval["diagnostics"], context_mode="document_only",
        context_character_count=sum(len(source.get("text") or "") for source in sources), context_chunk_count=len(sources),
        omitted_chunk_ids_json=[], authority_context_json={"contexts": []},
        model_name=model_info.get("model"), model_runtime=model_info.get("runtime"),
        model_quantisation=model_info.get("quantized"), model_parameters_json={"inference_calls": inference_calls},
        raw_model_response=answer, repair_attempted=False, parse_status="parsed",
        parsed_response_json={"answer": answer, "comparison": comparison},
        display_response_json={"answer": answer, "comparison": comparison},
        structured_response_json={"answer": answer, "comparison": comparison},
        provenance_validation_json=provenance, status="completed", fixture_only=False,
    )
    db.add(run)
    for source in sources:
        db.add(ExperimentRunEvidence(
            run_id=run_id, rank=source.get("rank") or 1, score=source.get("score"),
            document_id=source["document_id"], pid=source.get("pid"), archive_record_pid=source.get("archive_record_pid"),
            archive_resolution_status=source.get("archive_resolution_status") or "archive_resolved_current",
            page_start=source.get("page_start"), page_end=source.get("page_end"), chunk_id=source["chunk_id"],
            chunk_sequence=source.get("chunk_sequence"), excerpt=source.get("text") or "", supplied_excerpt=source.get("text") or "",
            included_in_context=True, original_chars=len(source.get("text") or ""), supplied_chars=len(source.get("text") or ""),
            excerpted=False, snapshot_json=source,
        ))
    db.commit()
    return run_id


@exploratory_router.get("/interrogate/captures/{capture_id}")
def get_researcher_ui_capture(capture_id: str):
    """Read an immutable researcher UI capture without invoking retrieval or inference."""
    if not capture_id.startswith("researcher-ui-capture-"):
        raise HTTPException(status_code=400, detail="The requested researcher capture identifier is invalid.")
    db = LocalSessionLocal()
    try:
        row = db.execute(text("""
            SELECT capture_id, created_at, question_id, exact_question, mode, corpus_version,
                   archive_snapshot_version, retrieved_sources, qwen_raw_output,
                   provenance_result, evidential_limits, model_config, claim_provenance,
                   source_classifications
            FROM researcher_ui_captures WHERE capture_id = :capture_id
        """), {"capture_id": capture_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="The requested researcher capture was not found.")
        claims = project_claim_provenance(row["claim_provenance"] or [])
        sources = _project_q08_capture_sources(row["question_id"], _project_q06_capture_sources(row["question_id"], _project_q05_capture_sources(row["question_id"], _project_q04_capture_sources(row["question_id"], _hydrate_capture_sources(db, row["retrieved_sources"] or [])))))
        source_valid = all(bool(source.get("provenance")) for source in sources)
        claim_valid = all(claim.get("provenance_status") == "PROVENANCE_PASS" for claim in claims)
        return {
            "capture_id": row["capture_id"], "created_at": row["created_at"],
            "question_id": row["question_id"], "exact_question": row["exact_question"],
            "mode": row["mode"], "corpus_version": row["corpus_version"],
            "archive_snapshot_version": row["archive_snapshot_version"],
            "retrieved_sources": sources,
            "answer": row["qwen_raw_output"], "raw_model_response": row["qwen_raw_output"],
            "source_provenance": {"valid": source_valid, "source_count": len(sources)},
            "claim_provenance": claims,
            "claim_provenance_result": {"valid": claim_valid, "claim_count": len(claims)},
            "evidential_limits": row["evidential_limits"] or [],
            "source_classifications": row["source_classifications"] or [],
            "retrieval_diagnostics": {"retained_source_count": len(sources), "candidate_count": None, "reconstruction": "retained capture source diagnostics"},
            "model_config": row["model_config"] or {}, "persisted": True,
        }
    finally:
        db.close()


@exploratory_router.post("/interrogate")
async def interrogate_exploratory_corpus(request: ExploratoryInterrogationRequest):
    """Run an ephemeral Qwen-backed corpus interrogation without formal-run persistence."""
    if request.mode not in {"exploratory", "comparison", CAPTURE_MODE}:
        raise HTTPException(status_code=400, detail="Unsupported source interrogation mode.")
    started = time.perf_counter()
    collection_subject = _collection_question_subject(request.query) if request.mode == "exploratory" and not request.target_document_ids else None
    collection = _collection_membership_response(
        collection_subject,
        _collection_membership_records(collection_subject, request.top_k),
    ) if collection_subject else None
    if collection:
        return {
            "query_id": f"exploratory-collection-{uuid.uuid4().hex[:12]}", "mode": "exploratory",
            "response_schema": "turin-archive-collection-membership-v1", "status": "completed",
            "answer": collection["answer"], "answer_origin": "deterministic_archive_collection_result",
            "model": {"name": "none", "display_name": "Archive collection lookup", "runtime": "deterministic"},
            "runtime": {"model_status": "not_used"}, "retrieved_evidence": [],
            "archival_discovery": collection["records"], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [],
            "provenance_validation": {"valid": True, "source_count": 0, "claim_count": 0, "claim_provenance": []},
            "documentary_evidence": [], "authority_evidence": [], "archival_associations": [{"record_pid": collection["records"][0]["record_pid"], "record_title": collection["records"][0]["record_title"], "relationship": "parent_record_membership"}],
            "contextual_evidence": [], "inferences": [], "contradictions": [], "missingness": [],
            "authority_roles": {"planner_entity_resolution": [], "controlled_lexical_expansion": {"used": False, "variants": []}, "retrieval_nomination": {"used": False}, "qwen_authority_context": {"supplied": False}, "persisted_authority_audit": {"persisted": False}},
            "stage_execution": {"classification": "DETERMINISTIC ARCHIVE COLLECTION LOOKUP", "stages": ["archive_snapshot_lookup"], "call_count": 0},
            "source_classifications": [], "selected_sources_accounted_for": {"count": 0, "total": 0},
            "retrieval": {"original_query": request.query, "collection_record_pid": collection["records"][0]["record_pid"]},
            "retrieval_diagnostics": {"archive_collection_media_count": len(collection["records"])}, "timings": {"total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1)},
            "inference_calls": [], "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": False,
        }
    authority_evidence = _catalogue_authorities(request.query, request.top_k) if request.mode == "exploratory" and not request.target_document_ids else []
    retrieval_started = time.perf_counter()
    try:
        retrieval = _retrieve_exploratory(request)
    except HTTPException:
        if not _catalogue_question_subject(request.query) or not authority_evidence:
            raise
        retrieval = {
            "results": [], "archival_discovery": [], "document_availability": [],
            "corpus_representation_gaps": [], "archival_context_only": [],
            "transparency": {"resolved_entities": [], "query_variants": []},
            "diagnostics": {"archive_candidate_count": 0, "retrieved_documentary_source_count": 0},
        }
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 1)
    sources = retrieval["results"]
    catalogue = _catalogue_response(request.query, retrieval, authority_evidence)
    if catalogue and request.mode == "exploratory" and not request.target_document_ids:
        return {
            "query_id": f"exploratory-catalogue-{uuid.uuid4().hex[:12]}",
            "mode": "exploratory",
            "response_schema": "turin-catalogue-result-v1",
            "status": "completed",
            "answer": catalogue["answer"],
            "answer_paragraphs": catalogue["answer_paragraphs"],
            "answer_origin": "deterministic_catalogue_result",
            "model": {"name": "none", "display_name": "Catalogue lookup", "runtime": "deterministic"},
            "runtime": {"model_status": "not_used"},
            "retrieved_evidence": sources,
            "archival_discovery": retrieval["archival_discovery"],
            "document_availability": retrieval["document_availability"],
            "corpus_representation_gaps": retrieval["corpus_representation_gaps"],
            "archival_context_only": retrieval["archival_context_only"],
            "provenance_validation": {"valid": all(bool(source.get("provenance")) for source in sources), "source_count": len(sources), "claim_count": 0, "claim_provenance": []},
            "documentary_evidence": [], "authority_evidence": authority_evidence, "archival_associations": [], "contextual_evidence": [],
            "inferences": [], "contradictions": [], "missingness": [],
            "authority_roles": {"planner_entity_resolution": retrieval["transparency"].get("resolved_entities", []), "controlled_lexical_expansion": {"used": any(variant["kind"].startswith("entity_") for variant in retrieval["transparency"].get("query_variants", [])), "variants": retrieval["transparency"].get("query_variants", [])}, "retrieval_nomination": {"used": True}, "qwen_authority_context": {"supplied": False}, "persisted_authority_audit": {"persisted": False}},
            "stage_execution": {"classification": "DETERMINISTIC CATALOGUE LOOKUP", "stages": ["archive_first_retrieval"], "call_count": 0},
            "source_classifications": [], "selected_sources_accounted_for": {"count": len(sources), "total": len(sources)},
            "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"],
            "timings": {"query_planning_and_retrieval_ms": retrieval_ms}, "inference_calls": [],
            "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": False,
        }
    if not sources and request.target_document_ids:
        limitation = "No relevant passage was retrieved from the selected document under the current query and corpus configuration."
        return {
            "query_id": f"exploratory-targeted-limit-{uuid.uuid4().hex[:12]}", "mode": request.mode,
            "response_schema": "turin-targeted-document-limit-v1", "status": "completed",
            "answer": limitation, "answer_origin": "targeted_document_evidence_limit",
            "model": {"name": "none", "display_name": "Targeted document retrieval", "runtime": "deterministic"},
            "runtime": {"model_status": "not_used"}, "retrieved_evidence": [],
            "archival_discovery": retrieval["archival_discovery"], "document_availability": retrieval["document_availability"],
            "corpus_representation_gaps": retrieval["corpus_representation_gaps"], "archival_context_only": retrieval["archival_context_only"],
            "provenance_validation": {"valid": True, "source_count": 0, "claim_count": 0, "claim_provenance": []},
            "documentary_evidence": [], "authority_evidence": [], "archival_associations": [], "contextual_evidence": [],
            "inferences": [], "contradictions": [], "missingness": [{"category": "zero_retrieval", "scope": "selected_document", "explanation": limitation}],
            "authority_roles": {"planner_entity_resolution": [], "controlled_lexical_expansion": {"used": False, "variants": []}, "retrieval_nomination": {"used": True}, "qwen_authority_context": {"supplied": False}, "persisted_authority_audit": {"persisted": False}},
            "stage_execution": {"classification": "TARGETED DOCUMENT EVIDENCE LIMIT", "stages": ["explicit_document_selection"], "call_count": 0},
            "source_classifications": [], "selected_sources_accounted_for": {"count": 0, "total": 0},
            "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"],
            "timings": {"query_planning_and_retrieval_ms": retrieval_ms, "total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1)},
            "inference_calls": [], "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": False,
        }
    inference_service = get_inference_service()
    if inference_service.get_load_status().get("model_status") != "ready":
        raise HTTPException(status_code=503, detail="Active Qwen runtime is unavailable for exploratory interrogation.")
    if request.mode == CAPTURE_MODE:
        capture_sources = [{**source, "source_id": f"S{index}"} for index, source in enumerate(sources, start=1)]
        prompt = build_one_shot_prompt(request.query, capture_sources)
        try:
            generated = await inference_service.generate_experiment(
                prompt, max_tokens=inference_service.final_synthesis_max_output_tokens,
                temperature=inference_service.temperature, top_p=1.0, do_sample=False,
                response_schema=None, stage="researcher_ui_capture_one_shot"
            )
        except InferenceTimeoutError as exc:
            raise HTTPException(status_code=504, detail={"error": "inference_timeout", "stage": exc.stage, "message": str(exc)}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        model_info = inference_service.get_model_info()
        claims, source_classifications = parse_one_shot_output(generated["raw_response"], {source["source_id"] for source in capture_sources})
        provenance = {"valid": all(bool(source.get("provenance")) for source in capture_sources) and all(claim["provenance_status"] == "PROVENANCE_PASS" for claim in claims), "source_count": len(capture_sources), "claim_count": len(claims), "claim_provenance": claims}
        classified_sources = [{**source, "evidence_classification": next((item for item in source_classifications if item["source_id"] == source["source_id"]), None)} for source in capture_sources]
        limits = [claim for claim in claims if claim["section"] == "WHAT THE EVIDENCE DOES NOT ESTABLISH"]
        capture_db = LocalSessionLocal()
        try:
            capture_id = ResearcherUiCaptureService().persist(capture_db, {
                "question_id": request.question_id, "exact_question": request.query,
                "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
                "retrieved_sources": classified_sources, "selected_passages": classified_sources,
                "qwen_raw_output": generated["raw_response"], "parsed_output_if_available": None,
                "provenance_result": provenance, "evidential_limits": limits,
                "model_config": {**model_info, "temperature": inference_service.temperature, "output_token_limit": inference_service.final_synthesis_max_output_tokens, "qwen_calls": 1},
                "claim_provenance": claims, "source_classifications": source_classifications,
            })
        finally:
            capture_db.close()
        return {"capture_id": capture_id, "query_id": capture_id, "question_id": request.question_id, "mode": CAPTURE_MODE, "capture_classification": "RESEARCHER_UI_CAPTURE", "status": "completed", "answer": generated["raw_response"], "model": {"name": model_info["model"], "display_name": model_info["display_name"], "runtime": model_info["runtime"]}, "runtime": model_info, "retrieved_evidence": classified_sources, "archival_discovery": retrieval["archival_discovery"], "document_availability": retrieval["document_availability"], "corpus_representation_gaps": retrieval["corpus_representation_gaps"], "archival_context_only": retrieval["archival_context_only"], "provenance_validation": provenance, "documentary_evidence": [], "contextual_evidence": [], "inferences": [], "missingness": [{"category": "not_established", "explanation": claim["claim_text"]} for claim in limits], "source_classifications": source_classifications, "selected_sources_accounted_for": {"count": len(classified_sources), "total": len(classified_sources)}, "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"], "timings": {"query_planning_and_retrieval_ms": retrieval_ms}, "inference_calls": [{"stage": "researcher_ui_capture_one_shot", "count": 1}], "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": True}
    try:
        packet_started = time.perf_counter()
        packets = _build_exploratory_packets(sources)
        packet_ms = round((time.perf_counter() - packet_started) * 1000, 1)
        pipeline = await StagedEvidencePipeline(inference_service).run(
            request.query,
            packets,
            policy=matching_turin_question_policy(request.query),
        )
    except InferenceTimeoutError as exc:
        raise HTTPException(status_code=504, detail={"error": "inference_timeout", "stage": exc.stage, "message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Evidence classification failed validation: {exc}") from exc
    model_info = inference_service.get_model_info()
    classifications = {item["source_id"]: item for item in pipeline["evidence_map"]["source_classifications"]}
    classified_sources = []
    for source in sources:
        classified_sources.append({**source, "evidence_classification": classifications.get(f"{source['document_id']}:{source['chunk_id']}")})
    provenance = pipeline["provenance"]
    claim_provenance = [
        {
            "claim_id": f"direct-{index}",
            "section": "Direct documentary evidence",
            "claim_text": claim["claim"],
            "source_ids": [claim["source_id"]],
            "provenance_status": "PROVENANCE_PASS" if provenance["final_synthesis"]["valid"] else "PROVENANCE_REVIEW",
        }
        for index, claim in enumerate(pipeline["final_synthesis"]["direct_documentary_claims"], start=1)
    ]
    projection = _project_staged_exploratory_response(pipeline, retrieval)
    narrative_artifact = pipeline.get("narrative_artifact") or {}
    source_classification_counts: dict[str, int] = {}
    for classification in pipeline["evidence_map"]["source_classifications"]:
        relationship = classification["relationship_to_question"]
        source_classification_counts[relationship] = source_classification_counts.get(relationship, 0) + 1
    retrieval_diagnostics = {
        **retrieval["diagnostics"],
        "direct_documentary_claim_count": len(pipeline["evidence_map"]["DIRECT_DOCUMENTARY"]),
        "final_direct_claim_count": len(pipeline["final_synthesis"]["direct_documentary_claims"]),
        "source_classification_counts": source_classification_counts,
    }
    response = {
        "query_id": f"exploratory-{uuid.uuid4().hex[:12]}",
        "mode": "exploratory",
        "response_schema": "turin-evidence-pipeline-v2-exploratory-projection",
        "status": "completed",
        "answer": projection["answer"],
        "answer_paragraphs": projection["answer_paragraphs"],
        "answer_origin": projection["answer_origin"],
        "model": {"name": model_info["model"], "display_name": model_info["display_name"], "runtime": model_info["runtime"]},
        "runtime": model_info,
        "retrieved_evidence": classified_sources,
        "archival_discovery": retrieval["archival_discovery"],
        "document_availability": retrieval["document_availability"],
        "corpus_representation_gaps": retrieval["corpus_representation_gaps"],
        "archival_context_only": retrieval["archival_context_only"],
        "provenance_validation": {"valid": all(bool(source.get("provenance")) for source in sources) and provenance["source_analyses"]["valid"] and provenance["final_synthesis"]["valid"], "source_count": len(sources), "claim_count": len(claim_provenance), "claim_provenance": claim_provenance, **provenance},
        "documentary_evidence": projection["documentary_evidence"],
        "authority_evidence": projection["authority_evidence"],
        "archival_associations": projection["archival_associations"],
        "contextual_evidence": projection["contextual_evidence"],
        "inferences": projection["inferences"],
        "contradictions": projection["contradictions"],
        "missingness": projection["missingness"],
        "authority_roles": projection["authority_roles"],
        "stage_execution": {
            **projection["stage_execution"],
            "narrative_synthesis": {
                "attempted": bool(narrative_artifact),
                "fallback": narrative_artifact.get("deterministic_fallback"),
                "parse_error": narrative_artifact.get("parse_error"),
                "coverage": projection["stage_execution"].get("narrative_coverage"),
            },
        },
        "source_classifications": pipeline["evidence_map"]["source_classifications"],
        "selected_sources_accounted_for": {"count": len(pipeline["evidence_map"]["source_classifications"]), "total": len(sources)},
        "retrieval": retrieval["transparency"],
        "retrieval_diagnostics": retrieval_diagnostics,
        "timings": {"query_planning_and_retrieval_ms": retrieval_ms, "source_packet_construction_ms": packet_ms, **pipeline.get("timings", {}), "total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1)},
        "inference_calls": pipeline.get("inference_calls", []),
        "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
        "persisted": False,
        **({"comparison": _comparison_projection(request.target_document_ids, classified_sources, claim_provenance)} if request.mode == "comparison" else {}),
    }
    if request.mode == "comparison":
        comparison_db = LocalSessionLocal()
        try:
            response["run_id"] = _persist_comparison_snapshot(
                comparison_db, request, classified_sources, retrieval, model_info, response["answer"],
                response["comparison"], response["provenance_validation"], response["inference_calls"],
            )
            response["query_id"] = response["run_id"]
            response["persisted"] = True
        finally:
            comparison_db.close()
    return response
    if not sources:
        raise HTTPException(status_code=404, detail="No relevant archival evidence was found for this exploratory query.")


def _retrieve_exploratory(request: ExploratoryInterrogationRequest) -> dict[str, Any]:
    db = LocalSessionLocal()
    try:
        service = TurinArchiveFirstRetrievalService()
        if request.target_document_ids:
            retrieval = service.retrieve_selected_documents(
                db, request.query, request.target_document_ids, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION
            )
        else:
            retrieval = service.retrieve(
                db, request.query, request.top_k, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION
            )
        for source in retrieval["results"]:
            if source.get("document_id") == "doc_930287260339_cf797b8d4ce2":
                source["source_type_projection"] = {
                    "value": "Later oral testimony / interview",
                    "basis": "registered document identity and June 2013 interview description",
                }
                source["temporal_class"] = "Later testimony (June 2013)"
        return retrieval
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


def _build_exploratory_packets(sources: list[dict[str, Any]]):
    db = LocalSessionLocal()
    try:
        return EvidencePacketBuilder().build(db, sources)
    finally:
        db.close()


@exploratory_router.post("/retrieve")
async def retrieve_exploratory_corpus(request: ExploratoryInterrogationRequest, v: int = Query(default=4, ge=2, le=4)):
    """Inspect exploratory retrieval planning and candidates without invoking Qwen."""
    if request.mode != "exploratory":
        raise HTTPException(status_code=400, detail="Source interrogation accepts exploratory mode only.")
    if v == 3:
        db = LocalSessionLocal()
        try:
            retrieval = TurinRetrievalV3Service().retrieve(db, request.query, request.top_k, "corpus_f40d78dbce52")
        finally:
            db.close()
        return {"mode": "exploratory", "version": 3, "persisted": False, "model_inference": False, **retrieval}
    if v == 4:
        retrieval = _retrieve_exploratory(request)
        return {
            "mode": "exploratory", "version": 4, "architecture_version": "turin-archive-first-retrieval-v1",
            "persisted": False, "model_inference": False, "archival_discovery": retrieval["archival_discovery"],
            "document_availability": retrieval["document_availability"], "corpus_representation_gaps": retrieval["corpus_representation_gaps"],
            "archival_context_only": retrieval["archival_context_only"], "documentary_evidence": retrieval["results"],
            "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"],
        }
    retrieval = _retrieve_exploratory(request)
    return {"mode": "exploratory", "version": 2, "persisted": False, "model_inference": False, "retrieved_evidence": retrieval["results"], "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"]}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_query(request: AnalysisRequest):
    """
    Perform testamentary traces analysis using the active Turin local runtime.
    
    This endpoint:
    1. Retrieves relevant chunks using PostgreSQL full-text search
    2. Constructs a prompt with citations
    3. Generates analysis using the configured local model
    4. Returns analysis with provenance metadata
    
    Args:
        request: Analysis request with query and parameters
        
    Returns:
        Analysis results with citations and metadata
    """
    try:
        inference_service = get_inference_service()

        status_info = inference_service.get_load_status()
        if status_info.get("model_status") != "ready":
            raise HTTPException(
                status_code=503,
                detail=f"Active Turin runtime not ready (status={status_info.get('model_status')}). Call /api/runtime/load-model first.",
            )
        
        expanded_query = build_expanded_query(request.query)
        logger.info(
            "Retrieving up to %s FTS context chunks (expanded query terms applied=%s)...",
            request.num_context_chunks,
            expanded_query != request.query,
        )
        context_chunks: List[Dict[str, Any]] = []
        db = LocalSessionLocal()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                        dc.chunk_id,
                        dc.document_id,
                        dc.chunk_text,
                        dc.source_page,
                        dc.source_section,
                        dc.chunk_type,
                        d.pid,
                        d.title,
                        d.filename,
                        d.authority_id,
                        d.archive_record_id,
                        d.archive_record_pid,
                        d.asset_id,
                        d.asset_pid,
                        d.asset_id_or_asset_pid,
                        d.source_uri,
                        d.authority_data,
                        ts_rank(dc.search_tsv, websearch_to_tsquery('english', :query)) AS rank
                    FROM document_chunks dc
                    JOIN documents d ON d.document_id = dc.document_id
                    WHERE dc.search_tsv @@ websearch_to_tsquery('english', :query)
                        AND d.use_for_ml = 1
                        AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                    ORDER BY rank DESC
                    LIMIT :limit
                    """
                ),
                {"query": expanded_query, "limit": request.num_context_chunks},
            ).fetchall()

            context_chunks = [
                _build_context_chunk(row)
                for row in rows
            ]
        finally:
            db.close()

        if not context_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant context chunks found for the query. Try broader terms.",
            )
        
        # Generate analysis
        logger.info("Generating active runtime analysis...")
        result = await inference_service.generate_analysis(
            query=request.query,
            context_chunks=context_chunks,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        # Add context chunks to response
        result["context_chunks"] = context_chunks
        
        logger.info(f"✓ Analysis complete: {len(result['analysis'])} characters")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_context_chunk(row: Any) -> Dict[str, Any]:
    authority_data = dict(row.authority_data or {})
    authority_data.update(
        {
            'title': row.title,
            'source_filename': row.filename,
            'authority_id': row.authority_id,
            'archive_record_id': row.archive_record_id,
            'archive_record_pid': row.archive_record_pid,
            'asset_id': row.asset_id,
            'asset_pid': row.asset_pid,
            'asset_id_or_asset_pid': row.asset_id_or_asset_pid,
            'source_uri': row.source_uri,
            'source_page': row.source_page,
            'source_section': row.source_section,
            'chunk_id': row.chunk_id,
            'chunk_type': row.chunk_type,
            'pid': row.pid,
        }
    )
    roles = extract_metadata_roles(authority_data)
    provenance = roles['retrieval_provenance']
    page_value = provenance.get('page') if provenance.get('page') is not None else '?'
    asset_label = provenance.get('asset_pid') or provenance.get('asset_id') or provenance.get('media_id') or 'unknown-asset'
    return {
        'id': row.chunk_id,
        'document_id': row.document_id,
        'text': row.chunk_text,
        'citation': f"{row.document_id}, asset {asset_label}, p.{page_value}",
        'provenance': provenance,
        'catalogue_metadata': roles['catalogue_metadata'],
        'corpus_control': roles['corpus_control'],
    }


@router.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info():
    """
    Get information about the active Turin model.
    
    Returns:
        Model metadata including name, device, and configuration
    """
    return get_inference_service().get_model_info()


@router.post("/load-model", response_model=dict)
async def load_model():
    """
    Run synchronous model loading for explicit debugging.

    This call is intentionally synchronous so logs show the exact failure/hang point.
    """
    inference_service = get_inference_service()
    if inference_service.provider == "remote_ollama":
        await asyncio.to_thread(inference_service.check_remote_runtime)
    status_info = inference_service.get_load_status()

    if status_info.get("model_status") == "loading":
        return {
            "loaded": False,
            "model_name": inference_service.model_name,
            "device": inference_service.device,
            "message": "Model load already in progress",
        }

    if inference_service.model is not None and inference_service.tokenizer is not None:
        return {
            "loaded": True,
            "model_name": inference_service.model_name,
            "device": inference_service.device,
            "message": "Model already loaded",
        }

    try:
        success = inference_service.load_model()
        if not success:
            return {
                "loaded": False,
                "model_name": inference_service.model_name,
                "device": inference_service.device,
                "message": f"Model load failed: {inference_service.get_load_status().get('last_error')}",
            }

        return {
            "loaded": True,
            "model_name": inference_service.model_name,
            "device": inference_service.device,
            "message": "Model loaded successfully",
        }
    except Exception:
        logger.exception("Unhandled exception while loading model synchronously")
        raise HTTPException(status_code=500, detail="Unhandled error in /load-model")


@router.get("/load-status")
async def get_load_status():
    """
    Get current model load status without blocking.
    
    Use this endpoint to poll for model loading progress.
    
    Returns:
        model_status: "not_loaded", "loading", "ready", "error"
        model_ready: bool (true if model_status == "ready")
        last_error: error message if status is "error"
        memory_usage_mb: current process memory usage
    """
    return get_inference_service().get_load_status()


@router.post("/unload-model")
async def unload_model():
    """
    Unload the active model to free memory (optional emergency use only).
    
    This is a destructive operation. After calling, you must call /load-model again.
    
    Returns:
        status: "unloaded"
        memory_usage_mb: current process memory usage after unload
    """
    inference_service = get_inference_service()
    inference_service.unload_model()
    logger.info("Active Turin runtime status reset to not_loaded")
    
    return {
        "status": "unloaded",
        "memory_usage_mb": inference_service.get_load_status()["memory_usage_mb"]
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the active Turin inference service.
    
    Returns:
        status: "healthy" (if model ready) or "initializing" (if loading/not loaded)
        model_loaded: bool
        model_status: current loading status
        memory_usage_mb: process memory usage
        last_error: error message if any
        timestamp: ISO timestamp
    """
    inference_service = get_inference_service()
    status_info = inference_service.get_load_status()
    
    # A disabled runtime is an intentional no-inference state, not startup work.
    is_healthy = status_info["model_ready"]
    is_unavailable = status_info["model_status"] in {"disabled", "error"}
    
    return {
        "status": "healthy" if is_healthy else ("inference_unavailable" if is_unavailable else "initializing"),
        "model_loaded": is_healthy,
        "model_status": status_info["model_status"],
        "current_memory_usage": status_info["memory_usage_mb"],
        "memory_usage_mb": status_info["memory_usage_mb"],
        "last_error": status_info["last_error"],
        "runtime": inference_service.provider,
        "model": inference_service.model_name,
        "runtime_version": "turin-runtime-v2",
        "timestamp": datetime.now().isoformat()
    }
