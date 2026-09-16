#!/usr/bin/env python3
"""Stress-test claim-adjacent Source Interrogation citations against live inventory."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://innovationdesign.io"
DEFAULT_SEED = 20260911
AUTHORITY_PEOPLE = [
    "Bruce Archer", "Ken Baynes", "Phil Roberts", "Eileen Adams", "Kenneth Agnew",
    "Richard Langdon", "Janet Daley", "Pierre Goumain", "John Wood", "George Mallen",
    "Christopher Frayling", "Anthony Finkelstein", "Brian Reffin Smith", "Henrietta Ryott",
]


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 90) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


def build_questions(documents: list[dict[str, Any]], seed: int) -> list[dict[str, str]]:
    usable_documents = [
        document for document in documents
        if document.get("document_id") and document.get("title")
    ]
    if len(usable_documents) < 109:
        raise ValueError("The archive inventory did not return enough titled documents for the 300-question stress sample")

    archive_questions = []
    for document in usable_documents:
        title = " ".join(str(document["title"]).split())
        archive_questions.extend([
            {"evidence_type": "archive", "question": f"What documents mention {title}?"},
            {"evidence_type": "archive", "question": f"Which archival records are relevant to {title}?"},
        ])

    job_numbers = []
    for document in usable_documents:
        job_numbers.extend(re.findall(r"\bJob\s+(\d+)\b", str(document["title"]), flags=re.IGNORECASE))
    job_numbers = list(dict.fromkeys(job_numbers))
    authority_templates = [
        "What projects did {person} work on?",
        "What role did {person} hold?",
        "When did {person} work at DDR?",
        "Which DDR records identify {person}?",
        "What employment details are recorded for {person}?",
        "What connections does the authority database record for {person}?",
    ]
    authority_questions = [
        {"evidence_type": "authority", "question": template.format(person=person)}
        for person in AUTHORITY_PEOPLE
        for template in authority_templates
    ]
    authority_questions.extend(
        {"evidence_type": "authority", "question": f"What is Job {job_number}?"}
        for job_number in job_numbers
    )

    randomizer = random.Random(seed)
    randomizer.shuffle(archive_questions)
    randomizer.shuffle(authority_questions)
    selected = archive_questions[:218] + authority_questions[:82]
    if len(selected) != 300:
        raise ValueError(f"Expected 300 questions, generated {len(selected)}")
    randomizer.shuffle(selected)
    return [
        {"number": index, **question}
        for index, question in enumerate(selected, start=1)
    ]


def validate_citations(result: dict[str, Any]) -> list[str]:
    answer = str(result.get("answer") or "").strip()
    paragraphs = result.get("answer_paragraphs") or []
    source_count = len(result.get("retrieved_evidence") or [])
    authority_count = len(result.get("authority_evidence") or [])
    errors = []

    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        for claim_index, claim in enumerate(paragraph.get("claims") or [], start=1):
            if not str(claim.get("text") or "").strip():
                errors.append(f"paragraph {paragraph_index} claim {claim_index} has no text")
                continue
            source_numbers = claim.get("source_numbers") or claim.get("sourceNumbers") or []
            authority_numbers = claim.get("authority_numbers") or claim.get("authorityNumbers") or []
            if not source_numbers and not authority_numbers:
                errors.append(f"paragraph {paragraph_index} claim {claim_index} has no citation")
            if any(not isinstance(number, int) or number < 1 or number > source_count for number in source_numbers):
                errors.append(f"paragraph {paragraph_index} claim {claim_index} has invalid source number")
            if any(not isinstance(number, int) or number < 1 or number > authority_count for number in authority_numbers):
                errors.append(f"paragraph {paragraph_index} claim {claim_index} has invalid authority number")

    has_inline_source_citation = bool(re.search(r"\[\d+(?:\s*,\s*\d+)*\]", answer))
    has_structured_citation = any(
        (claim.get("source_numbers") or claim.get("sourceNumbers") or claim.get("authority_numbers") or claim.get("authorityNumbers"))
        for paragraph in paragraphs
        for claim in (paragraph.get("claims") or [])
    )
    requires_citation = bool(answer) and (source_count > 0 or authority_count > 0)
    if requires_citation and not (has_structured_citation or has_inline_source_citation):
        errors.append("answer with returned evidence has no claim-adjacent citation")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--output", type=Path, default=Path("artifacts/answer-citation-stress-300.json"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    _, inventory = request_json(f"{args.base_url.rstrip('/')}/api/documents")
    questions = build_questions(inventory.get("documents") or [], args.seed)
    existing = {}
    if args.resume and args.output.exists():
        existing = {
            entry["number"]: entry
            for entry in json.loads(args.output.read_text()).get("results", [])
            if entry.get("http_status") == 200 and not entry.get("citation_errors")
        }

    results = []
    for question in questions[:args.limit]:
        if question["number"] in existing:
            results.append(existing[question["number"]])
            continue
        try:
            status, response = request_json(
                f"{args.base_url.rstrip('/')}/api/analysis/interrogate",
                {"query": question["question"], "top_k": 5, "mode": "exploratory"},
            )
            errors = validate_citations(response)
            result = {
                **question,
                "http_status": status,
                "answer_origin": response.get("answer_origin"),
                "source_count": len(response.get("retrieved_evidence") or []),
                "authority_count": len(response.get("authority_evidence") or []),
                "citation_errors": errors,
            }
        except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as error:
            result = {**question, "http_status": None, "citation_errors": [str(error)]}
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"seed": args.seed, "questions": questions, "results": results}, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        time.sleep(0.15)

    failures = [result for result in results if result["citation_errors"]]
    print(json.dumps({"total": len(results), "failures": len(failures), "output": str(args.output)}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())