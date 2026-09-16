import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_archive_first_retrieval_service import TurinArchiveFirstRetrievalService
from app.services.turin_question_policy import matching_turin_question_policy, validate_turin_question_policies


class ArchiveFirstNominationTests(unittest.TestCase):
    def test_q05_document_page_reservation_is_declared_and_valid(self):
        policy = matching_turin_question_policy(
            "How was design research understood within the DDR, and to what extent do the surviving documents present a consistent conception of it?"
        )

        self.assertIsNotNone(policy)
        self.assertEqual(policy.reservation_type, "CONFIGURED_DOCUMENT_PAGES")
        self.assertEqual(policy.document_pages, (
            ("doc_321843234637_764a8e8c3451", 2),
            ("doc_321843234637_ce936558310b", 34),
            ("doc_338541406157_15ef98daa711", 9),
            ("doc_259848197772_8cb8bebecae7", 33),
        ))
        validate_turin_question_policies()

    def test_empty_chunk_reservation_skips_the_document_query(self):
        class Database:
            def execute(self, *_args, **_kwargs):
                raise AssertionError("empty configured reservations must not query document chunks")

        results = TurinArchiveFirstRetrievalService()._configured_reservation_results(
            Database(),
            "What documentary traces connect Job 171, Designer-computer interaction in the early stages of design, to the people, activities and outputs associated with it?",
        )

        self.assertEqual(results, [])

    def test_stage_fallbacks_are_declared_by_policy(self):
        temporal_policy = matching_turin_question_policy(
            "How do contemporary DDR documents and later retrospective accounts differ in their descriptions of the Design Education Unit?"
        )
        missingness_policy = matching_turin_question_policy(
            "Does the current digitised corpus establish why the decision to close the DDR was made?"
        )

        self.assertEqual(temporal_policy.stage_fallback, {"final_synthesis": "EMPTY_TYPED_SYNTHESIS"})
        self.assertEqual(missingness_policy.stage_fallback, {"source_analysis": "CONTEXTUAL_ONLY"})

    def test_quoted_concepts_preserve_explicit_multi_word_concepts(self):
        self.assertEqual(
            TurinArchiveFirstRetrievalService._quoted_concepts(
                "How was ‘design research’ understood, compared with \"design methodology\"?"
            ),
            ["design research", "design methodology"],
        )

    def test_successor_availability_accepts_reused_document_with_successor_chunks(self):
        class Result:
            def mappings(self):
                return self

            def first(self):
                return {
                    "document_id": "frozen-document",
                    "source_uri": "https://example.test/source.pdf",
                    "source_path": "/app/source.pdf",
                    "processing_status": "completed",
                    "ml_policy_status": "eligible_unrestricted",
                    "docling_text_available": True,
                }

        class Database:
            def __init__(self):
                self.statement = ""

            def execute(self, statement, _params):
                self.statement = str(statement)
                return Result()

        database = Database()
        availability = TurinArchiveFirstRetrievalService._availability(
            database,
            {"asset_pid": "asset-pid", "asset_id": "asset-id", "use_for_ml": True},
            "corpus_turin_archive_first_cc11e8678168",
        )

        self.assertEqual(availability["classification"], "DOCLING_TEXT_AVAILABLE")
        self.assertNotIn("d.corpus_version = :corpus_version", database.statement)

    def test_q02_assets_are_nominated_from_structured_metadata_before_document_availability(self):
        service = TurinArchiveFirstRetrievalService()
        plan = {
            "normalised_query": "How is Bruce Archer's role in teaching and learning practice with students represented?",
            "resolved_entities": [{"label": "Bruce Archer"}],
        }
        assets = [
            {"asset_pid": "062054716175", "label": "Professor Archer course, spring term", "keywords": ["L Bruce Archer", "Introduction to Design Research", "Postgraduate education"]},
            {"asset_pid": "852120727979", "label": "Memo from Frank Height to Bruce Archer on allocation of tutorial days of research staff", "keywords": ["Bruce Archer", "Tutorial days", "Teaching allocation"]},
            {"asset_pid": "723660822664", "label": "Richard Langdon introductory week, autumn term", "keywords": ["Bruce Archer", "Design research courses", "Student orientation"]},
        ]
        nominated = [service._candidate_matches(asset, plan) for asset in assets]
        self.assertTrue(all(item["score"] > 0 for item in nominated))
        self.assertTrue(all(item["nomination_reasons"] for item in nominated))

    def test_source_family_topic_alignment_outranks_repeated_person_anchor_matches(self):
        service = TurinArchiveFirstRetrievalService()
        plan = {
            "normalised_query": "How is Bruce Archer's teaching and learning role with students represented?",
            "resolved_entities": [{"label": "Bruce Archer"}],
        }
        teaching_family = service._candidate_matches({
            "record_title": "DDR teaching and learning practice lectures",
            "label": "Professor Archer course, spring term",
            "keywords": ["L Bruce Archer"],
        }, plan)
        generic_person_match = service._candidate_matches({
            "record_title": "Bruce Archer collection",
            "attached_media_title": "Bruce Archer notes",
            "label": "Bruce Archer notes",
            "keywords": ["Bruce Archer"],
            "box_title": "Bruce Archer papers",
        }, plan)
        self.assertGreater(teaching_family["score"], generic_person_match["score"])
        self.assertTrue(any(reason["match"] == "source_family_topic_alignment" for reason in teaching_family["nomination_reasons"]))
        self.assertEqual(generic_person_match["score"], 10)

    def test_page_scope_excludes_documentary_pages_outside_ml_permission(self):
        self.assertTrue(TurinArchiveFirstRetrievalService._page_permitted(2, "1-3"))
        self.assertFalse(TurinArchiveFirstRetrievalService._page_permitted(4, "1-3"))
        self.assertTrue(TurinArchiveFirstRetrievalService._page_permitted(4, "all_pages"))

    def test_oral_history_coverage_accounts_for_checked_nominated_selected_and_excluded_assets(self):
        assets = [
            {"asset_pid": "oral-1", "use_for_ml": True, "source_type": "Oral history interview"},
            {"asset_pid": "oral-2", "use_for_ml": True, "label": "Interview with witness"},
            {"asset_pid": "report-1", "use_for_ml": True, "source_type": "Report"},
        ]
        coverage = TurinArchiveFirstRetrievalService._oral_history_coverage(
            assets, [{"asset_pid": "oral-1"}], [{"asset_pid": "oral-1"}], required=True
        )

        self.assertEqual(coverage, {"review_required": True, "eligible_assets_checked": 2, "nominated": 1, "selected": 1, "excluded_for_relevance": 1})

    def test_source_family_diagnostics_detects_missing_declared_family(self):
        assets = [
            {"asset_pid": "report-1", "use_for_ml": True, "source_type": "Report"},
            {"asset_pid": "oral-1", "use_for_ml": True, "source_type": "Oral history interview"},
        ]
        diagnostics = TurinArchiveFirstRetrievalService._source_family_diagnostics(
            {"documentary", "oral_history"}, assets, [{"asset_pid": "report-1"}]
        )

        self.assertEqual(diagnostics["selected"], ["documentary"])
        self.assertEqual(diagnostics["unmet"], ["oral_history"])
        self.assertFalse(diagnostics["requirements_satisfied"])

    def test_authority_asset_coverage_uses_only_controlled_people_and_alias_fields(self):
        assets = [
            {"asset_pid": "asset-1", "use_for_ml": True, "people": ["Asha Bell"]},
            {"asset_pid": "asset-2", "use_for_ml": True, "controlled_aliases": ["Asha Bell"]},
            {"asset_pid": "asset-3", "use_for_ml": True, "label": "Asha Bell mentioned in title"},
        ]
        coverage = TurinArchiveFirstRetrievalService._authority_asset_coverage(
            assets,
            {"resolved_entities": [{"authority_type": "agent", "authority_id": "ASHA", "label": "Asha Bell"}]},
            [{"asset_pid": "asset-2"}],
            required=True,
        )

        self.assertEqual(coverage["controlled_linked_asset_ids"], ["asset-1", "asset-2"])
        self.assertEqual(coverage["selected_controlled_linked_asset_count"], 1)
        self.assertEqual(coverage["resolved_authorities"][0]["authority_id"], "ASHA")
        self.assertEqual(coverage["coverage_status"], "COMPLETE")

    def test_authority_asset_coverage_flags_missing_controlled_linkage(self):
        coverage = TurinArchiveFirstRetrievalService._authority_asset_coverage(
            [{"asset_pid": "asset-1", "use_for_ml": True, "label": "Asha Bell title mention"}],
            {"resolved_entities": [{"authority_type": "agent", "authority_id": "ASHA", "label": "Asha Bell"}]},
            [],
            required=True,
        )

        self.assertEqual(coverage["coverage_status"], "CONTROLLED_LINKAGE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()