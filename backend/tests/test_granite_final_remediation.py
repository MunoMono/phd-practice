import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes import analysis
from app.services.retrieval_contract_service import (
    FacetRequirement, candidate_matches_facet, derive_retrieval_contract,
)
from app.services.turin_question_route import decompose_hybrid_question
from app.services.turin_research_answer_service import (
    _evidence_records, build_documentary_analysis_prompt,
    build_documentary_composition_prompt, DocumentaryAnalysis,
)
from tests.test_turin_evidence_pipeline_service import PACKET


QUESTION = (
    "What does the database authority record about John Wood's DDR role, and "
    "what do Jobs 146 and 175 document about the Strathclyde police control-room work?"
)
AUTHORITY = [{
    "authority_type": "agent_employment", "authority_id": "person-john-wood",
    "fields": {"name": "John Wood", "start_date": "1969", "end_date": "1977"},
}]


def test_leading_authority_question_does_not_consume_documentary_clause():
    decomposition = decompose_hybrid_question(QUESTION)
    assert decomposition.authority_query == "What does the database authority record about John Wood's DDR role"
    assert decomposition.documentary_query.startswith("what do Jobs 146 and 175")
    assert decomposition.documentary_anchors == ["Job 146", "Job 175"]
    assert "database authority" not in decomposition.documentary_query


def test_measurement_requires_a_mechanism_not_only_a_document_title():
    contract = derive_retrieval_contract(
        "How did teaching connect scientific method, modelling and measurement to design?"
    )
    facet = FacetRequirement("activity", "measurement")
    assert facet in contract.required_facets
    assert candidate_matches_facet({"chunk_text": "Learner performance is measured to control instruction."}, facet)
    assert not candidate_matches_facet({"chunk_text": "The course covers general design practice."}, facet)


def test_closure_announcement_in_existing_neighbor_is_retained_with_original_provenance():
    packet = deepcopy(PACKET)
    packet.document.update({"title": "Rector's report", "date": "December 1985"})
    text = "The Department of Design Research will close in August 1986."
    packet.document_context["ordered_chunks"].append({
        "chunk_id": "closure-neighbor", "chunk_index": 9, "page": 23, "text": text,
    })
    question = "What changes in DDR's institutional position and activities are visible across the Rector's reports from the late 1960s to 1985?"
    closure = next(item for item in _evidence_records([packet], question) if item["text"] == text)
    assert closure["chunk_id"] == "closure-neighbor"
    assert closure["date"] == "December 1985"
    assert closure["page"] == 23
    assert closure["evidence_role"] == "promoted_complete_neighbor_sentence"


def test_instructions_preserve_scope_cover_concepts_and_do_not_retract_overstrong_opening():
    prompt = build_documentary_composition_prompt(
        QUESTION, [], DocumentaryAnalysis(
            propositions=[{
                "proposition_id": "P1", "statement": "Recorded proposition",
                "actor": None, "qualifications": "Bounded", "evidence_ids": ["EV-123"],
            }],
            relationships=[], unsupported_conclusions=["No implementation outcome established"],
        ),
    )
    assert "DOCUMENTARY TASK" in prompt
    assert "database authority facts separately" in prompt
    assert "complete role" in prompt
    assert "then try to retract" in prompt
    assert "later date explicitly" in prompt
    assert "every explicitly requested concept" in prompt
    assert "not merely a title or list" in build_documentary_analysis_prompt(QUESTION, [])


@pytest.mark.parametrize("failure", [None, "empty", "generation"])
def test_hybrid_reuses_two_call_draft_and_preserves_authority_on_failure(failure):
    source = {"evidence_id": "EV-123", "text": "An original project report passage."}
    generated = {
        "original_draft": "The reports show contrasting design problems [EV-123].",
        "evidence_sources": [source], "citation_bindings": [{"evidence_ids": ["EV-123"]}],
        "inference_call_count": 2, "inference_calls": [],
        "human_acceptance_status": "UNASSESSED",
    }
    documentary_draft = generated["original_draft"]
    retrieval = {"results": [] if failure == "empty" else [{"document_id": "doc", "chunk_id": "chunk"}],
                 "transparency": {}, "diagnostics": {}}
    inference = MagicMock()
    inference.get_model_info.return_value = {
        "model": "granite4.1:30b-q4_K_M", "display_name": "Granite 30B", "runtime": "remote_ollama",
    }
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "_catalogue_authorities", return_value=AUTHORITY,
    ), patch.object(analysis, "_retrieve_exploratory", return_value=retrieval) as retrieve, patch.object(
        analysis, "_hydrate_source_display_dates",
    ), patch.object(analysis, "_build_research_answer_packets", return_value=[SimpleNamespace(source_id="doc:chunk")]) as packets, patch.object(
        analysis, "_evidence_records", return_value=[source],
    ), patch.object(analysis, "get_inference_service", return_value=inference), patch.object(
        analysis, "generate_documentary_synthesis",
        new=AsyncMock(side_effect=ValueError("Invalid analysis") if failure == "generation" else None, return_value=generated),
    ) as generate, patch.object(analysis.StagedEvidencePipeline, "run", new=AsyncMock()) as old_staged:
        result = asyncio.run(analysis.interrogate_exploratory_corpus(
            analysis.ExploratoryInterrogationRequest(query=QUESTION),
        ))
    assert result["authority_evidence"] == AUTHORITY
    assert "John Wood" in (result.get("original_draft") or result["answer"])
    assert "1969" in (result.get("original_draft") or result["answer"])
    old_staged.assert_not_awaited()
    retrieve.assert_called_once()
    if failure is None:
        assert result["original_draft"].endswith(documentary_draft)
        assert result["draft_label"] == "UNVERIFIED RESEARCH DRAFT"
        assert result["documentary_evidence"] == [source]
        assert result["citation_bindings"] == generated["citation_bindings"]
        assert result["stage_execution"]["call_count"] == 2
        assert result["human_acceptance_status"] == "UNASSESSED"
        packets.assert_called_once_with(retrieval["results"], decompose_hybrid_question(QUESTION).documentary_query)
        generate.assert_awaited_once()
    else:
        assert result["answer_state"] == "synthesis_unavailable"
        assert "absent" in result["answer"] or "does not establish historical absence" in result["answer"]
        if failure == "empty":
            generate.assert_not_awaited()
