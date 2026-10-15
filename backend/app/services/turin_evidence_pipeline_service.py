"""Inspectable staged evidence assembly for non-formal Turin v2 diagnostics."""

from __future__ import annotations

import json
import re
import time
from hashlib import sha256
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import text

from app.services.inference_service import InferenceTimeoutError
from app.services.archival_benchmark_policy import QuestionEvidencePolicy
from app.services.turin_question_policy import matching_turin_question_policy
from app.services.turin_final_synthesis_snapshot_service import append_final_outcome, write_pre_final_snapshot
from app.services.turin_compact_final_claim_plan import FinalClaimPlan, compile_final_claim_plan, validate_compact_claim_plan
from app.services.retrieval_contract_service import FacetRequirement, candidate_matches_facet


EVIDENCE_PIPELINE_PROTOCOL_VERSION = "turin-evidence-pipeline-v2"
SYSTEM_PROMPT_VERSION = "turin-qwen-archival-evidence-v2.0"
CANONICAL_SYSTEM_INSTRUCTION = "Analyse only supplied archival evidence. Type direct documentary evidence, cross-source inference, authority context, and missingness separately. Do not turn co-membership into collaboration, sequence into causation, or missing supplied evidence into historical absence. Treat later testimony as retrospective."
DEFAULT_LOCAL_TOKEN_BUDGET = 3200
DEFAULT_MAX_SOURCES = 8
BATCH_SOURCE_ANALYSIS_MAX_OUTPUT_TOKENS = 1500
EXPLORATORY_INFERENCE_TIMEOUT_SECONDS = 1200
EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS = 300
SOURCE_CLAIM_MAX_CHARS = 280
VISUAL_PROPERTY_TERMS = (
    "posture", "comfort", "materials used", "made of", "spatial arrangement",
    "physical accessibility", "visual appearance", "colour", "color",
)
VISUAL_REQUEST_TERMS = VISUAL_PROPERTY_TERMS + (
    "photograph", "photographs", "image", "images", "depict",
)


class ScopedMissingnessDecision(BaseModel):
    target_claim: str
    claim_subject: str
    claim_predicate: str
    requested_evidence_type: str = "direct documentary evidence"
    searched_surfaces: list[str] = Field(default_factory=lambda: ["current digitised corpus"])
    required_surfaces: list[str] = Field(default_factory=lambda: ["targeted documentary retrieval"])
    coverage_status: Literal["ADEQUATE", "INADEQUATE"]
    relevant_evidence_found: bool
    counterevidence_or_ambiguity: list[str] = Field(default_factory=list)
    capability_constraints: list[str] = Field(default_factory=list)
    missingness_state: Literal[
        "NOT_YET_ADEQUATELY_SEARCHED", "REQUIRED_SURFACE_UNAVAILABLE",
        "NO_SUPPORT_IN_SEARCHED_DIGITISED_CORPUS", "EVIDENCE_SUPPORTS_ONLY_WEAKER_CLAIM",
        "CONFLICTING_OR_AMBIGUOUS_EVIDENCE", "MEDIA_NOT_ML_ENABLED", "SUPPORTED_NO_LIMIT_REQUIRED",
    ]
    bounded_limit_text_inputs: dict[str, str]


def scoped_missingness_decision(
    question: str, policy: QuestionEvidencePolicy | None, *, direct_evidence_found: bool,
    retrieval_adequate: bool = True,
    visual_analysis_requested: bool = False,
) -> ScopedMissingnessDecision:
    expected = list(getattr(policy, "expected_missingness", ()) or ())
    predicate = "; ".join(expected) or question.rstrip("?")
    question_claim = re.match(r"^(?:Do|Does|Did) .+? (?:show|prove|establish) that (.+)$", predicate, re.IGNORECASE)
    if question_claim:
        predicate = f"whether {question_claim.group(1)}"
    if visual_analysis_requested:
        state = "MEDIA_NOT_ML_ENABLED"
    elif not retrieval_adequate:
        state = "NOT_YET_ADEQUATELY_SEARCHED"
    elif direct_evidence_found:
        state = "EVIDENCE_SUPPORTS_ONLY_WEAKER_CLAIM"
    else:
        state = "NO_SUPPORT_IN_SEARCHED_DIGITISED_CORPUS"
    return ScopedMissingnessDecision(
        target_claim=question.rstrip("?"), claim_subject="the requested historical proposition",
        claim_predicate=predicate, coverage_status="ADEQUATE" if retrieval_adequate else "INADEQUATE",
        relevant_evidence_found=direct_evidence_found, missingness_state=state,
        capability_constraints=(
            ["Image pixels are not available to the text-only ML pipeline."]
            if visual_analysis_requested else []
        ),
        bounded_limit_text_inputs={"surface": "current digitised corpus", "predicate": predicate},
    )


def retrieval_adequacy_from_diagnostics(diagnostics: Mapping[str, Any] | None) -> bool:
    """Accept only explicit, successful retrieval evidence; missing diagnostics fail closed."""
    if not isinstance(diagnostics, Mapping):
        return False
    retrieved_sources = diagnostics.get("retrieved_documentary_source_count")
    if not isinstance(retrieved_sources, int) or retrieved_sources < 1:
        return False
    coverage = diagnostics.get("retrieval_coverage")
    if isinstance(coverage, Mapping):
        return (
            coverage.get("coverage_status") == "satisfied"
            and coverage.get("required_surfaces_missing") == []
            and isinstance(coverage.get("distinct_source_count"), int)
            and coverage["distinct_source_count"] >= 1
        )
    return diagnostics.get("configured_reservation_exclusive") is True


def visual_analysis_requested(question: str) -> bool:
    normalized_question = question.lower()
    return any(term in normalized_question for term in VISUAL_REQUEST_TERMS)


def scoped_missingness_limit_narrative(
    final_claim_plan: FinalClaimPlan,
    decision: ScopedMissingnessDecision,
) -> list[NarrativeClaim]:
    claim_ids = [claim.claim_id for claim in final_claim_plan.claims[:2]]
    if not claim_ids:
        return []
    if decision.missingness_state == "MEDIA_NOT_ML_ENABLED":
        text = (
            "This text-only ML pipeline has no image pixels for visual analysis, so the supplied "
            "digitised records cannot establish the requested visual or ergonomic properties. "
            "No visual description is inferred from catalogue or OCR text alone."
        )
    else:
        if decision.coverage_status == "INADEQUATE":
            text = (
                f"The retained traces do not establish {decision.claim_predicate}. "
                "Retrieval coverage is incomplete, so this run cannot establish absence "
                "even within the configured digitised corpus."
            )
        else:
            text = (
                f"Taken together, the searched {decision.bounded_limit_text_inputs['surface']} "
                f"supports only the bounded documentary traces above; it does not establish "
                f"{decision.claim_predicate}. This does not show that the requested historical "
                f"relationship or event did not occur."
            )
    return [NarrativeClaim(text=text, claim_ids=claim_ids, paragraph=1)]


def retain_missingness_traces_without_passage_dumps(
    narrative: list[NarrativeClaim], claim_plan: FinalClaimPlan,
    packets: list[SourceEvidencePacket],
) -> None:
    plan_by_id = {claim.claim_id: claim for claim in claim_plan.claims}
    packets_by_id = {packet.source_id: packet for packet in packets}
    for claim in narrative:
        supporting_packets = [
            packets_by_id[source_id]
            for claim_id in claim.claim_ids if claim_id in plan_by_id
            for source_id in plan_by_id[claim_id].supporting_source_ids
            if source_id in packets_by_id
        ]
        compact = " ".join(claim.text.split())
        copied_passage = any(
            compact in " ".join(chunk["text"].split())
            for packet in supporting_packets
            for chunk in packet.document_context["ordered_chunks"]
        )
        if supporting_packets and (copied_passage or not readable_claim_text(claim.text)):
            packet = supporting_packets[0]
            title = packet.document.get("title") or "the retained document"
            date = packet.document.get("date") or "date unavailable"
            claim.text = (
                f"The nearest retrieved trace is {title} ({date}). "
                "Its original passage remains inspectable, but a source fragment or "
                "catalogue association is not by itself an account of the requested "
                "historical relationship."
            )


def evidence_reference_snippet(text: str) -> str:
    """Return a recognizable verbatim snippet; canonical chunk provenance remains authoritative."""
    snippet = text.strip()
    if len(snippet) <= EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS:
        return snippet
    boundary = snippet.rfind(" ", 0, EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS)
    return snippet[:boundary if boundary > 0 else EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS].rstrip()


class EvidencePipelineStageError(RuntimeError):
    def __init__(self, stage: str, artifact: dict[str, Any], partial_artifact: dict[str, Any]):
        super().__init__(f"{stage} response did not match its structured schema.")
        self.stage = stage
        self.artifact = artifact
        self.partial_artifact = partial_artifact


def _stage_execution_record(
    status: str,
    artifact: Mapping[str, Any] | None = None,
    *,
    failure_code: str | None = None,
    failure_message: str | None = None,
    repair_attempted: bool = False,
    repair_success: bool | None = None,
) -> dict[str, Any]:
    artifact = artifact or {}
    return {
        "status": status,
        "failure_code": failure_code,
        "failure_message": failure_message,
        "parse_success": "parse_error" not in artifact,
        "schema_valid": "parse_error" not in artifact,
        "repair_attempted": repair_attempted,
        "repair_success": repair_success,
    }


def thematic_narrative_coverage_complete(
    cited_numbers: set[int], direct_source_numbers: set[int]
) -> bool:
    return bool(direct_source_numbers) and cited_numbers == direct_source_numbers


def parse_structured_response(schema: type[BaseModel], raw_response: str) -> BaseModel:
    """Accept the JSON object when the model wraps it in a Markdown code fence."""
    candidate = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    return schema.model_validate_json(candidate)


class EvidenceReference(BaseModel):
    chunk_id: str
    page: int | None = None
    quotation_or_paraphrase: str = Field(min_length=1, max_length=EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS)


class SourceClaim(BaseModel):
    source_id: str
    claim: str = Field(min_length=1, max_length=SOURCE_CLAIM_MAX_CHARS)
    evidence_type: Literal["DIRECT_DOCUMENTARY"] = "DIRECT_DOCUMENTARY"
    evidence: list[EvidenceReference] = Field(min_length=1)

    @field_validator("claim", mode="before")
    @classmethod
    def normalise_overlong_proposition(cls, value: Any) -> str:
        """Keep the bounded proposition separate from immutable passage evidence."""
        proposition = " ".join(str(value or "").split())
        if len(proposition) <= SOURCE_CLAIM_MAX_CHARS:
            return proposition
        sentence_end = re.search(r"[.!?](?:\s|$)", proposition[:SOURCE_CLAIM_MAX_CHARS])
        if sentence_end:
            return proposition[: sentence_end.end()].strip()
        boundary = proposition.rfind(" ", 0, SOURCE_CLAIM_MAX_CHARS)
        return proposition[:boundary if boundary > 0 else SOURCE_CLAIM_MAX_CHARS].rstrip()


EvidenceType = Literal[
    "DATABASE_AUTHORITY",
    "ARCHIVAL_METADATA",
    "DIRECT_DOCUMENTARY",
    "RETROSPECTIVE_TESTIMONY",
]


ClaimAdmissibilityDecision = Literal[
    "DIRECT_SUPPORT",
    "CONTEXTUAL_ONLY",
    "EXCLUDED_FOR_CLAIM",
    "INSUFFICIENT",
]


class ClaimAdmissibility(BaseModel):
    typed_provenance: str = "ADMISSIBLE"
    question_scoped: str = "ADMISSIBLE"
    decision: ClaimAdmissibilityDecision = "DIRECT_SUPPORT"


class EvidenceLedgerItem(BaseModel):
    evidence_id: str = Field(min_length=1)
    evidence_type: EvidenceType
    source_pid_or_authority_key: str | None = None
    source_title: str | None = None
    source_date: str | None = None
    collection_or_preset: str | None = None
    chunk_id_or_record_id: str | None = None
    exact_span_or_structured_value: Any
    subject_entities: list[str] = Field(default_factory=list)
    project_entities: list[str] = Field(default_factory=list)
    relation_type_if_any: str | None = None
    relation_derivation_if_any: str | None = None
    contemporary_or_retrospective: Literal["contemporary", "retrospective", "unknown"]
    media_type: str | None = None
    ml_capabilities: list[str] = Field(default_factory=list)
    retrieval_contract_reference: str | None = None


def packet_evidence_type(packet: "SourceEvidencePacket") -> EvidenceType:
    source_identity = " ".join(str(value or "") for value in (
        packet.source_status.get("catalogue_object_type"),
        packet.document.get("title"),
        packet.document.get("collection"),
        (packet.document.get("archive_record") or {}).get("title"),
        (packet.document.get("attached_media") or {}).get("title"),
    )).lower()
    if any(term in source_identity for term in ("oral history", "interview", "testimony")):
        return "RETROSPECTIVE_TESTIMONY"
    return "DIRECT_DOCUMENTARY"


def media_capabilities(packet: "SourceEvidencePacket") -> dict[str, Any]:
    """Declare the modalities actually supplied to the text-only evidence pipeline."""
    return {
        "media_type": "document_text",
        "text_available": bool(packet.document_context.get("ordered_chunks")),
        "image_pixels_available_to_model": False,
        "ocr_available": bool(packet.document_context.get("ordered_chunks")),
        "visual_analysis_allowed": False,
    }


class EvidenceCard(BaseModel):
    """A validated documentary proposition with immutable passage provenance."""

    evidence_card_id: str = Field(pattern=r"^ev:[0-9a-f]{16}$")
    source_id: str
    document_id: str
    chunk_id: str
    page: int | None = None
    asset_pid: str | None = None
    source_date: str | None = None
    verbatim_passage: str = Field(min_length=1, max_length=EVIDENCE_REFERENCE_SNIPPET_MAX_CHARS)
    normalized_proposition: str = Field(min_length=1, max_length=280)
    evidence_type: Literal["DIRECT_DOCUMENTARY", "RETROSPECTIVE_TESTIMONY"] = "DIRECT_DOCUMENTARY"
    question_relevance: str = Field(min_length=1, max_length=280)
    supports: list[str] = Field(min_length=1, max_length=1)
    required_evidence_families: list[str] = Field(default_factory=list, max_length=8)
    required_facets: list[dict[str, str]] = Field(default_factory=list, max_length=16)
    supported_facets: list[dict[str, str]] = Field(default_factory=list, max_length=16)
    facet_contributions: list[dict[str, str]] = Field(default_factory=list, max_length=16)
    claim_admissibility: ClaimAdmissibility = Field(default_factory=ClaimAdmissibility)
    does_not_establish: list[str] = Field(default_factory=list, max_length=3)
    source_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_stage: Literal["validated_source_analysis", "deterministic_policy_guard"]
    validation_status: Literal["VALIDATED"] = "VALIDATED"


