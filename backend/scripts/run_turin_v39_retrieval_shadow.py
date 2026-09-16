#!/usr/bin/env python3
"""Read-only V3.9 retrieval shadow for the twelve registered Turin questions."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import LocalSessionLocal
from app.services.turin_question_register import TURIN_QUESTION_REGISTER
from app.services.turin_retrieval_v3_service import CORPUS_VERSION, TurinRetrievalV3Service
from app.services.turin_retrieval_v39_documentary_anchors import TurinRetrievalV39DocumentaryAnchors

OUTPUT = ROOT / "artifacts"
QUESTION_IDS = (("Q01", "KR1"), ("Q02", "KR2"), ("Q03", "KR3"), ("Q04", "KR4"), ("Q05", "CI1"), ("Q06", "CI2"), ("Q07", "CI3"), ("Q08", "CI4"), ("Q09", "SM1"), ("Q10", "SM2"), ("Q11", "SM3"), ("Q12", "SM4"))


def serialize(bundle: dict) -> dict:
    return {"source": bundle["source"], "archival_context": {key: bundle["source"].get(key) for key in ("canonical_asset_id", "document_id", "archive_record_pid", "attached_media_pid", "asset_pid", "source_family_id", "source_type", "source_nomination")}, "documentary_anchor_passage": bundle["documentary_evidence"][0], "documentary_evidence": bundle["documentary_evidence"], "evidential_limit": bundle["evidential_limit"]}


def main():
    OUTPUT.mkdir(exist_ok=True)
    service = TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2")
    database = LocalSessionLocal()
    shadows = []
    try:
        for display_id, question_id in QUESTION_IDS:
            _, question = TURIN_QUESTION_REGISTER[question_id]
            result = service.retrieve(database, question, 5, CORPUS_VERSION)
            selection = TurinRetrievalV39DocumentaryAnchors.build(service.last_passage_candidates, question, result["question_analysis"]["required_facets"], 8)
            shadow = {"shadow_version": "turin-v3.9-read-only", "question_id": display_id, "registered_question_id": question_id, "question": question, "corpus_version": CORPUS_VERSION, "qwen_calls": 0, "formal_runs": 0, "nominated_sources": result["canonical_source_ranking"], "source_profiles": [{key: value for key, value in profile.items() if key != "top_passages"} for profile in selection["source_profiles"]], "final_evidence_bundle": [serialize(bundle) for bundle in selection["evidence_bundles"]], "retrieval_adequacy": selection["selection_diagnostics"], "evidential_limits": [bundle["evidential_limit"] for bundle in selection["evidence_bundles"]]}
            (OUTPUT / f"turin_v39_shadow_{display_id.lower()}.json").write_text(json.dumps(shadow, indent=2) + "\n")
            shadows.append(shadow)
    finally:
        database.close()
    (OUTPUT / "turin_v39_shadow_all_12.json").write_text(json.dumps(shadows, indent=2) + "\n")
    print(json.dumps({"shadow_artifacts": len(shadows), "qwen_calls": 0, "formal_runs": 0}, indent=2))


if __name__ == "__main__":
    main()
