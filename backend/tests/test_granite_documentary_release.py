import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes import analysis
from app.api.routes.analysis import ExploratoryInterrogationRequest
from app.services.inference_service import _output_token_limit
from app.services.inference_service import InferenceService, ModelStatus
from tests.test_inference_service import FakeAsyncClient


def test_documentary_dispatch_uses_existing_candidate():
    request = ExploratoryInterrogationRequest(query="How is design described?")
    candidate = {"original_draft": "Complete unverified prose.", "answer": None}
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "_collection_question_subject", return_value=None
    ), patch.object(analysis, "_is_archive_scope_overview_request", return_value=False), patch.object(
        analysis, "classify_question_route", return_value=SimpleNamespace(family="DOCUMENTARY")
    ), patch.object(analysis, "research_answer_corpus", new=AsyncMock(return_value=candidate)) as generate:
        assert asyncio.run(analysis.interrogate_exploratory_corpus(request)) == candidate
    generate.assert_awaited_once_with(request)


def test_projection_retains_complete_draft_without_semantic_acceptance():
    source = {
        "evidence_id": "EV-123456789abc", "source_id": "doc:chunk",
        "document_id": "doc", "chunk_id": "chunk", "page": 7, "asset_id": "asset",
        "archive_record_pid": "archive", "attached_media_pid": "media", "asset_pid": "pid",
        "source_uri": "https://archive.test/source.pdf",
        "text": "An original conditional source passage.",
    }
    draft = "Complete model interpretation [EV-123456789abc]."
    generated = {
        "original_draft": draft, "answer": None, "verified_answer": None,
        "human_acceptance_status": "UNASSESSED", "evidence_sources": [source],
        "citation_bindings": [{"evidence_ids": [source["evidence_id"]], "source_spans": [source]}],
        "inference_calls": [{"stage": "documentary_evidence_analysis"}, {"stage": "documentary_scholarly_composition"}],
        "inference_call_count": 2,
    }
    retrieval = {"results": [{"document_id": "doc", "chunk_id": "chunk"}], "transparency": {}, "diagnostics": {}}
    inference = MagicMock()
    inference.get_model_info.return_value = {
        "model": "granite4.1:30b-q4_K_M", "display_name": "Granite 30B", "runtime": "remote_ollama",
    }
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "classify_question_route", return_value=SimpleNamespace(family="DOCUMENTARY")
    ), patch.object(analysis, "_retrieve_exploratory", return_value=retrieval) as retrieve, patch.object(
        analysis, "_hydrate_source_display_dates"
    ), patch.object(analysis, "_build_research_answer_packets", return_value=[SimpleNamespace(source_id="doc:chunk")]), patch.object(
        analysis, "_evidence_records", return_value=[source]
    ), patch.object(analysis, "get_inference_service", return_value=inference), patch.object(
        analysis, "generate_documentary_synthesis", new=AsyncMock(return_value=generated)
    ) as generate:
        result = asyncio.run(analysis.research_answer_corpus(
            ExploratoryInterrogationRequest(query="How is design described?")
        ))
    assert result["original_draft"] == result["researcher_facing"]["original_draft"] == draft
    assert result["draft_label"] == "UNVERIFIED RESEARCH DRAFT"
    assert result["answer"] is result["verified_answer"] is None
    assert result["provenance_validation"]["valid"] is False
    assert result["provenance_validation"]["semantic_status"] == "UNASSESSED"
    assert result["documentary_evidence"] == [source]
    assert result["human_acceptance_status"] == "UNASSESSED"
    assert result["stage_execution"]["call_count"] == 2
    retrieve.assert_called_once()
    generate.assert_awaited_once()
    assert generate.await_args.args[2] is inference


@pytest.mark.parametrize("family", ["AUTHORITY_ONLY", "SCOPED_MISSINGNESS"])
def test_other_classes_cannot_use_documentary_candidate(family):
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "classify_question_route", return_value=SimpleNamespace(family=family)
    ), patch.object(analysis, "get_inference_service") as factory:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(analysis.research_answer_corpus(ExploratoryInterrogationRequest(query="A question.")))
    assert raised.value.status_code == 409
    factory.assert_not_called()


@pytest.mark.parametrize("family", ["AUTHORITY_ONLY", "SCOPED_MISSINGNESS"])
def test_enabled_flag_keeps_other_classes_on_the_original_interrogation_route(family):
    class ExistingRouteCheckpoint(Exception):
        pass

    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "_collection_question_subject", return_value=None
    ), patch.object(analysis, "matching_archive_question_preset", return_value=None), patch.object(
        analysis, "classify_question_route", return_value=SimpleNamespace(family=family)
    ), patch.object(analysis, "_catalogue_authorities", side_effect=ExistingRouteCheckpoint), patch.object(
        analysis, "research_answer_corpus", new=AsyncMock()
    ) as documentary:
        with pytest.raises(ExistingRouteCheckpoint):
            asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(query="A synthetic route check.")
            ))
    documentary.assert_not_awaited()


def test_disabled_path_makes_no_generation():
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", False), patch.object(
        analysis, "generate_documentary_synthesis", new=AsyncMock()
    ) as generate:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(analysis.research_answer_corpus(ExploratoryInterrogationRequest(query="A question.")))
    assert raised.value.status_code == 404
    generate.assert_not_awaited()


def test_archive_overview_cannot_use_documentary_candidate():
    with patch.object(analysis.settings, "TURIN_GRANITE_DOCUMENTARY_ENABLED", True), patch.object(
        analysis, "_is_archive_scope_overview_request", return_value=True
    ):
        with pytest.raises(HTTPException) as raised:
            asyncio.run(analysis.research_answer_corpus(ExploratoryInterrogationRequest(query="Describe the archive.")))
    assert raised.value.status_code == 409


def test_existing_documentary_analysis_budget_is_preserved_without_changing_other_stages():
    assert _output_token_limit(2048, "documentary_evidence_analysis") == 2048
    assert _output_token_limit(1200, "documentary_scholarly_composition") == 1200
    assert _output_token_limit(2048, "source_analysis") == 1500
    assert _output_token_limit(2048, "final_synthesis") == 1500


def test_shared_transport_sends_existing_documentary_budget_without_clipping():
    with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "ollama"}, clear=True):
        service = InferenceService()
    service._status = ModelStatus.READY
    with patch("app.services.inference_service.httpx.AsyncClient", FakeAsyncClient):
        result = asyncio.run(service.generate_experiment(
            "Synthetic transport fixture", max_tokens=2048, stage="documentary_evidence_analysis",
        ))
    assert FakeAsyncClient.request["model"] == "granite4.1:30b-q4_K_M"
    assert FakeAsyncClient.request["options"]["num_predict"] == 2048
    assert result["generation"]["max_tokens"] == 2048