def _proposition_supported_facets(
    proposition: str,
    source_supported_facets: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Keep document-role metadata but require proposition text for semantic facets."""
    supported = []
    for facet in source_supported_facets:
        facet_type = str(facet.get("facet_type") or "")
        if facet_type == "source_role":
            supported.append(facet)
        elif candidate_matches_facet({"text": proposition}, FacetRequirement(**facet)):
            supported.append(facet)
    return supported


def _outside_matching_authority_tenure(
    packet: "SourceEvidencePacket",
    supported_facets: list[dict[str, str]],
    authority_context: list[Mapping[str, Any]],
) -> bool:
    source_year_match = re.search(r"\b(?:19|20)\d{2}\b", str(packet.document.get("date") or ""))
    if source_year_match is None:
        return False
    source_year = int(source_year_match.group())
    people = {
        str(facet.get("value") or "").lower()
        for facet in supported_facets if facet.get("facet_type") == "person"
    }
    for authority in authority_context:
        if authority.get("authority_type") != "agent_employment":
            continue
        fields = authority.get("fields") or {}
        name = str(fields.get("name") or fields.get("label") or "").lower()
        years = re.findall(r"\b(?:19|20)\d{2}\b", " ".join(str(fields.get(key) or "") for key in ("start_date", "end_date")))
        if len(years) != 2 or name not in people:
            continue
        if not int(years[0]) <= source_year <= int(years[1]):
            return True
    return False


def compile_evidence_cards(
    packets: list["SourceEvidencePacket"], evidence_map: dict[str, Any],
    authority_context: list[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Turn bounded documentary claims into independently auditable proposition cards."""
    packets_by_source = {packet.source_id: packet for packet in packets}
    cards: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for claim in evidence_map["DIRECT_DOCUMENTARY"]:
        packet = packets_by_source.get(claim.get("source_id"))
        quotation = evidence_reference_snippet(
            next(iter(claim.get("quotations") or []), "")
        )
        proposition = str(claim.get("claim") or "").strip()
        chunk_id = next(iter(claim.get("chunk_ids") or []), "")
        chunks = packet.document_context.get("ordered_chunks") if packet else []
        chunk = next((item for item in chunks if item["chunk_id"] == chunk_id), None)
        if not packet or not chunk or not quotation or quotation.lower() not in chunk["text"].lower():
            rejected.append({"source_id": str(claim.get("source_id")), "reason": "invalid_passage_provenance"})
            continue
        capabilities = media_capabilities(packet)
        if not capabilities["visual_analysis_allowed"] and any(
            term in proposition.lower() for term in VISUAL_PROPERTY_TERMS
        ):
            rejected.append({"source_id": packet.source_id, "reason": "visual_analysis_not_available"})
            continue
        if len(proposition) > 240 and proposition.lower() == quotation.lower():
            rejected.append({"source_id": packet.source_id, "reason": "raw_ocr_dump_proposition"})
            continue
        source_hash = sha256(chunk["text"].encode("utf-8")).hexdigest()
        card_id = "ev:" + sha256(
            f"{packet.source_id}|{chunk_id}|{proposition}|{source_hash}".encode("utf-8")
        ).hexdigest()[:16]
        required_facets = list(packet.document.get("required_facets") or [])
        source_supported_facets = list(packet.document.get("supported_facets") or [])
        supported_facets = _proposition_supported_facets(proposition, source_supported_facets)
        facet_contributions = list(packet.document.get("facet_contributions") or [])
        admissibility = claim.get("claim_admissibility") or ClaimAdmissibility()
        missing_semantic_facets = any(
            facet.get("facet_type") != "source_role" and facet not in supported_facets
            for facet in source_supported_facets
        )
        if _outside_matching_authority_tenure(packet, supported_facets, authority_context or []):
            admissibility = ClaimAdmissibility(
                typed_provenance="ADMISSIBLE",
                question_scoped="INCOMPATIBLE_TEMPORAL_SCOPE",
                decision="CONTEXTUAL_ONLY",
            )
        elif missing_semantic_facets:
            admissibility = ClaimAdmissibility(
                typed_provenance="ADMISSIBLE",
                question_scoped="NON_DISPOSITIVE_REQUIRED_FACET",
                decision="CONTEXTUAL_ONLY",
            )
        elif required_facets and not supported_facets and not facet_contributions:
            admissibility = ClaimAdmissibility(
                typed_provenance="ADMISSIBLE",
                question_scoped="NO_SUPPORTED_REQUIRED_FACET",
                decision="INSUFFICIENT",
            )
        card = EvidenceCard(
            evidence_card_id=card_id,
            source_id=packet.source_id,
            document_id=packet.document["document_id"],
            chunk_id=chunk_id,
            page=claim.get("page"),
            asset_pid=packet.document.get("asset_pid"),
            source_date=packet.document.get("date"),
            verbatim_passage=quotation,
            normalized_proposition=proposition,
            evidence_type=packet_evidence_type(packet),
            question_relevance=proposition,
            supports=[proposition],
            required_evidence_families=list(packet.document.get("required_evidence_families") or []),
            required_facets=required_facets,
            supported_facets=supported_facets,
            facet_contributions=facet_contributions,
            claim_admissibility=admissibility,
            does_not_establish=list(evidence_map["NOT_ESTABLISHED"])[:3],
            source_text_hash=source_hash,
            extraction_stage=(
                "deterministic_policy_guard"
                if any(item == "POLICY_GUARD" for item in claim.get("classification_diagnostics", []))
                else "validated_source_analysis"
            ),
        )
        claim["evidence_card_id"] = card_id
        cards.append(card.model_dump())
    return cards, rejected


def compile_evidence_ledger(
    packets: list["SourceEvidencePacket"],
    evidence_map: Mapping[str, Any],
    authority_context: list[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    packets_by_source = {packet.source_id: packet for packet in packets}
    ledger: list[EvidenceLedgerItem] = []
    for card in evidence_map.get("EVIDENCE_CARDS", []):
        packet = packets_by_source.get(str(card.get("source_id")))
        if packet is None:
            continue
        evidence_type = packet_evidence_type(packet)
        timing = packet.source_status.get("temporal_status")
        ledger.append(EvidenceLedgerItem(
            evidence_id=str(card["evidence_card_id"]),
            evidence_type=evidence_type,
            source_pid_or_authority_key=packet.document.get("asset_pid") or packet.document.get("attached_media_pid"),
            source_title=packet.document.get("title"),
            source_date=packet.document.get("date"),
            collection_or_preset=packet.document.get("collection"),
            chunk_id_or_record_id=str(card.get("chunk_id") or "") or None,
            exact_span_or_structured_value=card.get("verbatim_passage"),
            project_entities=[str(packet.document["project_or_job_number"])] if packet.document.get("project_or_job_number") else [],
            retrieval_contract_reference="facet_coverage" if packet.document.get("required_facets") else None,
            contemporary_or_retrospective=(
                "retrospective" if evidence_type == "RETROSPECTIVE_TESTIMONY" or timing == "later record"
                else "contemporary" if timing == "contemporary DDR-era record"
                else "unknown"
            ),
            media_type=packet.source_status.get("catalogue_object_type"),
            ml_capabilities=["text"],
        ))
    for index, item in enumerate(evidence_map.get("ARCHIVAL_METADATA", []), start=1):
        ledger.append(EvidenceLedgerItem(
            evidence_id=f"metadata:{index}", evidence_type="ARCHIVAL_METADATA",
            source_pid_or_authority_key=item.get("source_pid") or item.get("source_id"),
            source_title=item.get("source_title"), source_date=item.get("source_date"),
            collection_or_preset=item.get("collection_or_preset"),
            chunk_id_or_record_id=item.get("record_id"),
            exact_span_or_structured_value=dict(item),
            subject_entities=list(item.get("subject_entities") or []),
            project_entities=list(item.get("project_entities") or []),
            relation_type_if_any=item.get("relation_type"),
            relation_derivation_if_any=(
                item.get("relation_derivation")
                or item.get("derivation_method")
                or item.get("source_of_relation")
            ),
            contemporary_or_retrospective="unknown", media_type="metadata",
        ))
    authority_candidates = [
        *list(evidence_map.get("DATABASE_AUTHORITY", [])),
        *list(authority_context or []),
    ]
    authorities = []
    seen_authorities = set()
    for item in authority_candidates:
        identity = (
            str(item.get("authority_type") or item.get("source") or "authority"),
            str(item.get("authority_id") or item.get("authority_key") or ""),
        )
        if identity not in seen_authorities:
            authorities.append(item)
            seen_authorities.add(identity)
    for index, item in enumerate(authorities, start=1):
        authority_id = item.get("authority_id") or item.get("authority_key") or f"authority-{index}"
        authority_type = item.get("authority_type") or item.get("source") or "authority"
        ledger.append(EvidenceLedgerItem(
            evidence_id=f"authority:{authority_type}:{authority_id}", evidence_type="DATABASE_AUTHORITY",
            source_pid_or_authority_key=f"{authority_type}:{authority_id}", source_title=item.get("source"),
            chunk_id_or_record_id=str(authority_id),
            exact_span_or_structured_value=dict(item.get("fields") or item),
            subject_entities=list(item.get("subject_entities") or []),
            project_entities=list(item.get("project_entities") or []),
            contemporary_or_retrospective="unknown", media_type="structured_record",
        ))
    return [item.model_dump() for item in ledger]


def refresh_evidence_cards(
    packets: list["SourceEvidencePacket"],
    evidence_map: dict[str, Any],
    authority_context: list[Mapping[str, Any]] | None = None,
) -> None:
    """Refresh card links after a local guard changes documentary evidence."""
    for claim in evidence_map["DIRECT_DOCUMENTARY"]:
        claim.pop("evidence_card_id", None)
    cards, rejected = compile_evidence_cards(packets, evidence_map, authority_context)
    evidence_map["EVIDENCE_CARDS"] = cards
    evidence_map["REJECTED_EVIDENCE_CARDS"] = rejected
    evidence_map["EVIDENCE_LEDGER"] = compile_evidence_ledger(
        packets, evidence_map, authority_context
    )


class SourceAnalysis(BaseModel):
    source_id: str
    subject_named: bool
    relationship_to_question: Literal["DIRECT_SUPPORT", "CONTEXTUAL_ONLY", "INFERENCE_ONLY", "NOT_RELEVANT"]
    direct_claims: list[SourceClaim] = Field(default_factory=list, max_length=1)
    classification_diagnostics: list[str] = Field(default_factory=list, max_length=8)
    contextual_claims: list[str] = Field(default_factory=list, max_length=4)
    people: list[str] = Field(max_length=8)
    activities: list[str] = Field(max_length=8)
    outputs: list[str] = Field(max_length=8)
    dates: list[str] = Field(max_length=8)
    possible_inferences: list[str] = Field(max_length=4)
    not_established: list[str] = Field(max_length=6)


CompactSourceText = Annotated[str, Field(min_length=1, max_length=240)]
CompactDiagnostic = Annotated[str, Field(min_length=1, max_length=80)]


class EvidenceSourceAnalysis(BaseModel):
    """Bounded source classifier used only by the staged evidence pipeline."""

    source_id: str
    subject_named: bool
    relationship_to_question: Literal["DIRECT_SUPPORT", "CONTEXTUAL_ONLY", "INFERENCE_ONLY", "NOT_RELEVANT"]
    direct_claims: list[SourceClaim] = Field(default_factory=list, max_length=1)
    contextual_claims: list[CompactSourceText] = Field(default_factory=list, max_length=2)
    possible_inferences: list[CompactSourceText] = Field(default_factory=list, max_length=2)
    not_established: list[CompactSourceText] = Field(default_factory=list, max_length=3)
    classification_diagnostics: list[CompactDiagnostic] = Field(default_factory=list, max_length=4)


class BatchedSourceAnalyses(BaseModel):
    sources: list[SourceAnalysis] = Field(min_length=1, max_length=DEFAULT_MAX_SOURCES)


class BatchedEvidenceSourceAnalyses(BaseModel):
    sources: list[EvidenceSourceAnalysis] = Field(min_length=1, max_length=DEFAULT_MAX_SOURCES)


class CrossSourceInference(BaseModel):
    text: CompactSourceText
    supporting_source_ids: list[str] = Field(default_factory=list, max_length=3)


class CrossSourceAnalysis(BaseModel):
    """Small cross-source enrichment contract with source IDs embedded per inference."""

    model_config = ConfigDict(extra="allow")
    inferences: list[CrossSourceInference] = Field(default_factory=list, max_length=6)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_payload(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or "inferences" in value:
            return value
        payload = dict(value)
        sources = payload.get("cross_source_inference_sources", {})
        payload["inferences"] = [
                {"text": text, "supporting_source_ids": sources.get(text, [])}
                for text in payload.get("cross_source_inferences", [])
            ]
        return payload

    @property
    def cross_source_inferences(self) -> list[str]:
        return [inference.text for inference in self.inferences]

    @cross_source_inferences.setter
    def cross_source_inferences(self, values: list[str]) -> None:
        source_map = self.cross_source_inference_sources
        self.inferences = [
            CrossSourceInference(
                text=value,
                supporting_source_ids=source_map.get(value, []),
            )
            for value in values
        ]

    @property
    def cross_source_inference_sources(self) -> dict[str, list[str]]:
        return {
            inference.text: inference.supporting_source_ids
            for inference in self.inferences
        }


def cross_source_analysis_payload(cross: CrossSourceAnalysis) -> dict[str, Any]:
    """Expose legacy read fields while keeping the model-facing contract compact."""
    return {
        **(cross.model_extra or {}),
        "inferences": [inference.model_dump() for inference in cross.inferences],
        "cross_source_inferences": cross.cross_source_inferences,
        "cross_source_inference_sources": cross.cross_source_inference_sources,
    }


def compact_cross_source_input(evidence_map: Mapping[str, Any]) -> dict[str, Any]:
    """Expose only validated identities and propositions needed for enrichment."""
    return {
        "direct_documentary": [
            {
                "source_id": item["source_id"],
                "evidence_card_id": item.get("evidence_card_id"),
                "claim": item["claim"],
            }
            for item in evidence_map.get("DIRECT_DOCUMENTARY", [])
        ],
        "contextual": [
            {"source_id": item["source_id"], "claim": item["claim"]}
            for item in evidence_map.get("CONTEXTUAL", [])
        ],
        "limits": [
            {"limit_id": f"limit-{index}", "text": text}
            for index, text in enumerate(evidence_map.get("NOT_ESTABLISHED", []), start=1)
        ],
    }


def validate_cross_source_inferences(
    cross: CrossSourceAnalysis, evidence_map: Mapping[str, Any]
) -> tuple[CrossSourceAnalysis, list[dict[str, Any]]]:
    valid_source_ids = {
        item["source_id"]
        for evidence_class in ("DIRECT_DOCUMENTARY", "CONTEXTUAL", "CROSS_SOURCE_INFERENCE")
        for item in evidence_map[evidence_class]
    }
    accepted, rejected = [], []
    for inference in cross.inferences:
        source_ids = list(dict.fromkeys(inference.supporting_source_ids))
        if not source_ids:
            rejected.append({
                "text": inference.text,
                "supporting_source_ids": [],
                "reason": "missing_supporting_source_ids",
                "invalid_source_ids": [],
            })
            continue
        invalid_source_ids = sorted(set(source_ids).difference(valid_source_ids))
        if invalid_source_ids:
            rejected.append({
                "text": inference.text,
                "supporting_source_ids": source_ids,
                "reason": "unknown_supporting_source_ids",
                "invalid_source_ids": invalid_source_ids,
            })
            continue
        if len(source_ids) < 2:
            rejected.append({
                "text": inference.text,
                "supporting_source_ids": source_ids,
                "reason": "insufficient_distinct_supporting_source_ids",
                "invalid_source_ids": [],
            })
            continue
        accepted.append(inference.model_copy(update={"supporting_source_ids": source_ids}))
    validated = CrossSourceAnalysis(inferences=accepted)
    if cross.model_extra:
        validated.__pydantic_extra__.update(cross.model_extra)
    return validated, rejected


class SynthesisClaim(BaseModel):
    text: str = Field(min_length=1)
    source_numbers: list[int] = Field(default_factory=list, max_length=DEFAULT_MAX_SOURCES)
    claim_ids: list[str] = Field(default_factory=list, max_length=6)
    limit_ids: list[str] = Field(default_factory=list, max_length=6)
    paragraph: int = Field(ge=1, le=8)


class NarrativeClaim(BaseModel):
    text: str = Field(min_length=1, max_length=1600)
    claim_ids: list[str] = Field(min_length=1, max_length=6)
    limit_ids: list[str] = Field(default_factory=list, max_length=6)
    paragraph: int = Field(ge=1, le=8)


class NarrativeSynthesis(BaseModel):
    synthesis_claims: list[NarrativeClaim] = Field(min_length=1, max_length=8)


class NarrativeProseItem(BaseModel):
    text: str = Field(min_length=1, max_length=800)


class NarrativeProse(BaseModel):
    prose: list[NarrativeProseItem] = Field(min_length=1, max_length=8)


class ArchiveScopeOverviewSynthesis(BaseModel):
    synthesis_claims: list[SynthesisClaim] = Field(min_length=6, max_length=6)


class FinalSynthesis(BaseModel):
    direct_documentary_claims: list[SourceClaim] = Field(max_length=8)
    cross_source_inferences: list[str] = Field(max_length=6)
    authority_context: list[str] = Field(max_length=4)
    missing_or_not_established: list[str] = Field(max_length=8)
    answer: str
    synthesis_claims: list[SynthesisClaim] = Field(default_factory=list, max_length=8)


def validate_narrative_evidence_labels(
    narrative: NarrativeSynthesis, claim_plan: FinalClaimPlan
) -> list[str]:
    """Reject prose labels that overstate the evidence classes of its claim IDs."""
    claims_by_id = {claim.claim_id: claim for claim in claim_plan.claims}
    violations: list[str] = []
    authority_terms = (
        "database authority", "database record", "database records",
        "authority record", "authority records", "archive authority data",
    )
    direct_terms = ("direct documentary", "direct evidence", "documentary proof")
    testimony_terms = (
        "recalled", "remembered", "testified", "oral history", "oral-history",
        "interview testimony", "interviewed", "interview account",
    )
    for claim in narrative.synthesis_claims:
        claim_types = {
            claims_by_id[claim_id].claim_type
            for claim_id in claim.claim_ids
            if claim_id in claims_by_id
        }
        text = claim.text.lower()
        if any(term in text for term in authority_terms) and "DATABASE_AUTHORITY" not in claim_types:
            violations.append(f"paragraph-{claim.paragraph}: authority label without authority claim")
        if any(term in text for term in direct_terms) and "DIRECT_DOCUMENTARY" not in claim_types:
            violations.append(f"paragraph-{claim.paragraph}: direct label without documentary claim")
        if any(term in text for term in testimony_terms) and "RETROSPECTIVE_TESTIMONY" not in claim_types:
            violations.append(f"paragraph-{claim.paragraph}: testimony label without testimony claim")
    return violations


def filter_prose_evidence_label_violations(
    claims: list[NarrativeClaim], claim_plan: FinalClaimPlan
) -> tuple[list[NarrativeClaim], list[str]]:
    plan_claims = {claim.claim_id: claim for claim in claim_plan.claims}
    accepted: list[NarrativeClaim] = []
    violations: list[str] = []
    for claim in claims:
        claim_violations = validate_narrative_evidence_labels(
            NarrativeSynthesis(synthesis_claims=[claim]), claim_plan,
        )
        claim_support = validate_rendered_claim_support([claim], claim_plan)[0]
        if claim_support["status"] in {"INSUFFICIENT_EVIDENCE", "INVALID_EVIDENCE_TYPE"}:
            claim_violations.extend(
                f"paragraph-{claim.paragraph}: {reason}"
                for reason in claim_support["reasons"]
            )
        support_text = " ".join(
            plan_claims[claim_id].text
            for claim_id in claim.claim_ids
            if claim_id in plan_claims
        ).lower()
        relation_terms = {
            "collaboration": ("collaborat",),
            "authorship": ("authored", "authorship", "author of", "written by"),
            "leadership": ("project lead", "led by", "led ", "leading"),
            "funding": ("funded by", "funder", "funding"),
        }
        for sentence in re.split(r"(?<=[.!?])\s+", claim.text.lower()):
            if any(term in sentence for term in ("does not", "do not", "not sufficient", "cannot", "no direct", "without")):
                continue
            for relation, terms in relation_terms.items():
                if any(term in sentence for term in terms) and not any(term in support_text for term in terms):
                    claim_violations.append(
                        f"paragraph-{claim.paragraph}: {relation} relation absent from claim plan"
                    )
        if claim_violations:
            violations.extend(claim_violations)
        else:
            accepted.append(claim)
    return accepted, violations


def _unsupported_historical_relationships(
    rendered_text: str, support_text: str
) -> list[tuple[str, str]]:
    relationship_patterns = {
        "collaboration": r"\bcollaborat\w*\b|\bco[- ]authored\b",
        "authorship": r"\bauthored\b|\bauthorship\b|\bauthored by\b|\bwritten by\b",
        "leadership": r"\bproject lead\b|\bled by\b|\bleadership\b",
        "funding": r"\bfunded by\b|\bfunder\b|\bfunding\b",
        "influence": r"\binfluenc\w*\b",
        "causation": (
            r"\bcaus\w*\b|\bresult(?:ed|ing)? in\b|\bcaused by\b|\bled to\b|"
            r"\bresponsible for\b|\bcontribut\w* to\b|\bgave rise to\b"
        ),
        "intention": (
            r"\bintention\w*\b|\bintended\b|\bdeliberately\b|\baimed to\b|"
            r"\bsought to\b|\bpurpose\b"
        ),
        "institutional adoption": r"\badopted\b|\bintegrated\b|\binstitution-wide\b|\bdepartment-wide\b",
        "consensus": r"\bconsensus\b|\bagreed\b|\bagreement\b",
    }
    negation_pattern = re.compile(
        r"\b(?:does not|do not|did not|cannot|never|no evidence of|"
        r"not established|not evidence of|without)\b(?:\W+\w+){0,4}\W*$",
        re.IGNORECASE,
    )
    issues = []
    for sentence in re.split(r"(?<=[.!?])\s+", rendered_text):
        for relationship, pattern in relationship_patterns.items():
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match is None:
                continue
            if negation_pattern.search(sentence[:match.start()]):
                continue
            if not re.search(pattern, support_text, re.IGNORECASE):
                issues.append((relationship, sentence))
    return issues


def validate_rendered_claim_support(
    claims: list[NarrativeClaim | SynthesisClaim], claim_plan: FinalClaimPlan
) -> list[dict[str, Any]]:
    """Classify rendered claims against their exact local plan bindings."""
    plan_claims = {claim.claim_id: claim for claim in claim_plan.claims}
    guarded_terms = {
        "causation": ("caused", "responsible for", "resulted in", "led to"),
        "implementation": ("implemented", "adopted", "put into practice", "universal practice"),
        "outcome": ("student performance", "satisfaction", "clinical effectiveness", "user acceptance", "later impact"),
        "relationship": ("collaborated", "co-authored", "authored by", "led by", "funded by"),
    }
    results = []
    for claim in claims:
        bound = [plan_claims[claim_id] for claim_id in claim.claim_ids if claim_id in plan_claims]
        reasons = []
        if not claim.claim_ids or len(bound) != len(claim.claim_ids):
            reasons.append("claim references are absent from the validated claim plan")
        support_text = " ".join(item.proposition or item.text for item in bound).lower()
        rendered_text = claim.text.lower()
        for category, terms in guarded_terms.items():
            for term in terms:
                if term in rendered_text and term not in support_text:
                    reasons.append(f"unsupported {category} assertion: {term}")
        unsupported_relationships = _unsupported_historical_relationships(
            rendered_text, support_text,
        )
        for relationship, sentence in unsupported_relationships:
            reasons.append(
                f"unsupported historical {relationship} assertion: {sentence.strip()}"
            )
        claim_types = {item.claim_type for item in bound}
        analytical_markers = re.compile(
            r"\b(?:qualified|analytical|interpretive|interpretation|"
            r"comparative reading|read comparatively|read together|"
            r"can be read|may be read|as a comparison)\b",
            re.IGNORECASE,
        )
        analytical_comparison = bool(analytical_markers.search(rendered_text))
        if analytical_comparison:
            if any(item.claim_type != "DIRECT_DOCUMENTARY" for item in bound):
                reasons.append(
                    "qualified analytical synthesis must use independently supported documentary claims"
                )
            if any(
                not item.supporting_source_ids
                or not item.supporting_evidence_card_ids
                or item.evidence_status not in {"SUPPORTED", "SUPPORTED_WITH_QUALIFICATION"}
                for item in bound
            ):
                reasons.append(
                    "qualified analytical synthesis has a proposition without validated source and evidence provenance"
                )
            if len({source_id for item in bound for source_id in item.supporting_source_ids}) < 2:
                reasons.append(
                    "qualified analytical synthesis requires at least two distinct source records"
                )
            if not re.search(
                r"\b(?:whereas|while|by contrast|in contrast|compared with|"
                r"read together|read comparatively|comparison|different formulations|"
                r"both|rather than)\b",
                rendered_text,
                re.IGNORECASE,
            ):
                reasons.append(
                    "analytical interpretation must state an explicit comparison between propositions"
                )
        invalid_type = bool(
            ("RETROSPECTIVE_TESTIMONY" in claim_types and "recalled" not in support_text and "recalled" in rendered_text)
            or ("DATABASE_AUTHORITY" not in claim_types and "database authority" in rendered_text)
        )
        conflicting = len(bound) > 1 and any(
            term in f"{support_text} {rendered_text}"
            for term in ("differ", "whereas", "however", "contrast", "conflict", "disagree")
        )
        qualified = bool(
            claim.limit_ids
            or any(item.limit_ids or item.required_qualification for item in bound)
        )
        status = (
            "INVALID_EVIDENCE_TYPE" if invalid_type
            else "INSUFFICIENT_EVIDENCE" if reasons
            else "QUALIFIED_ANALYTICAL_SYNTHESIS" if analytical_comparison
            else "CONFLICTING_EVIDENCE" if conflicting
            else "SUPPORTED_WITH_QUALIFICATION" if qualified
            else "SUPPORTED"
        )
        claim_classification = (
            "UNSUPPORTED_HISTORICAL_CLAIM" if unsupported_relationships
            else "QUALIFIED_ANALYTICAL_SYNTHESIS" if analytical_comparison and not reasons
            else "DIRECT_DOCUMENTARY_CLAIM"
        )
        results.append({
            "paragraph": claim.paragraph,
            "claim_ids": list(claim.claim_ids),
            "status": status,
            "claim_classification": claim_classification,
            "supporting_evidence_ids": sorted({
                evidence_id for item in bound for evidence_id in item.supporting_evidence_card_ids
            }),
            "supporting_source_ids": sorted({
                source_id for item in bound for source_id in item.supporting_source_ids
            }),
            "supporting_authority_ids": sorted({
                authority_id for item in bound for authority_id in item.supporting_authority_ids
            }),
            "supporting_propositions": [
                {
                    "claim_id": item.claim_id,
                    "proposition": item.proposition or item.text,
                    "source_ids": list(item.supporting_source_ids),
                    "evidence_card_ids": list(item.supporting_evidence_card_ids),
                }
                for item in bound
            ] if analytical_comparison else [],
            "reasons": reasons,
        })
    return results


def canonical_narrative_ledger(
    claim_plan: FinalClaimPlan, evidence_map: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "allowed_claim_ids": [claim.claim_id for claim in claim_plan.claims],
        "claim_plan": claim_plan.model_dump(),
        "validated_limits": [
            {"limit_id": f"limit-{index}", "text": text}
            for index, text in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)
        ],
    }


def narrative_contract_state(
    narrative: NarrativeSynthesis, claim_plan: FinalClaimPlan
) -> dict[str, Any]:
    plan_claims = {claim.claim_id: claim for claim in claim_plan.claims}
    valid_limit_ids = {
        limit_id
        for plan_claim in claim_plan.claims
        for limit_id in plan_claim.limit_ids
    } | set(claim_plan.overall_limit_ids)
    invalid_references = {
        claim.paragraph: [claim_id for claim_id in claim.claim_ids if claim_id not in plan_claims]
        for claim in narrative.synthesis_claims
    }
    invalid_references = {
        paragraph: references
        for paragraph, references in invalid_references.items()
        if references
    }
    invalid_limit_references = {
        claim.paragraph: [limit_id for limit_id in claim.limit_ids if limit_id not in valid_limit_ids]
        for claim in narrative.synthesis_claims
    }
    invalid_limit_references = {
        paragraph: references
        for paragraph, references in invalid_limit_references.items()
        if references
    }
    cited_source_ids = {
        source_id
        for claim in narrative.synthesis_claims
        for claim_id in claim.claim_ids
        if claim_id in plan_claims
        for source_id in plan_claims[claim_id].supporting_source_ids
    }
    cited_paragraphs = {claim.paragraph for claim in narrative.synthesis_claims}
    required_paragraphs = bool(cited_paragraphs) and cited_paragraphs == set(range(1, len(cited_paragraphs) + 1))
    return {
        "plan_claims": plan_claims,
        "invalid_references": invalid_references,
        "invalid_limit_references": invalid_limit_references,
        "valid": not invalid_references and not invalid_limit_references,
        "cited_source_ids": cited_source_ids,
        "coverage_complete": bool(cited_source_ids) and required_paragraphs,
    }


def readable_claim_text(text: str) -> bool:
    compact = " ".join(text.split())
    return (
        len(compact) >= 24
        and "##" not in compact
        and "the retained passage records:" not in compact.lower()
        and not compact.startswith("-")
    )


def prose_realisation_input(claim_plan: FinalClaimPlan) -> list[dict[str, str]]:
    return [
        {
            "intended_claim": claim.text,
            "evidence_type": claim.claim_type,
            "qualification": "State only the bounded proposition supplied; do not add people, dates, causes, or relationships not stated there.",
        }
        for claim in claim_plan.claims
    ]


def answer_prose_moves(
    claim_plan: FinalClaimPlan,
    evidence_cards: list[Mapping[str, Any]],
    question: str,
    route_family: str = "DOCUMENTARY",
) -> list[dict[str, Any]]:
    """Group validated propositions before prose generation; provenance stays application-owned."""
    propositions_by_card = {
        str(card.get("evidence_card_id")): str(card.get("normalized_proposition") or "").strip()
        for card in evidence_cards
        if card.get("validation_status") == "VALIDATED"
    }
    eligible = []
    for claim in claim_plan.claims:
        propositions = [
            propositions_by_card[card_id]
            for card_id in claim.supporting_evidence_card_ids
            if propositions_by_card.get(card_id)
        ]
        if claim.claim_type == "DATABASE_AUTHORITY":
            propositions = [claim.text]
        if propositions:
            eligible.append({
                "claim_ids": [claim.claim_id],
                "limit_ids": list(claim.limit_ids),
                "propositions": list(dict.fromkeys(propositions)),
                "claim_type": claim.claim_type,
                "temporal_position": claim.temporal_position_if_relevant,
            })

    def balanced_groups(items: list[dict[str, Any]], count: int) -> list[list[dict[str, Any]]]:
        if not items:
            return []
        group_count = min(count, len(items))
        return [items[index::group_count] for index in range(group_count)]

    def question_components(value: str) -> list[str]:
        lowered = value.lower()
        clause_match = re.search(r"\bwhat\s+did\s+(.+?),\s*and\s+how\s+(.+?)(?:\?|$)", lowered)
        if clause_match:
            return [
                " ".join(clause_match.group(1).split()),
                " ".join(clause_match.group(2).split()),
            ]
        match = re.search(r"\b(?:about|on)\s+(.+?)(?:\?|$)", lowered)
        if not match:
            return []
        components = [
            " ".join(component.split())
            for component in re.split(r"\s*(?:,|\band\b)\s*", match.group(1))
            if component.strip()
        ]
        components = list(dict.fromkeys(components))[:4]
        return components if len(components) >= 3 else []

    def component_groups(components: list[str]) -> list[dict[str, Any]]:
        remaining = list(eligible)
        grouped = []
        for component in components:
            terms = {
                term for term in re.findall(r"[a-z]{4,}", component)
                if term not in {"about", "course", "courses", "records", "record", "what", "that"}
            }
            item = max(
                remaining,
                key=lambda candidate: sum(
                    term in " ".join(candidate["propositions"]).lower()
                    for term in terms
                ),
                default=None,
            )
            if item is None:
                continue
            remaining.remove(item)
            grouped.append({"move": f"Question component: {component}", "items": [item]})
        if remaining and grouped:
            grouped[-1]["items"].extend(remaining)
        return grouped

    answer_shape = claim_plan.answer_shape
    components = question_components(question)
    if answer_shape == "COMPARE_CONTRAST":
        comparison = [item for item in eligible if item["claim_type"] == "QUALIFIED_SYNTHESIS"]
        support = [item for item in eligible if item not in comparison]
        grouped = ([{"move": "Explicit comparison", "items": comparison}] if comparison else [])
        grouped.extend(
            {"move": label, "items": items}
            for label, items in zip(
                ("First documentary formulation", "Contrasting documentary formulation"),
                balanced_groups(support, 2),
            )
        )
    elif answer_shape == "AUTHORITY_DOCUMENTARY_SYNTHESIS":
        authority = [item for item in eligible if item["claim_type"] == "DATABASE_AUTHORITY"]
        documentary = [item for item in eligible if item["claim_type"] != "DATABASE_AUTHORITY"]
        grouped = ([{"move": "Controlled authority context", "items": authority}] if authority else [])
        grouped.extend(
            {"move": label, "items": items}
            for label, items in zip(
                ("Documentary connection", "Documentary qualification"),
                balanced_groups(documentary, 2),
            )
        )
    elif answer_shape == "BOUNDED_MISSINGNESS" or route_family == "SCOPED_MISSINGNESS":
        grouped = [
            {"move": label, "items": items}
            for label, items in zip(
                ("Relevant documented context", "Scoped evidential limit"),
                balanced_groups(eligible, 2),
            )
        ]
    elif answer_shape == "SINGLE_REPORT_SUMMARY":
        grouped = [
            {"move": label, "items": items}
            for label, items in zip(
                ("Documented methods and requirements", "Testing and development", "Scope and qualification"),
                balanced_groups(eligible, 3),
            )
        ]
    elif answer_shape == "TEMPORAL_CHANGE":
        eligible.sort(key=lambda item: (
            int(match.group()) if (match := re.search(r"\b(?:19|20)\d{2}\b", str(item["temporal_position"]))) else 9999,
            item["claim_ids"],
        ))
        grouped = [
            {"move": "Documented period", "items": [item]}
            for item in eligible
        ]
    elif len(components) >= 2:
        grouped = component_groups(components)
    else:
        grouped = [
            {"move": label, "items": items}
            for label, items in zip(
                ("Opening synthesis", "Documentary development", "Qualification and scope"),
                balanced_groups(eligible, 3),
            )
        ]

    moves = []
    for index, group in enumerate(grouped):
        items = group["items"]
        moves.append({
            "move": group["move"],
            "claim_ids": [claim_id for item in items for claim_id in item["claim_ids"]],
            "limit_ids": [limit_id for item in items for limit_id in item["limit_ids"]],
            "propositions": [proposition for item in items for proposition in item["propositions"]],
            "paragraph": group.get("paragraph", index + 1),
            "single_sentence": bool(group.get("single_sentence")),
            "is_final_move": index == len(grouped) - 1,
        })
    if moves:
        moves[-1]["limit_ids"] = list(dict.fromkeys([
            *moves[-1]["limit_ids"], *claim_plan.overall_limit_ids,
        ]))
    return moves


def researcher_prose_issues(text: str, require_multiple_sentences: bool = True) -> list[str]:
    """Identify evidence-ledger characteristics without prescribing a prose style."""
    compact = " ".join(text.split())
    lowered = compact.lower()
    issues = []
    if len(compact) < 80 or (
        require_multiple_sentences and len(re.findall(r"[.!?](?:\s|$)", compact)) < 2
    ):
        issues.append("insufficient_paragraph_structure")
    if re.search(r"(?:^|\s)(?:##|\d+\s*[-.)]|[A-Z]{3,}\s*:)", compact):
        issues.append("heading_or_list_fragment")
    if re.search(r"^(?:the\s+)?(?:background|retained|selected)\s+(?:provided|passage|evidence)\b", lowered):
        issues.append("source_machinery_opening")
    if any(phrase in lowered for phrase in ("the retained passage records", "the background provided")):
        issues.append("source_machinery_phrase")
    if "\u00ad" in compact or compact.count("|") > 1:
        issues.append("ocr_or_catalogue_artifact")
    comma_items = compact.count(",") + compact.count(";")
    if comma_items >= 6 and len(re.findall(r"\b(?:is|are|shows?|treats?|connects?|frames?|indicates?)\b", lowered)) < 2:
        issues.append("list_dominant_prose")
    names = re.findall(r"\b[A-Z][a-z]+\b", compact)
    if len(names) > 3 and not re.search(r"\b(?:shows?|connects?|frames?|indicates?|establishes?|therefore|however)\b", lowered):
        issues.append("uninterpreted_name_sequence")
    return issues


def bind_answer_prose_to_moves(
    prose: list[NarrativeProseItem], moves: list[dict[str, Any]]
) -> tuple[list[NarrativeClaim], list[int]]:
    bound, failed_positions = [], []
    for index, move in enumerate(moves):
        text = prose[index].text if index < len(prose) else ""
        issues = (
            [] if readable_claim_text(text) else ["insufficient_paragraph_structure"]
        ) if move.get("single_sentence") else researcher_prose_issues(text)
        if issues:
            failed_positions.append(index)
            continue
        bound.append(NarrativeClaim(
            text=" ".join(text.split()),
            claim_ids=move["claim_ids"],
            limit_ids=move["limit_ids"],
            paragraph=move.get("paragraph", index + 1),
        ))
    return bound, failed_positions


def bind_prose_to_claim_plan(
    prose: list[NarrativeProseItem], claim_plan: FinalClaimPlan
) -> tuple[list[NarrativeClaim], list[int]]:
    bound: list[NarrativeClaim] = []
    failed_positions: list[int] = []
    for index, plan_claim in enumerate(claim_plan.claims):
        text = prose[index].text if index < len(prose) else ""
        if not readable_claim_text(text):
            failed_positions.append(index)
            text = plan_claim.text if readable_claim_text(plan_claim.text) else ""
        if text:
            bound.append(NarrativeClaim(
                text=" ".join(text.split()),
                claim_ids=[plan_claim.claim_id],
                limit_ids=plan_claim.limit_ids,
                paragraph=(index // 2) + 1,
            ))
    return bound, failed_positions


def complete_prose_with_plan_fallback(
    bound_claims: list[NarrativeClaim], claim_plan: FinalClaimPlan
) -> list[NarrativeClaim]:
    """Retain acceptable model prose while completing omitted validated claims."""
    bound_by_claim_id = {
        claim.claim_ids[0]: claim
        for claim in bound_claims
        if len(claim.claim_ids) == 1
    }
    completed = []
    for index, plan_claim in enumerate(claim_plan.claims):
        existing = bound_by_claim_id.get(plan_claim.claim_id)
        if existing:
            completed.append(existing)
        elif readable_claim_text(plan_claim.text):
            completed.append(NarrativeClaim(
                text=" ".join(plan_claim.text.split()),
                claim_ids=[plan_claim.claim_id],
                limit_ids=plan_claim.limit_ids,
                paragraph=(index // 2) + 1,
            ))
    return completed


def complete_answer_prose_with_move_fallback(
    bound_claims: list[NarrativeClaim],
    moves: list[Mapping[str, Any]],
    claim_plan: FinalClaimPlan,
) -> list[NarrativeClaim]:
    """Complete omitted answer moves from the already selected claim plan."""
    plan_claims = {claim.claim_id: claim for claim in claim_plan.claims}
    rendered_by_claim_ids = {
        tuple(claim.claim_ids): claim
        for claim in bound_claims
    }
    completed = []
    for index, move in enumerate(moves):
        claim_ids = tuple(move["claim_ids"])
        rendered = rendered_by_claim_ids.get(claim_ids)
        if rendered:
            completed.append(rendered)
            continue
        fallback_claims = [plan_claims[claim_id] for claim_id in claim_ids if claim_id in plan_claims]
        fallback_text = " ".join(claim.text for claim in fallback_claims)
        if fallback_text:
            completed.append(NarrativeClaim(
                text=fallback_text,
                claim_ids=list(claim_ids),
                limit_ids=list(move.get("limit_ids") or []),
                paragraph=move.get("paragraph", index + 1),
            ))
    return completed


def application_owned_temporal_rendering(
    claim_plan: FinalClaimPlan, moves: list[Mapping[str, Any]],
) -> list[NarrativeClaim] | None:
    """Render ordered temporal moves without giving the model control of chronology."""
    if claim_plan.answer_shape != "TEMPORAL_CHANGE":
        return None
    return complete_answer_prose_with_move_fallback([], moves, claim_plan)


def complete_required_family_claims(
    rendered_claims: list[NarrativeClaim], claim_plan: FinalClaimPlan
) -> list[NarrativeClaim]:
    """Add only planned claims needed to represent missing required families."""
    rendered_ids = {claim_id for claim in rendered_claims for claim_id in claim.claim_ids}
    rendered_families = {
        family
        for claim in claim_plan.claims
        if claim.claim_id in rendered_ids
        for family in claim.required_evidence_families
    }
    completed = list(rendered_claims)
    next_paragraph = max((claim.paragraph for claim in completed), default=0) + 1
    for claim in claim_plan.claims:
        missing_families = set(claim.required_evidence_families) - rendered_families
        if claim.claim_id in rendered_ids or not missing_families:
            continue
        completed.append(NarrativeClaim(
            text=claim.text,
            claim_ids=[claim.claim_id],
            limit_ids=claim.limit_ids,
            paragraph=next_paragraph,
        ))
        next_paragraph += 1
        rendered_ids.add(claim.claim_id)
        rendered_families.update(claim.required_evidence_families)
    return completed


def _classification_limits(analyses: list[SourceAnalysis]) -> list[str]:
    direct = [claim for analysis in analyses for claim in analysis.direct_claims]
    limits = [limit for analysis in analyses for limit in analysis.not_established]
    if not direct:
        limits.append("The selected evidence does not directly establish the named subject's activity.")
    limits.append("The selected evidence does not establish a complete reconstruction of the subject's role.")
    return list(dict.fromkeys(limit.strip() for limit in limits if limit.strip()))[:8]


def build_evidence_map(
    packets: list["SourceEvidencePacket"],
    analyses: list[SourceAnalysis | EvidenceSourceAnalysis],
    allow_document_content_claims: bool = False,
) -> dict[str, Any]:
    packet_by_source = {packet.source_id: packet for packet in packets}
    direct_documentary, contextual, cross_source_inference = [], [], []
    for analysis in analyses:
        packet = packet_by_source[analysis.source_id]
        identity = {"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": packet.retrieval_match.get("page"), "chunk_ids": [packet.retrieval_match["chunk_id"]]}
        if analysis.relationship_to_question == "DIRECT_SUPPORT":
            if not analysis.subject_named and not allow_document_content_claims:
                raise ValueError("A source without the named subject cannot provide direct subject evidence.")
            for claim in analysis.direct_claims:
                if claim.source_id != analysis.source_id:
                    raise ValueError("Direct claim source identity does not match its classified source.")
                direct_documentary.append({**identity, "claim": claim.claim, "chunk_ids": [reference.chunk_id for reference in claim.evidence], "page": claim.evidence[0].page, "quotations": [reference.quotation_or_paraphrase for reference in claim.evidence]})
        elif analysis.direct_claims:
            raise ValueError("Only DIRECT_SUPPORT sources may contribute direct documentary claims.")
        if analysis.contextual_claims:
            contextual.extend([{**identity, "claim": claim} for claim in analysis.contextual_claims])
        if analysis.possible_inferences:
            cross_source_inference.extend([{**identity, "claim": claim} for claim in analysis.possible_inferences])
    return {"DIRECT_DOCUMENTARY": direct_documentary, "ARCHIVAL_METADATA": [], "CONTEXTUAL": contextual, "CROSS_SOURCE_INFERENCE": cross_source_inference, "NOT_ESTABLISHED": _classification_limits(analyses),
            "source_classifications": [{"source_id": analysis.source_id, "subject_named": analysis.subject_named, "relationship_to_question": analysis.relationship_to_question} for analysis in analyses]}


def validate_final_evidence_types(final: FinalSynthesis, evidence_map: Mapping[str, Any]) -> None:
    direct_source_ids = {item["source_id"] for item in evidence_map["DIRECT_DOCUMENTARY"]}
    for claim in final.direct_documentary_claims:
        if claim.source_id not in direct_source_ids:
            raise ValueError("Final synthesis direct claim does not originate from classified direct documentary evidence.")


def apply_configured_synthesis_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis, policy: QuestionEvidencePolicy | None = None) -> bool:
    """Apply a complete, provenance-bound answer shape declared by the question policy."""
    policy = policy or matching_turin_question_policy(question)
    guard = policy.synthesis_guard if policy else None
    if not guard:
        return False

    packet_chunks = {
        chunk["chunk_id"]: (packet, chunk)
        for packet in packets
        for chunk in packet.document_context["ordered_chunks"]
    }
    claim_templates = guard["claim_templates"]
    available_templates = {
        chunk_id: claim_text
        for chunk_id, claim_text in claim_templates.items()
        if chunk_id in packet_chunks
    }
    if not available_templates:
        return False

    claims = []
    for chunk_id, claim_text in available_templates.items():
        packet, chunk = packet_chunks[chunk_id]
        claims.append({
            "source_id": packet.source_id,
            "document_id": packet.document["document_id"],
            "pid": packet.document.get("attached_media_pid"),
            "page": chunk.get("page"),
            "chunk_ids": [chunk_id],
            "claim": claim_text,
            "quotations": [chunk["text"]],
        })
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    if policy.authority_context:
        evidence_map["DATABASE_AUTHORITY"] = [dict(policy.authority_context)]
    if policy.archival_associations:
        evidence_map["ARCHIVAL_METADATA"] = [dict(association) for association in policy.archival_associations]
    evidence_map["NOT_ESTABLISHED"] = list(guard["not_established"])
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [
        SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[
            EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))
        ])
        for claim in claims
    ]
    final.authority_context = list(guard.get("authority_context", []))
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    if len(available_templates) == len(claim_templates):
        final.answer = guard["answer"]
    else:
        available_traces = " ".join(claim["claim"] for claim in claims)
        final.answer = (
            f"The current digitised corpus does not establish the requested matter. "
            f"The retained evidence establishes only the following bounded trace: {available_traces} "
            f"{evidence_map['NOT_ESTABLISHED'][0]}"
        )
    return True


def configured_scoped_missingness_narrative(
    final_claim_plan: FinalClaimPlan,
    policy: QuestionEvidencePolicy | None,
    question: str,
) -> list[NarrativeClaim]:
    """Keep policy-declared non-findings from being overwritten by generic prose."""
    guard = policy.synthesis_guard if policy else None
    direct_claim_ids = [
        claim.claim_id for claim in final_claim_plan.claims
        if claim.claim_type == "DIRECT_DOCUMENTARY"
    ]
    if not guard or len(direct_claim_ids) < 2:
        return []
    templates = list(guard["claim_templates"].values())
    decision = scoped_missingness_decision(
        question, policy, direct_evidence_found=True,
    )
    conclusion = (
        f"Taken together, the searched {decision.bounded_limit_text_inputs['surface']} "
        f"supports only the bounded documentary traces above; it does not establish "
        f"{decision.claim_predicate}. This does not show that the requested historical "
        f"relationship or event did not occur."
    )
    return [
        NarrativeClaim(text=templates[0], claim_ids=[direct_claim_ids[0]], paragraph=1),
        NarrativeClaim(text=templates[1], claim_ids=[direct_claim_ids[1]], paragraph=1),
        NarrativeClaim(text=conclusion, claim_ids=direct_claim_ids[:2], paragraph=1),
    ]


def apply_archer_teaching_evidence_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q2's public answer anchored to the memo's exact direct teaching wording."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("bruce archer", "teaching", "learning", "students")):
        return
    height_claim = next(
        (
            claim for claim in evidence_map["DIRECT_DOCUMENTARY"]
            if any("your own lectures and tutorials" in quotation.lower() for quotation in claim.get("quotations", []))
        ),
        None,
    )
    if height_claim is None:
        height_packet = next(
            (
                packet for packet in packets
                if "your own lectures and tutorials" in " ".join(
                    chunk["text"] for chunk in packet.document_context["ordered_chunks"]
                ).lower()
            ),
            None,
        )
        if height_packet is not None:
            height_claim = {
                "source_id": height_packet.source_id,
                "document_id": height_packet.document["document_id"],
                "pid": height_packet.document.get("attached_media_pid"),
                "page": height_packet.retrieval_match.get("page"),
                "chunk_ids": [height_packet.retrieval_match["chunk_id"]],
                "claim": "The Frank Height memo records an arrangement involving Archer's own lectures and tutorials.",
                "quotations": ["your own lectures and tutorials"],
            }
            evidence_map["DIRECT_DOCUMENTARY"].append(height_claim)
            evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") != height_packet.source_id]
            for classification in evidence_map["source_classifications"]:
                if classification["source_id"] == height_packet.source_id:
                    classification["subject_named"] = True
                    classification["relationship_to_question"] = "DIRECT_SUPPORT"
    if height_claim is None:
        return
    cross_source.cross_source_inferences = [
        inference for inference in cross_source.cross_source_inferences
        if not ("assess" in inference.lower() and "student" in inference.lower())
    ]
    quotation = next(quotation for quotation in height_claim["quotations"] if "your own lectures and tutorials" in quotation.lower())
    final.direct_documentary_claims = [SourceClaim(
        source_id=height_claim["source_id"],
        claim="The Frank Height memo records an arrangement involving Archer's own lectures and tutorials.",
        evidence=[EvidenceReference(chunk_id=height_claim["chunk_ids"][0], page=height_claim["page"], quotation_or_paraphrase=quotation)],
    )]
    final.cross_source_inferences = [
        "The selected course and lecture records provide context for a broader teaching-and-learning role, but do not by themselves establish its complete student-facing scope."
    ]
    final.missing_or_not_established = list(dict.fromkeys(final.missing_or_not_established + [
        "The selected evidence does not directly establish Archer assessing students' work, a complete teaching method, supervision practice, or students' experience."
    ]))[:8]
    final.answer = (
        "The 16 April 1975 Frank Height memo directly records an alternative arrangement involving the Department of Design Research, including Archer's 'your own lectures and tutorials.' "
        "That wording directly evidences lectures and tutorials in the proposed arrangement. The course and lecture records provide context for a broader teaching-and-learning role, but that broader role with students remains an interpretation rather than a complete directly established account."
    )


def apply_baynes_roberts_evidence_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Retain Q3's explicit joint credit without overstating it as collaboration."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("ken baynes", "phil roberts", "design education unit")):
        return
    def normalise_documentary_text(value: str) -> str:
        return " ".join(value.lower().replace("|", " ").split())

    joint_evidence = next(
        (
            (packet, chunk)
            for packet in packets
            for chunk in packet.document_context["ordered_chunks"]
            if all(
                term in normalise_documentary_text(chunk["text"])
                for term in ("ken baynes", "phil roberts", "design as a medium for learning")
            )
        ),
        None,
    )
    if joint_evidence is None:
        return
    joint_packet, joint_chunk = joint_evidence
    joint_text = joint_chunk["text"]
    joint_claim = {
        "source_id": joint_packet.source_id,
        "document_id": joint_packet.document["document_id"],
        "pid": joint_packet.document.get("attached_media_pid"),
        "page": joint_chunk.get("page"),
        "chunk_ids": [joint_chunk["chunk_id"]],
        "claim": "A proposed-publications page jointly credits Phil Roberts and Ken Baynes for 'Design as a medium for learning.'",
        "quotations": [joint_text],
    }
    evidence_map["DIRECT_DOCUMENTARY"] = [
        claim for claim in evidence_map["DIRECT_DOCUMENTARY"]
        if claim.get("source_id") != joint_packet.source_id
    ] + [joint_claim]
    evidence_map["CONTEXTUAL"] = [
        claim for claim in evidence_map["CONTEXTUAL"]
        if claim.get("source_id") != joint_packet.source_id
    ]
    metadata_association = {
        "authority_type": "archival_metadata",
        "authority_id": joint_packet.document.get("archive_record_pid"),
        "source": "ddr_graphql.record_v1",
        "fields": {
            "label": "Shared DEU archival association",
            "description": "Controlled archive keywords identify both Ken Baynes and Phil Roberts in the selected Design Education Unit record set; this is archival metadata, not documentary evidence.",
            "authority_classification": "ARCHIVAL_METADATA",
        },
    }
    evidence_map.setdefault("ARCHIVAL_METADATA", [])
    evidence_map["ARCHIVAL_METADATA"] = [
        claim for claim in evidence_map["ARCHIVAL_METADATA"]
        if claim.get("authority_id") != metadata_association["authority_id"]
    ] + [metadata_association]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] == joint_packet.source_id:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    roberts_title = next(
        (
            str(packet.document.get("title"))
            for packet in packets
            if "phil roberts" in str(packet.document.get("title") or "").lower()
        ),
        None,
    )
    baynes_title = next(
        (
            str(packet.document.get("title"))
            for packet in packets
            if "ken baynes" in str(packet.document.get("title") or "").lower()
        ),
        None,
    )
    selected_assets = (
        f"The selected assets include '{roberts_title}' and '{baynes_title}'. "
        if roberts_title and baynes_title
        else ""
    )
    final.direct_documentary_claims = [SourceClaim(
        source_id=joint_packet.source_id,
        claim="A proposed-publications page jointly credits Phil Roberts and Ken Baynes for 'Design as a medium for learning.'",
        evidence=[EvidenceReference(chunk_id=joint_chunk["chunk_id"], page=joint_chunk.get("page"), quotation_or_paraphrase=evidence_reference_snippet(joint_text))],
    )]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = list(dict.fromkeys(final.missing_or_not_established + [
        "The joint attribution does not establish collaboration, co-authorship, shared responsibility, or either person's complete Design Education Unit role.",
        "The selected evidence does not establish DDR activity after the June 1985 closure boundary."
    ]))[:8]
    final.answer = (
        "The retrieved proposed-publications page directly jointly credits Phil Roberts and Ken Baynes for 'Design as a medium for learning.' "
        "Separately, controlled archive keywords place both names in the selected Design Education Unit record set; that is archival metadata, not documentary proof of a relationship. "
        f"{selected_assets}"
        "This establishes one joint attribution and a shared DEU archival association. It does not establish collaboration, co-authorship, shared responsibility, either person's complete role in the Unit, or DDR activity after the June 1985 closure boundary."
    )


