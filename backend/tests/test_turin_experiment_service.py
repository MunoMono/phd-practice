import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_experiment_service import (
    ArchivalAnalysisResponse,
    AuthorityContext,
    ContextBuilder,
    GraniteExperimentService,
    parse_with_one_repair,
    render_prompt,
    validate_provenance,
)


FIXTURE_CHUNKS = [
    {
        "id": "fixture-chunk-1", "chunk_id": "fixture-chunk-1", "document_id": "fixture-doc-1",
        "pid": "fixture-pid-1", "source_page": 4, "archive_resolution_status": "resolved_current",
        "text": "Archer and Baynes agreed that the Design Education Unit should continue.",
        "catalogue_metadata": {"title": "DEU memorandum"},
    },
    {
        "id": "fixture-chunk-2", "chunk_id": "fixture-chunk-2", "document_id": "fixture-doc-2",
        "pid": "fixture-pid-2", "source_page": 9, "archive_resolution_status": "resolved_current",
        "text": "The committee rejected the proposal; OCR reads rejectd in the margin.",
        "catalogue_metadata": {"title": "Committee minutes"},
    },
]


VALID_RESPONSE = '''{"answer":"The supplied memorandum supports a relationship.","evidence":[{"claim":"Archer and Baynes agreed.","pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1","quotation_or_paraphrase":"Archer and Baynes agreed that the Design Education Unit should continue."}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[]}'''


