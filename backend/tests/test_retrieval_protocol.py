import asyncio
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.services.experiment_run_service import (
    ExperimentRunRequest,
    ExperimentRunService,
    _normalise_persisted_plan_snapshot,
    is_failure_recovery_eligible,
    is_instrument_implementation_correction_eligible,
    is_q06_v12_read_timeout_recovery_eligible,
)
from app.services.retrieval_protocol import (
    AuthorityDerivedVariant,
    RetrievalFacet,
    RetrievalPlan,
    TemporalRetrievalStratum,
    compile_retrieval_plan,
)
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService
from test_experiment_run_service import FakeDatabase, FakeGranite, FixtureRetrieval
from test_retrieval_validation_service import make_row


QUESTION = "What documentary traces connect Job 171, “Designer-computer interaction in the early stages of design”, to the people, activities and outputs associated with it?"


def approved_plan(**changes):
    values = {
        "plan_id": "KR1-v1",
        "question_id": "KR1",
        "plan_version": "1.0",
        "researcher_approval_state": "approved",
        "researcher_approved_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "lexical_facets": [
            RetrievalFacet(facet_id="project", alternatives=["man-computer interaction", "man-computer design systems"]),
            RetrievalFacet(facet_id="person", alternatives=["Pierre Goumain"]),
        ],
        "top_k": 5,
        "rationale": "Researcher-approved archival terminology.",
    }
    values.update(changes)
    return RetrievalPlan(**values)


class ScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def scalar_one(self):
        return "('man-comput' & 'interact')"

    def mappings(self):
        return self

    def all(self):
        return self.rows


class PlanDatabase:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if len(self.calls) == 1:
            return ScalarResult([])
        return ScalarResult([make_row()])


class StratifiedPlanDatabase(PlanDatabase):
    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if len(self.calls) == 1:
            return ScalarResult([])
        if "record_title" in str(statement):
            return ScalarResult([make_row(chunk_id="retrospective-1", document_id="retrospective-doc", score=0.2)])
        return ScalarResult([
            make_row(chunk_id=f"contemporary-{index}", document_id=f"contemporary-doc-{index}", score=1.0 - index / 10)
            for index in range(1, 6)
        ])


class BalancedStratifiedPlanDatabase(PlanDatabase):
    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if len(self.calls) == 1:
            return ScalarResult([])
        if "record_title" in str(statement):
            return ScalarResult([
                make_row(chunk_id=f"retrospective-{index}", document_id=f"retrospective-doc-{index}", score=0.9 - index / 10)
                for index in range(1, 4)
            ])
        return ScalarResult([
            make_row(chunk_id=f"contemporary-{index}", document_id=f"contemporary-doc-{index}", score=0.4 - index / 10)
            for index in range(1, 4)
        ])


class ExistingPlanQuery:
    def __init__(self, plan):
        self.plan = plan

    def filter(self, _):
        return self

    def one_or_none(self):
        return self.plan


class ExistingPlanDatabase:
    def __init__(self, plan):
        self.plan = plan
        self.added = []

    def query(self, _):
        return ExistingPlanQuery(self.plan)

    def add(self, item):
        self.added.append(item)


