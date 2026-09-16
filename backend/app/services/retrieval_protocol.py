"""Versioned, researcher-approved retrieval plans for Turin experiments."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator


RETRIEVAL_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.0"


class RetrievalFacet(BaseModel):
    facet_id: str = Field(min_length=1)
    alternatives: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_alternatives(self) -> "RetrievalFacet":
        if any(not value.strip() for value in self.alternatives):
            raise ValueError("Retrieval facet alternatives must be non-empty.")
        return self


class ResolvedAuthority(BaseModel):
    authority_source: str = Field(min_length=1)
    authority_type: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)
    resolution_status: Literal["resolved", "ambiguous", "unresolved"]


class AuthorityDerivedVariant(BaseModel):
    facet_id: str = Field(min_length=1)
    authority_source: str = Field(min_length=1)
    authority_type: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    role: Literal["controlled_query_expansion"]
    rationale: str = Field(min_length=1)
    approval_state: Literal["approved", "pending", "rejected"]


class ResearcherSynonym(BaseModel):
    facet_id: str = Field(min_length=1)
    value: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    approval_state: Literal["approved", "pending", "rejected"]


class TemporalRetrievalStratum(BaseModel):
    stratum_id: Literal["contemporary", "retrospective"]
    classification: Literal["contemporary DDR document", "later retrospective account"]
    top_k: int = Field(ge=1, le=50)
    year_from: int | None = None
    year_to: int | None = None
    source_type: Literal["any", "oral_history"] = "any"
    lexical_facets: list[RetrievalFacet] | None = None


class RetrievalPlan(BaseModel):
    plan_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    protocol_version: str = RETRIEVAL_PROTOCOL_VERSION
    plan_version: str = Field(min_length=1)
    researcher_approval_state: Literal["approved", "pending", "rejected"]
    researcher_approved_at: datetime | None = None
    lexical_facets: list[RetrievalFacet] = Field(min_length=1)
    resolved_authorities: list[ResolvedAuthority] = Field(default_factory=list)
    authority_variants: list[AuthorityDerivedVariant] = Field(default_factory=list)
    researcher_synonyms: list[ResearcherSynonym] = Field(default_factory=list)
    retrieval_scope: Literal["corpus_wide", "sensitivity_or_diagnostic"] = "corpus_wide"
    run_classification: Literal["primary", "protocol_revision", "sensitivity_or_diagnostic"] = "primary"
    supersedes_plan_id: str | None = None
    authority_linked_document_ids: list[str] = Field(default_factory=list)
    authority_document_link_ids: list[str] = Field(default_factory=list)
    temporal_strata: list[TemporalRetrievalStratum] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=50)
    notes: str | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def validate_plan(self) -> "RetrievalPlan":
        facet_ids = [facet.facet_id for facet in self.lexical_facets]
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("Retrieval plan facet IDs must be unique.")
        known_facets = set(facet_ids)
        for variant in [*self.authority_variants, *self.researcher_synonyms]:
            if variant.facet_id not in known_facets:
                raise ValueError("Retrieval variants must belong to a declared lexical facet.")
        if self.researcher_approval_state == "approved" and self.researcher_approved_at is None:
            raise ValueError("Approved retrieval plans require an approval timestamp.")
        if self.authority_linked_document_ids and self.retrieval_scope != "sensitivity_or_diagnostic":
            raise ValueError("Authority-linked document restriction is allowed only for sensitivity_or_diagnostic scope.")
        if self.authority_linked_document_ids and not self.authority_document_link_ids:
            raise ValueError("Authority-linked document restriction requires recorded authority-document link IDs.")
        if self.authority_document_link_ids and not self.authority_linked_document_ids:
            raise ValueError("Authority-document link IDs require an explicit diagnostic document restriction.")
        if self.retrieval_scope == "sensitivity_or_diagnostic" and self.run_classification != "sensitivity_or_diagnostic":
            raise ValueError("Diagnostic retrieval scope requires sensitivity_or_diagnostic classification.")
        if self.run_classification == "sensitivity_or_diagnostic" and self.retrieval_scope != "sensitivity_or_diagnostic":
            raise ValueError("Sensitivity classification requires sensitivity_or_diagnostic retrieval scope.")
        if self.run_classification == "primary" and self.retrieval_scope != "corpus_wide":
            raise ValueError("Primary Turin runs require corpus_wide retrieval scope.")
        if self.run_classification == "protocol_revision" and not self.supersedes_plan_id:
            raise ValueError("Protocol revisions require the superseded retrieval plan ID.")
        if self.supersedes_plan_id == self.plan_id:
            raise ValueError("A retrieval plan cannot supersede itself.")
        if self.temporal_strata:
            stratum_ids = [stratum.stratum_id for stratum in self.temporal_strata]
            if set(stratum_ids) != {"contemporary", "retrospective"} or len(stratum_ids) != 2:
                raise ValueError("Temporal retrieval plans require contemporary and retrospective strata exactly once.")
            if sum(stratum.top_k for stratum in self.temporal_strata) != self.top_k:
                raise ValueError("Temporal stratum capacities must sum to the plan top_k.")
        return self

    def require_formal_approval(self) -> None:
        if self.researcher_approval_state != "approved" or self.researcher_approved_at is None:
            raise ValueError("Formal Turin runs require a researcher-approved retrieval plan.")
        if any(variant.approval_state != "approved" for variant in self.authority_variants):
            raise ValueError("Unapproved authority variants cannot enter formal retrieval.")
        if any(synonym.approval_state != "approved" for synonym in self.researcher_synonyms):
            raise ValueError("Unapproved researcher synonyms cannot enter formal retrieval.")


@dataclass(frozen=True)
class CompiledRetrievalPlan:
    lexical_formulation: dict[str, list[str]]
    tsquery_expression: str
    parameters: dict[str, str]


def compile_retrieval_plan(
    plan: RetrievalPlan,
    lexical_facets: list[RetrievalFacet] | None = None,
) -> CompiledRetrievalPlan:
    """Compile declared facets without inspecting or rewriting the research question."""
    active_facets = lexical_facets or plan.lexical_facets
    variants_by_facet: dict[str, list[str]] = {facet.facet_id: list(facet.alternatives) for facet in active_facets}
    for variant in plan.authority_variants:
        if variant.facet_id not in variants_by_facet:
            continue
        if variant.approval_state != "approved":
            raise ValueError("Unapproved authority variants cannot enter retrieval.")
        variants_by_facet[variant.facet_id].append(variant.value)
    for synonym in plan.researcher_synonyms:
        if synonym.facet_id not in variants_by_facet:
            continue
        if synonym.approval_state != "approved":
            raise ValueError("Unapproved researcher synonyms cannot enter retrieval.")
        variants_by_facet[synonym.facet_id].append(synonym.value)

    parameters: dict[str, str] = {}
    facet_expressions: list[str] = []
    lexical_formulation: dict[str, list[str]] = {}
    for facet_index, facet in enumerate(active_facets):
        values = list(dict.fromkeys(value.strip() for value in variants_by_facet[facet.facet_id]))
        lexical_formulation[facet.facet_id] = values
        alternatives = []
        for value_index, value in enumerate(values):
            parameter_name = f"facet_{facet_index}_{value_index}"
            parameters[parameter_name] = value
            alternatives.append(f"websearch_to_tsquery('english', :{parameter_name})")
        facet_expressions.append(f"({' || '.join(alternatives)})")
    return CompiledRetrievalPlan(
        lexical_formulation=lexical_formulation,
        tsquery_expression=f"({' && '.join(facet_expressions)})",
        parameters=parameters,
    )