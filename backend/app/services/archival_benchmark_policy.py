"""Versioned, collection-neutral archival evidence benchmark policies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ARCHIVAL_BENCHMARK_SCHEMA_VERSION = "archival-evidence-benchmark-v1"


@dataclass(frozen=True)
class QuestionEvidencePolicy:
    policy_id: str
    research_case: str
    trigger_all: tuple[str, ...]
    reservation_type: str
    chunk_ids: tuple[str, ...]
    document_pages: tuple[tuple[str, int], ...] = ()
    prohibited_inference_classes: tuple[str, ...] = ()
    expected_missingness: tuple[str, ...] = ()
    expected_direct_facts: tuple[str, ...] = ()
    temporal_boundaries: tuple[Mapping[str, Any], ...] = ()
    authority_context: Mapping[str, Any] | None = None
    archival_associations: tuple[Mapping[str, Any], ...] = ()
    synthesis_guard: Mapping[str, Any] | None = None
    source_selection: Mapping[str, Any] | None = None
    stage_fallback: Mapping[str, str] | None = None

    def matches(self, question: str) -> bool:
        normalized = " ".join(question.lower().split())
        return all(term in normalized for term in self.trigger_all)


def load_question_policies(path: Path) -> tuple[QuestionEvidencePolicy, ...]:
    specification = json.loads(path.read_text())
    if specification.get("schema_version") != ARCHIVAL_BENCHMARK_SCHEMA_VERSION:
        raise ValueError("Unsupported archival evidence benchmark schema version.")
    boundaries = {boundary["id"]: boundary for boundary in specification.get("temporal_boundaries", [])}
    policies = []
    for question in specification.get("questions", []):
        reservation = question.get("reservation") or {}
        policies.append(QuestionEvidencePolicy(
            policy_id=question["id"],
            research_case=question["research_case"],
            trigger_all=tuple(question["triggers"]),
            reservation_type=reservation["type"],
            chunk_ids=tuple(reservation.get("chunk_ids", [])),
            document_pages=tuple((str(item["document_id"]), int(item["page"])) for item in reservation.get("document_pages", [])),
            prohibited_inference_classes=tuple(question.get("prohibited_inference_classes", [])),
            expected_missingness=tuple(question.get("expected_missingness", [])),
            expected_direct_facts=tuple(question.get("expected_direct_facts", [])),
            temporal_boundaries=tuple(boundaries[boundary_id] for boundary_id in question.get("temporal_boundary_ids", []) if boundary_id in boundaries),
            authority_context=question.get("authority_context"),
            archival_associations=tuple(question.get("archival_associations", [])),
            synthesis_guard=question.get("synthesis_guard"),
            source_selection=question.get("source_selection"),
            stage_fallback=question.get("stage_fallback"),
        ))
    validate_question_policies(policies)
    return tuple(policies)


def validate_question_policies(policies: tuple[QuestionEvidencePolicy, ...]) -> None:
    policy_ids: set[str] = set()
    for policy in policies:
        if not policy.policy_id or policy.policy_id in policy_ids:
            raise ValueError("Question policy IDs must be unique and non-empty.")
        if not policy.trigger_all:
            raise ValueError(f"Question policy {policy.policy_id} requires triggers.")
        if policy.reservation_type == "CONFIGURED_DOCUMENT_PAGES" and not policy.document_pages:
            raise ValueError(f"Question policy {policy.policy_id} requires configured document pages.")
        if policy.reservation_type != "CONFIGURED_DOCUMENT_PAGES" and policy.reservation_type != "GENERIC_ARCHIVE_FIRST" and not policy.chunk_ids:
            raise ValueError(f"Question policy {policy.policy_id} requires reserved chunks for {policy.reservation_type}.")
        if len(set(policy.document_pages)) != len(policy.document_pages):
            raise ValueError(f"Question policy {policy.policy_id} document pages must be unique.")
        for association in policy.archival_associations:
            required = {"record_pid", "scope", "controlled_fields", "source", "description"}
            if not required.issubset(association):
                raise ValueError(f"Question policy {policy.policy_id} archival associations require record scope and provenance.")
        if policy.synthesis_guard:
            claim_templates = policy.synthesis_guard.get("claim_templates", {})
            if set(claim_templates) != set(policy.chunk_ids):
                raise ValueError(f"Question policy {policy.policy_id} guard templates must match its reserved chunks.")
            if not policy.synthesis_guard.get("answer"):
                raise ValueError(f"Question policy {policy.policy_id} guard requires an answer.")
        if policy.stage_fallback and not policy.synthesis_guard:
            raise ValueError(f"Question policy {policy.policy_id} fallback requires a synthesis guard.")
        policy_ids.add(policy.policy_id)