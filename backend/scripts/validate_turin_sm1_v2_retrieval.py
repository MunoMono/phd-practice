#!/usr/bin/env python3
"""Read-only SM1-v2 retrieval validation; no Granite invocation or persistence."""

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
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "SM1-v2"
QUESTION_ID = "SM1"
CORPUS_VERSION = "corpus_f40d78dbce52"


def main() -> None:
    db = LocalSessionLocal()
    try:
        stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
        if stored is None:
            raise RuntimeError("SM1-v2 is not registered.")
        plan = RetrievalPlan.model_validate(stored.plan_json)
        research_case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        if (
            plan.question_id != QUESTION_ID
            or plan.top_k != 6
            or plan.run_classification != "primary"
            or plan.retrieval_scope != "corpus_wide"
            or plan.supersedes_plan_id != "SM1-v1"
        ):
            raise RuntimeError("SM1-v2 does not match its governed retrieval identity.")
        retrieval = RetrievalValidationService().retrieve(
            db,
            RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION, retrieval_plan=plan),
        )
        counts = {stratum: sum(item.get("stratum") == stratum for item in retrieval["results"]) for stratum in ("contemporary", "retrospective")}
        if counts != {"contemporary": 3, "retrospective": 3}:
            raise RuntimeError(f"SM1-v2 allocation differs from governed 3/3 target: {counts}")
        if not all(item["archive_resolution_status"] == "archive_resolved_current" for item in retrieval["results"]):
            raise RuntimeError("SM1-v2 retrieval contains unresolved evidence.")
        if retrieval["corpus_versions"] != [CORPUS_VERSION]:
            raise RuntimeError("SM1-v2 retrieval escaped the frozen corpus.")
        print(json.dumps({
            "dry_run_only": True,
            "formal_research_inference": False,
            "persistence": False,
            "plan_id": plan.plan_id,
            "lexical_formulation": retrieval["transparency"]["lexical_formulation"],
            "stratum_lexical_formulations": retrieval["transparency"]["temporal_stratum_lexical_formulations"],
            "temporal_strata": retrieval["transparency"]["temporal_strata"],
            "corpus_versions": retrieval["corpus_versions"],
            "results": [{key: item.get(key) for key in ("rank", "stratum", "within_stratum_rank", "score", "title", "catalogue_metadata", "pid", "page_start", "chunk_id", "archive_resolution_status")} for item in retrieval["results"]],
        }, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()