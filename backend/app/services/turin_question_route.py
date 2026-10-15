"""Deterministic question-intent routing for Source Interrogation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal
from app.services.retrieval_contract_service import project_anchors_from_question


RouteFamily = Literal[
    "AUTHORITY_ONLY",
    "DOCUMENTARY",
    "HYBRID_AUTHORITY_DOCUMENTARY",
    "SCOPED_MISSINGNESS",
]


@dataclass(frozen=True)
class QuestionRouteDecision:
    family: RouteFamily
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HybridQuestionDecomposition:
    """Typed documentary surface for a hybrid authority/documentary question."""

    authority_query: str
    documentary_query: str
    documentary_anchors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


MISSINGNESS_PATTERN = re.compile(
    r"\b(?:does|do|can|what can)\b.{0,140}\b(?:current |digitised |digital )?"
    r"(?:corpus|archive|apparatus|evidence|text retrieval|authority[- ]source associations|"
    r"overlap|photographs?|visual)\b.{0,140}\b(?:establish|prove|show)\b|"
    r"\b(?:can|does|do)\b.{0,140}\b(?:surviving|digitised|digital)\b.{0,80}\b"
    r"(?:records?|evidence)\b.{0,100}\b(?:reception|received|impact|establish)\b|"
    r"\b(?:responsib(?:le|ility)|caus(?:e|al)|collaborat(?:e|ion)|authors?hip|"
    r"current text retrieval|non[- ]?text|photographs?|visual)\b",
    re.IGNORECASE,
)
DOCUMENTARY_PATTERN = re.compile(
    r"\b(?:documents?|records?|reports?|papers?|lecture(?:s)?|course(?:s)?|notes?|"
    r"prospectuses?|calendars?|transcripts?|material|surviving|documentary|"
    r"teaching|curriculum|what do(?:es)? .+ (?:show|say|describe|establish)|"
    r"how do(?:es)? .+ (?:show|say|describe|document))\b",
    re.IGNORECASE,
)
AUTHORITY_CUE_PATTERN = re.compile(
    r"\b(?:according to (?:the )?(?:database |project )?authorit(?:y|ies)|"
    r"database (?:authority|record)|project authority|controlled (?:methodology |ddr )?"
    r"(?:registry|periods?|vocabulary)|employment (?:trajectory|period)|"
    r"employment authorit(?:y|ies)|formal (?:ddr )?role|"
    r"recorded (?:role|job title|employment|period|lead|funder|duration)|"
    r"(?:role|job title|employment period|employment trajectory|project lead|funder|duration)"
    r" (?:is|are|was|were|recorded)|who is recorded as (?:project )?lead|"
    r"who is recorded as (?:leading|funding)|who (?:is )?recorded as (?:leading|funding))\b",
    re.IGNORECASE,
)
HYBRID_CONNECTOR_PATTERN = re.compile(
    r"\b(?:and what do(?:es)?|and how do(?:es)?|compare with|alongside|"
    r"documentary (?:evidence|traces)|surviving (?:documents?|records?|reports?))\b",
    re.IGNORECASE,
)
HYBRID_DOCUMENTARY_CLAUSE_PATTERN = re.compile(
    r"\b(?:and\s+)?(?P<documentary>"
    r"(?:what|how)\s+do(?:es)?\b.+|"
    r"(?:documentary\s+(?:evidence|traces)|surviving\s+(?:documents?|records?|reports?))\b.+"
    r")",
    re.IGNORECASE,
)
EXPLICIT_DOCUMENTARY_ANCHOR_PATTERN = re.compile(
    r"\b(?:job|project)\s+(?:number\s+)?\d+\b",
    re.IGNORECASE,
)


def classify_question_route(question: str) -> QuestionRouteDecision:
    """Classify intent before entity/authority resolution can influence retrieval."""
    normalized = " ".join(question.split())
    closure_rationale = bool(re.search(
        r"\b(?:why|reason|rationale|cause)\b.{0,120}\b(?:ddr|department of design research)\b.{0,120}\b(?:close|closed|closure|closing)\b|"
        r"\b(?:ddr|department of design research)\b.{0,120}\b(?:close|closed|closure|closing)\b",
        normalized,
        re.IGNORECASE,
    ))
    missingness = bool(MISSINGNESS_PATTERN.search(normalized))
    documentary = bool(DOCUMENTARY_PATTERN.search(normalized))
    authority = bool(AUTHORITY_CUE_PATTERN.search(normalized))
    hybrid_connector = bool(HYBRID_CONNECTOR_PATTERN.search(normalized))

    if authority and (documentary or hybrid_connector):
        return QuestionRouteDecision(
            "HYBRID_AUTHORITY_DOCUMENTARY",
            ["controlled_authority_context_requested", "documentary_interpretation_requested"],
        )
    if missingness or closure_rationale:
        return QuestionRouteDecision(
            "SCOPED_MISSINGNESS",
            ["closure_rationale_requires_scoped_evidence", "entity_resolution_is_context_only"]
            if closure_rationale else ["evidence_test_or_negative_control", "entity_resolution_is_context_only"],
        )
    if authority:
        return QuestionRouteDecision(
            "AUTHORITY_ONLY",
            ["controlled_database_fact_requested", "no_documentary_interpretation_requested"],
        )
    return QuestionRouteDecision(
        "DOCUMENTARY",
        ["documentary_interpretation_default", "entity_resolution_is_context_only"],
    )


def decompose_hybrid_question(question: str) -> HybridQuestionDecomposition | None:
    """Extract the documentary proposition without reusing authority-side wording."""
    normalized = " ".join(question.split())
    if classify_question_route(normalized).family != "HYBRID_AUTHORITY_DOCUMENTARY":
        return None
    connector = re.search(
        r"\band\s+(?=(?:what|how)\b|documentary\s+(?:evidence|traces)\b)",
        normalized, re.IGNORECASE,
    )
    match = HYBRID_DOCUMENTARY_CLAUSE_PATTERN.search(
        normalized, connector.end() if connector else 0,
    )
    if match is None:
        return None
    documentary_query = match.group("documentary").strip()
    if not documentary_query:
        return None
    anchors = list(dict.fromkeys(
        anchor.group(0).strip()
        for anchor in EXPLICIT_DOCUMENTARY_ANCHOR_PATTERN.finditer(normalized)
    ))
    anchors.extend(
        f"Job {number}" for number in project_anchors_from_question(normalized)
        if not any(re.search(rf"\b{number}\b", anchor) for anchor in anchors)
    )
    authority_query = normalized[:connector.start() if connector else match.start()].strip(" ,;")
    return HybridQuestionDecomposition(
        authority_query=authority_query,
        documentary_query=documentary_query,
        documentary_anchors=anchors,
    )
