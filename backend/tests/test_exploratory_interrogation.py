import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes import analysis
from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.inference_service import InferenceTimeoutError


class FakeInference:
    def get_load_status(self):
        return {"model_status": "ready"}

    async def generate_analysis(self, query, sources):
        self.query = query
        self.sources = sources
        return {"analysis": "A source-backed exploratory answer."}

    def get_model_info(self):
        return {"model": "qwen3:8b-q4_K_M", "display_name": "Qwen3 8B · Q4_K_M", "runtime": "ollama"}

    temperature = 0.2
    final_synthesis_max_output_tokens = 768

    async def generate_experiment(self, *args, **kwargs):
        self.one_shot_calls = getattr(self, "one_shot_calls", 0) + 1
        return {"raw_response": "DIRECT DOCUMENTARY EVIDENCE\nS1 [DIRECT_SUPPORT]: A documentary claim.\n\nCROSS-SOURCE INFERENCE\nNone.\n\nCONTESTED / QUALIFIED EVIDENCE\nNone.\n\nWHAT THE EVIDENCE DOES NOT ESTABLISH\nS1 [NO_RELEVANT_PASSAGE]: A scoped limit.", "generation": {"done_reason": "stop"}}


class FakeDatabase:
    def execute(self, _query, _parameters=None):
        class Result:
            def mappings(self):
                return self

            def all(self):
                return []

        return Result()

    def close(self):
        pass


class FakeCaptureProjectionDatabase:
    def execute(self, _query, _parameters):
        class Result:
            def mappings(self):
                return self

            def all(self):
                return [{
                    "document_id": "doc-1", "archive_record_id": None, "archive_record_pid": "record-1",
                    "attached_media_pid": "media-1", "asset_pid": "asset-1", "asset_id": "asset-id-1",
                    "asset_id_or_asset_pid": "asset-id-1", "source_uri": "https://archive.test/source.pdf",
                    "chunk_id": "chunk-1", "source_page": 2, "chunk_type": "paragraph",
                }]
        return Result()


class FakeRetrievalService:
    def retrieve(self, _db, query, top_k, corpus_version):
        self.query = query
        self.top_k = top_k
        self.corpus_version = corpus_version
        return {
            "results": [{"chunk_id": "chunk-1", "document_id": "doc-1", "text": "documentary passage", "provenance": {"pid": "123"}}],
            "transparency": {
                "original_query": query,
                "resolved_entities": [{"label": "Job 171", "authority_type": "ddr_projects"}],
                "query_variants": [{"kind": "entity_anchor", "query": "Job 171"}],
            },
            "diagnostics": {"archive_candidate_count": 4, "retrieved_documentary_source_count": 1},
            "archival_discovery": [{"asset_pid": "asset-1", "label": "Archive candidate"}],
            "document_availability": [{"asset_pid": "asset-1", "classification": "DOCLING_TEXT_AVAILABLE"}],
            "corpus_representation_gaps": [],
            "archival_context_only": [],
            "corpus_versions": ["corpus_f40d78dbce52"],
        }

    def retrieve_selected_documents(self, db, query, document_ids, corpus_version):
        result = self.retrieve(db, query, 5, corpus_version)
        result["results"][0]["document_id"] = document_ids[0]
        return result


class FakePacketBuilder:
    def build(self, _db, _sources):
        return [object()]


class FakeCaptureService:
    def persist(self, _db, payload):
        self.payload = payload
        return "researcher-ui-capture-test"


class FakePipeline:
    def __init__(self, inference):
        self.inference = inference

    async def run(self, query, _packets, **_kwargs):
        self.query = query
        return {
            "final_synthesis": {
                "answer": "A classified source-backed exploratory answer.",
                "direct_documentary_claims": [{"source_id": "doc-1:chunk-1", "claim": "The passage is documentary."}],
                "cross_source_inferences": ["Final synthesis inference."],
            },
            "cross_source_analysis": {
                "cross_source_inferences": ["Stage B inference."],
                "differences_or_contradictions": ["A qualified difference."],
            },
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [{"source_id": "doc-1:chunk-1", "document_id": "doc-1", "pid": "123", "page": 1, "chunk_ids": ["chunk-1"], "claim": "The passage is documentary."}],
                "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [],
                "NOT_ESTABLISHED": [
                    "A model-scoped limit.",
                    "The selected evidence does not establish a complete reconstruction of the subject's role.",
                ],
                "source_classifications": [{"source_id": "doc-1:chunk-1", "subject_named": True, "relationship_to_question": "DIRECT_SUPPORT"}],
            },
            "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            "inference_calls": [
                {"stage": "source_analysis"},
                {"stage": "cross_source"},
                {"stage": "final_synthesis"},
            ],
        }


class FakeV3RetrievalService:
    def retrieve(self, _db, query, top_k, corpus_version):
        return {
            "question_analysis": {"question": query}, "retrieval_template": "PERSON_ROLE",
            "lane_queries": {"entity": ["Example Person"]}, "lane_candidate_counts": {"entity": 1},
            "canonical_source_ranking": [], "passage_ranking": [], "final_five": [{"chunk_id": "chunk-1"}],
            "retrieval_adequacy": {"status": "RETRIEVAL_SUFFICIENT"}, "retrieval": {"strategy": "turin-retrieval-v3"},
            "results": [{"chunk_id": "chunk-1"}], "diagnostics": {"metadata_documentary_leakage": 0},
        }


