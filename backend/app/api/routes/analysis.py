"""
API route for the active Turin local inference runtime.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import logging
import re
import uuid
import time
from enum import Enum
from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from app.services.inference_service import InferenceTimeoutError, get_inference_service
from app.core.database import LocalSessionLocal
from app.core.config import settings
from app.services.metadata_roles import extract_metadata_roles
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService
from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.turin_archive_first_retrieval_service import ARCHIVE_ASSET_SNAPSHOT_VERSION, TurinArchiveFirstRetrievalService
from app.services.archive_question_preset_service import matching_archive_question_preset
from app.services.retrieval_contract_service import derive_retrieval_contract, project_anchors_from_question
from app.services.turin_evidence_pipeline_service import EvidencePacketBuilder, StagedEvidencePipeline, compile_evidence_ledger, readable_claim_text, researcher_prose_issues
from app.services.turin_evidence_pipeline_service import EvidencePacketBuilder, EvidencePipelineStageError, StagedEvidencePipeline
from app.services.turin_question_policy import matching_turin_question_policy
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service
from app.services.researcher_ui_capture_service import CAPTURE_MODE, ResearcherUiCaptureService, build_one_shot_prompt, parse_one_shot_output, project_claim_provenance
from app.services.authority_registry import AuthorityRegistry
from app.services.turin_question_route import classify_question_route, decompose_hybrid_question
from app.services.provenance_integrity import experiment_evidence_digest, experiment_run_digest
from app.models.research_outputs import ExperimentRun, ExperimentRunEvidence
from app.services.turin_research_answer_service import generate_documentary_synthesis, _evidence_records

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
    top_k: int = Field(default=8, ge=1, le=20)
    archive_record_pid: str | None = Field(default=None, max_length=32)
    target_document_ids: list[str] = Field(default_factory=list, max_length=2)
    selected_chunk_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_document_selection(self):
        if self.mode == "comparison" and len(self.target_document_ids) != 2:
            raise ValueError("Comparison mode requires exactly two selected documents.")
        if self.selected_chunk_ids and self.target_document_ids:
            raise ValueError("Select either document targets or specific passages, not both.")
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


class AnswerState(str, Enum):
    SYNTHESIS_VALID = "synthesis_valid"
    SYNTHESIS_PARTIAL = "synthesis_partial"
    SYNTHESIS_UNAVAILABLE = "synthesis_unavailable"
    EVIDENTIAL_LIMIT = "evidential_limit"


def _is_archive_scope_overview_request(request: ExploratoryInterrogationRequest) -> bool:
    return bool(request.archive_record_pid) and bool(re.search(
        r"\b(?:key take\s*aways?|main (?:arguments?|themes?)|central (?:arguments?|themes?)|overall argument|broadly)\b",
        request.query,
        flags=re.IGNORECASE,
    ))


def _catalogue_question_subject(query: str) -> str | None:
    patterns = (
        r"^according to (?:the )?.+?\bauthorit(?:y|ies)\b,?\s*(?P<subject>.+?)\??$",
        r"^what projects did (?P<subject>.+?) work on\??$",
        r"^what documents (?:by|mention) (?P<subject>.+?) (?:are )?available\??$",
        r"^what documents mention (?P<subject>.+?)\??$",
        r"^(?:list|show) (?:the )?documents (?P<subject>.+?) worked on\??$",
        r"^when did (?P<subject>.+?) (?:take in|admit) (?:its )?first students\??$",
        r"^what (?:was|is) (?P<subject>.+?)(?:'s|’s) involvement (?:at|with|in) (?:the )?ddr\??$",
        r"^what role did (?P<subject>.+?) (?:hold|have)\??$",
        r"^when did (?P<subject>.+?) work at ddr\??$",
        r"^(?:tell me )?what (?P<subject>.+?) did at the ddr(?:,? and when(?: please)?)?\??$",
        r"^when was (?P<subject>.+?) at the ddr\??$",
        r"^when was (?P<subject>.+?) at the ddr and what did (?:he|she|they) do there\??$",
    )
    normalised = " ".join(query.strip().split()).rstrip(".?! ")
    for pattern in patterns:
        match = re.match(pattern, normalised, flags=re.IGNORECASE)
        if match:
            return match.group("subject").strip(" ?. ")
    if re.search(
        r"\b(?:key take\s*aways?|main (?:arguments?|themes?)|central (?:arguments?|themes?)|"
        r"overall argument|implications?|significance|analyse|analyze|synthesi[sz]e|overview)\b",
        normalised,
        flags=re.IGNORECASE,
    ):
        return None
    if re.match(r"^(?:what|which|who|when)\b", normalised, flags=re.IGNORECASE) and re.search(
        r"\b(?:documents?|records?|projects?|job|students?|degree|thesis|period|funder|lead|first|constituted|constitution)\b",
        normalised,
        flags=re.IGNORECASE,
    ):
        return normalised.rstrip("?")
    return None


def _requires_documentary_evidence(query: str) -> bool:
    return bool(re.search(
        r"\b(?:documents?|records?|documentary|surviving|teaching|curriculum|practice|"
        r"reports?|traces?|what do|what does|show)\b",
        query,
        flags=re.IGNORECASE,
    ))


def _is_authority_only_question(query: str, authority_evidence: list[dict[str, Any]]) -> bool:
    """Recognise controlled-authority questions without relying on their initial wh-word."""
    return bool(
        authority_evidence
        and re.match(r"^according to (?:the )?.+?\bauthorit(?:y|ies)\b", query.strip(), flags=re.IGNORECASE)
        and not _requires_documentary_evidence(query)
    )


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


def _hydrate_source_display_dates(sources: list[dict[str, Any]]) -> None:
    """Add the governed archival display date to each retrieved source in place."""
    identities = {
        str(identity)
        for source in sources
        for identity in (
            source.get("asset_pid"),
            source.get("asset_id"),
            (source.get("provenance") or {}).get("asset_pid"),
            (source.get("provenance") or {}).get("asset_id"),
        )
        if identity
    }
    if not identities:
        return

    db = LocalSessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT asset_pid, asset_id, display_date
                FROM turin_archive_asset_snapshots
                WHERE source_snapshot_version = :snapshot_version
                  AND (asset_pid IN :identities OR asset_id IN :identities)
                """
            ).bindparams(bindparam("identities", expanding=True)),
            {"snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION, "identities": sorted(identities)},
        ).mappings().all()
    finally:
        db.close()

    dates_by_identity = {
        str(identity): row["display_date"]
        for row in rows
        if row["display_date"]
        for identity in (row["asset_pid"], row["asset_id"])
        if identity
    }
    for source in sources:
        provenance = source.get("provenance") or {}
        source["display_date"] = next(
            (
                dates_by_identity[str(identity)]
                for identity in (
                    source.get("asset_pid"),
                    source.get("asset_id"),
                    provenance.get("asset_pid"),
                    provenance.get("asset_id"),
                )
                if identity and str(identity) in dates_by_identity
            ),
            None,
        )


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
    exact_project_field_request = bool(
        re.search(r"\bjob(?: number)?\s+\d+\b", question)
        and re.search(
            r"\b(?:project lead|who (?:is )?recorded as (?:project )?lead|leading|funder|funding|funded|duration)\b",
            question,
        )
    )
    if exact_project_field_request:
        authority_types = ["ddr_projects"]
    elif "database authorit" in question and any(term in question for term in ("employment", "role", "job title", "trajectory")):
        authority_types = ["agent_employment"]
    elif "project authorit" in question:
        authority_types = ["ddr_projects"]
    elif "controlled ddr period" in question or "ddr periods" in question:
        authority_types = ["ref_ddr_period"]
    elif "methodology registry" in question:
        authority_types = ["ref_methodology"]
    else:
        authority_types = AuthorityRegistry().selected_types(query)
    if any(term in question for term in ("degree", "thesis")) and "ref_students" not in authority_types:
        authority_types.append("ref_students")
    if any(term in question for term in ("constituted", "constitution")) and "ref_ddr_period" not in authority_types:
        authority_types.append("ref_ddr_period")
    if (project_anchors_from_question(query) or any(term in question for term in ("project", "job ", "job number", "funder"))) and "ddr_projects" not in authority_types:
        authority_types.append("ddr_projects")
    authority_types = list(dict.fromkeys(authority_types))
    if not authority_types:
        return []
    db = LocalSessionLocal()
    try:
        try:
            contexts = AuthorityRegistry().resolve(db, query, authority_types)
            controlled_vocabularies = {"ref_ddr_period", "ref_methodology"}
            selected_contexts = contexts if set(authority_types).issubset(controlled_vocabularies) else contexts[:limit]
            return [context.model_dump() for context in selected_contexts]
        except SQLAlchemyError:
            logger.warning("Authority registry unavailable; continuing without authority context")
            return []
    finally:
        db.close()


