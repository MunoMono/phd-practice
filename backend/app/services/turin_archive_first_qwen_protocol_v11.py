"""Compact, inspectable output contract for archive-first Qwen evaluation v1.1."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


PROTOCOL_VERSION = "turin-archive-first-qwen-evaluation-v1.1"
OUTPUT_TOKEN_LIMIT = 1024
EXPECTED_KEYS = ("direct", "inferences", "contested", "limits")
NEGATIVE_EVIDENCE_PATTERN = re.compile(
    r"\b(does not establish|no direct evidence|cannot determine|does not show|insufficient evidence)\b",
    re.IGNORECASE,
)


class CompactClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=600)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class CompactEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direct: list[CompactClaim] = Field(default_factory=list, max_length=8)
    inferences: list[CompactClaim] = Field(default_factory=list, max_length=6)
    contested: list[CompactClaim] = Field(default_factory=list, max_length=6)
    limits: list[CompactClaim] = Field(default_factory=list, max_length=8)


def build_compact_prompt(question: str, sources: list[dict[str, Any]]) -> str:
    source_blocks = "\n\n".join(
        "\n".join((
            source["source_id"],
            f"TITLE: {source['title']}",
            f"DATE: {source['date'] or 'undated'}",
            f"TYPE: {source['source_type'] or 'unspecified'}",
            f"TEMPORAL_CLASS: {source['temporal_class']}",
            f"PAGE: {source['page']}",
            f"PASSAGE: {source['documentary_passage']}",
        )) for source in sources
    )
    return f"""Use only the supplied documentary passages. Return JSON only, with exactly these keys: direct, inferences, contested, limits. Each value is an array of objects with only claim and source_ids. Use short source IDs such as S1 only. Arrays may be empty. Every claim must be concise and cite supplied source IDs. Put statements about what evidence does not establish only in limits. Inferences belong only in inferences. Do not add prose, markdown, fields, source metadata, or invented facts.

QUESTION: {question}

SOURCES:
{source_blocks}"""


def parse_and_validate(raw_text: str, valid_source_ids: set[str]) -> tuple[CompactEvidenceResponse | None, dict[str, Any]]:
    try:
        raw_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, {"valid": False, "parse_error": f"{exc.msg} at line {exc.lineno}, column {exc.colno}", "flags": ["INVALID_JSON"]}
    if not isinstance(raw_json, dict) or set(raw_json) != set(EXPECTED_KEYS):
        return None, {"valid": False, "parse_error": None, "flags": ["SCHEMA_SHAPE_DEVIATION"]}
    try:
        parsed = CompactEvidenceResponse.model_validate(raw_json)
    except ValidationError as exc:
        return None, {"valid": False, "parse_error": str(exc), "flags": ["SCHEMA_SHAPE_DEVIATION"]}
    flags: list[str] = []
    for section_name in EXPECTED_KEYS:
        for item in getattr(parsed, section_name):
            if not item.source_ids:
                flags.append("UNCITED_CLAIM")
            if set(item.source_ids) - valid_source_ids:
                flags.append("INVALID_SOURCE_ID")
            if section_name == "direct" and NEGATIVE_EVIDENCE_PATTERN.search(item.claim):
                flags.append("MISSECTIONED_LIMIT")
    return parsed, {"valid": not flags, "parse_error": None, "flags": sorted(set(flags))}


def generation_record(
    raw_text: str | None,
    generation: dict[str, Any] | None,
    parsed: CompactEvidenceResponse | None,
    validation: dict[str, Any],
    input_token_estimate: int,
) -> dict[str, Any]:
    """Preserve every observable generation field, including invalid raw output."""
    metadata = generation or {}
    return {
        "raw_text": raw_text if raw_text is not None else "NOT_AVAILABLE",
        "parsed_json_if_valid": parsed.model_dump() if parsed else "NOT_AVAILABLE",
        "input_token_count_or_estimate": input_token_estimate,
        "output_token_count": metadata.get("eval_count", "NOT_AVAILABLE"),
        "output_token_limit": OUTPUT_TOKEN_LIMIT,
        "finish_reason": metadata.get("done_reason", "NOT_AVAILABLE"),
        "generation_duration": metadata.get("request_elapsed_ms", "NOT_AVAILABLE"),
        "provider_runtime_response_metadata": metadata or "NOT_AVAILABLE",
        "parse_error": validation.get("parse_error") or "NOT_AVAILABLE",
        "schema_validation_errors": validation.get("parse_error") if "SCHEMA_SHAPE_DEVIATION" in validation.get("flags", []) else "NOT_AVAILABLE",
        "provenance_validation_errors": [flag for flag in validation.get("flags", []) if flag in {"INVALID_SOURCE_ID", "UNCITED_CLAIM", "MISSECTIONED_LIMIT"}] or "NOT_AVAILABLE",
        "validation": validation,
    }