class ExploratoryInterrogationTests(unittest.TestCase):
    def _citation_projection(self, claims, cards, sources, *, synthesis_claims=None, route_family="DOCUMENTARY", evidence_source_ids=None):
        evidence_source_ids = evidence_source_ids or [f"{source['document_id']}:{source['chunk_id']}" for source in sources]
        if synthesis_claims is None:
            synthesis_claims = [{
                "text": "The validated evidence supports a bounded scholarly interpretation of the question. Its conclusion remains limited to the cited material.",
                "claim_ids": [claim["claim_id"] for claim in claims],
                "paragraph": 1,
            }]
        return analysis._project_staged_exploratory_response(
            {
                "final_synthesis": {
                    "answer": "Unrendered answer.",
                    "synthesis_claims": synthesis_claims,
                    "cross_source_inferences": [],
                },
                "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [
                        {"source_id": source_id, "claim": f"Claim for {source_id}", "chunk_ids": [source_id.split(":", 1)[1]]}
                        for source_id in evidence_source_ids
                    ],
                    "EVIDENCE_CARDS": cards,
                    "CONTEXTUAL": [],
                    "CROSS_SOURCE_INFERENCE": [],
                    "NOT_ESTABLISHED": [],
                    "source_classifications": [],
                },
                "final_claim_plan": {"claims": claims},
                "stage_execution": {"source_analysis": {"status": "success"}},
                "narrative_validation": [],
                "narrative_artifact": {},
            },
            {"results": sources, "transparency": {"route_family": route_family}},
        )

    def test_staged_projection_exposes_answer_state_and_source_usage(self):
        projection = analysis._project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "A source-backed answer.", "synthesis_claims": [{"text": "A cited claim.", "claim_ids": ["c1"], "paragraph": 1}], "cross_source_inferences": []},
                "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
                "evidence_map": {"DIRECT_DOCUMENTARY": [{"source_id": "doc-1:chunk-1", "claim": "A cited claim.", "chunk_ids": ["chunk-1"]}], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:0123456789abcdef", "source_id": "doc-1:chunk-1", "validation_status": "VALIDATED"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": []},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "supporting_source_ids": ["doc-1:chunk-1"], "supporting_evidence_card_ids": ["ev:0123456789abcdef"], "supporting_authority_ids": []}]},
                "stage_execution": {"source_analysis": {"status": "success"}},
                "narrative_validation": [],
                "narrative_artifact": {},
            },
            {"results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Source one"}], "transparency": {}},
        )

        self.assertEqual(projection["answer_state"], "synthesis_valid")
        self.assertEqual(projection["source_usage"]["cited_source_numbers"], [1])
        self.assertEqual(projection["evidence_cards"][0]["evidence_card_id"], "ev:0123456789abcdef")

    def test_staged_projection_rejects_citation_when_evidence_card_belongs_to_another_source(self):
        projection = analysis._project_staged_exploratory_response(
            {
                "final_synthesis": {"answer": "A source-backed answer.", "synthesis_claims": [{"text": "A cited claim.", "claim_ids": ["c1"], "paragraph": 1}], "cross_source_inferences": []},
                "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
                "evidence_map": {"DIRECT_DOCUMENTARY": [{"source_id": "doc-1:chunk-1", "claim": "A cited claim.", "chunk_ids": ["chunk-1"]}], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:0123456789abcdef", "source_id": "doc-2:chunk-2", "validation_status": "VALIDATED"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": []},
                "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "supporting_source_ids": ["doc-1:chunk-1"], "supporting_evidence_card_ids": ["ev:0123456789abcdef"], "supporting_authority_ids": []}]},
                "stage_execution": {"source_analysis": {"status": "success"}},
                "narrative_validation": [],
                "narrative_artifact": {},
            },
            {"results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Source one"}], "transparency": {"route_family": "DOCUMENTARY"}},
        )

        self.assertEqual(projection["answer_state"], "synthesis_unavailable")
        self.assertEqual(projection["source_usage"]["cited_source_numbers"], [])

    def test_deterministic_claim_with_one_validated_card_marks_its_source_cited(self):
        sources = [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "One"}]
        source_id = "doc-1:chunk-1"
        result = self._citation_projection(
            [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Supported claim.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:one"]}],
            [{"evidence_card_id": "ev:one", "source_id": source_id, "validation_status": "VALIDATED"}],
            sources,
        )
        self.assertEqual(result["answer_state"], "synthesis_valid")
        self.assertEqual(result["answer_paragraphs"][0]["claims"][0]["claim_ids"], ["c1"])
        self.assertEqual(result["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1])
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [1])

    def test_deterministic_claim_with_multiple_cards_cites_every_mapped_source_in_order(self):
        sources = [{"document_id": "doc-1", "chunk_id": "chunk-1"}, {"document_id": "doc-2", "chunk_id": "chunk-2"}]
        source_ids = ["doc-1:chunk-1", "doc-2:chunk-2"]
        result = self._citation_projection(
            [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Jointly supported.", "supporting_source_ids": list(reversed(source_ids)), "supporting_evidence_card_ids": ["ev:one", "ev:two"]}],
            [{"evidence_card_id": "ev:one", "source_id": source_ids[0], "validation_status": "VALIDATED"}, {"evidence_card_id": "ev:two", "source_id": source_ids[1], "validation_status": "VALIDATED"}],
            sources,
        )
        self.assertIn("[1, 2]", result["answer"])
        self.assertEqual(result["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1, 2])
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [1, 2])

    def test_sources_are_renumbered_by_first_appearance_in_final_argument(self):
        sources = [
            {"document_id": "doc-1", "chunk_id": "chunk-1"},
            {"document_id": "doc-2", "chunk_id": "chunk-2"},
            {"document_id": "doc-3", "chunk_id": "chunk-3"},
        ]
        ordered = analysis._sources_in_answer_order(
            sources,
            {"claims": [
                {"claim_id": "c1", "supporting_source_ids": ["doc-3:chunk-3"]},
                {"claim_id": "c2", "supporting_source_ids": ["doc-1:chunk-1"]},
            ]},
            {"synthesis_claims": [
                {"claim_ids": ["c1"], "paragraph": 1},
                {"claim_ids": ["c2"], "paragraph": 2},
            ]},
        )

        self.assertEqual(
            [(source["document_id"], source["chunk_id"]) for source in ordered],
            [("doc-3", "chunk-3"), ("doc-1", "chunk-1"), ("doc-2", "chunk-2")],
        )

    def test_retained_but_unused_card_and_retrieved_only_source_are_not_cited(self):
        sources = [
            {"document_id": "doc-1", "chunk_id": "chunk-1"},
            {"document_id": "doc-2", "chunk_id": "chunk-2"},
            {"document_id": "doc-3", "chunk_id": "chunk-3"},
        ]
        first_source, second_source = "doc-1:chunk-1", "doc-2:chunk-2"
        result = self._citation_projection(
            [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Used claim.", "supporting_source_ids": [first_source], "supporting_evidence_card_ids": ["ev:one"]}],
            [{"evidence_card_id": "ev:one", "source_id": first_source, "validation_status": "VALIDATED"}, {"evidence_card_id": "ev:two", "source_id": second_source, "validation_status": "VALIDATED"}],
            sources,
            evidence_source_ids=[first_source, second_source],
        )
        self.assertEqual(result["source_usage"]["retained_evidence_source_ids"], [first_source, second_source])
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [1])
        self.assertEqual(result["source_usage"]["unused_source_numbers"], [2, 3])

    def test_missing_claim_card_or_resolvable_source_prevents_valid_synthesis(self):
        source_id = "doc-1:chunk-1"
        result = self._citation_projection(
            [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Unsupported projection.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:missing"]}],
            [],
            [{"document_id": "doc-1", "chunk_id": "chunk-1"}],
        )
        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [])
        self.assertNotIn("[1]", result["answer"])

    def test_authority_mapping_stays_separate_from_documentary_source_usage(self):
        source_id = "doc-1:chunk-1"
        result = self._citation_projection(
            [
                {"claim_id": "authority:agent_employment:RICHARDLAN", "claim_type": "DATABASE_AUTHORITY", "text": "Authority fact.", "supporting_source_ids": [], "supporting_evidence_card_ids": [], "supporting_authority_ids": ["RICHARDLAN"]},
                {"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Documentary fact.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:one"], "supporting_authority_ids": []},
            ],
            [{"evidence_card_id": "ev:one", "source_id": source_id, "validation_status": "VALIDATED"}],
            [{"document_id": "doc-1", "chunk_id": "chunk-1"}],
            synthesis_claims=[
                {"text": "Authority fact.", "claim_ids": ["authority:agent_employment:RICHARDLAN"], "paragraph": 1},
                {"text": "Documentary fact.", "claim_ids": ["c1"], "paragraph": 2},
            ],
            route_family="HYBRID_AUTHORITY_DOCUMENTARY",
        )
        claims = [claim for paragraph in result["answer_paragraphs"] for claim in paragraph["claims"]]
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [1])
        self.assertEqual(next(claim for claim in claims if claim["claim_ids"] == ["authority:agent_employment:RICHARDLAN"])["source_numbers"], [])

    def test_hospital_bedstead_claim_projects_cited_support_source(self):
        source_id = "doc_archive_482546702591_8f1cb9c49d31:chunk_4f0eae26ac53a9e7"
        result = self._citation_projection(
            [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Hospital requirements claim.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:8db16c72eb6d804a"]}],
            [{"evidence_card_id": "ev:8db16c72eb6d804a", "source_id": source_id, "validation_status": "VALIDATED"}],
            [{"document_id": "doc_archive_482546702591_8f1cb9c49d31", "chunk_id": "chunk_4f0eae26ac53a9e7", "provenance": {"asset_pid": "482546702591"}}],
        )
        self.assertEqual(result["source_usage"]["cited_source_numbers"], [1])
        self.assertEqual(result["source_usage"]["unused_source_numbers"], [])

    def test_researcher_facing_limits_use_only_final_plan_limits(self):
        source_id = "computing:chunk-1"
        response = analysis._project_researcher_facing_response(
            {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "A 1972 report records computing activity.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:one"]}], "overall_limit_ids": ["limit-1"]},
            [{"evidence_card_id": "ev:one", "source_id": source_id, "validation_status": "VALIDATED"}],
            [{"document_id": "computing", "chunk_id": "chunk-1"}], [],
            {"NOT_ESTABLISHED": ["The evidence does not establish a unique initiator.", "The selected evidence cannot establish DDR activity after the June 1985 closure boundary."]},
            "SCOPED_MISSINGNESS",
        )
        self.assertEqual([item["limit_id"] for item in response["evidential_limits"]], ["limit-1"])
        self.assertNotIn("June 1985", str(response))

    def test_researcher_facing_documentary_route_excludes_unused_authority(self):
        response = analysis._project_researcher_facing_response(
            {"claims": [], "overall_limit_ids": []}, [], [],
            [{"authority_id": "UNUSED", "authority_type": "agent_employment", "fields": {}}],
            {"NOT_ESTABLISHED": []}, "DOCUMENTARY",
        )
        self.assertEqual(response["authority_evidence"], [])
        self.assertEqual(response["answer_paragraphs"], [])

    def test_researcher_facing_comparison_leads_with_dual_supported_claim(self):
        left, right = "job-146:chunk", "job-175:chunk"
        response = analysis._project_researcher_facing_response(
            {"claims": [{"claim_id": "c1", "claim_type": "QUALIFIED_SYNTHESIS", "text": "Job 146 foregrounds systems analysis; whereas Job 175 foregrounds working conditions.", "supporting_source_ids": [left, right], "supporting_evidence_card_ids": ["ev:146", "ev:175"]}], "overall_limit_ids": []},
            [{"evidence_card_id": "ev:146", "source_id": left, "validation_status": "VALIDATED"}, {"evidence_card_id": "ev:175", "source_id": right, "validation_status": "VALIDATED"}],
            [{"document_id": "job-146", "chunk_id": "chunk"}, {"document_id": "job-175", "chunk_id": "chunk"}], [], {"NOT_ESTABLISHED": []}, "DOCUMENTARY",
            final_synthesis={"synthesis_claims": [{"text": "Job 146 foregrounds systems analysis, whereas Job 175 foregrounds controller working conditions. This contrast is bounded by the surviving records.", "claim_ids": ["c1"], "limit_ids": [], "paragraph": 1}]},
            narrative_artifact={"prose_granularity": "answer_level"},
        )
        claim = response["answer_paragraphs"][0]["claims"][0]
        self.assertEqual(response["answer_paragraphs"][0]["title"], "Supported comparison")
        self.assertEqual(claim["source_numbers"], [1, 2])

    def test_researcher_facing_uses_quality_checked_qwen_prose_without_stage_marker(self):
        source_id = "bedstead:chunk"
        response = analysis._project_researcher_facing_response(
            {"claims": [{"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "Raw catalogue fragment.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:one"]}], "overall_limit_ids": []},
            [{"evidence_card_id": "ev:one", "source_id": source_id, "validation_status": "VALIDATED"}],
            [{"document_id": "bedstead", "chunk_id": "chunk"}], [], {"NOT_ESTABLISHED": []}, "DOCUMENTARY",
            final_synthesis={"synthesis_claims": [{"text": "The report frames user requirements as part of design development. Its conclusion remains limited to the documented material.", "claim_ids": ["c1"], "limit_ids": [], "paragraph": 1}]},
            narrative_artifact={},
        )

        claim = response["answer_paragraphs"][0]["claims"][0]
        self.assertEqual(claim["text"], "The report frames user requirements as part of design development. Its conclusion remains limited to the documented material.")
        self.assertEqual(claim["source_numbers"], [1])

    def test_researcher_facing_hybrid_separates_authority_and_documentary(self):
        source_id = "langdon:chunk"
        authority = {"authority_id": "RICHARDLAN", "authority_type": "agent_employment", "fields": {"label": "Richard Langdon"}}
        response = analysis._project_researcher_facing_response(
            {"claims": [
                {"claim_id": "c1", "claim_type": "DATABASE_AUTHORITY", "text": "Richard Langdon held a recorded teaching role.", "supporting_authority_ids": ["RICHARDLAN"]},
                {"claim_id": "c2", "claim_type": "DIRECT_DOCUMENTARY", "text": "His teaching records document curriculum practice.", "supporting_source_ids": [source_id], "supporting_evidence_card_ids": ["ev:one"]},
            ], "overall_limit_ids": []},
            [{"evidence_card_id": "ev:one", "source_id": source_id, "validation_status": "VALIDATED"}],
            [{"document_id": "langdon", "chunk_id": "chunk"}], [authority], {"NOT_ESTABLISHED": []}, "HYBRID_AUTHORITY_DOCUMENTARY",
            final_synthesis={"synthesis_claims": [{"text": "The surviving teaching record documents curriculum practice alongside the recorded formal role. Its scope remains limited to the material retained here.", "claim_ids": ["c2"], "limit_ids": [], "paragraph": 1}]},
            narrative_artifact={"prose_granularity": "answer_level"},
        )
        self.assertEqual([paragraph["title"] for paragraph in response["answer_paragraphs"]], ["Database authority", "Documentary argument"])
        self.assertEqual(response["authority_evidence"], [authority])
        self.assertEqual(response["documentary_evidence"][0]["source_numbers"], [1])

    def test_passage_selection_rejects_zero_fts_score(self):
        result = ExploratoryRetrievalService._select_best_passage([
            {
                "chunk_id": "chunk-zero-score",
                "chunk_text": "A substantial documentary passage that happens to repeat the question terms for testing.",
                "score": 0.0,
            },
        ], {"documentary", "passage"})
        self.assertIsNone(result)

    def test_q06_projection_preserves_stored_classes_and_contributor_absence(self):
        sources = [
            {"source_id": "S1", "title": "Job 171 report", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
            {"source_id": "S2", "title": "Job 171 report", "evidence_classification": {"classification": "DIRECT_SUPPORT"}},
            {"source_id": "S4", "title": "Job 171 report", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
            {"source_id": "S5", "title": "Inter-university institute", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
        ]
        result = analysis._project_q06_capture_sources("Q06", sources)
        self.assertEqual(sources[0]["evidence_classification"]["classification"], "NO_RELEVANT_PASSAGE")
        self.assertEqual(result[0]["evidence_classification"]["classification"], "PARTIAL_SUPPORT")
        self.assertEqual(result[1]["evidence_classification"]["classification"], "DIRECT_SUPPORT")
        self.assertEqual(result[2]["classification_projection"]["audit_status"], "PERSISTED_CLASSIFICATION_BUG")
        self.assertEqual(result[0]["contributor_status"], "Contributor not retained in capture")
        self.assertEqual(result[0]["source_family_projection"], "Job 171 source family (4 of 5 retained sources)")
        self.assertIn("art-versus-science", result[2]["formulation_projection"]["value"])

    def test_q05_projection_preserves_stored_classes_and_surfaces_unclassified_status(self):
        sources = [
            {"source_id": "S1", "excerpt": "theoretical developments in design research", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
            {"source_id": "S2", "excerpt": "the quest for order in the design-build-evaluate process", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
            {"source_id": "S3", "excerpt": "a preliminary study", "evidence_classification": {"classification": "UNCLASSIFIED"}},
            {"source_id": "S5", "excerpt": "Design Research methods for short courses", "evidence_classification": {"classification": "DIRECT_SUPPORT"}},
        ]
        result = analysis._project_q05_capture_sources("Q05", sources)
        self.assertEqual(sources[0]["evidence_classification"]["classification"], "NO_RELEVANT_PASSAGE")
        self.assertEqual(result[0]["evidence_classification"]["classification"], "PARTIAL_SUPPORT")
        self.assertEqual(result[1]["classification_projection"]["audit_status"], "PERSISTED_CLASSIFICATION_BUG")
        self.assertEqual(result[2]["evidence_classification"]["classification"], "UNCLASSIFIED")
        self.assertEqual(result[2]["unclassified_status"], "UNCLASSIFIED — model did not classify")
        self.assertIn("Educational", result[3]["formulation_projection"]["value"])

    def test_q04_projection_marks_documented_wood_ergonomics_passage_as_partial_support(self):
        sources = [{
            "source_id": "S2", "title": "Visiting lecture of ergonomics course, notes to John Wood",
            "excerpt": "I understand from John Wood that you might contribute to our ergonomic course.",
            "evidence_classification": {"source_id": "S2", "classification": "NO_RELEVANT_PASSAGE"},
        }]
        result = analysis._project_q04_capture_sources("Q04", sources)
        self.assertEqual(sources[0]["evidence_classification"]["classification"], "NO_RELEVANT_PASSAGE")
        self.assertEqual(result[0]["evidence_classification"]["classification"], "PARTIAL_SUPPORT")
        self.assertEqual(result[0]["classification_projection"]["stored_classification"], "NO_RELEVANT_PASSAGE")
        self.assertEqual(result[0]["source_type_projection"]["value"], "Course correspondence")

    def test_q08_projection_keeps_persisted_classes_and_surfaces_formulations(self):
        sources = [
            {"source_id": "S1", "evidence_classification": {"classification": "CONTEXTUAL"}},
            {"source_id": "S2", "evidence_classification": {"classification": "NO_RELEVANT_PASSAGE"}},
            {"source_id": "S3", "evidence_classification": {"classification": "CONTEXTUAL"}},
            {"source_id": "S4", "evidence_classification": {"classification": "UNCLASSIFIED"}},
            {"source_id": "S5", "evidence_classification": {"classification": "UNCLASSIFIED"}},
        ]
        result = analysis._project_q08_capture_sources("Q08", sources)
        self.assertEqual(result[0]["evidence_classification"]["classification"], "CONTEXTUAL")
        self.assertIn("does not make that model claim directly evidenced", result[0]["classification_audit_note"])
        self.assertIn("does not contribute", result[1]["classification_audit_note"])
        self.assertEqual(result[3]["unclassified_status"], "UNCLASSIFIED — model did not classify")
        self.assertIn("incompletely perceived goals", result[3]["formulation_projection"]["value"])
        self.assertIn("Iterative modelling", result[4]["formulation_projection"]["value"])
        self.assertEqual(sources[3]["evidence_classification"]["classification"], "UNCLASSIFIED")

    def test_capture_projection_hydrates_only_empty_provenance_without_mutating_saved_source(self):
        saved_source = {"source_id": "S1", "chunk_id": "chunk-1", "provenance": {}}
        result = analysis._hydrate_capture_sources(FakeCaptureProjectionDatabase(), [saved_source])
        self.assertEqual(saved_source["provenance"], {})
        self.assertEqual(result[0]["provenance"]["archive_record_pid"], "record-1")
        self.assertEqual(result[0]["provenance"]["attached_media_pid"], "media-1")
        self.assertEqual(result[0]["provenance"]["asset_pid"], "asset-1")
        self.assertEqual(result[0]["provenance"]["page"], 2)
        self.assertEqual(result[0]["provenance_projection"], "document_chunk_identity")

    def test_arbitrary_exploratory_request_uses_qwen_and_never_formal_run(self):
        inference = FakeInference()
        retrieval = FakeRetrievalService()
        with patch.object(analysis, "get_inference_service", return_value=inference), patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval), patch.object(analysis, "EvidencePacketBuilder", return_value=FakePacketBuilder()), patch.object(analysis, "StagedEvidencePipeline", FakePipeline):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="Describe the supplied archival passage.", mode="exploratory")))
        self.assertEqual(result["mode"], "exploratory")
        self.assertFalse(result["persisted"])
        self.assertEqual(result["answer_origin"], "pipeline_synthesis_unavailable")
        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertEqual(result["model"]["name"], "qwen3:8b-q4_K_M")
        self.assertEqual(result["retrieved_evidence"][0]["chunk_id"], "chunk-1")
        self.assertEqual(result["archival_discovery"][0]["asset_pid"], "asset-1")
        self.assertTrue(result["provenance_validation"]["valid"])
        self.assertEqual(result["selected_sources_accounted_for"], {"count": 1, "total": 1})
        self.assertTrue(result["missingness"])
        self.assertEqual(result["response_schema"], "turin-evidence-pipeline-v2-exploratory-projection")
        self.assertEqual([item["inference"] for item in result["inferences"]], ["Stage B inference.", "Final synthesis inference."])
        self.assertEqual(result["contradictions"][0]["description"], "A qualified difference.")
        self.assertEqual(result["missingness"][0]["origin"], "model")
        self.assertEqual(result["missingness"][1]["origin"], "system_pipeline")
        self.assertEqual(result["authority_roles"]["planner_entity_resolution"][0]["label"], "Job 171")
        self.assertTrue(result["authority_roles"]["controlled_lexical_expansion"]["used"])
        self.assertFalse(result["authority_roles"]["qwen_authority_context"]["supplied"])
        self.assertEqual(result["stage_execution"]["call_count"], 3)
        self.assertEqual(result["stage_execution"]["stages"], ["source_analysis", "cross_source", "final_synthesis"])

    def test_catalogue_question_bypasses_qwen_and_preserves_retrieved_identity(self):
        retrieval = FakeRetrievalService()
        with patch.object(analysis, "get_inference_service") as inference, patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval), patch.object(analysis, "StagedEvidencePipeline") as pipeline:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="What documents mention Janet Daley?", mode="exploratory")))
        inference.assert_not_called()
        pipeline.assert_not_called()
        self.assertEqual(result["answer_origin"], "deterministic_catalogue_result")
        self.assertIn("Retrieved catalogue records for Janet Daley:", result["answer"])
        self.assertIn("Asset PID 123", result["answer"])
        self.assertEqual(result["stage_execution"]["call_count"], 0)
        self.assertFalse(result["authority_roles"]["qwen_authority_context"]["supplied"])

    def test_targeted_request_does_not_use_catalogue_or_authority_shortcuts(self):
        retrieval = FakeRetrievalService()
        with patch.object(analysis, "get_inference_service", return_value=FakeInference()), patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval), patch.object(analysis, "EvidencePacketBuilder", return_value=FakePacketBuilder()), patch.object(analysis, "StagedEvidencePipeline", FakePipeline), patch.object(analysis, "_catalogue_authorities") as authorities:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="What documents mention Janet Daley?", target_document_ids=["document-a"], mode="exploratory")))
        authorities.assert_not_called()
        self.assertNotEqual(result.get("answer_origin"), "deterministic_catalogue_result")
        self.assertEqual(retrieval.corpus_version, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)

    def test_targeted_request_with_no_passages_returns_scoped_limit_without_qwen(self):
        class EmptySelectedDocumentRetrieval(FakeRetrievalService):
            def retrieve_selected_documents(self, db, query, document_ids, corpus_version):
                result = super().retrieve_selected_documents(db, query, document_ids, corpus_version)
                result["results"] = []
                return result

        retrieval = EmptySelectedDocumentRetrieval()
        with patch.object(analysis, "get_inference_service") as inference, patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="What documents mention Janet Daley?", target_document_ids=["document-a"], mode="exploratory")))
        inference.assert_not_called()
        self.assertEqual(result["answer_origin"], "targeted_document_evidence_limit")
        self.assertEqual(result["stage_execution"]["call_count"], 0)
        self.assertEqual(result["missingness"][0]["scope"], "selected_document")

    def test_direct_support_without_model_claim_preserves_source_without_rendering_raw_prose(self):
        pipeline = {
            "final_synthesis": {"answer": "The evidence is not established.", "cross_source_inferences": []},
            "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
                "source_classifications": [{"source_id": "doc-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"}],
            },
            "inference_calls": [],
        }
        retrieval = {
            "results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Programme draft", "text": "The programme will establish a teachers group.", "page_start": 3}],
            "transparency": {"resolved_entities": [], "query_variants": []},
        }
        result = analysis._project_staged_exploratory_response(pipeline, retrieval)
        self.assertEqual(result["answer_origin"], "unvalidated_source_passages")
        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertNotIn("The programme will establish a teachers group.", result["answer"])
        self.assertEqual(len(retrieval["results"]), 1)

    def test_direct_support_fallback_keeps_all_retained_sources_out_of_answer_prose(self):
        pipeline = {
            "final_synthesis": {"answer": "No answer.", "cross_source_inferences": []},
            "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
                "source_classifications": [
                    {"source_id": "doc-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"},
                    {"source_id": "doc-2:chunk-2", "relationship_to_question": "DIRECT_SUPPORT"},
                ],
            },
            "inference_calls": [],
        }
        retrieval = {
            "results": [
                {"document_id": "doc-1", "chunk_id": "chunk-1", "title": "First record", "text": "First direct statement.", "page_start": 1},
                {"document_id": "doc-2", "chunk_id": "chunk-2", "title": "Second record", "text": "Second direct statement.", "page_start": 2},
            ],
            "transparency": {"resolved_entities": [], "query_variants": []},
        }
        result = analysis._project_staged_exploratory_response(pipeline, retrieval)
        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertNotIn("First direct statement.", result["answer"])
        self.assertNotIn("Second direct statement.", result["answer"])
        self.assertEqual(result["source_usage"]["unused_source_numbers"], [1, 2])

    def test_complete_qwen_narrative_renders_all_source_citations(self):
        pipeline = {
            "final_synthesis": {
                "answer": "Unrendered model answer.",
                "cross_source_inferences": [],
                "synthesis_claims": [
                    {"text": "The first two records establish a shared publication context.", "source_numbers": [1, 2], "paragraph": 1},
                    {"text": "The remaining record supplies qualified contextual detail.", "source_numbers": [3], "paragraph": 2},
                ],
            },
            "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
                "source_classifications": [
                    {"source_id": "doc-1:chunk-1", "relationship_to_question": "DIRECT_SUPPORT"},
                    {"source_id": "doc-2:chunk-2", "relationship_to_question": "CONTEXTUAL_ONLY"},
                    {"source_id": "doc-3:chunk-3", "relationship_to_question": "CONTEXTUAL_ONLY"},
                ],
            },
            "inference_calls": [],
        }
        retrieval = {
            "results": [
                {"document_id": "doc-1", "chunk_id": "chunk-1"},
                {"document_id": "doc-2", "chunk_id": "chunk-2"},
                {"document_id": "doc-3", "chunk_id": "chunk-3"},
            ],
            "transparency": {"resolved_entities": [], "query_variants": []},
        }
        result = analysis._project_staged_exploratory_response(pipeline, retrieval)
        self.assertEqual(result["answer_origin"], "qwen_cited_evidence_synthesis")
        self.assertIn("shared publication context. [1, 2]", result["answer"])
        self.assertIn("qualified contextual detail. [3]", result["answer"])

    def test_selected_document_passage_stays_in_sources_when_model_misses_direct_support(self):
        pipeline = {
            "final_synthesis": {"answer": "The aims are not established.", "cross_source_inferences": []},
            "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []},
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
                "source_classifications": [{"source_id": "doc-1:chunk-1", "relationship_to_question": "NO_RELEVANT_PASSAGE"}],
            },
            "inference_calls": [],
        }
        retrieval = {
            "results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Selected programme", "text": "The programme aims to establish teacher cadres.", "page_start": 3}],
            "transparency": {"strategy": "explicit_document_selection_v1", "resolved_entities": [], "query_variants": []},
        }
        result = analysis._project_staged_exploratory_response(pipeline, retrieval)
        self.assertEqual(result["answer_origin"], "unvalidated_source_passages")
        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertNotIn("The programme aims to establish teacher cadres.", result["answer"])

    def test_frayling_interview_projects_testimony_type_from_registered_document_identity(self):
        retrieval = FakeRetrievalService()
        with patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval):
            result = analysis._retrieve_exploratory(analysis.ExploratoryInterrogationRequest(
                query="What does Christopher Frayling say?",
                target_document_ids=["doc_930287260339_cf797b8d4ce2"],
                mode="exploratory",
            ))
        source = result["results"][0]
        self.assertEqual(source["source_type_projection"]["value"], "Later oral testimony / interview")
        self.assertEqual(source["temporal_class"], "Later testimony (June 2013)")

    def test_catalogue_response_labels_direct_project_register_results(self):
        retrieval = {"results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Project report", "pid": "123", "page_start": 2}]}
        authority_evidence = [{"authority_type": "ddr_projects", "authority_id": "83", "fields": {"title": "Patterns of educational purchases", "start_year": 1972, "end_year": 1972, "project_lead_name": "Richard Langdon"}}]
        result = analysis._catalogue_response("What projects did Richard Langdon work on?", retrieval, authority_evidence)
        self.assertTrue(result["answer"].startswith("Projects in the register"))
        self.assertIn("Authority-register results (not documentary quotations):", result["answer"])
        self.assertIn("Job 83: Patterns of educational purchases", result["answer"])

    def test_exact_job_lookup_does_not_present_unrelated_documentary_records(self):
        retrieval = {"results": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Unrelated report", "pid": "123", "page_start": 2}]}
        authority_evidence = [{"authority_type": "ddr_projects", "authority_id": "31", "fields": {"title": "Safe design of metal cutting guillotines", "project_lead_name": "Anthony Smallhorn"}}]
        result = analysis._catalogue_response("What is Job 31?", retrieval, authority_evidence)
        self.assertIn("Job 31: Safe design of metal cutting guillotines", result["answer"])
        self.assertNotIn("Unrelated report", result["answer"])

    def test_catalogue_question_detection_includes_direct_authority_questions(self):
        self.assertEqual(analysis._catalogue_question_subject("Which students are recorded in the DDR register?"), "Which students are recorded in the DDR register")
        self.assertEqual(analysis._catalogue_question_subject("What is Job 31?"), "What is Job 31")
        self.assertEqual(analysis._catalogue_question_subject("When was the DDR formally constituted?"), "When was the DDR formally constituted")
        self.assertEqual(analysis._catalogue_question_subject("What was Bruce Archer's involvement at DDR?"), "Bruce Archer")
        self.assertEqual(analysis._catalogue_question_subject("What was Janet Daley's involvement with the DDR?"), "Janet Daley")
        self.assertEqual(analysis._catalogue_question_subject("What role did Bruce Archer hold?"), "Bruce Archer")
        self.assertEqual(analysis._catalogue_question_subject("When did Bruce Archer work at DDR?"), "Bruce Archer")
        self.assertEqual(analysis._catalogue_question_subject("List the documents Bruce Archer worked on"), "Bruce Archer")

    def test_according_to_authority_question_bypasses_documentary_and_qwen(self):
        authority = [{"authority_type": "ddr_projects", "authority_id": "171", "fields": {"title": "Job 171", "project_lead_name": "Pierre Goumain", "start_year": 1977, "end_year": 1979}}]
        with patch.object(analysis, "_catalogue_authorities", return_value=authority), patch.object(
            analysis, "_retrieve_exploratory"
        ) as retrieval, patch.object(analysis, "get_inference_service") as inference, patch.object(
            analysis, "StagedEvidencePipeline"
        ) as pipeline:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(
                analysis.ExploratoryInterrogationRequest(
                    query="According to the project authority, who led Job 171, who funded it, and what duration is recorded?",
                    mode="exploratory",
                )
            ))

        retrieval.assert_not_called()
        inference.assert_not_called()
        pipeline.assert_not_called()
        self.assertEqual(result["retrieval"]["strategy"], "deterministic_authority_lookup_v1")
        self.assertEqual(result["authority_evidence"], authority)
        self.assertEqual(result["stage_execution"]["call_count"], 0)

    def test_hybrid_authority_question_keeps_documentary_pipeline(self):
        authority = [{"authority_type": "ddr_projects", "authority_id": "171", "fields": {"title": "Job 171", "project_lead_name": "Pierre Goumain"}}]
        retrieval = FakeRetrievalService().retrieve(None, "Hybrid question", 8, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        with patch.object(analysis, "_catalogue_authorities", return_value=authority), patch.object(
            analysis, "_retrieve_exploratory", return_value=retrieval
        ), patch.object(analysis, "_build_exploratory_packets", return_value=[object()]), patch.object(
            analysis, "get_inference_service", return_value=FakeInference()
        ), patch.object(analysis, "StagedEvidencePipeline", FakePipeline):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(
                analysis.ExploratoryInterrogationRequest(
                    query="What does the project authority establish about Job 171, and what do its surviving reports show?",
                    mode="exploratory",
                )
            ))

        self.assertEqual(result["authority_evidence"], authority)
        self.assertEqual(result["stage_execution"]["call_count"], 3)

    def test_hybrid_teaching_question_preserves_authority_with_controlled_preset(self):
        authority = [{"authority_type": "agent_employment", "authority_id": "RICHARDLAN", "fields": {"label": "Richard Langdon", "job_title_label": "Deputy Head of Department (Teaching)", "start_date": "1967-01-01", "end_date": "1985-12-31"}}]
        retrieval = FakeRetrievalService().retrieve(None, "Richard Langdon", 8, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        retrieval["transparency"]["route_family"] = "HYBRID_AUTHORITY_DOCUMENTARY"
        with patch.object(analysis, "_catalogue_authorities", return_value=authority) as authorities, patch.object(
            analysis, "_retrieve_exploratory", return_value=retrieval
        ), patch.object(analysis, "_build_exploratory_packets", return_value=[object()]), patch.object(
            analysis, "get_inference_service", return_value=FakeInference()
        ), patch.object(analysis, "StagedEvidencePipeline", FakePipeline):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(
                analysis.ExploratoryInterrogationRequest(
                    query="What does the database record establish about Richard Langdon's formal DDR role, and what do his surviving teaching records show about his curriculum and teaching practice?",
                    mode="exploratory",
                )
            ))

        authorities.assert_called_once()
        self.assertEqual(result["authority_evidence"], authority)
        self.assertEqual(result["answer_paragraphs"][0]["claims"][0]["authority_numbers"], [1])
        self.assertEqual(result["final_claim_plan"]["claims"][0]["supporting_authority_ids"], ["RICHARDLAN"])

    def test_hybrid_failure_preserves_authority_and_documentary_provenance(self):
        class FailingPipeline:
            def __init__(self, _inference):
                pass

            async def run(self, *_args, **_kwargs):
                raise analysis.EvidencePipelineStageError("source_analysis", {}, {})

        authority = [{"authority_type": "ddr_projects", "authority_id": "171", "fields": {"title": "Job 171", "project_lead_name": "Pierre Goumain"}}]
        retrieval = FakeRetrievalService().retrieve(None, "Hybrid question", 8, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        with patch.object(analysis, "_catalogue_authorities", return_value=authority), patch.object(
            analysis, "_retrieve_exploratory", return_value=retrieval
        ), patch.object(analysis, "_build_exploratory_packets", return_value=[object()]), patch.object(
            analysis, "get_inference_service", return_value=FakeInference()
        ), patch.object(analysis, "StagedEvidencePipeline", FailingPipeline):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(
                analysis.ExploratoryInterrogationRequest(
                    query="What does the project authority establish about Job 171, and what do its surviving reports show?",
                    mode="exploratory",
                )
            ))

        self.assertEqual(result["answer_state"], "synthesis_unavailable")
        self.assertEqual(result["authority_evidence"], authority)
        self.assertEqual(len(result["retrieved_evidence"]), 1)
        self.assertEqual(result["stage_execution"]["records"]["source_analysis"]["status"], "failed")
        self.assertTrue(result["evidence_anchors"])

    def test_analytical_document_question_bypasses_catalogue_shortcut(self):
        self.assertIsNone(analysis._catalogue_question_subject(
            "What are the key takeaways from the teaching and learning documents in the archive?"
        ))

    def test_teaching_preset_bypasses_person_authority_retrieval(self):
        class ThematicPipeline(FakePipeline):
            run_kwargs = None

            async def run(self, query, packets, **kwargs):
                type(self).run_kwargs = kwargs
                return await super().run(query, packets, **kwargs)

        retrieval = FakeRetrievalService().retrieve(
            None,
            "What are the key takeaways from the teaching and learning documents in the archive?",
            8,
            analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION,
        )
        with patch.object(analysis, "_catalogue_authorities") as authorities, patch.object(
            analysis, "_retrieve_exploratory", return_value=retrieval
        ), patch.object(analysis, "_build_exploratory_packets", return_value=[object()]), patch.object(
            analysis, "get_inference_service", return_value=FakeInference()
        ), patch.object(analysis, "StagedEvidencePipeline", ThematicPipeline):
            asyncio.run(analysis.interrogate_exploratory_corpus(
                analysis.ExploratoryInterrogationRequest(
                    query="What are the key takeaways from the teaching and learning documents in the archive?",
                    mode="exploratory",
                )
            ))

        authorities.assert_not_called()
        self.assertTrue(ThematicPipeline.run_kwargs["thematic_document_question"])

    def test_catalogue_response_renders_employment_role_and_tenure(self):
        authority = [{"authority_type": "agent_employment", "authority_id": "BA", "fields": {"label": "Bruce Archer", "job_title_label": "Professor", "start_date": "1972", "end_date": "1986"}}]
        result = analysis._catalogue_response("What was Bruce Archer's involvement at DDR?", {"results": []}, authority)
        self.assertIn("Bruce Archer: Professor (1972 to 1986)", result["answer"])

    def test_authority_defined_answers_exclude_incidental_document_records(self):
        authority = [{"authority_type": "ddr_projects", "authority_id": "31", "fields": {"title": "Safe design", "project_lead_name": "Anthony Smallhorn"}}]
        result = analysis._catalogue_response("What is Job 31?", {"results": [{"title": "Unrelated report", "pid": "123", "page_start": 2}]}, authority)
        self.assertIn("Job 31: Safe design", result["answer"])
        self.assertNotIn("Unrelated report", result["answer"])

    def test_project_authority_response_uses_only_requested_project_fields(self):
        authorities = [
            {"authority_type": "ddr_projects", "authority_id": "171", "fields": {"project_lead_name": "Pierre Goumain", "funder_name": "Science Research Council", "duration_text": "<= 12 months"}},
            {"authority_type": "agent_employment", "authority_id": "RICHARDLAN", "fields": {"label": "Richard Langdon"}},
        ]
        result = analysis._catalogue_response("According to the project authority, who led Job 171, who funded it, and what duration is recorded?", {"results": []}, authorities)
        self.assertIn("Pierre Goumain", result["answer"])
        self.assertIn("Science Research Council", result["answer"])
        self.assertEqual(result["used_authorities"], [authorities[0]])
        self.assertEqual(result["unused_authorities"], [authorities[1]])

    def test_source_analysis_projection_preserves_success_and_failure_records(self):
        results, summary = analysis._source_analysis_projection([
            {"packet": {"source_id": "source-1"}, "status": "success", "analysis": {"relationship_to_question": "DIRECT_SUPPORT", "direct_claims": [{"claim": "Supported"}]}, "duration_ms": 1000},
            {"packet": {"source_id": "source-2"}, "status": "failed", "failure_code": "ValidationError", "failure_message": "bad JSON"},
        ])
        self.assertEqual([item["status"] for item in results], ["success", "failed"])
        self.assertEqual(results[1]["failure_code"], "ValidationError")
        self.assertEqual(summary, {"attempted_sources": 2, "successful_sources": 1, "failed_sources": 1, "direct_support_sources": 1, "contextual_sources": 0, "inference_only_sources": 0, "not_relevant_sources": 0, "source_analysis_stage_status": "partial"})

    def test_collection_membership_response_labels_parent_record_scope(self):
        records = [{"record_pid": "873981573030", "record_title": "Bruce Archer collection", "attached_media_pid": "338541406157", "asset_pid": "023074909505", "title": "Bruce Archer draft", "display_date": "Circa 1979"}]
        result = analysis._collection_membership_response("Bruce Archer", records)
        self.assertIn("Record PID 873981573030", result["answer"])
        self.assertIn("Media PID 338541406157", result["answer"])
        self.assertIn("does not by itself establish authorship", result["answer"])

    def test_generic_model_limit_is_made_source_specific(self):
        pipeline = {"final_synthesis": {"answer": "The DDR documents do not provide direct documentary evidence describing design research.", "cross_source_inferences": []}, "cross_source_analysis": {"cross_source_inferences": [], "differences_or_contradictions": []}, "evidence_map": {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": []}, "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}}, "inference_calls": []}
        retrieval = {"results": [{"document_id": "doc-1", "title": "DDR record", "pid": "123", "page_start": 4, "provenance": {}}], "transparency": {"resolved_entities": [], "query_variants": []}}
        result = analysis._project_staged_exploratory_response(pipeline, retrieval)
        self.assertIn("DDR record (Asset PID 123, p. 4)", result["answer"])

    def test_catalogue_authority_selection_includes_degree_thesis_and_constitution_questions(self):
        with patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis.AuthorityRegistry, "resolve", return_value=[] ) as resolve:
            analysis._catalogue_authorities("What was Eileen Adams's degree?")
            self.assertIn("ref_students", resolve.call_args.args[2])
            analysis._catalogue_authorities("When was the DDR formally constituted?")
            self.assertIn("ref_ddr_period", resolve.call_args.args[2])

    def test_exact_job_project_lead_query_excludes_unrelated_authority_types(self):
        queries = [
            (
                "Who is recorded as project lead for Job 181, and what does the surviving "
                "Job 181 report say about internal representations in architectural design?"
            ),
            (
                "Who does the database authority record as leading and funding Job 171, "
                "and what do the surviving reports themselves identify as the project's research needs?"
            ),
            (
                "Who is recorded as leading and funding Job 97, and what does the surviving report "
                "establish about the feasibility of computer-aided architectural design for METHOD building?"
            ),
        ]
        for query in queries:
            with self.subTest(query=query), patch.object(
                analysis, "LocalSessionLocal", return_value=FakeDatabase()
            ), patch.object(analysis.AuthorityRegistry, "resolve", return_value=[]) as resolve:
                analysis._catalogue_authorities(query)

            self.assertEqual(resolve.call_args.args[2], ["ddr_projects"])

    def test_catalogue_authority_lookup_failure_keeps_retrieval_available(self):
        from sqlalchemy.exc import ProgrammingError

        with patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(
            analysis.AuthorityRegistry,
            "resolve",
            side_effect=ProgrammingError("SELECT", {}, Exception("database_authorities is absent")),
        ):
            self.assertEqual(
                analysis._catalogue_authorities("Why did the Department of Design Research close?"),
                [],
            )

    def test_named_period_matches_period_register_label(self):
        rows = [{"authority_id": "1973-79", "label": "Peak productivity", "description": "A register description.", "code": None, "metadata": {}}]
        self.assertEqual(analysis.AuthorityRegistry._period_matches("What did the Peak productivity period cover?", rows), rows)

    def test_catalogue_response_includes_period_range(self):
        result = analysis._catalogue_response("When was the DDR formally constituted?", {"results": []}, [{"authority_type": "ref_ddr_period", "authority_id": "1972-73", "fields": {"label": "Formal constitution of DDR", "description": "DDR formally constituted."}}])
        self.assertIn("1972-73 - Formal constitution of DDR", result["answer"])

    def test_catalogue_authority_result_does_not_require_a_documentary_chunk(self):
        class EmptyRetrievalService(FakeRetrievalService):
            def retrieve(self, _db, query, top_k, corpus_version):
                result = super().retrieve(_db, query, top_k, corpus_version)
                result["results"] = []
                return result

        authority = [{"authority_type": "ddr_projects", "authority_id": "31", "fields": {"title": "Safe design of metal cutting guillotines", "start_year": 1966, "end_year": 1966, "project_lead_name": "Anthony Smallhorn"}}]
        with patch.object(analysis, "get_inference_service") as inference, patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=EmptyRetrievalService()), patch.object(analysis, "_catalogue_authorities", return_value=authority), patch.object(analysis, "StagedEvidencePipeline") as pipeline:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="What is Job 31?", mode="exploratory")))
        inference.assert_not_called()
        pipeline.assert_not_called()
        self.assertEqual(result["answer_origin"], "deterministic_catalogue_result")
        self.assertIn("Job 31: Safe design of metal cutting guillotines", result["answer"])

    def test_catalogue_authority_result_survives_retrieval_rejection(self):
        authority = [{"authority_type": "ref_ddr_period", "authority_id": "1972-73", "fields": {"label": "Formal constitution of DDR", "description": "DDR formally constituted."}}]
        with patch.object(analysis, "_retrieve_exploratory", side_effect=analysis.HTTPException(status_code=422, detail="No usable query terms")), patch.object(analysis, "_catalogue_authorities", return_value=authority), patch.object(analysis, "get_inference_service") as inference:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="When was the DDR formally constituted?", mode="exploratory")))
        inference.assert_not_called()
        self.assertEqual(result["answer_origin"], "deterministic_catalogue_result")
        self.assertIn("Formal constitution of DDR", result["answer"])

    def test_interrogation_uses_successor_corpus_and_reports_it(self):
        inference = FakeInference()
        retrieval = FakeRetrievalService()
        with patch.object(analysis, "get_inference_service", return_value=inference), patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval), patch.object(analysis, "EvidencePacketBuilder", return_value=FakePacketBuilder()), patch.object(analysis, "StagedEvidencePipeline", FakePipeline):
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="Known archive-first question", mode="exploratory")))
        self.assertEqual(retrieval.corpus_version, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        self.assertEqual(result["corpus_version"], analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)

    def test_one_shot_capture_uses_one_qwen_call_and_persists_non_historical_capture(self):
        inference = FakeInference()
        retrieval = FakeRetrievalService()
        capture = FakeCaptureService()
        canonical_q01 = 'What documentary traces connect Job 171, "Designer-computer interaction in the early stages of design”, to the people, activities and outputs associated with it?'
        with patch.object(analysis, "get_inference_service", return_value=inference), patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=retrieval), patch.object(analysis, "ResearcherUiCaptureService", return_value=capture), patch.object(analysis, "StagedEvidencePipeline") as pipeline:
            result = asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query=canonical_q01, mode="archive_first_one_shot", question_id="Q01")))
        pipeline.assert_not_called()
        self.assertEqual(inference.one_shot_calls, 1)
        self.assertEqual(retrieval.corpus_version, analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        self.assertTrue(result["persisted"])
        self.assertEqual(result["capture_id"], "researcher-ui-capture-test")
        self.assertEqual(result["mode"], "archive_first_one_shot")
        self.assertEqual(result["question_id"], "Q01")
        self.assertEqual(result["corpus_version"], analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        self.assertEqual(capture.payload["corpus_version"], analysis.settings.TURIN_ARCHIVE_FIRST_CORPUS_VERSION)
        self.assertEqual(capture.payload["question_id"], "Q01")
        self.assertEqual(capture.payload["exact_question"], canonical_q01)
        self.assertEqual(capture.payload["source_classifications"], [{"source_id": "S1", "classification": "NO_RELEVANT_PASSAGE"}])

    def test_non_exploratory_mode_is_rejected_without_formal_fallback(self):
        with self.assertRaises(ValidationError):
            analysis.ExploratoryInterrogationRequest(query="A query", mode="formal")

    def test_inference_timeout_is_a_structured_gateway_timeout(self):
        inference = FakeInference()
        with patch.object(analysis, "get_inference_service", return_value=inference), patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinArchiveFirstRetrievalService", return_value=FakeRetrievalService()), patch.object(analysis, "EvidencePacketBuilder", return_value=FakePacketBuilder()), patch.object(analysis, "StagedEvidencePipeline") as pipeline:
            pipeline.return_value.run.side_effect = InferenceTimeoutError("source_analysis", 1200, {})
            with self.assertRaises(Exception) as raised:
                asyncio.run(analysis.interrogate_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="Neutral query", mode="exploratory")))
        self.assertEqual(raised.exception.status_code, 504)
        self.assertEqual(raised.exception.detail["error"], "inference_timeout")
        self.assertEqual(raised.exception.detail["stage"], "source_analysis")

    def test_v3_retrieve_is_model_neutral_and_non_persistent(self):
        with patch.object(analysis, "LocalSessionLocal", return_value=FakeDatabase()), patch.object(analysis, "TurinRetrievalV3Service", return_value=FakeV3RetrievalService()), patch.object(analysis, "get_inference_service") as inference:
            result = asyncio.run(analysis.retrieve_exploratory_corpus(analysis.ExploratoryInterrogationRequest(query="Example Person teaching"), v=3))
        inference.assert_not_called()
        self.assertEqual(result["version"], 3)
        self.assertFalse(result["persisted"])
        self.assertFalse(result["model_inference"])
        self.assertEqual(result["retrieval_adequacy"]["status"], "RETRIEVAL_SUFFICIENT")


if __name__ == "__main__":
    unittest.main()