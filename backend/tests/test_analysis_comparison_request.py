import sys
import json
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError
from starlette.requests import Request

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.analysis import (
    ExploratoryInterrogationRequest,
    _catalogue_response,
    _authority_claim_violations,
    _deterministic_authority_response,
    _merge_authority_evidence_ledger,
    _project_source_groups,
    _project_researcher_facing_response,
    _project_staged_exploratory_response,
    _synthesis_unavailable_response,
)
from app.api.routes import analysis


class ExploratoryComparisonRequestTests(unittest.TestCase):
    def test_route_authority_records_survive_in_typed_evidence_ledger(self):
        authority = [{
            "authority_type": "agent_employment", "authority_id": "PERSON-1",
            "fields": {"label": "A Person", "job_title_label": "Tutor"},
        }]

        ledger = _merge_authority_evidence_ledger([], authority)
        deduplicated = _merge_authority_evidence_ledger(ledger, authority)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]["evidence_type"], "DATABASE_AUTHORITY")
        self.assertEqual(deduplicated[0]["chunk_id_or_record_id"], "PERSON-1")

    def test_authority_claim_text_must_match_structured_role_fields(self):
        authorities = [{
            "authority_type": "ddr_projects", "authority_id": "181",
            "fields": {
                "label": "Recent developments in Design Research",
                "project_lead_name": "George Mallen",
                "funder_name": "Science Research Council",
                "duration_text": "12 months",
            },
        }]
        claims = _deterministic_authority_response(authorities)["final_claim_plan"]["claims"]

        self.assertIn("project lead: George Mallen", claims[0]["text"])
        self.assertEqual(_authority_claim_violations(claims, authorities), [])
        changed = [{**claims[0], "text": claims[0]["text"].replace("George Mallen", "Another Person")}]
        self.assertTrue(_authority_claim_violations(changed, authorities))

    def test_authority_response_exposes_provenance_and_project_boundary(self):
        response = _deterministic_authority_response([{
            "authority_type": "ddr_projects", "authority_id": "171",
            "fields": {"label": "Job 171", "project_lead_name": "Pierre Goumain"},
        }])

        self.assertEqual(response["authority_provenance"], [{"authority_type": "ddr_projects", "authority_id": "171"}])
        self.assertIn("does not by itself establish report authorship", response["authority_boundaries"][0])

    def test_report_role_does_not_overwrite_project_authority_role(self):
        authority = [{
            "authority_type": "ddr_projects", "authority_id": "171",
            "fields": {"label": "Job 171", "project_lead_name": "Pierre Goumain"},
        }]
        authority_claim = _deterministic_authority_response(authority)["final_claim_plan"]["claims"][0]
        documentary_claim = {
            "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
            "text": "The report front matter names another person as group leader.",
            "supporting_source_ids": ["doc-1:chunk-1"],
            "supporting_evidence_card_ids": ["ev:1234567890abcdef"],
            "supporting_authority_ids": [],
        }

        projection = _project_researcher_facing_response(
            {"claims": [authority_claim, documentary_claim], "overall_limit_ids": []},
            [{
                "evidence_card_id": "ev:1234567890abcdef", "source_id": "doc-1:chunk-1",
                "validation_status": "VALIDATED",
            }],
            [{"document_id": "doc-1", "chunk_id": "chunk-1"}],
            authority,
            {"NOT_ESTABLISHED": []},
            "HYBRID_AUTHORITY_DOCUMENTARY",
        )

        self.assertEqual(projection["authority_evidence"][0]["fields"]["project_lead_name"], "Pierre Goumain")
        self.assertIn("group leader", projection["documentary_evidence"][0]["text"])
        self.assertEqual(projection["role_reconciliation"][0]["status"], "distinct_evidence_roles")
        self.assertEqual(projection["role_reconciliation"][0]["authority_numbers"], [1])
        self.assertEqual(projection["role_reconciliation"][0]["source_numbers"], [1])

    def test_source_groups_retain_chunks_under_a_single_asset(self):
        sources = [
            {
                "document_id": "document-1", "chunk_id": "chunk-1", "title": "Rector's report",
                "page_start": 12, "text": "First passage.", "display_date": "December 1972",
                "provenance": {"asset_pid": "613671017198", "collection_title": "RCA Rector's reports"},
                "evidence_anchor": {"preset_id": "ddr_teaching_learning_practice"},
            },
            {
                "document_id": "document-1", "chunk_id": "chunk-2", "title": "Rector's report",
                "page_start": 13, "text": "Second passage.", "display_date": "December 1972",
                "provenance": {"asset_pid": "613671017198", "collection_title": "RCA Rector's reports"},
                "evidence_anchor": {"preset_id": "ddr_teaching_learning_practice"},
            },
        ]

        groups = _project_source_groups(sources, [{
            "source_id": "document-1:chunk-1", "evidence_type": "DIRECT_DOCUMENTARY",
        }])

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["title"], "Rector's report")
        self.assertEqual(groups[0]["date"], "December 1972")
        self.assertEqual(groups[0]["pid"], "613671017198")
        self.assertEqual(groups[0]["evidence_types"], ["DIRECT_DOCUMENTARY"])
        self.assertEqual(groups[0]["presets"], ["ddr_teaching_learning_practice"])
        self.assertEqual([chunk["source_number"] for chunk in groups[0]["chunks"]], [1, 2])
        self.assertEqual([chunk["chunk_id"] for chunk in groups[0]["chunks"]], ["chunk-1", "chunk-2"])

    def test_source_group_chunk_numbers_match_global_citation_order(self):
        sources = [
            {"document_id": "document-1", "chunk_id": "chunk-1", "provenance": {"asset_pid": "asset-1"}},
            {"document_id": "document-2", "chunk_id": "chunk-2", "provenance": {"asset_pid": "asset-2"}},
        ]

        groups = _project_source_groups(sources, [])

        self.assertEqual([group["chunks"][0]["source_number"] for group in groups], [1, 2])

    def test_comparison_requires_exactly_two_documents(self):
        with self.assertRaises(ValidationError):
            ExploratoryInterrogationRequest(
                query="Compare the selected sources.",
                mode="comparison",
                target_document_ids=["document-a"],
            )

    def test_comparison_accepts_two_documents(self):
        request = ExploratoryInterrogationRequest(
            query="Compare the selected sources.",
            mode="comparison",
            target_document_ids=["document-a", "document-b"],
        )

        self.assertEqual(request.mode, "comparison")
        self.assertEqual(request.target_document_ids, ["document-a", "document-b"])

    def test_catalogue_authority_claims_include_authority_citation_numbers(self):
        response = _catalogue_response(
            "What projects did Pierre Goumain work on?",
            {"results": []},
            [{
                "authority_type": "ddr_projects",
                "authority_id": "171",
                "fields": {"title": "Designer-computer interaction", "project_lead_name": "Pierre Goumain"},
            }],
        )

        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["authority_numbers"], [1])

    def test_catalogue_document_claims_include_source_citation_numbers(self):
        response = _catalogue_response(
            "What documents mention Janet Daley?",
            {"results": [{
                "document_id": "document-1",
                "chunk_id": "chunk-1",
                "title": "RCA yearbook",
                "asset_pid": "asset-1",
                "page_start": 40,
            }]},
            [],
        )

        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1])

    def test_staged_projection_exposes_validated_and_rejected_evidence_cards(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [],
                    "EVIDENCE_CARDS": [{"evidence_card_id": "ev:0123456789abcdef", "source_text_hash": "a" * 64}],
                    "EVIDENCE_LEDGER": [{"evidence_id": "ev:0123456789abcdef", "evidence_type": "DIRECT_DOCUMENTARY"}],
                    "REJECTED_EVIDENCE_CARDS": [{"source_id": "document-1:chunk-1", "reason": "invalid_passage_provenance"}],
                },
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": []},
        )

        self.assertEqual(response["evidence_cards"][0]["evidence_card_id"], "ev:0123456789abcdef")
        self.assertEqual(response["evidence_ledger"][0]["evidence_type"], "DIRECT_DOCUMENTARY")
        self.assertEqual(response["evidence_cards"][0]["source_text_hash"], "a" * 64)
        self.assertEqual(response["rejected_evidence_cards"][0]["reason"], "invalid_passage_provenance")

    def test_staged_projection_keeps_testimony_separate_from_documentary_evidence(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "A bounded recollection.", "synthesis_claims": []},
                "cross_source_analysis": {},
                "final_claim_plan": {"claims": [], "overall_limit_ids": []},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [{
                        "source_id": "interview:chunk-1", "claim": "The interviewee recalled the event.",
                        "evidence_card_id": "ev:1234567890abcdef",
                    }],
                    "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [],
                    "NOT_ESTABLISHED": [], "source_classifications": [],
                    "EVIDENCE_CARDS": [{
                        "evidence_card_id": "ev:1234567890abcdef",
                        "evidence_type": "RETROSPECTIVE_TESTIMONY",
                    }],
                },
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": []},
        )

        self.assertEqual(response["documentary_evidence"], [])
        self.assertEqual(response["testimony_evidence"][0]["origin"], "retrospective_testimony")

    def test_evidence_limit_claim_includes_all_returned_source_citations(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {
                    "answer": "The DDR documents do not provide direct documentary evidence for this question.",
                    "synthesis_claims": [],
                },
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [],
                    "DATABASE_AUTHORITY": [],
                    "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [],
                    "NOT_ESTABLISHED": [],
                    "source_classifications": [],
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{
                    "document_id": "document-1",
                    "chunk_id": "chunk-1",
                    "title": "RCA yearbook",
                    "asset_pid": "asset-1",
                    "page_start": 5,
                }],
            },
        )

        self.assertEqual(response["answer_origin"], "deterministic_evidence_limit")
        self.assertEqual(response["answer_state"], "evidential_limit")
        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1])

    def test_authority_context_with_documentary_limit_is_an_evidential_limit(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [{"source_id": "document-1:chunk-1", "claim": "Context only.", "evidence_card_id": "ev:1"}],
                    "EVIDENCE_CARDS": [{"evidence_card_id": "ev:1", "evidence_type": "DIRECT_DOCUMENTARY", "claim_admissibility": {"decision": "INSUFFICIENT"}}],
                    "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [],
                    "source_classifications": [{"source_id": "document-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"}],
                },
                "final_claim_plan": {
                    "claims": [{"claim_id": "authority:1", "claim_type": "DATABASE_AUTHORITY", "text": "Authority context."}],
                    "open_uncertainties": ["Available evidence does not establish the requested activity."],
                },
                "stage_execution": {"source_analysis": {"status": "success"}},
            },
            {
                "transparency": {"strategy": "semantic", "route_family": "HYBRID_AUTHORITY_DOCUMENTARY", "resolved_entities": [], "query_variants": []},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1", "title": "Report"}],
            },
        )

        self.assertEqual(response["answer_origin"], "deterministic_evidence_limit")
        self.assertEqual(response["answer_state"], "evidential_limit")
        self.assertIn("authority", response["answer"].lower())
        self.assertIn("does not establish", response["answer"])

    def test_degraded_evidence_analysis_is_synthesis_unavailable_not_limit(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [],
                },
                "stage_execution": {
                    "source_analysis": {
                        "status": "partial",
                        "failure_code": "source_analysis_validation",
                    },
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1", "title": "RCA yearbook"}],
            },
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(response["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(response["synthesis_failure"]["code"], "evidence_validation_failed")
        self.assertNotIn("do not provide a direct documentary description", response["answer"])

    def test_failed_final_synthesis_is_not_projected_as_evidential_limit(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [],
                },
                "stage_execution": {
                    "source_analysis": {"status": "success"},
                    "final_synthesis": {"status": "failed", "failure_code": "final_synthesis_generation"},
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1", "title": "RCA yearbook"}],
            },
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(response["synthesis_failure"]["code"], "synthesis_service_error")
        self.assertNotIn("do not provide a direct documentary description", response["answer"])

    def test_failed_final_synthesis_preserves_source_and_authority_ledgers(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [],
                    "DATABASE_AUTHORITY": [{"authority_id": "ARCHERB", "role": "employment"}],
                    "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [],
                    "source_classifications": [],
                },
                "source_analyses": [{
                    "packet": {"source_id": "document-1:chunk-1"}, "status": "success",
                    "analysis": {"relationship_to_question": "CONTEXTUAL_ONLY", "contextual_claims": ["Context only"]},
                }],
                "stage_execution": {
                    "source_analysis": {"status": "success"},
                    "final_synthesis": {"status": "failed", "failure_code": "final_synthesis_generation"},
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1", "title": "RCA yearbook"}],
            },
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(response["authority_evidence"][0]["authority_id"], "ARCHERB")
        self.assertEqual(response["source_analysis_results"][0]["source_id"], "document-1:chunk-1")
        self.assertEqual(response["source_analysis_summary"]["contextual_sources"], 1)

    def test_repairable_narrative_coverage_failure_is_partial_synthesis(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {
                    "answer": "",
                    "synthesis_claims": [{
                        "text": "The first record supports a bounded conclusion.",
                        "source_numbers": [1],
                        "paragraph": 1,
                    }],
                },
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [],
                },
                "narrative_validation": [{
                    "rule_id": "narrative_source_coverage", "status": "fail", "severity": "repairable",
                }],
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [
                    {"document_id": "document-1", "chunk_id": "chunk-1"},
                    {"document_id": "document-2", "chunk_id": "chunk-2"},
                ],
            },
        )

        self.assertEqual(response["answer_state"], "synthesis_partial")
        self.assertIn("bounded conclusion. [1]", response["answer"])
        self.assertEqual(response["source_usage"]["unused_source_numbers"], [2])

    def test_optional_narrative_repair_failure_does_not_discard_valid_plan(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": [{
                    "text": "A validated documentary conclusion.", "claim_ids": ["c1"], "paragraph": 1,
                }]},
                "final_claim_plan": {"claims": [{
                    "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
                    "supporting_source_ids": ["document-1:chunk-1"], "supporting_authority_ids": [], "limit_ids": ["limit-1"],
                }], "overall_limit_ids": ["limit-1"]},
                "cross_source_analysis": {},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": ["A bounded limit."], "source_classifications": []},
                "stage_execution": {
                    "source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "success"},
                    "final_synthesis": {"status": "success"}, "narrative_synthesis": {"status": "success"},
                    "narrative_repair": {"status": "failed"},
                },
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-1", "chunk_id": "chunk-1"}]},
        )

        self.assertEqual(response["answer_state"], "synthesis_valid")
        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["claim_ids"], ["c1"])

    def test_claim_id_citations_are_deterministic_and_ignore_model_source_numbers(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": [{
                    "text": "A bounded synthesis from two validated claims.",
                    "claim_ids": ["c1", "c2"], "limit_ids": ["limit-1"],
                    "source_numbers": [99], "paragraph": 1,
                }]},
                "final_claim_plan": {"claims": [
                    {"claim_id": "c1", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": ["document-1:chunk-1", "document-2:chunk-2"], "supporting_authority_ids": [], "limit_ids": ["limit-1"]},
                    {"claim_id": "c2", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": ["document-2:chunk-2"], "supporting_authority_ids": [], "limit_ids": []},
                ], "overall_limit_ids": ["limit-1"]},
                "cross_source_analysis": {},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [
                {"document_id": "document-1", "chunk_id": "chunk-1"},
                {"document_id": "document-2", "chunk_id": "chunk-2"},
            ]},
        )
        claim = response["answer_paragraphs"][0]["claims"][0]
        self.assertEqual(claim["source_numbers"], [1, 2])
        self.assertEqual(claim["claim_ids"], ["c1", "c2"])
        self.assertEqual(claim["limit_ids"], ["limit-1"])
        self.assertNotIn("[99]", response["answer"])

    def test_persisted_cross_source_provenance_round_trips_to_narrative_citations(self):
        pipeline = {
            "final_synthesis": {"answer": "", "synthesis_claims": [{"text": "A bounded inference.", "claim_ids": ["c3"], "paragraph": 1}]},
            "final_claim_plan": {"claims": [{"claim_id": "c3", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": ["document-a:chunk-a", "document-c:chunk-c"], "supporting_authority_ids": [], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": []}]},
            "cross_source_analysis": {"cross_source_inferences": ["Inference X"], "cross_source_inference_sources": {"Inference X": ["document-a:chunk-a", "document-c:chunk-c"]}},
            "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
        }
        retrieval = {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [
            {"document_id": "document-a", "chunk_id": "chunk-a"}, {"document_id": "document-b", "chunk_id": "chunk-b"}, {"document_id": "document-c", "chunk_id": "chunk-c"},
        ]}
        persisted = json.loads(json.dumps(_project_staged_exploratory_response(pipeline, retrieval)))
        provenance = persisted["cross_source_inference_provenance"][0]
        self.assertEqual(provenance["supporting_source_ids"], ["document-a:chunk-a", "document-c:chunk-c"])
        self.assertEqual(provenance["supporting_source_numbers"], [1, 3])
        self.assertEqual(provenance["compiled_claim_ids"], ["c3"])
        self.assertEqual(persisted["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1, 3])

    def test_outer_exploratory_response_preserves_durable_provenance_after_json_round_trip(self):
        source_a = "document-a:chunk-a"
        source_c = "document-c:chunk-c"
        pipeline = {
            "final_synthesis": {"answer": "", "direct_documentary_claims": [], "synthesis_claims": [{"text": "A bounded inference.", "claim_ids": ["c3"], "paragraph": 1}]},
            "final_claim_plan": {"claims": [{"claim_id": "c3", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": [source_a, source_c], "supporting_authority_ids": [], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": []}]},
            "cross_source_analysis": {"cross_source_inferences": ["Inference X"], "cross_source_inference_sources": {"Inference X": [source_a, source_c]}},
            "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [
                {"source_id": source_a, "relationship_to_question": "DIRECT_SUPPORT"}, {"source_id": "document-b:chunk-b", "relationship_to_question": "NOT_RELEVANT"}, {"source_id": source_c, "relationship_to_question": "DIRECT_SUPPORT"},
            ]},
            "source_analyses": [],
            "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            "stage_execution": {"source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "success"}, "final_synthesis": {"status": "success"}},
            "timings": {}, "execution_telemetry": {}, "inference_calls": [],
        }
        retrieval = {"results": [
            {"document_id": "document-a", "chunk_id": "chunk-a", "provenance": {}}, {"document_id": "document-b", "chunk_id": "chunk-b", "provenance": {}}, {"document_id": "document-c", "chunk_id": "chunk-c", "provenance": {}},
        ], "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [], "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "diagnostics": {}}
        authority = {"authority_id": "AUTH-PROJECTED", "authority_type": "ddr_projects", "fields": {"label": "Project authority"}}
        inference = MagicMock()
        inference.get_load_status.return_value = {"model_status": "ready"}
        inference.get_model_info.return_value = {"model": "test", "display_name": "Test", "runtime": "test"}
        with (
            patch.object(analysis, "_catalogue_authorities", return_value=[authority]),
            patch.object(analysis, "_retrieve_exploratory", return_value=retrieval),
            patch.object(analysis, "_catalogue_response", return_value=None),
            patch.object(analysis, "_hydrate_source_display_dates"),
            patch.object(analysis, "_build_exploratory_packets", return_value=[]),
            patch.object(analysis, "get_inference_service", return_value=inference),
            patch.object(analysis.StagedEvidencePipeline, "run", new_callable=AsyncMock, return_value=pipeline),
        ):
            response = asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(query="What does the project evidence establish?", mode="exploratory"),
                Request({"type": "http", "headers": []}),
            ))
        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["final_claim_plan"]["claims"][0]["claim_id"], "c3")
        self.assertEqual(persisted["cross_source_inference_provenance"][0]["text"], "Inference X")
        self.assertEqual(persisted["cross_source_inference_provenance"][0]["supporting_source_ids"], [source_a, source_c])
        self.assertEqual(persisted["cross_source_inference_provenance"][0]["supporting_source_numbers"], [1, 3])
        narrative_claim = persisted["answer_paragraphs"][0]["claims"][0]
        self.assertEqual(narrative_claim["claim_ids"], ["c3"])
        self.assertEqual(narrative_claim["source_numbers"], [1, 3])
        self.assertEqual(persisted["authority_evidence"], [authority])
        self.assertEqual(persisted["final_claim_plan"]["claims"][0]["supporting_authority_ids"], [])
        self.assertEqual(
            [group["chunks"][0]["source_number"] for group in persisted["source_groups"]],
            [1, 2, 3],
        )

    def test_outer_hybrid_response_exposes_grouped_source_passages(self):
        source_id = "document-a:chunk-a"
        pipeline = {
            "final_synthesis": {"answer": "", "direct_documentary_claims": [], "synthesis_claims": []},
            "final_claim_plan": {"claims": [], "overall_limit_ids": []},
            "cross_source_analysis": {"cross_source_inferences": [], "cross_source_inference_sources": {}},
            "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
            "source_analyses": [], "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            "stage_execution": {}, "timings": {}, "execution_telemetry": {}, "inference_calls": [],
        }
        retrieval = {"results": [{"document_id": "document-a", "chunk_id": "chunk-a", "provenance": {"asset_pid": "asset-1"}}], "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [], "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "diagnostics": {}}
        authority = {"authority_id": "JANETDALEY", "authority_type": "agent_employment", "fields": {"label": "Janet Daley", "job_title_label": "Tutor"}}
        inference = MagicMock()
        inference.get_load_status.return_value = {"model_status": "ready"}
        inference.get_model_info.return_value = {"model": "test", "display_name": "Test", "runtime": "test"}
        with (
            patch.object(analysis, "_catalogue_authorities", return_value=[authority]),
            patch.object(analysis, "_retrieve_exploratory", return_value=retrieval),
            patch.object(analysis, "_catalogue_response", return_value=None),
            patch.object(analysis, "_hydrate_source_display_dates"),
            patch.object(analysis, "_build_exploratory_packets", return_value=[]),
            patch.object(analysis, "get_inference_service", return_value=inference),
            patch.object(analysis.StagedEvidencePipeline, "run", new_callable=AsyncMock, return_value=pipeline),
        ):
            response = asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(query="What can the current apparatus establish about Janet Daley's formal role and documentary traces?", mode="exploratory"),
                Request({"type": "http", "headers": []}),
            ))
        self.assertEqual(response["source_groups"][0]["asset_key"], "asset-1")
        self.assertEqual(response["source_groups"][0]["chunks"][0]["source_number"], 1)

    def test_hybrid_authority_context_with_explicit_title_limit_is_evidential_limit(self):
        source_id = "document-181:chunk-1"
        pipeline = {
            "final_synthesis": {"answer": "", "direct_documentary_claims": [], "synthesis_claims": []},
            "final_claim_plan": {
                "claims": [],
                "open_uncertainties": ["The retained report does not establish the requested relationship."],
                "overall_limit_ids": ["limit-1"],
            },
            "cross_source_analysis": {"cross_source_inferences": [], "cross_source_inference_sources": {}},
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [{"source_id": source_id, "claim": "Documentary context.", "evidence_card_id": "ev:1"}],
                "EVIDENCE_CARDS": [{
                    "evidence_card_id": "ev:1", "source_id": source_id,
                    "evidence_type": "DIRECT_DOCUMENTARY", "validation_status": "VALIDATED",
                    "claim_admissibility": {"decision": "INSUFFICIENT"},
                }],
                "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [],
                "source_classifications": [{"source_id": source_id, "relationship_to_question": "DIRECT_SUPPORT"}],
            },
            "source_analyses": [],
            "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            "stage_execution": {"source_analysis": {"status": "success"}},
            "timings": {}, "execution_telemetry": {}, "inference_calls": [],
        }
        retrieval = {
            "results": [{
                "document_id": "document-181", "chunk_id": "chunk-1", "title": "Job 181 report",
                "text": "A retained documentary passage.", "provenance": {"asset_pid": "asset-181"},
            }],
            "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [],
            "archival_context_only": [],
            "transparency": {"strategy": "explicit_source_title_v2", "resolved_entities": [], "query_variants": []},
            "diagnostics": {},
        }
        authority = {
            "authority_type": "ddr_projects", "authority_id": "181",
            "fields": {"label": "Job 181", "project_lead_name": "George Mallen"},
        }
        inference = MagicMock()
        inference.get_load_status.return_value = {"model_status": "ready"}
        inference.get_model_info.return_value = {"model": "test", "display_name": "Test", "runtime": "test"}
        with (
            patch.object(analysis, "_catalogue_authorities", return_value=[authority]),
            patch.object(analysis, "_retrieve_exploratory", return_value=retrieval),
            patch.object(analysis, "_catalogue_response", return_value=None),
            patch.object(analysis, "_hydrate_source_display_dates"),
            patch.object(analysis, "_build_exploratory_packets", return_value=[]),
            patch.object(analysis, "get_inference_service", return_value=inference),
            patch.object(analysis.StagedEvidencePipeline, "run", new_callable=AsyncMock, return_value=pipeline),
        ):
            response = asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(
                    query="Who is recorded as project lead for Job 181, and what does the report say?",
                    mode="exploratory",
                ),
                Request({"type": "http", "headers": []}),
            ))

        self.assertEqual(response["answer_origin"], "deterministic_evidence_limit")
        self.assertEqual(response["answer_state"], "evidential_limit")
        self.assertIn("George Mallen", response["answer"])
        self.assertIn("does not establish", response["answer"])

    def test_guard_rejected_narrative_fallback_preserves_claim_plan_provenance_after_json_round_trip(self):
        source_a = "document-a:chunk-a"
        source_c = "document-c:chunk-c"
        pipeline = {
            "final_synthesis": {"answer": "", "direct_documentary_claims": [], "synthesis_claims": []},
            "final_claim_plan": {"claims": [
                {"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Document A establishes a bounded fact.", "supporting_source_ids": [source_a], "supporting_authority_ids": [], "limit_ids": ["limit-7"]},
                {"claim_id": "c2", "claim_type": "CROSS_SOURCE_INFERENCE", "text": "The two records support a qualified inference.", "supporting_source_ids": [source_a, source_c], "supporting_authority_ids": [], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": []},
                {"claim_id": "c3", "claim_type": "DATABASE_AUTHORITY", "text": "The authority records a bounded employment fact.", "supporting_source_ids": [], "supporting_authority_ids": ["AUTH-1"], "limit_ids": []},
            ], "overall_limit_ids": ["limit-1", "limit-2"]},
            "cross_source_analysis": {"cross_source_inferences": ["The two records support a qualified inference."], "cross_source_inference_sources": {"The two records support a qualified inference.": [source_a, source_c]}},
            "evidence_map": {"DIRECT_DOCUMENTARY": [{"source_id": source_a, "claim": "Document A establishes a bounded fact."}], "DATABASE_AUTHORITY": [{"authority_id": "AUTH-1"}], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": [
                {"source_id": source_a, "relationship_to_question": "DIRECT_SUPPORT"}, {"source_id": "document-b:chunk-b", "relationship_to_question": "NOT_RELEVANT"}, {"source_id": source_c, "relationship_to_question": "DIRECT_SUPPORT"},
            ]},
            "narrative_artifact": {"deterministic_fallback": "INVALID_NARRATIVE_EVIDENCE_LABEL", "evidence_label_violations": ["paragraph-1: authority label without authority claim"]},
            "narrative_validation": [{"rule_id": "narrative_evidence_label", "status": "fail", "severity": "critical"}],
            "source_analyses": [], "provenance": {},
            "stage_execution": {"source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "success"}, "final_synthesis": {"status": "success"}, "narrative_synthesis": {"status": "partial"}},
            "timings": {}, "execution_telemetry": {}, "inference_calls": [],
        }
        retrieval = {"results": [
            {"document_id": "document-a", "chunk_id": "chunk-a", "provenance": {}}, {"document_id": "document-b", "chunk_id": "chunk-b", "provenance": {}}, {"document_id": "document-c", "chunk_id": "chunk-c", "provenance": {}},
        ], "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [], "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "diagnostics": {}}
        inference = MagicMock()
        inference.get_load_status.return_value = {"model_status": "ready"}
        inference.get_model_info.return_value = {"model": "test", "display_name": "Test", "runtime": "test"}
        with (
            patch.object(analysis, "_catalogue_authorities", return_value=[]),
            patch.object(analysis, "_retrieve_exploratory", return_value=retrieval),
            patch.object(analysis, "_catalogue_response", return_value=None),
            patch.object(analysis, "_build_exploratory_packets", return_value=[]),
            patch.object(analysis, "get_inference_service", return_value=inference),
            patch.object(analysis.StagedEvidencePipeline, "run", new_callable=AsyncMock, return_value=pipeline),
        ):
            response = asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(query="What does the evidence establish?", mode="exploratory"),
                Request({"type": "http", "headers": []}),
            ))

        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["answer_state"], "synthesis_unavailable")
        self.assertEqual(persisted["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(persisted["answer_paragraphs"], [])
        self.assertEqual(persisted["final_claim_plan"]["claims"][1]["supporting_cross_source_inference_ids"], ["cross-source-inference-1"])
        self.assertEqual(persisted["cross_source_inference_provenance"][0]["compiled_claim_ids"], ["c2"])
        self.assertEqual(persisted["cross_source_inference_provenance"][0]["supporting_source_numbers"], [1, 3])

    def test_outer_cross_source_parse_failure_preserves_plan_backed_partial_fallback(self):
        source_a = "document-a:chunk-a"
        pipeline = {
            "final_synthesis": {"answer": "", "direct_documentary_claims": [], "synthesis_claims": []},
            "final_claim_plan": {"claims": [{
                "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Document A establishes a bounded fact.",
                "supporting_source_ids": [source_a], "supporting_authority_ids": [], "limit_ids": ["limit-1"],
            }], "overall_limit_ids": ["limit-1"]},
            "cross_source_analysis": {"inferences": [], "cross_source_inferences": [], "cross_source_inference_sources": {}},
            "cross_source_artifact": {"deterministic_fallback": "STRUCTURED_PARSE_FAILURE", "failure_code": "truncated_output", "cross_source_stop_reason": "length", "cross_source_truncated": True, "rejected_inferences": []},
            "evidence_map": {"DIRECT_DOCUMENTARY": [{"source_id": source_a, "claim": "Document A establishes a bounded fact."}], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": ["A bounded limit."], "source_classifications": [{"source_id": source_a, "relationship_to_question": "DIRECT_SUPPORT"}]},
            "narrative_artifact": {"deterministic_fallback": "INVALID_NARRATIVE_SYNTHESIS"},
            "narrative_validation": [{"rule_id": "narrative_schema_validation", "status": "fail", "severity": "critical"}],
            "source_analyses": [], "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            "stage_execution": {"source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "failed", "failure_code": "structured_parse_failure"}, "final_synthesis": {"status": "success"}, "narrative_synthesis": {"status": "partial"}},
            "timings": {}, "execution_telemetry": {"final_claim_compilation": {"model_calls": 0}}, "inference_calls": [],
        }
        retrieval = {"results": [{"document_id": "document-a", "chunk_id": "chunk-a", "provenance": {}}], "archival_discovery": [], "document_availability": [], "corpus_representation_gaps": [], "archival_context_only": [], "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "diagnostics": {}}
        inference = MagicMock()
        inference.get_load_status.return_value = {"model_status": "ready"}
        inference.get_model_info.return_value = {"model": "test", "display_name": "Test", "runtime": "test"}
        with (
            patch.object(analysis, "_catalogue_authorities", return_value=[]),
            patch.object(analysis, "_retrieve_exploratory", return_value=retrieval),
            patch.object(analysis, "_catalogue_response", return_value=None),
            patch.object(analysis, "_build_exploratory_packets", return_value=[]),
            patch.object(analysis, "get_inference_service", return_value=inference),
            patch.object(analysis.StagedEvidencePipeline, "run", new_callable=AsyncMock, return_value=pipeline),
        ):
            response = asyncio.run(analysis.interrogate_exploratory_corpus(
                ExploratoryInterrogationRequest(query="What does the evidence establish?", mode="exploratory"),
                Request({"type": "http", "headers": []}),
            ))

        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["answer_state"], "synthesis_unavailable")
        self.assertEqual(persisted["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertNotEqual(persisted["answer_state"], "evidential_limit")
        self.assertEqual(persisted["answer_paragraphs"], [])
        self.assertEqual(persisted["final_claim_plan"]["claims"][0]["claim_id"], "c1")
        self.assertEqual(persisted["cross_source_inference_diagnostics"]["cross_source_status"], "failed")
        self.assertEqual(persisted["cross_source_inference_diagnostics"]["cross_source_inferences_rejected"], 0)
        self.assertEqual(persisted["cross_source_inference_diagnostics"]["cross_source_failure_code"], "truncated_output")
        self.assertEqual(persisted["cross_source_inference_diagnostics"]["cross_source_stop_reason"], "length")
        self.assertTrue(persisted["cross_source_inference_diagnostics"]["cross_source_truncated"])

    def test_configured_missingness_fallback_round_trips_plan_and_limit_provenance(self):
        source_a = "document-a:chunk-a"
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "The current digitised corpus does not establish why the decision was made. The retained report records a projected closure but no rationale.", "synthesis_claims": []},
                "final_artifact": {"configured_synthesis_guard": True},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "The retained report records a projected closure but no rationale.", "supporting_source_ids": [source_a], "supporting_authority_ids": [], "limit_ids": []}], "overall_limit_ids": ["limit-1", "limit-2"]},
                "cross_source_analysis": {"inferences": [], "cross_source_inferences": [], "cross_source_inference_sources": {}},
                "evidence_map": {"DIRECT_DOCUMENTARY": [{"source_id": source_a, "claim": "The retained report records a projected closure but no rationale."}], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": ["A rationale is not established."], "source_classifications": [{"source_id": source_a, "relationship_to_question": "DIRECT_SUPPORT"}]},
                "narrative_artifact": {"deterministic_fallback": "INVALID_NARRATIVE_SYNTHESIS"},
                "stage_execution": {"source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "success"}, "final_synthesis": {"status": "success"}, "narrative_synthesis": {"status": "partial"}},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-a", "chunk_id": "chunk-a"}]},
        )
        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["answer_state"], "synthesis_unavailable")
        self.assertEqual(persisted["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(persisted["answer_paragraphs"], [])

    def test_rejected_cross_source_only_plan_is_unavailable_not_evidential_limit(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "final_claim_plan": {"claims": [], "overall_limit_ids": []},
                "cross_source_analysis": {"inferences": [], "cross_source_inferences": [], "cross_source_inference_sources": {}},
                "cross_source_artifact": {"rejected_inferences": [{"reason": "insufficient_distinct_supporting_source_ids"}]},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [{"source_id": "document-a:chunk-a", "claim": "Context only."}], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": "document-a:chunk-a", "relationship_to_question": "CONTEXTUAL_ONLY"}]},
                "narrative_artifact": {},
                "stage_execution": {"source_analysis": {"status": "success"}, "cross_source_analysis": {"status": "success"}, "final_synthesis": {"status": "success"}, "narrative_synthesis": {"status": "partial"}},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-a", "chunk_id": "chunk-a"}]},
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(response["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(response["answer_paragraphs"], [])

    def test_guard_rejected_narrative_fallback_deduplicates_multi_claim_sources_after_round_trip(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "final_claim_plan": {"claims": [
                    {"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Claim one.", "supporting_source_ids": ["document-a:chunk-a"], "supporting_authority_ids": [], "limit_ids": []},
                    {"claim_id": "c2", "claim_type": "CROSS_SOURCE_INFERENCE", "text": "Claim two.", "supporting_source_ids": ["document-b:chunk-b", "document-c:chunk-c"], "supporting_authority_ids": [], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": []},
                ], "overall_limit_ids": []},
                "cross_source_analysis": {"cross_source_inferences": ["Claim two."], "cross_source_inference_sources": {"Claim two.": ["document-b:chunk-b", "document-c:chunk-c"]}},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
                "narrative_artifact": {"deterministic_fallback": "INVALID_NARRATIVE_EVIDENCE_LABEL"},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [
                {"document_id": "document-a", "chunk_id": "chunk-a"}, {"document_id": "document-b", "chunk_id": "chunk-b"}, {"document_id": "document-c", "chunk_id": "chunk-c"},
            ]},
        )
        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["answer_state"], "synthesis_unavailable")
        self.assertEqual(persisted["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(persisted["answer_paragraphs"], [])

    def test_guard_rejected_narrative_fallback_preserves_plan_limit_linkage_after_round_trip(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "A bounded claim.", "supporting_source_ids": ["document-a:chunk-a"], "supporting_authority_ids": [], "limit_ids": ["limit-7"]}], "overall_limit_ids": ["limit-1"]},
                "cross_source_analysis": {},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
                "narrative_artifact": {"deterministic_fallback": "INVALID_NARRATIVE_EVIDENCE_LABEL"},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-a", "chunk_id": "chunk-a"}]},
        )
        persisted = json.loads(json.dumps(response))
        self.assertEqual(persisted["answer_state"], "synthesis_unavailable")
        self.assertEqual(persisted["answer_paragraphs"], [])
        self.assertEqual(persisted["final_claim_plan"]["claims"][0]["limit_ids"], ["limit-7"])

    def test_persisted_multi_claim_sources_are_deduplicated(self):
        response = _project_staged_exploratory_response(
            {"final_synthesis": {"answer": "", "synthesis_claims": [{"text": "Combined claims.", "claim_ids": ["c1", "c2"], "paragraph": 1}]}, "final_claim_plan": {"claims": [
                {"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "supporting_source_ids": ["document-a:chunk-a", "document-b:chunk-b"], "supporting_authority_ids": [], "limit_ids": []},
                {"claim_id": "c2", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": ["document-b:chunk-b", "document-c:chunk-c"], "supporting_authority_ids": [], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": []},
            ]}, "cross_source_analysis": {}, "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []}},
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-a", "chunk_id": "chunk-a"}, {"document_id": "document-b", "chunk_id": "chunk-b"}, {"document_id": "document-c", "chunk_id": "chunk-c"}]},
        )
        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1, 2, 3])

    def test_projected_only_authority_is_not_in_narrative_claim_plan(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": [{"text": "Documentary context only.", "claim_ids": ["c1"], "paragraph": 1}]},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "CROSS_SOURCE_INFERENCE", "supporting_source_ids": ["document-1:chunk-1"], "supporting_authority_ids": [], "limit_ids": []}]},
                "cross_source_analysis": {},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [{"authority_id": "AUTH-1"}], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-1", "chunk_id": "chunk-1"}]},
        )
        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["authority_ids"], [])
        self.assertEqual(response["authority_evidence"][0]["authority_id"], "AUTH-1")

    def test_explicit_authority_plan_claim_retains_authority_provenance(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": [{"text": "The authority records a bounded employment fact.", "claim_ids": ["c1"], "paragraph": 1}]},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DATABASE_AUTHORITY", "supporting_source_ids": [], "supporting_authority_ids": ["AUTH-1"], "limit_ids": []}]},
                "cross_source_analysis": {},
                "evidence_map": {"DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [{"authority_id": "AUTH-1"}], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [], "NOT_ESTABLISHED": [], "source_classifications": []},
            },
            {"transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []}, "results": [{"document_id": "document-1", "chunk_id": "chunk-1"}]},
        )
        claim = response["answer_paragraphs"][0]["claims"][0]
        self.assertEqual(claim["authority_ids"], ["AUTH-1"])
        self.assertEqual(claim["source_numbers"], [])
        persisted_claim = response["final_claim_plan"]["claims"][0]
        self.assertEqual(persisted_claim["supporting_authority_ids"], ["AUTH-1"])
        self.assertEqual(persisted_claim["supporting_source_ids"], [])

    def test_unvalidated_retrieved_excerpt_is_not_rendered_as_answer_prose(self):
        raw_excerpt = "This complete source passage must remain a retained source, not answer prose."
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [], "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [], "NOT_ESTABLISHED": [],
                    "source_classifications": [{"source_id": "document-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"}],
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1", "text": raw_excerpt}],
            },
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(response["answer_origin"], "unvalidated_source_passages")
        self.assertNotIn(raw_excerpt, response["answer"])

    def test_invalid_prose_uses_validated_documentary_claim_plan_fallback(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "", "synthesis_claims": []},
                "final_claim_plan": {"claims": [{
                    "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
                    "text": "The report identifies the documented research need.",
                    "supporting_source_ids": ["document-1:chunk-1"],
                    "supporting_evidence_card_ids": ["ev-1"],
                    "supporting_authority_ids": [], "limit_ids": [],
                }]},
                "cross_source_analysis": {},
                "narrative_artifact": {"deterministic_fallback": "INVALID_PROSE_EVIDENCE_LABEL"},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [{"source_id": "document-1:chunk-1", "claim": "The report identifies the documented research need."}],
                    "EVIDENCE_CARDS": [{
                        "evidence_card_id": "ev-1", "source_id": "document-1:chunk-1",
                        "validation_status": "VALIDATED", "evidence_type": "DIRECT_DOCUMENTARY",
                    }],
                    "DATABASE_AUTHORITY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [],
                    "NOT_ESTABLISHED": [],
                    "source_classifications": [{"source_id": "document-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"}],
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": [], "route_family": "DOCUMENTARY"},
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1"}],
            },
        )

        self.assertEqual(response["answer_origin"], "validated_claim_plan_fallback")
        self.assertEqual(response["answer_state"], "synthesis_valid")
        self.assertIn("documented research need", response["answer"])

    def test_pipeline_stage_failure_preserves_retrieved_sources(self):
        response = _synthesis_unavailable_response(
            ExploratoryInterrogationRequest(query="What does this establish?"),
            {
                "results": [{"document_id": "document-1", "chunk_id": "chunk-1"}],
                "transparency": {"strategy": "semantic"},
                "diagnostics": {"retrieved_documentary_source_count": 1},
            },
            stage="source_analysis",
            failure_code="pipeline_stage_error",
            failure_message="source_analysis response did not match its structured schema.",
        )

        self.assertEqual(response["answer_state"], "synthesis_unavailable")
        self.assertEqual(len(response["retrieved_evidence"]), 1)
        self.assertEqual(response["source_groups"][0]["chunks"][0]["chunk_id"], "chunk-1")
        self.assertEqual(response["stage_execution"]["records"]["source_analysis"]["status"], "failed")
        self.assertEqual(response["synthesis_failure"], {
            "code": "pipeline_stage_error",
            "message": "source_analysis response did not match its structured schema.",
            "stage": "source_analysis",
        })


if __name__ == "__main__":
    unittest.main()