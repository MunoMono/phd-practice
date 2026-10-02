"""Durable diagnostic snapshots for isolated final-synthesis replay."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_SCHEMA_VERSION = "turin-final-synthesis-stage-snapshot-v1"
FINAL_PROMPT_CONTRACT_VERSION = "turin-final-synthesis-inline-v1"
_REQUIRED_SNAPSHOT_FIELDS = {
    "snapshot_schema_version", "run_id", "uat_id", "question", "route", "corpus",
    "lineage", "authority", "source_analyses", "evidence_map", "cross_source_analysis",
    "final_synthesis", "final_prompt", "final_prompt_sha256", "input_payload_sha256",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _snapshot_directory() -> Path:
    return Path(os.getenv("TURIN_FINAL_SYNTHESIS_SNAPSHOT_DIR", "/app/artifacts/ml_triage_recovery"))


def _snapshot_path(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Diagnostic snapshot run_id contains unsupported characters.")
    return _snapshot_directory() / f"hyb01-stage-snapshot-{run_id}.json"


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, ensure_ascii=True)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def write_pre_final_snapshot(
    metadata: Mapping[str, Any],
    *,
    question: str,
    source_analyses: list[dict[str, Any]],
    evidence_map: Mapping[str, Any],
    cross_source_analysis: Mapping[str, Any],
    final_prompt: str,
    final_schema: Mapping[str, Any],
    final_configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Write the exact validated state available immediately before final synthesis."""
    run_id = str(metadata["run_id"])
    payload = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "uat_id": metadata.get("uat_id"),
        "question": question,
        "route": metadata["route"],
        "corpus": dict(metadata["corpus"]),
        "lineage": dict(metadata["lineage"]),
        "authority": {
            "resolved_authority_records": list(metadata.get("resolved_authority_records") or []),
            "authority_context_passed_to_final": list(metadata.get("authority_context_passed_to_final") or []),
        },
        "source_analyses": source_analyses,
        "evidence_map": dict(evidence_map),
        "cross_source_analysis": dict(cross_source_analysis),
        "final_synthesis": {
            "prompt_contract_version": FINAL_PROMPT_CONTRACT_VERSION,
            "schema": dict(final_schema),
            "schema_sha256": _sha256(final_schema),
            "configuration": dict(final_configuration),
            "outcome": None,
        },
        "final_prompt": final_prompt,
        "final_prompt_sha256": _sha256(final_prompt),
        "input_payload_sha256": _sha256({
            "question": question,
            "evidence_map": evidence_map,
            "cross_source_analysis": cross_source_analysis,
            "final_configuration": final_configuration,
        }),
    }
    path = _snapshot_path(run_id)
    _atomic_write(path, payload)
    return {"path": str(path), "input_payload_sha256": payload["input_payload_sha256"], "final_prompt_sha256": payload["final_prompt_sha256"]}


def append_final_outcome(snapshot: Mapping[str, Any], outcome: Mapping[str, Any]) -> None:
    """Atomically append safe final-stage execution diagnostics to a prior snapshot."""
    path = Path(str(snapshot["path"]))
    payload = load_final_synthesis_snapshot(path)
    payload["final_synthesis"]["outcome"] = dict(outcome)
    _atomic_write(path, payload)


def load_final_synthesis_snapshot(path: Path) -> dict[str, Any]:
    """Load a replay snapshot strictly; absent fields are never inferred."""
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict) or payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Unsupported final-synthesis diagnostic snapshot.")
    missing = sorted(_REQUIRED_SNAPSHOT_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"Final-synthesis snapshot is missing required fields: {', '.join(missing)}")
    if _sha256(payload["final_prompt"]) != payload["final_prompt_sha256"]:
        raise ValueError("Final-synthesis snapshot prompt hash does not match its payload.")
    expected_input_hash = _sha256({
        "question": payload["question"],
        "evidence_map": payload["evidence_map"],
        "cross_source_analysis": payload["cross_source_analysis"],
        "final_configuration": payload["final_synthesis"]["configuration"],
    })
    if expected_input_hash != payload["input_payload_sha256"]:
        raise ValueError("Final-synthesis snapshot input hash does not match its payload.")
    return payload