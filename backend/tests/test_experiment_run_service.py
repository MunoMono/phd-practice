import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.experiment_run_service import (
    ExperimentRunRequest,
    ExperimentRunService,
    ResearchInterrogationRequest,
    ResearcherAssessmentInput,
    apply_temporal_guardrail,
    render_run_report,
    serialize_run,
)
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.turin_experiment_service import AuthorityContext


VALID_RESPONSE = '''{"answer":"The fixture supports collaboration.","evidence":[{"claim":"Archer and Baynes agreed.","pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1","quotation_or_paraphrase":"Archer and Baynes agreed that the Design Education Unit should continue."}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[],"authority_assertions":[]}'''


class FakeDatabase:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, _):
        pass


class AuthorityRows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


PROJECT_ROWS = [
    {"authority_id": "82", "label": "Computers in industrialised building", "metadata": {"funder_name": "Royal Institute of British Architects", "duration_text": "Null", "project_lead_name": "Null", "start_year": None, "end_year": None}},
    {"authority_id": "83", "label": "Patterns of educational purchases of equipment and materials", "metadata": {"funder_name": "National Council for Educational Technology", "duration_text": "≤ 12 months", "project_lead_name": "Richard Langdon", "start_year": 1972, "end_year": 1972}},
    {"authority_id": "84", "label": "Inflatable play equipment for handicapped children", "metadata": {"funder_name": "Viscount Nuffield Auxiliary Fund", "duration_text": "≤ 12 months", "project_lead_name": "Jim Singh Sandhu", "start_year": 1973, "end_year": 1973}},
    {"authority_id": "97", "label": "The application of computer aided architectural design to METHOD building: Phase 1", "metadata": {"funder_name": "Consortium for METHOD building", "duration_text": "≤ 12 months", "project_lead_name": "Andrew Garnett", "start_year": 1970, "end_year": 1970}},
    {"authority_id": "98", "label": "Coding of push button controls", "metadata": {"funder_name": "PHQ/PMD/DD2", "duration_text": "≤ 12 months", "project_lead_name": "John Oates", "start_year": 1971, "end_year": 1971}},
    {"authority_id": "99", "label": "Design of an improved medicine trolley for ward use", "metadata": {"funder_name": "Llewellyn and Co", "duration_text": "≤ 12 months", "project_lead_name": "Kenneth Agnew", "start_year": 1971, "end_year": 1971}},
]


class ProjectAuthorityDatabase(FakeDatabase):
    def __init__(self, rows=PROJECT_ROWS):
        super().__init__()
        self.rows = rows

    def execute(self, *_):
        return AuthorityRows(self.rows)


class FixtureRetrieval:
    def retrieve(self, _, request):
        result = {
            "rank": 1, "score": 0.9, "pid": "fixture-pid-1", "archive_record_pid": "fixture-record-1",
            "document_id": "fixture-doc-1", "archive_resolution_status": "resolved_current", "title": "Fixture memorandum",
            "page_start": 4, "page_end": 4, "chunk_id": "fixture-chunk-1", "chunk_sequence": 1,
            "text": "Archer and Baynes agreed that the Design Education Unit should continue.", "included_in_context": True,
            "provenance": {"archive_record_pid": "fixture-record-1"}, "catalogue_metadata": {"title": "Fixture memorandum"},
        }
        return {"transparency": {"original_query": request.query, "normalised_query": request.query, "expanded_query": request.query, "query_expansions": [], "filters": {}, "top_k": request.top_k, "ranking_function": "fixture"}, "results": [result], "diagnostics": {"result_count": 1, "notes": []}, "corpus_versions": ["fixture-v1"]}


class FakeGranite:
    def get_load_status(self):
        return {"model_ready": True, "model_status": "ready"}

    def get_model_info(self):
        return {"model_name": "fixture-granite", "runtime": "fake", "quantized": "fixture"}

    async def generate_experiment(self, prompt, **kwargs):
        return {"raw_response": VALID_RESPONSE, "generation": kwargs}


