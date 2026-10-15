import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

from app.services.turin_archive_first_retrieval_service import TurinArchiveFirstRetrievalService
from app.services.turin_research_answer_service import (
    _evidence_records, build_documentary_analysis_prompt,
    build_documentary_composition_prompt, generate_documentary_synthesis,
    DocumentaryAnalysis,
)
from tests.test_turin_evidence_pipeline_service import PACKET
from app.services.turin_evidence_pipeline_service import _trim_to_token_budget


def notes():
    return DocumentaryAnalysis(
        propositions=[{"proposition_id": "P1", "statement": "A source establishes a bounded claim",
                       "actor": None, "qualifications": "Conditional", "evidence_ids": ["EV-123"]}],
        relationships=[], unsupported_conclusions=["No common curriculum established"],
    )


def test_context_separates_recorded_employment_from_documentary_attribution():
    authority = [{"source": "database_authorities.agent_employment", "authority_type": "agent_employment",
                  "authority_id": "unchanged-id", "fields": {"name": "A researcher", "start_date": "1972"}}]
    for prompt in (
        build_documentary_analysis_prompt("A hybrid research question", [], authority),
        build_documentary_composition_prompt("A hybrid research question", [], notes(), authority),
    ):
        assert "Royal College of Art Department of Design Research" in prompt
        assert "Do not invent another expansion" in prompt
        assert '"authority_id":"unchanged-id"' in prompt
        assert '"start_date":"1972"' in prompt
        assert "employment is unestablished" in prompt
        assert "does not establish sole authorship" in prompt
        assert "Do not create EV citations for database fields" in prompt


def test_retrospective_neighbor_preserves_other_institution_referent_and_source_bytes():
    packet = deepcopy(PACKET)
    packet.document["title"] = "Interview with a former researcher"
    hit_id = packet.retrieval_match["chunk_id"]
    hit = next(c for c in packet.document_context["ordered_chunks"] if c["chunk_id"] == hit_id)
    hit["text"] = "I moved to another institution later. There were no walls between disciplines, and"
    neighbor = {"chunk_id": "next-testimony-chunk", "chunk_index": 99, "page": 22,
                "text": "only one department in that later institution. This recollection concerns that school."}
    packet.document_context["ordered_chunks"].append(neighbor)
    records = _evidence_records([packet], "How does the recollection compare with contemporary records?")
    context = next(item for item in records if item["chunk_id"] == neighbor["chunk_id"])
    assert context["text"] == neighbor["text"]
    assert context["page"] == 22
    assert context["evidence_role"] == "adjacent_testimony_context"
    assert context["document_id"] == packet.document["document_id"]
    assert any(item["text"] == hit["text"] for item in records)


def test_oral_comparison_selects_computing_account_not_single_mention_in_travel_story():
    rows = [
        {"title": "Interview with a researcher", "chunk_text": "At a later school I recalled a computer at my previous college. " * 2},
        {"title": "Interview with a researcher", "chunk_text": "Computing was used in design research. Computers were available for our art and computing experiments."},
    ]
    rows[0]["chunk_text"] = "I was invited to a later school after a visitor mentioned my computer at the college. " + "The building had thick walls and a fine view. " * 3
    selected = TurinArchiveFirstRetrievalService._requested_task_passages(
        rows, "Compare the oral-history account of computing with institutional descriptions.", hybrid=False,
    )
    assert [r["chunk_text"] for r in selected] == [rows[1]["chunk_text"]]
    assert selected[0]["score"] > 0
    assert selected[0]["task_query_matches"]


def test_broad_research_needs_prefer_substantive_content_without_named_case_constants():
    rows = [
        {"chunk_text": "The project team will conduct a review of research needs. " * 3},
        {"chunk_text": "Complexity is a performance problem. Cognitive understanding and ergonomics require methodological research."},
    ]
    selected = TurinArchiveFirstRetrievalService._requested_task_passages(
        rows, "What do reports identify as research needs?", hybrid=True,
    )
    assert [r["chunk_text"] for r in selected] == [rows[1]["chunk_text"]]
    assert TurinArchiveFirstRetrievalService._requested_task_passages(
        rows, "What do reports identify as research needs and interface problems?", hybrid=False,
    ) == rows


def test_scientific_action_comparison_preserves_conditional_requirements():
    rows = [
        {"chunk_text": "This course covers action research and scientific method. " * 3},
        {"chunk_text": "On those occasions when the research is intended to be objective, its evidence must be independently verifiable and capable of replication."},
    ]
    assert [r["chunk_text"] for r in TurinArchiveFirstRetrievalService._requested_task_passages(
        rows, "Compare scientific method with action research.", hybrid=False,
    )] == [rows[1]["chunk_text"]]
    prompt = build_documentary_composition_prompt(
        "Compare scientific method with action research and measurement.", [], notes(),
    )
    assert "separately evidenced treatments" in prompt
    assert "do not collapse systematic enquiry" in prompt
    assert "first sentence express the documented distinction" in prompt
    assert "where genuinely ambiguous, leave them unresolved" in prompt


def test_conditional_neighbor_survives_existing_packet_budget_without_losing_anchor():
    chunks = [
        {"chunk_id": "anchor", "chunk_index": 2, "text": "Action research suffices for decisions. " * 5},
        {"chunk_id": "peripheral", "chunk_index": 1, "text": "A course lists simulation and design. " * 6},
        {"chunk_id": "conditional", "chunk_index": 0,
         "text": "On those occasions when research is intended to be objective, its evidence must be verifiable and replicable."},
    ]
    selected = _trim_to_token_budget(chunks, "anchor", 90, "Compare scientific method and action research.")
    assert {c["chunk_id"] for c in selected} == {"anchor", "conditional"}
    assert _trim_to_token_budget(chunks, "anchor", 90, "Describe the design course.") == _trim_to_token_budget(chunks, "anchor", 90)


def test_reading_packet_retains_original_condition_even_without_full_facet_term_match():
    packet = deepcopy(PACKET)
    original = "On those occasions when research is intended to be scientific, the enquiry must be objective and independently verifiable."
    packet.document_context["ordered_chunks"].append({
        "chunk_id": "original-condition", "chunk_index": 1, "page": 6, "text": original,
    })
    evidence = _evidence_records([packet], "Compare scientific method and action research.")
    retained = next(e for e in evidence if e["chunk_id"] == "original-condition")
    assert retained["text"] == original
    assert retained["page"] == 6
    assert retained["evidence_role"] == "requested_method_condition_context"


def test_authority_context_reaches_both_existing_calls_without_additional_generation():
    inference = MagicMock()
    inference.generate_experiment = AsyncMock(side_effect=[
        {"raw_response": notes().model_dump_json(), "generation": {}},
        {"raw_response": "An unchanged research draft [EV-123].", "generation": {}},
    ])
    evidence = [{"evidence_id": "EV-123", "text": "Original source passage", "evidence_role": "retrieved_match"}]
    authority = [{"authority_type": "agent_employment", "authority_id": "record-id", "fields": {"name": "Recorded name"}}]
    result = asyncio.run(generate_documentary_synthesis("A research question", evidence, inference, authority))
    assert inference.generate_experiment.await_count == result["inference_call_count"] == 2
    for call in inference.generate_experiment.await_args_list:
        assert '"authority_id":"record-id"' in call.args[0]
        assert '"name":"Recorded name"' in call.args[0]
    assert result["original_draft"] == "An unchanged research draft [EV-123]."
    assert result["human_acceptance_status"] == "UNASSESSED"
