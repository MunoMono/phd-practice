#!/usr/bin/env python3
"""Persist a read-only archive-first documentary evidence review for Q01-Q12."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.services.turin_archive_first_retrieval_service import (
    ARCHIVE_ASSET_SNAPSHOT_VERSION,
    TurinArchiveFirstRetrievalService,
)
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


FROZEN_CORPUS_VERSION = "corpus_f40d78dbce52"
SUCCESSOR_CORPUS_VERSION = "corpus_turin_archive_first_cc11e8678168"
QUESTION_IDS = (
    ("Q01", "KR1"), ("Q02", "KR2"), ("Q03", "KR3"), ("Q04", "KR4"),
    ("Q05", "CI1"), ("Q06", "CI2"), ("Q07", "CI3"), ("Q08", "CI4"),
    ("Q09", "SM1"), ("Q10", "SM2"), ("Q11", "SM3"), ("Q12", "SM4"),
)
OUTPUT_DIR = BACKEND_ROOT / "artifacts"
TOP_K = 40
Q02_KEY_ASSET_PIDS = ("062054716175", "852120727979", "723660822664")


def _excerpt(value: str, limit: int = 360) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[:limit].rsplit(' ', 1)[0]}..."


def _passage_classification(result: dict[str, Any], case: str, question: str) -> str:
    """Classify textual relevance only; never turn archive metadata into evidence."""
    text = str(result["text"]).lower()
    question_words = {
        word for word in re.findall(r"[a-z]+", question.lower())
        if len(word) > 3 and word not in {"across", "aspects", "directly", "documents", "rather", "represented", "students", "what"}
    }
    documentary_matches = sum(word in text for word in question_words)
    activity_terms = {"assessment", "course", "lecture", "learning", "seminar", "student", "teaching", "training", "tutorial"}
    concrete_activity = any(term in text for term in activity_terms)
    if not text.strip():
        return "NO_RELEVANT_PASSAGE"
    if documentary_matches >= 2 and concrete_activity:
        return "DIRECT_SUPPORT" if case == "known_relationship" else "PARTIAL_SUPPORT"
    if documentary_matches >= 1 or concrete_activity:
        return "PARTIAL_SUPPORT"
    return "CONTEXTUAL"


def _selected_passages(retrieval: dict[str, Any], case: str, question: str) -> list[dict[str, Any]]:
    return [{
        "asset_pid": result.get("asset_pid") or result["archive_nomination"].get("asset_pid"),
        "asset_id": result.get("asset_id") or result["archive_nomination"].get("asset_id"),
        "source_identity": result["title"],
        "document_id": result["document_id"],
        "page": result["page_start"],
        "classification": _passage_classification(result, case, question),
        "passage_excerpt": _excerpt(result["text"]),
        "documentary_claim": f"The selected passage states: {_excerpt(result['text'], 220)}",
        "archive_nomination_reasons": result["archive_nomination"]["nomination_reasons"],
    } for result in retrieval["results"]]


def _missingness(retrieval: dict[str, Any], case: str) -> tuple[str, str]:
    if retrieval["corpus_representation_gaps"]:
        return "CORPUS_REPRESENTATION_GAP", "At least one ML-eligible archive-nominated asset has no successor-corpus representation."
    if not retrieval["results"]:
        return "RETRIEVAL_FAILURE", "Archive nomination found eligible material, but no permitted documentary passage was selected."
    if case == "scoped_missingness":
        return "DOCUMENTARY_INSUFFICIENCY", "The selected passages are bounded documentary traces and do not, by retrieval alone, establish a complete causal, origin, reception, or role account."
    return "NONE", "No representation or passage-selection absence was observed among the retained archive-nominated evidence."


def _comparison(frozen: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    frozen_assets = {item.get("asset_pid") or item.get("asset_id") for item in frozen["results"]}
    successor_assets = {item.get("asset_pid") or item.get("asset_id") for item in successor["results"]}
    newly_surfaced = sorted(successor_assets - frozen_assets)
    removed = sorted(frozen_assets - successor_assets)
    return {
        "newly_surfaced_documentary_assets": newly_surfaced,
        "historical_only_documentary_assets": removed,
        "meaningful_difference": (
            "new documentary evidence surfaced" if newly_surfaced else
            "successor evidence surface is unchanged for selected passages"
        ),
        "frozen_result_count": len(frozen["results"]),
        "successor_result_count": len(successor["results"]),
        "frozen_representation_gaps": len(frozen["corpus_representation_gaps"]),
        "successor_representation_gaps": len(successor["corpus_representation_gaps"]),
    }


def _q02_acceptance(db: Any, passages: list[dict[str, Any]]) -> dict[str, Any]:
    rows = db.execute(text("""
        SELECT d.asset_pid, dc.source_page, dc.chunk_text
        FROM document_chunks dc JOIN documents d USING(document_id)
        WHERE dc.corpus_version = :corpus_version
          AND d.asset_pid = ANY(:asset_pids)
        ORDER BY d.asset_pid, dc.source_page, dc.chunk_index
    """), {"corpus_version": SUCCESSOR_CORPUS_VERSION, "asset_pids": list(Q02_KEY_ASSET_PIDS)}).mappings().all()
    direct_terms = {"assessment", "course", "lecture", "seminar", "student", "training", "tutorial"}
    by_asset: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_text = str(row["chunk_text"])
        lower = source_text.lower()
        if "archer" in lower and any(term in lower for term in direct_terms):
            by_asset.setdefault(row["asset_pid"], {"page": row["source_page"], "passage": _excerpt(source_text)})
    key_assets = {
        asset_pid: {
            "nominated": any(passage["asset_pid"] == asset_pid for passage in passages),
            "passage_classification": "DIRECT_SUPPORT" if asset_pid in by_asset else "NO_RELEVANT_PASSAGE",
            "page": by_asset.get(asset_pid, {}).get("page"),
            "documentary_passage": by_asset.get(asset_pid, {}).get("passage"),
        }
        for asset_pid in Q02_KEY_ASSET_PIDS
    }
    classifications = [entry["passage_classification"] for entry in key_assets.values()]
    assessment = "YES" if all(value == "DIRECT_SUPPORT" for value in classifications) else "PARTIAL" if any(value == "DIRECT_SUPPORT" for value in classifications) else "NO"
    return {
        "documentary_assessment": assessment,
        "key_assets": key_assets,
        "directly_evidenced": "Only selected passage wording is treated as direct evidence; archive metadata supplies nomination only.",
        "only_inferred": "Any broader account of Archer's teaching role across the source set remains an interpretation, not a retrieval result.",
        "remaining_unknown": "The retained passages do not by themselves establish a complete account of pedagogical practice, student experience, or outcomes.",
    }


def _review_question(service: TurinArchiveFirstRetrievalService, db: Any, display_id: str, register_id: str) -> dict[str, Any]:
    research_case, question = TURIN_QUESTION_REGISTER[register_id]
    successor = service.retrieve(db, question, TOP_K, SUCCESSOR_CORPUS_VERSION)
    frozen = service.retrieve(db, question, TOP_K, FROZEN_CORPUS_VERSION)
    passages = _selected_passages(successor, research_case, question)
    missingness, missingness_reason = _missingness(successor, research_case)
    review = {
        "question_id": display_id,
        "registered_question_id": register_id,
        "exact_registered_question": question,
        "research_dimensions_exercised": [research_case],
        "archival_relationships_used": successor["transparency"],
        "archive_nominated_assets": successor["archival_discovery"],
        "selected_documentary_passages": passages,
        "directly_evidenced_claims": [item["documentary_claim"] for item in passages if item["classification"] == "DIRECT_SUPPORT"],
        "contested_cross_source_interpretive_potential": (
            "Retained passages are preserved as separate documentary statements; this retrieval-only review does not reconcile them."
            if research_case == "contested_interpretation" else "No interpretive reconciliation was performed in this retrieval-only review."
        ),
        "scoped_missingness": {"classification": missingness, "reason": missingness_reason},
        "comparison_to_historical_control": _comparison(frozen, successor),
        "successor_diagnostics": successor["diagnostics"],
    }
    if display_id == "Q02":
        review["q02_acceptance"] = _q02_acceptance(db, passages)
    return review


def _markdown(artifact: dict[str, Any]) -> str:
    lines = [
        "# Turin Archive-First Q01-Q12 Retrieval Review",
        "",
        f"- Successor corpus: `{SUCCESSOR_CORPUS_VERSION}`",
        f"- Archive snapshot: `{ARCHIVE_ASSET_SNAPSHOT_VERSION}`",
        f"- Run timestamp: `{artifact['run_timestamp_utc']}`",
        "- Qwen calls: `0`",
        "- Formal Qwen run records: `0`",
        "",
        "This is a read-only evidence review. Archive metadata nominates sources; only the selected Docling passages are classified as documentary evidence.",
    ]
    for review in artifact["questions"]:
        lines.extend(["", f"## {review['question_id']} ({review['registered_question_id']})", "", review["exact_registered_question"], "", f"Research dimension: `{', '.join(review['research_dimensions_exercised'])}`", "", "### Nominated assets"])
        for asset in review["archive_nominated_assets"][:12]:
            lines.append(f"- `{asset['asset_pid']}` {asset['label']} ({asset['availability']['classification']})")
        lines.extend(["", "### Selected documentary passages"])
        for passage in review["selected_documentary_passages"]:
            lines.append(f"- `{passage['asset_pid']}` p. {passage['page']} [{passage['classification']}]: {passage['passage_excerpt']}")
        if review["question_id"] == "Q02":
            lines.extend(["", "### Q02 documentary assessment", f"`{review['q02_acceptance']['documentary_assessment']}`"])
            for asset_pid, detail in review["q02_acceptance"]["key_assets"].items():
                lines.append(f"- `{asset_pid}` nominated: `{detail['nominated']}`; passage classification: `{detail['passage_classification']}`")
        lines.extend([
            "", "### Scoped missingness",
            f"`{review['scoped_missingness']['classification']}`: {review['scoped_missingness']['reason']}",
            "", "### Historical-control comparison",
            review["comparison_to_historical_control"]["meaningful_difference"],
        ])
    return "\n".join(lines) + "\n"


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    database = LocalSessionLocal()
    try:
        service = TurinArchiveFirstRetrievalService()
        questions = [_review_question(service, database, display_id, register_id) for display_id, register_id in QUESTION_IDS]
    finally:
        database.close()
    artifact = {
        "artifact_version": "turin-archive-first-q01-q12-retrieval-review-v1",
        "run_timestamp_utc": timestamp,
        "successor_corpus_version": SUCCESSOR_CORPUS_VERSION,
        "historical_control_corpus_version": FROZEN_CORPUS_VERSION,
        "archive_snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION,
        "qwen_calls": 0,
        "formal_qwen_run_records": 0,
        "questions": questions,
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"turin_archive_first_q01_q12_retrieval_review_{stamp}.json"
    markdown_path = OUTPUT_DIR / f"turin_archive_first_q01_q12_retrieval_review_{stamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(artifact), encoding="utf-8")
    print(json.dumps({"json_artifact": str(json_path), "markdown_artifact": str(markdown_path), "questions": len(questions), "qwen_calls": 0}, indent=2))


if __name__ == "__main__":
    main()