class ExperimentRunServiceTests(unittest.TestCase):
    def request(self):
        return ExperimentRunRequest(research_case="known_relationship", research_question="What relationship is supported?", retrieval=RetrievalValidationRequest(query="Archer Baynes", top_k=1), fixture_only=True)

    def test_persists_immutable_fixture_snapshot_and_reload_payload(self):
        database = FakeDatabase()
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=FakeGranite())
        run = asyncio.run(service.run_archival_experiment(database, self.request()))
        payload = serialize_run(run)
        self.assertTrue(run.fixture_only)
        self.assertEqual(payload["classification"], "FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN")
        self.assertEqual(run.prompt_name, "turin_known_relationship")
        self.assertEqual(run.prompt_version, "v4")
        self.assertEqual(run.raw_model_response, VALID_RESPONSE)
        self.assertEqual(run.structured_response_json["answer"], "The fixture supports collaboration.")
        self.assertTrue(run.provenance_validation_json["valid"])
        evidence = next(item for item in database.added if item.__class__.__name__ == "ExperimentRunEvidence")
        self.assertEqual(evidence.excerpt, "Archer and Baynes agreed that the Design Education Unit should continue.")
        self.assertEqual(evidence.archive_record_pid, "fixture-record-1")
        self.assertTrue(evidence.included_in_context)
        self.assertEqual(evidence.supplied_excerpt, evidence.excerpt)
        self.assertEqual(payload["context"]["budget"]["context_builder_version"], "turin-context-budget-v2")

    def test_zero_retrieval_is_saved_as_review_required_missingness_run(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": ["No source passage was retrieved."]}, "corpus_versions": []}
        database = FakeDatabase()
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), granite_service=FakeGranite()).run_archival_experiment(database, self.request()))
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertEqual(run.structured_response_json["answer"], "The supplied authority and retrieved corpus do not establish this.")
        self.assertEqual(serialize_run(run)["interpretative_status"], "researcher_review_required")

    def test_authority_only_run_does_not_invoke_granite(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": []}, "corpus_versions": []}

        class CountingGranite(FakeGranite):
            def __init__(self):
                self.calls = 0

            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                return await super().generate_experiment(prompt, **kwargs)

        granite = CountingGranite()
        request = self.request().model_copy(update={"authority_context": [AuthorityContext(authority_id="BRUCEARCHE", authority_type="agent_employment", label="Bruce Archer", source="database_authorities.agent_employment", role="structural_context", fields={"requested_year": 1980})]})
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), granite_service=granite).run_archival_experiment(FakeDatabase(), request))
        self.assertEqual(granite.calls, 0)
        self.assertIsNone(run.raw_model_response)
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertIn("Database authority records", run.structured_response_json["answer"])

    def test_parse_failure_preserves_raw_output_but_renders_no_claim(self):
        invalid_response = '''{"answer":"Unsupported claim.","evidence":[{"claim":"Unsupported.","pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1"}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[],"authority_assertions":[]}'''

        class InvalidGranite(FakeGranite):
            async def generate_experiment(self, prompt, **kwargs):
                return {"raw_response": invalid_response, "generation": kwargs}

        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=InvalidGranite()).run_archival_experiment(FakeDatabase(), self.request()))
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.raw_model_response, invalid_response)
        self.assertEqual(run.parse_status, "failed_with_safe_response")
        self.assertEqual(run.structured_response_json["evidence"], [])
        self.assertEqual(run.structured_response_json["inferences"], [])
        self.assertIn("structured response validation failed", run.structured_response_json["answer"])

    def test_temporal_guardrail_rejects_1971_to_1973_for_1980(self):
        retrieval = FixtureRetrieval().retrieve(None, self.request().retrieval)
        retrieval["results"][0]["text"] = "The project ran from 1971 to 1973."
        guarded = apply_temporal_guardrail(retrieval, [1980])
        self.assertEqual(guarded["results"], [])
        self.assertEqual(guarded["diagnostics"]["temporal_rejections"][0]["chunk_id"], "fixture-chunk-1")

    def test_demographic_question_with_only_generic_evidence_is_missingness(self):
        class GenericRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                retrieval = super().retrieve(_, request)
                retrieval["results"][0]["text"] = "The department employed researchers on several projects from 1971 to 1973."
                return retrieval
        request = ResearchInterrogationRequest(research_question="What does the corpus establish about women working in the DDR in 1970?")
        run = asyncio.run(ExperimentRunService(retrieval_service=GenericRetrieval(), granite_service=FakeGranite()).run_research_interrogation(FakeDatabase(), request))
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertNotIn("women were", run.structured_response_json["answer"].lower())
        self.assertTrue(run.structured_response_json["missingness"])

    def test_staff_authority_context_is_resolved_for_requested_year(self):
        class AuthorityRows:
            def mappings(self):
                return self

            def all(self):
                return [{"authority_id": "BRUCEARCHE", "label": "Bruce Archer", "metadata": {"start_date": "1961-01-01", "end_date": "1988-12-31"}}]

        class AuthorityDatabase:
            def execute(self, *_):
                return AuthorityRows()

        contexts = ExperimentRunService().resolve_authority_context(AuthorityDatabase(), "Who worked at the DDR in 1980?", [1980])
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0].authority_type, "agent_employment")
        self.assertEqual(contexts[0].fields["requested_year"], 1980)

    def test_named_staff_authority_context_is_separate_from_documentary_retrieval(self):
        class StaffAuthorityDatabase(FakeDatabase):
            def execute(self, *_):
                return AuthorityRows([{
                    "authority_id": "KENNETHBAY",
                    "label": "Kenneth Baynes",
                    "metadata": {
                        "job_title_label": "Research Fellow / later Tutor DEU / later Head of Department DEU",
                        "start_date": "1976-01-01",
                        "end_date": "1985-12-31",
                        "is_primary": True,
                    },
                }])

        class CapturingRetrieval(FixtureRetrieval):
            def __init__(self):
                self.calls = 0

            def retrieve(self, database, request):
                self.calls += 1
                return super().retrieve(database, request)

        retrieval = CapturingRetrieval()
        run = asyncio.run(
            ExperimentRunService(retrieval_service=retrieval, granite_service=FakeGranite()).run_research_interrogation(
                StaffAuthorityDatabase(),
                ResearchInterrogationRequest(research_question="How did Ken Baynes appear across DDR records?"),
            )
        )

        self.assertEqual(retrieval.calls, 1)
        self.assertEqual(run.retrieval_method, "postgresql_fts")
        self.assertEqual(run.authority_context_json["contexts"][0]["authority_id"], "KENNETHBAY")
        self.assertEqual(run.authority_context_json["contexts"][0]["fields"]["name"], "Kenneth Baynes")
        self.assertEqual(run.authority_context_json["contexts"][0]["fields"]["job_title_label"], "Research Fellow / later Tutor DEU / later Head of Department DEU")
        self.assertEqual(run.structured_response_json["evidence"][0]["chunk_id"], "fixture-chunk-1")
        self.assertIn("KENNETHBAY", render_run_report(run))

    def test_unknown_person_keeps_documentary_retrieval_unchanged(self):
        class StaffAuthorityDatabase(FakeDatabase):
            def execute(self, *_):
                return AuthorityRows([{
                    "authority_id": "KENNETHBAY",
                    "label": "Kenneth Baynes",
                    "metadata": {"job_title_label": "Research Fellow"},
                }])

        class CapturingRetrieval(FixtureRetrieval):
            def __init__(self):
                self.calls = 0

            def retrieve(self, database, request):
                self.calls += 1
                return super().retrieve(database, request)

        retrieval = CapturingRetrieval()
        run = asyncio.run(
            ExperimentRunService(retrieval_service=retrieval, granite_service=FakeGranite()).run_research_interrogation(
                StaffAuthorityDatabase(),
                ResearchInterrogationRequest(research_question="How did Unknown Person appear across DDR records?"),
            )
        )

        self.assertEqual(retrieval.calls, 1)
        self.assertEqual(run.retrieval_method, "postgresql_fts")
        self.assertEqual(run.authority_context_json["contexts"], [])
        self.assertEqual(run.structured_response_json["evidence"][0]["chunk_id"], "fixture-chunk-1")

    def test_project_job_range_is_authority_only_and_never_fabricates_numbers(self):
        class CountingGranite(FakeGranite):
            def __init__(self):
                self.calls = 0

            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                return await super().generate_experiment(prompt, **kwargs)

        granite = CountingGranite()
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=granite).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="List the DDR job numbers 80 to 100")))
        contexts = run.authority_context_json["contexts"]
        self.assertEqual([item["fields"]["job_number"] for item in contexts], [82, 83, 84, 97, 98, 99])
        self.assertEqual(granite.calls, 0)
        self.assertEqual(run.retrieval_method, "authority_only")
        self.assertEqual(run.status, "completed")

    def test_single_project_is_authority_not_documentary_evidence(self):
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=FakeGranite()).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="What was DDR job 97?")))
        context = run.authority_context_json["contexts"][0]
        self.assertEqual(context["authority_type"], "ddr_projects")
        self.assertEqual(context["fields"]["job_number"], 97)
        self.assertEqual(context["fields"]["title"], "The application of computer aided architectural design to METHOD building: Phase 1")
        self.assertEqual(run.structured_response_json["evidence"], [])

    def test_project_year_uses_explicit_dates_and_never_job_number_order(self):
        service = ExperimentRunService()
        resolution = service.resolve_authority_resolution(ProjectAuthorityDatabase(), "List the DDR jobs in 1972", [1972])
        self.assertEqual([item.fields["job_number"] for item in resolution.contexts], [83])

        no_dates = [{**row, "metadata": {key: value for key, value in row["metadata"].items() if key not in {"start_year", "end_year"}}} for row in PROJECT_ROWS]
        missing_resolution = service.resolve_authority_resolution(ProjectAuthorityDatabase(no_dates), "List the DDR jobs in 1972", [1972])
        self.assertEqual(missing_resolution.contexts, [])
        self.assertEqual(missing_resolution.missingness["category"], "insufficient_project_temporal_authority")

    def test_documentary_project_question_resolves_authority_then_retrieves(self):
        class CapturingRetrieval(FixtureRetrieval):
            def __init__(self):
                self.request = None

            def retrieve(self, database, request):
                self.request = request
                return super().retrieve(database, request)

        retrieval = CapturingRetrieval()
        run = asyncio.run(ExperimentRunService(retrieval_service=retrieval, granite_service=FakeGranite()).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="What does the archive say about DDR job 97?")))
        self.assertEqual(run.authority_context_json["contexts"][0]["authority_id"], "97")
        self.assertEqual(retrieval.request.expansions[-1].authority_source, "database_authorities.ddr_projects")
        self.assertEqual(retrieval.request.expansions[-1].authority_id, "97")
        self.assertEqual(run.status, "completed")
        self.assertTrue(run.structured_response_json["evidence"])

    def test_assessment_is_separate_editable_and_scores_are_bounded(self):
        database = FakeDatabase()
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=FakeGranite())
        run = asyncio.run(service.run_archival_experiment(database, self.request()))
        assessment = service.save_assessment(database, run, ResearcherAssessmentInput(retrieval_relevance=3, provenance_accuracy=2, notes="Researcher judgement."))
        self.assertEqual(assessment.retrieval_relevance, 3)
        self.assertEqual(serialize_run(run, include_evidence=False)["assessment"]["provenance_accuracy"], 2)
        with self.assertRaises(Exception):
            ResearcherAssessmentInput(retrieval_relevance=4)

    def test_each_rerun_has_a_new_run_id(self):
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=FakeGranite())
        first = asyncio.run(service.run_archival_experiment(FakeDatabase(), self.request()))
        second = asyncio.run(service.run_archival_experiment(FakeDatabase(), self.request()))
        self.assertNotEqual(first.run_id, second.run_id)


if __name__ == "__main__":
    unittest.main()