def _person_authority_response(
    subject: str,
    sources: list[dict[str, Any]],
    authority_evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Combine a staff authority fact with only passages that explicitly name that person."""
    employment = [
        authority for authority in authority_evidence
        if authority.get("authority_type") == "agent_employment"
    ]
    if not employment:
        return None

    subject_terms = set(re.findall(r"[a-z]{3,}", subject.lower()))
    authority_claims, documentary_claims = [], []
    for authority_number, authority in enumerate(authority_evidence, start=1):
        if authority.get("authority_type") != "agent_employment":
            continue
        fields = authority.get("fields") or {}
        name = fields.get("name") or fields.get("label") or subject
        role = fields.get("job_title_label") or fields.get("job_title_code") or "role unavailable"
        start = fields.get("start_date") or "an unavailable start date"
        end = fields.get("end_date") or "an unavailable end date"
        authority_claims.append({
            "text": f"The DDR employment register records {name} as {role} from {start} to {end}.",
            "authority_numbers": [authority_number],
        })

    for source_number, source in enumerate(sources, start=1):
        excerpt = " ".join(str(source.get("excerpt") or source.get("text") or "").split())
        excerpt_terms = set(re.findall(r"[a-z]{3,}", excerpt.lower()))
        if not excerpt or not subject_terms.issubset(excerpt_terms):
            continue
        documentary_claims.append({
            "text": f"A surviving passage names {subject}: \"{excerpt}\"",
            "source_numbers": [source_number],
        })

    paragraphs = []
    if authority_claims:
        paragraphs.append({"claims": authority_claims})
    if documentary_claims:
        paragraphs.append({"claims": documentary_claims})
    else:
        paragraphs.append({"claims": [{
            "text": f"The retrieved passages do not themselves state a specific activity by {subject}; the employment record establishes appointment and tenure, not a complete account of duties.",
        }]})
    return {
        "answer": "",
        "answer_paragraphs": paragraphs,
        "records": [],
        "subject": subject,
    }


def _named_employment_authority(authority_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (authority for authority in authority_evidence if authority.get("authority_type") == "agent_employment"),
        None,
    )


def _deterministic_authority_response(authority_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Render controlled authority fields without a documentary or model claim."""
    claims = []
    provenance = []
    boundaries = []
    for authority in authority_evidence:
        fields = authority.get("fields") or {}
        authority_id = str(authority.get("authority_id") or "")
        authority_type = str(authority.get("authority_type") or "")
        label = str(fields.get("label") or fields.get("name") or fields.get("title") or authority_id)
        if authority_type == "agent_employment":
            values = [
                ("employment role", fields.get("job_title_trajectory") or fields.get("job_title_label") or fields.get("job_title_code")),
                ("start date", fields.get("start_date")),
                ("end date", fields.get("end_date")),
            ]
        elif authority_type == "ddr_projects":
            values = [
                ("project lead", fields.get("project_lead_name")),
                ("funder", fields.get("funder_name")),
                ("duration", fields.get("duration_text")),
                ("start year", fields.get("start_year")),
                ("end year", fields.get("end_year")),
            ]
        else:
            values = [
                ("code", fields.get("code")),
                ("description", fields.get("description")),
                ("definition", fields.get("definition")),
            ]
        detail = "; ".join(
            f"{field}: {value}" for field, value in values if value not in (None, "")
        )
        text_value = f"{label}: {detail}." if detail else f"{label}."
        claim_id = f"authority:{authority_type}:{authority_id}" if authority_id else f"authority:{authority_type}:{len(claims) + 1}"
        claims.append({
            "claim_id": claim_id,
            "claim_type": "DATABASE_AUTHORITY",
            "text": text_value,
            "supporting_source_ids": [],
            "supporting_evidence_card_ids": [],
            "supporting_authority_ids": [authority_id] if authority_id else [],
        })
        provenance.append({"authority_type": authority_type, "authority_id": authority_id})
        if authority_type == "agent_employment":
            boundary = "This controlled employment entry does not by itself establish documentary activity, authorship, project participation, or duties in a particular source."
        elif authority_type == "ddr_projects":
            boundary = "This controlled project entry does not by itself establish report authorship, group leadership, documentary content, or project outcomes."
        elif authority_type == "ref_ddr_period":
            boundary = "These controlled period labels are analytical authority context; contemporary documentary evidence is required to establish a historical claim about a period."
        elif authority_type == "ref_methodology":
            boundary = "This controlled methodology definition does not establish that a particular project, document, or person used the method."
        else:
            boundary = "This controlled authority value provides classification or context; it is not direct documentary substantiation."
        if boundary not in boundaries:
            boundaries.append(boundary)
    return {
        "answer": "\n".join(claim["text"] for claim in claims),
        "answer_paragraphs": [{"claims": [{"text": claim["text"], "claim_ids": [claim["claim_id"]]} for claim in claims]}] if claims else [],
        "final_claim_plan": {"claims": claims, "overall_limit_ids": []},
        "authority_provenance": provenance,
        "authority_boundaries": boundaries,
    }


def _authority_claim_violations(
    claims: list[dict[str, Any]], authority_evidence: list[dict[str, Any]]
) -> list[str]:
    expected = {
        claim["claim_id"]: claim
        for claim in _deterministic_authority_response(authority_evidence)["final_claim_plan"]["claims"]
    }
    violations = []
    for claim in claims:
        expected_claim = expected.get(str(claim.get("claim_id")))
        if expected_claim is None or claim.get("text") != expected_claim.get("text"):
            violations.append(f"{claim.get('claim_id')}: authority text does not match structured fields")
        elif claim.get("supporting_authority_ids") != expected_claim.get("supporting_authority_ids"):
            violations.append(f"{claim.get('claim_id')}: authority reference does not match structured record")
    return violations


def _merge_authority_evidence_ledger(
    ledger: list[dict[str, Any]], authority_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    authority_ledger = compile_evidence_ledger(
        [], {"EVIDENCE_CARDS": [], "ARCHIVAL_METADATA": [], "DATABASE_AUTHORITY": []},
        authority_evidence,
    )
    existing_ids = {str(item.get("evidence_id")) for item in ledger}
    return [
        *ledger,
        *(item for item in authority_ledger if str(item.get("evidence_id")) not in existing_ids),
    ]


def _catalogue_response(query: str, retrieval: dict[str, Any], authority_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Present direct catalogue findings without asking Qwen to synthesise them."""
    subject = _catalogue_question_subject(query)
    sources = retrieval["results"]
    if not subject:
        return None

    project_match = re.search(r"\bjob\s+(\d+)\b", query, flags=re.IGNORECASE)
    if re.match(r"^according to .*\bproject authority\b", query, flags=re.IGNORECASE) and project_match:
        project_id = project_match.group(1)
        used = [authority for authority in authority_evidence if authority.get("authority_type") == "ddr_projects" and str(authority.get("authority_id")) == project_id]
        if used:
            fields = used[0].get("fields") or {}
            requested_fields = (("project lead", "project_lead_name", ("project lead", "who led", "led by")), ("funder", "funder_name", ("funder", "funded by", "who funded")), ("duration", "duration_text", ("duration",)))
            facts = [f"{label}: {fields.get(field) or 'not established in the project authority'}" for label, field, terms in requested_fields if any(term in query.lower() for term in terms)]
            claim = f"Job {project_id} project authority records " + "; ".join(facts) + "."
            return {"answer": claim, "answer_paragraphs": [{"claims": [{"text": claim, "authority_numbers": [1]}]}], "records": [], "subject": subject, "used_authorities": used, "unused_authorities": [authority for authority in authority_evidence if authority not in used]}

    person_response = _person_authority_response(subject, sources, authority_evidence)
    if person_response and person_response["answer"] and not sources:
        return person_response

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
        "used_authorities": authority_evidence,
        "unused_authorities": [],
    }


def _source_analysis_projection(source_artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int | str]]:
    results, counts = [], {"DIRECT_SUPPORT": 0, "CONTEXTUAL_ONLY": 0, "INFERENCE_ONLY": 0, "NOT_RELEVANT": 0}
    for artifact in source_artifacts:
        analysis, telemetry, generation = artifact.get("analysis") or {}, artifact.get("execution_telemetry") or {}, artifact.get("generation") or {}
        relationship = analysis.get("relationship_to_question")
        if relationship in counts:
            counts[relationship] += 1
        results.append({"source_id": (artifact.get("packet") or {}).get("source_id"), "status": artifact.get("status", "failed"), "relationship_to_question": relationship, "direct_claims": analysis.get("direct_claims", []), "contextual_claims": analysis.get("contextual_claims", []), "possible_inferences": analysis.get("possible_inferences", []), "not_established": analysis.get("not_established", []), "parse_success": "parse_error" not in artifact, "schema_success": "parse_error" not in artifact, "input_tokens": generation.get("prompt_eval_count"), "output_tokens": generation.get("eval_count"), "stop_reason": generation.get("done_reason"), "runtime_seconds": round((artifact.get("duration_ms") or 0) / 1000, 3), "failure_code": artifact.get("failure_code"), "failure_message": artifact.get("failure_message")})
    successful = sum(item["status"] == "success" for item in results)
    return results, {"attempted_sources": len(results), "successful_sources": successful, "failed_sources": len(results) - successful, "direct_support_sources": counts["DIRECT_SUPPORT"], "contextual_sources": counts["CONTEXTUAL_ONLY"], "inference_only_sources": counts["INFERENCE_ONLY"], "not_relevant_sources": counts["NOT_RELEVANT"], "source_analysis_stage_status": "success" if successful == len(results) else ("partial" if successful else "failed")}


def _project_researcher_facing_response(
    final_claim_plan: dict[str, Any], evidence_cards: list[dict[str, Any],],
    sources: list[dict[str, Any]], authority_evidence: list[dict[str, Any]],
    evidence_map: dict[str, Any], route_family: str,
    final_synthesis: dict[str, Any] | None = None,
    narrative_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project validated answer-level prose with application-owned citations."""
    source_numbers = {
        f"{source['document_id']}:{source['chunk_id']}": index
        for index, source in enumerate(sources, start=1)
        if source.get("document_id") and source.get("chunk_id")
    }
    card_sources = {
        card.get("evidence_card_id"): card.get("source_id")
        for card in evidence_cards
        if card.get("validation_status") == "VALIDATED"
    }
    authority_numbers = {
        str(authority.get("authority_id")): index
        for index, authority in enumerate(authority_evidence, start=1)
        if authority.get("authority_id") is not None
    }
    limit_texts = {
        f"limit-{index}": str(text)
        for index, text in enumerate(evidence_map.get("NOT_ESTABLISHED", []), start=1)
    }
    claims = []
    for plan_claim in final_claim_plan.get("claims", []):
        claim_type = plan_claim.get("claim_type")
        source_ids = set(plan_claim.get("supporting_source_ids") or [])
        card_source_ids = {
            card_sources.get(card_id)
            for card_id in plan_claim.get("supporting_evidence_card_ids") or []
        }
        if claim_type in {"DIRECT_DOCUMENTARY", "RETROSPECTIVE_TESTIMONY", "QUALIFIED_SYNTHESIS"} and (
            not source_ids or source_ids != card_source_ids or not source_ids.issubset(source_numbers)
        ):
            continue
        authority_ids = plan_claim.get("supporting_authority_ids") or []
        if claim_type == "DATABASE_AUTHORITY" and not authority_ids:
            continue
        text_value = " ".join(str(plan_claim.get("text") or "").split())
        if not text_value:
            continue
        claims.append({
            "text": text_value,
            "claim_ids": [plan_claim["claim_id"]],
            "limit_ids": plan_claim.get("limit_ids") or [],
            "source_numbers": sorted(source_numbers[source_id] for source_id in source_ids),
            "authority_numbers": sorted(authority_numbers[authority_id] for authority_id in authority_ids if authority_id in authority_numbers),
            "claim_type": claim_type,
        })
    limits = [
        {"limit_id": limit_id, "explanation": limit_texts[limit_id], "origin": "validated_final_plan"}
        for limit_id in final_claim_plan.get("overall_limit_ids") or []
        if limit_id in limit_texts
    ]
    authority_claims = [claim for claim in claims if claim["claim_type"] == "DATABASE_AUTHORITY"]
    documentary_claims = [claim for claim in claims if claim["claim_type"] in {"DIRECT_DOCUMENTARY", "QUALIFIED_SYNTHESIS"}]
    testimony_claims = [claim for claim in claims if claim["claim_type"] == "RETROSPECTIVE_TESTIMONY"]
    claims_by_id = {claim["claim_ids"][0]: claim for claim in claims if claim.get("claim_ids")}
    answer_level_prose = (narrative_artifact or {}).get("prose_granularity") == "answer_level"
    per_source_fallback = (narrative_artifact or {}).get("prose_granularity") == "per_claim_fallback"
    prose_by_paragraph: dict[int, list[dict[str, Any]]] = {}
    if answer_level_prose or final_synthesis:
        for narrative_claim in (final_synthesis or {}).get("synthesis_claims", []):
            claim_ids = narrative_claim.get("claim_ids") or []
            supporting_claims = [claims_by_id[claim_id] for claim_id in claim_ids if claim_id in claims_by_id]
            if not claim_ids or len(supporting_claims) != len(claim_ids):
                continue
            text_value = " ".join(str(narrative_claim.get("text") or "").split())
            if not text_value or (
                not readable_claim_text(text_value)
                if per_source_fallback
                else researcher_prose_issues(text_value)
            ):
                continue
            prose_by_paragraph.setdefault(narrative_claim.get("paragraph", 1), []).append(
                {
                    "text": text_value,
                    "claim_ids": claim_ids,
                    "limit_ids": narrative_claim.get("limit_ids") or [],
                    "source_numbers": sorted({
                        source_number
                        for claim in supporting_claims
                        for source_number in claim["source_numbers"]
                    }),
                    "authority_numbers": sorted({
                        authority_number
                        for claim in supporting_claims
                        for authority_number in claim["authority_numbers"]
                    }),
                }
            )
    prose_paragraphs = [
        {"claims": claims}
        for _, claims in sorted(prose_by_paragraph.items())
    ]
    if route_family == "HYBRID_AUTHORITY_DOCUMENTARY":
        paragraphs = [
            *([{"title": "Database authority", "claims": authority_claims}] if authority_claims else []),
            *[
                {**paragraph, "title": "Documentary argument" if index == 0 else None}
                for index, paragraph in enumerate(prose_paragraphs)
            ],
        ]
    elif route_family == "SCOPED_MISSINGNESS":
        paragraphs = [
            {**paragraph, "title": "Historical argument" if index == 0 else None}
            for index, paragraph in enumerate(prose_paragraphs)
        ]
    else:
        paragraphs = [
            {**paragraph, "title": "Supported comparison" if route_family == "DOCUMENTARY" and any(
                claims_by_id.get(claim_id, {}).get("claim_type") == "QUALIFIED_SYNTHESIS"
                for claim_id in paragraph["claims"][0].get("claim_ids", [])
            ) else ("Research answer" if index == 0 else None)}
            for index, paragraph in enumerate(prose_paragraphs)
        ]
    used_authority_numbers = {number for claim in authority_claims for number in claim["authority_numbers"]}
    role_reconciliation = []
    if route_family == "HYBRID_AUTHORITY_DOCUMENTARY" and authority_claims and documentary_claims:
        role_reconciliation.append({
            "status": "distinct_evidence_roles",
            "authority_claim_ids": [claim_id for claim in authority_claims for claim_id in claim["claim_ids"]],
            "documentary_claim_ids": [claim_id for claim in documentary_claims for claim_id in claim["claim_ids"]],
            "authority_numbers": sorted({number for claim in authority_claims for number in claim["authority_numbers"]}),
            "source_numbers": sorted({number for claim in documentary_claims for number in claim["source_numbers"]}),
            "boundary": "Controlled authority fields and documentary role statements remain distinct. This response does not resolve a difference between them unless directly supported by evidence.",
        })
    return {
        "route_family": route_family,
        "answer_paragraphs": [paragraph for paragraph in paragraphs if paragraph["claims"]],
        "documentary_evidence": [claim for claim in documentary_claims if claim["source_numbers"]],
        "testimony_evidence": [claim for claim in testimony_claims if claim["source_numbers"]],
        "authority_evidence": [authority for index, authority in enumerate(authority_evidence, start=1) if index in used_authority_numbers],
        "evidential_limits": limits,
        "role_reconciliation": role_reconciliation,
    }


def _sources_in_answer_order(
    sources: list[dict[str, Any]], final_claim_plan: dict[str, Any], final_synthesis: dict[str, Any]
) -> list[dict[str, Any]]:
    """Order source cards by their first supporting claim in the rendered argument."""
    source_by_id = {
        f"{source.get('document_id')}:{source.get('chunk_id')}": source
        for source in sources
        if source.get("document_id") and source.get("chunk_id")
    }
    claims_by_id = {
        claim.get("claim_id"): claim
        for claim in final_claim_plan.get("claims", [])
        if claim.get("claim_id")
    }
    ordered_ids: list[str] = []
    for narrative_claim in final_synthesis.get("synthesis_claims", []):
        for claim_id in narrative_claim.get("claim_ids") or []:
            for source_id in claims_by_id.get(claim_id, {}).get("supporting_source_ids") or []:
                if source_id in source_by_id and source_id not in ordered_ids:
                    ordered_ids.append(source_id)
    ordered_sources = [source_by_id[source_id] for source_id in ordered_ids]
    return [*ordered_sources, *(source for source in sources if source not in ordered_sources)]


def _project_source_groups(
    sources: list[dict[str, Any]], evidence_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group retrieved passages by archival asset while retaining chunk-level provenance."""
    evidence_type_by_source = {
        str(card.get("source_id")): str(card.get("evidence_type") or "DIRECT_DOCUMENTARY")
        for card in evidence_cards
        if card.get("source_id")
    }
    groups: dict[str, dict[str, Any]] = {}
    for source_number, source in enumerate(sources, start=1):
        provenance = source.get("provenance") or {}
        catalogue_metadata = source.get("catalogue_metadata") or {}
        source_id = f"{source.get('document_id')}:{source.get('chunk_id')}"
        asset_key = str(
            provenance.get("asset_id_or_asset_pid")
            or source.get("asset_id_or_asset_pid")
            or provenance.get("asset_id")
            or source.get("asset_id")
            or provenance.get("asset_pid")
            or source.get("asset_pid")
            or source.get("document_id")
            or source_id
        )
        group = groups.setdefault(asset_key, {
            "asset_key": asset_key,
            "title": source.get("title") or catalogue_metadata.get("title") or source.get("document_id"),
            "date": source.get("display_date") or catalogue_metadata.get("date"),
            "pid": provenance.get("asset_pid") or source.get("asset_pid") or source.get("pid"),
            "evidence_types": [],
            "collection": provenance.get("collection_title") or provenance.get("container_title"),
            "presets": [],
            "chunks": [],
        })
        evidence_type = evidence_type_by_source.get(source_id, "DIRECT_DOCUMENTARY")
        if evidence_type not in group["evidence_types"]:
            group["evidence_types"].append(evidence_type)
        preset_id = (source.get("evidence_anchor") or {}).get("preset_id")
        if preset_id and preset_id not in group["presets"]:
            group["presets"].append(preset_id)
        group["chunks"].append({
            "source_id": source_id,
            "source_number": source_number,
            "chunk_id": source.get("chunk_id"),
            "page_start": source.get("page_start"),
            "page_end": source.get("page_end"),
            "text": source.get("excerpt") or source.get("text"),
        })
    return list(groups.values())


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
    evidence_card_types = {
        card.get("evidence_card_id"): card.get("evidence_type") or "DIRECT_DOCUMENTARY"
        for card in evidence_map.get("EVIDENCE_CARDS", [])
    }
    documentary_evidence = [
        {**claim, "origin": "documentary"}
        for claim in evidence_map["DIRECT_DOCUMENTARY"]
        if evidence_card_types.get(claim.get("evidence_card_id"), "DIRECT_DOCUMENTARY") == "DIRECT_DOCUMENTARY"
    ]
    testimony_evidence = [
        {**claim, "origin": "retrospective_testimony"}
        for claim in evidence_map["DIRECT_DOCUMENTARY"]
        if evidence_card_types.get(claim.get("evidence_card_id")) == "RETROSPECTIVE_TESTIMONY"
    ]
    source_numbers = {
        f"{source['document_id']}:{source['chunk_id']}": index
        for index, source in enumerate(retrieval["results"], start=1)
        if source.get("document_id") and source.get("chunk_id")
    }
    claim_plan = pipeline.get("final_claim_plan") or {}
    claim_plan_by_id = {
        claim.get("claim_id"): claim
        for claim in claim_plan.get("claims", [])
        if claim.get("claim_id")
    }
    evidence_cards_by_id = {
        card.get("evidence_card_id"): card
        for card in evidence_map.get("EVIDENCE_CARDS", [])
        if card.get("evidence_card_id")
        and card.get("validation_status") == "VALIDATED"
        and card.get("source_id") in source_numbers
    }

    def documentary_claim_has_valid_card(claim: dict[str, Any]) -> bool:
        if claim.get("claim_type") not in {"DIRECT_DOCUMENTARY", "QUALIFIED_SYNTHESIS"}:
            return True
        supporting_source_ids = set(claim.get("supporting_source_ids") or [])
        supporting_card_ids = claim.get("supporting_evidence_card_ids") or []
        cards = [evidence_cards_by_id.get(card_id) for card_id in supporting_card_ids]
        card_source_ids = {card["source_id"] for card in cards if card}
        return bool(supporting_source_ids and cards) and card_source_ids == supporting_source_ids

    renderable_claim_plan_by_id = {
        claim_id: claim
        for claim_id, claim in claim_plan_by_id.items()
        if documentary_claim_has_valid_card(claim)
    }
    cross_source_inference_provenance = []
    inference_sources = cross_source.get("cross_source_inference_sources", {})
    for index, inference in enumerate(cross_source.get("cross_source_inferences", []), start=1):
        inference_id = f"cross-source-inference-{index}"
        supporting_source_ids = list(dict.fromkeys(inference_sources.get(inference, [])))
        compiled_claim_ids = sorted(
            claim_id for claim_id, claim in claim_plan_by_id.items()
            if inference_id in claim.get("supporting_cross_source_inference_ids", [])
        )
        cross_source_inference_provenance.append({
            "inference_id": inference_id,
            "text": inference,
            "supporting_source_ids": supporting_source_ids,
            "supporting_source_numbers": sorted({
                source_numbers[source_id]
                for source_id in supporting_source_ids
                if source_id in source_numbers
            }),
            "compiled_claim_ids": compiled_claim_ids,
            "status": "accepted" if compiled_claim_ids else "rejected_unmapped",
        })
    rejected_cross_source_inferences = list(
        (pipeline.get("cross_source_artifact") or {}).get("rejected_inferences", [])
    )
    cross_source_inference_diagnostics = {
        "cross_source_inferences_total": len(cross_source_inference_provenance),
        "cross_source_inferences_mapped": sum(item["status"] == "accepted" for item in cross_source_inference_provenance),
        "cross_source_inferences_unmapped": sum(item["status"] != "accepted" for item in cross_source_inference_provenance),
        "cross_source_inferences_rejected": len(rejected_cross_source_inferences),
        "cross_source_status": (pipeline.get("stage_execution") or {}).get("cross_source_analysis", {}).get("status", "success"),
        "cross_source_failure_code": (pipeline.get("cross_source_artifact") or {}).get("failure_code"),
        "cross_source_stop_reason": (pipeline.get("cross_source_artifact") or {}).get("cross_source_stop_reason"),
        "cross_source_truncated": bool((pipeline.get("cross_source_artifact") or {}).get("cross_source_truncated")),
    }
    narrative_claims = []
    for claim in final_synthesis.get("synthesis_claims", []):
        claim_ids = claim.get("claim_ids", [])
        if claim_ids:
            if not set(claim_ids).issubset(renderable_claim_plan_by_id):
                continue
            supporting_source_ids = [
                source_id
                for claim_id in claim_ids
                for source_id in renderable_claim_plan_by_id[claim_id].get("supporting_source_ids", [])
            ]
            narrative_claims.append({
                **claim,
                "source_numbers": sorted({
                    source_numbers[source_id]
                    for source_id in supporting_source_ids
                    if source_id in source_numbers
                }),
                "authority_ids": sorted({
                    authority_id
                    for claim_id in claim_ids
                    for authority_id in renderable_claim_plan_by_id[claim_id].get("supporting_authority_ids", [])
                }),
            })
    cited_narrative_numbers = {
        source_number
        for claim in narrative_claims
        for source_number in claim.get("source_numbers", [])
    }
    source_document_ids = {
        source_number: source["document_id"]
        for source_number, source in enumerate(retrieval["results"], start=1)
        if source.get("document_id")
    }
    cited_document_ids = {
        source_document_ids[source_number]
        for source_number in cited_narrative_numbers
        if source_number in source_document_ids
    }
    narrative_coverage_complete = bool(narrative_claims) and cited_narrative_numbers.issubset(set(source_document_ids))
    narrative_citations_resolvable = bool(narrative_claims) and cited_narrative_numbers.issubset(set(source_document_ids)) and all(
        claim.get("source_numbers") or claim.get("authority_ids")
        for claim in narrative_claims
    )
    answer_paragraphs = []
    if narrative_citations_resolvable:
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
                "claim_ids": claim.get("claim_ids", []),
                "limit_ids": claim.get("limit_ids", []),
                "authority_ids": claim.get("authority_ids", []),
            })
        rendered_paragraphs = [" ".join(paragraphs[paragraph]) for paragraph in sorted(paragraphs)]
        answer_paragraphs = [
            {"claims": claims_by_paragraph[paragraph]}
            for paragraph in sorted(claims_by_paragraph)
        ]
        if rendered_paragraphs:
            answer = "\n\n".join(rendered_paragraphs)
            answer_origin = (
                "curated_cited_evidence_synthesis"
                if (pipeline.get("narrative_artifact") or {}).get("deterministic_fallback")
                == "CURATED_ELECTROHOME_PASSAGE_SYNTHESIS"
                else "model_cited_evidence_synthesis"
            )
    if (
        (
            (pipeline.get("narrative_artifact") or {}).get("deterministic_fallback")
            or (pipeline.get("stage_execution") or {}).get("cross_source_analysis", {}).get("status") == "failed"
        )
        and not answer_origin
    ):
        fallback_claims = []
    explicit_title_sources = str(
        retrieval.get("transparency", {}).get("strategy") or ""
    ).startswith("explicit_source_title_")
    explicit_person_sources = (
        retrieval.get("transparency", {}).get("strategy")
        == "explicit_person_authority_v1"
    )
    if explicit_person_sources and documentary_evidence and not answer_origin:
        person_claims = []
        for claim in documentary_evidence:
            source_id = claim.get("source_id")
            claim_text = " ".join(str(claim.get("claim") or "").split())
            citation = source_numbers.get(source_id)
            if claim_text and citation:
                person_claims.append({"text": claim_text, "source_numbers": [citation]})
        if person_claims:
            answer_paragraphs = [{"claims": person_claims}]
            answer = " ".join(claim["text"] for claim in person_claims)
            answer_origin = "validated_person_evidence_synthesis"
    deterministic_claims = []
    for plan_claim in renderable_claim_plan_by_id.values():
        if plan_claim.get("claim_type") != "DIRECT_DOCUMENTARY":
            continue
        claim_text = " ".join(str(plan_claim.get("text") or "").split())
        supporting_source_ids = plan_claim.get("supporting_source_ids") or []
        citations = sorted({
            source_numbers[source_id]
            for source_id in supporting_source_ids
            if source_id in source_numbers
        })
        if claim_text and citations and not (
            explicit_title_sources
            and claim_text == "The named document addresses the question in the cited passage."
        ):
            deterministic_claims.append({
                "text": claim_text,
                "claim_ids": [plan_claim["claim_id"]],
                "limit_ids": plan_claim.get("limit_ids", []),
                "source_numbers": citations,
                "authority_ids": [],
            })
    narrative_fallback = str(
        (pipeline.get("narrative_artifact") or {}).get("deterministic_fallback") or ""
    )
    if (
        not answer_origin
        and deterministic_claims
        and narrative_fallback == "INVALID_PROSE_EVIDENCE_LABEL"
    ):
        answer_paragraphs = [{"claims": deterministic_claims}]
        answer = " ".join(
            f"{claim['text']} [{', '.join(map(str, claim['source_numbers']))}]"
            for claim in deterministic_claims
        )
        answer_origin = "validated_claim_plan_fallback"
    direct_support_sources = [
        source for source in retrieval["results"]
        if (next((item for item in evidence_map["source_classifications"] if item["source_id"] == f"{source['document_id']}:{source['chunk_id']}"), {}).get("relationship_to_question") == "DIRECT_SUPPORT")
    ]
    selected_document_sources = (
        retrieval.get("transparency", {}).get("strategy") == "explicit_document_selection_v1"
    )
    fallback_sources = (
        retrieval["results"]
        if selected_document_sources or explicit_title_sources
        else direct_support_sources
    )
    authority_only_bounded_plan = (
        bool(claim_plan.get("claims"))
        and bool(claim_plan.get("open_uncertainties"))
        and all(claim.get("claim_type") == "DATABASE_AUTHORITY" for claim in claim_plan["claims"])
    )
    if (
        fallback_sources
        and not answer_origin
        and not authority_only_bounded_plan
        and (not documentary_evidence or explicit_title_sources)
    ):
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
            answer = (
                "Relevant passages were retained, but no validated documentary claim could be produced for this run. "
                "Inspect the retrieved sources and diagnostic trail."
            )
            answer_origin = "unvalidated_source_passages"
    stage_records = pipeline.get("stage_execution") or {}
    source_analysis_results, source_analysis_summary = _source_analysis_projection(pipeline.get("source_analyses") or [])
    source_analysis_status = (stage_records.get("source_analysis") or {}).get("status", "success")
    has_failed_pipeline_stage = any(
        stage not in {"cross_source_analysis", "narrative_repair"}
        and record.get("status") == "failed"
        for stage, record in stage_records.items()
    )
    evidence_analysis_completed = source_analysis_status == "success" and not has_failed_pipeline_stage
    validation_results = pipeline.get("narrative_validation") or []
    has_repairable_validation_failure = any(
        result.get("status") == "fail" and result.get("severity") == "repairable"
        for result in validation_results
    )
    if (
        not answer_origin
        and retrieval["results"]
        and not claim_plan.get("claims")
        and claim_plan.get("open_uncertainties")
        and evidence_analysis_completed
    ):
        answer = (
            "The selected records remain inspectable context, but they do not provide admissible "
            "direct evidence for the requested claim. " + str(claim_plan["open_uncertainties"][0])
        )
        answer_paragraphs = []
        answer_origin = "deterministic_evidence_limit"
    if not answer_origin and retrieval["results"] and not evidence_map["DIRECT_DOCUMENTARY"]:
        if (
            rejected_cross_source_inferences
            or (stage_records.get("cross_source_analysis") or {}).get("status") == "failed"
        ) and not claim_plan.get("claims"):
            answer = (
                "Relevant evidence was retrieved, but no validated cross-source synthesis "
                "could be produced for this run. Inspect the retained sources and diagnostic trail."
            )
            answer_paragraphs = []
            answer_origin = "pipeline_synthesis_unavailable"
        else:
            source_labels = []
            for source in retrieval["results"][:5]:
                title = str(source.get("snapshot", {}).get("title") or source.get("title") or source.get("document_id") or "Untitled record")
                provenance = source.get("provenance") or {}
                asset_pid = provenance.get("asset_pid") or source.get("asset_pid") or source.get("pid") or "unavailable"
                page = source.get("page_start") or source.get("source_page") or "unavailable"
                source_labels.append(f"{title} (Asset PID {asset_pid}, p. {page})")
            if source_labels and evidence_analysis_completed:
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
    if answer_origin == "deterministic_evidence_limit":
        answer_state = AnswerState.EVIDENTIAL_LIMIT
    elif answer_origin in {"unvalidated_source_passages", "pipeline_synthesis_unavailable"}:
        answer_state = AnswerState.SYNTHESIS_UNAVAILABLE
    elif not evidence_analysis_completed and retrieval["results"]:
        answer = (
            "Relevant evidence was retrieved, but a validated synthesis could not be produced for this run. "
            "Inspect the retained sources and diagnostic trail."
        )
        answer_paragraphs = []
        answer_origin = answer_origin or "pipeline_synthesis_unavailable"
        answer_state = AnswerState.SYNTHESIS_UNAVAILABLE
    elif answer_origin and (
        source_analysis_status == "partial"
        or has_repairable_validation_failure
        or (stage_records.get("cross_source_analysis") or {}).get("status") == "failed"
    ):
        answer_state = AnswerState.SYNTHESIS_PARTIAL
    elif answer_origin and retrieval.get("transparency", {}).get("route_family") in {"DOCUMENTARY", "HYBRID_AUTHORITY_DOCUMENTARY"} and not any(
        claim.get("claim_type") == "DIRECT_DOCUMENTARY"
        for claim in renderable_claim_plan_by_id.values()
    ):
        if claim_plan.get("open_uncertainties"):
            answer = (
                f"{answer}\n\nThe retained documentary context does not provide admissible direct support. "
                f"{claim_plan['open_uncertainties'][0]}"
            )
            answer_paragraphs = []
            answer_origin = "deterministic_evidence_limit"
            answer_state = AnswerState.EVIDENTIAL_LIMIT
        else:
            answer = (
                "Relevant evidence was retrieved, but no validated final documentary claim "
                "could be produced for this run. Inspect the retained sources and diagnostic trail."
            )
            answer_paragraphs = []
            answer_origin = "pipeline_synthesis_unavailable"
            answer_state = AnswerState.SYNTHESIS_UNAVAILABLE
    elif answer_origin:
        answer_state = AnswerState.SYNTHESIS_VALID
    else:
        if (
            retrieval["results"]
            and claim_plan.get("open_uncertainties")
            and claim_plan.get("claims")
            and all(claim.get("claim_type") == "DATABASE_AUTHORITY" for claim in claim_plan["claims"])
        ):
            answer = (
                "The authority record provides context, but the retained documentary evidence does not provide "
                "admissible direct support. " + str(claim_plan["open_uncertainties"][0])
            )
            answer_origin = "deterministic_evidence_limit"
            answer_state = AnswerState.EVIDENTIAL_LIMIT
        elif retrieval["results"]:
            answer = (
                "Relevant evidence was retrieved, but readable, validated research prose "
                "could not be produced for this run. Inspect the retained sources and diagnostic trail."
            )
            answer_origin = "pipeline_synthesis_unavailable"
            answer_state = AnswerState.SYNTHESIS_UNAVAILABLE
        else:
            answer_state = AnswerState.SYNTHESIS_UNAVAILABLE
    synthesis_failure = None
    if answer_state == AnswerState.SYNTHESIS_UNAVAILABLE:
        failed_stage = next(
            (
                (stage, record)
                for stage, record in stage_records.items()
                if record.get("status") == "failed"
            ),
            None,
        )
        if source_analysis_status == "partial":
            failure_code = "evidence_validation_failed"
            failure_message = "Evidence validation did not permit a bounded final synthesis."
        elif retrieval["results"] and not claim_plan.get("claims") and not failed_stage:
            failure_code = "no_admissible_claims"
            failure_message = "Retrieved material did not yield a validated final claim."
        elif failed_stage:
            failure_code = "synthesis_service_error"
            failure_message = failed_stage[1].get("failure_message") or failed_stage[1].get("failure_code") or "A synthesis stage failed."
        else:
            failure_code = "evidence_validation_failed"
            failure_message = "Evidence validation did not permit a bounded final synthesis."
        synthesis_failure = {
            "code": failure_code,
            "message": failure_message,
            "stage": failed_stage[0] if failed_stage else None,
        }
    cited_source_numbers = sorted({
        source_number
        for paragraph in answer_paragraphs
        for claim in paragraph.get("claims", [])
        for source_number in claim.get("source_numbers", [])
    })
    response = {
        "answer": answer,
        "answer_paragraphs": answer_paragraphs,
        "answer_origin": answer_origin,
        "answer_state": answer_state.value,
        "synthesis_failure": synthesis_failure,
        "documentary_evidence": documentary_evidence,
        "testimony_evidence": testimony_evidence,
        "evidence_cards": evidence_map.get("EVIDENCE_CARDS", []),
        "evidence_ledger": evidence_map.get("EVIDENCE_LEDGER", []),
        "source_groups": _project_source_groups(
            retrieval["results"], evidence_map.get("EVIDENCE_CARDS", []),
        ),
        "rejected_evidence_cards": evidence_map.get("REJECTED_EVIDENCE_CARDS", []),
        "authority_evidence": evidence_map.get("DATABASE_AUTHORITY", []),
        "archival_associations": evidence_map.get("ARCHIVAL_METADATA", []),
        "contextual_evidence": [
            {**claim, "origin": "model"}
            for claim in evidence_map["CONTEXTUAL"]
        ],
        "inferences": interpretations,
        "cross_source_inference_provenance": cross_source_inference_provenance,
        "cross_source_inference_diagnostics": cross_source_inference_diagnostics,
        "final_claim_plan": claim_plan,
        "claim_validation": pipeline.get("claim_validation") or {},
        "missingness_decision": pipeline.get("missingness_decision"),
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
            "records": stage_records,
            "validation_results": validation_results,
            "narrative_coverage": {
                "complete": narrative_coverage_complete,
                "required_source_ids": list(source_numbers),
                "returned_source_numbers": sorted(cited_narrative_numbers),
            },
        },
        "source_usage": {
            "retrieved_source_numbers": sorted(source_document_ids),
            "retained_evidence_source_ids": sorted({claim["source_id"] for claim in documentary_evidence}),
            "cited_source_numbers": cited_source_numbers,
            "unused_source_numbers": sorted(set(source_document_ids) - set(cited_source_numbers)),
        },
        "source_analysis_results": source_analysis_results,
        "source_analysis_summary": source_analysis_summary,
    }
    return response


def _synthesis_unavailable_response(
    request: ExploratoryInterrogationRequest,
    retrieval: dict[str, Any],
    *,
    stage: str,
    failure_code: str,
    failure_message: str,
    authority_evidence: list[dict[str, Any]] | None = None,
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sources = retrieval["results"]
    authority_evidence = authority_evidence or []
    if sources:
        limitation = (
            "Relevant documentary passages were retrieved, but a validated synthesis could "
            "not be produced for this run. The retained passages remain available for review; "
            "this generation failure does not establish historical absence."
        )
    else:
        limitation = (
            f"No admissible documentary passage was retrieved in {settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION}. "
            "This is a retrieval or corpus-representation limit, not evidence that the "
            "historical records or activity were absent."
        )
        available_records = retrieval.get("document_availability") or []
        if available_records:
            labels = [
                f"{item.get('label') or item.get('asset_pid') or 'Matched archive asset'} "
                f"(Asset PID {item.get('asset_pid') or 'unavailable'}; {item.get('classification') or 'availability unresolved'})"
                for item in available_records[:4]
            ]
            limitation += " Matched archive traces: " + "; ".join(labels) + "."
    authority_answer = _deterministic_authority_response(authority_evidence)["answer"] if authority_evidence else ""
    return {
        "query_id": f"exploratory-{uuid.uuid4().hex[:12]}",
        "mode": request.mode,
        "response_schema": "turin-evidence-pipeline-v2-exploratory-projection",
        "status": "completed",
        "answer": "\n\n".join(part for part in (authority_answer, limitation) if part),
        "answer_paragraphs": [],
        "answer_origin": "pipeline_synthesis_unavailable",
        "answer_state": AnswerState.SYNTHESIS_UNAVAILABLE.value,
        "synthesis_failure": {
            "code": failure_code,
            "message": failure_message,
            "stage": stage,
        },
        "model": model or {"name": "unavailable", "display_name": "Active local runtime", "runtime": "failed"},
        "retrieved_evidence": sources,
        "source_groups": _project_source_groups(sources, []),
        "documentary_evidence": [],
        "authority_evidence": authority_evidence,
        "archival_associations": [],
        "contextual_evidence": [],
        "inferences": [],
        "contradictions": [],
        "missingness": [{"category": failure_code, "scope": "configured_corpus_and_retrieved_passages", "explanation": limitation}],
        "archival_discovery": retrieval.get("archival_discovery", []),
        "document_availability": retrieval.get("document_availability", []),
        "corpus_representation_gaps": retrieval.get("corpus_representation_gaps", []),
        "archival_context_only": retrieval.get("archival_context_only", []),
        "source_usage": {
            "retrieved_source_numbers": list(range(1, len(sources) + 1)),
            "retained_evidence_source_ids": [],
            "cited_source_numbers": [],
            "unused_source_numbers": list(range(1, len(sources) + 1)),
        },
        "evidence_anchors": [
            source.get("evidence_anchor") or {
                "document_id": source.get("document_id"),
                "chunk_id": source.get("chunk_id"),
                "page": source.get("page_start"),
            }
            for source in sources
            if source.get("chunk_id")
        ],
        "authority_roles": {
            "resolved_deterministic_authority": bool(authority_evidence),
            "qwen_authority_context": {"supplied": False},
        },
        "stage_execution": {
            "classification": "EXPLORATORY / NON-FORMAL INTERROGATION",
            "stages": [stage],
            "call_count": 0,
            "records": {
                stage: {
                    "status": "failed",
                    "failure_code": failure_code,
                    "failure_message": failure_message,
                    "parse_success": False,
                    "schema_valid": False,
                    "repair_attempted": False,
                    "repair_success": None,
                },
            },
        },
        "retrieval": retrieval.get("transparency", {}),
        "retrieval_diagnostics": retrieval.get("diagnostics", {}),
        "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
        "persisted": False,
    }


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
    evidence_records = []
    for source in sources:
        evidence_payload = {
            "run_id": run_id,
            "rank": source.get("rank") or 1,
            "chunk_id": source["chunk_id"],
            "document_id": source["document_id"],
            "supplied_excerpt": source.get("text") or "",
            "snapshot_json": source,
        }
        evidence_records.append(ExperimentRunEvidence(
            run_id=run_id, rank=source.get("rank") or 1, score=source.get("score"),
            document_id=source["document_id"], pid=source.get("pid"), archive_record_pid=source.get("archive_record_pid"),
            archive_resolution_status=source.get("archive_resolution_status") or "archive_resolved_current",
            page_start=source.get("page_start"), page_end=source.get("page_end"), chunk_id=source["chunk_id"],
            chunk_sequence=source.get("chunk_sequence"), excerpt=source.get("text") or "", supplied_excerpt=source.get("text") or "",
            included_in_context=True, original_chars=len(source.get("text") or ""), supplied_chars=len(source.get("text") or ""),
            excerpted=False, snapshot_json=source, evidence_sha256=experiment_evidence_digest(evidence_payload),
        ))
    run.output_sha256 = experiment_run_digest(
        {
            "run_id": run.run_id,
            "research_question": run.exact_research_question,
            "corpus_version": run.corpus_version,
            "git_commit": run.git_commit,
            "retrieval_config_json": run.retrieval_config_json,
            "model_parameters_json": run.model_parameters_json,
            "structured_response_json": run.structured_response_json,
            "provenance_validation_json": run.provenance_validation_json,
            "status": run.status,
        },
        [item.evidence_sha256 for item in evidence_records],
    )
    db.add(run)
    for evidence in evidence_records:
        db.add(evidence)
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
async def interrogate_exploratory_corpus(request: ExploratoryInterrogationRequest, http_request: Request = None):
    """Run an ephemeral model-backed corpus interrogation without formal-run persistence."""
    if request.mode not in {"exploratory", "comparison", CAPTURE_MODE}:
        raise HTTPException(status_code=400, detail="Unsupported source interrogation mode.")
    started = time.perf_counter()
    scope_overview_request = _is_archive_scope_overview_request(request)
    collection_subject = _collection_question_subject(request.query) if request.mode == "exploratory" and not request.target_document_ids and not request.archive_record_pid else None
    collection = _collection_membership_response(
        collection_subject,
        _collection_membership_records(collection_subject, request.top_k),
    ) if collection_subject else None
    if collection:
        return {
            "query_id": f"exploratory-collection-{uuid.uuid4().hex[:12]}", "mode": "exploratory",
            "response_schema": "turin-archive-collection-membership-v1", "status": "completed",
            "answer": collection["answer"], "answer_origin": "deterministic_archive_collection_result",
            "answer_state": AnswerState.SYNTHESIS_VALID.value,
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
    route_decision = classify_question_route(request.query)
    if (
        settings.TURIN_GRANITE_DOCUMENTARY_ENABLED
        and request.mode == "exploratory"
        and route_decision.family in {"DOCUMENTARY", "HYBRID_AUTHORITY_DOCUMENTARY"}
        and not scope_overview_request
    ):
        return await research_answer_corpus(request)
    thematic_preset = matching_archive_question_preset(request.query)
    thematic_document_question = thematic_preset is not None
    authority_evidence = _catalogue_authorities(request.query, request.top_k) if (
        request.mode == "exploratory"
        and not request.target_document_ids
        and not scope_overview_request
        and (route_decision.family == "HYBRID_AUTHORITY_DOCUMENTARY" or not thematic_document_question)
    ) else []
    retrieval_started = time.perf_counter()
    if route_decision.family == "AUTHORITY_ONLY":
        retrieval = {
            "results": [], "archival_discovery": [], "document_availability": [],
            "corpus_representation_gaps": [], "archival_context_only": [],
            "transparency": {"strategy": "deterministic_authority_lookup_v1", "route_family": route_decision.family, "route_decision": route_decision.as_dict(), "resolved_entities": [], "query_variants": []},
            "diagnostics": {"archive_candidate_count": 0, "retrieved_documentary_source_count": 0},
        }
    else:
        try:
            retrieval = _retrieve_exploratory(request)
            retrieval["transparency"]["route_family"] = route_decision.family
            retrieval["transparency"]["route_decision"] = route_decision.as_dict()
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
    _hydrate_source_display_dates(sources)
    scoped_overview = retrieval.get("transparency", {}).get("strategy") == "archive_scope_overview_v1"
    if route_decision.family == "AUTHORITY_ONLY":
        authority_response = _deterministic_authority_response(authority_evidence)
        return {
            "query_id": f"exploratory-authority-{uuid.uuid4().hex[:12]}", "mode": "exploratory",
            "response_schema": "turin-authority-result-v2", "status": "completed",
            "answer": authority_response["answer"], "answer_paragraphs": authority_response["answer_paragraphs"],
            "answer_origin": "deterministic_authority_result", "answer_state": AnswerState.SYNTHESIS_VALID.value,
            "model": {"name": "none", "display_name": "Authority lookup", "runtime": "deterministic"}, "runtime": {"model_status": "not_used"},
            "retrieved_evidence": [], "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [],
            "provenance_validation": {"valid": bool(authority_evidence), "source_count": 0, "claim_count": len(authority_response["answer_paragraphs"]), "claim_provenance": []},
            "documentary_evidence": [], "authority_evidence": authority_evidence, "archival_associations": [], "contextual_evidence": [], "inferences": [], "contradictions": [], "missingness": [],
            "authority_roles": {"planner_entity_resolution": [], "controlled_lexical_expansion": {"used": False, "variants": []}, "retrieval_nomination": {"used": False}, "qwen_authority_context": {"supplied": False}, "persisted_authority_audit": {"persisted": False}},
            "stage_execution": {"classification": "DETERMINISTIC AUTHORITY LOOKUP", "stages": ["authority_lookup"], "call_count": 0},
            "source_classifications": [], "selected_sources_accounted_for": {"count": 0, "total": 0}, "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"],
            "timings": {"query_planning_and_retrieval_ms": retrieval_ms, "total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1)}, "inference_calls": [],
            "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": False, "final_claim_plan": authority_response["final_claim_plan"],
            "authority_provenance": authority_response["authority_provenance"], "authority_boundaries": authority_response["authority_boundaries"],
        }
    catalogue = _catalogue_response(request.query, retrieval, authority_evidence)
    if (
        catalogue
        and request.mode == "exploratory"
        and not request.target_document_ids
        and not scoped_overview
        and not _requires_documentary_evidence(request.query)
        and not (_named_employment_authority(authority_evidence) and sources)
    ):
        return {
            "query_id": f"exploratory-catalogue-{uuid.uuid4().hex[:12]}",
            "mode": "exploratory",
            "response_schema": "turin-catalogue-result-v1",
            "status": "completed",
            "answer": catalogue["answer"],
            "answer_paragraphs": catalogue["answer_paragraphs"],
            "answer_origin": "deterministic_catalogue_result",
            "answer_state": AnswerState.SYNTHESIS_VALID.value,
            "model": {"name": "none", "display_name": "Catalogue lookup", "runtime": "deterministic"},
            "runtime": {"model_status": "not_used"},
            "retrieved_evidence": sources,
            "archival_discovery": retrieval["archival_discovery"],
            "document_availability": retrieval["document_availability"],
            "corpus_representation_gaps": retrieval["corpus_representation_gaps"],
            "archival_context_only": retrieval["archival_context_only"],
            "provenance_validation": {"valid": all(bool(source.get("provenance")) for source in sources), "source_count": len(sources), "claim_count": 0, "claim_provenance": []},
            "documentary_evidence": [], "authority_evidence": catalogue.get("used_authorities", authority_evidence), "unused_authorities": catalogue.get("unused_authorities", []), "archival_associations": [], "contextual_evidence": [],
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
            "answer_state": AnswerState.EVIDENTIAL_LIMIT.value,
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
        raise HTTPException(status_code=503, detail="Active research runtime is unavailable for exploratory interrogation.")
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
                "model_config": {**model_info, "temperature": inference_service.temperature, "output_token_limit": inference_service.final_synthesis_max_output_tokens, "model_calls": 1},
                "claim_provenance": claims, "source_classifications": source_classifications,
            })
        finally:
            capture_db.close()
        return {"capture_id": capture_id, "query_id": capture_id, "question_id": request.question_id, "mode": CAPTURE_MODE, "capture_classification": "RESEARCHER_UI_CAPTURE", "status": "completed", "answer": generated["raw_response"], "answer_state": AnswerState.SYNTHESIS_VALID.value, "model": {"name": model_info["model"], "display_name": model_info["display_name"], "runtime": model_info["runtime"]}, "runtime": model_info, "retrieved_evidence": classified_sources, "archival_discovery": retrieval["archival_discovery"], "document_availability": retrieval["document_availability"], "corpus_representation_gaps": retrieval["corpus_representation_gaps"], "archival_context_only": retrieval["archival_context_only"], "provenance_validation": provenance, "documentary_evidence": [], "contextual_evidence": [], "inferences": [], "missingness": [{"category": "not_established", "explanation": claim["claim_text"]} for claim in limits], "source_classifications": source_classifications, "selected_sources_accounted_for": {"count": len(classified_sources), "total": len(classified_sources)}, "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"], "timings": {"query_planning_and_retrieval_ms": retrieval_ms}, "inference_calls": [{"stage": "researcher_ui_capture_one_shot", "count": 1}], "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": True}
    try:
        packet_started = time.perf_counter()
        named_document = str(
            retrieval.get("transparency", {}).get("strategy") or ""
        ).startswith("explicit_source_title_") or scoped_overview
        packets = _build_exploratory_packets(sources, named_document=named_document)
        packet_ms = round((time.perf_counter() - packet_started) * 1000, 1)
        diagnostic_snapshot = None
        if http_request and http_request.headers.get("X-ML-Triage-Diagnostic-Snapshot") == "true":
            diagnostic_snapshot = {
                "run_id": http_request.headers["X-ML-Triage-Run-ID"],
                "uat_id": http_request.headers["X-ML-Triage-UAT-ID"],
                "route": retrieval.get("transparency", {}).get("strategy"),
                "corpus": {"version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION},
                "resolved_authority_records": authority_evidence,
                "authority_context_passed_to_final": [],
            }
        pipeline = await StagedEvidencePipeline(inference_service).run(
            request.query,
            packets,
            policy=matching_turin_question_policy(request.query),
            allow_document_content_claims=True,
            thematic_document_question=thematic_document_question,
            diagnostic_snapshot=diagnostic_snapshot,
            route_family=route_decision.family,
            retrieval_diagnostics=retrieval.get("diagnostics"),
        )
    except EvidencePipelineStageError as exc:
        return _synthesis_unavailable_response(
            request,
            retrieval,
            stage=exc.stage,
            failure_code="pipeline_stage_error",
            failure_message=str(exc),
            authority_evidence=authority_evidence,
            model=inference_service.get_model_info(),
        )
    except InferenceTimeoutError as exc:
        raise HTTPException(status_code=504, detail={
            "error": "inference_timeout",
            "stage": exc.stage,
            "message": str(exc),
            "answer_state": AnswerState.SYNTHESIS_UNAVAILABLE.value,
            "answer_origin": "pipeline_timeout",
            "retrieved_source_count": len(sources),
        }) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        return _synthesis_unavailable_response(
            request,
            retrieval,
            stage="evidence_validation",
            failure_code="pipeline_validation_error",
            failure_message=str(exc),
            authority_evidence=authority_evidence,
            model=inference_service.get_model_info(),
        )
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
    projection_started = time.perf_counter()
    sources = _sources_in_answer_order(sources, pipeline["final_claim_plan"], pipeline["final_synthesis"])
    retrieval["results"] = sources
    projection = _project_staged_exploratory_response(pipeline, retrieval)
    projection_ms = round((time.perf_counter() - projection_started) * 1000, 1)
    projection["authority_evidence"] = authority_evidence
    projection["evidence_ledger"] = _merge_authority_evidence_ledger(
        projection["evidence_ledger"], authority_evidence,
    )
    projection["authority_roles"]["resolved_deterministic_authority"] = bool(authority_evidence)
    if route_decision.family == "HYBRID_AUTHORITY_DOCUMENTARY":
        authority_projection = _deterministic_authority_response(authority_evidence)
        authority_claims = authority_projection["final_claim_plan"]["claims"]
        authority_claim_violations = _authority_claim_violations(authority_claims, authority_evidence)
        if authority_claim_violations:
            projection["answer_state"] = AnswerState.SYNTHESIS_UNAVAILABLE.value
            projection["answer_origin"] = "authority_consistency_validation_error"
            projection["answer"] = "Structured authority claims could not be validated for rendering."
            projection["answer_paragraphs"] = []
            authority_claims = []
        elif authority_claims:
            if not projection["answer_paragraphs"]:
                source_numbers = {
                    f"{source.get('document_id')}:{source.get('chunk_id')}": index
                    for index, source in enumerate(sources, start=1)
                    if source.get("document_id") and source.get("chunk_id")
                }
                documentary_claims = []
                for claim in projection["final_claim_plan"].get("claims", []):
                    if claim.get("claim_type") != "DIRECT_DOCUMENTARY":
                        continue
                    citations = sorted({
                        source_numbers[source_id]
                        for source_id in claim.get("supporting_source_ids", [])
                        if source_id in source_numbers
                    })
                    if claim.get("text") and citations:
                        documentary_claims.append({
                            "text": claim["text"],
                            "claim_ids": [claim["claim_id"]],
                            "source_numbers": citations,
                            "authority_numbers": [],
                        })
                if documentary_claims:
                    projection["answer_paragraphs"] = [{"claims": documentary_claims}]
                    projection["answer"] = " ".join(
                        f"{claim['text']} [{', '.join(map(str, claim['source_numbers']))}]"
                        for claim in documentary_claims
                    )
                    projection["answer_origin"] = "validated_claim_plan_fallback"
                    projection["answer_state"] = AnswerState.SYNTHESIS_VALID.value
            if (
                projection["answer_origin"] == "unvalidated_source_passages"
                and projection["final_claim_plan"].get("open_uncertainties")
                and not any(
                    claim.get("claim_type") == "DIRECT_DOCUMENTARY"
                    for claim in projection["final_claim_plan"].get("claims", [])
                )
            ):
                projection["answer"] = (
                    "The retained documentary evidence does not provide admissible direct support. "
                    + str(projection["final_claim_plan"]["open_uncertainties"][0])
                )
                projection["answer_paragraphs"] = []
                projection["answer_origin"] = "deterministic_evidence_limit"
                projection["answer_state"] = AnswerState.EVIDENTIAL_LIMIT.value
            documentary_answer = projection["answer"]
            projection["final_claim_plan"]["claims"] = [
                *authority_claims,
                *projection["final_claim_plan"].get("claims", []),
            ]
            projection["answer_paragraphs"] = [
                {
                    "claims": [
                        {
                            "text": claim["text"],
                            "claim_ids": [claim["claim_id"]],
                            "source_numbers": [],
                            "authority_numbers": [index],
                        }
                        for index, claim in enumerate(authority_claims, start=1)
                    ]
                },
                *projection["answer_paragraphs"],
            ]
            projection["answer"] = "\n\n".join(
                part for part in (authority_projection["answer"], documentary_answer) if part
            )
        if not authority_evidence:
            projection["answer_state"] = AnswerState.SYNTHESIS_UNAVAILABLE.value
            projection["answer_origin"] = "required_authority_unavailable"
            projection["answer"] = (
                "A required database authority component could not be resolved; "
                "a hybrid synthesis is unavailable for this run."
            )
    projection["researcher_facing"] = _project_researcher_facing_response(
        projection["final_claim_plan"], projection["evidence_cards"], sources,
        authority_evidence, pipeline["evidence_map"], route_decision.family,
        final_synthesis=pipeline["final_synthesis"],
        narrative_artifact=pipeline.get("narrative_artifact"),
    )
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
        "answer_state": projection["answer_state"],
        "researcher_facing": projection["researcher_facing"],
        "model": {"name": model_info["model"], "display_name": model_info["display_name"], "runtime": model_info["runtime"]},
        "runtime": model_info,
        "retrieved_evidence": classified_sources,
        "archival_discovery": retrieval["archival_discovery"],
        "document_availability": retrieval["document_availability"],
        "corpus_representation_gaps": retrieval["corpus_representation_gaps"],
        "archival_context_only": retrieval["archival_context_only"],
        "provenance_validation": {"valid": all(bool(source.get("provenance")) for source in sources) and provenance["source_analyses"]["valid"] and provenance["final_synthesis"]["valid"], "source_count": len(sources), "claim_count": len(claim_provenance), "claim_provenance": claim_provenance, **provenance},
        "documentary_evidence": projection["documentary_evidence"],
        "testimony_evidence": projection["testimony_evidence"],
        "evidence_cards": projection["evidence_cards"],
        "evidence_ledger": projection["evidence_ledger"],
        "rejected_evidence_cards": projection["rejected_evidence_cards"],
        "source_groups": projection["source_groups"],
        "authority_evidence": projection["authority_evidence"],
        "final_claim_plan": projection["final_claim_plan"],
        "claim_validation": projection["claim_validation"],
        "cross_source_inference_provenance": projection["cross_source_inference_provenance"],
        "cross_source_inference_diagnostics": projection["cross_source_inference_diagnostics"],
        "source_analysis_results": projection["source_analysis_results"],
        "source_analysis_summary": projection["source_analysis_summary"],
        "archival_associations": projection["archival_associations"],
        "contextual_evidence": projection["contextual_evidence"],
        "inferences": projection["inferences"],
        "contradictions": projection["contradictions"],
        "missingness": projection["missingness"],
        "missingness_decision": projection["missingness_decision"],
        "source_usage": projection["source_usage"],
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
        "timings": {"query_planning_and_retrieval_ms": retrieval_ms, "source_packet_construction_ms": packet_ms, "response_projection_ms": projection_ms, **pipeline.get("timings", {}), "total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1)},
        "execution_telemetry": pipeline.get("execution_telemetry", {}),
        "diagnostic_stage_snapshot": pipeline.get("diagnostic_snapshot"),
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
        if request.selected_chunk_ids:
            retrieval = service.retrieve_selected_chunks(
                db, request.selected_chunk_ids, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION
            )
        elif request.target_document_ids:
            retrieval = service.retrieve_selected_documents(
                db, request.query, request.target_document_ids, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION
            )
        elif preset := matching_archive_question_preset(request.query):
            plan = service.planner.build_plan(db, request.query)
            contract = derive_retrieval_contract(
                request.query,
                preset_id=preset.preset_id,
                single_document_mode=preset.preset_id == "general_purpose_hospital_bedstead",
                entity_anchors=tuple(
                    str(entity["label"])
                    for entity in plan.get("resolved_entities", [])
                    if entity.get("label")
                ),
            )
            retrieval = service.retrieve_archive_scope_overview(
                db,
                request.query,
                settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
                preset.record_pid,
                max(request.top_k, 8),
                thematic_terms=preset.documentary_terms,
                preset_id=preset.preset_id,
                contract=contract,
            )
            retrieval["transparency"] = {
                **plan,
                **retrieval["transparency"],
                "archive_question_preset": preset.preset_id,
            }
        else:
            retrieval = (
                service.retrieve(
                    db, request.query, request.top_k, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
                    request.archive_record_pid,
                )
                if request.archive_record_pid
                else service.retrieve(
                    db, request.query, request.top_k, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
                )
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


@exploratory_router.get("/archive-scopes")
async def list_archive_scopes():
    """Return the controlled parent-record boundaries available for scoped interrogation."""
    db = LocalSessionLocal()
    try:
        rows = db.execute(text("""
            SELECT record_pid, MIN(COALESCE(record_title, label)) AS label, COUNT(*) AS asset_count
            FROM turin_archive_asset_snapshots
            WHERE source_snapshot_version = :snapshot_version
              AND use_for_ml = TRUE
              AND record_pid IS NOT NULL
            GROUP BY record_pid
            ORDER BY label, record_pid
        """), {"snapshot_version": "turin-archive-asset-snapshot-v1"}).mappings().all()
        return {"scopes": [
            {"record_pid": str(row["record_pid"]), "label": str(row["label"] or row["record_pid"]), "asset_count": row["asset_count"]}
            for row in rows
        ]}
    finally:
        db.close()


def _build_exploratory_packets(sources: list[dict[str, Any]], named_document: bool = False):
    db = LocalSessionLocal()
    try:
        return EvidencePacketBuilder().build(
            db,
            sources,
            max_sources=8 if named_document else 5,
            local_token_budget=700 if named_document else 1800,
        )
    finally:
        db.close()


def _build_research_answer_packets(sources: list[dict[str, Any]], question: str):
    db = LocalSessionLocal()
    try:
        packets = EvidencePacketBuilder().build(
            db, sources, max_sources=8, local_token_budget=1800, question=question,
        )
        dates = {
            f"{source['document_id']}:{source['chunk_id']}": source.get("display_date")
            for source in sources
        }
        for packet in packets:
            if dates.get(packet.source_id):
                packet.document["date"] = dates[packet.source_id]
        return packets
    finally:
        db.close()


@exploratory_router.post("/research-answer")
async def research_answer_corpus(request: ExploratoryInterrogationRequest):
    """Construct a documentary draft, retaining separate deterministic hybrid authorities."""
    if not settings.TURIN_GRANITE_DOCUMENTARY_ENABLED:
        raise HTTPException(status_code=404, detail="The documentary research-answer path is disabled.")
    if request.mode != "exploratory":
        raise HTTPException(status_code=400, detail="The documentary research-answer path accepts exploratory mode only.")
    route_decision = classify_question_route(request.query)
    if route_decision.family not in {"DOCUMENTARY", "HYBRID_AUTHORITY_DOCUMENTARY"} or _is_archive_scope_overview_request(request):
        raise HTTPException(status_code=409, detail={
            "error": "unsupported_question_class", "route_family": route_decision.family,
            "message": "Use the established authority, scoped-missingness or archive-overview route.",
        })
    started = time.perf_counter()
    hybrid = route_decision.family == "HYBRID_AUTHORITY_DOCUMENTARY"
    decomposition = decompose_hybrid_question(request.query) if hybrid else None
    authority_evidence = _catalogue_authorities(request.query, request.top_k) if hybrid else []
    authority_projection = _deterministic_authority_response(authority_evidence) if hybrid else None
    if hybrid and (
        decomposition is None or not authority_evidence
        or _authority_claim_violations(authority_projection["final_claim_plan"]["claims"], authority_evidence)
    ):
        return _synthesis_unavailable_response(
            request, {"results": [], "transparency": {}, "diagnostics": {}},
            stage="hybrid_authority_reconciliation",
            failure_code="hybrid_context_unresolved",
            failure_message="The requested authority facts or documentary clause could not be resolved.",
            authority_evidence=authority_evidence,
        )
    documentary_question = decomposition.documentary_query if decomposition else request.query
    retrieval_started = time.perf_counter()
    retrieval = _retrieve_exploratory(request)
    _hydrate_source_display_dates(retrieval["results"])
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 1)
    if not retrieval["results"]:
        return _synthesis_unavailable_response(
            request, retrieval, stage="archive_first_retrieval",
            failure_code="no_admissible_documentary_passages",
            failure_message="No documentary passages were retrieved in the configured corpus.",
            authority_evidence=authority_evidence,
        )
    packet_started = time.perf_counter()
    try:
        packets = _build_research_answer_packets(retrieval["results"], documentary_question)
        if not packets:
            return _synthesis_unavailable_response(
                request, retrieval, stage="evidence_packet_assembly",
                failure_code="no_eligible_documentary_packets",
                failure_message="Retrieved passages did not yield eligible documentary packets.",
                authority_evidence=authority_evidence,
            )
        packet_ms = round((time.perf_counter() - packet_started) * 1000, 1)
        inference_service = get_inference_service()
        result = await generate_documentary_synthesis(
            request.query, _evidence_records(packets, documentary_question), inference_service,
            authority_evidence=authority_evidence,
        )
    except (InferenceTimeoutError, RuntimeError, ValueError) as exc:
        if hybrid:
            logger.warning("Hybrid documentary construction failed: %s", exc)
            return _synthesis_unavailable_response(
                request, retrieval, stage="documentary_scholarly_construction",
                failure_code="documentary_generation_failed",
                failure_message=str(exc), authority_evidence=authority_evidence,
            )
        if isinstance(exc, InferenceTimeoutError):
            raise HTTPException(status_code=504, detail={
                "error": "inference_timeout", "stage": exc.stage, "message": str(exc),
                "answer_state": AnswerState.SYNTHESIS_UNAVAILABLE.value,
            }) from exc
        raise HTTPException(status_code=422 if isinstance(exc, ValueError) else 503, detail=str(exc)) from exc
    model_info = inference_service.get_model_info()
    if hybrid:
        result["original_draft"] = "\n\n".join(
            (authority_projection["answer"], result["original_draft"]),
        )
    result.update({
        "answer_state": "unverified_research_draft",
        "draft_label": "UNVERIFIED RESEARCH DRAFT",
        "answer_origin": "granite_hybrid_research_draft" if hybrid else "granite_documentary_research_draft",
        "verification_status": "not_performed",
        "researcher_facing": {
            "original_draft": result["original_draft"], "answer": None, "verified_answer": None,
            "draft_label": "UNVERIFIED RESEARCH DRAFT",
            "verification_status": "not_performed", "human_acceptance_status": "UNASSESSED",
        },
        "query_id": f"research-answer-{uuid.uuid4().hex[:12]}",
        "mode": "research_answer", "response_schema": "turin-research-answer-v1",
        "status": "completed",
        "model": {"name": model_info["model"], "display_name": model_info["display_name"], "runtime": model_info["runtime"]},
        "runtime": model_info, "retrieved_evidence": retrieval["results"],
        "retrieval": retrieval["transparency"], "retrieval_diagnostics": retrieval["diagnostics"],
        "corpus_version": settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION, "persisted": False,
        "source_analysis": {
            "performed": False,
            "reason": "Original documentary passages supplied to the existing two-stage construction.",
        },
        "stage_execution": {
            "classification": "UNVERIFIED HYBRID RESEARCH DRAFT" if hybrid else "UNVERIFIED DOCUMENTARY RESEARCH DRAFT",
            "stages": ["archive_first_retrieval", "evidence_packet_assembly", *[
                call["stage"] for call in result["inference_calls"]
            ]],
            "call_count": result["inference_call_count"],
            "source_ids": [str(packet.source_id) for packet in packets],
        },
        "provenance_validation": {
            "valid": False, "semantic_status": "UNASSESSED",
            "source_count": len(result["evidence_sources"]),
            "claim_count": len(result["citation_bindings"]),
            "claim_provenance": result["citation_bindings"],
        },
        "timings": {
            "query_planning_and_retrieval_ms": retrieval_ms,
            "source_packet_construction_ms": packet_ms,
            "total_backend_request_ms": round((time.perf_counter() - started) * 1000, 1),
        },
        "authority_evidence": authority_evidence, "documentary_evidence": result["evidence_sources"],
        "contextual_evidence": [], "testimony_evidence": [], "inferences": [], "missingness": [],
    })
    return result


@exploratory_router.post("/retrieve")
async def retrieve_exploratory_corpus(request: ExploratoryInterrogationRequest, v: int = Query(default=4, ge=2, le=4)):
    """Inspect exploratory retrieval planning and candidates without invoking Qwen."""
    if request.mode != "exploratory":
        raise HTTPException(status_code=400, detail="Source interrogation accepts exploratory mode only.")
    if v == 3:
        db = LocalSessionLocal()
        try:
            retrieval = TurinRetrievalV3Service().retrieve(db, request.query, request.top_k, settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
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