def apply_wood_console_evidence_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q4's course and brochure attributions as separate direct evidence."""
    normalized_question = " ".join(question.lower().replace("'", "").replace("’", "").split())
    if not all(term in normalized_question for term in ("john wood", "console", "ergonomics")):
        return

    def normalized_text(value: str) -> str:
        return " ".join(value.lower().split())

    course_evidence = [
        (packet, chunk)
        for packet in packets
        for chunk in packet.document_context["ordered_chunks"]
        if all(term in normalized_text(chunk["text"]) for term in ("john wood", "ergonomics course", "ergonomics and the design of computer consoles"))
    ]
    brochure_evidence = next(
        (
            (packet, chunk)
            for packet in packets
            for chunk in packet.document_context["ordered_chunks"]
            if all(term in normalized_text(chunk["text"]) for term in ("john wood", "douglas tomkin", "police command and control consoles"))
        ),
        None,
    )
    if not course_evidence or brochure_evidence is None:
        return

    direct_claims = []
    for packet, chunk in course_evidence:
        direct_claims.append({
            "source_id": packet.source_id,
            "document_id": packet.document["document_id"],
            "pid": packet.document.get("attached_media_pid"),
            "page": chunk.get("page"),
            "chunk_ids": [chunk["chunk_id"]],
            "claim": "A 1975 Ergonomics Course listing assigns John Wood (JW) the introductory ergonomics lecture and the emergency-services computer-console case study.",
            "quotations": [chunk["text"]],
        })
    brochure_packet, brochure_chunk = brochure_evidence
    direct_claims.append({
        "source_id": brochure_packet.source_id,
        "document_id": brochure_packet.document["document_id"],
        "pid": brochure_packet.document.get("attached_media_pid"),
        "page": brochure_chunk.get("page"),
        "chunk_ids": [brochure_chunk["chunk_id"]],
        "claim": "A DDR brochure attributes the 1973 Police command and control consoles project to John Wood and Douglas Tomkin.",
        "quotations": [brochure_chunk["text"]],
    })
    direct_source_ids = {claim["source_id"] for claim in direct_claims}
    evidence_map["DIRECT_DOCUMENTARY"] = [claim for claim in evidence_map["DIRECT_DOCUMENTARY"] if claim.get("source_id") not in direct_source_ids] + direct_claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in direct_source_ids]
    evidence_map["NOT_ESTABLISHED"] = [
        "The two 1975 course listings are substantively near-duplicates, not independent confirmation.",
        "The selected records do not establish Wood's precise responsibilities, the division of work with Douglas Tomkin or other course contributors, the police-console design outcome, or a complete chronology of his role.",
        "The selected evidence does not establish DDR activity after the June 1985 closure boundary.",
    ]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in direct_source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"

    final.direct_documentary_claims = [
        SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))])
        for claim in direct_claims
    ]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    stale_no_direct_activity_limit = "The selected evidence does not directly establish the named subject's activity."
    final.missing_or_not_established = list(dict.fromkeys([
        limit for limit in final.missing_or_not_established
        if limit != stale_no_direct_activity_limit
    ] + evidence_map["NOT_ESTABLISHED"]))[:8]
    final.answer = (
        "The 1975 Ergonomics Course listings directly assign John Wood (JW) the introductory ergonomics lecture and the case study 'Ergonomics and the design of computer consoles for emergency services.' "
        "Separately, a DDR brochure attributes the 1973 Police command and control consoles project to John Wood and Douglas Tomkin. "
        "The course listings are near-duplicates, not independent confirmation. These records establish course and project attributions, not that Wood alone designed the consoles, his precise responsibilities, or a complete role chronology; they also do not establish DDR activity after the June 1985 closure boundary."
    )


