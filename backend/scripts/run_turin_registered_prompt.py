#!/usr/bin/env python3
"""Run one registered Turin prompt serially and persist one immutable experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import QueryExpansion, RetrievalValidationRequest, RetrievalValidationService

CORPUS_VERSION = "corpus_f40d78dbce52"


@dataclass(frozen=True)
class RegisteredPrompt:
    research_case: str
    question: str
    query: str
    expansions: tuple[str, ...] = ()


PROMPTS = {
    "A1": RegisteredPrompt("known_relationship", "What relationship does the supplied archival evidence establish between Bruce Archer and design education?", "Bruce Archer design education"),
    "A2": RegisteredPrompt("known_relationship", "What relationship does the supplied archival evidence establish between Bruce Archer and the Design Education Unit?", "Bruce Archer Design Education Unit"),
    "B1": RegisteredPrompt("contested_interpretation", "How do the supplied passages characterize the relationship between design research and industrial design education, and where do they differ?", "design research industrial design education"),
    "B2": RegisteredPrompt("contested_interpretation", "What tensions or disagreements concerning computer aided design are present in the supplied archival passages?", "computer aided design"),
    "C1": RegisteredPrompt("scoped_missingness", "What does the retrieved Turin corpus context not establish about the relationship between Bruce Archer and design education?", "Bruce Archer design education"),
    "C2": RegisteredPrompt("scoped_missingness", "What support for the requested relationship is absent from passages returned for industrial design education?", "industrial design education"),
    "V1": RegisteredPrompt("known_relationship", "What relationship does the supplied evidence establish between Archer and design education?", "Archer design education"),
    "V2": RegisteredPrompt("contested_interpretation", "How does controlled entity expansion affect retrieved context for Bruce Archer and design education?", "design education", ("Bruce Archer",)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt_id", choices=sorted(PROMPTS))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--context-budget", type=int, default=4200)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    prompt = PROMPTS[args.prompt_id]
    db = LocalSessionLocal()
    try:
        granite = get_granite_service()
        if not granite.get_load_status()["model_ready"] and not granite.load_model():
            raise RuntimeError(f"Granite runtime could not load: {granite.get_load_status()['last_error']}")
        expansions = [QueryExpansion(value=value, source="researcher_supplied") for value in prompt.expansions]
        request = ExperimentRunRequest(
            research_case=prompt.research_case,
            research_question=prompt.question,
            retrieval=RetrievalValidationRequest(query=prompt.query, top_k=args.top_k, corpus_version=CORPUS_VERSION, expansions=expansions),
            context_budget=args.context_budget,
            context_mode="document_only",
        )
        run = await ExperimentRunService(retrieval_service=RetrievalValidationService(), granite_service=granite).run_archival_experiment(db, request)
        print(json.dumps({"prompt_id": args.prompt_id, "run": serialize_run(run)}, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
