"""Persistence and one-shot prompt construction for researcher UI captures."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import text


CAPTURE_MODE = "archive_first_one_shot"
CAPTURE_CLASSIFICATION = "RESEARCHER_UI_CAPTURE"
ARCHIVE_SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"
SECTION_HEADINGS = (
    "DIRECT DOCUMENTARY EVIDENCE",
    "CROSS-SOURCE INFERENCE",
    "CONTESTED / QUALIFIED EVIDENCE",
    "WHAT THE EVIDENCE DOES NOT ESTABLISH",
)
SOURCE_CLASSIFICATIONS = {
    "DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXTUAL",
    "CONTRADICTORY_OR_CONTESTING", "NO_RELEVANT_PASSAGE",
}


def build_one_shot_prompt(question: str, sources: list[dict[str, Any]]) -> str:
    source_text = "\n\n".join(
        "\n".join((
            f"SOURCE S{index}",
            f"TITLE: {source.get('title') or 'unavailable'}",
            f"DATE: {source.get('snapshot', {}).get('catalogue_metadata', {}).get('date') or 'undated'}",
            f"TYPE: {source.get('snapshot', {}).get('catalogue_metadata', {}).get('source_type') or 'unspecified'}",
            f"PAGE: {source.get('page_start') or 'unavailable'}",
            f"PASSAGE: {source.get('excerpt') or source.get('text') or ''}",
            "EVIDENTIAL CLASSIFICATION: State exactly one of DIRECT_SUPPORT, PARTIAL_SUPPORT, CONTEXTUAL, CONTRADICTORY_OR_CONTESTING, or NO_RELEVANT_PASSAGE for this source from the documentary passage only; archive metadata only nominates this source.",
        )) for index, source in enumerate(sources, start=1)
    )
    return f"""Use only the supplied documentary passages. Job/project metadata may nominate a source but is not documentary proof. Do not invent people, roles, activities, outputs, causation, reception, or archival absence. Distinguish direct evidence, cross-source inference, contested or qualified evidence, and limits. For every supplied source, include one line in the relevant section in this form: S1 [DIRECT_SUPPORT]: concise claim. Use only DIRECT_SUPPORT, PARTIAL_SUPPORT, CONTEXTUAL, CONTRADICTORY_OR_CONTESTING, or NO_RELEVANT_PASSAGE. Cite every substantive claim with its supplied source IDs in square brackets. Return concise researcher-readable plain text with exactly these headings:\n\nDIRECT DOCUMENTARY EVIDENCE\n\nCROSS-SOURCE INFERENCE\n\nCONTESTED / QUALIFIED EVIDENCE\n\nWHAT THE EVIDENCE DOES NOT ESTABLISH\n\nEXACT REGISTERED QUESTION\n{question}\n\nFIXED ARCHIVE-FIRST EVIDENCE\n{source_text}"""


def parse_one_shot_output(raw_output: str, supplied_source_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Record output citations and source classes without inferring or repairing either."""
    normalized = raw_output.replace("**", "")
    headings = [(heading, normalized.find(heading)) for heading in SECTION_HEADINGS]
    claims: list[dict[str, Any]] = []
    classes: dict[str, str] = {}
    for index, (heading, start) in enumerate(headings):
        if start < 0:
            continue
        following = [position for _, position in headings[index + 1:] if position >= 0]
        section_text = normalized[start + len(heading):min(following) if following else len(normalized)]
        for line in section_text.splitlines():
            claim_text = line.strip().lstrip("-• ").strip()
            if not claim_text or claim_text.lower() in {"none.", "none"}:
                continue
            source_ids = re.findall(r"\bS\d+\b", claim_text)
            declared = re.findall(r"\b(DIRECT_SUPPORT|PARTIAL_SUPPORT|CONTEXTUAL|CONTRADICTORY_OR_CONTESTING|NO_RELEVANT_PASSAGE)\b", claim_text)
            for source_id in source_ids:
                if declared and source_id in supplied_source_ids:
                    classes[source_id] = declared[0]
            if not source_ids:
                provenance_status = "UNCITED_CLAIM"
            elif set(source_ids) - supplied_source_ids:
                provenance_status = "INVALID_SOURCE_ID"
            else:
                provenance_status = "PROVENANCE_PASS"
            claims.append({"claim_id": f"claim-{len(claims) + 1}", "section": heading, "claim_text": claim_text, "source_ids": source_ids, "provenance_status": provenance_status})
    return claims, [{"source_id": source_id, "classification": classes.get(source_id, "UNCLASSIFIED")} for source_id in sorted(supplied_source_ids, key=lambda value: int(value[1:]))]


def project_claim_provenance(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark explicit prompt echoes without mutating stored capture data."""
    projected: list[dict[str, Any]] = []
    echo_active = False
    for claim in claims:
        projected_claim = dict(claim)
        if claim.get("claim_text", "").strip() == "EXACT REGISTERED QUESTION":
            echo_active = True
        if echo_active:
            projected_claim["provenance_status"] = "FORMAT_VIOLATION"
        projected.append(projected_claim)
    return projected


class ResearcherUiCaptureService:
    def persist(self, db: Any, payload: dict[str, Any]) -> str:
        capture_id = f"researcher-ui-capture-{uuid.uuid4().hex[:12]}"
        db.execute(text("""
            INSERT INTO researcher_ui_captures (
                capture_id, capture_classification, mode, question_id, exact_question,
                corpus_version, archive_snapshot_version, retrieved_sources, selected_passages,
                qwen_raw_output, parsed_output_if_available, provenance_result,
                evidential_limits, model_config, claim_provenance, source_classifications
            ) VALUES (
                :capture_id, :capture_classification, :mode, :question_id, :exact_question,
                :corpus_version, :archive_snapshot_version, CAST(:retrieved_sources AS jsonb),
                CAST(:selected_passages AS jsonb), :qwen_raw_output,
                CAST(:parsed_output_if_available AS jsonb), CAST(:provenance_result AS jsonb),
                CAST(:evidential_limits AS jsonb), CAST(:model_config AS jsonb)
                , CAST(:claim_provenance AS jsonb), CAST(:source_classifications AS jsonb)
            )
        """), {
            "capture_id": capture_id,
            "capture_classification": CAPTURE_CLASSIFICATION,
            "mode": CAPTURE_MODE,
            "question_id": payload.get("question_id"),
            "exact_question": payload["exact_question"],
            "corpus_version": payload["corpus_version"],
            "archive_snapshot_version": ARCHIVE_SNAPSHOT_VERSION,
            "retrieved_sources": json.dumps(payload["retrieved_sources"]),
            "selected_passages": json.dumps(payload["selected_passages"]),
            "qwen_raw_output": payload.get("qwen_raw_output"),
            "parsed_output_if_available": json.dumps(payload.get("parsed_output_if_available")),
            "provenance_result": json.dumps(payload["provenance_result"]),
            "evidential_limits": json.dumps(payload["evidential_limits"]),
            "model_config": json.dumps(payload["model_config"]),
            "claim_provenance": json.dumps(payload["claim_provenance"]),
            "source_classifications": json.dumps(payload["source_classifications"]),
        })
        db.commit()
        return capture_id