"""Deterministic context and local Granite infrastructure for Turin fixtures."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, Field, ValidationError


SYSTEM_PROMPT_V1 = """You are assisting with a bounded archival research experiment concerning the Royal College of Art Department of Design Research (DDR), 1965–1985.

Use only the supplied context.

Keep SOURCE DOCUMENT EVIDENCE separate from ARCHIVE / DATABASE AUTHORITY CONTEXT.

Do not present archive/database authority metadata as if it were quotation from a source document.

Do not use general knowledge to complete missing information.

Do not claim that an event, person or relationship is absent from history because it is absent from the supplied context.

Separate direct documentary support from interpretation.

Preserve disagreement, contradiction and uncertainty.

Cite substantive documentary claims using the supplied PID, page and chunk identifiers.

When evidence is insufficient, state exactly what the supplied context does not establish.

Return valid JSON matching the required response schema."""

CONTEXT_BUILDER_VERSION = "turin-context-budget-v2"

RESPONSE_SCHEMA_INSTRUCTION = """Return only a JSON object with exactly these top-level fields:
{
    "answer": "string",
    "evidence": [{"claim": "string", "pid": "string", "page": 1, "chunk_id": "string", "quotation_or_paraphrase": "string"}],
    "inferences": [{"inference": "string", "supporting_sources": ["chunk id"], "confidence": "low|medium|high", "rationale": "string"}],
    "contradictions": [{"description": "string", "sources": ["chunk id"]}],
    "missingness": [{"scope": "string", "category": "string", "explanation": "string", "follow_up_action": null}],
    "follow_up_queries": ["string"],
    "authority_assertions": [{"assertion": "string", "source": "string", "authority_id": "string"}]
}
Use empty arrays where the supplied context does not support a category."""

CONCISE_RESPONSE_REQUIREMENT = """The local runtime is bounded. Keep the answer under 180 characters; use at most one concise item in each array; keep every string under 180 characters; use empty arrays rather than elaborating unsupported categories."""

KNOWN_RELATIONSHIP_COMMISSIONING_REQUIREMENT = """For this known-relationship commissioning response, return exactly one evidence item with a quotation_or_paraphrase under 100 characters. Keep answer under 120 characters. Return empty arrays for inferences, contradictions, missingness, follow_up_queries, and authority_assertions unless a non-empty item is strictly required by the supplied source."""


class EvidenceItem(BaseModel):
    claim: str
    pid: str
    page: int | None = None
    chunk_id: str
    quotation_or_paraphrase: str


class InferenceItem(BaseModel):
    inference: str
    supporting_sources: list[str]
    confidence: Literal["low", "medium", "high"]
    rationale: str


class ContradictionItem(BaseModel):
    description: str
    sources: list[str]


class MissingnessItem(BaseModel):
    scope: str
    category: str
    explanation: str
    follow_up_action: str | None = None


class AuthorityAssertion(BaseModel):
    assertion: str
    source: str
    authority_id: str


class ArchivalAnalysisResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItem]
    inferences: list[InferenceItem]
    contradictions: list[ContradictionItem]
    missingness: list[MissingnessItem]
    follow_up_queries: list[str]
    authority_assertions: list[AuthorityAssertion] = Field(default_factory=list)


class AuthorityContext(BaseModel):
    source: str
    authority_type: str
    authority_id: str
    role: str
    fields: dict[str, Any]


class ContextAssemblyResult(BaseModel):
    context: str
    context_mode: Literal["document_only", "document_plus_authority_context"]
    document_chunk_count: int
    authority_context_count: int
    context_character_count: int
    context_budget: int
    context_builder_version: str = CONTEXT_BUILDER_VERSION
    input_budget_chars: int | None = None
    fixed_prompt_chars: int = 0
    available_evidence_chars: int | None = None
    assembled_input_chars: int | None = None
    omitted_chunk_ids: list[str]
    omitted_chunks: dict[str, str]
    supplied_chunks: list[dict[str, Any]]
    evidence_decisions: list[dict[str, Any]] = Field(default_factory=list)


class ProvenanceValidationResult(BaseModel):
    valid: bool
    checked_claims: int
    valid_claims: int
    invalid_claims: int
    issues: list[str]


class StructuredResponseResult(BaseModel):
    raw_response: str
    repaired_response: str | None = None
    response: ArchivalAnalysisResponse | None = None
    parse_error: str | None = None
    repair_attempted: bool = False
    structural_normalisations: list[str] = Field(default_factory=list)


class GraniteExperimentError(RuntimeError):
    """Base error for bounded experiment inference."""


class GraniteNotReadyError(GraniteExperimentError):
    pass


class GraniteContextOverflowError(GraniteExperimentError):
    pass


class GraniteParseError(GraniteExperimentError):
    pass


class PromptTemplate(BaseModel):
    prompt_name: str
    prompt_version: str
    research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"]
    system_template: str
    user_template: str
    created_metadata: dict[str, str] = Field(default_factory=lambda: {"instrument": "turin_experiment"})


PROMPT_REGISTER = {
    "known_relationship": PromptTemplate(
        prompt_name="turin_known_relationship", prompt_version="v4", research_case="known_relationship",
        system_template=SYSTEM_PROMPT_V1,
        user_template="RESEARCH CASE: known relationship\nQUESTION: {question}\n\nCONTEXT:\n{context}\n\n" + RESPONSE_SCHEMA_INSTRUCTION + "\n" + CONCISE_RESPONSE_REQUIREMENT + "\n" + KNOWN_RELATIONSHIP_COMMISSIONING_REQUIREMENT,
    ),
    "contested_interpretation": PromptTemplate(
        prompt_name="turin_contested_interpretation", prompt_version="v3", research_case="contested_interpretation",
        system_template=SYSTEM_PROMPT_V1,
        user_template="RESEARCH CASE: contested interpretation\nQUESTION: {question}\n\nCONTEXT:\n{context}\n\n" + RESPONSE_SCHEMA_INSTRUCTION + "\n" + CONCISE_RESPONSE_REQUIREMENT + "\nPreserve contradictions.",
    ),
    "scoped_missingness": PromptTemplate(
        prompt_name="turin_scoped_missingness", prompt_version="v3", research_case="scoped_missingness",
        system_template=SYSTEM_PROMPT_V1,
        user_template="RESEARCH CASE: scoped missingness\nQUESTION: {question}\n\nCONTEXT:\n{context}\n\n" + RESPONSE_SCHEMA_INSTRUCTION + "\n" + CONCISE_RESPONSE_REQUIREMENT + "\nDescribe only what this supplied context does not establish; do not claim historical absence.",
    ),
}


def _field(chunk: Mapping[str, Any], name: str, default: Any = None) -> Any:
    aliases = {"source_page": "page_start", "page": "page_start"}
    alias = aliases.get(name)
    return chunk.get(name, chunk.get(alias, chunk.get("provenance", {}).get(name, default)))


def _render_fields(fields: Mapping[str, Any]) -> list[str]:
    return [f"{key.upper()}: {value}" for key, value in sorted(fields.items()) if value is not None and value != ""]


class ContextBuilder:
    def assemble(
        self,
        ranked_chunks: list[Mapping[str, Any]],
        catalogue_metadata: Mapping[str, Any] | None = None,
        authority_context: list[AuthorityContext] | None = None,
        context_budget: int = 6000,
        authority_mode: Literal["document_only", "document_plus_authority_context"] = "document_only",
    ) -> ContextAssemblyResult:
        if context_budget <= 0:
            raise GraniteContextOverflowError("Context budget must be positive.")
        parts: list[str] = []
        supplied: list[dict[str, Any]] = []
        omitted: dict[str, str] = {}
        for rank, chunk in enumerate(ranked_chunks, 1):
            chunk_id = str(_field(chunk, "chunk_id", chunk.get("id", "")))
            block = self._document_block(rank, chunk, catalogue_metadata)
            candidate = "\n\n".join([*parts, block]) if parts else block
            if len(candidate) > context_budget:
                omitted[chunk_id] = "exceeds_context_budget_without_truncation"
                continue
            parts.append(block)
            supplied.append(dict(chunk, retrieval_rank=rank, chunk_id=chunk_id))
        included_authorities = authority_context or [] if authority_mode == "document_plus_authority_context" else []
        if included_authorities:
            authority_block = self._authority_block(included_authorities)
            candidate = "\n\n".join([*parts, authority_block])
            if len(candidate) > context_budget:
                for item in included_authorities:
                    omitted[f"authority:{item.authority_id}"] = "authority_context_exceeds_context_budget"
                included_authorities = []
            else:
                parts.append(authority_block)
        context = "\n\n".join(parts)
        return ContextAssemblyResult(
            context=context, context_mode=authority_mode, document_chunk_count=len(supplied),
            authority_context_count=len(included_authorities), context_character_count=len(context),
            context_budget=context_budget, omitted_chunk_ids=[key for key in omitted if not key.startswith("authority:")],
            omitted_chunks=omitted, supplied_chunks=supplied,
        )

    def assemble_for_prompt(
        self,
        research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"],
        question: str,
        ranked_chunks: list[Mapping[str, Any]],
        catalogue_metadata: Mapping[str, Any] | None = None,
        authority_context: list[AuthorityContext] | None = None,
        input_budget: int = 6000,
        authority_mode: Literal["document_only", "document_plus_authority_context"] = "document_only",
    ) -> ContextAssemblyResult:
        if input_budget <= 0:
            raise GraniteContextOverflowError("Input budget must be positive.")
        template = PROMPT_REGISTER[research_case]
        fixed_prompt = f"{template.system_template}\n\n{template.user_template.replace('{question}', question).replace('{context}', '')}"
        fixed_prompt_chars = len(fixed_prompt)
        available = input_budget - fixed_prompt_chars
        if available < 0:
            raise GraniteContextOverflowError("System prompt, research question and response schema exceed Granite input budget.")

        parts: list[str] = []
        supplied: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        omitted: dict[str, str] = {}
        for rank, chunk in enumerate(ranked_chunks, 1):
            chunk_id = str(_field(chunk, "chunk_id", chunk.get("id", "")))
            original_text = str(chunk.get("text") or chunk.get("chunk_text") or "")
            full_block = self._document_block(rank, chunk, catalogue_metadata, original_text)
            remaining = available - len("\n\n".join(parts)) - (2 if parts else 0)
            supplied_text = original_text
            excerpted = False
            exclusion_reason: str | None = None
            if len(full_block) > remaining:
                header = self._document_block(rank, chunk, catalogue_metadata, "")
                text_budget = remaining - len(header)
                if text_budget <= 0:
                    supplied_text = ""
                    exclusion_reason = "insufficient_budget_for_evidence_header"
                    omitted[chunk_id] = exclusion_reason
                else:
                    supplied_text = original_text[:text_budget]
                    excerpted = len(supplied_text) < len(original_text)
            if exclusion_reason is None:
                block = self._document_block(rank, chunk, catalogue_metadata, supplied_text)
                parts.append(block)
                supplied.append(dict(chunk, retrieval_rank=rank, chunk_id=chunk_id, text=supplied_text, original_text=original_text))
            decisions.append({
                "retrieval_rank": rank,
                "chunk_id": chunk_id,
                "original_chars": len(original_text),
                "supplied_chars": len(supplied_text) if exclusion_reason is None else 0,
                "included_in_context": exclusion_reason is None,
                "excerpted": excerpted,
                "exclusion_reason": exclusion_reason,
            })

        included_authorities = authority_context or [] if authority_mode == "document_plus_authority_context" else []
        if included_authorities:
            authority_block = self._authority_block(included_authorities)
            if len("\n\n".join([*parts, authority_block])) > available:
                for item in included_authorities:
                    omitted[f"authority:{item.authority_id}"] = "authority_context_exceeds_evidence_budget"
                included_authorities = []
            else:
                parts.append(authority_block)
        context = "\n\n".join(parts)
        return ContextAssemblyResult(
            context=context, context_mode=authority_mode, document_chunk_count=len(supplied),
            authority_context_count=len(included_authorities), context_character_count=len(context),
            context_budget=available, input_budget_chars=input_budget, fixed_prompt_chars=fixed_prompt_chars,
            available_evidence_chars=available, assembled_input_chars=fixed_prompt_chars + len(context),
            omitted_chunk_ids=[key for key in omitted if not key.startswith("authority:")],
            omitted_chunks=omitted, supplied_chunks=supplied, evidence_decisions=decisions,
        )

    @staticmethod
    def _document_block(rank: int, chunk: Mapping[str, Any], catalogue_metadata: Mapping[str, Any] | None, text: str | None = None) -> str:
        pid = _field(chunk, "pid", "")
        document_id = _field(chunk, "document_id", "")
        chunk_id = _field(chunk, "chunk_id", chunk.get("id", ""))
        metadata = dict(catalogue_metadata or {})
        metadata.update(chunk.get("catalogue_metadata") or {})
        lines = [f"[SOURCE DOCUMENT EVIDENCE {rank}]", f"RANK: {rank}", f"PID: {pid}", f"DOCUMENT ID: {document_id}", f"TITLE: {metadata.get('title') or _field(chunk, 'title', '')}", f"PAGE: {_field(chunk, 'page', _field(chunk, 'source_page', ''))}", f"CHUNK: {chunk_id}", f"ARCHIVE RESOLUTION STATUS: {chunk.get('archive_resolution_status', '')}"]
        lines.extend(_render_fields({key: metadata.get(key) for key in ("date", "creator", "archive_reference", "document_type")}))
        lines.extend(["TEXT:", str(chunk.get("text") or chunk.get("chunk_text") or "") if text is None else text])
        return "\n".join(lines)

    @staticmethod
    def _authority_block(authorities: list[AuthorityContext]) -> str:
        blocks = []
        for authority in authorities:
            blocks.append("\n".join(["[ARCHIVE / DATABASE AUTHORITY CONTEXT]", f"SOURCE: {authority.source}", f"AUTHORITY TYPE: {authority.authority_type}", f"AUTHORITY ID: {authority.authority_id}", f"ROLE: {authority.role}", "FIELDS:", *_render_fields(authority.fields)]))
        return "\n\n".join(blocks)


def render_prompt(research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"], question: str, context: ContextAssemblyResult) -> tuple[PromptTemplate, str]:
    template = PROMPT_REGISTER[research_case]
    user_prompt = template.user_template.replace("{question}", question).replace("{context}", context.context)
    return template, f"{template.system_template}\n\n{user_prompt}"


def _parse_response(raw_response: str) -> tuple[ArchivalAnalysisResponse, list[str]]:
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    payload = json.loads(candidate)
    normalisations: list[str] = []
    for field_name in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions"):
        if isinstance(payload.get(field_name), dict):
            payload[field_name] = [payload[field_name]]
            normalisations.append(f"{field_name}: singleton object normalized to list")
    return ArchivalAnalysisResponse.model_validate(payload), normalisations


async def parse_with_one_repair(raw_response: str, repair: Any | None = None) -> StructuredResponseResult:
    try:
        response, normalisations = _parse_response(raw_response)
        return StructuredResponseResult(raw_response=raw_response, response=response, structural_normalisations=normalisations)
    except (ValidationError, ValueError) as exc:
        if repair is None:
            return StructuredResponseResult(raw_response=raw_response, parse_error=str(exc))
        repair_prompt = "Repair JSON formatting and schema only. Do not add, remove, or alter historical substance. Return only JSON.\n\n" + RESPONSE_SCHEMA_INSTRUCTION + "\n\nORIGINAL RESPONSE:\n" + raw_response
        repaired = await repair(repair_prompt)
        try:
            response, normalisations = _parse_response(repaired)
            return StructuredResponseResult(raw_response=raw_response, repaired_response=repaired, response=response, repair_attempted=True, structural_normalisations=normalisations)
        except (ValidationError, ValueError) as repair_exc:
            return StructuredResponseResult(raw_response=raw_response, repaired_response=repaired, parse_error=str(repair_exc), repair_attempted=True)


def validate_provenance(response: ArchivalAnalysisResponse, context: ContextAssemblyResult) -> ProvenanceValidationResult:
    supplied = {str(chunk["chunk_id"]): chunk for chunk in context.supplied_chunks}
    issues: list[str] = []
    valid_claims = 0
    for item in response.evidence:
        chunk = supplied.get(item.chunk_id)
        if chunk is None:
            reason = "omitted" if item.chunk_id in context.omitted_chunk_ids else "not supplied"
            issues.append(f"Evidence citation {item.chunk_id} was {reason} in context.")
            continue
        if str(_field(chunk, "pid", "")) != item.pid:
            issues.append(f"Evidence citation {item.chunk_id} has a PID that does not match supplied context.")
            continue
        page = _field(chunk, "page", _field(chunk, "source_page"))
        if item.page is not None and str(page) != str(item.page):
            issues.append(f"Evidence citation {item.chunk_id} has a page that does not match supplied context.")
            continue
        quote = item.quotation_or_paraphrase.strip().lower()
        text = str(chunk.get("text") or chunk.get("chunk_text") or "").lower()
        if quote and quote not in text and not _approximately_present(quote, text):
            issues.append(f"Evidence citation {item.chunk_id} quotation is not present in source text.")
            continue
        valid_claims += 1
    authorities = {
        (str(item.get("authority_id")), str(item.get("source")))
        for item in _authority_records_from_context(context)
    }
    for raw_assertion in response.authority_assertions:
        assertion = AuthorityAssertion.model_validate(raw_assertion)
        if (assertion.authority_id, assertion.source) not in authorities:
            issues.append(f"Authority assertion {assertion.authority_id} is not present in supplied authority context.")
        else:
            valid_claims += 1
    checked = len(response.evidence) + len(response.authority_assertions)
    return ProvenanceValidationResult(valid=not issues, checked_claims=checked, valid_claims=valid_claims, invalid_claims=checked - valid_claims, issues=issues)


def _authority_records_from_context(context: ContextAssemblyResult) -> list[dict[str, str]]:
    records = []
    for block in re.findall(r"\[ARCHIVE / DATABASE AUTHORITY CONTEXT\](.*?)(?=\n\n\[|\Z)", context.context, flags=re.DOTALL):
        source = re.search(r"^SOURCE: (.+)$", block, flags=re.MULTILINE)
        authority_id = re.search(r"^AUTHORITY ID: (.+)$", block, flags=re.MULTILINE)
        if source and authority_id:
            records.append({"source": source.group(1), "authority_id": authority_id.group(1)})
    return records


def _approximately_present(quote: str, text: str) -> bool:
    words = [word for word in re.findall(r"\w+", quote) if len(word) > 2]
    return bool(words) and sum(word in text for word in words) / len(words) >= 0.8


class LocalGranite(Protocol):
    def get_load_status(self) -> dict[str, Any]: ...
    def get_model_info(self) -> dict[str, Any]: ...
    async def generate_experiment(self, prompt: str, max_tokens: int, temperature: float, top_p: float, do_sample: bool) -> dict[str, Any]: ...


class GraniteExperimentService:
    def __init__(self, granite: LocalGranite, context_builder: ContextBuilder | None = None):
        self.granite = granite
        self.context_builder = context_builder or ContextBuilder()

    async def infer(self, research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"], question: str, context: ContextAssemblyResult, max_tokens: int = 350) -> dict[str, Any]:
        if context.context_character_count > context.context_budget:
            raise GraniteContextOverflowError("Assembled context exceeds its configured budget.")
        status = self.granite.get_load_status()
        if not status.get("model_ready"):
            raise GraniteNotReadyError(f"Granite runtime not ready (status={status.get('model_status')}).")
        template, prompt = render_prompt(research_case, question, context)
        if context.input_budget_chars is not None and len(prompt) > context.input_budget_chars:
            raise GraniteContextOverflowError(f"Experiment prompt exceeds Granite input budget ({context.input_budget_chars} chars).")
        started = time.monotonic()
        result = await self.granite.generate_experiment(prompt, max_tokens=max_tokens, temperature=0.0, top_p=1.0, do_sample=False)

        async def repair_call(repair_prompt: str) -> str:
            repair_result = await self.granite.generate_experiment(
                repair_prompt, max_tokens=max_tokens, temperature=0.0, top_p=1.0, do_sample=False
            )
            return repair_result["raw_response"]

        parsed = await parse_with_one_repair(result["raw_response"], repair_call)
        provenance = validate_provenance(parsed.response, context) if parsed.response else None
        return {"prompt": prompt, "prompt_template": template.model_dump(), "context": context.model_dump(), "raw_response": result["raw_response"], "parsed": parsed.model_dump(), "provenance": provenance.model_dump() if provenance else None, "model": self.granite.get_model_info(), "generation": result.get("generation", {}), "inference_duration_seconds": time.monotonic() - started}