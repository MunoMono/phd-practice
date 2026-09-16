"""Read-only V3.16 registered-question retrieval review."""
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import LocalSessionLocal
from app.services.turin_question_register import TURIN_QUESTION_REGISTER
from app.services.turin_retrieval_v3_service import CORPUS_VERSION, TurinRetrievalV3Service
from app.services.turin_retrieval_v316_project_identity_surface import TurinRetrievalV316ProjectIdentitySurface

IDS = (("Q01", "KR1"), ("Q02", "KR2"), ("Q03", "KR3"), ("Q04", "KR4"), ("Q05", "CI1"), ("Q06", "CI2"), ("Q07", "CI3"), ("Q08", "CI4"), ("Q09", "SM1"), ("Q10", "SM2"), ("Q11", "SM3"), ("Q12", "SM4"))

db = LocalSessionLocal()
service = TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2")
reviews = []
try:
    authorities = [dict(row) for row in db.execute(text("SELECT authority_type, authority_id, code, label, metadata FROM database_authorities ORDER BY authority_type, authority_id")).mappings().all()]
    project_identities = [dict(row) for row in db.execute(text("SELECT project_identity_id, project_authority_id, project_job_id, project_title, normalized_project_title, source_of_truth, source_path, archive_record_pid, attached_media_pid, asset_pid, snapshot_version FROM turin_project_identities WHERE snapshot_version = 'turin-project-identity-v1' ORDER BY project_identity_id")).mappings().all()]
    selector = TurinRetrievalV316ProjectIdentitySurface(authorities, project_identities)
    for display_id, question_id in IDS:
        _, question = TURIN_QUESTION_REGISTER[question_id]
        retrieval = service.retrieve(db, question, 5, CORPUS_VERSION)
        selected = selector.build(service.last_passage_candidates, question, retrieval["question_analysis"]["required_facets"])
        review = {"version": "v3.16-read-only", "question_id": display_id, "question": question, "qwen_calls": 0, "formal_runs": 0, "query_anchors": selected["query_anchors"], "source_profiles": [{key: value for key, value in profile.items() if key != "top_passages"} for profile in selected["source_profiles"]], "evidence_bundles": selected["evidence_bundles"], "retrieval_adequacy": selected["retrieval_adequacy"]}
        (ROOT / "artifacts" / f"turin_v316_review_{display_id.lower()}.json").write_text(json.dumps(review, indent=2) + "\n")
        reviews.append(review)
finally:
    db.close()
(ROOT / "artifacts" / "turin_v316_review_all_12.json").write_text(json.dumps(reviews, indent=2) + "\n")
print(json.dumps({"reviews": len(reviews), "qwen_calls": 0, "formal_runs": 0}))