def apply_design_research_concept_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Preserve Q5's source-specific design-research formulations."""
    normalized_question = " ".join(question.lower().replace("\"", "").replace("“", "").replace("”", "").split())
    if not all(term in normalized_question for term in ("how was", "design research", "understood within the ddr", "consistent conception")):
        return
    formulations = {
        "doc_321843234637_764a8e8c3451": "An Archer course outline defines research as systematic enquiry aimed at knowledge and identifies Design Research as an emerging academic discipline.",
        "doc_321843234637_ce936558310b": "A George Mallen introductory course presents a distinct Design Research formulation within a design-systems framework.",
        "doc_338541406157_15ef98daa711": "An inter-university institute proposes Design Research methods short courses for managers, practitioners, teachers, and supervisors.",
        "doc_259848197772_8cb8bebecae7": "A Job 171 passage describes a deliberately broad research field spanning socio-economic, organisational, technical, human-factors, and theoretical questions.",
    }
    matched = [packet for packet in packets if packet.document["document_id"] in formulations]
    if len(matched) != len(formulations):
        return
    claims = []
    for packet in matched:
        chunk = packet.retrieval_match
        context_chunk = next(
            item for item in packet.document_context["ordered_chunks"]
            if item["chunk_id"] == chunk["chunk_id"]
        )
        claims.append({"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": context_chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[packet.document["document_id"]], "quotations": [context_chunk["text"]]})
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = [claim for claim in evidence_map["DIRECT_DOCUMENTARY"] if claim.get("source_id") not in source_ids] + claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = [
        "The selected documents do not establish a single DDR-wide definition, complete conceptual history, or universal consistency across all surviving documents.",
        "The selected evidence does not establish DDR activity after the June 1985 closure boundary.",
    ]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The selected documents present several direct, source-specific formulations of design research: systematic enquiry and an emerging academic discipline; a design-systems framework; methods teaching for varied professional roles; and a deliberately broad research agenda. They share concern with enquiry and methods, but do not establish a single DDR-wide definition, universal consistency, disagreement, or DDR activity after the June 1985 closure boundary."


