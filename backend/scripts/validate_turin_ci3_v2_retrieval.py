#!/usr/bin/env python3
"""Dry-run CI3-v2 retrieval and context representation without Granite or persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import TurinRetrievalPlan
from app.services.retrieval_protocol import RetrievalPlan
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService
from app.services.turin_experiment_service import ContextBuilder
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "CI3-v2"
QUESTION_ID = "CI3"
CORPUS_VERSION = "corpus_f40d78dbce52"


def main() -> None:
    db = LocalSessionLocal()
    try:
        stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
        if stored is None:
            raise RuntimeError("CI3-v2 is not registered.")
        plan = RetrievalPlan.model_validate(stored.plan_json)
        research_case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        if plan.question_id != QUESTION_ID or plan.top_k != 6 or plan.run_classification != "protocol_revision":
            raise RuntimeError("CI3-v2 does not match its governed retrieval identity.")
        retrieval = RetrievalValidationService().retrieve(
            db,
            RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION, retrieval_plan=plan),
        )
        counts = {stratum: sum(item.get("stratum") == stratum for item in retrieval["results"]) for stratum in ("contemporary", "retrospective")}
        if counts != {"contemporary": 4, "retrospective": 2}:
            raise RuntimeError(f"CI3-v2 allocation differs from governed 4/2 target: {counts}")
        context = ContextBuilder().assemble_for_prompt(research_case, question, retrieval["results"], input_budget=6000)
        if context.document_chunk_count != 6 or context.omitted_chunk_ids or not all(item["included_in_context"] and item["supplied_chars"] > 0 for item in context.evidence_decisions):
            raise RuntimeError("CI3-v2 context did not represent every retrieved source directly.")
        if context.assembled_input_chars is None or context.assembled_input_chars > 6000:
            raise RuntimeError("CI3-v2 prompt exceeds the 6000-character ceiling.")
        print(json.dumps({
            "dry_run_only": True,
            "formal_research_inference": False,
            "persistence": False,
            "plan_id": plan.plan_id,
            "lexical_formulation": retrieval["transparency"]["lexical_formulation"],
            "temporal_strata": retrieval["transparency"]["temporal_strata"],
            "results": [{key: item.get(key) for key in ("stratum", "within_stratum_rank", "rank", "title", "pid", "score", "catalogue_metadata", "temporal_classification", "temporal_classification_basis")} for item in retrieval["results"]],
            "context": context.model_dump(),
        }, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()