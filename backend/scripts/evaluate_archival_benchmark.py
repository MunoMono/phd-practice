#!/usr/bin/env python3
"""Evaluate saved pipeline artifacts against a versioned benchmark specification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.benchmark_evaluation_service import evaluate_benchmark_artifact, render_evaluation_matrix
from app.services.archival_benchmark_policy import load_question_policies


DEFAULT_CONFIG = BACKEND_ROOT / "config" / "benchmark_questions" / "turin-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path, help="JSON file mapping policy IDs to pipeline artifacts")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Versioned benchmark question configuration")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-matrix", type=Path, required=True)
    arguments = parser.parse_args()

    artifacts = json.loads(arguments.artifacts.read_text())
    specification = json.loads(arguments.config.read_text())
    policies = {policy.policy_id: policy for policy in load_question_policies(arguments.config)}
    unknown_policy_ids = sorted(set(artifacts).difference(policies))
    if unknown_policy_ids:
        parser.error(f"Artifacts include unknown policy IDs: {', '.join(unknown_policy_ids)}")
    results = [
        evaluate_benchmark_artifact(policies[policy_id], artifact)
        for policy_id, artifact in artifacts.items()
    ]
    arguments.output_json.write_text(json.dumps({
        "schema_version": specification["schema_version"],
        "collection_id": specification.get("collection_id"),
        "corpus_version": specification.get("corpus_version"),
        "config_path": str(arguments.config),
        "results": results,
    }, indent=2) + "\n")
    arguments.output_matrix.write_text(render_evaluation_matrix(results))
    return 0 if all(result["valid"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
