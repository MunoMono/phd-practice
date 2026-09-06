import asyncio
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.experiment_run_service import (
    ExperimentRunRequest,
    ExperimentRunService,
    QWEN_V2_FORMAL_RESPONSE_SCHEMA_VERSION,
    ResearchInterrogationRequest,
    ResearcherAssessmentInput,
    apply_temporal_guardrail,
    classify_temporal_source,
    formal_result_evaluability,
    project_saved_run_response,
    render_run_report,
    serialize_run,
)
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.retrieval_protocol import RetrievalFacet, RetrievalPlan
from app.services.turin_experiment_service import AuthorityContext, ContextBuilder, OUTPUT_CAPACITY_PROTOCOL_VERSION, PROMPT_REGISTER, STRUCTURED_OUTPUT_MAX_TOKENS, V13_OUTPUT_CAPACITY_PROTOCOL_VERSION, V14_OUTPUT_CAPACITY_PROTOCOL_VERSION, V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, structured_output_max_tokens


VALID_RESPONSE = '''{"answer":"The fixture supports collaboration.","evidence":[{"claim":"Archer and Baynes agreed.","source_pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1","quotation_or_paraphrase":"Archer and Baynes agreed that the Design Education Unit should continue."}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[],"authority_assertions":[]}'''


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
    def test_qwen_v2_projection_is_distinct_and_does_not_mutate_historical_artifact(self):
        artifact = {
            "final_synthesis": {
                "answer": "First saved answer.",
                "direct_documentary_claims": [{"claim": "A documentary claim."}],
                "cross_source_inferences": ["Inference one", "Inference two"],
                "missing_or_not_established": [
                    "A model-derived limit.",
                    "The selected evidence does not directly establish the named subject's activity.",
                ],
            },
            "cross_source_analysis": {"differences_or_contradictions": ["A qualification."]},
        }
        original = copy.deepcopy(artifact)
        projected, provenance = project_saved_run_response(
            artifact,
            {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            QWEN_V2_FORMAL_RESPONSE_SCHEMA_VERSION,
        )

        second, _ = project_saved_run_response(
            {**artifact, "final_synthesis": {**artifact["final_synthesis"], "answer": "Second saved answer."}},
            {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True}},
            QWEN_V2_FORMAL_RESPONSE_SCHEMA_VERSION,
        )

        self.assertEqual(projected["answer"], "First saved answer.")
        self.assertEqual(second["answer"], "Second saved answer.")
        self.assertNotEqual(projected["answer"], second["answer"])
        self.assertEqual(projected["inferences"], [
            {"inference": "Inference one", "confidence": None, "origin": "model"},
            {"inference": "Inference two", "confidence": None, "origin": "model"},
        ])
        self.assertEqual(projected["missingness"][0]["origin"], "model")
        self.assertEqual(projected["missingness"][1]["origin"], "system_pipeline")
        self.assertTrue(provenance["valid"])
        self.assertIsNot(projected, artifact)
        self.assertEqual(artifact, original)

    def test_qwen_v2_stage_a_failure_projects_no_synthetic_final_response(self):
        artifact = {"failed_stage": "source_analysis"}
        projected, provenance = project_saved_run_response(
            artifact,
            None,
            QWEN_V2_FORMAL_RESPONSE_SCHEMA_VERSION,
        )

        self.assertIsNone(projected["answer"])
        self.assertEqual(projected["evidence"], [])
        self.assertEqual(projected["pipeline_failure"], {"stage": "source_analysis", "raw_output_preserved": True})
        self.assertFalse(provenance["valid"])

    def test_legacy_qwen_v2_stage_a_failure_without_schema_version_is_projected(self):
        projected, provenance = project_saved_run_response(
            None,
            None,
            None,
            run_status="failed",
            error_message="EvidencePipelineStageError: unknown response did not match its structured schema.",
        )

        self.assertIsNone(projected["answer"])
        self.assertEqual(projected["pipeline_failure"], {"stage": "source_analysis", "raw_output_preserved": True})
        self.assertFalse(provenance["valid"])

    def test_temporal_source_classification_uses_only_persisted_metadata(self):
        self.assertEqual(classify_temporal_source({"catalogue_metadata": {"normalized_date": "1979", "extent_unit": "Seminar"}})["classification"], "contemporary DDR document")
        self.assertEqual(classify_temporal_source({"catalogue_metadata": {"normalized_date": "1992", "extent_unit": "Memoir"}})["classification"], "later retrospective account")
        self.assertEqual(classify_temporal_source({"catalogue_metadata": {"normalized_date": "1992", "extent_unit": "Report", "title": "Annual report"}})["classification"], "institutional retrospective/annual report")
        self.assertEqual(classify_temporal_source({"catalogue_metadata": {"extent_unit": "Box"}})["classification"], "ambiguous / requires researcher review")

    def test_formal_result_evaluability_requires_complete_parsed_natural_response(self):
        complete = SimpleNamespace(
            raw_model_response='{"answer":"complete"}',
            parsed_response_json={"answer": "complete"},
            parse_status="parsed",
            generation_metadata_json={"done": True, "done_reason": "stop"},
            provenance_validation_json={"valid": True, "checked_claims": 1, "valid_claims": 1, "invalid_claims": 0},
        )
        self.assertEqual(formal_result_evaluability(complete), "evaluable")

        provenance_failure = SimpleNamespace(**vars(complete))
        provenance_failure.parse_status = "parsed_with_provenance_failure"
        provenance_failure.provenance_validation_json = {"valid": False, "checked_claims": 4, "valid_claims": 3, "invalid_claims": 1}
        self.assertEqual(formal_result_evaluability(provenance_failure), "evaluable_with_provenance_failure")

        for label, field, value in [
            ("token_exhaustion", "generation_metadata_json", {"done": True, "done_reason": "length"}),
            ("read_timeout_no_output", "raw_model_response", None),
            ("raw_lost", "raw_model_response", None),
            ("parsing_failure", "parse_status", "failed_with_safe_response"),
        ]:
            non_evaluable = SimpleNamespace(**vars(complete))
            if label == "read_timeout_no_output":
                non_evaluable.error_code = "granite_failure"
                non_evaluable.error_message = "ReadTimeout: timed out"
            if label == "raw_lost":
                non_evaluable.error_code = "persistence_failure"
            setattr(non_evaluable, field, value)
            self.assertIsNone(formal_result_evaluability(non_evaluable), label)

    def test_write_ahead_shell_is_committed_before_granite_generation(self):
        database = FakeDatabase()
        test_case = self

        class ShellCheckingGranite(FakeGranite):
            async def generate_experiment(self, prompt, **kwargs):
                test_case.assertGreaterEqual(database.commits, 1)
                test_case.assertTrue(any(item.__class__.__name__ == "ExperimentRun" and item.status == "running" for item in database.added))
                return await super().generate_experiment(prompt, **kwargs)

        granite = ShellCheckingGranite()
        asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=granite).run_archival_experiment(database, self.request()))
        self.assertGreaterEqual(database.commits, 3)

    def test_raw_response_is_committed_before_repair_generation(self):
        database = FakeDatabase()
        test_case = self

        class RepairCheckingGranite(FakeGranite):
            def __init__(self):
                self.calls = 0

            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    test_case.assertTrue(any(item.__class__.__name__ == "ExperimentRun" and item.raw_model_response == '{"answer":"truncated' for item in database.added))
                    test_case.assertGreaterEqual(database.commits, 2)
                return {"raw_response": '{"answer":"truncated', "generation": {**kwargs, "done": True, "done_reason": "length"}}

        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=RepairCheckingGranite()).run_archival_experiment(database, self.request()))
        self.assertEqual(run.error_code, "output_token_exhaustion")
        self.assertEqual(run.raw_model_response, '{"answer":"truncated')

    def test_governed_recovery_categories_are_accepted_by_request_schemas(self):
        categories = [
            "infrastructure_failure_before_inference",
            "instrument_implementation_correction",
            "infrastructure_recovery_after_v1_2_read_timeout",
            "orphaned_inference_replacement_after_write_ahead_persistence_remediation",
            "protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion",
        ]
        for category in categories:
            self.assertEqual(
                ResearchInterrogationRequest(research_question="Fixture question", recovery_category=category).recovery_category,
                category,
            )
            self.assertEqual(
                ExperimentRunRequest(
                    research_case="known_relationship",
                    research_question="Fixture question",
                    retrieval=RetrievalValidationRequest(query="fixture"),
                    recovery_category=category,
                ).recovery_category,
                category,
            )

        with self.assertRaises(ValidationError):
            ResearchInterrogationRequest(research_question="Fixture question", recovery_category="unknown_recovery_category")
        with self.assertRaises(ValidationError):
            ExperimentRunRequest(
                research_case="known_relationship",
                research_question="Fixture question",
                retrieval=RetrievalValidationRequest(query="fixture"),
                recovery_category="unknown_recovery_category",
            )

    def request(self):
        return ExperimentRunRequest(research_case="known_relationship", research_question="What relationship is supported?", retrieval=RetrievalValidationRequest(query="Archer Baynes", top_k=1), fixture_only=True)

    def test_persists_immutable_fixture_snapshot_and_reload_payload(self):
        database = FakeDatabase()
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite())
        run = asyncio.run(service.run_archival_experiment(database, self.request()))
        payload = serialize_run(run)
        self.assertTrue(run.fixture_only)
        self.assertEqual(payload["classification"], "FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN")
        self.assertEqual(run.prompt_name, "turin_known_relationship")
        self.assertEqual(run.prompt_version, "v4")
        self.assertEqual(run.corpus_version, "fixture-v1")
        self.assertEqual(run.raw_model_response, VALID_RESPONSE)
        self.assertEqual(run.parsed_response_json["answer"], "The fixture supports collaboration.")
        self.assertEqual(run.display_response_json["answer"], "The fixture supports collaboration.")
        self.assertEqual(run.structured_response_json["answer"], "The fixture supports collaboration.")
        self.assertEqual(run.generation_metadata_json["response_schema"], run.response_schema_json)
        self.assertEqual(run.response_schema_version, "turin-archival-analysis-response-v1")
        self.assertTrue(run.response_schema_hash)
        self.assertTrue(run.provenance_validation_json["valid"])
        evidence = next(item for item in database.added if item.__class__.__name__ == "ExperimentRunEvidence")
        self.assertEqual(evidence.excerpt, "Archer and Baynes agreed that the Design Education Unit should continue.")
        self.assertEqual(evidence.archive_record_pid, "fixture-record-1")
        self.assertTrue(evidence.included_in_context)
        self.assertEqual(evidence.supplied_excerpt, evidence.excerpt)
        self.assertEqual(payload["context"]["budget"]["context_builder_version"], "turin-context-budget-v3")
        self.assertEqual(payload["context"]["budget"]["context_assembly_protocol_version"], "turin-retrieval-protocol-v1.1")

    def test_v12_fixture_persists_increased_capacity_without_repair(self):
        request = self.request().model_copy(update={"execution_protocol_version": OUTPUT_CAPACITY_PROTOCOL_VERSION})
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite()).run_archival_experiment(FakeDatabase(), request))

        self.assertEqual(run.retrieval_protocol_version, OUTPUT_CAPACITY_PROTOCOL_VERSION)
        self.assertEqual(run.generation_metadata_json["max_tokens"], STRUCTURED_OUTPUT_MAX_TOKENS)
        self.assertFalse(run.repair_attempted)
        self.assertTrue(run.parsed_response_json)
        self.assertTrue(run.provenance_validation_json["valid"])

    def test_output_exhaustion_is_persisted_separately_from_parse_failure(self):
        invalid_response = '{"answer":"truncated'

        class ExhaustedGranite(FakeGranite):
            async def generate_experiment(self, prompt, **kwargs):
                return {"raw_response": invalid_response, "generation": {**kwargs, "done": True, "done_reason": "length", "eval_count": 350, "eval_duration": 1, "prompt_eval_count": 12, "prompt_eval_duration": 2}}

        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=ExhaustedGranite()).run_archival_experiment(FakeDatabase(), self.request()))
        self.assertEqual(run.error_code, "output_token_exhaustion")
        self.assertEqual(run.generation_metadata_json["done_reason"], "length")
        self.assertEqual(run.repair_generation_metadata_json["done_reason"], "length")
        self.assertIsNone(run.parsed_response_json)
        self.assertTrue(run.display_response_json["missingness"])

    def test_header_capacity_failure_persists_without_granite_generation(self):
        class CountingGranite(FakeGranite):
            def __init__(self):
                self.calls = 0

            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                return await super().generate_experiment(prompt, **kwargs)

        granite = CountingGranite()
        retrieval_result = FixtureRetrieval().retrieve(None, self.request().retrieval)["results"][0]
        question = self.request().research_question
        template = PROMPT_REGISTER["known_relationship"]
        fixed_prompt_chars = len(f"{template.system_template}\n\n{template.user_template.replace('{question}', question).replace('{context}', '')}")
        header_chars = len(ContextBuilder()._document_block(1, retrieval_result, None, ""))
        request = self.request().model_copy(update={"context_budget": fixed_prompt_chars + header_chars - 1})
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=granite).run_archival_experiment(FakeDatabase(), request))
        self.assertEqual(run.error_code, "context_representation_failure")
        self.assertEqual(run.parse_status, "not_invoked")
        self.assertEqual(granite.calls, 0)
        self.assertTrue(run.display_response_json["missingness"])

    def test_zero_retrieval_is_saved_as_review_required_missingness_run(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": ["No source passage was retrieved."]}, "corpus_versions": []}
        database = FakeDatabase()
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), inference_service=FakeGranite()).run_archival_experiment(database, self.request()))
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
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), inference_service=granite).run_archival_experiment(FakeDatabase(), request))
        self.assertEqual(granite.calls, 0)
        self.assertIsNone(run.raw_model_response)
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertIn("Database authority records", run.structured_response_json["answer"])

    def test_v16_zero_retrieval_requires_explicit_permission(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": []}, "corpus_versions": []}

        granite = FakeGranite()
        request = self.request().model_copy(update={"fixture_only": True, "execution_protocol_version": V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION})
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), inference_service=granite).run_archival_experiment(FakeDatabase(), request))
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertIsNone(run.raw_model_response)

    def test_v16_explicit_zero_retrieval_requires_matching_authorization(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": []}, "corpus_versions": []}

        class NoAuthorizationDatabase(FakeDatabase):
            def execute(self, *_args, **_kwargs):
                return type("AuthorizationResult", (), {"first": lambda self: None})()

        request = self.request().model_copy(update={
            "fixture_only": False,
            "execution_protocol_version": V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION,
            "formal_authorization_id": "missing-v16-authorization",
            "allow_zero_documentary_inference": True,
        })
        with self.assertRaisesRegex(ValueError, "exact explicit v1.6 authorization"):
            asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), inference_service=FakeGranite())._run_with_retrieval(NoAuthorizationDatabase(), request, EmptyRetrieval().retrieve(None, request.retrieval)))

    def test_protocol_capacity_mapping_is_unchanged_through_v16(self):
        self.assertEqual(
            [structured_output_max_tokens(version) for version in (
                "turin-retrieval-protocol-v1.0", "turin-retrieval-protocol-v1.1",
                OUTPUT_CAPACITY_PROTOCOL_VERSION, V13_OUTPUT_CAPACITY_PROTOCOL_VERSION,
                V14_OUTPUT_CAPACITY_PROTOCOL_VERSION, V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION,
                V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION,
            )],
            [350, 350, 500, 1000, 1500, 1500, 1500],
        )

    def test_v16_authorized_zero_retrieval_writes_shell_and_generates_once(self):
        class EmptyRetrieval(FixtureRetrieval):
            def retrieve(self, _, request):
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": []}, "corpus_versions": []}

        class CountingGranite(FakeGranite):
            def __init__(self):
                self.calls = 0

            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                self.asserted_prompt = prompt
                self.asserted_write_ahead = database.commits >= 1 and any(
                    item.__class__.__name__ == "ExperimentRun" and item.status == "running"
                    for item in database.added
                )
                return {
                    "raw_response": '{"answer":"No documentary evidence was retrieved.","evidence":[],"inferences":[],"contradictions":[],"missingness":[{"scope":"documentary evidence","category":"zero retrieval","explanation":"No passages.","follow_up_action":null}],"follow_up_queries":[],"authority_assertions":[]}',
                    "generation": {**kwargs, "done": True, "done_reason": "stop"},
                }

        database = FakeDatabase()
        granite = CountingGranite()
        authority = AuthorityContext(source="fixture-db", authority_type="agent_employment", authority_id="fixture-staff", role="structural_context", fields={"name": "Fixture Staff", "job_title_label": "Secretary"})
        plan = RetrievalPlan(plan_id="SM4-v2", question_id="SM4", plan_version="2.0", researcher_approval_state="approved", researcher_approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc), lexical_facets=[RetrievalFacet(facet_id="person", alternatives=["Henrietta Ryott"])], top_k=1, rationale="Fixture plan for zero-documentary persistence.")
        request = self.request().model_copy(update={"fixture_only": True, "question_id": "SM4", "retrieval": RetrievalValidationRequest(query="What relationship is supported?", top_k=1, corpus_version="corpus_f40d78dbce52"), "retrieval_plan": plan, "execution_protocol_version": V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, "formal_authorization_id": "fixture-v16-authorization", "allow_zero_documentary_inference": True, "authority_context": [authority], "context_mode": "document_plus_authority_context"})
        run = asyncio.run(ExperimentRunService(retrieval_service=EmptyRetrieval(), inference_service=granite).run_archival_experiment(database, request))
        self.assertEqual(granite.calls, 1)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.context_chunk_count, 0)
        self.assertTrue(granite.asserted_write_ahead)
        self.assertIsNotNone(run.raw_model_response)
        self.assertFalse(run.repair_attempted)
        self.assertEqual(run.corpus_version, "corpus_f40d78dbce52")
        self.assertEqual(run.retrieval_protocol_version, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION)
        self.assertFalse(any(value is None for value in (run.question_id, run.retrieval_plan_id, run.retrieval_plan_version, run.retrieval_scope, run.retrieval_run_classification, run.formal_authorization_id, run.corpus_version, run.model_name, run.model_parameters_json)))
        self.assertIn("No documentary passages were retrieved", granite.asserted_prompt)
        self.assertIn("AUTHORITY CONTEXT — NOT DOCUMENTARY EVIDENCE", granite.asserted_prompt)
        self.assertEqual(run.structured_response_json["evidence"], [])

    def test_parse_failure_preserves_raw_output_but_renders_no_claim(self):
        invalid_response = '''{"answer":"Unsupported claim.","evidence":[{"claim":"Unsupported.","pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1"}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[],"authority_assertions":[]}'''

        class InvalidGranite(FakeGranite):
            async def generate_experiment(self, prompt, **kwargs):
                return {"raw_response": invalid_response, "generation": kwargs}

        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=InvalidGranite()).run_archival_experiment(FakeDatabase(), self.request()))
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.raw_model_response, invalid_response)
        self.assertEqual(run.parse_status, "failed_with_safe_response")
        self.assertEqual(run.structured_response_json["evidence"], [])
        self.assertEqual(run.structured_response_json["inferences"], [])
        self.assertIn("structured response validation failed", run.structured_response_json["answer"])

    def test_identifier_failure_preserves_raw_and_parsed_response(self):
        identifier_mismatch = VALID_RESPONSE.replace('"source_pid":"fixture-pid-1"', '"source_pid":"fixture-doc-1"')

        class InvalidCitationGranite(FakeGranite):
            async def generate_experiment(self, prompt, **kwargs):
                return {"raw_response": identifier_mismatch, "generation": kwargs}

        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=InvalidCitationGranite()).run_archival_experiment(FakeDatabase(), self.request()))
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_code, "provenance_validation_failure")
        self.assertEqual(run.raw_model_response, identifier_mismatch)
        self.assertEqual(run.parsed_response_json["evidence"][0]["source_pid"], "fixture-doc-1")
        self.assertEqual(run.structured_response_json["evidence"], [])
        self.assertIn("citation_identifier_mismatch", run.error_message)

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
        request = ResearchInterrogationRequest(research_question="What does the corpus establish about women working in the DDR in 1970?", fixture_only=True)
        run = asyncio.run(ExperimentRunService(retrieval_service=GenericRetrieval(), inference_service=FakeGranite()).run_research_interrogation(FakeDatabase(), request))
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
            ExperimentRunService(retrieval_service=retrieval, inference_service=FakeGranite()).run_research_interrogation(
                StaffAuthorityDatabase(),
                ResearchInterrogationRequest(research_question="How did Ken Baynes appear across DDR records?", fixture_only=True),
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
            ExperimentRunService(retrieval_service=retrieval, inference_service=FakeGranite()).run_research_interrogation(
                StaffAuthorityDatabase(),
                ResearchInterrogationRequest(research_question="How did Unknown Person appear across DDR records?", fixture_only=True),
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
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=granite).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="List the DDR job numbers 80 to 100", fixture_only=True)))
        contexts = run.authority_context_json["contexts"]
        self.assertEqual([item["fields"]["job_number"] for item in contexts], [82, 83, 84, 97, 98, 99])
        self.assertEqual(granite.calls, 0)
        self.assertEqual(run.retrieval_method, "authority_only")
        self.assertEqual(run.status, "completed")

    def test_single_project_is_authority_not_documentary_evidence(self):
        run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite()).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="What was DDR job 97?", fixture_only=True)))
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
        run = asyncio.run(ExperimentRunService(retrieval_service=retrieval, inference_service=FakeGranite()).run_research_interrogation(ProjectAuthorityDatabase(), ResearchInterrogationRequest(research_question="What does the archive say about DDR job 97?", fixture_only=True)))
        self.assertEqual(run.authority_context_json["contexts"][0]["authority_id"], "97")
        self.assertEqual(retrieval.request.expansions, [])
        self.assertEqual(run.status, "completed")
        self.assertTrue(run.structured_response_json["evidence"])

    def test_assessment_is_separate_editable_and_scores_are_bounded(self):
        database = FakeDatabase()
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite())
        run = asyncio.run(service.run_archival_experiment(database, self.request()))
        assessment = service.save_assessment(database, run, ResearcherAssessmentInput(retrieval_relevance=3, provenance_accuracy=2, notes="Researcher judgement."))
        self.assertEqual(assessment.retrieval_relevance, 3)
        self.assertEqual(serialize_run(run, include_evidence=False)["assessment"]["provenance_accuracy"], 2)
        with self.assertRaises(Exception):
            ResearcherAssessmentInput(retrieval_relevance=4)

    def test_each_rerun_has_a_new_run_id(self):
        service = ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite())
        first = asyncio.run(service.run_archival_experiment(FakeDatabase(), self.request()))
        second = asyncio.run(service.run_archival_experiment(FakeDatabase(), self.request()))
        self.assertNotEqual(first.run_id, second.run_id)


if __name__ == "__main__":
    unittest.main()