class FakeGranite:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get_load_status(self):
        return {"model_ready": True, "model_status": "ready"}

    def get_model_info(self):
        return {"model_name": "fixture-granite", "runtime": "fake", "quantized": "fixture"}

    async def generate_experiment(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {"raw_response": next(self.responses), "generation": kwargs}


class TurinExperimentContextTests(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()

    def test_context_preserves_order_identifiers_and_is_deterministic(self):
        first = self.builder.assemble(FIXTURE_CHUNKS, context_budget=3000)
        second = self.builder.assemble(FIXTURE_CHUNKS, context_budget=3000)
        self.assertEqual(first.context, second.context)
        self.assertLess(first.context.index("EVIDENCE 1"), first.context.index("EVIDENCE 2"))
        self.assertIn("PID: fixture-pid-1", first.context)
        self.assertIn("CHUNK: fixture-chunk-2", first.context)

    def test_context_budget_omits_whole_chunk_without_truncation(self):
        result = self.builder.assemble(FIXTURE_CHUNKS, context_budget=400)
        self.assertEqual(result.document_chunk_count, 1)
        self.assertEqual(result.omitted_chunk_ids, ["fixture-chunk-2"])
        self.assertNotIn("committee rejected", result.context)
        self.assertLessEqual(result.context_character_count, result.context_budget)

    def test_final_input_budget_is_deterministic_and_records_an_excerpt(self):
        oversized = [dict(FIXTURE_CHUNKS[0], text="source text " * 1000)]
        first = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", oversized, input_budget=3000)
        second = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", oversized, input_budget=3000)
        _, prompt = render_prompt("known_relationship", "What relationship is supported?", first)
        decision = first.evidence_decisions[0]
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertLessEqual(len(prompt), 3000)
        self.assertTrue(decision["included_in_context"])
        self.assertTrue(decision["excerpted"])
        self.assertEqual(decision["supplied_chars"], len(first.supplied_chunks[0]["text"]))
        self.assertIn("PID: fixture-pid-1", first.context)

    def test_authority_is_separate_and_document_only_excludes_it(self):
        authority = AuthorityContext(source="fixture-db", authority_type="catalogue", authority_id="a-1", role="controlled_query_expansion", fields={"term": "DEU"})
        document_only = self.builder.assemble(FIXTURE_CHUNKS, authority_context=[authority], context_budget=3000)
        combined = self.builder.assemble(FIXTURE_CHUNKS, authority_context=[authority], authority_mode="document_plus_authority_context", context_budget=3000)
        self.assertNotIn("AUTHORITY CONTEXT", document_only.context)
        self.assertIn("[ARCHIVE / DATABASE AUTHORITY CONTEXT]", combined.context)
        self.assertNotIn("TEXT:\nDEU", combined.context)

    def test_prompt_register_has_distinct_versioned_research_cases(self):
        context = self.builder.assemble(FIXTURE_CHUNKS, context_budget=3000)
        template, prompt = render_prompt("scoped_missingness", "What is not established?", context)
        self.assertEqual(template.prompt_version, "v3")
        self.assertIn("Use only the supplied context.", prompt)
        self.assertIn("do not claim historical absence", prompt)
        self.assertIn("SOURCE DOCUMENT EVIDENCE", prompt)


class TurinExperimentParsingAndProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.context = ContextBuilder().assemble(FIXTURE_CHUNKS, context_budget=3000)

    def test_valid_json_retains_raw_response(self):
        result = asyncio.run(parse_with_one_repair(VALID_RESPONSE))
        self.assertEqual(result.raw_response, VALID_RESPONSE)
        self.assertIsNotNone(result.response)
        self.assertFalse(result.repair_attempted)

    def test_singleton_schema_object_is_normalized_and_recorded(self):
        singleton = VALID_RESPONSE.replace('"missingness":[]', '"missingness":{"scope":"fixture","category":"scope","explanation":"No additional support."}')
        result = asyncio.run(parse_with_one_repair(singleton))
        self.assertIsNotNone(result.response)
        self.assertEqual(len(result.response.missingness), 1)
        self.assertEqual(result.structural_normalisations, ["missingness: singleton object normalized to list"])

    def test_malformed_json_uses_exactly_one_repair_attempt(self):
        calls = []
        async def repair(prompt):
            calls.append(prompt)
            return VALID_RESPONSE
        result = asyncio.run(parse_with_one_repair("{not json", repair))
        self.assertTrue(result.repair_attempted)
        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(result.response)
        self.assertIn("formatting and schema only", calls[0])

    def test_unrecoverable_parse_failure_retains_both_raw_outputs(self):
        async def repair(_):
            return "still malformed"
        result = asyncio.run(parse_with_one_repair("bad", repair))
        self.assertTrue(result.repair_attempted)
        self.assertEqual(result.repaired_response, "still malformed")
        self.assertIsNone(result.response)

    def test_provenance_validates_citation_and_approximate_ocr_quote(self):
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        result = validate_provenance(response, self.context)
        self.assertTrue(result.valid)
        damaged = response.model_copy(deep=True)
        damaged.evidence[0].quotation_or_paraphrase = "Archer Baynes agreed Design Education Unit continue"
        self.assertTrue(validate_provenance(damaged, self.context).valid)

    def test_provenance_rejects_invented_wrong_omitted_and_page_citations(self):
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.evidence[0].chunk_id = "invented"
        self.assertFalse(validate_provenance(response, self.context).valid)
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.evidence[0].pid = "wrong-pid"
        self.assertFalse(validate_provenance(response, self.context).valid)
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.evidence[0].page = 99
        self.assertFalse(validate_provenance(response, self.context).valid)
        constrained = ContextBuilder().assemble(FIXTURE_CHUNKS, context_budget=400)
        response.evidence[0].chunk_id = "fixture-chunk-2"
        response.evidence[0].pid = "fixture-pid-2"
        response.evidence[0].page = 9
        self.assertIn("omitted", validate_provenance(response, constrained).issues[0])

    def test_authority_assertion_is_not_treated_as_documentary_evidence(self):
        authority = AuthorityContext(source="fixture-db", authority_type="catalogue", authority_id="a-1", role="controlled_query_expansion", fields={"term": "DEU"})
        context = ContextBuilder().assemble(FIXTURE_CHUNKS, authority_context=[authority], authority_mode="document_plus_authority_context", context_budget=3000)
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.authority_assertions = [{"assertion": "DEU is an authority term.", "source": "fixture-db", "authority_id": "a-1"}]
        self.assertTrue(validate_provenance(response, context).valid)
        response.authority_assertions = [{"assertion": "DEU is an authority term.", "source": "fixture-db", "authority_id": "invented-authority"}]
        self.assertFalse(validate_provenance(response, context).valid)

    def test_fixture_inference_is_bounded_and_does_not_convert_missingness(self):
        granite = FakeGranite([VALID_RESPONSE])
        service = GraniteExperimentService(granite)
        result = asyncio.run(service.infer("scoped_missingness", "What is not established?", self.context))
        self.assertTrue(result["provenance"]["valid"])
        self.assertEqual(granite.calls[0][1], {"max_tokens": 350, "temperature": 0.0, "top_p": 1.0, "do_sample": False})
        self.assertNotIn("historical absence", result["parsed"]["response"]["answer"].lower())


if __name__ == "__main__":
    unittest.main()