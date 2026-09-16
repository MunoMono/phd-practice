import asyncio
import json
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_experiment_service import (
    ArchivalAnalysisResponse,
    AuthorityContext,
    ContextBuilder,
    ContextRepresentationError,
    GraniteExperimentService,
    LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS,
    OUTPUT_CAPACITY_PROTOCOL_VERSION,
    PROMPT_REGISTER,
    STRUCTURED_OUTPUT_MAX_TOKENS,
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


VALID_RESPONSE = '''{"answer":"The supplied memorandum supports a relationship.","evidence":[{"claim":"Archer and Baynes agreed.","source_pid":"fixture-pid-1","page":4,"chunk_id":"fixture-chunk-1","quotation_or_paraphrase":"Archer and Baynes agreed that the Design Education Unit should continue."}],"inferences":[],"contradictions":[],"missingness":[],"follow_up_queries":[]}'''


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
        self.assertIn("SOURCE PID: fixture-pid-1", first.context)
        self.assertIn("CHUNK ID: fixture-chunk-2", first.context)

    def test_context_budget_omits_whole_chunk_without_truncation(self):
        result = self.builder.assemble(FIXTURE_CHUNKS, context_budget=400)
        self.assertEqual(result.document_chunk_count, 1)
        self.assertEqual(result.omitted_chunk_ids, ["fixture-chunk-2"])
        self.assertNotIn("committee rejected", result.context)
        self.assertLessEqual(result.context_character_count, result.context_budget)

    def test_final_input_budget_is_deterministic_and_records_an_excerpt(self):
        oversized = [dict(FIXTURE_CHUNKS[0], text="source text " * 1000)]
        first = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", oversized, input_budget=4000)
        second = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", oversized, input_budget=4000)
        _, prompt = render_prompt("known_relationship", "What relationship is supported?", first)
        decision = first.evidence_decisions[0]
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertLessEqual(len(prompt), 4000)
        self.assertTrue(decision["included_in_context"])
        self.assertTrue(decision["excerpted"])
        self.assertEqual(decision["supplied_chars"], len(first.supplied_chunks[0]["text"]))
        self.assertIn("SOURCE PID: fixture-pid-1", first.context)

    def test_v11_represents_every_rank_with_direct_max_min_excerpts(self):
        chunks = [
            dict(FIXTURE_CHUNKS[0], id=f"fixture-{index}", chunk_id=f"fixture-{index}", document_id=f"document-{index}", pid=f"pid-{index}", text=("source text " * length))
            for index, length in enumerate((100, 120, 1, 2, 120), 1)
        ]
        chunks[2]["text"] = "x"
        chunks[3]["text"] = "y"
        first = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", chunks, input_budget=4000)
        second = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", chunks, input_budget=4000)

        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(first.document_chunk_count, 5)
        self.assertEqual(first.omitted_chunk_ids, [])
        self.assertTrue(all(item["included_in_context"] for item in first.evidence_decisions))
        self.assertTrue(all(f"SOURCE PID: pid-{index}" in first.context for index in range(1, 6)))
        self.assertTrue(all(item["text"] in item["original_text"] for item in first.supplied_chunks))
        decisions = {item["retrieval_rank"]: item for item in first.evidence_decisions}
        self.assertFalse(decisions[3]["excerpted"])
        self.assertFalse(decisions[4]["excerpted"])
        self.assertEqual(decisions[1]["supplied_chars"], decisions[2]["supplied_chars"])
        self.assertEqual(decisions[2]["supplied_chars"], decisions[5]["supplied_chars"])

    def test_v11_fails_before_generation_when_all_headers_cannot_fit(self):
        chunks = [dict(FIXTURE_CHUNKS[0], id=f"fixture-{index}", chunk_id=f"fixture-{index}", document_id=f"document-{index}", pid=f"pid-{index}") for index in range(1, 6)]
        question = "What relationship is supported?"
        template = PROMPT_REGISTER["known_relationship"]
        fixed_prompt_chars = len(f"{template.system_template}\n\n{template.user_template.replace('{question}', question).replace('{context}', '')}")
        header_chars = sum(len(self.builder._document_block(index, chunk, None, "")) for index, chunk in enumerate(chunks, 1)) + 8

        with self.assertRaises(ContextRepresentationError):
            self.builder.assemble_for_prompt("known_relationship", question, chunks, input_budget=fixed_prompt_chars + header_chars - 1)

    def test_v11_authority_cannot_displace_documentary_representation(self):
        chunks = [dict(FIXTURE_CHUNKS[0], id=f"fixture-{index}", chunk_id=f"fixture-{index}", document_id=f"document-{index}", pid=f"pid-{index}") for index in range(1, 6)]
        authority = AuthorityContext(source="fixture-db", authority_type="catalogue", authority_id="a-1", role="structural_context", fields={"note": "x" * 5000})
        result = self.builder.assemble_for_prompt("known_relationship", "What relationship is supported?", chunks, authority_context=[authority], authority_mode="document_plus_authority_context", input_budget=4000)

        self.assertEqual(result.document_chunk_count, 5)
        self.assertTrue(result.authority_context_requested)
        self.assertFalse(result.authority_context_included)
        self.assertEqual(result.authority_context_omitted_reason, "authority_context_exceeds_remaining_documentary_budget")

    def test_v11_q02_frozen_retrieval_shape_represents_all_five_sources(self):
        frozen_sources = [
            ("turin_doc_287080879712_23ba7078a89a_2_7_2e9518aee318db8f", "doc_287080879712_23ba7078a89a", "287080879712", "Design Dimension Project proposed publications", 859),
            ("turin_doc_338541406157_3c95cfa4ad23_2_7_acf063e79badfe9b", "doc_338541406157_3c95cfa4ad23", "338541406157", "Paper for Imperial Chemical Industries", 1197),
            ("turin_doc_896818280654_d6f37b80240d_7_43_062f90c197b279ab", "doc_896818280654_d6f37b80240d", "896818280654", "Department of Design Research brochure", 133),
            ("turin_doc_930287260339_9640c875ff8d_2_11_152d6c9239bb7846", "doc_930287260339_9640c875ff8d", "930287260339", "Interview with Anthony Finkelstein", 228),
            ("turin_doc_521129471965_26e48f4ee403_4_1_2e3df79b8a436929", "doc_521129471965_26e48f4ee403", "521129471965", "Rector's report", 1197),
        ]
        chunks = [
            {"chunk_id": chunk_id, "document_id": document_id, "pid": pid, "source_page": index + 1, "archive_resolution_status": "resolved_current", "catalogue_metadata": {"title": title}, "text": ("source " * ((length // 7) + 1))[:length]}
            for index, (chunk_id, document_id, pid, title, length) in enumerate(frozen_sources)
        ]
        question = "How is Bruce Archer's role in teaching and learning practice with students represented across multiple DDR documents, and what aspects of that role are directly evidenced rather than inferred?"
        result = self.builder.assemble_for_prompt("known_relationship", question, chunks, input_budget=6000)

        self.assertEqual(result.document_chunk_count, 5)
        self.assertEqual(result.omitted_chunk_ids, [])
        self.assertLessEqual(result.assembled_input_chars, 6000)
        self.assertTrue(all(item["included_in_context"] for item in result.evidence_decisions))
        self.assertTrue(all(item["supplied_chars"] > 0 for item in result.evidence_decisions))

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

    def test_known_relationship_prompt_requires_one_complete_evidence_object(self):
        context = self.builder.assemble(FIXTURE_CHUNKS, context_budget=3000)
        _, prompt = render_prompt("known_relationship", "What relationship is supported?", context)
        self.assertIn("The evidence array must contain exactly one complete object.", prompt)
        self.assertIn("Do not split evidence fields across multiple objects.", prompt)
        self.assertIn("claim, source_pid, page, chunk_id, and quotation_or_paraphrase", prompt)


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
        response.evidence[0].source_pid = "wrong-pid"
        invalid = validate_provenance(response, self.context)
        self.assertFalse(invalid.valid)
        self.assertIn("citation_identifier_mismatch", invalid.issues[0])
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.evidence[0].page = 99
        self.assertFalse(validate_provenance(response, self.context).valid)
        constrained = ContextBuilder().assemble(FIXTURE_CHUNKS, context_budget=400)
        response.evidence[0].chunk_id = "fixture-chunk-2"
        response.evidence[0].source_pid = "fixture-pid-2"
        response.evidence[0].page = 9
        self.assertIn("omitted", validate_provenance(response, constrained).issues[0])

    def test_provenance_rejects_non_source_pid_namespaces_without_reclassifying_claim_support(self):
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        for invalid_source_pid in ("fixture-doc-1", "pid-1-derived", "fixture-record-1"):
            invalid = response.model_copy(deep=True)
            invalid.evidence[0].source_pid = invalid_source_pid
            result = validate_provenance(invalid, self.context)
            self.assertFalse(result.valid)
            self.assertEqual(result.valid_claims, 0)
            self.assertEqual(result.invalid_claims, 1)
            self.assertTrue(result.issues[0].startswith("citation_identifier_mismatch:"))

    def test_authority_assertion_is_not_treated_as_documentary_evidence(self):
        authority = AuthorityContext(source="fixture-db", authority_type="catalogue", authority_id="a-1", role="controlled_query_expansion", fields={"term": "DEU"})
        context = ContextBuilder().assemble(FIXTURE_CHUNKS, authority_context=[authority], authority_mode="document_plus_authority_context", context_budget=3000)
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.authority_assertions = [{"assertion": "DEU is an authority term.", "source": "fixture-db", "authority_id": "a-1"}]
        self.assertTrue(validate_provenance(response, context).valid)
        response.authority_assertions = [{"assertion": "DEU is an authority term.", "source": "fixture-db", "authority_id": "invented-authority"}]
        self.assertFalse(validate_provenance(response, context).valid)

    def test_v16_non_documentary_authority_context_validates_authority_assertions(self):
        authority = AuthorityContext(source="fixture-db", authority_type="agent_employment", authority_id="a-1", role="structural_context", fields={"name": "Henrietta Ryott"})
        context = ContextBuilder().assemble_for_prompt("scoped_missingness", "What can the corpus establish?", [], authority_context=[authority], authority_mode="document_plus_authority_context", zero_documentary_evidence=True)
        response = ArchivalAnalysisResponse.model_validate_json(VALID_RESPONSE)
        response.evidence = []
        response.authority_assertions = [{"assertion": "The authority record lists Henrietta Ryott.", "source": "fixture-db", "authority_id": "a-1"}]
        self.assertTrue(validate_provenance(response, context).valid)

    def test_fixture_inference_is_bounded_and_does_not_convert_missingness(self):
        granite = FakeGranite([VALID_RESPONSE])
        service = GraniteExperimentService(granite)
        result = asyncio.run(service.infer("scoped_missingness", "What is not established?", self.context, max_tokens=STRUCTURED_OUTPUT_MAX_TOKENS))
        self.assertTrue(result["provenance"]["valid"])
        self.assertEqual(STRUCTURED_OUTPUT_MAX_TOKENS, 500)
        self.assertEqual({key: value for key, value in granite.calls[0][1].items() if key != "response_schema"}, {"max_tokens": 500, "temperature": 0.0, "top_p": 1.0, "do_sample": False})
        self.assertEqual(result["response_schema_version"], "turin-archival-analysis-response-v1")
        self.assertIn("$defs", granite.calls[0][1]["response_schema"])
        self.assertNotIn("historical absence", result["parsed"]["response"]["answer"].lower())

    def test_output_capacity_dispatch_preserves_historical_protocols_and_adds_v14(self):
        from app.services.turin_experiment_service import V13_OUTPUT_CAPACITY_PROTOCOL_VERSION, V13_STRUCTURED_OUTPUT_MAX_TOKENS, V14_OUTPUT_CAPACITY_PROTOCOL_VERSION, V14_STRUCTURED_OUTPUT_MAX_TOKENS, structured_output_max_tokens

        self.assertEqual(structured_output_max_tokens(OUTPUT_CAPACITY_PROTOCOL_VERSION), STRUCTURED_OUTPUT_MAX_TOKENS)
        self.assertEqual(structured_output_max_tokens(V13_OUTPUT_CAPACITY_PROTOCOL_VERSION), V13_STRUCTURED_OUTPUT_MAX_TOKENS)
        self.assertEqual(structured_output_max_tokens(V14_OUTPUT_CAPACITY_PROTOCOL_VERSION), V14_STRUCTURED_OUTPUT_MAX_TOKENS)
        self.assertEqual(structured_output_max_tokens("turin-retrieval-protocol-v1.1"), LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS)
        self.assertEqual(structured_output_max_tokens(None), LEGACY_STRUCTURED_OUTPUT_MAX_TOKENS)

    def test_v15_schema_enforces_the_existing_concise_response_contract(self):
        from app.services.turin_experiment_service import CONCISE_RESPONSE_SCHEMA_VERSION, ConciseArchivalAnalysisResponse, V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, parse_with_one_repair, response_schema_definition, response_schema_version, structured_output_max_tokens

        concise = json.loads(VALID_RESPONSE)
        self.assertIsNotNone(ConciseArchivalAnalysisResponse.model_validate(concise))
        self.assertEqual(response_schema_version(V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION), CONCISE_RESPONSE_SCHEMA_VERSION)
        self.assertEqual(structured_output_max_tokens(V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION), 1500)
        parsed = asyncio.run(parse_with_one_repair(VALID_RESPONSE, response_model=ConciseArchivalAnalysisResponse))
        self.assertIsInstance(parsed.response, ConciseArchivalAnalysisResponse)
        historical_schema = response_schema_definition()
        concise_schema = response_schema_definition(V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION)
        self.assertNotIn("maxLength", json.dumps(historical_schema))
        self.assertIn('"maxItems": 1', json.dumps(concise_schema))
        self.assertIn('"maxLength": 180', json.dumps(concise_schema))
        self.assertEqual(response_schema_version(V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION), CONCISE_RESPONSE_SCHEMA_VERSION)
        self.assertEqual(response_schema_definition(V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION), concise_schema)
        self.assertEqual(structured_output_max_tokens(V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION), 1500)

        for field in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions"):
            invalid = json.loads(VALID_RESPONSE)
            if field == "evidence":
                invalid[field].append(dict(invalid[field][0]))
            elif field == "inferences":
                invalid[field] = [{"inference": "bounded", "supporting_sources": ["fixture-chunk-1"], "confidence": "low", "rationale": "bounded"}] * 2
            elif field == "contradictions":
                invalid[field] = [{"description": "bounded", "sources": []}] * 2
            elif field == "missingness":
                invalid[field] = [{"scope": "bounded", "category": "bounded", "explanation": "bounded"}] * 2
            elif field == "follow_up_queries":
                invalid[field] = ["bounded", "second"]
            else:
                invalid[field] = [{"assertion": "bounded", "source": "fixture", "authority_id": "fixture"}] * 2
            with self.assertRaises(ValidationError, msg=field):
                ConciseArchivalAnalysisResponse.model_validate(invalid)

        for path in (("answer",), ("evidence", 0, "claim"), ("evidence", 0, "quotation_or_paraphrase"), ("inferences", 0, "inference"), ("inferences", 0, "rationale"), ("contradictions", 0, "description"), ("missingness", 0, "scope"), ("missingness", 0, "category"), ("missingness", 0, "explanation"), ("follow_up_queries", 0), ("authority_assertions", 0, "assertion")):
            invalid = json.loads(VALID_RESPONSE)
            if path[0] == "inferences":
                invalid["inferences"] = [{"inference": "bounded", "supporting_sources": [], "confidence": "low", "rationale": "bounded"}]
            elif path[0] == "contradictions":
                invalid["contradictions"] = [{"description": "bounded", "sources": []}]
            elif path[0] == "missingness":
                invalid["missingness"] = [{"scope": "bounded", "category": "bounded", "explanation": "bounded"}]
            elif path[0] == "authority_assertions":
                invalid["authority_assertions"] = [{"assertion": "bounded", "source": "fixture", "authority_id": "fixture"}]
            elif path[0] == "follow_up_queries":
                invalid["follow_up_queries"] = ["bounded"]
            target = invalid
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "x" * 181
            with self.assertRaises(ValidationError, msg=str(path)):
                ConciseArchivalAnalysisResponse.model_validate(invalid)


if __name__ == "__main__":
    unittest.main()