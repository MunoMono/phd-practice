"""Deterministic context and local Granite infrastructure for Turin fixtures."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, Field, StringConstraints, ValidationError


SYSTEM_PROMPT_V1 = """You are assisting with a bounded archival research experiment concerning the Royal College of Art Department of Design Research (DDR), 1965–1985.

Use only the supplied context.

Keep SOURCE DOCUMENT EVIDENCE separate from ARCHIVE / DATABASE AUTHORITY CONTEXT.

Do not present archive/database authority metadata as if it were quotation from a source document.

When both are supplied, distinguish them explicitly: use "Authority records indicate..." for authority context and "Retrieved documents show..." for documentary evidence.

Do not use general knowledge to complete missing information.

Do not claim that an event, person or relationship is absent from history because it is absent from the supplied context.

Separate direct documentary support from interpretation.

Preserve disagreement, contradiction and uncertainty.

Cite substantive documentary claims using the supplied source PID, page and chunk identifiers.

For every documentary evidence item, source_pid must exactly copy the numeric value shown after SOURCE PID: in the cited source block.

Never place DOCUMENT ID, ARCHIVE RECORD PID, ATTACHED-MEDIA PID, ASSET PID, or a derived identifier in source_pid.

When evidence is insufficient, state exactly what the supplied context does not establish.

