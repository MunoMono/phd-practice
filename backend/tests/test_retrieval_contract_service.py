import unittest

from app.services.retrieval_contract_service import (
    FacetRequirement,
    RetrievalContract,
    derive_retrieval_contract,
    diversify_candidates,
)


class RetrievalContractTests(unittest.TestCase):
    def test_required_surfaces_and_temporal_buckets_precede_duplicate_backfill(self):
        contract = RetrievalContract(
            required_evidence_types=("documentary", "oral_history"),
            temporal_requirement="multiple_buckets",
            temporal_buckets=("1970s", "2010s"),
            minimum_distinct_sources=2,
            initial_max_chunks_per_source=1,
        )
        candidates = [
            {"document_id": "report", "chunk_id": "report-1", "title": "Teaching report", "display_date": "1979"},
            {"document_id": "report", "chunk_id": "report-2", "title": "Teaching report", "display_date": "1979"},
            {"document_id": "interview", "chunk_id": "interview-1", "title": "Interview with a witness", "display_date": "2013"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 3)

        self.assertEqual([item["chunk_id"] for item in selected[:2]], ["report-1", "interview-1"])
        self.assertEqual(coverage.coverage_status, "satisfied")
        self.assertEqual(coverage.required_surfaces_found, ("documentary", "oral_history"))
        self.assertEqual(coverage.temporal_buckets_found, ("1970s", "2010s"))

    def test_single_document_mode_allows_multiple_chunks_from_one_source(self):
        contract = RetrievalContract(
            retrieval_mode="single_document",
            minimum_distinct_sources=1,
            initial_max_chunks_per_source=8,
            single_document_mode=True,
        )
        candidates = [
            {"document_id": "report", "chunk_id": f"report-{index}", "title": "Hospital bedstead report", "display_date": "1966"}
            for index in range(3)
        ]

        selected, coverage = diversify_candidates(candidates, contract, 3)

        self.assertEqual(len(selected), 3)
        self.assertEqual(coverage.coverage_status, "satisfied")
        self.assertEqual(coverage.distinct_source_count, 1)

    def test_derived_comparison_contract_requires_testimony_and_contemporary_time(self):
        contract = derive_retrieval_contract(
            "How does a 2013 oral-history account compare with contemporary teaching material?"
        )

        self.assertEqual(contract.required_evidence_types, ("documentary", "oral_history"))
        self.assertEqual(contract.temporal_requirement, "multiple_buckets")
        self.assertEqual(contract.temporal_buckets, ())

    def test_cross_document_comparison_requires_each_named_document_role(self):
        contract = derive_retrieval_contract(
            "How did DDR teaching and Archer's papers describe the relationship between design, science and research?"
        )
        candidates = [
            {"document_id": "teaching", "title": "DDR teaching and learning material"},
            {"document_id": "paper", "title": "Archer design research paper"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual(contract.required_document_roles, ("teaching", "paper"))
        self.assertEqual([item["document_id"] for item in selected], ["teaching", "paper"])
        self.assertEqual(coverage.document_roles_missing, ())

    def test_prospectus_contract_reports_missing_required_surface(self):
        contract = derive_retrieval_contract("How did prospectuses describe teaching across 1965-85?")

        _selected, coverage = diversify_candidates(
            [{"document_id": "report", "title": "Rector's report", "display_date": "1985"}],
            contract,
            4,
        )

        self.assertEqual(coverage.coverage_status, "partially_satisfied")
        self.assertIn("prospectus", coverage.required_surfaces_missing)

    def test_project_contract_excludes_unrelated_jobs(self):
        contract = derive_retrieval_contract(
            "What does the surviving Job 181 report say about internal representations?"
        )
        candidates = [
            {"document_id": "job-170", "title": "Job 170 report"},
            {"document_id": "job-181", "title": "Job 181 report"},
            {"document_id": "job-97", "title": "Job 97 report"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 4)

        self.assertEqual([item["document_id"] for item in selected], ["job-181"])
        self.assertTrue(coverage.target_project_evidence_found)
        self.assertEqual(coverage.required_surfaces_found, ("documentary", "project_report"))

    def test_comparative_project_contract_preserves_each_explicit_job_anchor(self):
        contract = derive_retrieval_contract(
            "How do Jobs 146 and 175 documents differ in control-room design and implementation?"
        )

        self.assertEqual(contract.project_anchors, ("146", "175"))
        self.assertIn("project_report", contract.required_evidence_types)

    def test_comparative_project_selection_requires_each_project_family_before_duplicates(self):
        contract = derive_retrieval_contract(
            "How do Jobs 146 and 175 documents differ in control-room design and implementation?"
        )
        candidates = [
            {"document_id": "job-170", "chunk_id": "170", "title": "Job 170 design analysis report"},
            {"document_id": "job-146-a", "chunk_id": "146-a", "title": "Job 146 control room systems analysis"},
            {"document_id": "job-146-b", "chunk_id": "146-b", "title": "Job 146 controller console report"},
            {"document_id": "job-175", "chunk_id": "175", "title": "Job 175 control room implementation report"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual([item["document_id"] for item in selected], ["job-146-a", "job-175"])
        self.assertEqual(coverage.project_anchors_found, ("146", "175"))
        self.assertEqual(coverage.project_anchors_missing, ())

    def test_shared_project_document_retains_explicit_attribution_to_both_requested_jobs(self):
        contract = derive_retrieval_contract(
            "How do Jobs 146 and 175 documents differ in control-room design and implementation?"
        )
        candidates = [
            {"document_id": "shared", "chunk_id": "shared", "title": "Jobs 146 and 175 joint control room report"},
            {"document_id": "generic", "chunk_id": "generic", "title": "Control room design background paper"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual([item["document_id"] for item in selected], ["shared"])
        self.assertEqual(selected[0]["project_anchor_matches"], ["146", "175"])
        self.assertEqual(coverage.project_anchors_found, ("146", "175"))

    def test_project_comparison_does_not_require_authority_side_person_in_every_report(self):
        contract = RetrievalContract(
            entity_anchors=("John Wood",),
            project_anchors=("146", "175"),
            required_evidence_types=("documentary", "project_report"),
            minimum_distinct_sources=2,
        )
        candidates = [
            {"document_id": "job-146", "chunk_id": "146", "title": "Job 146 John Wood control room report"},
            {"document_id": "job-175", "chunk_id": "175", "title": "Job 175 control room implementation report"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual([item["document_id"] for item in selected], ["job-146", "job-175"])
        self.assertEqual(coverage.project_anchors_missing, ())

    def test_open_temporal_contract_selects_a_second_decade(self):
        contract = RetrievalContract(
            temporal_requirement="multiple_buckets",
            minimum_distinct_sources=2,
        )
        candidates = [
            {"document_id": "early-a", "display_date": "1972"},
            {"document_id": "early-b", "display_date": "1978"},
            {"document_id": "later", "display_date": "2013"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual([item["document_id"] for item in selected], ["early-a", "later"])
        self.assertEqual(coverage.temporal_buckets_found, ("1970s", "2010s"))
        self.assertEqual(coverage.coverage_status, "satisfied")

    def test_explicit_period_bounds_exclude_later_candidates(self):
        contract = derive_retrieval_contract(
            "How did institutional records change across 1965-85?"
        )
        candidates = [
            {"document_id": "early", "display_date": "1967"},
            {"document_id": "late", "display_date": "1984"},
            {"document_id": "retrospective", "display_date": "2013"},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 3)

        self.assertEqual([item["document_id"] for item in selected], ["early", "late"])
        self.assertEqual((contract.temporal_start_year, contract.temporal_end_year), (1965, 1985))
        self.assertEqual(coverage.temporal_buckets_found, ("1960s", "1980s"))

    def test_entity_anchor_preserves_target_person(self):
        contract = RetrievalContract(entity_anchors=("Patrick Purcell",), minimum_distinct_sources=1)
        candidates = [
            {"document_id": "mallen", "text": "George Mallen taught computing."},
            {"document_id": "purcell", "text": "Patrick Purcell wrote the course note."},
        ]

        selected, coverage = diversify_candidates(candidates, contract, 2)

        self.assertEqual([item["document_id"] for item in selected], ["purcell"])
        self.assertTrue(coverage.target_entity_evidence_found)

    def test_derived_contract_retains_resolved_entity_anchors(self):
        contract = derive_retrieval_contract(
            "How did the named researcher describe computing?",
            entity_anchors=("Patrick Purcell",),
        )

        self.assertEqual(contract.entity_anchors, ("Patrick Purcell",))

    def test_duplicate_source_is_suppressed_until_distinct_minimum_is_met(self):
        contract = RetrievalContract(minimum_distinct_sources=2, initial_max_chunks_per_source=1)
        candidates = [
            {"document_id": "one", "chunk_id": "one-a"},
            {"document_id": "one", "chunk_id": "one-b"},
            {"document_id": "two", "chunk_id": "two-a"},
        ]

        selected, _coverage = diversify_candidates(candidates, contract, 3)

        self.assertEqual([item["chunk_id"] for item in selected[:2]], ["one-a", "two-a"])

    def test_temporal_contract_reports_partial_coverage_for_one_bucket(self):
        contract = RetrievalContract(
            temporal_requirement="multiple_buckets",
            temporal_buckets=("1970s", "2010s"),
            minimum_distinct_sources=1,
        )

        _selected, coverage = diversify_candidates(
            [{"document_id": "early", "display_date": "1976"}], contract, 2
        )

        self.assertEqual(coverage.coverage_status, "partially_satisfied")
        self.assertEqual(coverage.temporal_buckets_found, ("1970s",))

    def test_required_surface_failure_is_machine_readable_when_no_candidates_exist(self):
        contract = RetrievalContract(required_evidence_types=("oral_history",))

        selected, coverage = diversify_candidates([], contract, 2)

        self.assertEqual(selected, [])
        self.assertEqual(coverage.coverage_status, "unsatisfied")
        self.assertEqual(coverage.required_surfaces_missing, ("oral_history",))

    def test_thematic_facet_gap_remains_machine_readable(self):
        contract = RetrievalContract(
            required_facets=(
                FacetRequirement("thematic", "systems"),
                FacetRequirement("thematic", "modelling"),
            ),
            minimum_distinct_sources=1,
        )

        selected, coverage = diversify_candidates(
            [{"document_id": "systems", "chunk_text": "The course introduced systems thinking."}],
            contract,
            2,
        )

        self.assertEqual([item["document_id"] for item in selected], ["systems"])
        self.assertEqual(coverage.facets_found, (FacetRequirement("thematic", "systems"),))
        self.assertEqual(coverage.facets_missing, (FacetRequirement("thematic", "modelling"),))
        self.assertEqual(coverage.coverage_status, "partially_satisfied")

    def test_activity_and_relationship_facets_require_direct_textual_support(self):
        contract = RetrievalContract(
            required_facets=(
                FacetRequirement("activity", "modelling"),
                FacetRequirement("relationship", "collaborated"),
            ),
            minimum_distinct_sources=1,
        )

        _selected, coverage = diversify_candidates(
            [{"document_id": "association", "chunk_text": "Asha Bell and Ben Cole appear in DEU records."}],
            contract,
            2,
        )

        self.assertEqual(coverage.facets_found, ())
        self.assertEqual(
            coverage.facets_missing,
            (
                FacetRequirement("activity", "modelling"),
                FacetRequirement("relationship", "collaborated"),
            ),
        )
        self.assertEqual(coverage.coverage_status, "partially_satisfied")

    def test_derived_temporal_and_source_role_facets_are_preserved(self):
        contract = derive_retrieval_contract(
            "How do contemporary teaching records compare with later retrospective interviews?"
        )

        self.assertIn(FacetRequirement("temporal", "contemporary"), contract.required_facets)
        self.assertIn(FacetRequirement("temporal", "retrospective"), contract.required_facets)
        self.assertIn(FacetRequirement("source_role", "teaching"), contract.required_facets)

    def test_multi_facet_request_cannot_become_complete_when_one_person_is_missing(self):
        contract = RetrievalContract(
            required_facets=(
                FacetRequirement("person", "Asha Bell"),
                FacetRequirement("person", "Ben Cole"),
                FacetRequirement("activity", "modelling"),
                FacetRequirement("temporal", "contemporary"),
                FacetRequirement("source_role", "teaching"),
            ),
            minimum_distinct_sources=1,
        )

        _selected, coverage = diversify_candidates(
            [{
                "document_id": "teaching-1978",
                "title": "Teaching notes",
                "display_date": "1978",
                "chunk_text": "Asha Bell used modelling exercises in the teaching programme.",
            }],
            contract,
            2,
        )

        self.assertIn(FacetRequirement("person", "Asha Bell"), coverage.facets_found)
        self.assertIn(FacetRequirement("person", "Ben Cole"), coverage.facets_missing)
        self.assertEqual(coverage.coverage_status, "partially_satisfied")


if __name__ == "__main__":
    unittest.main()