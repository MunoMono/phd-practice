"""Deterministic integrity bindings for persisted provenance records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def query_run_chunk_digest(payload: dict[str, Any]) -> str:
    return sha256_digest({
        "chunk_id": payload["chunk_id"],
        "document_id": payload.get("document_id"),
        "page_range": payload.get("page_range"),
        "rank": payload.get("rank"),
        "score": payload.get("score"),
        "citation_text": payload.get("citation_text"),
        "provenance_json": payload.get("provenance_json"),
        "source_metadata_json": payload.get("source_metadata_json"),
    })


def query_run_digest(payload: dict[str, Any], chunk_digests: list[str]) -> str:
    return sha256_digest({
        "query_id": payload["query_id"],
        "prompt": payload["prompt"],
        "mode": payload.get("mode"),
        "model": payload.get("model"),
        "response": payload.get("response"),
        "caveats": payload.get("caveats"),
        "failed_or_partial": bool(payload.get("failed_or_partial")),
        "failure_reason": payload.get("failure_reason"),
        "chunk_sha256": chunk_digests,
    })


def claim_evidence_digest(payload: dict[str, Any]) -> str:
    return sha256_digest({
        "claim_id": payload["claim_id"],
        "chunk_id": payload["chunk_id"],
        "document_id": payload.get("document_id"),
        "page_range": payload.get("page_range"),
        "citation_text": payload.get("citation_text"),
        "provenance_json": payload.get("provenance_json"),
    })


def provenance_event_digest(payload: dict[str, Any]) -> str:
    return sha256_digest({
        "event_id": payload["event_id"],
        "event_type": payload["event_type"],
        "subject_type": payload["subject_type"],
        "subject_id": payload["subject_id"],
        "actor": payload.get("actor"),
        "previous_event_sha256": payload.get("previous_event_sha256"),
        "payload_json": payload.get("payload_json") or {},
        "created_at": payload["created_at"],
    })


def experiment_evidence_digest(payload: dict[str, Any]) -> str:
    return sha256_digest({
        "run_id": payload["run_id"],
        "rank": payload["rank"],
        "chunk_id": payload["chunk_id"],
        "document_id": payload["document_id"],
        "supplied_excerpt": payload.get("supplied_excerpt"),
        "snapshot_json": payload.get("snapshot_json") or {},
    })


def experiment_run_digest(payload: dict[str, Any], evidence_digests: list[str]) -> str:
    return sha256_digest({
        "run_id": payload["run_id"],
        "research_question": payload["research_question"],
        "corpus_version": payload.get("corpus_version"),
        "git_commit": payload.get("git_commit"),
        "retrieval_config_json": payload.get("retrieval_config_json") or {},
        "model_parameters_json": payload.get("model_parameters_json") or {},
        "structured_response_json": payload.get("structured_response_json") or {},
        "provenance_validation_json": payload.get("provenance_validation_json") or {},
        "status": payload["status"],
        "evidence_sha256": evidence_digests,
    })