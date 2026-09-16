#!/usr/bin/env python3
"""Run every configured archival benchmark question against an interrogation API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.archival_benchmark_policy import load_question_policies
from app.services.benchmark_evaluation_service import evaluate_benchmark_artifact, render_evaluation_matrix

DEFAULT_CONFIG = BACKEND_ROOT / "config" / "benchmark_questions" / "turin-v1.json"


def evaluator_artifact(response: dict[str, Any]) -> dict[str, Any]:
    """Normalize the public interrogation projection into evaluator input."""
    direct_claims = list(response.get("documentary_evidence") or [])
    final_claims = [
        {
            "source_id": claim.get("source_id"),
            "claim": claim.get("claim"),
            "evidence": [{
                "chunk_id": (claim.get("chunk_ids") or [None])[0],
                "page": claim.get("page"),
                "quotation_or_paraphrase": (claim.get("quotations") or [""])[0],
            }],
        }
        for claim in direct_claims
    ]
    provenance = response.get("provenance_validation") or {}
    return {
        "evidence_map": {
            "DIRECT_DOCUMENTARY": direct_claims,
            "ARCHIVAL_METADATA": response.get("archival_associations") or [],
            "DATABASE_AUTHORITY": response.get("authority_evidence") or [],
            "NOT_ESTABLISHED": [item.get("explanation", "") for item in response.get("missingness") or []],
            "source_classifications": response.get("source_classifications") or [],
        },
        "final_synthesis": {
            "direct_documentary_claims": final_claims,
            "cross_source_inferences": [item.get("inference", "") for item in response.get("inferences") or []],
            "answer": response.get("answer", ""),
        },
        "cross_source_analysis": {"cross_source_inferences": []},
        "provenance": {
            "source_analyses": provenance.get("source_analyses") or {},
            "final_synthesis": provenance.get("final_synthesis") or {},
        },
        "retrieval_diagnostics": response.get("retrieval_diagnostics") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Interrogation endpoint URL")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-artifacts", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-matrix", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--retries", type=int, default=10, help="Retries per transient request failure")
    parser.add_argument("--retry-delay", type=int, default=15, help="Seconds to wait between transient request retries")
    arguments = parser.parse_args()

    specification = json.loads(arguments.config.read_text())
    policies = load_question_policies(arguments.config)
    artifacts: dict[str, dict[str, Any]] = {}
    results = []
    for policy, question in zip(policies, specification["questions"], strict=True):
        try:
            for attempt in range(arguments.retries + 1):
                try:
                    response = requests.post(arguments.url, json={"query": question["question"], "mode": "exploratory"}, timeout=arguments.timeout)
                    response.raise_for_status()
                    artifact = evaluator_artifact(response.json())
                    break
                except (requests.RequestException, ValueError) as exc:
                    if attempt == arguments.retries:
                        raise
                    time.sleep(arguments.retry_delay)
        except (requests.RequestException, ValueError) as exc:
            artifact = {"evidence_map": {}, "final_synthesis": {"answer": f"Smoke-run failure: {exc}"}, "provenance": {}}
        artifacts[policy.policy_id] = artifact
        results.append(evaluate_benchmark_artifact(policy, artifact))

    arguments.output_artifacts.write_text(json.dumps(artifacts, indent=2) + "\n")
    arguments.output_json.write_text(json.dumps({
        "schema_version": specification["schema_version"],
        "collection_id": specification.get("collection_id"),
        "corpus_version": specification.get("corpus_version"),
        "results": results,
    }, indent=2) + "\n")
    arguments.output_matrix.write_text(render_evaluation_matrix(results))
    return 0 if all(result["valid"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