Return valid JSON matching the required response schema."""

CONTEXT_BUILDER_VERSION = "turin-context-budget-v3"
CONTEXT_ASSEMBLY_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.1"
STRUCTURED_OUTPUT_MAX_TOKENS = 500
V13_STRUCTURED_OUTPUT_MAX_TOKENS = 1000
V14_STRUCTURED_OUTPUT_MAX_TOKENS = 1500
V15_STRUCTURED_OUTPUT_MAX_TOKENS = 1500
LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS = 350
OUTPUT_CAPACITY_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.2"
V13_OUTPUT_CAPACITY_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.3"
V14_OUTPUT_CAPACITY_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.4"
V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.5"
V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.6"
QWEN_COMPARISON_PROTOCOL_VERSION = "turin-comparison-protocol-v2.0-qwen"


def structured_output_max_tokens(execution_protocol_version: str | None) -> int:
    if execution_protocol_version in {V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, QWEN_COMPARISON_PROTOCOL_VERSION}:
        return V15_STRUCTURED_OUTPUT_MAX_TOKENS
    if execution_protocol_version == V14_OUTPUT_CAPACITY_PROTOCOL_VERSION:
        return V14_STRUCTURED_OUTPUT_MAX_TOKENS
    if execution_protocol_version == V13_OUTPUT_CAPACITY_PROTOCOL_VERSION:
        return V13_STRUCTURED_OUTPUT_MAX_TOKENS
    return STRUCTURED_OUTPUT_MAX_TOKENS if execution_protocol_version == OUTPUT_CAPACITY_PROTOCOL_VERSION else LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS

RESPONSE_SCHEMA_INSTRUCTION = """Return only a JSON object with exactly these top-level fields:
{
    "answer": "string",
    "evidence": [{"claim": "string", "source_pid": "string", "page": 1, "chunk_id": "string", "quotation_or_paraphrase": "string"}],
    "inferences": [{"inference": "string", "supporting_sources": ["chunk id"], "confidence": "low|medium|high", "rationale": "string"}],
    "contradictions": [{"description": "string", "sources": ["chunk id"]}],
    "missingness": [{"scope": "string", "category": "string", "explanation": "string", "follow_up_action": null}],
    "follow_up_queries": ["string"],
    "authority_assertions": [{"assertion": "string", "source": "string", "authority_id": "string"}]
}
Use empty arrays where the supplied context does not support a category."""

CONCISE_RESPONSE_REQUIREMENT = """The local runtime is bounded. Keep the answer under 180 characters; use at most one concise item in each array; keep every string under 180 characters; use empty arrays rather than elaborating unsupported categories."""

KNOWN_RELATIONSHIP_COMMISSIONING_REQUIREMENT = """For this known-relationship commissioning response, return exactly one evidence item with a quotation_or_paraphrase under 100 characters. The evidence array must contain exactly one complete object. Do not split evidence fields across multiple objects. The claim, source_pid, page, chunk_id, and quotation_or_paraphrase fields must all belong to that same evidence object. Never output partial evidence objects. Return only the JSON object with no additional text. Keep answer under 120 characters. Return empty arrays for inferences, contradictions, missingness, follow_up_queries, and authority_assertions unless a non-empty item is strictly required by the supplied source."""


class EvidenceItem(BaseModel):
    claim: str
    source_pid: str
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


RESPONSE_SCHEMA_VERSION = "turin-archival-analysis-response-v1"
CONCISE_RESPONSE_SCHEMA_VERSION = "turin-archival-analysis-response-v1.5-concise"
ConciseText = Annotated[str, StringConstraints(max_length=180)]


class ConciseEvidenceItem(BaseModel):
    claim: ConciseText
    source_pid: str
    page: int | None = None
    chunk_id: str
    quotation_or_paraphrase: ConciseText


class ConciseInferenceItem(BaseModel):
    inference: ConciseText
    supporting_sources: list[str]
    confidence: Literal["low", "medium", "high"]
    rationale: ConciseText


class ConciseContradictionItem(BaseModel):
    description: ConciseText
    sources: list[str]


class ConciseMissingnessItem(BaseModel):
    scope: ConciseText
    category: ConciseText
    explanation: ConciseText
    follow_up_action: ConciseText | None = None


class ConciseAuthorityAssertion(BaseModel):
    assertion: ConciseText
    source: str
    authority_id: str


class ConciseArchivalAnalysisResponse(BaseModel):
    answer: ConciseText
    evidence: list[ConciseEvidenceItem] = Field(max_length=1)
    inferences: list[ConciseInferenceItem] = Field(max_length=1)
    contradictions: list[ConciseContradictionItem] = Field(max_length=1)
    missingness: list[ConciseMissingnessItem] = Field(max_length=1)
    follow_up_queries: list[ConciseText] = Field(max_length=1)
    authority_assertions: list[ConciseAuthorityAssertion] = Field(default_factory=list, max_length=1)


def response_schema_definition(execution_protocol_version: str | None = None) -> dict[str, Any]:
    response_model = ConciseArchivalAnalysisResponse if execution_protocol_version in {V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, QWEN_COMPARISON_PROTOCOL_VERSION} else ArchivalAnalysisResponse
    return response_model.model_json_schema()


def response_schema_version(execution_protocol_version: str | None = None) -> str:
    return CONCISE_RESPONSE_SCHEMA_VERSION if execution_protocol_version in {V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, QWEN_COMPARISON_PROTOCOL_VERSION} else RESPONSE_SCHEMA_VERSION


def response_schema_hash(schema: Mapping[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    context_assembly_protocol_version: str = CONTEXT_ASSEMBLY_PROTOCOL_VERSION
    authority_context_requested: bool = False
    authority_context_included: bool = False
    authority_context_omitted_reason: str | None = None
    authority_context_character_cost: int = 0
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
    response: Any | None = None
    parse_error: str | None = None
    repair_attempted: bool = False
    structural_normalisations: list[str] = Field(default_factory=list)


class TurinExperimentError(RuntimeError):
    """Base error for bounded experiment inference."""


class InferenceNotReadyError(TurinExperimentError):
    pass


class ContextOverflowError(TurinExperimentError):
    pass


class ContextRepresentationError(TurinExperimentError):
    pass


class ParseError(TurinExperimentError):
    pass


# Historical runner imports remain valid without making Granite the active abstraction.
GraniteExperimentError = TurinExperimentError
GraniteNotReadyError = InferenceNotReadyError
GraniteContextOverflowError = ContextOverflowError
GraniteParseError = ParseError


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
        zero_documentary_evidence: bool = False,
    ) -> ContextAssemblyResult:
        if input_budget <= 0:
            raise GraniteContextOverflowError("Input budget must be positive.")
        template = PROMPT_REGISTER[research_case]
        fixed_prompt = f"{template.system_template}\n\n{template.user_template.replace('{question}', question).replace('{context}', '')}"
        fixed_prompt_chars = len(fixed_prompt)
        available = input_budget - fixed_prompt_chars
        if available < 0:
            raise GraniteContextOverflowError("System prompt, research question and response schema exceed Granite input budget.")

        source_items = []
        for rank, chunk in enumerate(ranked_chunks, 1):
            chunk_id = str(_field(chunk, "chunk_id", chunk.get("id", "")))
            source_items.append((rank, chunk, chunk_id, str(chunk.get("text") or chunk.get("chunk_text") or ""), self._document_block(rank, chunk, catalogue_metadata, "")))

        header_chars = sum(len(header) for _, _, _, _, header in source_items) + max(0, len(source_items) - 1) * 2
        if header_chars > available:
            raise ContextRepresentationError("Complete provenance headers for all retrieved sources exceed the documentary context budget.")
        text_capacity = available - header_chars
        text_cap = self._max_min_text_cap([len(original_text) for _, _, _, original_text, _ in source_items], text_capacity)

        parts: list[str] = ["[DOCUMENTARY EVIDENCE]\nNo documentary passages were retrieved for this question."] if zero_documentary_evidence else []
        supplied: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        for rank, chunk, chunk_id, original_text, _ in source_items:
            supplied_text = self._direct_text_prefix(original_text, text_cap)
            excerpted = len(supplied_text) < len(original_text)
            parts.append(self._document_block(rank, chunk, catalogue_metadata, supplied_text))
            supplied.append(dict(chunk, retrieval_rank=rank, chunk_id=chunk_id, text=supplied_text, original_text=original_text))
            decisions.append({
                "retrieval_rank": rank,
                "chunk_id": chunk_id,
                "original_chars": len(original_text),
                "supplied_chars": len(supplied_text),
                "header_chars": len(self._document_block(rank, chunk, catalogue_metadata, "")),
                "included_in_context": True,
                "excerpted": excerpted,
                "exclusion_reason": None,
            })

        requested_authorities = authority_context or [] if authority_mode == "document_plus_authority_context" else []
        authority_block = self._authority_block(requested_authorities, non_documentary_label=zero_documentary_evidence) if requested_authorities else ""
        authority_omitted_reason: str | None = None
        included_authorities = requested_authorities
        if authority_block and len("\n\n".join([*parts, authority_block])) > available:
            included_authorities = []
            authority_omitted_reason = "authority_context_exceeds_remaining_documentary_budget"
        elif authority_block:
            parts.append(authority_block)
        context = "\n\n".join(parts)
        return ContextAssemblyResult(
            context=context, context_mode=authority_mode, document_chunk_count=len(supplied),
            authority_context_count=len(included_authorities), context_character_count=len(context),
            context_budget=available, input_budget_chars=input_budget, fixed_prompt_chars=fixed_prompt_chars,
            available_evidence_chars=available, assembled_input_chars=fixed_prompt_chars + len(context),
            authority_context_requested=bool(requested_authorities),
            authority_context_included=bool(included_authorities),
            authority_context_omitted_reason=authority_omitted_reason,
            authority_context_character_cost=len(authority_block),
            omitted_chunk_ids=[], omitted_chunks={}, supplied_chunks=supplied, evidence_decisions=decisions,
        )

    @staticmethod
    def _max_min_text_cap(lengths: list[int], capacity: int) -> int:
        if not lengths or capacity <= 0:
            return 0
        lower, upper = 0, max(lengths)
        while lower < upper:
            candidate = (lower + upper + 1) // 2
            if sum(min(length, candidate) for length in lengths) <= capacity:
                lower = candidate
            else:
                upper = candidate - 1
        return lower

    @staticmethod
    def _direct_text_prefix(text: str, character_cap: int) -> str:
        if len(text) <= character_cap:
            return text
        prefix = text[:character_cap]
        boundary = max(prefix.rfind(" "), prefix.rfind("\n"), prefix.rfind("\t"))
        return prefix[:boundary].rstrip() if boundary > 0 else ""

    @staticmethod
    def _document_block(rank: int, chunk: Mapping[str, Any], catalogue_metadata: Mapping[str, Any] | None, text: str | None = None) -> str:
        pid = _field(chunk, "pid", "")
        document_id = _field(chunk, "document_id", "")
        chunk_id = _field(chunk, "chunk_id", chunk.get("id", ""))
        metadata = dict(catalogue_metadata or {})
        metadata.update(chunk.get("catalogue_metadata") or {})
        lines = [f"[SOURCE DOCUMENT EVIDENCE {rank}]", f"RANK: {rank}", f"SOURCE PID: {pid}", f"DOCUMENT ID: {document_id}", f"TITLE: {metadata.get('title') or _field(chunk, 'title', '')}", f"PAGE: {_field(chunk, 'page', _field(chunk, 'source_page', ''))}", f"CHUNK ID: {chunk_id}", f"ARCHIVE RESOLUTION STATUS: {chunk.get('archive_resolution_status', '')}"]
        lines.extend(_render_fields({key: metadata.get(key) for key in ("date", "creator", "archive_reference", "document_type")}))
        lines.extend(["TEXT:", str(chunk.get("text") or chunk.get("chunk_text") or "") if text is None else text])
        return "\n".join(lines)

    @staticmethod
    def _authority_block(authorities: list[AuthorityContext], non_documentary_label: bool = False) -> str:
        blocks = []
        for authority in authorities:
            header = "[ARCHIVE / DATABASE AUTHORITY CONTEXT — NOT DOCUMENTARY EVIDENCE]" if non_documentary_label else "[ARCHIVE / DATABASE AUTHORITY CONTEXT]"
            blocks.append("\n".join([header, f"SOURCE: {authority.source}", f"AUTHORITY TYPE: {authority.authority_type}", f"AUTHORITY ID: {authority.authority_id}", f"ROLE: {authority.role}", "FIELDS:", *_render_fields(authority.fields)]))
        return "\n\n".join(blocks)


def render_prompt(research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"], question: str, context: ContextAssemblyResult) -> tuple[PromptTemplate, str]:
    template = PROMPT_REGISTER[research_case]
    user_prompt = template.user_template.replace("{question}", question).replace("{context}", context.context)
    return template, f"{template.system_template}\n\n{user_prompt}"


def _parse_response(raw_response: str, response_model: type[BaseModel] = ArchivalAnalysisResponse) -> tuple[BaseModel, list[str]]:
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    payload = json.loads(candidate)
    normalisations: list[str] = []
    for field_name in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions"):
        if isinstance(payload.get(field_name), dict):
            payload[field_name] = [payload[field_name]]
            normalisations.append(f"{field_name}: singleton object normalized to list")
    return response_model.model_validate(payload), normalisations


async def parse_with_one_repair(raw_response: str, repair: Any | None = None, response_model: type[BaseModel] = ArchivalAnalysisResponse) -> StructuredResponseResult:
    try:
        response, normalisations = _parse_response(raw_response, response_model)
        return StructuredResponseResult(raw_response=raw_response, response=response, structural_normalisations=normalisations)
    except (ValidationError, ValueError) as exc:
        if repair is None:
            return StructuredResponseResult(raw_response=raw_response, parse_error=str(exc))
        repair_prompt = "Repair JSON formatting and schema only. Do not add, remove, or alter historical substance. Return only JSON.\n\n" + RESPONSE_SCHEMA_INSTRUCTION + "\n\nORIGINAL RESPONSE:\n" + raw_response
        repaired = await repair(repair_prompt)
        try:
            response, normalisations = _parse_response(repaired, response_model)
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
        if str(_field(chunk, "pid", "")) != item.source_pid:
            issues.append(f"citation_identifier_mismatch: evidence source_pid for {item.chunk_id} must exactly match the supplied numeric SOURCE PID.")
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
    for block in re.findall(r"\[ARCHIVE / DATABASE AUTHORITY CONTEXT(?: — NOT DOCUMENTARY EVIDENCE)?\](.*?)(?=\n\n\[|\Z)", context.context, flags=re.DOTALL):
        source = re.search(r"^SOURCE: (.+)$", block, flags=re.MULTILINE)
        authority_id = re.search(r"^AUTHORITY ID: (.+)$", block, flags=re.MULTILINE)
        if source and authority_id:
            records.append({"source": source.group(1), "authority_id": authority_id.group(1)})
    return records


def _approximately_present(quote: str, text: str) -> bool:
    words = [word for word in re.findall(r"\w+", quote) if len(word) > 2]
    return bool(words) and sum(word in text for word in words) / len(words) >= 0.8


class LocalInference(Protocol):
    def get_load_status(self) -> dict[str, Any]: ...
    def get_model_info(self) -> dict[str, Any]: ...
    async def generate_experiment(self, prompt: str, max_tokens: int, temperature: float, top_p: float, do_sample: bool, response_schema: dict[str, Any] | None = None) -> dict[str, Any]: ...


class ExperimentInferenceService:
    def __init__(self, inference: LocalInference, context_builder: ContextBuilder | None = None):
        self.inference = inference
        self.context_builder = context_builder or ContextBuilder()

    async def infer(self, research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"], question: str, context: ContextAssemblyResult, max_tokens: int = LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS, on_raw_response: Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]] | None = None, allow_repair: bool = True, execution_protocol_version: str | None = None) -> dict[str, Any]:
        if context.context_character_count > context.context_budget:
            raise ContextOverflowError("Assembled context exceeds its configured budget.")
        status = self.inference.get_load_status()
        if not status.get("model_ready"):
            raise InferenceNotReadyError(f"Active inference runtime not ready (status={status.get('model_status')}).")
        template, prompt = render_prompt(research_case, question, context)
        if context.input_budget_chars is not None and len(prompt) > context.input_budget_chars:
            raise ContextOverflowError(f"Experiment prompt exceeds configured input budget ({context.input_budget_chars} chars).")
        started = time.monotonic()
        schema = response_schema_definition(execution_protocol_version)
        response_model = ConciseArchivalAnalysisResponse if execution_protocol_version in {V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, QWEN_COMPARISON_PROTOCOL_VERSION} else ArchivalAnalysisResponse
        result = await self.inference.generate_experiment(prompt, max_tokens=max_tokens, temperature=0.0, top_p=1.0, do_sample=False, response_schema=schema)
        if on_raw_response:
            await on_raw_response(result["raw_response"], result.get("generation", {}), self.inference.get_model_info())
        repair_generation: dict[str, Any] | None = None

        async def repair_call(repair_prompt: str) -> str:
            nonlocal repair_generation
            repair_result = await self.inference.generate_experiment(
                repair_prompt, max_tokens=max_tokens, temperature=0.0, top_p=1.0, do_sample=False, response_schema=schema
            )
            repair_generation = repair_result.get("generation", {})
            return repair_result["raw_response"]

        parsed = await parse_with_one_repair(result["raw_response"], repair_call if allow_repair else None, response_model)
        provenance = validate_provenance(parsed.response, context) if parsed.response else None
        return {"prompt": prompt, "prompt_template": template.model_dump(), "context": context.model_dump(), "raw_response": result["raw_response"], "parsed": parsed.model_dump(), "provenance": provenance.model_dump() if provenance else None, "model": self.inference.get_model_info(), "generation": result.get("generation", {}), "repair_generation": repair_generation, "response_schema": schema, "response_schema_version": response_schema_version(execution_protocol_version), "response_schema_hash": response_schema_hash(schema), "inference_duration_seconds": time.monotonic() - started}


# Preserve historical runner/test imports without exposing Granite to active callers.
GraniteExperimentService = ExperimentInferenceService