#!/usr/bin/env python3
"""Record frozen-corpus FTS diagnostics and one immutable Turin commissioning run."""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import QueryExpansion, RetrievalValidationRequest, RetrievalValidationService


CORPUS_VERSION = "corpus_f40d78dbce52"
QUESTION = "What relationship does the supplied archival evidence establish between Bruce Archer and design education?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-run-id", help="Serialize an existing immutable run without invoking Granite.")
    parser.add_argument("--context-budget", type=int, default=6000, help="Deterministic Granite input budget; must not exceed the runtime maximum.")
    parser.add_argument("--output", type=Path, default=Path("/artifacts/turin-phase2a/full-corpus-commissioning.json"))
    return parser.parse_args()


def request(query: str, *, expansions: list[QueryExpansion] | None = None) -> RetrievalValidationRequest:
    return RetrievalValidationRequest(query=query, top_k=5, corpus_version=CORPUS_VERSION, expansions=expansions or [])


async def main() -> None:
    args = parse_args()
    db = LocalSessionLocal()
    try:
        retrieval_service = RetrievalValidationService()
        diagnostics = [
            ("known_person", request("Bruce Archer")),
            ("known_topic", request("design research")),
            ("terminology", request("industrial design education")),
            ("multi_document", request("computer aided design")),
            ("restricted_page", request("Bruce Archer")),
            ("controlled_lexical_expansion", request("design education", expansions=[QueryExpansion(value="computer", source="researcher_supplied")])),
            ("sparse_result", request("xylophonic counterfactual nomenclature")),
        ]
        retrieval_records = [{"kind": kind, "result": retrieval_service.retrieve(db, value)} for kind, value in diagnostics]
        if args.export_run_id:
            reloaded = db.query(ExperimentRun).filter(ExperimentRun.run_id == args.export_run_id).one()
            reload_verified = True
        else:
            granite = get_granite_service()
            if not granite.get_load_status()["model_ready"]:
                granite.load_model()
            service = ExperimentRunService(retrieval_service=retrieval_service, granite_service=granite)
            run = await service.run_archival_experiment(
                db,
                ExperimentRunRequest(
                    research_case="known_relationship",
                    research_question=QUESTION,
                    retrieval=request("Bruce Archer design education"),
                    context_budget=args.context_budget,
                    context_mode="document_only",
                    fixture_only=False,
                ),
            )
            reloaded = db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one()
            reload_verified = reloaded.raw_model_response == run.raw_model_response
        output = {
            "classification": "FIRST FULL-CORPUS TURIN RESEARCH-INSTRUMENT RUN",
            "corpus_version": CORPUS_VERSION,
            "fts_diagnostics": retrieval_records,
            "run": serialize_run(reloaded),
            "reload_verified": reload_verified,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())