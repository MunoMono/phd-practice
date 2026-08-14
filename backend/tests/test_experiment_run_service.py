import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, ResearcherAssessmentInput, serialize_run
from app.services.retrieval_validation_service import RetrievalValidationRequest


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

    def test_zero_retrieval_is_saved_as_failed_run(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": ["No source passage was retrieved."]}, "corpus_versions": []}
        database = FakeDatabase()
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), granite_service=FakeGranite()).run_archival_experiment(database, self.request()))
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_code, "zero_retrieval")
        self.assertEqual(run.parse_status, "not_invoked")

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