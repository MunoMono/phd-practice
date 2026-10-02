#!/usr/bin/env python3
"""Execute or replay the ML-triage development set and persist auditable traces."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.query_execution_trace import (  # noqa: E402
    ExecutionOutcome,
    build_query_error_trace,
    build_query_execution_trace,
)


DEFAULT_CSV = REPO_ROOT / "docs" / "ml_triage_dev_v2" / "clean_ml_triage_dev_UAT_50_v2.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "ml_triage_dev_v2" / "uat_runs"


def load_cases(csv_path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        cases = list(csv.DictReader(source))
    required = {"uat_id", "question", "question_class", "uat_pass_fail"}
    missing = required - set(cases[0] if cases else {})
    if missing:
        raise ValueError(f"Baseline CSV is missing required columns: {sorted(missing)}")
    identifiers = [case["uat_id"] for case in cases]
    if len(cases) != 50 or len(set(identifiers)) != 50:
        raise ValueError("Baseline CSV must contain exactly 50 uniquely identified cases.")
    statuses = Counter((case.get("uat_pass_fail") or "").strip().upper() or "UNRESOLVED_BLANK" for case in cases)
    baseline = {
        "total": len(cases),
        "pass": statuses["PASS"],
        "fail": statuses["FAIL"],
        "unresolved_blank": statuses["UNRESOLVED_BLANK"],
    }
    if baseline != {"total": 50, "pass": 2, "fail": 47, "unresolved_blank": 1}:
        raise ValueError(f"Unexpected baseline distribution: {baseline}")
    return cases, baseline


def request_query(base_url: str, case: dict[str, str], top_k: int, timeout: float) -> dict[str, Any]:
    payload = {
        "query": case["question"],
        "question_id": case["uat_id"],
        "top_k": top_k,
        "mode": "exploratory",
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/analysis/interrogate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def replay_query(replay_dir: Path, case_id: str) -> dict[str, Any]:
    candidates = (replay_dir / f"{case_id}.response.json", replay_dir / f"{case_id}.json")
    replay_path = next((path for path in candidates if path.is_file()), None)
    if replay_path is None:
        raise FileNotFoundError(f"No replay response found for {case_id}")
    return json.loads(replay_path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    cases, baseline = load_cases(arguments.csv)
    if arguments.case_ids:
        requested = set(arguments.case_ids)
        cases = [case for case in cases if case["uat_id"] in requested]
        unknown = requested - {case["uat_id"] for case in cases}
        if unknown:
            raise ValueError(f"Unknown case IDs: {sorted(unknown)}")

    harness_run_id = f"ml-triage-v2-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = arguments.output_root / harness_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "trace_schema": "ml-triage-dev-v2-run-v1",
        "run_id": harness_run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "replay" if arguments.replay_dir else "execute",
        "baseline": baseline,
        "requested_case_count": len(cases),
        "cases": [],
    }
    write_json(run_dir / "manifest.json", manifest)

    for case in cases:
        case_id = case["uat_id"]
        try:
            response = (
                replay_query(arguments.replay_dir, case_id)
                if arguments.replay_dir
                else request_query(arguments.base_url, case, arguments.top_k, arguments.timeout)
            )
            trace = build_query_execution_trace(
                response,
                external_test_id=case_id,
                question_text=case["question"],
                question_classification=case["question_class"],
            )
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as error:
            outcome = (
                ExecutionOutcome.RETRIEVAL_COVERAGE_ERROR
                if isinstance(error, urllib.error.HTTPError) and error.code == 404
                else ExecutionOutcome.SYNTHESIS_VALIDATION_ERROR
            )
            trace = build_query_error_trace(
                run_id=f"{harness_run_id}:{case_id}",
                external_test_id=case_id,
                question_text=case["question"],
                question_classification=case["question_class"],
                error=f"{type(error).__name__}: {error}",
                outcome=outcome,
            )
        trace["harness_run_id"] = harness_run_id
        write_json(run_dir / f"{case_id}.json", trace)
        manifest["cases"].append({
            "uat_id": case_id,
            "execution_outcome": trace["execution_outcome"],
            "trace_file": f"{case_id}.json",
        })
        write_json(run_dir / "manifest.json", manifest)

    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["outcome_counts"] = dict(Counter(item["execution_outcome"] for item in manifest["cases"]))
    write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_id": harness_run_id, "run_dir": str(run_dir), **manifest["outcome_counts"]}, sort_keys=True))
    error_outcomes = {
        ExecutionOutcome.SYNTHESIS_VALIDATION_ERROR.value,
        ExecutionOutcome.RETRIEVAL_COVERAGE_ERROR.value,
    }
    return 1 if any(item["execution_outcome"] in error_outcomes for item in manifest["cases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())