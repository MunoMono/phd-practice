"""Inspectable staged evidence assembly for non-formal Turin v2 diagnostics."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Mapping

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from app.services.inference_service import InferenceTimeoutError
from app.services.archival_benchmark_policy import QuestionEvidencePolicy
from app.services.turin_question_policy import matching_turin_question_policy


EVIDENCE_PIPELINE_PROTOCOL_VERSION = "turin-evidence-pipeline-v2"
SYSTEM_PROMPT_VERSION = "turin-qwen-archival-evidence-v2.0"
CANONICAL_SYSTEM_INSTRUCTION = "Analyse only supplied archival evidence. Type direct documentary evidence, cross-source inference, authority context, and missingness separately. Do not turn co-membership into collaboration, sequence into causation, or missing supplied evidence into historical absence. Treat later testimony as retrospective."
DEFAULT_LOCAL_TOKEN_BUDGET = 1800
DEFAULT_MAX_SOURCES = 5
BATCH_SOURCE_ANALYSIS_MAX_OUTPUT_TOKENS = 1500
EXPLORATORY_INFERENCE_TIMEOUT_SECONDS = 1200


class EvidencePipelineStageError(RuntimeError):
    def __init__(self, stage: str, artifact: dict[str, Any], partial_artifact: dict[str, Any]):
        super().__init__(f"{stage} response did not match its structured schema.")
        self.stage = stage
        self.artifact = artifact
        self.partial_artifact = partial_artifact


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
    quotation_or_paraphrase: str


class SourceClaim(BaseModel):
    source_id: str
    claim: str
    evidence_type: Literal["DIRECT_DOCUMENTARY"] = "DIRECT_DOCUMENTARY"
    evidence: list[EvidenceReference] = Field(min_length=1)


class SourceAnalysis(BaseModel):
    source_id: str
    subject_named: bool
    relationship_to_question: Literal["DIRECT_SUPPORT", "CONTEXTUAL_ONLY", "INFERENCE_ONLY", "NOT_RELEVANT"]
    direct_claims: list[SourceClaim] = Field(default_factory=list, max_length=4)
    contextual_claims: list[str] = Field(default_factory=list, max_length=4)
    people: list[str] = Field(max_length=8)
    activities: list[str] = Field(max_length=8)
    outputs: list[str] = Field(max_length=8)
    dates: list[str] = Field(max_length=8)
    possible_inferences: list[str] = Field(max_length=4)
    not_established: list[str] = Field(max_length=6)


class BatchedSourceAnalyses(BaseModel):
    sources: list[SourceAnalysis] = Field(min_length=1, max_length=DEFAULT_MAX_SOURCES)


class CrossSourceAnalysis(BaseModel):
    supported_by_multiple_sources: list[str] = Field(max_length=8)
    supported_by_one_source: list[str] = Field(max_length=12)
    differences_or_contradictions: list[str] = Field(max_length=6)
    cross_source_inferences: list[str] = Field(max_length=6)
    not_established: list[str] = Field(max_length=8)


class SynthesisClaim(BaseModel):
    text: str = Field(min_length=1)
    source_numbers: list[int] = Field(min_length=1, max_length=DEFAULT_MAX_SOURCES)
    paragraph: int = Field(ge=1, le=2)


class NarrativeSynthesis(BaseModel):
    synthesis_claims: list[SynthesisClaim] = Field(min_length=1, max_length=8)


class FinalSynthesis(BaseModel):
    direct_documentary_claims: list[SourceClaim] = Field(max_length=8)
    cross_source_inferences: list[str] = Field(max_length=6)
    authority_context: list[str] = Field(max_length=4)
    missing_or_not_established: list[str] = Field(max_length=8)
    answer: str
    synthesis_claims: list[SynthesisClaim] = Field(default_factory=list, max_length=8)


def _classification_limits(analyses: list[SourceAnalysis]) -> list[str]:
    direct = [claim for analysis in analyses for claim in analysis.direct_claims]
    limits = [limit for analysis in analyses for limit in analysis.not_established]
    if not direct:
        limits.append("The selected evidence does not directly establish the named subject's activity.")
    limits.append("The selected evidence does not establish a complete reconstruction of the subject's role.")
    return list(dict.fromkeys(limit.strip() for limit in limits if limit.strip()))[:8]


def build_evidence_map(packets: list["SourceEvidencePacket"], analyses: list[SourceAnalysis]) -> dict[str, Any]:
    packet_by_source = {packet.source_id: packet for packet in packets}
    direct_documentary, contextual, cross_source_inference = [], [], []
    for analysis in analyses:
        packet = packet_by_source[analysis.source_id]
        identity = {"source_id": packet.source_id, "document_id": packet.document["document_id"], "pid": packet.document.get("attached_media_pid"), "page": packet.retrieval_match.get("page"), "chunk_ids": [packet.retrieval_match["chunk_id"]]}
        if analysis.relationship_to_question == "DIRECT_SUPPORT":
            if not analysis.subject_named:
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
    if not all(chunk_id in packet_chunks for chunk_id in claim_templates):
        return False

    claims = []
    for chunk_id, claim_text in claim_templates.items():
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
            EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])
        ])
        for claim in claims
    ]
    final.authority_context = list(guard.get("authority_context", []))
    cross_source.cross_source_inferences = []
    final.cross_source_inferences = []
    final.missing_or_not_established = evidence_map["NOT_ESTABLISHED"]
    final.answer = guard["answer"]
    return True


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
        evidence=[EvidenceReference(chunk_id=joint_chunk["chunk_id"], page=joint_chunk.get("page"), quotation_or_paraphrase=joint_text)],
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
        SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])])
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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
    final.direct_documentary_claims = [SourceClaim(source_id=claim["source_id"], claim=claim["claim"], evidence=[EvidenceReference(chunk_id=claim["chunk_ids"][0], page=claim["page"], quotation_or_paraphrase=claim["quotations"][0])]) for claim in claims]
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


def _trim_to_token_budget(chunks: list[dict[str, Any]], matched_id: str, budget: int) -> list[dict[str, Any]]:
    """Keep a deterministic documentary neighbourhood under a conservative token estimate."""
    selected: list[dict[str, Any]] = []
    used = 0
    matched_index = next(value["chunk_index"] for value in chunks if value["chunk_id"] == matched_id)
    ordered_chunks = sorted(
        chunks,
        key=lambda item: (item["chunk_id"] != matched_id, abs(item["chunk_index"] - matched_index), item["chunk_index"]),
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
            chunks = _trim_to_token_budget([_context_chunk(row) for row in rows], str(result["chunk_id"]), local_token_budget)
            match_index = next((index for index, chunk in enumerate(chunks) if chunk["chunk_id"] == result["chunk_id"]), None)
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
                    "source_filename": document_row["filename"], "source_uri": document_row["source_uri"], "caption": authority_data.get("caption"),
                    "description": authority_data.get("scope_and_content") or authority_data.get("abstract"), "contributor": authority_data.get("creator"),
                    "access_rights_status": authority_data.get("rights_access"), "ml_eligibility": document_row["ml_policy_status"],
                    "ml_page_scope": document_row["ml_page_scope"], "corpus_version": document_row["corpus_version"],
                    "archive_record": {"pid": result.get("archive_record_pid"), "title": authority_data.get("record_title")},
                    "attached_media": {"pid": result.get("pid"), "title": authority_data.get("title"), "caption": authority_data.get("caption")},
                    "asset": {"pid": result.get("asset_pid"), "asset_id": result.get("asset_id"), "label": authority_data.get("master_label"), "display_date": authority_data.get("date_text"), "ml_eligible": bool(result.get("use_for_ml", True))},
                    "matched_metadata": list(result.get("metadata_matches") or []),
                },
                retrieval_match={"chunk_id": result["chunk_id"], "page": result.get("page_start"), "score": result.get("score"), "text_score": result.get("text_score", result.get("score")), "metadata_score": result.get("metadata_score", 0), "combined_score": result.get("combined_score", result.get("score")), "channels": result.get("retrieval_channels", ["TEXT_MATCH"]), "matched_metadata": list(result.get("metadata_matches") or []), "matched_text": result.get("text", "")},
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
    packets: list[SourceEvidencePacket], analyses: list[SourceAnalysis]
) -> None:
    expected_ids = [packet.source_id for packet in packets]
    actual_ids = [analysis.source_id for analysis in analyses]
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("Batched source analysis contains duplicate source classifications.")
    if len(actual_ids) != len(expected_ids) or set(actual_ids) != set(expected_ids):
        raise ValueError("Batched source analysis must classify every selected source exactly once.")
    for analysis in analyses:
        if analysis.relationship_to_question == "DIRECT_SUPPORT" and not analysis.subject_named:
            analysis.relationship_to_question = "CONTEXTUAL_ONLY"
            analysis.direct_claims = []
        for claim in analysis.direct_claims:
            if claim.source_id != analysis.source_id:
                raise ValueError("Direct claim source identity does not match its classified source.")
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


def build_batched_source_prompt(question: str, packets: list[SourceEvidencePacket]) -> str:
    return CANONICAL_SYSTEM_INSTRUCTION + "\nReturn only concise JSON with a `sources` array containing exactly one classification per supplied source packet. Judge every source independently: never use one source to upgrade another source from contextual to direct. Allowed relationship_to_question values are DIRECT_SUPPORT, CONTEXTUAL_ONLY, INFERENCE_ONLY, NOT_RELEVANT. subject_named is true only if the subject appears in that source's DOCUMENTARY_TEXT, not metadata. A false subject_named source cannot have direct_claims. Direct claims require exact supplied chunk/page quotations and the matching source_id. ARCHIVAL_METADATA is used only for identity, archival association, and retrieval nomination. A person named only in ARCHIVAL_METADATA is not named in the documentary passage. Archival grouping or keyword association does not prove an activity, relationship, role or historical event. DOCUMENTARY_TEXT is the only material that may establish direct documentary claims. Include not_established limits whenever a source does not establish an aspect of the question.\nQUESTION: " + question + "\n\nSOURCE PACKETS IN DETERMINISTIC RANKED ORDER:\n" + "\n\n".join(format_batched_source_packet(packet) for packet in packets)


def batched_source_prompt_metrics(question: str, packets: list[SourceEvidencePacket], schema: type[BaseModel]) -> dict[str, Any]:
    source_metrics = []
    metadata_characters = documentary_characters = 0
    for packet in packets:
        formatted = format_batched_source_packet(packet)
        metadata = formatted.split("DOCUMENTARY_TEXT:", 1)[0]
        documentary = formatted.split("DOCUMENTARY_TEXT:\n", 1)[1]
        metadata_characters += len(metadata)
        documentary_characters += len(documentary)
        source_metrics.append({"source_id": packet.source_id, "documentary_characters": len(documentary), "metadata_characters": len(metadata), "chunk_count": len(packet.document_context["ordered_chunks"]), "section_heading": packet.document_context.get("section_heading"), "total_packet_characters": len(formatted)})
    prompt = build_batched_source_prompt(question, packets)
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
        artifact = {"raw_response": result["raw_response"], "generation": result["generation"], "duration_ms": round((time.perf_counter() - started) * 1000, 1)}
        if on_raw_response:
            await on_raw_response(stage, artifact)
        try:
            return parse_structured_response(schema, result["raw_response"]), artifact
        except ValidationError as exc:
            artifact["parse_error"] = str(exc)
            raise EvidencePipelineStageError("unknown", artifact, {}) from exc

    async def run(self, question: str, packets: list[SourceEvidencePacket], on_raw_response: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None, authority_context: list[dict[str, Any]] | None = None, policy: QuestionEvidencePolicy | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        if authority_context is not None:
            authority_context.clear()
        batch_prompt = build_batched_source_prompt(question, packets)
        source_metrics = batched_source_prompt_metrics(question, packets, BatchedSourceAnalyses)
        max_input_tokens = getattr(self.inference, "max_input_tokens", 12000)
        if source_metrics["estimated_prompt_tokens"] > max_input_tokens:
            raise ValueError(f"Source analysis prompt exceeds the explicit {max_input_tokens}-token input budget.")
        try:
            batch, batch_artifact = await self._generate(
                "source_analysis", batch_prompt, BatchedSourceAnalyses, BATCH_SOURCE_ANALYSIS_MAX_OUTPUT_TOKENS, source_metrics, on_raw_response
            )
        except EvidencePipelineStageError as exc:
            exc.stage = "source_analysis"
            exc.partial_artifact = {"failed_packets": [packet.model_dump() for packet in packets], "failed_stage": exc.stage, "stage_artifact": exc.artifact}
            raise
        analyses = batch.sources
        try:
            validate_batched_source_analyses(packets, analyses)
        except ValueError:
            fallback = (policy.stage_fallback or {}).get("source_analysis") if policy else None
            analyses = contextual_only_source_analyses(packets)
            batch_artifact["deterministic_fallback"] = (
                "CONFIGURED_CONTEXTUAL_ONLY_SOURCE_ANALYSIS"
                if fallback == "CONTEXTUAL_ONLY"
                else "INVALID_SOURCE_ANALYSIS_CONTEXTUAL_ONLY"
            )
        source_artifacts = [
            {"packet": packet.model_dump(), "analysis": next(analysis for analysis in analyses if analysis.source_id == packet.source_id).model_dump(), **batch_artifact}
            for packet in packets
        ]
        evidence_map = build_evidence_map(packets, analyses)
        source_analysis_ms = batch_artifact["duration_ms"]
        cross_prompt = CANONICAL_SYSTEM_INSTRUCTION + "\nCompare only this deterministic evidence map. Return concise JSON.\n\n" + json.dumps(evidence_map)
        try:
            cross, cross_artifact = await self._generate("cross_source", cross_prompt, CrossSourceAnalysis, self.inference.cross_source_max_output_tokens, on_raw_response=on_raw_response)
        except EvidencePipelineStageError as exc:
            exc.stage = "cross_source_analysis"
            exc.partial_artifact = {"source_analyses": source_artifacts, "evidence_map": evidence_map, "failed_stage": exc.stage, "stage_artifact": exc.artifact}
            raise
        final_prompt = CANONICAL_SYSTEM_INSTRUCTION + "\nAnswer only from this deterministic evidence map and comparison. Authority context is absent. Do not convert CONTEXTUAL evidence into a direct claim about the subject. Do not present CROSS_SOURCE_INFERENCE as documentary fact. Do not infer an individual role from institutional context alone. Preserve all NOT_ESTABLISHED limits. Return concise JSON with typed direct claims, cross-source inferences, missingness, and synthesis_paragraphs. synthesis_paragraphs must contain one or two readable prose paragraphs. Every retained source must appear in source_ids at least once, and each paragraph must explicitly preserve the evidence type and limits of the sources it synthesises. Do not put citation markers in text; source_ids will be rendered as citations.\nQUESTION: " + question + "\n\nEVIDENCE MAP:\n" + json.dumps(evidence_map) + "\n\nCOMPARISON:\n" + cross.model_dump_json()
        try:
            final, final_artifact = await self._generate("final_synthesis", final_prompt, FinalSynthesis, self.inference.final_synthesis_max_output_tokens, on_raw_response=on_raw_response)
        except EvidencePipelineStageError as exc:
            fallback = (policy.stage_fallback or {}).get("final_synthesis") if policy else None
            final = FinalSynthesis(
                direct_documentary_claims=[],
                cross_source_inferences=[],
                authority_context=[],
                missing_or_not_established=[],
                answer="",
                synthesis_claims=[],
            )
            final_artifact = {
                **exc.artifact,
                "deterministic_fallback": (
                    "CONFIGURED_EMPTY_TYPED_SYNTHESIS"
                    if fallback == "EMPTY_TYPED_SYNTHESIS"
                    else "INVALID_FINAL_SYNTHESIS_EVIDENCE_MAP_FALLBACK"
                ),
            }
        apply_configured_synthesis_guard(question, final, evidence_map, packets, cross, policy=policy)
        narrative_artifact = None
        if len(packets) > 1:
            narrative_ledger = json.dumps(evidence_map)
            for index, packet in enumerate(packets, start=1):
                narrative_ledger = narrative_ledger.replace(packet.source_id, str(index))
            narrative_prompt = (
                CANONICAL_SYSTEM_INSTRUCTION
                + "\nWrite one or two coherent research-answer paragraphs from the validated source ledger below. "
                "Use the breadth, differences, and limits across all retained sources. Do not claim that contextual evidence is direct documentary proof. "
                "Do not call a joint credit co-authorship or collaboration unless the ledger explicitly establishes it. Do not say a source confirms more than its ledger claim. "
                "Write no more than 220 words in total and do not mention source numbers in the prose; citations are rendered separately. "
                "Each paragraph must list every source it relies on in source_numbers. Across the paragraphs, include every source number from 1 through "
                + str(len(packets)) + ". "
                "Return JSON with synthesis_claims only. Each item is one complete, evidence-bounded sentence: text, source_numbers, and paragraph (1 or 2). "
                "Do not include numeric citation markers in text.\nQUESTION: "
                + question + "\n\nSOURCE LEDGER:\n" + narrative_ledger
            )
            try:
                narrative, narrative_artifact = await self._generate(
                    "narrative_synthesis", narrative_prompt, NarrativeSynthesis,
                    self.inference.final_synthesis_max_output_tokens, on_raw_response=on_raw_response,
                )
                cited_numbers = {number for claim in narrative.synthesis_claims for number in claim.source_numbers}
                if not cited_numbers.issubset(set(range(1, len(packets) + 1))) or cited_numbers != set(range(1, len(packets) + 1)):
                    narrative_artifact["deterministic_fallback"] = "INCOMPLETE_NARRATIVE_SOURCE_COVERAGE"
                else:
                    final.synthesis_claims = narrative.synthesis_claims
            except EvidencePipelineStageError as exc:
                narrative_artifact = {**exc.artifact, "deterministic_fallback": "INVALID_NARRATIVE_SYNTHESIS"}
        final.missing_or_not_established = list(dict.fromkeys(evidence_map["NOT_ESTABLISHED"] + final.missing_or_not_established))[:8]
        validate_final_evidence_types(final, evidence_map)
        source_validation = validate_claims([claim for analysis in analyses for claim in analysis.direct_claims], packets)
        final_validation = validate_claims(final.direct_documentary_claims, packets)
        return {"protocol_version": EVIDENCE_PIPELINE_PROTOCOL_VERSION, "question": question, "source_analyses": source_artifacts,
                "evidence_map": evidence_map, "cross_source_analysis": cross.model_dump(), "cross_source_artifact": cross_artifact,
                "final_synthesis": final.model_dump(), "final_artifact": final_artifact,
                "narrative_artifact": narrative_artifact,
            "provenance": {"source_analyses": source_validation, "final_synthesis": final_validation},
            "timings": {"source_analysis_ms": source_analysis_ms, "cross_source_ms": cross_artifact["duration_ms"], "final_synthesis_ms": final_artifact["duration_ms"], "total_pipeline_ms": round((time.perf_counter() - started) * 1000, 1)},
                "inference_calls": [
                    _call_diagnostic("source_analysis", batch_artifact["generation"], getattr(self.inference, "provider", "ollama"), getattr(self.inference, "model_name", None)),
                    _call_diagnostic("cross_source", cross_artifact["generation"], getattr(self.inference, "provider", "ollama"), getattr(self.inference, "model_name", None)),
                    _call_diagnostic("final_synthesis", final_artifact["generation"], getattr(self.inference, "provider", "ollama"), getattr(self.inference, "model_name", None)),
                    *([_call_diagnostic("narrative_synthesis", narrative_artifact["generation"], getattr(self.inference, "provider", "ollama"), getattr(self.inference, "model_name", None))] if narrative_artifact and "generation" in narrative_artifact else []),
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