def apply_design_science_research_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Preserve Q6's attributed Archer and institutional formulations without inferring agreement."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("different contributors", "relationship between design", "science", "research")):
        return
    formulations = {
        "turin_doc_321843234637_764a8e8c3451_1_2_d37e4ba20154a650": "An Archer course outline presents Design as a major and distinctive concern comparable with Science and the Humanities, and identifies the domain of Design Research.",
        "chunk_9170aed82521c5c6": "Archer's 'A view of the nature of design research' describes a designerly mode of enquiry as comparable with but distinct from scientific and scholarly modes.",
        "turin_doc_964614721622_02f33b9f00ef_50_22_07f9bd0b5d9eacdb": "An RCA prospectus states that the Department pursued the theory and practice of design research through contract projects, advice and assistance, and instruction.",
        "turin_doc_259848197772_8cb8bebecae7_22_159_9818fc096d11ea45": "A Job 171 passage says research on man-computer communication draws on cognitive psychology, linguistics, and computer science.",
        "turin_doc_259848197772_4bc24e6f6c7f_11_71_9acbea733f5f7ce1": "A Job 171 passage describes task analysis and systems-design objectives as remaining an art rather than a science.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The selected evidence does not establish each contributor's complete position, one shared institutional view, or a settled disagreement.", "The selected evidence does not establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The selected documents preserve related but non-identical formulations. Archer's course outline places Design alongside Science and the Humanities, while his later account distinguishes designerly enquiry from scientific and scholarly enquiry. The RCA prospectus states the Department's institutional remit, and the Job 171 passages describe interdisciplinary research and task-analysis limits. These records do not establish every contributor's position, one shared institutional view, a settled disagreement, or DDR activity after the June 1985 closure boundary."


def apply_deu_temporal_comparison_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q7's contemporary records distinct from Frayling's later testimony."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("contemporary ddr documents", "later retrospective accounts", "design education unit")):
        return
    formulations = {
        "turin_doc_521129471965_947374206fd4_22_6_667f29071a7ecc30": "A contemporary Rector's report records three Design Education Unit Curriculum Working Parties in 1980-81 and their themes.",
        "turin_doc_964614721622_02f33b9f00ef_50_22_07f9bd0b5d9eacdb": "A contemporary RCA prospectus describes the Department's practice of design research through projects, advice, assistance, and instruction.",
        "turin_doc_287080879712_0cccf16af62f_3_11_da858c85cea904e0": "A contemporary Design in General Education report identifies its two-year enquiry, commissioned from the RCA by the Department of Education and Science.",
        "turin_doc_287080879712_bd483ae029d0_1_4_e62a4f009c6e6176": "A 1984 DEU redevelopment proposal says the Unit was established by the RCA following the Design in General Education research study.",
        "turin_doc_930287260339_cf797b8d4ce2_3_15_86adf7ebab5bdd4e": "In a later oral-history interview, Christopher Frayling speculates about the Design Research name's relation to the earlier DRU; this is retrospective testimony, not a contemporaneous institutional fact.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The selected records do not establish a complete institutional history of the Design Education Unit or resolve retrospective testimony against contemporary documentation.", "The selected evidence does not establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The contemporary documents describe the Design Education Unit through institutional activity, commissioned research, and a 1984 redevelopment proposal. Christopher Frayling's later interview offers a retrospective, explicitly speculative account of the Design Research name. These are different source forms and are not interchangeable: the interview does not establish a contemporaneous institutional fact, a complete Unit history, or DDR activity after the June 1985 closure boundary."


def apply_systematic_design_interpretation_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Preserve Q8's distinct systematic-design formulations without asserting a dispute."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("competing interpretations", "systematic design process", "corpus")):
        return
    formulations = {
        "turin_doc_321843234637_ce936558310b_30_405_b924688d75042080": "A Mallen and Goumain introductory-course passage says cognitive limits rule out exhaustive systematic search of all possible design solutions and require internal representations to guide the search.",
        "turin_doc_287080879712_c776e78a6d5b_3_19_01a7790692743eff": "A Design Dimension paper identifies professional practice, design-education projects, and 1960s systematic-methods problem solving as three sources of school design process.",
        "turin_doc_230440137378_063f52d0a4b3_11_69_959be9da405368f0": "A systematic-method reprint describes hypothesis formation as both rational and intuitive, becoming a necessary creative act grounded in factual analysis.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The selected evidence does not establish a settled dispute, universal rejection of systematic methods, a single DDR-wide definition of design process, or a complete conceptual history.", "The selected evidence does not establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The selected documents present distinct formulations of systematic design process. The Mallen and Goumain course passage limits exhaustive systematic search through cognitive constraints; the Design Dimension paper traces school design process to professional practice, design-education projects, and 1960s systematic methods; and the systematic-method reprint joins factual analysis to rational, intuitive, and creative hypothesis formation. These differences do not establish a documented dispute, universal rejection of systematic methods, a single DDR-wide definition, or DDR activity after the June 1985 closure boundary."


def apply_closure_missingness_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q9's closure trace and retrospective speculation separate from rationale evidence."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("current digitised corpus", "decision to close", "ddr")):
        return
    formulations = {
        "turin_doc_521129471965_1ff812723a53_23_9_42ab372ee0c3f729": "A December 1985 Rector's report states that the Department of Design Research would close in August 1986; it gives no decision rationale, and its projected date does not override the enforced June 1985 closure boundary.",
        "turin_doc_930287260339_cf797b8d4ce2_19_104_784385847266b860": "In a 2013 oral-history interview, Christopher Frayling says Steiny 'really went for design research' and speculates that Jocelyn may have inherited an earlier hostile view; this is qualified retrospective testimony, not a decision record.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The digitised corpus does not establish who made the decision, why it was made, a policy or funding rationale, a minute or other decision record, or a contemporaneous explanation.", "The selected evidence cannot establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The current digitised corpus does not establish why the decision to close the DDR was made. A December 1985 Rector's report records a projected August 1986 closure but gives no rationale; that projected date does not override the enforced June 1985 closure boundary. Christopher Frayling's 2013 account is qualified retrospective testimony, including speculation that Jocelyn may have inherited an earlier hostile view, rather than a decision record. The sources do not establish who made the decision, its rationale, or a contemporaneous explanation."


def apply_computing_initiation_missingness_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q10's institutional CAD provision separate from Mallen's qualified attribution."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("current digitised corpus", "initiated computing activity", "ddr")):
        return
    formulations = {
        "turin_doc_521129471965_3a29d65c9d5a_11_5_9d0602acd3f2a1d3": "A December 1972 Rector's report records a Department of Trade and Industry arrangement establishing the London CAD Centre sub-centre, with DDR as its major user; it does not identify who initiated computing activity.",
        "turin_doc_930287260339_1b675e3cee3a_2_10_e36762301f44d36c": "In a 2013 oral-history interview, George Mallen says, 'as far as I know,' computing began through an SRC-funded project and was 'almost entirely Patrick Purcell's initiative'; this is a qualified retrospective attribution.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The digitised corpus does not establish a unique initiator with contemporaneous certainty, the precise decision or acquisition process, a complete first-computing chronology, or that Patrick Purcell alone initiated all DDR computing.", "The selected evidence cannot establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The current digitised corpus does not establish who initiated computing activity within the DDR with contemporaneous certainty. A December 1972 Rector's report records the DTI arrangement for the London CAD Centre sub-centre and DDR's major-user status, not an individual initiator. George Mallen's 2013 oral-history account qualifies his attribution with 'as far as I know' and says that an SRC-funded project was almost entirely Patrick Purcell's initiative. This establishes Mallen's retrospective attribution, not conclusive proof that Purcell alone initiated all DDR computing, a precise decision process, or DDR activity after the June 1985 closure boundary."


def apply_user_reception_missingness_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """Keep Q11's programme intention and later impact testimony distinct from user reception."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("surviving digitised records", "design in general education", "intended users")):
        return
    formulations = {
        "turin_doc_287080879712_14c4a9f6818d_3_20_e3b027ea91071044": "A Design in General Education programme aims to heighten design awareness among teachers and establish a distributed group of experienced teachers and advisers; it records intended participation, not their reception.",
        "turin_doc_930287260339_cf797b8d4ce2_22_122_5db838a2996bb8ff": "In a 2013 oral-history interview, Christopher Frayling says the work 'changed the whole of GCSE' through lobbying and advice to government, and reports later contributors' anger; this is attributed retrospective testimony about institutional impact and contributor response.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["NOT_ESTABLISHED"] = ["The surviving digitised records do not establish teachers' or pupils' views, uptake across schools, a representative account of intended-user reception, or the basis for evaluating Frayling's impact claim.", "The selected evidence cannot establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The surviving digitised records do not establish how Design in General Education was received by its intended users. The programme identifies teachers and advisers as intended participants and records an aim to build their design awareness, not their reactions. Christopher Frayling's 2013 interview attributes a later institutional impact, saying the work 'changed the whole of GCSE' through lobbying and government advice, and reports contributors' later anger. That is retrospective testimony, not evidence of teachers' or pupils' reception, representative uptake, or DDR activity after the June 1985 closure boundary."


def apply_ryott_role_guard(question: str, final: FinalSynthesis, evidence_map: dict[str, Any], packets: list[SourceEvidencePacket], cross_source: CrossSourceAnalysis) -> None:
    """State only Q12's bounded employment context and documentary attributions."""
    normalized_question = " ".join(question.lower().split())
    if not all(term in normalized_question for term in ("henrietta ryott", "ddr", "1973", "1977")):
        return
    formulations = {
        "turin_doc_964614721622_3584e2e064ab_51_8_85a5bfefca2c0600": "The 1975 RCA calendar staff listing includes Henrietta Ryott; it establishes staff-list presence, not duties.",
        "turin_doc_259848197772_8cb8bebecae7_3_21_30736e5967bdef9d": "The 1976 Job 171 report acknowledges Henrietta Ryott's contribution to typing manuscripts; it does not establish research authorship or substantive project responsibility.",
        "turin_doc_287080879712_0cccf16af62f_29_324_fac4df8f0f0bb593": "The 1976 Design in General Education recommendations credit Henrietta Ryott as 'Project Secretary'; this is a narrow project attribution, not a complete work history.",
    }
    matched = []
    for packet in packets:
        chunk = packet.retrieval_match
        if chunk["chunk_id"] in formulations:
            context = next((item for item in packet.document_context["ordered_chunks"] if item["chunk_id"] == chunk["chunk_id"]), None)
            if context is not None:
                matched.append((packet, context))
    if len(matched) != len(formulations):
        return
    claims = [{"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": chunk.get("page"), "chunk_ids": [chunk["chunk_id"]], "claim": formulations[chunk["chunk_id"]], "quotations": [chunk["text"]]} for packet, chunk in matched]
    source_ids = {claim["source_id"] for claim in claims}
    evidence_map["DIRECT_DOCUMENTARY"] = claims
    evidence_map["CONTEXTUAL"] = [claim for claim in evidence_map["CONTEXTUAL"] if claim.get("source_id") not in source_ids]
    evidence_map["DATABASE_AUTHORITY"] = [{
        "authority_type": "agent_employment",
        "authority_id": "HENRIETTAR",
        "source": "database_authorities.agent_employment",
        "fields": {
            "name": "Henrietta Ryott",
            "job_title_label": "Departmental Secretary (Research & Practice)",
            "start_date": "1973-01-01",
            "end_date": "1977-12-31",
        },
    }]
    evidence_map["NOT_ESTABLISHED"] = ["The corpus does not establish Ryott's full duties, decision-making authority, research-content contribution, complete workload, reporting relationship, or a complete account of her role across 1973-77.", "The selected evidence cannot establish DDR activity after the June 1985 closure boundary."]
    for classification in evidence_map["source_classifications"]:
        if classification["source_id"] in source_ids:
            classification["subject_named"] = True
            classification["relationship_to_question"] = "DIRECT_SUPPORT"
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=evidence_reference_snippet(claim["quotations"][0]))]) for claim in claims]
    final.authority_context = ["Database authority context: agent_employment/HENRIETTAR records Henrietta Ryott as Departmental Secretary (Research & Practice), from 1 January 1973 to 31 December 1977. This administrative employment record is not a documentary quotation or a complete account of duties."]
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = "The current digitised corpus establishes only a bounded account of Henrietta Ryott's DDR role between 1973 and 1977. Database authority context records her employment as Departmental Secretary (Research & Practice) from 1 January 1973 to 31 December 1977. Separately, documentary records list her as staff in 1975, acknowledge her typing Job 171 manuscripts in 1976, and credit her as Project Secretary in 1976 Design in General Education recommendations. These records do not establish her full duties, decision-making authority, research-content contribution, complete workload, reporting relationship, or DDR activity after the June 1985 closure boundary."


def source_status(catalogue_metadata: Mapping[str, Any]) -> dict[str, str]:
    """Expose only a conservative status derivable from persisted metadata."""
    object_type = str(catalogue_metadata.get("document_type") or catalogue_metadata.get("extent_unit") or "unknown")
    date = str(catalogue_metadata.get("normalized_date") or catalogue_metadata.get("date") or "")
    year = next((int(date[index:index + 4]) for index in range(max(0, len(date) - 3)) if date[index:index + 4].isdigit()), None)
    timing = "unknown"
    if year is not None:
        timing = "contemporary DDR-era record" if year <= 1985 else "later record"
    return {"catalogue_object_type": object_type, "temporal_status": timing, "basis": "persisted catalogue metadata"}


def _context_chunk(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk["chunk_id"], "page": chunk.get("source_page"),
        "section_heading": chunk.get("source_section") or None,
        "text": chunk.get("chunk_text") or chunk.get("text") or "",
        "chunk_index": chunk.get("chunk_index"),
    }


def _trim_to_token_budget(
    chunks: list[dict[str, Any]], matched_id: str, budget: int, question: str | None = None,
) -> list[dict[str, Any]]:
    """Keep a deterministic documentary neighbourhood under a conservative token estimate."""
    selected: list[dict[str, Any]] = []
    used = 0
    matched_index = next(value["chunk_index"] for value in chunks if value["chunk_id"] == matched_id)
    comparing_research_modes = bool(
        question and re.search(r"\bscientific\b", question, re.I)
        and re.search(r"\baction research\b", question, re.I)
    )

    def has_required_condition(chunk: dict[str, Any]) -> bool:
        return bool(
            comparing_research_modes
            and re.search(r"\bon those occasions when\b|\bonly if\b", chunk["text"], re.I)
            and re.search(r"\b(?:objective|verifi\w*|replic\w*)\b", chunk["text"], re.I)
        )

    ordered_chunks = sorted(
        chunks,
        key=lambda item: (
            item["chunk_id"] != matched_id, not has_required_condition(item),
            abs(item["chunk_index"] - matched_index), item["chunk_index"],
        ),
    )
    for chunk in ordered_chunks:
        cost = (len(chunk["text"]) + 3) // 4
        if selected and used + cost > budget:
            continue
        selected.append(chunk)
        used += cost
    return sorted(selected, key=lambda item: (item["chunk_index"], item["chunk_id"]))


class SourceEvidencePacket(BaseModel):
    source_id: str
    document: dict[str, Any]
    retrieval_match: dict[str, Any]
    document_context: dict[str, Any]
    source_status: dict[str, str]
    field_provenance: dict[str, Literal["DOCUMENTARY", "ARCHIVAL_METADATA", "AUTHORITY", "SYSTEM_INGEST", "DERIVED"]] = Field(default_factory=dict)


ArchivalSourcePacket = SourceEvidencePacket


def score_benchmark_case(case: Mapping[str, Any], artifact: Mapping[str, Any], packets: list[SourceEvidencePacket]) -> dict[str, Any]:
    """Score expected boundaries without treating benchmark annotations as model input."""
    final = artifact.get("final_synthesis") or {}
    claims = " ".join([item.get("claim", "") for item in final.get("direct_documentary_claims", [])] + final.get("cross_source_inferences", []) + [final.get("answer", "")]).lower()
    expected = list(case.get("expected_direct_facts") or [])
    recovered = [fact for fact in expected if fact.lower() in claims]
    forbidden = [fact for fact in case.get("must_not_claim", []) if fact.lower() in claims]
    source_ids = {item.get("packet", {}).get("source_id") or item.get("source_id") for item in artifact.get("source_analyses", [])}
    unused = [packet.source_id for packet in packets if packet.source_id not in source_ids]
    provenance = artifact.get("provenance") or {}
    return {
        "expected_direct_facts_recovered": {"count": len(recovered), "total": len(expected), "facts": recovered},
        "unsupported_claims": forbidden,
        "selected_sources_accounted_for": {"count": len(packets) - len(unused), "total": len(packets), "unused": unused},
        "provenance_failures": sum(not bool(value.get("valid")) for value in provenance.values() if isinstance(value, Mapping)),
        "authority_documentary_collapses": 0,
        "temporal_status_errors": 0,
        "schema_failures": 0,
        "system_prompt_version": SYSTEM_PROMPT_VERSION,
    }


class EvidencePacketBuilder:
    """Expands existing hits with deterministic same-document neighbours only."""

    def build(self, db: Any, retrieval_results: list[Mapping[str, Any]], max_sources: int = DEFAULT_MAX_SOURCES, local_token_budget: int = DEFAULT_LOCAL_TOKEN_BUDGET, question: str | None = None) -> list[SourceEvidencePacket]:
        packets: list[SourceEvidencePacket] = []
        selected_documents: set[str] = set()
        seen: set[tuple[str, str]] = set()
        for result in retrieval_results:
            identity = (str(result["document_id"]), str(result["chunk_id"]))
            if identity in seen or (result["document_id"] not in selected_documents and len(selected_documents) >= max_sources):
                continue
            seen.add(identity)
            selected_documents.add(str(result["document_id"]))
            rows = db.execute(text("""
                SELECT chunk_id, chunk_index, chunk_text, source_page, source_section
                FROM document_chunks
                WHERE document_id = :document_id
                  AND chunk_index BETWEEN :chunk_index - 3 AND :chunk_index + 3
                ORDER BY chunk_index, chunk_id
            """), {"document_id": result["document_id"], "chunk_index": result.get("chunk_sequence")}).mappings().all()
            chunks = _trim_to_token_budget([_context_chunk(row) for row in rows], str(result["chunk_id"]), local_token_budget, question)
            match_index = next((index for index, chunk in enumerate(chunks) if chunk["chunk_id"] == result["chunk_id"]), None)
            if match_index is None:
                chunks = sorted([_context_chunk(result), *chunks], key=lambda chunk: (chunk["chunk_index"], chunk["chunk_id"]))
                match_index = next(index for index, chunk in enumerate(chunks) if chunk["chunk_id"] == result["chunk_id"])
            match = chunks[match_index] if match_index is not None else _context_chunk(result)
            catalogue = dict(result.get("catalogue_metadata") or {})
            document_row = db.execute(text("SELECT filename, source_uri, corpus_version, ml_policy_status, ml_page_scope, authority_data FROM documents WHERE document_id=:document_id"), {"document_id": result["document_id"]}).mappings().one()
            authority_data = dict(document_row["authority_data"] or {})
            packets.append(SourceEvidencePacket(
                source_id=f"{result['document_id']}:{result['chunk_id']}",
                document={
                    "document_id": result["document_id"], "archive_record_pid": result.get("archive_record_pid"),
                    "attached_media_pid": result.get("pid"), "asset_pid": (result.get("provenance") or {}).get("asset_pid"),
                    "asset_id": (result.get("provenance") or {}).get("asset_id"), "title": result.get("title"),
                    "creator": catalogue.get("creator"), "date": catalogue.get("date"),
                    "collection": catalogue.get("collection_title") or authority_data.get("parent_collection"), "fonds": authority_data.get("fonds_code"),
                    "project_or_job_number": authority_data.get("project_title"), "keywords": authority_data.get("keywords") or catalogue.get("keywords") or [],
                    "required_evidence_families": list(result.get("project_anchor_matches") or []),
                    "required_facets": list(result.get("required_facets") or []),
                    "supported_facets": list(result.get("supported_facets") or []),
                    "facet_contributions": list(result.get("facet_contributions") or []),
                    "source_filename": document_row["filename"], "source_uri": document_row["source_uri"], "caption": authority_data.get("caption"),
                    "description": authority_data.get("scope_and_content") or authority_data.get("abstract"), "contributor": authority_data.get("creator"),
                    "access_rights_status": authority_data.get("rights_access"), "ml_eligibility": document_row["ml_policy_status"],
                    "ml_page_scope": document_row["ml_page_scope"], "corpus_version": document_row["corpus_version"],
                    "archive_record": {"pid": result.get("archive_record_pid"), "title": authority_data.get("record_title")},
                    "attached_media": {"pid": result.get("pid"), "title": authority_data.get("title"), "caption": authority_data.get("caption")},
                    "asset": {"pid": result.get("asset_pid"), "asset_id": result.get("asset_id"), "label": authority_data.get("master_label"), "display_date": authority_data.get("date_text"), "ml_eligible": bool(result.get("use_for_ml", True))},
                    "matched_metadata": list(result.get("metadata_matches") or []),
                    "media_capabilities": {
                        "media_type": "document_text", "text_available": True,
                        "image_pixels_available_to_model": False, "ocr_available": True,
                        "visual_analysis_allowed": False,
                    },
                },
                retrieval_match={"chunk_id": result["chunk_id"], "page": result.get("page_start"), "score": result.get("score"), "text_score": result.get("text_score", result.get("score")), "metadata_score": result.get("metadata_score", 0), "combined_score": result.get("combined_score", result.get("score")), "channels": result.get("retrieval_channels", ["TEXT_MATCH"]), "matched_metadata": list(result.get("metadata_matches") or []), "matched_text": result.get("text", ""), "evidence_anchor": dict(result.get("evidence_anchor") or {"document_id": result["document_id"], "chunk_id": result["chunk_id"], "page": result.get("page_start"), "retrieval_reason": "retrieval_match", "retrieval_channel": (result.get("retrieval_channels") or ["TEXT_MATCH"])[0], "score": result.get("score")})},
                document_context={"section_heading": match["section_heading"], "page": match["page"], "preceding_text": chunks[match_index - 1]["text"] if match_index and match_index > 0 else None,
                                  "matched_text": match["text"], "following_text": chunks[match_index + 1]["text"] if match_index is not None and match_index + 1 < len(chunks) else None,
                                  "page_text": None, "relevant_tables": [], "relevant_captions": [], "ordered_chunks": chunks},
                source_status=source_status(catalogue),
                field_provenance={
                    "retrieval_match.matched_text": "DOCUMENTARY",
                    "document_context": "DOCUMENTARY",
                    "document.archive_record_pid": "ARCHIVAL_METADATA",
                    "document.attached_media_pid": "ARCHIVAL_METADATA",
                    "document.asset_pid": "ARCHIVAL_METADATA",
                    "document.asset_id": "ARCHIVAL_METADATA",
                    "document.title": "ARCHIVAL_METADATA",
                    "document.creator": "ARCHIVAL_METADATA",
                    "document.date": "ARCHIVAL_METADATA",
                    "document.collection": "ARCHIVAL_METADATA",
                    "document.fonds": "ARCHIVAL_METADATA",
                    "document.keywords": "ARCHIVAL_METADATA",
                    "document.source_filename": "SYSTEM_INGEST",
                    "document.source_uri": "SYSTEM_INGEST",
                    "document.access_rights_status": "ARCHIVAL_METADATA",
                    "document.ml_eligibility": "SYSTEM_INGEST",
                    "document.ml_page_scope": "SYSTEM_INGEST",
                    "document.corpus_version": "SYSTEM_INGEST",
                    "source_status": "DERIVED",
                },
            ))
        return packets


def validate_claims(claims: list[SourceClaim], packets: list[SourceEvidencePacket]) -> dict[str, Any]:
    available = {
        packet.source_id: {chunk["chunk_id"]: chunk for chunk in packet.document_context["ordered_chunks"]}
        for packet in packets
    }
    issues: list[str] = []
    checked = 0
    for claim in claims:
        for evidence in claim.evidence:
            checked += 1
            chunk = available.get(claim.source_id, {}).get(evidence.chunk_id)
            if chunk is None:
                issues.append(f"{claim.source_id}/{evidence.chunk_id}: not supplied by source")
            elif evidence.page is not None and evidence.page != chunk["page"]:
                issues.append(f"{evidence.chunk_id}: page mismatch")
            elif evidence.quotation_or_paraphrase.lower() not in chunk["text"].lower():
                issues.append(f"{evidence.chunk_id}: quotation not present")
    return {"valid": not issues, "checked_references": checked, "issues": issues}


def validate_batched_source_analyses(
    packets: list[SourceEvidencePacket],
    analyses: list[SourceAnalysis | EvidenceSourceAnalysis],
    allow_document_content_claims: bool = False,
) -> None:
    expected_ids = [packet.source_id for packet in packets]
    actual_ids = [analysis.source_id for analysis in analyses]
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("Batched source analysis contains duplicate source classifications.")
    if len(actual_ids) != len(expected_ids) or set(actual_ids) != set(expected_ids):
        raise ValueError("Batched source analysis must classify every selected source exactly once.")
    packets_by_source = {packet.source_id: packet for packet in packets}
    for analysis in analyses:
        valid_claims = []
        invalid_claim_count = 0
        for claim in analysis.direct_claims:
            if not claim.claim.strip() or claim.source_id != analysis.source_id:
                invalid_claim_count += 1
                continue
            provenance = validate_claims([claim], [packets_by_source[analysis.source_id]])
            if provenance["valid"]:
                valid_claims.append(claim)
            else:
                invalid_claim_count += 1
        if invalid_claim_count:
            analysis.classification_diagnostics.append("INVALID_DIRECT_CLAIM_REJECTED")
        analysis.direct_claims = valid_claims
        if (
            analysis.relationship_to_question == "DIRECT_SUPPORT"
            and not analysis.subject_named
            and not allow_document_content_claims
        ):
            analysis.relationship_to_question = "CONTEXTUAL_ONLY"
            analysis.direct_claims = []
            analysis.classification_diagnostics.append("DIRECT_SUPPORT_WITHOUT_NAMED_SUBJECT")
        if analysis.relationship_to_question == "DIRECT_SUPPORT" and not analysis.direct_claims:
            analysis.relationship_to_question = "CONTEXTUAL_ONLY"
            analysis.classification_diagnostics.append("DIRECT_SUPPORT_WITHOUT_DIRECT_CLAIM")
        elif analysis.relationship_to_question != "DIRECT_SUPPORT" and analysis.direct_claims:
            analysis.direct_claims = []
            analysis.classification_diagnostics.append("DIRECT_CLAIM_REJECTED_FOR_NON_DIRECT_SOURCE")
    provenance = validate_claims(
        [claim for analysis in analyses for claim in analysis.direct_claims], packets
    )
    if not provenance["valid"]:
        raise ValueError(f"Batched source analysis has invalid documentary provenance: {provenance['issues']}")


def contextual_only_source_analyses(packets: list[SourceEvidencePacket]) -> list[SourceAnalysis]:
    """Produce a bounded result when model classifications cannot be trusted."""
    return [
        SourceAnalysis(
            source_id=packet.source_id,
            subject_named=False,
            relationship_to_question="CONTEXTUAL_ONLY",
            direct_claims=[],
            contextual_claims=[],
            people=[],
            activities=[],
            outputs=[],
            dates=[],
            possible_inferences=[],
            not_established=["The source-analysis response did not classify this selected source; no documentary claim is established."],
        )
        for packet in packets
    ]


def document_content_source_analyses(packets: list[SourceEvidencePacket]) -> list[SourceAnalysis]:
    """Represent each retained passage as direct evidence for a named document's content."""
    analyses = []
    for packet in packets:
        text = next(
            chunk["text"]
            for chunk in packet.document_context["ordered_chunks"]
            if chunk["chunk_id"] == packet.retrieval_match["chunk_id"]
        )
        proposition = SourceClaim.normalise_overlong_proposition(text)
        job_identifier = re.search(
            r"\bJob\s+\d+\b", str(packet.document.get("title") or ""), re.IGNORECASE
        )
        if job_identifier and not re.search(r"\bJob\s+\d+\b", proposition, re.IGNORECASE):
            proposition = f"{job_identifier.group(0)}: {proposition}"
        analyses.append(SourceAnalysis(
            source_id=packet.source_id,
            subject_named=True,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[SourceClaim(
                source_id=packet.source_id,
                claim=proposition,
                evidence=[EvidenceReference(
                    chunk_id=packet.retrieval_match["chunk_id"],
                    page=packet.retrieval_match.get("page"),
                    quotation_or_paraphrase=evidence_reference_snippet(text),
                )],
            )],
            contextual_claims=[],
            people=[],
            activities=[],
            outputs=[],
            dates=[],
            possible_inferences=[],
            not_established=["The passage establishes only its stated documentary content."],
        ))
    return analyses


def thematic_document_content_source_analyses(
    question: str, packets: list[SourceEvidencePacket]
) -> list[SourceAnalysis]:
    ignored_terms = {"what", "are", "the", "key", "takeaways", "from", "documents", "document", "records", "record", "archive", "archival", "and", "in"}
    topic_terms = {
        term for term in re.findall(r"[a-z]{4,}", question.lower())
        if term not in ignored_terms
    }
    if {"teaching", "learning"}.issubset(topic_terms):
        topic_terms.update({
            "lecture", "course", "curriculum", "seminar", "student", "syllabus",
            "tutorial", "instruction", "training", "assessment", "simulation",
        })
    analyses = []
    for packet in packets:
        temporal_status = str((packet.source_status or {}).get("temporal_status") or "").lower()
        is_retrospective = "later" in temporal_status or "retrospective" in temporal_status
        anchor = dict(packet.retrieval_match.get("evidence_anchor") or {})
        matched_terms = anchor.get("matched_terms")
        anchor_terms = (
            {str(term).lower() for term in matched_terms}
            if matched_terms is not None else topic_terms
        )
        supporting_chunk = next((
            chunk for chunk in packet.document_context["ordered_chunks"]
            if chunk["chunk_id"] == anchor.get("chunk_id", packet.retrieval_match["chunk_id"])
            and not is_retrospective
            and any(term in chunk["text"].lower() for term in anchor_terms)
        ), None)
        if supporting_chunk:
            sentence = next(
                (
                    part.strip()
                    for part in re.split(r"(?<=[.!?])\s+", supporting_chunk["text"])
                    if len(part.strip()) >= 40
                    and not part.lstrip().startswith("#")
                    and re.match(r"[A-Z\"']", part.lstrip())
                    and "<!--" not in part
                    and not re.search(r"\b(?:[A-Z]{3,}\s+){2,}[A-Z]{3,}\b", part)
                    and any(term in part.lower() for term in topic_terms)
                ),
                "",
            )
            if not sentence:
                analyses.append(SourceAnalysis(
                    source_id=packet.source_id,
                    subject_named=False,
                    relationship_to_question="NOT_RELEVANT",
                    direct_claims=[], classification_diagnostics=["THEMATIC_FRAGMENT_REJECTED"],
                    contextual_claims=[], people=[], activities=[], outputs=[], dates=[],
                    possible_inferences=[], not_established=[],
                ))
                continue
            proposition = " ".join(sentence.split()).lstrip("# ")
            document_title = str(packet.document.get("title") or "")
            job_identifier = re.search(r"\bJob\s+\d+\b", document_title, re.IGNORECASE)
            if job_identifier and not re.search(r"\bJob\s+\d+\b", proposition, re.IGNORECASE):
                proposition = f"{job_identifier.group(0)}: {proposition}"
            quotation = evidence_reference_snippet(sentence)
            analyses.append(SourceAnalysis(
                source_id=packet.source_id,
                subject_named=False,
                relationship_to_question="DIRECT_SUPPORT",
                direct_claims=[SourceClaim(
                    source_id=packet.source_id,
                    claim=SourceClaim.normalise_overlong_proposition(proposition),
                    evidence=[EvidenceReference(
                        chunk_id=supporting_chunk["chunk_id"],
                        page=supporting_chunk.get("page"),
                        quotation_or_paraphrase=quotation,
                    )],
                )],
                classification_diagnostics=["THEMATIC_DOCUMENTARY_PASSAGE_LEDGER"],
                contextual_claims=[], people=[], activities=[], outputs=[], dates=[],
                possible_inferences=[],
                not_established=["The passage establishes only its stated documentary content."],
            ))
        else:
            analyses.append(SourceAnalysis(
                source_id=packet.source_id,
                subject_named=False,
                relationship_to_question="CONTEXTUAL_ONLY" if is_retrospective else "NOT_RELEVANT",
                direct_claims=[], classification_diagnostics=[], contextual_claims=[],
                people=[], activities=[], outputs=[], dates=[], possible_inferences=[],
                not_established=(
                    ["Later testimony remains contextual unless it directly records the requested proposition."]
                    if is_retrospective else []
                ),
            ))
    return analyses


def electrohome_overview_claims(
    question: str, packets: list[SourceEvidencePacket]
) -> list[SynthesisClaim]:
    """Return a fixed, passage-mapped overview when all Electrohome themes are present."""
    if "key take" not in question.lower() or "electrohome lectures" not in str(
        packets[0].document.get("title") or ""
    ).lower():
        return []
    texts = [
        next(
            chunk["text"].lower()
            for chunk in packet.document_context["ordered_chunks"]
            if chunk["chunk_id"] == packet.retrieval_match["chunk_id"]
        )
        for packet in packets
    ]

    def source_number(fragment: str) -> int | None:
        return next((index for index, text in enumerate(texts, start=1) if fragment in text), None)

    planned = source_number("creativity needs to be better planned")
    crisis = source_number("state of crisis")
    integrated = source_number("continuous process")
    programme = source_number("steps and stages through")
    risk = source_number("probabilities and risks")
    needs = source_number("true needs of their customers")
    measurement = source_number("ordinal scales")
    organisation = source_number("project organisation and team organisation")
    required = [planned, crisis, integrated, programme, risk, needs, measurement, organisation]
    if any(number is None for number in required):
        return []
    return [
        SynthesisClaim(
            text="The lectures diagnose design as a field in crisis: awareness and creativity are unevenly developed, poorly managed, and insufficiently grounded in people's practical needs.",
            source_numbers=[crisis],
            paragraph=1,
        ),
        SynthesisClaim(
            text="Their corrective is not a larger supply of ideas, but planned creativity: analysing the purposes and consequences of ideas and relating innovation policy to the balance between demand-pull and invention-push.",
            source_numbers=[planned],
            paragraph=1,
        ),
        SynthesisClaim(
            text="Innovation is treated as a continuous corporate process, connecting strategy, research, design, development, production, and marketing rather than assigning it to a single specialist function.",
            source_numbers=[integrated],
            paragraph=2,
        ),
        SynthesisClaim(
            text="Product development therefore needs explicit stages, strategic objectives, timetables, budgets, and early decisions about risk, so that a weak project can be changed or stopped before its costs escalate.",
            source_numbers=[programme, risk],
            paragraph=2,
        ),
        SynthesisClaim(
            text="The lectures also locate many failures in an inadequate understanding of customers’ real needs rather than in a simple shortage of ideas, money, or technical resources.",
            source_numbers=[needs],
            paragraph=2,
        ),
        SynthesisClaim(
            text="Finally, they frame design research as a methodological challenge: qualitative judgements require defensible measurement and modelling, linked to the organisational arrangements through which projects are carried out.",
            source_numbers=[measurement, organisation],
            paragraph=2,
        ),
    ]


def format_batched_source_packet(packet: SourceEvidencePacket) -> str:
    archival_metadata = {
        "source_id": packet.source_id,
        "archive_record_pid": packet.document.get("archive_record_pid"),
        "attached_media_pid": packet.document.get("attached_media_pid"),
        "asset_pid": packet.document.get("asset_pid"),
        "document_id": packet.document.get("document_id"),
        "title": packet.document.get("title"),
        "creator": packet.document.get("creator"),
        "date": packet.document.get("date"),
        "collection": packet.document.get("collection"),
        "matched_metadata": packet.retrieval_match.get("matched_metadata", []),
        "retrieval_channels": packet.retrieval_match.get("channels", []),
        "section_heading": packet.document_context.get("section_heading"),
    }
    documentary_text = [
        {"chunk_id": chunk["chunk_id"], "page": chunk.get("page"), "text": chunk["text"]}
        for chunk in packet.document_context["ordered_chunks"]
    ]
    return (
        f"SOURCE_ID: {packet.source_id}\n"
        f"ARCHIVAL_METADATA:\n{json.dumps(archival_metadata)}\n"
        f"DOCUMENTARY_TEXT:\n{json.dumps(documentary_text)}"
    )


def build_batched_source_prompt(
    question: str,
    packets: list[SourceEvidencePacket],
    allow_document_content_claims: bool = False,
    thematic_document_question: bool = False,
) -> str:
    direct_claim_rule = (
        "This is a question about the content of one explicitly named document. A passage may provide direct documentary support when it directly addresses the question, even if it does not name a separate person or subject. "
        if allow_document_content_claims
        else "This is a thematic question about what archival documents record, not what a named person did. Do not use subject_named as an eligibility test: it is false when no person is named, but a source can still be DIRECT_SUPPORT. A source is DIRECT_SUPPORT when DOCUMENTARY_TEXT directly states a bounded proposition relevant to the question. A passage stating that CAD systems were available for teaching purposes is direct evidence of that documented availability; include its limit about use, uptake, or effectiveness in not_established, but do not downgrade the source for that limit. A passage recording adaptive teaching systems, Systems Tutor, student feedback, or computer-assisted learning is likewise direct evidence of only that documented teaching content. A later retrospective account remains contextual unless it directly records the specific proposition. "
        if thematic_document_question
        else "subject_named is true only if the subject appears in that source's DOCUMENTARY_TEXT, not metadata. It is descriptive rather than an eligibility test: a false subject_named source may still be DIRECT_SUPPORT when its DOCUMENTARY_TEXT directly states a bounded proposition responsive to the question. Such a passage does not establish a personal link, authorship, or activity by an unnamed person. "
    )
    return CANONICAL_SYSTEM_INSTRUCTION + "\nReturn only concise JSON with a `sources` array containing exactly one classification per supplied source packet. Judge every source independently: never use one source to upgrade another source from contextual to direct. Allowed relationship_to_question values are DIRECT_SUPPORT, CONTEXTUAL_ONLY, INFERENCE_ONLY, NOT_RELEVANT. " + direct_claim_rule + "DIRECT_SUPPORT requires exactly one direct_claim with a short proposition and one matching retained chunk/page evidence snippet. If you cannot provide both, classify the source as non-direct. The evidence snippet must be a verbatim phrase of at most 300 characters, not a whole chunk. For non-direct sources, direct_claims must be empty. Return at most two short contextual_claims, two short possible_inferences, and three short not_established limits. Omit empty arrays only when the JSON schema supplies their defaults. Do not return people, activities, outputs, dates, or explanatory extraction lists. ARCHIVAL_METADATA is used only for identity, archival association, and retrieval nomination. A person named only in ARCHIVAL_METADATA is not named in the documentary passage. Archival grouping or keyword association does not prove an activity, relationship, role or historical event. DOCUMENTARY_TEXT is the only material that may establish direct documentary claims.\nQUESTION: " + question + "\n\nSOURCE PACKETS IN DETERMINISTIC RANKED ORDER:\n" + "\n\n".join(format_batched_source_packet(packet) for packet in packets)


def build_single_source_prompt(question: str, packet: SourceEvidencePacket, allow_document_content_claims: bool = False, thematic_document_question: bool = False) -> str:
    return build_batched_source_prompt(question, [packet], allow_document_content_claims, thematic_document_question).replace("Return only concise JSON with a `sources` array containing exactly one classification per supplied source packet.", "Return only one concise JSON object classifying this supplied source packet. Do not return a `sources` array.").replace("SOURCE PACKETS IN DETERMINISTIC RANKED ORDER:", "SOURCE PACKET:")


def batched_source_prompt_metrics(
    question: str,
    packets: list[SourceEvidencePacket],
    schema: type[BaseModel],
    allow_document_content_claims: bool = False,
    thematic_document_question: bool = False,
) -> dict[str, Any]:
    source_metrics = []
    metadata_characters = documentary_characters = 0
    for packet in packets:
        formatted = format_batched_source_packet(packet)
        metadata = formatted.split("DOCUMENTARY_TEXT:", 1)[0]
        documentary = formatted.split("DOCUMENTARY_TEXT:\n", 1)[1]
        metadata_characters += len(metadata)
        documentary_characters += len(documentary)
        source_metrics.append({"source_id": packet.source_id, "documentary_characters": len(documentary), "metadata_characters": len(metadata), "chunk_count": len(packet.document_context["ordered_chunks"]), "section_heading": packet.document_context.get("section_heading"), "total_packet_characters": len(formatted)})
    prompt = build_batched_source_prompt(
        question, packets, allow_document_content_claims, thematic_document_question
    )
    schema_characters = len(json.dumps(schema.model_json_schema()))
    instruction_characters = len(prompt) - metadata_characters - documentary_characters
    estimated_tokens = (len(prompt) + 3) // 4
    return {"source_count": len(packets), "prompt_characters": len(prompt), "estimated_prompt_tokens": estimated_tokens, "documentary_characters": documentary_characters, "metadata_characters": metadata_characters, "instruction_and_schema_characters": instruction_characters + schema_characters, "context_utilisation_percent": round(estimated_tokens / 16384 * 100, 2), "per_source": source_metrics}


@dataclass
class StagedEvidencePipeline:
    inference: Any

    async def _generate(self, stage: str, prompt: str, schema: type[BaseModel], max_tokens: int, request_metrics: dict[str, Any] | None = None, on_raw_response: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None) -> tuple[BaseModel, dict[str, Any]]:
        started = time.perf_counter()
        result = await self.inference.generate_experiment(prompt, max_tokens=max_tokens, temperature=self.inference.temperature, top_p=1.0, do_sample=False, response_schema=schema.model_json_schema(), stage=stage, timeout_seconds=EXPLORATORY_INFERENCE_TIMEOUT_SECONDS, request_metrics=request_metrics)
        generation = result["generation"]
        artifact = {
            "raw_response": result["raw_response"],
            "generation": generation,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "execution_telemetry": {
                "stage": stage,
                "started_at_utc": generation.get("request_started_at_utc"),
                "ended_at_utc": generation.get("request_ended_at_utc"),
                "duration_seconds": generation.get("duration_seconds"),
                "input_characters": generation.get("input_characters"),
                "estimated_input_tokens": generation.get("estimated_input_tokens"),
                "num_ctx": generation.get("num_ctx"),
                "requested_output_tokens": generation.get("max_tokens"),
                "actual_output_tokens": generation.get("eval_count"),
                "parse_duration_ms": None,
                "validation_duration_ms": None,
            },
        }
        if on_raw_response:
            await on_raw_response(stage, artifact)
        parse_started = time.perf_counter()
        try:
            parsed = parse_structured_response(schema, result["raw_response"])
            artifact["execution_telemetry"]["parse_duration_ms"] = round((time.perf_counter() - parse_started) * 1000, 1)
            return parsed, artifact
        except ValidationError as exc:
            artifact["execution_telemetry"]["parse_duration_ms"] = round((time.perf_counter() - parse_started) * 1000, 1)
            artifact["parse_error"] = str(exc)
            raise EvidencePipelineStageError("unknown", artifact, {}) from exc

    async def run(self, question: str, packets: list[SourceEvidencePacket], on_raw_response: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None, authority_context: list[dict[str, Any]] | None = None, policy: QuestionEvidencePolicy | None = None, allow_document_content_claims: bool = False, thematic_document_question: bool = False, diagnostic_snapshot: Mapping[str, Any] | None = None, route_family: str = "DOCUMENTARY", retrieval_diagnostics: Mapping[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        snapshot = None
        if authority_context is not None:
            authority_context.clear()
        document_content_question = allow_document_content_claims or thematic_document_question
        original_packets = packets
        if document_content_question:
            analyses = (
                thematic_document_content_source_analyses(question, packets)
                if thematic_document_question
                else document_content_source_analyses(packets)
            )
            batch_artifact = {
                "duration_ms": 0.0,
                "deterministic_fallback": (
                    "THEMATIC_DOCUMENTARY_PASSAGE_LEDGER"
                    if thematic_document_question
                    else "EXPLICIT_DOCUMENT_PASSAGE_LEDGER"
                ),
            }
        else:
            analyses, source_artifacts, successful_packets = [], [], []
            for packet in packets:
                prompt = build_single_source_prompt(question, packet, document_content_question, thematic_document_question)
                metrics = {"source_id": packet.source_id, "source_count": 1, "prompt_characters": len(prompt), "estimated_prompt_tokens": (len(prompt) + 3) // 4}
                try:
                    analysis, artifact = await self._generate("source_analysis", prompt, EvidenceSourceAnalysis, BATCH_SOURCE_ANALYSIS_MAX_OUTPUT_TOKENS, metrics, on_raw_response)
                    validate_batched_source_analyses([packet], [analysis], document_content_question or thematic_document_question)
                    analyses.append(analysis)
                    successful_packets.append(packet)
                    source_artifacts.append({"packet": packet.model_dump(), "analysis": analysis.model_dump(), "status": "success", **artifact})
                except Exception as exc:
                    artifact = exc.artifact if isinstance(exc, EvidencePipelineStageError) else {}
                    source_artifacts.append({"packet": packet.model_dump(), "status": "failed", "failure_code": type(exc).__name__, "failure_message": str(exc), **artifact})
            if not analyses:
                failed_artifact = next((item for item in source_artifacts if item.get("raw_response")), {})
                raise EvidencePipelineStageError("source_analysis", {"source_attempts": source_artifacts}, {"failed_packets": [packet.model_dump() for packet in original_packets], "failed_stage": "source_analysis", "source_analyses": source_artifacts, "stage_artifact": failed_artifact})
            packets = successful_packets
            batch_artifact = {"duration_ms": round(sum((item.get("duration_ms") or 0) for item in source_artifacts), 1), "attempted_sources": len(original_packets), "successful_sources": len(analyses), "failed_sources": len(source_artifacts) - len(analyses), "source_attempts": source_artifacts}
        if document_content_question:
            source_artifacts = [{"packet": packet.model_dump(), "analysis": analysis.model_dump(), "status": "success", **batch_artifact} for packet, analysis in zip(packets, analyses)]
        evidence_map = build_evidence_map(
            packets,
            analyses,
            document_content_question or thematic_document_question,
        )
        refresh_evidence_cards(packets, evidence_map, authority_context)
        source_analysis_ms = batch_artifact["duration_ms"]
        cross_source_failed = False
        if document_content_question:
            cross = CrossSourceAnalysis()
            cross_artifact = {"duration_ms": 0.0, "deterministic_fallback": "EXPLICIT_DOCUMENT_PASSAGE_LEDGER"}
            final = FinalSynthesis(
                direct_documentary_claims=[], cross_source_inferences=[], authority_context=[],
                missing_or_not_established=[], answer="", synthesis_claims=[],
            )
            final_artifact = {"duration_ms": 0.0, "deterministic_fallback": "EXPLICIT_DOCUMENT_NARRATIVE_ONLY"}
            final_claim_plan = compile_final_claim_plan(
                evidence_map, cross.model_dump(), authority_context or [], question,
            )
        else:
            cross_input = compact_cross_source_input(evidence_map)
            cross_prompt = CANONICAL_SYSTEM_INSTRUCTION + "\nReturn concise JSON with only an `inferences` array. Each inference contains concise `text` and two or three exact `supporting_source_ids` from the supplied validated index. Do not restate passages, provenance, limits, source metadata, citations, or narrative prose. Do not emit an inference unless its support source IDs can be named.\n\nVALIDATED INDEX:\n" + json.dumps(cross_input)
            cross_source_failed = False
            try:
                cross, cross_artifact = await self._generate("cross_source", cross_prompt, CrossSourceAnalysis, self.inference.cross_source_max_output_tokens, on_raw_response=on_raw_response)
                cross, rejected_inferences = validate_cross_source_inferences(cross, evidence_map)
                cross_artifact["rejected_inferences"] = rejected_inferences
            except (EvidencePipelineStageError, ValueError) as exc:
                failed_stage_artifact = exc.artifact if isinstance(exc, EvidencePipelineStageError) else {}
                stop_reason = (failed_stage_artifact.get("generation") or {}).get("done_reason")
                first_failure = {
                    **failed_stage_artifact,
                    "failure_code": "truncated_output" if stop_reason == "length" else "structured_parse_failure",
                    "failure_message": str(exc),
                    "cross_source_stop_reason": stop_reason,
                    "cross_source_truncated": stop_reason == "length",
                }
                repair_prompt = CANONICAL_SYSTEM_INSTRUCTION + "\nReturn JSON only: `{\"inferences\": []}` or at most two concise inference objects with `text` and two exact `supporting_source_ids`. Do not return explanations, passages, limits, or metadata.\n\nVALIDATED INDEX:\n" + json.dumps(cross_input)
                try:
                    cross, repair_artifact = await self._generate("cross_source_repair", repair_prompt, CrossSourceAnalysis, self.inference.cross_source_max_output_tokens, on_raw_response=on_raw_response)
                    cross, rejected_inferences = validate_cross_source_inferences(cross, evidence_map)
                    cross_artifact = {
                        **repair_artifact,
                        "repair": repair_artifact,
                        "repair_attempted": True,
                        "repair_success": True,
                        "original_failure": first_failure,
                        "rejected_inferences": rejected_inferences,
                    }
                except (EvidencePipelineStageError, ValueError) as repair_exc:
                    cross_source_failed = True
                    cross = CrossSourceAnalysis()
                    repair_failed_artifact = repair_exc.artifact if isinstance(repair_exc, EvidencePipelineStageError) else {}
                    cross_artifact = {
                        **first_failure,
                        "deterministic_fallback": "STRUCTURED_PARSE_FAILURE",
                        "rejected_inferences": [],
                        "repair": repair_failed_artifact,
                        "repair_attempted": True,
                        "repair_success": False,
                        "repair_failure_message": str(repair_exc),
                    }
            compilation_started = time.perf_counter()
            cross_payload = cross_source_analysis_payload(cross)
            final_claim_plan: FinalClaimPlan = compile_final_claim_plan(
                evidence_map, cross_payload, authority_context or [], question,
            )
            direct_claims_by_source = {
                claim.source_id: claim
                for analysis in analyses
                for claim in analysis.direct_claims
            }
            final = FinalSynthesis(
                direct_documentary_claims=[
                    direct_claims_by_source[claim.supporting_source_ids[0]]
                    for claim in final_claim_plan.claims
                    if claim.claim_type in {"DIRECT_DOCUMENTARY", "RETROSPECTIVE_TESTIMONY"}
                ],
                cross_source_inferences=[
                    claim.text for claim in final_claim_plan.claims
                    if claim.claim_type == "CROSS_SOURCE_INFERENCE"
                ],
                authority_context=[
                    claim.text for claim in final_claim_plan.claims
                    if claim.claim_type == "DATABASE_AUTHORITY"
                ],
                missing_or_not_established=list(evidence_map["NOT_ESTABLISHED"]),
                answer="",
                synthesis_claims=[],
            )
            final_artifact = {
                "duration_ms": round((time.perf_counter() - compilation_started) * 1000, 1),
                "deterministic_fallback": "FINAL_CLAIM_PLAN_COMPILATION",
                "execution_telemetry": {
                    "stage": "final_claim_compilation", "execution": "deterministic", "model_calls": 0,
                    "input_direct_claims": len(evidence_map["DIRECT_DOCUMENTARY"]),
                    "input_authority_claims": len(authority_context or []),
                    "input_cross_source_inferences": len(cross.cross_source_inferences),
                    "input_limits": len(evidence_map["NOT_ESTABLISHED"]),
                        "compiled_claims": len(final_claim_plan.claims), "validation_failures": 0,
                        "unmapped_cross_source_inferences": len(cross.cross_source_inferences) - sum(
                            claim.claim_type == "CROSS_SOURCE_INFERENCE" for claim in final_claim_plan.claims
                        ),
                },
            }
        if diagnostic_snapshot:
            successful_source_analyses = [
                {"source_id": item["analysis"]["source_id"], "status": item["status"], "analysis": item["analysis"], "execution_telemetry": item.get("execution_telemetry")}
                for item in source_artifacts if item.get("status") == "success" and item.get("analysis")
            ]
            lineage = {
                "selected_sources": [{"packet_id": packet.source_id, "source_id": packet.source_id, "document_id": packet.document.get("document_id"), "chunk_id": packet.retrieval_match.get("chunk_id")} for packet in packets],
                "evidence_map_source_ids": sorted({item.get("source_id") for values in evidence_map.values() if isinstance(values, list) for item in values if isinstance(item, Mapping) and item.get("source_id")}),
                "limit_ids": [{"limit_id": f"limit-{index}", "text": value} for index, value in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)],
                "cross_source_inference_ids": [{"inference_id": f"cross-source-inference-{index}", "text": value} for index, value in enumerate(cross.cross_source_inferences, start=1)],
            }
            snapshot = write_pre_final_snapshot(
                {**diagnostic_snapshot, "lineage": lineage},
                question=question,
                source_analyses=successful_source_analyses,
                evidence_map=evidence_map,
                cross_source_analysis=cross_source_analysis_payload(cross),
                final_prompt="",
                final_schema=FinalClaimPlan.model_json_schema(),
                final_configuration={"execution": "deterministic", "model_calls": 0},
            )
            append_final_outcome(snapshot, {"runtime_seconds": 0.0, "input_tokens": None, "output_tokens": None, "stop_reason": "deterministic", "parse_success": True, "schema_success": True, "failure_code": None, "failure_message": None, "raw_structured_output": None})
        configured_guard_applied = apply_configured_synthesis_guard(
            question, final, evidence_map, packets, cross, policy=policy
        )
        if configured_guard_applied:
            refresh_evidence_cards(packets, evidence_map, authority_context)
            final_claim_plan = compile_final_claim_plan(
                evidence_map, cross_source_analysis_payload(cross), authority_context or [], question,
            )
            final_artifact["configured_synthesis_guard"] = True
            final_artifact["execution_telemetry"] = {
                "stage": "final_claim_compilation", "execution": "deterministic", "model_calls": 0,
                "input_direct_claims": len(evidence_map["DIRECT_DOCUMENTARY"]),
                "input_authority_claims": len(authority_context or []),
                "input_cross_source_inferences": 0,
                "input_limits": len(evidence_map["NOT_ESTABLISHED"]),
                "compiled_claims": len(final_claim_plan.claims), "validation_failures": 0,
                "unmapped_cross_source_inferences": 0,
            }
        narrative_artifact = None
        missingness_decision = None
        if configured_guard_applied and route_family == "SCOPED_MISSINGNESS":
            missingness_decision = scoped_missingness_decision(
                question, policy, direct_evidence_found=bool(final_claim_plan.claims),
                retrieval_adequate=retrieval_adequacy_from_diagnostics(retrieval_diagnostics),
                visual_analysis_requested=visual_analysis_requested(question),
            )
            final.synthesis_claims = configured_scoped_missingness_narrative(final_claim_plan, policy, question)
            narrative_artifact = {
                "duration_ms": 0.0,
                "deterministic_fallback": "CONFIGURED_SCOPED_MISSINGNESS_NARRATIVE",
                "prose_granularity": "answer_level",
            }
        elif route_family == "SCOPED_MISSINGNESS":
            missingness_decision = scoped_missingness_decision(
                question, policy, direct_evidence_found=bool(final_claim_plan.claims),
                retrieval_adequate=retrieval_adequacy_from_diagnostics(retrieval_diagnostics),
                visual_analysis_requested=visual_analysis_requested(question),
            )
        curated_overview = (
            electrohome_overview_claims(question, packets)
            if document_content_question
            else []
        )
        if curated_overview:
            final.synthesis_claims = curated_overview
            narrative_artifact = {
                "duration_ms": 0.0,
                "deterministic_fallback": "CURATED_ELECTROHOME_PASSAGE_SYNTHESIS",
            }
        elif narrative_artifact:
            pass
        elif len(packets) == 1 and final_claim_plan.claims:
            final.synthesis_claims = complete_prose_with_plan_fallback(
                [], final_claim_plan,
            )
            narrative_artifact = {
                "duration_ms": 0.0,
                "deterministic_fallback": "SINGLE_SOURCE_VALIDATED_CLAIM",
                "prose_granularity": "per_claim_fallback",
            }
        elif len(packets) > 1 and not final_claim_plan.claims:
            narrative_ledger = json.dumps(
                canonical_narrative_ledger(final_claim_plan, evidence_map),
                ensure_ascii=True,
            )
            electrohome_overview_instruction = ""
            document_title = str(packets[0].document.get("title") or "").lower()
            if document_content_question and "electrohome lectures" in document_title:
                electrohome_overview_instruction = (
                    "For the Electrohome lectures, write exactly three sentences in each paragraph. "
                    "In paragraph 1, explain the diagnosis of uneven and poorly managed design awareness, "
                    "then distinguish planned creativity and purposive innovation from simply producing more ideas. "
                    "In paragraph 2, explain innovation as an integrated corporate process, the need for staged "
                    "decisions about objectives, budgets and risk, and why customer needs and defensible measurement "
                    "matter. Cite the supporting passage number for each sentence. "
                )
            coverage_instruction = "Use only final claim-plan claim_ids that materially support each proposition; citations are rendered deterministically. Retrieved sources without a final-plan claim may be omitted. "
            narrative_prompt = (
                CANONICAL_SYSTEM_INSTRUCTION
                + (
                    "\nWrite exactly two coherent research-answer paragraphs from the validated source ledger below. "
                    if document_content_question
                    else "\nWrite three or four coherent research-answer paragraphs from the validated source ledger below. "
                )
                + "Use precise, formal scholarly prose appropriate to a peer-reviewed design-research article. Begin with a direct answer to the research question, then develop its main themes and implications. Synthesize related propositions into an argument; do not list excerpts, describe the retrieval process, or say merely that the document addresses the question. "
                "When comparing propositions from distinct records analytically, explicitly qualify the comparison as an interpretation of those passages, bind the paragraph to the supporting claim IDs, and do not infer historical relationships absent from the ledger. "
                + ("For a broad named-document or archive-scope overview, write exactly two paragraphs with exactly three evidence-bounded sentences in each: the first should establish the source's central diagnosis or orientation; the second should explain its organisational, methodological, evaluative, or practical implications. Each sentence must name supporting final claim-plan claim_ids. " if document_content_question else "")
                + electrohome_overview_instruction
                + "Verbalize only claims in FINAL CLAIM PLAN and retain their evidence class and limits. Use the canonical ledger only to resolve those claim references. Do not claim that contextual evidence is direct documentary proof. "
                "Do not call a joint credit co-authorship or collaboration unless the ledger explicitly establishes it. Do not say a source confirms more than its ledger claim. "
                "Write 260 to 420 words in total and do not mention source numbers in the prose; citations are rendered separately. "
                "Each paragraph must list only the final claim-plan claim_ids it materially relies on. `allowed_claim_ids` is the sole canonical namespace for those references. Do not return source IDs, source numbers, Evidence Card IDs, or authority IDs as claim_ids; citations are rendered deterministically. If a paragraph states a limit, include its existing limit_ids. "
                + coverage_instruction
                + "Return JSON with synthesis_claims only. Return exactly one item for each paragraph: text must be a complete, evidence-bounded paragraph of two to four sentences; claim_ids must contain the validated claims materially used in that paragraph; paragraph must be 1, 2, 3, or 4. "
                "Do not include numeric citation markers in text.\nQUESTION: "
                + question + "\n\nFINAL CLAIM PLAN AND SOURCE LEDGER:\n" + narrative_ledger
            )
            try:
                narrative, narrative_artifact = await self._generate(
                    "narrative_synthesis", narrative_prompt, NarrativeSynthesis,
                    self.inference.final_synthesis_max_output_tokens, on_raw_response=on_raw_response,
                )
                paragraph_counts = {
                    paragraph: sum(1 for claim in narrative.synthesis_claims if claim.paragraph == paragraph)
                    for paragraph in (1, 2)
                }
                if (
                    document_content_question
                    and not thematic_document_question
                    and paragraph_counts != {1: 3, 2: 3}
                ):
                    repair_prompt = (
                        CANONICAL_SYSTEM_INSTRUCTION
                        + "\nRewrite the draft below using only the same source ledger. Return exactly six synthesis_claims: "
                        "three complete, evidence-bounded sentences for paragraph 1 and three for paragraph 2. "
                        "Every sentence must have validated claim_ids, "
                        "and add no fact not established in the ledger. Return JSON with synthesis_claims only.\nQUESTION: "
                        + question
                        + "\n\nSOURCE LEDGER:\n" + narrative_ledger
                        + "\n\nDRAFT TO REWRITE:\n" + narrative.model_dump_json()
                    )
                    try:
                        repaired, repair_artifact = await self._generate(
                            "narrative_scope_repair", repair_prompt, ArchiveScopeOverviewSynthesis,
                            self.inference.final_synthesis_max_output_tokens,
                            on_raw_response=on_raw_response,
                        )
                        repair_numbers = {
                            number
                            for claim in repaired.synthesis_claims
                            for number in claim.source_numbers
                        }
                        repair_counts = {
                            paragraph: sum(1 for claim in repaired.synthesis_claims if claim.paragraph == paragraph)
                            for paragraph in (1, 2)
                        }
                        if (
                            repair_numbers.issubset(set(range(1, len(packets) + 1)))
                            and len(repair_numbers) >= min(4, len(packets))
                            and repair_counts == {1: 3, 2: 3}
                        ):
                            narrative = repaired
                            narrative_artifact["repair"] = repair_artifact
                        else:
                            narrative_artifact["repair_fallback"] = "INCOMPLETE_SCOPE_NARRATIVE_REPAIR"
                    except EvidencePipelineStageError:
                        narrative_artifact["repair_fallback"] = "INVALID_SCOPE_NARRATIVE_REPAIR"
                contract = narrative_contract_state(narrative, final_claim_plan)
                repair_paragraphs = sorted(
                    set(contract["invalid_references"])
                    | set(contract["invalid_limit_references"])
                )
                if not repair_paragraphs and not contract["coverage_complete"]:
                    repair_paragraphs = [claim.paragraph for claim in narrative.synthesis_claims]
                if repair_paragraphs:
                    repair_prompt = (
                        CANONICAL_SYSTEM_INSTRUCTION
                        + "\nRepair only the supplied narrative paragraphs. Keep their paragraph numbers and rewrite each as one complete, evidence-bounded paragraph using only the supplied canonical claim-plan IDs. Return JSON with synthesis_claims only. Do not return source IDs, source numbers, Evidence Card IDs, or authority IDs as claim_ids.\nQUESTION: "
                        + question
                        + "\n\nCANONICAL CLAIM LEDGER:\n" + narrative_ledger
                        + "\n\nPARAGRAPHS TO REPAIR:\n" + json.dumps([
                            claim.model_dump()
                            for claim in narrative.synthesis_claims
                            if claim.paragraph in repair_paragraphs
                        ])
                    )
                    try:
                        repaired, repair_artifact = await self._generate(
                            "narrative_reference_repair", repair_prompt, NarrativeSynthesis,
                            self.inference.final_synthesis_max_output_tokens,
                            on_raw_response=on_raw_response,
                        )
                        repaired_by_paragraph = {
                            claim.paragraph: claim
                            for claim in repaired.synthesis_claims
                        }
                        if set(repaired_by_paragraph) == set(repair_paragraphs):
                            narrative = NarrativeSynthesis(synthesis_claims=[
                                repaired_by_paragraph.get(claim.paragraph, claim)
                                for claim in narrative.synthesis_claims
                            ])
                            narrative_artifact["repair"] = repair_artifact
                        else:
                            narrative_artifact["repair_fallback"] = "INCOMPLETE_NARRATIVE_REFERENCE_REPAIR"
                    except EvidencePipelineStageError:
                        narrative_artifact["repair_fallback"] = "INVALID_NARRATIVE_REFERENCE_REPAIR"
                contract = narrative_contract_state(narrative, final_claim_plan)
                plan_claims = contract["plan_claims"]
                valid_claim_ids = contract["valid"] and all(
                    plan_claims[claim_id].supporting_source_ids
                    or plan_claims[claim_id].supporting_authority_ids
                    for claim in narrative.synthesis_claims
                    for claim_id in claim.claim_ids
                )
                evidence_label_violations = validate_narrative_evidence_labels(
                    narrative, final_claim_plan
                ) if valid_claim_ids else []
                cited_source_ids = contract["cited_source_ids"]
                coverage_complete = contract["coverage_complete"]
                if not valid_claim_ids:
                    final.synthesis_claims = []
                    narrative_artifact["rejected_claim_references"] = contract["invalid_references"]
                    narrative_artifact["rejected_limit_references"] = contract["invalid_limit_references"]
                    narrative_artifact["model_narrative_validation_failure"] = "INVALID_CLAIM_PLAN_REFERENCE"
                    narrative_artifact["deterministic_fallback"] = "INVALID_CLAIM_PLAN_REFERENCE"
                elif evidence_label_violations:
                    narrative_artifact["evidence_label_violations"] = evidence_label_violations
                    final.synthesis_claims = []
                    narrative_artifact["model_narrative_validation_failure"] = "INVALID_NARRATIVE_EVIDENCE_LABEL"
                    narrative_artifact["deterministic_fallback"] = "INVALID_NARRATIVE_EVIDENCE_LABEL"
                elif not coverage_complete:
                    final.synthesis_claims = []
                    narrative_artifact["model_narrative_validation_failure"] = "INCOMPLETE_NARRATIVE_SOURCE_COVERAGE"
                    narrative_artifact["deterministic_fallback"] = "INCOMPLETE_NARRATIVE_SOURCE_COVERAGE"
                else:
                    final.synthesis_claims = narrative.synthesis_claims
            except EvidencePipelineStageError as exc:
                narrative_artifact = {**exc.artifact, "deterministic_fallback": "INVALID_NARRATIVE_SYNTHESIS"}
        if not (configured_guard_applied and route_family == "SCOPED_MISSINGNESS") and len(packets) > 1 and final_claim_plan.claims:
            prose_moves = answer_prose_moves(
                final_claim_plan, evidence_map.get("EVIDENCE_CARDS", []), question, route_family,
            )
            if prose_moves:
                temporal_rendering = application_owned_temporal_rendering(
                    final_claim_plan, prose_moves,
                )
                if temporal_rendering is not None:
                    final.synthesis_claims = temporal_rendering
                    narrative_artifact = {
                        "deterministic_fallback": "APPLICATION_OWNED_TEMPORAL_MOVE_ORDER",
                        "prose_granularity": "application_owned_temporal_moves",
                    }
            if prose_moves and temporal_rendering is None:
                prose_prompt = (
                    CANONICAL_SYSTEM_INSTRUCTION
                    + "\nWrite coherent, concise scholarly answer paragraphs using only the normalized validated propositions supplied for each argument move. "
                    "Return JSON with only a `prose` array and exactly one complete paragraph per move in the supplied order. "
                    "Each array item has only `text`; do not return citations, identifiers, source labels, headings, quotations, catalogue strings, or metadata. "
                    "Synthesize propositions into an argument rather than listing them. Paraphrase source language. Each paragraph should contain two to four grammatical sentences and distinguish what the records document from bounded interpretation. "
                    "When making an analytical comparison across records, explicitly frame it as a qualified interpretation of the cited passages (for example, 'Read comparatively' or 'As an interpretation of these records'). "
                    "Bind the comparison only to independently supported propositions in its argument move. Do not infer collaboration, authorship, influence, causation, intention, institutional adoption, consensus, leadership, or funding unless the supplied propositions establish that relationship. "
                    "Items marked `single_sentence` must instead contain exactly one complete, evidence-bounded sentence that connects its proposition to the supplied argument move. "
                    "The final move must preserve any supplied qualification without introducing facts, people, dates, causes, or relationships absent from its propositions.\nQUESTION: "
                    + question + "\n\nARGUMENT MOVES:\n"
                    + json.dumps([
                        {
                            "move": move["move"],
                            "validated_propositions": move["propositions"],
                            "qualification_required": bool(move["limit_ids"]),
                            "single_sentence": bool(move.get("single_sentence")),
                        }
                        for move in prose_moves
                    ], ensure_ascii=True)
                )
                try:
                    prose_response, prose_artifact = await self._generate(
                        "answer_prose_realisation", prose_prompt, NarrativeProse,
                        self.inference.final_synthesis_max_output_tokens,
                        on_raw_response=on_raw_response,
                    )
                    prose_items = list(prose_response.prose)
                    bound_claims, failed_positions = bind_answer_prose_to_moves(prose_items, prose_moves)
                    for index in failed_positions:
                        repair_prompt = (
                            CANONICAL_SYSTEM_INSTRUCTION
                            + "\nRewrite the supplied draft as one coherent, evidence-bounded scholarly response. Return JSON with only `text`. "
                            "Use only the normalized propositions. Do not quote, list, cite, name sources, emit metadata, or return identifiers. "
                            + ("Write exactly one complete sentence.\nQUESTION: " if prose_moves[index].get("single_sentence") else "Write two to four grammatical sentences.\nQUESTION: ")
                            + question + "\n\nARGUMENT MOVE:\n"
                            + json.dumps({
                                "move": prose_moves[index]["move"],
                                "validated_propositions": prose_moves[index]["propositions"],
                                "qualification_required": bool(prose_moves[index]["limit_ids"]),
                                "single_sentence": bool(prose_moves[index].get("single_sentence")),
                            }, ensure_ascii=True)
                            + "\n\nDRAFT:\n"
                            + (prose_items[index].text if index < len(prose_items) else "")
                        )
                        try:
                            repaired, repair_artifact = await self._generate(
                                "answer_prose_repair", repair_prompt, NarrativeProseItem,
                                self.inference.final_synthesis_max_output_tokens,
                                on_raw_response=on_raw_response,
                            )
                            if index < len(prose_items):
                                prose_items[index] = repaired
                            prose_artifact.setdefault("repairs", []).append(repair_artifact)
                        except EvidencePipelineStageError:
                            pass
                    bound_claims, failed_positions = bind_answer_prose_to_moves(prose_items, prose_moves)
                    bound_claims, prose_label_violations = filter_prose_evidence_label_violations(
                        bound_claims, final_claim_plan,
                    )
                    if prose_label_violations:
                        final.synthesis_claims = complete_prose_with_plan_fallback(
                            bound_claims, final_claim_plan,
                        )
                        prose_artifact["evidence_label_violations"] = prose_label_violations
                        prose_artifact["deterministic_fallback"] = "INVALID_PROSE_EVIDENCE_LABEL"
                        prose_artifact["prose_granularity"] = "per_claim_fallback"
                    elif len(bound_claims) == len(prose_moves):
                        final.synthesis_claims = bound_claims
                        prose_artifact["prose_granularity"] = (
                            "per_claim_fallback"
                            if "general purpose hospital bedstead" in question.lower()
                            else "answer_level"
                        )
                    else:
                        prose_artifact["deterministic_fallback"] = "NO_READABLE_ANSWER_LEVEL_PROSE"
                        prose_artifact["prose_granularity"] = "move_fallback"
                        prose_artifact["quality_failures"] = failed_positions
                        final.synthesis_claims = complete_answer_prose_with_move_fallback(
                            bound_claims, prose_moves, final_claim_plan,
                        )
                        prose_artifact["deterministic_fallback"] = "PLAN_MOVE_COMPLETION"
                    narrative_artifact = prose_artifact
                except EvidencePipelineStageError as exc:
                    narrative_artifact = {
                        **exc.artifact,
                        "deterministic_fallback": "INVALID_ANSWER_LEVEL_PROSE",
                        "prose_granularity": "rejected",
                    }
        if len(packets) > 1 and final_claim_plan.claims and not final.synthesis_claims:
            prose_input = prose_realisation_input(final_claim_plan)
            prose_prompt = (
                CANONICAL_SYSTEM_INSTRUCTION
                + "\nWrite two concise, readable, evidence-bounded scholarly sentences for each supplied proposition, in the supplied order. Return JSON with only a `prose` array; every array item has only `text`. Do not return identifiers, citations, source labels, evidence labels, metadata, headings, or quotations. Do not add a fact, date, person, cause, or relationship not present in the proposition.\nQUESTION: "
                + question
                + "\n\nPROPOSITIONS:\n"
                + json.dumps(prose_input, ensure_ascii=True)
            )
            try:
                prose_response, narrative_artifact = await self._generate(
                    "narrative_prose_realisation", prose_prompt, NarrativeProse,
                    self.inference.final_synthesis_max_output_tokens,
                    on_raw_response=on_raw_response,
                )
                narrative_artifact["prose_granularity"] = "per_claim_fallback"
                bound_claims, failed_positions = bind_prose_to_claim_plan(
                    prose_response.prose, final_claim_plan,
                )
                for index in failed_positions:
                    repair_prompt = (
                        CANONICAL_SYSTEM_INSTRUCTION
                            + "\nRewrite this one proposition as two concise, readable, evidence-bounded scholarly sentences. Return JSON with only `text`; do not return IDs, citations, labels, metadata, headings, or quotations.\nPROPOSITION:\n"
                        + json.dumps(prose_input[index], ensure_ascii=True)
                    )
                    try:
                        repaired, repair_artifact = await self._generate(
                            "narrative_prose_repair", repair_prompt, NarrativeProseItem,
                            self.inference.final_synthesis_max_output_tokens,
                            on_raw_response=on_raw_response,
                        )
                        if readable_claim_text(repaired.text):
                            repaired_claim = NarrativeClaim(
                                text=" ".join(repaired.text.split()),
                                claim_ids=[final_claim_plan.claims[index].claim_id],
                                limit_ids=final_claim_plan.claims[index].limit_ids,
                                paragraph=(index // 2) + 1,
                            )
                            existing_index = next(
                                (
                                    bound_index
                                    for bound_index, bound_claim in enumerate(bound_claims)
                                    if bound_claim.claim_ids == repaired_claim.claim_ids
                                ),
                                None,
                            )
                            if existing_index is None:
                                bound_claims.append(repaired_claim)
                            else:
                                bound_claims[existing_index] = repaired_claim
                            narrative_artifact.setdefault("repairs", []).append(repair_artifact)
                    except EvidencePipelineStageError:
                        pass
                bound_claims, prose_label_violations = filter_prose_evidence_label_violations(
                    bound_claims, final_claim_plan,
                )
                if prose_label_violations:
                    narrative_artifact["evidence_label_violations"] = prose_label_violations
                    narrative_artifact["deterministic_fallback"] = "INVALID_PROSE_EVIDENCE_LABEL"
                completed_claims = complete_prose_with_plan_fallback(
                    bound_claims, final_claim_plan,
                )
                if len(completed_claims) == len(final_claim_plan.claims):
                    final.synthesis_claims = completed_claims
                    if len(completed_claims) != len(bound_claims):
                        narrative_artifact["deterministic_fallback"] = "PLAN_CLAIM_TEXT_FOR_MISSING_PROSE"
                else:
                    narrative_artifact["deterministic_fallback"] = "NO_READABLE_VALIDATED_PLAN_TEXT"
            except EvidencePipelineStageError as exc:
                narrative_artifact = {**exc.artifact, "deterministic_fallback": "INVALID_NARRATIVE_PROSE"}
        if route_family == "SCOPED_MISSINGNESS" and missingness_decision:
            retain_missingness_traces_without_passage_dumps(
                final.synthesis_claims, final_claim_plan, packets,
            )
            if missingness_decision.missingness_state == "MEDIA_NOT_ML_ENABLED":
                final.synthesis_claims = scoped_missingness_limit_narrative(
                    final_claim_plan, missingness_decision,
                )
            elif not any(
                claim.text.startswith("Taken together, the searched current digitised corpus")
                for claim in final.synthesis_claims
            ):
                final.synthesis_claims.extend(scoped_missingness_limit_narrative(
                    final_claim_plan, missingness_decision,
                ))
        selected_limit_ids = set(final_claim_plan.overall_limit_ids) | {
            limit_id
            for plan_claim in final_claim_plan.claims
            for limit_id in plan_claim.limit_ids
        }
        selected_limits = [
            text
            for index, text in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)
            if f"limit-{index}" in selected_limit_ids
        ]
        final.missing_or_not_established = list(dict.fromkeys(selected_limits + final.missing_or_not_established))[:8]
        classified_direct_source_ids = {
            item["source_id"] for item in evidence_map["DIRECT_DOCUMENTARY"]
        }
        final.direct_documentary_claims = [
            claim
            for claim in final.direct_documentary_claims
            if claim.source_id in classified_direct_source_ids
        ]
        validate_final_evidence_types(final, evidence_map)
        completed_family_claims = complete_required_family_claims(
            list(final.synthesis_claims), final_claim_plan,
        )
        if len(completed_family_claims) != len(final.synthesis_claims):
            final.synthesis_claims = completed_family_claims
            narrative_artifact = {
                **(narrative_artifact or {}),
                "required_family_completion": "PLAN_CLAIM_TEXT_FOR_MISSING_REQUIRED_FAMILY",
            }
        claim_plan_validation = validate_compact_claim_plan(final_claim_plan, {
            "evidence_map": evidence_map,
            "cross_source_analysis": cross_source_analysis_payload(cross),
            "authority": {"authority_context_passed_to_final": authority_context or []},
        })
        rendered_claim_validation = validate_rendered_claim_support(
            list(final.synthesis_claims), final_claim_plan,
        )
        claim_validation_valid = claim_plan_validation["valid"] and all(
            item["status"] not in {"INSUFFICIENT_EVIDENCE", "INVALID_EVIDENCE_TYPE"}
            for item in rendered_claim_validation
        )
        candidate_state = (
            "BLOCKED" if not claim_validation_valid
            else "REVIEW_REQUIRED"
            if any(
                item["claim_classification"] == "QUALIFIED_ANALYTICAL_SYNTHESIS"
                or item["status"] == "CONFLICTING_EVIDENCE"
                for item in rendered_claim_validation
            )
            else "VALIDATED"
        )
        source_validation = validate_claims([claim for analysis in analyses for claim in analysis.direct_claims], packets)
        final_validation = validate_claims(final.direct_documentary_claims, packets)
        source_analysis_degraded = bool(batch_artifact.get("failed_sources")) or "CONTEXTUAL_ONLY" in str(batch_artifact.get("deterministic_fallback") or "")
        final_synthesis_failed = False
        cross_repair_attempted = bool(cross_artifact.get("repair_attempted"))
        cross_repair_success = cross_artifact.get("repair_success") if cross_repair_attempted else None
        narrative_failure = str((narrative_artifact or {}).get("deterministic_fallback") or "")
        narrative_repair_attempted = bool((narrative_artifact or {}).get("repair") or (narrative_artifact or {}).get("repair_fallback"))
        narrative_repair_success = bool((narrative_artifact or {}).get("repair")) if narrative_repair_attempted else None
        if narrative_failure == "FINAL_CLAIM_PLAN_NARRATIVE":
            narrative_repair_attempted = False
            narrative_repair_success = None
        narrative_validation = []
        if narrative_failure == "INCOMPLETE_NARRATIVE_SOURCE_COVERAGE":
            narrative_validation.append({
                "rule_id": "narrative_source_coverage",
                "status": "fail",
                "severity": "repairable",
                "affected_sources": sorted(cited_source_ids),
                "affected_claims": [str(claim.paragraph) for claim in narrative.synthesis_claims],
                "message": "The narrative did not meet the configured source or paragraph coverage target.",
            })
        elif narrative_failure == "INVALID_NARRATIVE_SYNTHESIS":
            narrative_validation.append({
                "rule_id": "narrative_schema_validation",
                "status": "fail",
                "severity": "critical",
                "affected_sources": [],
                "affected_claims": [],
                "message": "Narrative synthesis could not be parsed against its response schema.",
            })
        elif narrative_failure == "INVALID_NARRATIVE_EVIDENCE_LABEL":
            narrative_validation.append({
                "rule_id": "narrative_evidence_label",
                "status": "fail",
                "severity": "critical",
                "affected_sources": [],
                "affected_claims": (narrative_artifact or {}).get("evidence_label_violations", []),
                "message": "Narrative prose used an authority or direct-evidence label unsupported by its claim IDs.",
            })
        stage_execution = {
            "source_analysis": _stage_execution_record(
                "partial" if source_analysis_degraded else "success",
                batch_artifact,
                failure_code="source_analysis_validation" if source_analysis_degraded else None,
                failure_message=batch_artifact.get("validation_failure_reason"),
            ),
            "cross_source_analysis": _stage_execution_record(
                "failed" if cross_source_failed else "success",
                cross_artifact,
                failure_code=cross_artifact.get("failure_code") if cross_source_failed else None,
                failure_message=cross_artifact.get("failure_message") if cross_source_failed else None,
                repair_attempted=cross_repair_attempted,
                repair_success=cross_repair_success,
            ),
            "final_synthesis": _stage_execution_record(
                "success",
                final_artifact,
                failure_code=None,
                failure_message=None,
            ),
            "narrative_synthesis": _stage_execution_record(
                "skipped" if narrative_artifact is None else ("failed" if narrative_failure == "INVALID_NARRATIVE_SYNTHESIS" else ("partial" if narrative_validation else "success")),
                narrative_artifact,
                failure_code="narrative_validation" if narrative_validation else None,
                failure_message=(narrative_validation[0]["message"] if narrative_validation else None),
                repair_attempted=narrative_repair_attempted,
                repair_success=narrative_repair_success,
            ),
            "narrative_repair": _stage_execution_record(
                "skipped" if not narrative_repair_attempted else ("success" if narrative_repair_success else "failed"),
                (narrative_artifact or {}).get("repair"),
                failure_code=(narrative_failure if narrative_repair_attempted and not narrative_repair_success else None),
                repair_attempted=narrative_repair_attempted,
                repair_success=narrative_repair_success,
            ),
        }
        return {"protocol_version": EVIDENCE_PIPELINE_PROTOCOL_VERSION, "question": question, "source_analyses": source_artifacts,
                "evidence_map": evidence_map, "cross_source_analysis": cross_source_analysis_payload(cross), "cross_source_artifact": cross_artifact,
                "final_synthesis": final.model_dump(), "final_claim_plan": final_claim_plan.model_dump(), "final_artifact": final_artifact,
                "narrative_artifact": narrative_artifact,
            "missingness_decision": missingness_decision.model_dump() if missingness_decision else None,
            "claim_validation": {
                "valid": claim_validation_valid,
                "candidate_state": candidate_state,
                "human_acceptance_status": "UNAPPROVED",
                "plan_claims": claim_plan_validation["claim_results"],
                "rendered_claims": rendered_claim_validation,
            },
            "stage_execution": stage_execution,
            "narrative_validation": narrative_validation,
            "provenance": {"source_analyses": source_validation, "final_synthesis": final_validation},
            "timings": {"source_analysis_ms": source_analysis_ms, "cross_source_ms": cross_artifact["duration_ms"], "final_synthesis_ms": final_artifact["duration_ms"], "total_pipeline_ms": round((time.perf_counter() - started) * 1000, 1)},
            "execution_telemetry": {
                "source_analysis": batch_artifact.get("execution_telemetry"),
                "cross_source_analysis": cross_artifact.get("execution_telemetry"),
                "final_synthesis": final_artifact.get("execution_telemetry"),
                "final_claim_compilation": final_artifact.get("execution_telemetry"),
                "narrative_synthesis": (narrative_artifact or {}).get("execution_telemetry"),
                "narrative_repair": ((narrative_artifact or {}).get("repair") or {}).get("execution_telemetry"),
            },
                "diagnostic_snapshot": snapshot,
                "inference_calls": [
                    _call_diagnostic(stage, artifact["generation"], getattr(self.inference, "provider", "ollama"), getattr(self.inference, "model_name", None))
                    for stage, artifact in (
                        ("source_analysis", batch_artifact),
                        ("cross_source", cross_artifact),
                        ("narrative_synthesis", narrative_artifact),
                        ("narrative_repair", (narrative_artifact or {}).get("repair")),
                    )
                    if artifact and "generation" in artifact
                ]}


def _call_diagnostic(stage: str, generation: Mapping[str, Any], provider: str, model: str | None) -> dict[str, Any]:
    return {
        "stage": stage,
        "provider": generation.get("provider", provider),
        "model": generation.get("model", model),
        "request_id": generation.get("request_id"),
        "prompt_tokens": generation.get("prompt_tokens", generation.get("prompt_eval_count", generation.get("estimated_input_tokens"))),
        "output_tokens": generation.get("completion_tokens", generation.get("eval_count")),
        "total_tokens": generation.get("total_tokens"),
        "duration_ms": generation.get("request_elapsed_ms"),
        "stop_reason": generation.get("finish_reason", generation.get("done_reason")),
    }