class RetrievalProtocolTests(unittest.TestCase):
    def test_instrument_implementation_correction_requires_only_documented_contract_failure_conditions(self):
        plan = approved_plan()
        run = SimpleNamespace(
            status="failed", error_code="provenance_validation_failure", raw_model_response="parsed model output",
            model_name="granite3.1-dense:2b-instruct-q4_K_M",
            model_parameters_json={"max_tokens": 350, "temperature": 0.0, "top_p": 1.0, "do_sample": False},
            provenance_validation_json={"valid": False, "checked_claims": 1, "invalid_claims": 1},
            retrieval_plan_id="KR1-v1", retrieval_plan_version="1.0",
            retrieval_protocol_version="turin-retrieval-protocol-v1.0",
            corpus_version="corpus_f40d78dbce52", retrieval_scope="corpus_wide",
            retrieval_run_classification="primary",
        )
        self.assertTrue(is_instrument_implementation_correction_eligible(run, plan, "corpus_f40d78dbce52"))

        for field, value in [
            ("status", "completed"),  # A valid/evaluable primary result closes the slot.
            ("error_code", "granite_failure"),  # Infrastructure is governed by the separate recovery category.
            ("error_code", "weak_retrieval"),
            ("error_code", "zero_retrieval"),
            ("error_code", "researcher_rejection"),
            ("error_code", "poor_model_answer"),
            ("provenance_validation_json", {"valid": True, "checked_claims": 1, "invalid_claims": 0}),
            ("raw_model_response", None),
            ("retrieval_plan_id", "KR1-v2"),
            ("retrieval_plan_version", "2.0"),
            ("retrieval_protocol_version", "other-protocol"),
            ("corpus_version", "other-corpus"),
            ("retrieval_scope", "sensitivity_or_diagnostic"),
            ("retrieval_run_classification", "sensitivity_or_diagnostic"),
            ("model_name", "other-model"),
            ("model_parameters_json", {"max_tokens": 384, "temperature": 0.0, "top_p": 1.0, "do_sample": False}),
        ]:
            changed = SimpleNamespace(**vars(run))
            setattr(changed, field, value)
            self.assertFalse(is_instrument_implementation_correction_eligible(changed, plan, "corpus_f40d78dbce52"), field)

    def test_failure_recovery_requires_an_uninferred_matching_infrastructure_failure(self):
        plan = approved_plan()
        run = SimpleNamespace(
            status="failed", error_code="granite_failure", raw_model_response=None,
            model_name=None, inference_duration_ms=None, parse_status="not_invoked",
            structured_response_json=None, provenance_validation_json=None,
            retrieval_plan_id="KR1-v1", retrieval_plan_version="1.0",
            retrieval_protocol_version="turin-retrieval-protocol-v1.0",
            corpus_version="corpus_f40d78dbce52", retrieval_scope="corpus_wide",
            retrieval_run_classification="primary",
        )
        self.assertTrue(is_failure_recovery_eligible(run, plan, "corpus_f40d78dbce52"))

        for field, value in [
            ("raw_model_response", "valid Granite output"),
            ("model_name", "granite3.1-dense:2b-instruct-q4_K_M"),
            ("inference_duration_ms", 1),
            ("parse_status", "parsed"),
            ("structured_response_json", {"answer": "saved"}),
            ("provenance_validation_json", {"valid": False}),
            ("status", "completed_with_missingness"),
            ("error_code", "provenance_validation_failure"),
            ("retrieval_plan_id", "KR1-v2"),
            ("retrieval_plan_version", "2.0"),
            ("retrieval_protocol_version", "other-protocol"),
            ("corpus_version", "other-corpus"),
            ("retrieval_scope", "sensitivity_or_diagnostic"),
            ("retrieval_run_classification", "sensitivity_or_diagnostic"),
        ]:
            changed = SimpleNamespace(**vars(run))
            setattr(changed, field, value)
            self.assertFalse(is_failure_recovery_eligible(changed, plan, "corpus_f40d78dbce52"), field)

    def test_q06_v12_read_timeout_recovery_is_limited_to_the_no_output_failure(self):
        plan = approved_plan(plan_id="CI2-v1", question_id="CI2")
        run = SimpleNamespace(
            run_id="experiment-3643a4fc2fb0", question_id="CI2", status="failed", error_code="granite_failure", error_message="ReadTimeout: ",
            raw_model_response=None, raw_repair_response=None, model_name=None,
            model_parameters_json={},
            inference_duration_ms=None, parse_status="not_invoked", repair_attempted=False,
            parsed_response_json=None, structured_response_json=None, display_response_json=None, provenance_validation_json=None,
            retrieval_plan_id="CI2-v1", retrieval_plan_version="1.0",
            retrieval_protocol_version="turin-retrieval-protocol-v1.2",
            formal_authorization_id="turin-q06-v12-primary-authorization",
            corpus_version="corpus_f40d78dbce52", retrieval_scope="corpus_wide",
            retrieval_run_classification="primary",
        )
        self.assertTrue(is_q06_v12_read_timeout_recovery_eligible(run, plan, "corpus_f40d78dbce52"))

        empty_placeholders = SimpleNamespace(**vars(run))
        empty_placeholders.structured_response_json = {}
        empty_placeholders.display_response_json = {}
        empty_placeholders.provenance_validation_json = {}
        self.assertTrue(is_q06_v12_read_timeout_recovery_eligible(empty_placeholders, plan, "corpus_f40d78dbce52"))

        for field, value in [
            ("raw_model_response", "partial output"), ("raw_repair_response", "repair output"),
            ("error_message", "ConnectionError"), ("error_code", "provenance_validation_failure"),
            ("status", "completed"), ("parse_status", "parsed"), ("repair_attempted", True),
            ("parsed_response_json", {"answer": "output"}),
            ("structured_response_json", {"answer": "output"}), ("display_response_json", {"answer": "output"}),
            ("provenance_validation_json", {"valid": False}), ("retrieval_plan_id", "CI2-v2"),
            ("retrieval_protocol_version", "turin-retrieval-protocol-v1.1"), ("corpus_version", "other-corpus"),
            ("formal_authorization_id", "other-authorization"), ("run_id", "other-run"),
            ("question_id", "CI3"), ("model_parameters_json", {"max_tokens": 500}),
        ]:
            changed = SimpleNamespace(**vars(run))
            setattr(changed, field, value)
            self.assertFalse(is_q06_v12_read_timeout_recovery_eligible(changed, plan, "corpus_f40d78dbce52"), field)

        for field in ["structured_response_json", "display_response_json", "provenance_validation_json"]:
            changed = SimpleNamespace(**vars(run))
            setattr(changed, field, [])
            self.assertFalse(is_q06_v12_read_timeout_recovery_eligible(changed, plan, "corpus_f40d78dbce52"), field)

    def test_existing_plan_must_match_exact_execution_snapshot(self):
        plan = approved_plan()
        persisted = SimpleNamespace(plan_json=plan.model_dump(mode="json"))
        database = ExistingPlanDatabase(persisted)

        ExperimentRunService._persist_plan_snapshot(database, plan)
        self.assertEqual(database.added, [])

        persisted.plan_json["top_k"] = 6
        with self.assertRaisesRegex(ValueError, "does not exactly match"):
            ExperimentRunService._persist_plan_snapshot(database, plan)

    def test_immutable_plan_snapshot_accepts_only_omitted_declared_defaults(self):
        plan = approved_plan(temporal_strata=[])
        persisted = plan.model_dump(mode="json")
        del persisted["temporal_strata"]
        database = ExistingPlanDatabase(SimpleNamespace(plan_json=persisted))

        self.assertEqual(
            _normalise_persisted_plan_snapshot(persisted, plan),
            plan.model_dump(mode="json"),
        )
        ExperimentRunService._persist_plan_snapshot(database, plan)

        persisted_optional_null = dict(persisted)
        del persisted_optional_null["supersedes_plan_id"]
        self.assertIsNone(plan.model_dump(mode="json")["supersedes_plan_id"])
        self.assertEqual(
            _normalise_persisted_plan_snapshot(persisted_optional_null, plan),
            plan.model_dump(mode="json"),
        )

        for field, value in [
            ("temporal_strata", [{"stratum_id": "contemporary"}]),
            ("top_k", 6),
            ("retrieval_scope", "sensitivity_or_diagnostic"),
            ("run_classification", "protocol_revision"),
            ("plan_version", "2.0"),
        ]:
            changed = dict(persisted)
            changed[field] = value
            with self.assertRaisesRegex(ValueError, "does not exactly match", msg=field):
                ExperimentRunService._persist_plan_snapshot(ExistingPlanDatabase(SimpleNamespace(plan_json=changed)), plan)

        changed_terms = dict(persisted)
        changed_terms["lexical_facets"] = [{"facet_id": "project", "alternatives": ["different term"]}, {"facet_id": "person", "alternatives": ["Pierre Goumain"]}]
        with self.assertRaisesRegex(ValueError, "does not exactly match"):
            ExperimentRunService._persist_plan_snapshot(ExistingPlanDatabase(SimpleNamespace(plan_json=changed_terms)), plan)

    def test_nested_stratum_defaults_normalise_without_accepting_substantive_changes(self):
        plan = approved_plan(
            plan_id="SM1-v2",
            question_id="SM1",
            plan_version="2.0",
            top_k=6,
            supersedes_plan_id="SM1-v1",
            temporal_strata=[
                TemporalRetrievalStratum(stratum_id="contemporary", classification="contemporary DDR document", top_k=3, year_to=1985),
                TemporalRetrievalStratum(
                    stratum_id="retrospective", classification="later retrospective account", top_k=3, year_from=1986,
                    source_type="oral_history", lexical_facets=[RetrievalFacet(
                        facet_id="retrospective_institutional_fate", alternatives=['\\"future of design research\\"', '\\"close the DDR\\"', '\\"DDR closing\\"'],
                    )],
                ),
            ],
        )
        persisted = plan.model_dump(mode="json")
        del persisted["temporal_strata"][0]["lexical_facets"]
        del persisted["temporal_strata"][1]["year_to"]
        self.assertEqual(_normalise_persisted_plan_snapshot(persisted, plan), plan.model_dump(mode="json"))
        ExperimentRunService._persist_plan_snapshot(ExistingPlanDatabase(SimpleNamespace(plan_json=persisted)), plan)

        explicit_null = plan.model_dump(mode="json")
        self.assertEqual(_normalise_persisted_plan_snapshot(explicit_null, plan), explicit_null)

        changes = [
            ("lexical facets", lambda snapshot: snapshot["temporal_strata"][1].update({"lexical_facets": []})),
            ("retrospective phrase", lambda snapshot: snapshot["temporal_strata"][1]["lexical_facets"][0].update({"alternatives": ['\\"different phrase\\"']})),
            ("contemporary date", lambda snapshot: snapshot["temporal_strata"][0].update({"year_to": 1984})),
            ("source type", lambda snapshot: snapshot["temporal_strata"][1].update({"source_type": "any"})),
            ("allocation", lambda snapshot: snapshot["temporal_strata"][0].update({"top_k": 4})),
            ("top-k", lambda snapshot: snapshot.update({"top_k": 7})),
            ("version", lambda snapshot: snapshot.update({"plan_version": "2.1"})),
        ]
        for label, mutate in changes:
            changed = copy.deepcopy(persisted)
            mutate(changed)
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "does not exactly match"):
                ExperimentRunService._persist_plan_snapshot(ExistingPlanDatabase(SimpleNamespace(plan_json=changed)), plan)

    def test_compiler_ands_facets_and_ors_alternatives(self):
        compiled = compile_retrieval_plan(approved_plan())

        self.assertIn(" || ", compiled.tsquery_expression)
        self.assertIn(" && ", compiled.tsquery_expression)
        self.assertEqual(compiled.lexical_formulation["project"], ["man-computer interaction", "man-computer design systems"])
        self.assertNotIn("documentary traces", " ".join(compiled.parameters.values()))

    def test_unapproved_authority_variant_cannot_enter_retrieval(self):
        plan = approved_plan(authority_variants=[AuthorityDerivedVariant(
            facet_id="project", authority_source="database_authorities.ddr_projects",
            authority_type="ddr_projects", authority_id="171", field="title",
            value="Designer-computer interaction", role="controlled_query_expansion",
            rationale="Controlled project authority label.", approval_state="pending",
        )])

        with self.assertRaisesRegex(ValueError, "Unapproved authority variants"):
            compile_retrieval_plan(plan)

    def test_authority_restriction_requires_diagnostic_scope(self):
        with self.assertRaisesRegex(ValueError, "sensitivity_or_diagnostic"):
            approved_plan(authority_linked_document_ids=["doc-171"])

        diagnostic_plan = approved_plan(
            retrieval_scope="sensitivity_or_diagnostic",
            run_classification="sensitivity_or_diagnostic",
            authority_linked_document_ids=["doc-171"],
            authority_document_link_ids=["link-job-171"],
        )
        self.assertEqual(diagnostic_plan.retrieval_scope, "sensitivity_or_diagnostic")

    def test_plan_retrieval_never_uses_question_as_fts_parameter(self):
        database = PlanDatabase()
        payload = RetrievalValidationService().retrieve(
            database,
            RetrievalValidationRequest(query=QUESTION, top_k=5, retrieval_plan=approved_plan()),
        )

        sql, params = database.calls[-1]
        self.assertIn("compiled_query.tsquery", sql)
        self.assertNotIn("What documentary traces", sql)
        self.assertNotIn("query", params)
        self.assertEqual(payload["transparency"]["compiled_postgresql_tsquery"], "('man-comput' & 'interact')")

    def test_ci3_v1_remains_unstratified_global_top_k(self):
        plan = approved_plan(
            plan_id="CI3-v1",
            question_id="CI3",
            lexical_facets=[
                RetrievalFacet(facet_id="unit", alternatives=["Design Education Unit", "DEU"]),
                RetrievalFacet(facet_id="archive_context", alternatives=["DDR", "Department of Design Research"]),
            ],
        )
        database = PlanDatabase()
        payload = RetrievalValidationService().retrieve(
            database,
            RetrievalValidationRequest(query=QUESTION, top_k=5, retrieval_plan=plan),
        )

        self.assertNotIn("temporal_strata", payload["transparency"])
        self.assertEqual(database.calls[-1][1]["limit"], 5)
        self.assertNotIn("stratum", payload["results"][0])

    def test_sm1_v1_remains_unstratified_with_its_historical_top_k(self):
        plan = approved_plan(
            plan_id="SM1-v1",
            question_id="SM1",
            lexical_facets=[
                RetrievalFacet(facet_id="institution", alternatives=["Department of Design Research", "DDR"]),
                RetrievalFacet(facet_id="institutional_decision_status", alternatives=["Department of Architectural and Design Studies"]),
            ],
        )
        database = PlanDatabase()
        payload = RetrievalValidationService().retrieve(
            database, RetrievalValidationRequest(query=QUESTION, top_k=5, corpus_version="corpus_f40d78dbce52", retrieval_plan=plan),
        )

        self.assertEqual(plan.top_k, 5)
        self.assertFalse(plan.temporal_strata)
        self.assertNotIn("temporal_strata", payload["transparency"])
        self.assertEqual(database.calls[-1][1]["limit"], 5)
        self.assertEqual(database.calls[-1][1]["corpus_version"], "corpus_f40d78dbce52")

    def test_ci3_v2_stratifies_the_unchanged_compiled_query_and_backfills_missing_retrospective_capacity(self):
        plan = approved_plan(
            plan_id="CI3-v2",
            question_id="CI3",
            plan_version="2.0",
            top_k=6,
            run_classification="protocol_revision",
            supersedes_plan_id="CI3-v1",
            lexical_facets=[
                RetrievalFacet(facet_id="unit", alternatives=["Design Education Unit", "DEU"]),
                RetrievalFacet(facet_id="archive_context", alternatives=["DDR", "Department of Design Research"]),
            ],
            temporal_strata=[
                TemporalRetrievalStratum(stratum_id="contemporary", classification="contemporary DDR document", top_k=4, year_to=1985),
                TemporalRetrievalStratum(stratum_id="retrospective", classification="later retrospective account", top_k=2, year_from=1986, source_type="oral_history"),
            ],
        )
        database = StratifiedPlanDatabase()
        payload = RetrievalValidationService().retrieve(
            database,
            RetrievalValidationRequest(query=QUESTION, top_k=6, retrieval_plan=plan),
        )

        self.assertEqual([result["stratum"] for result in payload["results"]], ["contemporary"] * 5 + ["retrospective"])
        self.assertEqual([result["within_stratum_rank"] for result in payload["results"]], [1, 2, 3, 4, 5, 1])
        self.assertEqual([result["rank"] for result in payload["results"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual(payload["transparency"]["temporal_strata"], [
            {"stratum": "contemporary", "requested_top_k": 4, "retrieved": 5},
            {"stratum": "retrospective", "requested_top_k": 2, "retrieved": 1},
        ])
        self.assertEqual(database.calls[1][1]["limit"], 2)
        self.assertEqual(database.calls[2][1]["limit"], 5)
        self.assertIn("compiled_query.tsquery", database.calls[1][0])
        self.assertIn("compiled_query.tsquery", database.calls[2][0])
        self.assertNotIn("retrospective", " ".join(plan.lexical_facets[0].alternatives + plan.lexical_facets[1].alternatives).lower())
        self.assertIn("COALESCE(d.authority_data->>'record_title', '') ILIKE '%oral histor%'", database.calls[1][0])

    def test_sm1_v2_allows_a_distinct_retrospective_query_without_document_restriction(self):
        plan = approved_plan(
            plan_id="SM1-v2",
            question_id="SM1",
            plan_version="2.0",
            top_k=6,
            supersedes_plan_id="SM1-v1",
            temporal_strata=[
                TemporalRetrievalStratum(
                    stratum_id="contemporary", classification="contemporary DDR document", top_k=3, year_to=1985,
                ),
                TemporalRetrievalStratum(
                    stratum_id="retrospective", classification="later retrospective account", top_k=3, year_from=1986,
                    source_type="oral_history", lexical_facets=[
                        RetrievalFacet(
                            facet_id="retrospective_institutional_fate",
                            alternatives=['"future of design research"', '"close the DDR"', '"DDR closing"'],
                        ),
                    ],
                ),
            ],
        )
        database = StratifiedPlanDatabase()
        first = RetrievalValidationService().retrieve(
            database, RetrievalValidationRequest(query=QUESTION, top_k=6, retrieval_plan=plan),
        )
        second = RetrievalValidationService().retrieve(
            StratifiedPlanDatabase(), RetrievalValidationRequest(query=QUESTION, top_k=6, retrieval_plan=plan),
        )

        self.assertEqual([item["chunk_id"] for item in first["results"]], [item["chunk_id"] for item in second["results"]])
        self.assertEqual(first["transparency"]["temporal_strata"], [
            {"stratum": "contemporary", "requested_top_k": 3, "retrieved": 5},
            {"stratum": "retrospective", "requested_top_k": 3, "retrieved": 1},
        ])
        self.assertEqual(first["results"][0]["stratum"], "contemporary")
        self.assertEqual(first["results"][-1]["stratum"], "retrospective")
        self.assertEqual(first["transparency"]["temporal_stratum_lexical_formulations"]["retrospective"], {
            "retrospective_institutional_fate": ['"future of design research"', '"close the DDR"', '"DDR closing"'],
        })
        self.assertEqual(plan.authority_linked_document_ids, [])
        self.assertNotIn("Frayling", str(plan.model_dump()))

    def test_sm1_v2_keeps_three_by_three_strata_without_cross_stratum_rescoring(self):
        plan = approved_plan(
            plan_id="SM1-v2",
            question_id="SM1",
            plan_version="2.0",
            top_k=6,
            supersedes_plan_id="SM1-v1",
            temporal_strata=[
                TemporalRetrievalStratum(stratum_id="contemporary", classification="contemporary DDR document", top_k=3, year_to=1985),
                TemporalRetrievalStratum(
                    stratum_id="retrospective", classification="later retrospective account", top_k=3, year_from=1986,
                    source_type="oral_history", lexical_facets=[RetrievalFacet(
                        facet_id="retrospective_institutional_fate", alternatives=['"future of design research"'],
                    )],
                ),
            ],
        )
        payload = RetrievalValidationService().retrieve(
            BalancedStratifiedPlanDatabase(), RetrievalValidationRequest(query=QUESTION, top_k=6, corpus_version="corpus_f40d78dbce52", retrieval_plan=plan),
        )

        self.assertEqual([item["stratum"] for item in payload["results"]], ["contemporary"] * 3 + ["retrospective"] * 3)
        self.assertEqual([item["within_stratum_rank"] for item in payload["results"]], [1, 2, 3, 1, 2, 3])
        self.assertEqual([item["rank"] for item in payload["results"]], [1, 2, 3, 4, 5, 6])
        self.assertGreater(payload["results"][3]["score"], payload["results"][0]["score"])

    def test_formal_run_requires_production_and_approved_plan(self):
        request = ExperimentRunRequest(
            research_case="known_relationship", research_question=QUESTION,
            question_id="KR1", retrieval_plan=approved_plan(),
            retrieval=RetrievalValidationRequest(query=QUESTION, top_k=5),
        )
        with patch.object(settings, "ENVIRONMENT", "development"):
            with self.assertRaisesRegex(ValueError, "only in production"):
                ExperimentRunService()._prepare_formal_request(request)

        with patch.object(settings, "ENVIRONMENT", "production"):
            rejected = request.model_copy(update={"retrieval_plan": approved_plan(researcher_approval_state="pending", researcher_approved_at=None)})
            with self.assertRaisesRegex(ValueError, "researcher-approved retrieval plan"):
                ExperimentRunService()._prepare_formal_request(rejected)

    def test_formal_run_requires_exact_registered_question(self):
        request = ExperimentRunRequest(
            research_case="known_relationship", research_question="Changed question text",
            question_id="KR1", retrieval_plan=approved_plan(),
            retrieval=RetrievalValidationRequest(query="Changed question text", top_k=5),
        )
        with patch.object(settings, "ENVIRONMENT", "production"):
            with self.assertRaisesRegex(ValueError, "exact approved question text"):
                ExperimentRunService()._prepare_formal_request(request)

    def test_formal_run_snapshots_plan_and_execution_environment(self):
        request = ExperimentRunRequest(
            research_case="known_relationship", research_question=QUESTION,
            question_id="KR1", retrieval_plan=approved_plan(),
            retrieval=RetrievalValidationRequest(query=QUESTION, top_k=5),
        )
        database = FakeDatabase()
        with patch.object(settings, "ENVIRONMENT", "production"):
            run = asyncio.run(ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite()).run_archival_experiment(database, request))

        self.assertEqual(run.retrieval_plan_id, "KR1-v1")
        self.assertEqual(run.retrieval_scope, "corpus_wide")
        self.assertEqual(run.execution_environment, "production")
        self.assertTrue(any(item.__class__.__name__ == "TurinRetrievalPlan" for item in database.added))

    def test_zero_retrieval_does_not_reformulate_an_approved_plan(self):
        class EmptyRetrieval:
            def __init__(self):
                self.calls = []

            def retrieve(self, _, request):
                self.calls.append(request)
                return {"transparency": {"original_query": request.query}, "results": [], "diagnostics": {"result_count": 0, "notes": []}, "corpus_versions": []}

        retrieval = EmptyRetrieval()
        request = ExperimentRunRequest(
            research_case="known_relationship", research_question=QUESTION,
            question_id="KR1", retrieval_plan=approved_plan(),
            retrieval=RetrievalValidationRequest(query=QUESTION, top_k=5),
        )
        with patch.object(settings, "ENVIRONMENT", "production"):
            run = asyncio.run(ExperimentRunService(retrieval_service=retrieval, inference_service=FakeGranite()).run_archival_experiment(FakeDatabase(), request))

        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(run.status, "completed_with_missingness")
        self.assertEqual(run.retrieval_plan_id, "KR1-v1")

    def test_later_plan_version_creates_a_distinct_immutable_snapshot(self):
        first_request = ExperimentRunRequest(
            research_case="known_relationship", research_question=QUESTION,
            question_id="KR1", retrieval_plan=approved_plan(),
            retrieval=RetrievalValidationRequest(query=QUESTION, top_k=5),
        )
        second_request = first_request.model_copy(update={
            "retrieval_plan": approved_plan(plan_id="KR1-v2", plan_version="2.0", run_classification="protocol_revision", supersedes_plan_id="KR1-v1"),
        })
        with patch.object(settings, "ENVIRONMENT", "production"):
            service = ExperimentRunService(retrieval_service=FixtureRetrieval(), inference_service=FakeGranite())
            first = asyncio.run(service.run_archival_experiment(FakeDatabase(), first_request))
            second = asyncio.run(service.run_archival_experiment(FakeDatabase(), second_request))

        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(second.retrieval_plan_version, "2.0")
        self.assertEqual(second.retrieval_run_classification, "protocol_revision")

    def test_protocol_revision_requires_the_superseded_plan(self):
        with self.assertRaisesRegex(ValueError, "superseded retrieval plan ID"):
            approved_plan(plan_id="KR1-v2", plan_version="2.0", run_classification="protocol_revision")


if __name__ == "__main__":
    unittest.main()