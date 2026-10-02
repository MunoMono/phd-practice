import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.retrieval_contract_service import derive_retrieval_contract
from app.services.turin_archive_first_retrieval_service import TurinArchiveFirstRetrievalService
from app.services.turin_question_route import decompose_hybrid_question
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

    def test_complete_sentence_count_prefers_prose_over_heading_and_table_fragment(self):
        prose = (
            "The curriculum introduced a structured programme of seminars and lectures, "
            "connecting design research with professional practice."
        )
        fragment = "Royal College of Art | Autumn Term 1975 | Cognitive Psychology | 1 | General concepts"

        self.assertEqual(TurinArchiveFirstRetrievalService._complete_sentence_count(prose), 1)
        self.assertEqual(TurinArchiveFirstRetrievalService._complete_sentence_count(fragment), 0)

    def test_stage_fallbacks_are_declared_by_policy(self):
        temporal_policy = matching_turin_question_policy(
            "How do contemporary DDR documents and later retrospective accounts differ in their descriptions of the Design Education Unit?"
        )
        missingness_policy = matching_turin_question_policy(
            "Does the current digitised corpus establish why the decision to close the DDR was made?"
        )

        self.assertEqual(temporal_policy.stage_fallback, {"final_synthesis": "EMPTY_TYPED_SYNTHESIS"})
        self.assertEqual(missingness_policy.stage_fallback, {"source_analysis": "CONTEXTUAL_ONLY"})

    def test_natural_language_ddr_closure_rationale_uses_sm1_reservation(self):
        policy = matching_turin_question_policy(
            "Why did the Department of Design Research close?"
        )

        self.assertIsNotNone(policy)
        self.assertEqual(policy.policy_id, "SM1")
        self.assertEqual(policy.reservation_type, "SCOPED_MISSINGNESS")

    def test_scoped_missingness_reservation_is_exclusive(self):
        service = TurinArchiveFirstRetrievalService()
        reserved_results = [
            {"document_id": "frayling", "chunk_id": "frayling-chunk"},
            {"document_id": "rector", "chunk_id": "rector-chunk"},
        ]

        with patch.object(service, "_explicit_title_document_ids", return_value=["wrong-document"]) as explicit_title, patch.object(
            service, "_configured_document_page_results", return_value=[]), patch.object(
            service, "_configured_reservation_results", return_value=reserved_results
        ), patch.object(service, "_asset_rows") as asset_rows:
            retrieval = service.retrieve(
                object(), "Why did the Department of Design Research close?", 5, "corpus-test"
            )

        self.assertEqual(retrieval["results"], reserved_results)
        self.assertEqual(retrieval["transparency"]["policy_id"], "SM1")
        self.assertTrue(retrieval["diagnostics"]["configured_reservation_exclusive"])
        explicit_title.assert_not_called()
        asset_rows.assert_not_called()

    def test_hybrid_without_documentary_clause_returns_no_documentary_retrieval(self):
        service = TurinArchiveFirstRetrievalService()
        with patch.object(service, "_configured_document_page_results", return_value=[]), patch.object(
            service, "_configured_reservation_results", return_value=[]
        ), patch.object(service, "_explicit_title_document_ids", return_value=[]), patch.object(
            service, "_is_archive_scope_overview_question", return_value=False
        ):
            retrieval = service.retrieve(
                object(),
                "According to the database record, who is recorded as leading Job 171 alongside archival context?",
                5,
                "corpus-test",
            )

        self.assertEqual(retrieval["results"], [])
        self.assertEqual(retrieval["diagnostics"]["diagnostic_state"], "DOCUMENTARY_CLAUSE_UNAVAILABLE")

    def test_multi_surface_archive_overview_backfills_across_scope_and_reports_coverage(self):
        class Rows:
            def mappings(self):
                return self

            def all(self):
                substantive = " ".join(["Documentary evidence describes teaching practice and design research."] * 8)
                return [
                    {
                        "document_id": "report", "chunk_id": "report-1", "chunk_text": substantive,
                        "title": "Contemporary teaching report",
                        "chunk_index": 1, "source_page": 2, "ml_page_scope": "all_pages",
                        "archive_record_pid": "preferred", "asset_pid": "report-asset", "score": 0.8,
                    },
                    {
                        "document_id": "interview", "chunk_id": "interview-1", "chunk_text": substantive,
                        "title": "Oral-history interview",
                        "chunk_index": 1, "source_page": 3, "ml_page_scope": "all_pages",
                        "archive_record_pid": "other", "asset_pid": "oral-asset", "score": 0.7,
                    },
                ]

        class Database:
            def __init__(self):
                self.params = None

            def execute(self, _statement, params):
                self.params = params
                return Rows()

        service = TurinArchiveFirstRetrievalService()
        database = Database()
        assets = [
            {"asset_pid": "report-asset", "source_type": "Report", "display_date": "1978"},
            {"asset_pid": "oral-asset", "source_type": "Oral history interview", "display_date": "2013"},
        ]
        with patch.object(service, "_asset_rows", return_value=assets), patch.object(
            service.mapper,
            "_result_from_row",
            side_effect=lambda row, rank: {
                "document_id": row["document_id"], "chunk_id": row["chunk_id"], "rank": rank,
            },
        ):
            retrieval = service.retrieve_archive_scope_overview(
                database,
                "How do contemporary teaching documents compare with a 2013 oral-history interview?",
                "corpus-test",
                "preferred",
                5,
            )

        self.assertTrue(database.params["allow_cross_scope"])
        self.assertEqual([result["document_id"] for result in retrieval["results"]], ["report", "interview"])
        self.assertEqual(retrieval["diagnostics"]["retrieval_coverage"]["coverage_status"], "satisfied")
        self.assertEqual(
            retrieval["diagnostics"]["retrieval_coverage"]["required_surfaces_found"],
            ["documentary", "oral_history"],
        )

    def test_explicit_title_contract_preserves_multiple_passages_from_one_report(self):
        service = TurinArchiveFirstRetrievalService()
        report_results = [
            {"document_id": "report", "chunk_id": "report-1", "title": "Electrohome lectures"},
            {"document_id": "report", "chunk_id": "report-2", "title": "Electrohome lectures"},
        ]
        with patch.object(service, "_explicit_title_document_ids", return_value=["report"]), patch.object(
            service,
            "retrieve_explicit_title_documents",
            return_value={
                "results": report_results,
                "transparency": {"strategy": "explicit_quoted_source_title_v1"},
                "diagnostics": {"retrieved_documentary_source_count": 2},
                "archival_discovery": [], "document_availability": [],
                "archival_context_only": [], "corpus_representation_gaps": [],
            },
        ):
            retrieval = service.retrieve(
                object(), "What are the key takeaways from the Electrohome lectures?", 1, "corpus-test"
            )

        self.assertEqual(len(retrieval["results"]), 2)
        self.assertTrue(retrieval["transparency"]["retrieval_contract"]["single_document_mode"])
        self.assertEqual(retrieval["diagnostics"]["retrieval_coverage"]["coverage_status"], "satisfied")

    def test_quoted_concepts_preserve_explicit_multi_word_concepts(self):
        self.assertEqual(
            TurinArchiveFirstRetrievalService._quoted_concepts(
                "How was ‘design research’ understood, compared with \"design methodology\"?"
            ),
            ["design research", "design methodology"],
        )

    def test_explicit_quoted_source_title_accepts_a_title_without_its_suffix(self):
        matches = TurinArchiveFirstRetrievalService._explicit_source_title_matches(
            'What does the draft "Development of mobile toilets" establish?',
            ["Development of mobile toilets draft", "Job 171 | Design analysis project"],
        )

        self.assertEqual(matches, ["Development of mobile toilets draft"])

    def test_explicit_unquoted_distinctive_title_routes_to_its_document(self):
        matches = TurinArchiveFirstRetrievalService._explicit_source_title_matches(
            "What does Bruce Archer's 1983 introductory lecture course, the designerly approach to knowledge, define?",
            [
                "Bruce Archer introductory lecture course outline, 'The designerly approach to knowledge'",
                "Ken Baynes proposal for redevelopment of the DEU",
            ],
        )

        self.assertEqual(matches, ["Bruce Archer introductory lecture course outline, 'The designerly approach to knowledge'"])

    def test_explicit_unquoted_distinctive_two_word_title_routes_to_its_document(self):
        matches = TurinArchiveFirstRetrievalService._explicit_source_title_matches(
            "What are the key takeaways from the Electrohome lectures?",
            ["Electrohome lectures", "Design research methods"],
        )

        self.assertEqual(matches, ["Electrohome lectures"])

    def test_exact_job_identifier_routes_to_the_matching_report_title(self):
        matches = TurinArchiveFirstRetrievalService._explicit_source_title_matches(
            "What does the surviving Job 181 report say about internal representations?",
            ["Job 181 | Internal representations", "Job 170 | Design analysis"],
        )

        self.assertEqual(matches, ["Job 181 | Internal representations"])

    def test_entity_anchor_allows_cross_scope_backfill(self):
        contract = derive_retrieval_contract(
            "What do the named researcher's course notes establish?",
            preset_id="teaching",
            entity_anchors=("Asha Bell",),
        )

        class Rows:
            @staticmethod
            def mappings():
                return Rows()

            @staticmethod
            def all():
                return []

        class Database:
            params = None

            def execute(self, _statement, params):
                self.params = params
                return Rows()

        database = Database()
        service = TurinArchiveFirstRetrievalService()
        with patch.object(service, "_asset_rows", return_value=[]):
            service.retrieve_archive_scope_overview(
                database,
                "What do the named researcher's course notes establish?",
                "corpus-test",
                "preferred",
                5,
                contract=contract,
            )

        self.assertTrue(database.params["allow_cross_scope"])

    def test_explicit_source_title_requires_three_words(self):
        matches = TurinArchiveFirstRetrievalService._explicit_source_title_matches(
            'How was "design research" understood?',
            ["Design research methods", "Development of mobile toilets draft"],
        )

        self.assertEqual(matches, [])

    def test_across_time_question_does_not_collapse_to_one_matching_title(self):
        self.assertFalse(TurinArchiveFirstRetrievalService._explicit_title_route_is_sufficient(
            "How did a researcher formulate design research across papers from the mid-1960s to the 1980s?",
            1,
        ))

    def test_single_report_question_can_use_one_matching_title(self):
        self.assertTrue(TurinArchiveFirstRetrievalService._explicit_title_route_is_sufficient(
            "What does the hospital bedstead final report show about ergonomics and testing?",
            1,
        ))

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

    def test_hybrid_documentary_nomination_excludes_authority_vocabulary(self):
        question = (
            "According to the database record, who is recorded as leading Job 171, "
            "and what do the surviving Job 171 reports establish about research needs?"
        )
        decomposition = decompose_hybrid_question(question)
        self.assertIsNotNone(decomposition)
        plan = {
            "normalised_query": decomposition.documentary_query,
            "resolved_entities": [],
        }
        service = TurinArchiveFirstRetrievalService()
        authority_match = service._candidate_matches({
            "asset_pid": "authority-only",
            "record_title": "Database record of leading and funding",
        }, plan)
        documentary_match = service._candidate_matches({
            "asset_pid": "relevant-report",
            "record_title": "Job 171 report on research needs",
        }, plan)

        self.assertEqual(authority_match["score"], 0)
        self.assertGreater(documentary_match["score"], 0)

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