import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.exploratory_retrieval_service import ExploratoryQueryPlanner, ExploratoryRetrievalService


class Rows:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self

    def all(self):
        return self.values


class AuthorityDatabase:
    def execute(self, *_args, **_kwargs):
        return Rows([
            {"authority_type": "agent_employment", "authority_id": "EXAMPLEPERSON", "label": "Example Person"},
            {"authority_type": "ddr_projects", "authority_id": "170", "label": "Design Analysis Project"},
        ])


class ExploratoryQueryPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = ExploratoryQueryPlanner()
        self.db = AuthorityDatabase()

    def test_long_natural_language_question_is_decomposed_without_low_information_terms(self):
        plan = self.planner.build_plan(self.db, "How is Example Person's teaching practice represented across multiple documents and what is directly evidenced?")
        self.assertEqual(plan["concepts"], ["teaching"])
        self.assertIn({"label": "Example Person", "authority_type": "agent_employment", "authority_id": "EXAMPLEPERSON", "source": "database_authorities"}, plan["resolved_entities"])
        self.assertIn('"Example Person"', [variant["query"] for variant in plan["query_variants"]])
        self.assertIn('"Example Person" teaching', [variant["query"] for variant in plan["query_variants"]])

    def test_project_identifier_and_quoted_title_become_inspectable_variants(self):
        plan = self.planner.build_plan(self.db, 'Find "Design Analysis Project" activity for Job 170.')
        variants = {variant["query"] for variant in plan["query_variants"]}
        self.assertIn('"Design Analysis Project"', variants)
        self.assertIn('"Job 170"', variants)

    def test_variants_are_deterministic_and_bounded(self):
        query = "Example Person and design learning in the department"
        self.assertEqual(self.planner.build_plan(self.db, query), self.planner.build_plan(self.db, query))
        self.assertLessEqual(len(self.planner.build_plan(self.db, query)["query_variants"]), 10)

    def test_no_entity_question_still_has_concept_anchors(self):
        plan = self.planner.build_plan(self.db, "Find unrecorded hypothetical taxonomy")
        self.assertEqual(plan["resolved_entities"], [])
        self.assertGreater(len(plan["query_variants"]), 0)

    def test_source_diversity_selects_one_strongest_candidate_per_document_first(self):
        candidates = [
            {"chunk_id": "chunk-1", "document_id": "doc-a", "score": 0.9},
            {"chunk_id": "chunk-2", "document_id": "doc-a", "score": 0.8},
            {"chunk_id": "chunk-3", "document_id": "doc-b", "score": 0.7},
        ]
        selected = ExploratoryRetrievalService._select_diverse_sources(candidates, 2)
        self.assertEqual([item["chunk_id"] for item in selected], ["chunk-1", "chunk-3"])

    def test_derivative_identity_and_metadata_text_fusion_are_canonical(self):
        candidates = {}
        text_candidate = {"document_id": "doc-master", "asset_id": "asset-1", "asset_pid": "master", "chunk_id": "text", "score": 0.7, "text_score": 0.7, "metadata_score": 0.0, "retrieval_channels": ["TEXT_MATCH"], "metadata_matches": [], "originating_query_variants": ["variant-1"]}
        metadata_candidate = {"document_id": "doc-display", "asset_id": "asset-1", "asset_pid": "display", "chunk_id": "metadata", "score": 0.4, "text_score": 0.0, "metadata_score": 0.4, "retrieval_channels": ["METADATA_MATCH"], "metadata_matches": [{"field": "keywords", "value": "Example Person"}], "originating_query_variants": ["variant-2"]}
        ExploratoryRetrievalService._merge_source_candidate(candidates, text_candidate)
        ExploratoryRetrievalService._merge_source_candidate(candidates, metadata_candidate)
        self.assertEqual(len(candidates), 1)
        fused = next(iter(candidates.values()))
        self.assertEqual(fused["source_nomination_score"], 1.1)
        self.assertEqual(fused["source_nomination_channels"], ["METADATA_MATCH", "TEXT_MATCH"])

    def test_metadata_nominated_source_selects_deeper_informative_passage(self):
        rows = [
            {"chunk_id": "first", "chunk_text": "Imperial Chemical Industries Limited.", "score": 0.9, "source_section": None},
            {"chunk_id": "image", "chunk_text": "<!-- image -->", "score": 1.0, "source_section": None},
            {"chunk_id": "later", "chunk_text": "Example Person led tutorial sessions where students tested design research methods together.", "score": 0.2, "source_section": "Teaching"},
        ]
        selected = ExploratoryRetrievalService._select_best_passage(rows, {"example", "person", "teaching", "students"})
        self.assertEqual(selected["chunk_id"], "later")
        self.assertEqual(selected["passage_evidence_channel"] if "passage_evidence_channel" in selected else "DIRECT_TEXT_MATCH", "DIRECT_TEXT_MATCH")

    def test_metadata_only_source_has_no_eligible_documentary_passage(self):
        rows = [{"chunk_id": "image", "chunk_text": "<!-- image -->", "score": 1.0, "source_section": None}]
        self.assertIsNone(ExploratoryRetrievalService._select_best_passage(rows, {"example", "person"}))

    def test_snapshot_identity_fills_legacy_empty_document_columns(self):
        candidate = {"document_id": "doc-1", "archive_record_pid": None, "asset_pid": None, "asset_id": None, "asset_id_or_asset_pid": None}
        ExploratoryRetrievalService._apply_snapshot_identity(candidate, {"authority_data": {"record_pid": "record-1", "asset_pid": "asset-pid-1", "asset_id": "asset-id-1"}})
        self.assertEqual(candidate["archive_record_pid"], "record-1")
        self.assertEqual(candidate["asset_pid"], "asset-pid-1")
        self.assertEqual(candidate["asset_id"], "asset-id-1")


if __name__ == "__main__":
    unittest.main()