#!/usr/bin/env python3
"""Validate v1.1 fixed-evidence prompts without contacting Qwen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_archive_first_qwen_protocol_v11 import OUTPUT_TOKEN_LIMIT, PROTOCOL_VERSION, build_compact_prompt


REVIEW_PATH = BACKEND_ROOT / "artifacts" / "turin_archive_first_q01_q12_retrieval_review_20260903.json"
OUTPUT_PATH = BACKEND_ROOT / "artifacts" / "turin_archive_first_qwen_evaluation_v11_dry_run_20260903.json"
CONTEXT_WINDOW = 16384


def source_context(question: dict) -> list[dict]:
    nominations = {item["asset_pid"]: item for item in question["archive_nominated_assets"]}
    sources = []
    for index, passage in enumerate(question["selected_documentary_passages"], start=1):
        nomination = nominations.get(passage["asset_pid"], {})
        normalized_date = str(nomination.get("normalized_date") or "")
        year = int(normalized_date[:4]) if normalized_date[:4].isdigit() else None
        sources.append({"source_id": f"S{index}", "title": passage["source_identity"], "date": nomination.get("display_date"), "source_type": nomination.get("source_type"), "temporal_class": "contemporary DDR-era" if year is not None and year <= 1985 else "later/undated", "page": passage["page"], "documentary_passage": passage["passage_excerpt"]})
    return sources


def main() -> None:
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    questions = []
    for question in review["questions"]:
        sources = source_context(question)
        prompt = build_compact_prompt(question["exact_registered_question"], sources)
        input_estimate = (len(prompt) + 3) // 4
        questions.append({"question_id": question["question_id"], "source_count": len(sources), "source_ids_valid": [source["source_id"] for source in sources] == [f"S{index}" for index in range(1, len(sources) + 1)], "prompt_characters": len(prompt), "input_token_estimate": input_estimate, "output_token_limit": OUTPUT_TOKEN_LIMIT, "worst_case_context_tokens": input_estimate + OUTPUT_TOKEN_LIMIT, "within_context_window": input_estimate + OUTPUT_TOKEN_LIMIT <= CONTEXT_WINDOW})
    artifact = {"protocol": PROTOCOL_VERSION, "qwen_calls": 0, "review_artifact": str(REVIEW_PATH), "context_window": CONTEXT_WINDOW, "questions": questions, "worst_case_context_tokens": max(item["worst_case_context_tokens"] for item in questions), "all_source_ids_valid": all(item["source_ids_valid"] for item in questions), "all_within_context_window": all(item["within_context_window"] for item in questions)}
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()