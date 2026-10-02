import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_evidence_pipeline_service import (
    CrossSourceAnalysis, EvidenceReference, FinalSynthesis, SourceClaim, SourceEvidencePacket,
    EvidencePipelineStageError, EvidencePacketBuilder, StagedEvidencePipeline, SourceAnalysis, EvidenceSourceAnalysis, BatchedEvidenceSourceAnalyses, apply_archer_teaching_evidence_guard, apply_baynes_roberts_evidence_guard, apply_wood_console_evidence_guard, apply_systematic_design_interpretation_guard, apply_configured_synthesis_guard, apply_closure_missingness_guard, apply_computing_initiation_missingness_guard, apply_user_reception_missingness_guard, apply_ryott_role_guard, build_batched_source_prompt, contextual_only_source_analyses, document_content_source_analyses, format_batched_source_packet, build_evidence_map, validate_batched_source_analyses, validate_cross_source_inferences, validate_final_evidence_types, source_status, validate_claims,
)
from app.services.turin_evidence_pipeline_service import NarrativeClaim, NarrativeProse, NarrativeProseItem, NarrativeSynthesis, answer_prose_moves, application_owned_temporal_rendering, bind_answer_prose_to_moves, bind_prose_to_claim_plan, build_evidence_map, canonical_narrative_ledger, complete_answer_prose_with_move_fallback, complete_prose_with_plan_fallback, compile_evidence_cards, compile_evidence_ledger, compact_cross_source_input, configured_scoped_missingness_narrative, cross_source_analysis_payload, filter_prose_evidence_label_violations, narrative_contract_state, packet_evidence_type, parse_structured_response, refresh_evidence_cards, researcher_prose_issues, retrieval_adequacy_from_diagnostics, scoped_missingness_decision, thematic_document_content_source_analyses, thematic_narrative_coverage_complete, validate_narrative_evidence_labels, validate_rendered_claim_support
from app.services.turin_final_synthesis_snapshot_service import load_final_synthesis_snapshot, write_pre_final_snapshot
from app.services.turin_compact_final_claim_plan import CompactFinalClaimPlan, classify_answer_shape, comparison_move_covered, compact_claim_plan_input, compile_final_claim_plan, relevant_final_limits, validate_compact_claim_plan
from app.services.turin_question_policy import matching_turin_question_policy


PACKET = SourceEvidencePacket(
    source_id="doc-1:chunk-2",
    document={"document_id": "doc-1"}, retrieval_match={"chunk_id": "chunk-2", "page": 4, "score": 1, "matched_text": "final report"},
    document_context={"section_heading": "Guide", "page": 4, "preceding_text": "before", "matched_text": "The final report records a pilot study.", "following_text": "after", "page_text": None, "relevant_tables": [], "relevant_captions": [], "ordered_chunks": [{"chunk_id": "chunk-1", "page": 4, "text": "before"}, {"chunk_id": "chunk-2", "page": 4, "text": "The final report records a pilot study."}]},
    source_status={"catalogue_object_type": "Report", "temporal_status": "contemporary DDR-era record", "basis": "persisted catalogue metadata"},
)


class FakeInference:
    def __init__(self):
        self.calls = 0
        self.max_tokens = []
        self.temperatures = []
        self.prompts = []
        self.response_schemas = []
        self.source_analysis_max_output_tokens = 1000
        self.cross_source_max_output_tokens = 1000
        self.final_synthesis_max_output_tokens = 768
        self.temperature = 0.2
    async def generate_experiment(self, prompt, **_kwargs):
        self.calls += 1
        self.max_tokens.append(_kwargs["max_tokens"])
        self.temperatures.append(_kwargs["temperature"])
        self.prompts.append(prompt)
        self.response_schemas.append(_kwargs["response_schema"])
        payloads = [
            {"source_id": "doc-1:chunk-2", "subject_named": True, "relationship_to_question": "DIRECT_SUPPORT", "direct_claims": [{"source_id": "doc-1:chunk-2", "claim": "A pilot study is recorded.", "evidence": [{"chunk_id": "chunk-2", "page": 4, "quotation_or_paraphrase": "The final report records a pilot study."}]}], "contextual_claims": [], "possible_inferences": [], "not_established": ["The report does not establish outcomes."]},
            {"supported_by_multiple_sources": [], "supported_by_one_source": ["pilot study"], "differences_or_contradictions": [], "cross_source_inferences": [], "cross_source_inference_sources": {}, "not_established": []},
            {"direct_documentary_claims": [{"source_id": "doc-1:chunk-2", "claim": "A pilot study is recorded.", "evidence": [{"chunk_id": "chunk-2", "page": 4, "quotation_or_paraphrase": "The final report records a pilot study."}]}], "cross_source_inferences": [], "authority_context": [], "missing_or_not_established": [], "answer": "The report directly records a pilot study."},
        ]
        return {"raw_response": json.dumps(payloads[self.calls - 1]), "generation": {"done": True}}


class EvidencePipelineTests(unittest.TestCase):
    def test_evidence_ledger_preserves_all_source_classes(self):
        testimony_packet = PACKET.model_copy(deep=True)
        testimony_packet.document["title"] = "Interview with a design researcher"
        testimony_packet.source_status = {
            "catalogue_object_type": "File",
            "temporal_status": "later record",
            "basis": "persisted catalogue metadata",
        }
        evidence_map = {
            "EVIDENCE_CARDS": [{
                "evidence_card_id": "ev:1234567890abcdef",
                "source_id": testimony_packet.source_id,
                "chunk_id": "chunk-2",
                "verbatim_passage": "The final report records a pilot study.",
            }],
            "ARCHIVAL_METADATA": [{
                "source_id": "archive-1", "relation_type": "PERSON_ASSOCIATED_WITH_SOURCE",
                "relation_derivation": "keyword_metadata",
            }],
        }
        authorities = [{"authority_id": "job-181", "fields": {"project_lead": "A. Researcher"}}]

        ledger = compile_evidence_ledger([testimony_packet], evidence_map, authorities)

        self.assertEqual(packet_evidence_type(testimony_packet), "RETROSPECTIVE_TESTIMONY")
        self.assertEqual([item["evidence_type"] for item in ledger], [
            "RETROSPECTIVE_TESTIMONY", "ARCHIVAL_METADATA", "DATABASE_AUTHORITY",
        ])
        self.assertEqual(ledger[0]["contemporary_or_retrospective"], "retrospective")
        self.assertEqual(ledger[1]["relation_derivation_if_any"], "keyword_metadata")
        self.assertEqual(ledger[2]["exact_span_or_structured_value"]["project_lead"], "A. Researcher")

    def test_overlong_source_proposition_is_bounded_without_changing_evidence(self):
        evidence = EvidenceReference(
            chunk_id="chunk-2", page=4,
            quotation_or_paraphrase="The final report records a pilot study in the original passage.",
        )
        claim = SourceClaim(
            source_id=PACKET.source_id,
            claim=("The report records a pilot study " * 12).strip(),
            evidence=[evidence],
        )

        self.assertLessEqual(len(claim.claim), 280)
        self.assertEqual(claim.evidence[0].quotation_or_paraphrase, evidence.quotation_or_paraphrase)

    def test_source_proposition_sentence_ending_at_character_281_is_bounded(self):
        evidence = EvidenceReference(
            chunk_id="chunk-2", page=4,
            quotation_or_paraphrase="The retained passage preserves the full source evidence.",
        )
        overlong_sentence = ("alpha " * 46) + "beta. Additional source content."

        self.assertEqual(len(("alpha " * 46) + "beta."), 281)
        claim = SourceClaim(
            source_id=PACKET.source_id,
            claim=overlong_sentence,
            evidence=[evidence],
        )

        self.assertLessEqual(len(claim.claim), 280)
        self.assertTrue(claim.claim.endswith("alpha"))
        self.assertEqual(claim.evidence[0].quotation_or_paraphrase, evidence.quotation_or_paraphrase)

    def test_document_content_analysis_bounds_long_retained_chunk(self):
        long_text = "long retained passage " * 60
        packet = PACKET.model_copy(deep=True)
        packet.document_context["ordered_chunks"][1]["text"] = long_text
        analyses = document_content_source_analyses([packet])

        claim = analyses[0].direct_claims[0]
        self.assertLessEqual(len(claim.claim), 280)
        self.assertLessEqual(len(claim.evidence[0].quotation_or_paraphrase), 300)
        self.assertIn(claim.evidence[0].quotation_or_paraphrase, long_text)

    def test_compact_cross_source_input_excludes_passage_and_provenance(self):
        compact = compact_cross_source_input({
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "evidence_card_id": "ev:source-1",
                "claim": "Validated proposition.", "verbatim_passage": "Do not send this.",
                "provenance": {"chunk_id": "chunk-1"},
            }],
            "CONTEXTUAL": [{"source_id": "source-2", "claim": "Context only."}],
            "NOT_ESTABLISHED": ["A limit."],
        })

        self.assertEqual(compact["direct_documentary"][0], {
            "source_id": "source-1", "evidence_card_id": "ev:source-1", "claim": "Validated proposition.",
        })
        self.assertNotIn("verbatim_passage", json.dumps(compact))
        self.assertNotIn("provenance", json.dumps(compact))

    def test_compact_final_claim_plan_rejects_invalid_references(self):
        snapshot = {
            "evidence_map": {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": "source-1", "claim": "Context"}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": ["Limit"]},
            "cross_source_analysis": {"cross_source_inferences": ["Inference"], "cross_source_inference_sources": {"Inference": ["source-1"]}},
            "authority": {"authority_context_passed_to_final": []},
        }
        plan = CompactFinalClaimPlan.model_validate({"claims": [{"claim_id": "c1", "claim_type": "CROSS_SOURCE_INFERENCE", "text": "Bounded inference.", "supporting_source_ids": ["source-1"], "supporting_cross_source_inference_ids": ["cross-source-inference-1"], "limit_ids": ["limit-1"]}], "overall_limit_ids": ["limit-1"]})
        self.assertTrue(validate_compact_claim_plan(plan, snapshot)["valid"])
        invalid = plan.model_copy(update={"overall_limit_ids": ["limit-99"]})
        self.assertFalse(validate_compact_claim_plan(invalid, snapshot)["valid"])
        self.assertEqual(compact_claim_plan_input(snapshot)["validated_limits"][0]["limit_id"], "limit-1")

    def test_claim_plan_records_answer_shape_and_claim_local_support_status(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": "source-1", "evidence_card_id": "ev:1", "claim": "The earlier report records a staged process."},
                {"source_id": "source-2", "evidence_card_id": "ev:2", "claim": "The later report uses different process vocabulary."},
            ],
            "EVIDENCE_CARDS": [
                {"evidence_card_id": "ev:1", "source_id": "source-1", "evidence_type": "DIRECT_DOCUMENTARY"},
                {"evidence_card_id": "ev:2", "source_id": "source-2", "evidence_type": "DIRECT_DOCUMENTARY"},
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(
            evidence_map, {"cross_source_inferences": []}, [],
            "How do the earlier and later process descriptions differ?",
        )
        validation = validate_compact_claim_plan(plan, {
            "evidence_map": evidence_map,
            "cross_source_analysis": {"cross_source_inferences": []},
            "authority": {"authority_context_passed_to_final": []},
        })

        self.assertEqual(plan.answer_shape, "COMPARE_CONTRAST")
        self.assertEqual(plan.claims[0].proposition, plan.claims[0].text)
        self.assertTrue(validation["valid"])
        self.assertEqual([item["status"] for item in validation["claim_results"]], ["SUPPORTED", "SUPPORTED"])
        self.assertEqual(classify_answer_shape("What does the final report establish?"), "SINGLE_REPORT_SUMMARY")

    def test_deterministic_claim_compiler_preserves_ledger_classes_and_order(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": "source-1", "claim": "Context"}, {"source_id": "source-2", "claim": "Context two"}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": ["Limit one", "Limit two"]}
        cross = {"cross_source_inferences": ["Validated inference"], "cross_source_inference_sources": {"Validated inference": ["source-1", "source-2"]}}
        plan = compile_final_claim_plan(evidence_map, cross, [])
        self.assertEqual([claim.claim_type for claim in plan.claims], ["CROSS_SOURCE_INFERENCE"])
        self.assertEqual(plan.claims[0].supporting_source_ids, ["source-1", "source-2"])
        self.assertFalse(any(claim.claim_type == "DIRECT_DOCUMENTARY" for claim in plan.claims))
        self.assertEqual(plan.overall_limit_ids, ["limit-1", "limit-2"])
        self.assertEqual(plan, compile_final_claim_plan(evidence_map, cross, []))

    def test_deterministic_claim_compiler_rejects_unmapped_cross_source_inference(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": "source-1", "claim": "Context"}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": ["Unmapped inference"], "cross_source_inference_sources": {}}, [])
        self.assertEqual(plan.claims, [])

    def test_hyb_truncation_shape_compiles_empty_plan_without_dropping_evidence_limits(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [],
            "CONTEXTUAL": [{"source_id": "source-1", "claim": "Context only."}],
            "CROSS_SOURCE_INFERENCE": [],
            "NOT_ESTABLISHED": [f"Limit {index}" for index in range(1, 9)],
        }

        plan = compile_final_claim_plan(evidence_map, {
            "cross_source_inferences": [], "cross_source_inference_sources": {},
        }, [])

        self.assertEqual(plan.claims, [])
        self.assertEqual(plan.overall_limit_ids, [f"limit-{index}" for index in range(1, 7)])
        self.assertEqual(evidence_map["NOT_ESTABLISHED"], [f"Limit {index}" for index in range(1, 9)])

    def test_degraded_cross_source_artifact_without_inferences_compiles_direct_claims(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "Validated direct claim"}],
            "CONTEXTUAL": [],
            "CROSS_SOURCE_INFERENCE": [],
            "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inference_sources": {}}, [])

        self.assertEqual([claim.claim_type for claim in plan.claims], ["DIRECT_DOCUMENTARY"])

    def test_narrative_evidence_label_guard_requires_matching_claim_type(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": "source-1", "claim": "Context"}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": ["Inference"], "cross_source_inference_sources": {"Inference": ["source-1"]}}, [])
        for text in (
            "Database records establish the conclusion.",
            "The database authority record identifies the lead without specifying an individual.",
        ):
            narrative = NarrativeSynthesis.model_validate({"synthesis_claims": [{"text": text, "claim_ids": ["c1"], "paragraph": 1}]})
            self.assertTrue(validate_narrative_evidence_labels(narrative, plan))
        neutral = narrative.model_copy(update={"synthesis_claims": [narrative.synthesis_claims[0].model_copy(update={"text": "The combined evidence suggests the conclusion."})]})
        self.assertEqual(validate_narrative_evidence_labels(neutral, plan), [])

    def test_testimony_claim_type_survives_card_to_claim_plan(self):
        testimony_packet = PACKET.model_copy(deep=True)
        testimony_packet.document["title"] = "Interview with a design researcher"
        testimony_packet.source_status["temporal_status"] = "later record"
        claim = SourceClaim(
            source_id=testimony_packet.source_id,
            claim="The interviewee recalled the teaching experiment.",
            evidence=[EvidenceReference(
                chunk_id="chunk-2", page=4,
                quotation_or_paraphrase="The final report records a pilot study.",
            )],
        )
        analysis = SourceAnalysis(
            source_id=testimony_packet.source_id, subject_named=True,
            relationship_to_question="DIRECT_SUPPORT", direct_claims=[claim],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )
        evidence_map = build_evidence_map([testimony_packet], [analysis])
        refresh_evidence_cards([testimony_packet], evidence_map)

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        self.assertEqual(plan.claims[0].claim_type, "RETROSPECTIVE_TESTIMONY")
        narrative = NarrativeSynthesis.model_validate({
            "synthesis_claims": [{
                "text": "The interviewee recalled the teaching experiment.",
                "claim_ids": [plan.claims[0].claim_id], "paragraph": 1,
            }],
        })
        self.assertEqual(validate_narrative_evidence_labels(narrative, plan), [])

    def test_oral_history_attribution_requires_testimony_claim(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "A learning process is described."}],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        narrative = NarrativeSynthesis.model_validate({
            "synthesis_claims": [{
                "text": "A 2013 oral-history account recalled a learning process.",
                "claim_ids": [plan.claims[0].claim_id], "paragraph": 1,
            }],
        })

        violations = validate_narrative_evidence_labels(narrative, plan)

        self.assertIn("testimony label without testimony claim", violations[0])

        accepted, prose_violations = filter_prose_evidence_label_violations(
            [NarrativeClaim(
                text=narrative.synthesis_claims[0].text,
                claim_ids=narrative.synthesis_claims[0].claim_ids,
                paragraph=1,
            )],
            plan,
        )
        self.assertEqual(accepted, [])
        self.assertIn("testimony label without testimony claim", prose_violations[0])

    def test_prose_cannot_invent_leadership_or_funding_from_a_named_organisation(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "claim": "Ministry of Public Building and Works.",
            }],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        prose = [NarrativeClaim(
            text="The project was led and funded by the Ministry of Public Building and Works.",
            claim_ids=[plan.claims[0].claim_id], paragraph=1,
        )]

        accepted, violations = filter_prose_evidence_label_violations(prose, plan)

        self.assertEqual(accepted, [])
        self.assertTrue(any("leadership relation absent from claim plan" in item for item in violations))
        self.assertTrue(any("funding relation absent from claim plan" in item for item in violations))

    def test_negative_collaboration_limit_survives_prose_relation_guard(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "Both names occur in DEU records."}],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        prose = [NarrativeClaim(
            text="The shared record does not prove collaboration.",
            claim_ids=[plan.claims[0].claim_id], paragraph=1,
        )]

        accepted, violations = filter_prose_evidence_label_violations(prose, plan)

        self.assertEqual(accepted, prose)
        self.assertEqual(violations, [])

    def test_rendered_claim_validation_blocks_citation_laundering(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "evidence_card_id": "ev:1",
                "claim": "The course paper records an intermediate assessment timetable.",
            }],
            "EVIDENCE_CARDS": [{
                "evidence_card_id": "ev:1", "source_id": "source-1",
                "evidence_type": "DIRECT_DOCUMENTARY",
            }],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        unsupported = NarrativeClaim(
            text="The course improved student satisfaction.",
            claim_ids=["c1"], paragraph=1,
        )

        result = validate_rendered_claim_support([unsupported], plan)[0]
        accepted, violations = filter_prose_evidence_label_violations([unsupported], plan)

        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("unsupported outcome assertion: satisfaction", result["reasons"])
        self.assertEqual(accepted, [])
        self.assertTrue(any("satisfaction" in item for item in violations))

    def test_rendered_comparison_preserves_conflicting_evidence_status(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": "source-1", "evidence_card_id": "ev:1", "claim": "The earlier report uses a linear process model."},
                {"source_id": "source-2", "evidence_card_id": "ev:2", "claim": "The later report uses an iterative process model."},
            ],
            "EVIDENCE_CARDS": [
                {"evidence_card_id": "ev:1", "source_id": "source-1", "evidence_type": "DIRECT_DOCUMENTARY"},
                {"evidence_card_id": "ev:2", "source_id": "source-2", "evidence_type": "DIRECT_DOCUMENTARY"},
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        comparison = NarrativeClaim(
            text="The formulations differ: the earlier report is linear, whereas the later report is iterative.",
            claim_ids=["c1", "c2"], paragraph=1,
        )

        result = validate_rendered_claim_support([comparison], plan)[0]

        self.assertEqual(result["status"], "CONFLICTING_EVIDENCE")
        self.assertEqual(result["supporting_evidence_ids"], ["ev:1", "ev:2"])

    def test_rendered_temporal_claim_retains_qualification(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "evidence_card_id": "ev:1",
                "claim": "The 1975 report records a linear process model.",
            }],
            "EVIDENCE_CARDS": [{
                "evidence_card_id": "ev:1", "source_id": "source-1",
                "evidence_type": "DIRECT_DOCUMENTARY",
            }],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [],
            "NOT_ESTABLISHED": ["The selected record does not establish why the process changed."],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        plan.claims[0].limit_ids = ["limit-1"]
        temporal = NarrativeClaim(
            text="The 1975 report records a linear process model, but does not establish why that model later changed.",
            claim_ids=["c1"], limit_ids=["limit-1"], paragraph=1,
        )

        result = validate_rendered_claim_support([temporal], plan)[0]

        self.assertEqual(result["status"], "SUPPORTED_WITH_QUALIFICATION")
        self.assertEqual(result["supporting_evidence_ids"], ["ev:1"])

    def test_rendered_authority_label_requires_authority_claim(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "evidence_card_id": "ev:1",
                "claim": "The report records an assessment timetable.",
            }],
            "EVIDENCE_CARDS": [{
                "evidence_card_id": "ev:1", "source_id": "source-1",
                "evidence_type": "DIRECT_DOCUMENTARY",
            }],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        mislabeled = NarrativeClaim(
            text="The database authority records an assessment timetable.",
            claim_ids=["c1"], paragraph=1,
        )

        result = validate_rendered_claim_support([mislabeled], plan)[0]

        self.assertEqual(result["status"], "INVALID_EVIDENCE_TYPE")

    def test_claim_plan_excludes_ocr_headings_and_table_fragments(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": "source-1", "evidence_card_id": "ev:1", "claim": "Job 171: ## 0."},
                {"source_id": "source-2", "evidence_card_id": "ev:2", "claim": "| Computers and Design | Computers and Design |"},
                {"source_id": "source-3", "evidence_card_id": "ev:3", "claim": "The report identifies hardware design, training, and procedure specification as interface-design activities."},
            ],
            "EVIDENCE_CARDS": [
                {"evidence_card_id": "ev:1", "source_id": "source-1", "evidence_type": "DIRECT_DOCUMENTARY"},
                {"evidence_card_id": "ev:2", "source_id": "source-2", "evidence_type": "DIRECT_DOCUMENTARY"},
                {"evidence_card_id": "ev:3", "source_id": "source-3", "evidence_type": "DIRECT_DOCUMENTARY"},
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        self.assertEqual([claim.proposition for claim in plan.claims], [
            "The report identifies hardware design, training, and procedure specification as interface-design activities.",
        ])

    def test_evidence_cards_reject_visual_claim_without_pixel_capability(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": PACKET.source_id, "chunk_ids": [PACKET.retrieval_match["chunk_id"]],
                "page": 4, "quotations": ["final report"],
                "claim": "The photograph shows a comfortable seating posture.",
            }],
            "NOT_ESTABLISHED": [],
        }

        cards, rejected = compile_evidence_cards([PACKET], evidence_map)

        self.assertEqual(cards, [])
        self.assertEqual(rejected, [{"source_id": PACKET.source_id, "reason": "visual_analysis_not_available"}])

    def test_collaboration_requires_explicit_documentary_relationship(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{
                "source_id": "source-1", "claim": "Two people held overlapping appointments.",
                "evidence_card_id": "ev:1234567890abcdef",
            }],
            "EVIDENCE_CARDS": [{
                "evidence_card_id": "ev:1234567890abcdef", "source_id": "source-1",
                "evidence_type": "DIRECT_DOCUMENTARY",
                "normalized_proposition": "Two people held overlapping appointments.",
            }],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = CompactFinalClaimPlan.model_validate({
            "claims": [{
                "claim_id": "c1", "claim_type": "QUALIFIED_SYNTHESIS",
                "text": "The two people collaborated.",
                "supporting_source_ids": ["source-1"],
                "supporting_evidence_card_ids": ["ev:1234567890abcdef"],
            }],
        })
        snapshot = {
            "evidence_map": evidence_map,
            "cross_source_analysis": {"cross_source_inferences": []},
            "authority": {"authority_context_passed_to_final": []},
        }

        validation = validate_compact_claim_plan(plan, snapshot)

        self.assertFalse(validation["valid"])
        self.assertIn("collaborat is not explicit", validation["invalid"]["claim_types"][0])

    def test_documentary_claim_cannot_use_database_authority_alone(self):
        plan = CompactFinalClaimPlan.model_validate({
            "claims": [{
                "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
                "text": "The document states a project role.",
                "supporting_authority_ids": ["181"],
            }],
        })
        snapshot = {
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "EVIDENCE_CARDS": [], "CONTEXTUAL": [],
                "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
            },
            "cross_source_analysis": {"cross_source_inferences": []},
            "authority": {"authority_context_passed_to_final": [{"authority_id": "181"}]},
        }

        validation = validate_compact_claim_plan(plan, snapshot)

        self.assertFalse(validation["valid"])
        self.assertTrue(any(
            "direct claim lacks documentary support" in item
            for item in validation["invalid"]["claim_types"]
        ))

    def test_metadata_association_cannot_support_authorship_claim(self):
        plan = CompactFinalClaimPlan.model_validate({
            "claims": [{
                "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
                "text": "The associated person authored the report.",
                "supporting_source_ids": ["metadata-source"],
            }],
        })
        snapshot = {
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [], "EVIDENCE_CARDS": [], "CONTEXTUAL": [],
                "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
                "ARCHIVAL_METADATA": [{
                    "source_id": "metadata-source",
                    "relation_type": "PERSON_ASSOCIATED_WITH_SOURCE",
                    "relation_derivation": "keyword_metadata",
                }],
            },
            "cross_source_analysis": {"cross_source_inferences": []},
            "authority": {"authority_context_passed_to_final": []},
        }

        validation = validate_compact_claim_plan(plan, snapshot)

        self.assertFalse(validation["valid"])
        self.assertTrue(any(
            "direct claim lacks documentary support" in item
            for item in validation["invalid"]["claim_types"]
        ))

    def test_deterministic_claim_compiler_accepts_direct_and_explicit_authority_only(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "Validated direct claim"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        cross = {"cross_source_inferences": []}
        resolved_only = [{"authority_id": "ARCHERB", "fields": {"label": "Bruce Archer"}}]
        without_authority = compile_final_claim_plan(evidence_map, cross, [])
        with_authority = compile_final_claim_plan(evidence_map, cross, resolved_only)
        self.assertEqual([claim.claim_type for claim in without_authority.claims], ["DIRECT_DOCUMENTARY"])
        self.assertEqual([claim.claim_type for claim in with_authority.claims], ["DIRECT_DOCUMENTARY", "DATABASE_AUTHORITY"])

    def test_evidence_cards_bind_passage_hash_and_claim_plan_reference(self):
        packet = PACKET.model_copy(deep=True)
        packet.document.update({
            "required_facets": [
                {"facet_type": "activity", "value": "modelling"},
                {"facet_type": "person", "value": "Asha Bell"},
            ],
            "supported_facets": [
                {"facet_type": "activity", "value": "modelling"},
            ],
        })
        claim = SourceClaim(
            source_id=packet.source_id,
            claim="The report records a pilot study using modelling.",
            evidence=[EvidenceReference(
                chunk_id="chunk-2", page=4,
                quotation_or_paraphrase="The final report records a pilot study.",
            )],
        )
        analysis = SourceAnalysis(
            source_id=packet.source_id, subject_named=True,
            relationship_to_question="DIRECT_SUPPORT", direct_claims=[claim],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[],
            not_established=["The report does not establish outcomes."],
        )
        evidence_map = build_evidence_map([packet], [analysis])
        refresh_evidence_cards([packet], evidence_map)
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        card = evidence_map["EVIDENCE_CARDS"][0]
        self.assertEqual(card["verbatim_passage"], "The final report records a pilot study.")
        self.assertEqual(card["chunk_id"], "chunk-2")
        self.assertEqual(len(card["source_text_hash"]), 64)
        self.assertEqual(card["supported_facets"], [{"facet_type": "activity", "value": "modelling"}])
        self.assertEqual(plan.required_facets, [
            {"facet_type": "activity", "value": "modelling"},
            {"facet_type": "person", "value": "Asha Bell"},
        ])
        self.assertEqual(plan.facets_missing, [{"facet_type": "person", "value": "Asha Bell"}])
        self.assertEqual(plan.claims[0].supporting_evidence_card_ids, [card["evidence_card_id"]])

    def test_multi_source_temporal_facet_preserves_attributable_contributions(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": "early", "claim": "The earlier paper defines design research as systematic enquiry.", "evidence_card_id": "ev:early"},
                {"source_id": "late", "claim": "The later paper describes design research as an academic discipline.", "evidence_card_id": "ev:late"},
            ],
            "EVIDENCE_CARDS": [
                {"evidence_card_id": "ev:early", "source_id": "early", "evidence_type": "DIRECT_DOCUMENTARY", "normalized_proposition": "The earlier paper defines design research as systematic enquiry.", "required_facets": [{"facet_type": "temporal", "value": "multiple_periods"}], "facet_contributions": [{"facet_type": "temporal", "value": "multiple_periods", "component": "1960s"}]},
                {"evidence_card_id": "ev:late", "source_id": "late", "evidence_type": "DIRECT_DOCUMENTARY", "normalized_proposition": "The later paper describes design research as an academic discipline.", "required_facets": [{"facet_type": "temporal", "value": "multiple_periods"}], "facet_contributions": [{"facet_type": "temporal", "value": "multiple_periods", "component": "1980s"}]},
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        self.assertEqual(plan.facets_missing, [])
        self.assertEqual(plan.facets_found, [{"facet_type": "temporal", "value": "multiple_periods"}])
        self.assertEqual(plan.facet_contributions, [{
            "facet": {"facet_type": "temporal", "value": "multiple_periods"},
            "contributions": [
                {"component": "1960s", "evidence_card_id": "ev:early", "source_id": "early", "proposition": "The earlier paper defines design research as systematic enquiry."},
                {"component": "1980s", "evidence_card_id": "ev:late", "source_id": "late", "proposition": "The later paper describes design research as an academic discipline."},
            ],
        }])
        self.assertEqual([claim.supporting_source_ids for claim in plan.claims], [["early"], ["late"]])

    def test_single_temporal_contribution_remains_a_bounded_gap(self):
        evidence_map = {
            "DIRECT_DOCUMENTARY": [{"source_id": "early", "claim": "The earlier paper defines design research.", "evidence_card_id": "ev:early"}],
            "EVIDENCE_CARDS": [{"evidence_card_id": "ev:early", "source_id": "early", "evidence_type": "DIRECT_DOCUMENTARY", "normalized_proposition": "The earlier paper defines design research.", "required_facets": [{"facet_type": "temporal", "value": "multiple_periods"}], "facet_contributions": [{"facet_type": "temporal", "value": "multiple_periods", "component": "1960s"}]}],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        self.assertEqual(plan.facets_missing, [{"facet_type": "temporal", "value": "multiple_periods"}])
        self.assertIn("multiple_periods temporal", plan.open_uncertainties[0])

    def test_claim_plan_uses_only_admissible_direct_evidence(self):
        def card(card_id, source_id, decision, typed="ADMISSIBLE", scoped="ADMISSIBLE"):
            return {
                "evidence_card_id": card_id,
                "source_id": source_id,
                "evidence_type": "DIRECT_DOCUMENTARY",
                "normalized_proposition": f"{source_id} proposition.",
                "claim_admissibility": {
                    "typed_provenance": typed,
                    "question_scoped": scoped,
                    "decision": decision,
                },
            }

        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": "authority-context", "evidence_card_id": "ev:authority", "claim": "Authority role context."},
                {"source_id": "period-a", "evidence_card_id": "ev:period-a", "claim": "Earlier period context."},
                {"source_id": "association", "evidence_card_id": "ev:association", "claim": "Association context."},
                {"source_id": "non-dispositive", "evidence_card_id": "ev:nondispositive", "claim": "Theme context."},
                {"source_id": "direct", "evidence_card_id": "ev:direct", "claim": "The report directly records the requested activity."},
            ],
            "EVIDENCE_CARDS": [
                card("ev:authority", "authority-context", "CONTEXTUAL_ONLY", typed="CONTEXT_ONLY"),
                card("ev:period-a", "period-a", "CONTEXTUAL_ONLY", scoped="INCOMPATIBLE_TEMPORAL_SCOPE"),
                card("ev:association", "association", "CONTEXTUAL_ONLY", scoped="RELATION_NOT_ACTIVITY"),
                card("ev:nondispositive", "non-dispositive", "INSUFFICIENT", scoped="NON_DISPOSITIVE"),
                card("ev:direct", "direct", "DIRECT_SUPPORT"),
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "Does the report establish the requested activity in Period B?")

        self.assertEqual([claim.supporting_source_ids for claim in plan.claims], [["direct"]])
        self.assertTrue(any("contextual" in limit.lower() for limit in plan.open_uncertainties))
        self.assertEqual(evidence_map["EVIDENCE_CARDS"][0]["claim_admissibility"]["decision"], "CONTEXTUAL_ONLY")
        invalid = plan.model_copy(update={"claims": [
            plan.claims[0].model_copy(update={
                "supporting_source_ids": ["authority-context"],
                "supporting_evidence_card_ids": ["ev:authority"],
            })
        ]})
        validation = validate_compact_claim_plan(invalid, {
            "evidence_map": evidence_map,
            "cross_source_analysis": {"cross_source_inferences": []},
            "authority": {"authority_context_passed_to_final": []},
        })
        self.assertFalse(validation["valid"])
        self.assertTrue(any(
            reason.startswith("inadmissible evidence card")
            for reason in validation["claim_results"][0]["reasons"]
        ))

    def test_cards_require_proposition_specific_temporal_and_relationship_support(self):
        def packet(source_id, date, required_facets, text):
            item = PACKET.model_copy(deep=True)
            item.source_id = source_id
            item.document = {
                "document_id": source_id,
                "date": date,
                "required_facets": required_facets,
                "supported_facets": required_facets,
            }
            item.retrieval_match = {"chunk_id": "chunk", "page": 1}
            item.document_context = {"ordered_chunks": [{"chunk_id": "chunk", "page": 1, "text": text}]}
            return item

        person_facet = {"facet_type": "person", "value": "Example Researcher"}
        relationship_facet = {"facet_type": "relationship", "value": "responsible"}
        contemporaneous = packet(
            "contemporary", "1975", [person_facet],
            "Example Researcher led the documented 1975 project.",
        )
        later = packet(
            "later", "1985", [person_facet],
            "Example Researcher is named in a later design-education account.",
        )
        contextual = packet(
            "contextual", "1975", [relationship_facet],
            "The unit's staff received bursaries and salaries.",
        )
        dispositive = packet(
            "dispositive", "1975", [relationship_facet],
            "The committee was responsible for the documented decision.",
        )
        evidence_map = {
            "DIRECT_DOCUMENTARY": [
                {"source_id": item.source_id, "document_id": item.document["document_id"], "chunk_ids": ["chunk"], "page": 1, "claim": item.document_context["ordered_chunks"][0]["text"], "quotations": [item.document_context["ordered_chunks"][0]["text"]]}
                for item in (contemporaneous, later, contextual, dispositive)
            ],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }

        cards, _ = compile_evidence_cards(
            [contemporaneous, later, contextual, dispositive],
            evidence_map,
            [{"authority_type": "agent_employment", "fields": {"name": "Example Researcher", "start_date": "1970-01-01", "end_date": "1980-12-31"}}],
        )
        evidence_map["EVIDENCE_CARDS"] = cards
        by_source = {card["source_id"]: card for card in cards}

        self.assertEqual(by_source["contemporary"]["claim_admissibility"]["decision"], "DIRECT_SUPPORT")
        self.assertEqual(by_source["later"]["claim_admissibility"]["decision"], "CONTEXTUAL_ONLY")
        self.assertEqual(by_source["contextual"]["claim_admissibility"]["decision"], "CONTEXTUAL_ONLY")
        self.assertEqual(by_source["dispositive"]["claim_admissibility"]["decision"], "DIRECT_SUPPORT")

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        self.assertEqual([claim.supporting_source_ids for claim in plan.claims], [["contemporary"], ["dispositive"]])
        self.assertEqual({card["source_id"] for card in cards}, {"contemporary", "later", "contextual", "dispositive"})
        self.assertTrue(any("contextual" in limit.lower() for limit in plan.open_uncertainties))

    def test_invalid_card_does_not_remove_valid_sibling_card(self):
        long_text = "x" * 260
        long_packet = PACKET.model_copy(update={
            "source_id": "doc-2:chunk-3",
            "document": {"document_id": "doc-2"},
            "retrieval_match": {"chunk_id": "chunk-3", "page": 5},
            "document_context": {"ordered_chunks": [{"chunk_id": "chunk-3", "page": 5, "text": long_text}]},
        })
        valid_claim = {"source_id": PACKET.source_id, "document_id": "doc-1", "pid": None, "page": 4, "chunk_ids": ["chunk-2"], "claim": "The report records a pilot study.", "quotations": ["The final report records a pilot study."]}
        invalid_claim = {"source_id": long_packet.source_id, "document_id": "doc-2", "pid": None, "page": 5, "chunk_ids": ["chunk-3"], "claim": long_text, "quotations": [long_text]}
        evidence_map = {"DIRECT_DOCUMENTARY": [valid_claim, invalid_claim], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}

        refresh_evidence_cards([PACKET, long_packet], evidence_map)
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        self.assertEqual(len(evidence_map["EVIDENCE_CARDS"]), 1)
        self.assertEqual(evidence_map["REJECTED_EVIDENCE_CARDS"][0]["reason"], "raw_ocr_dump_proposition")
        self.assertEqual([claim.text for claim in plan.claims], ["The report records a pilot study."])
    def test_final_synthesis_snapshot_round_trip_is_strict_and_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            from unittest.mock import patch
            with patch.dict("os.environ", {"TURIN_FINAL_SYNTHESIS_SNAPSHOT_DIR": temporary_directory}):
                written = write_pre_final_snapshot(
                    {"run_id": "hyb01-test", "uat_id": "MLT-HYB-01", "route": "explicit_person_authority_v1", "corpus": {"version": "corpus-test"}, "lineage": {"selected_source_ids": [PACKET.source_id]}, "resolved_authority_records": [{"authority_id": "ARCHERB"}], "authority_context_passed_to_final": []},
                    question="What can the corpus establish?",
                    source_analyses=[{"source_id": PACKET.source_id, "status": "success", "analysis": {"relationship_to_question": "CONTEXTUAL_ONLY"}}],
                    evidence_map={"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": PACKET.source_id}], "NOT_ESTABLISHED": ["A bounded limit."], "source_classifications": [{"source_id": PACKET.source_id}]},
                    cross_source_analysis={"supported_by_multiple_sources": [], "supported_by_one_source": [], "differences_or_contradictions": [], "cross_source_inferences": [], "not_established": []},
                    final_prompt="QUESTION: What can the corpus establish?",
                    final_schema=FinalSynthesis.model_json_schema(),
                    final_configuration={"max_tokens": 768, "num_ctx": 16384, "temperature": 0.2, "timeout_seconds": 1200},
                )
                loaded = load_final_synthesis_snapshot(Path(written["path"]))

            self.assertEqual(loaded["lineage"]["selected_source_ids"], [PACKET.source_id])
            self.assertEqual(loaded["evidence_map"]["CONTEXTUAL"][0]["source_id"], PACKET.source_id)
            self.assertEqual(loaded["input_payload_sha256"], written["input_payload_sha256"])
            del loaded["evidence_map"]
            with Path(written["path"]).open("w", encoding="utf-8") as target:
                json.dump(loaded, target)
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                load_final_synthesis_snapshot(Path(written["path"]))

    def test_pipeline_snapshot_captures_pre_final_state_and_final_outcome(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            from unittest.mock import patch
            with patch.dict("os.environ", {"TURIN_FINAL_SYNTHESIS_SNAPSHOT_DIR": temporary_directory}):
                artifact = asyncio.run(StagedEvidencePipeline(FakeInference()).run(
                    "What does it establish?", [PACKET],
                    diagnostic_snapshot={"run_id": "hyb01-pipeline-test", "uat_id": "MLT-HYB-01", "route": "test-route", "corpus": {"version": "corpus-test"}, "resolved_authority_records": [{"authority_id": "ARCHERB"}], "authority_context_passed_to_final": []},
                ))
                snapshot = load_final_synthesis_snapshot(Path(artifact["diagnostic_snapshot"]["path"]))

        self.assertEqual(snapshot["source_analyses"][0]["source_id"], PACKET.source_id)
        self.assertEqual(snapshot["authority"]["resolved_authority_records"][0]["authority_id"], "ARCHERB")
        self.assertEqual(snapshot["authority"]["authority_context_passed_to_final"], [])
        self.assertTrue(snapshot["final_synthesis"]["outcome"]["parse_success"])

    def test_single_validated_source_renders_deterministic_cited_claim(self):
        artifact = asyncio.run(StagedEvidencePipeline(FakeInference()).run(
            "What does the report establish?", [PACKET],
        ))

        self.assertEqual(len(artifact["final_synthesis"]["synthesis_claims"]), 1)
        self.assertEqual(
            artifact["final_synthesis"]["synthesis_claims"][0]["claim_ids"], ["c1"],
        )
        self.assertEqual(
            artifact["narrative_artifact"]["deterministic_fallback"],
            "SINGLE_SOURCE_VALIDATED_CLAIM",
        )

    def test_structured_response_accepts_markdown_fenced_json(self):
        parsed = parse_structured_response(
            NarrativeSynthesis,
            '```json\n{"synthesis_claims": [{"text": "A cited synthesis.", "claim_ids": ["c1"], "paragraph": 1}]}\n```',
        )
        self.assertEqual(parsed.synthesis_claims[0].claim_ids, ["c1"])

    def test_narrative_synthesis_accepts_claim_led_paragraph_citations(self):
        parsed = parse_structured_response(
            NarrativeSynthesis,
            json.dumps({"synthesis_claims": [
                {"text": "The first thematic argument is supported by the selected evidence. It develops a bounded interpretation.", "claim_ids": ["c1", "c2"], "paragraph": 1},
                {"text": "A second theme follows from a different group of records. Its scope remains explicit.", "claim_ids": ["c3", "c4"], "paragraph": 2},
                {"text": "The final paragraph states the qualified implication. It does not exceed the supplied evidence.", "claim_ids": ["c4", "c5"], "paragraph": 3},
            ]}),
        )
        self.assertEqual([claim.paragraph for claim in parsed.synthesis_claims], [1, 2, 3])

    def test_narrative_ledger_exposes_only_canonical_final_plan_claim_ids(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "A readable documentary proposition."}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])

        ledger = canonical_narrative_ledger(plan, evidence_map)

        self.assertEqual(ledger["allowed_claim_ids"], ["c1"])
        self.assertEqual(ledger["claim_plan"]["claims"][0]["claim_id"], "c1")

    def test_narrative_contract_rejects_unknown_ids_without_remapping(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "A readable documentary proposition."}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        narrative = NarrativeSynthesis.model_validate({"synthesis_claims": [{"text": "The report records a bounded proposition.", "claim_ids": ["source-1"], "paragraph": 1}]})

        contract = narrative_contract_state(narrative, plan)

        self.assertFalse(contract["valid"])
        self.assertEqual(contract["invalid_references"], {1: ["source-1"]})

    def test_narrative_contract_accepts_readable_documentary_prose_with_plan_id(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "source-1", "claim": "A pilot study is recorded."}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        narrative = NarrativeSynthesis.model_validate({"synthesis_claims": [{"text": "The report records a pilot study and bounds that conclusion to the surviving evidence.", "claim_ids": ["c1"], "paragraph": 1}]})

        contract = narrative_contract_state(narrative, plan)

        self.assertTrue(contract["valid"])
        self.assertTrue(contract["coverage_complete"])

    def test_final_limit_relevance_excludes_unrelated_closure_boundary(self):
        evidence_map = {"NOT_ESTABLISHED": [
            "The evidence does not establish a unique initiator of computing activity.",
            "The selected evidence cannot establish DDR activity after the June 1985 closure boundary.",
        ]}

        limits = relevant_final_limits(
            evidence_map,
            "Can the current digitised corpus establish who initiated computing activity within DDR?",
            ["A 1972 report records a CAD Centre sub-centre."],
        )

        self.assertEqual(limits, [("limit-1", "The evidence does not establish a unique initiator of computing activity.")])

    def test_broad_teaching_plan_prioritises_supported_semantic_moves(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "curriculum", "claim": "The curriculum joins professional practice with design research."},
            {"source_id": "method", "claim": "Scientific method, systems research, modelling and measurement are taught."},
            {"source_id": "computing", "claim": "Computing and CAD appear as documented teaching practice."},
            {"source_id": "experiential", "claim": "Simulation and learning by doing structure experiential teaching."},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "What are the key takeaways from the teaching and learning documents in the archive?")

        self.assertEqual([claim.supporting_source_ids[0] for claim in plan.claims[:4]], ["curriculum", "method", "computing", "experiential"])

    def test_answer_level_teaching_moves_preserve_claim_bindings(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "curriculum", "evidence_card_id": "ev:curriculum", "claim": "The curriculum joins professional practice with design research."},
            {"source_id": "method", "evidence_card_id": "ev:method", "claim": "Scientific method and systems research are taught."},
            {"source_id": "computing", "evidence_card_id": "ev:computing", "claim": "Computing and CAD appear in teaching."},
            {"source_id": "experiential", "evidence_card_id": "ev:experiential", "claim": "Simulation structures learning by doing."},
        ], "EVIDENCE_CARDS": [
            {"evidence_card_id": "ev:curriculum"}, {"evidence_card_id": "ev:method"},
            {"evidence_card_id": "ev:computing"}, {"evidence_card_id": "ev:experiential"},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "What are the key takeaways from the teaching and learning documents in the archive?")
        cards = [
            {"evidence_card_id": "ev:curriculum", "validation_status": "VALIDATED", "normalized_proposition": "The curriculum joins professional practice with design research."},
            {"evidence_card_id": "ev:method", "validation_status": "VALIDATED", "normalized_proposition": "Scientific method and systems research are taught."},
            {"evidence_card_id": "ev:computing", "validation_status": "VALIDATED", "normalized_proposition": "Computing and CAD appear in teaching."},
            {"evidence_card_id": "ev:experiential", "validation_status": "VALIDATED", "normalized_proposition": "Simulation structures learning by doing."},
        ]

        moves = answer_prose_moves(plan, cards, "What are the key takeaways from the teaching and learning documents in the archive?")

        self.assertEqual([move["move"] for move in moves], ["Opening synthesis", "Documentary development", "Qualification and scope"])
        self.assertEqual([move["claim_ids"] for move in moves], [["c1", "c4"], ["c2"], ["c3"]])

    def test_multi_part_question_moves_preserve_each_supported_component_and_limit(self):
        question = "What do the course records teach about design methods, management practice, and participant framing?"
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "methods", "evidence_card_id": "ev:methods", "claim": "The course taught design methods through staged problem analysis."},
            {"source_id": "management", "evidence_card_id": "ev:management", "claim": "The course addressed management practice through project coordination."},
            {"source_id": "framing", "evidence_card_id": "ev:framing", "claim": "The course framing distinguished delegates from public-sector participants."},
        ], "EVIDENCE_CARDS": [
            {"evidence_card_id": "ev:methods"}, {"evidence_card_id": "ev:management"},
            {"evidence_card_id": "ev:framing"},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [],
        "NOT_ESTABLISHED": ["The selected course records do not establish participant outcomes."],
        }
        cards = [
            {"evidence_card_id": "ev:methods", "validation_status": "VALIDATED", "normalized_proposition": "The course taught design methods through staged problem analysis."},
            {"evidence_card_id": "ev:management", "validation_status": "VALIDATED", "normalized_proposition": "The course addressed management practice through project coordination."},
            {"evidence_card_id": "ev:framing", "validation_status": "VALIDATED", "normalized_proposition": "The course framing distinguished delegates from public-sector participants."},
        ]

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        moves = answer_prose_moves(plan, cards, question)

        self.assertEqual([move["move"] for move in moves], [
            "Question component: design methods",
            "Question component: management practice",
            "Question component: participant framing",
        ])
        self.assertEqual([move["claim_ids"] for move in moves], [["c1"], ["c2"], ["c3"]])
        self.assertEqual(
            {claim_id for move in moves for claim_id in move["claim_ids"]},
            {claim.claim_id for claim in plan.claims},
        )
        self.assertTrue(moves[-1]["limit_ids"])

    def test_temporal_question_moves_order_supported_claims_without_inferring_change(self):
        question = "What changes are visible across the institutional records from 1968 to 1985?"
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "late", "evidence_card_id": "ev:late", "claim": "The 1985 report records a later institutional activity."},
            {"source_id": "early", "evidence_card_id": "ev:early", "claim": "The 1968 report records an earlier institutional activity."},
            {"source_id": "middle", "evidence_card_id": "ev:middle", "claim": "The 1976 report records a mid-period institutional activity."},
        ], "EVIDENCE_CARDS": [
            {"evidence_card_id": "ev:late", "source_date": "1985"},
            {"evidence_card_id": "ev:early", "source_date": "1968"},
            {"evidence_card_id": "ev:middle", "source_date": "1976"},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        cards = [
            {"evidence_card_id": "ev:late", "validation_status": "VALIDATED", "normalized_proposition": "The 1985 report records a later institutional activity.", "source_date": "1985"},
            {"evidence_card_id": "ev:early", "validation_status": "VALIDATED", "normalized_proposition": "The 1968 report records an earlier institutional activity.", "source_date": "1968"},
            {"evidence_card_id": "ev:middle", "validation_status": "VALIDATED", "normalized_proposition": "The 1976 report records a mid-period institutional activity.", "source_date": "1976"},
        ]

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        moves = answer_prose_moves(plan, cards, question)

        self.assertEqual([move["claim_ids"] for move in moves], [["c2"], ["c3"], ["c1"]])
        self.assertEqual([claim.temporal_position_if_relevant for claim in plan.claims], ["1985", "1968", "1976"])
        self.assertNotIn("caused", " ".join(move["move"] for move in moves).lower())

    def test_temporal_rendering_follows_plan_order_not_input_order_or_unsupported_progression(self):
        question = "What changes are visible across the institutional records from an earlier period to a later period?"
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "later", "evidence_card_id": "ev:later", "claim": "The later report records activity Y."},
            {"source_id": "earlier", "evidence_card_id": "ev:earlier", "claim": "The earlier report records activity X."},
        ], "EVIDENCE_CARDS": [
            {"evidence_card_id": "ev:later", "source_date": "later 1983"},
            {"evidence_card_id": "ev:earlier", "source_date": "earlier 1972"},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        cards = [
            {"evidence_card_id": "ev:later", "validation_status": "VALIDATED", "normalized_proposition": "The later report records activity Y."},
            {"evidence_card_id": "ev:earlier", "validation_status": "VALIDATED", "normalized_proposition": "The earlier report records activity X."},
        ]

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        moves = answer_prose_moves(plan, cards, question)
        rendered = application_owned_temporal_rendering(plan, moves)

        self.assertEqual([move["claim_ids"] for move in moves], [["c2"], ["c1"]])
        self.assertEqual([claim.claim_ids for claim in rendered], [["c2"], ["c1"]])
        self.assertEqual([claim.paragraph for claim in rendered], [1, 2])
        self.assertEqual(
            [item["supporting_source_ids"] for item in validate_rendered_claim_support(rendered, plan)],
            [["earlier"], ["later"]],
        )
        self.assertNotIn("evolved", " ".join(claim.text for claim in rendered).lower())
        self.assertNotIn("expanded", " ".join(claim.text for claim in rendered).lower())

    def test_temporal_rendering_preserves_an_explicit_supported_change_claim(self):
        question = "What changes are visible over time in the records?"
        evidence_map = {"DIRECT_DOCUMENTARY": [{
            "source_id": "change", "evidence_card_id": "ev:change",
            "claim": "The later report explicitly records that the programme expanded into a new activity.",
        }], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:change", "source_date": "later 1983"}],
        "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        cards = [{
            "evidence_card_id": "ev:change", "validation_status": "VALIDATED",
            "normalized_proposition": "The later report explicitly records that the programme expanded into a new activity.",
        }]

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        rendered = application_owned_temporal_rendering(plan, answer_prose_moves(plan, cards, question))

        self.assertIn("expanded", rendered[0].text.lower())
        self.assertEqual(rendered[0].claim_ids, ["c1"])

    def test_application_owned_temporal_rendering_leaves_non_temporal_plans_to_existing_prose(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{
            "source_id": "record", "evidence_card_id": "ev:record", "claim": "The record documents a bounded activity.",
        }], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:record"}],
        "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "What does the record document?")
        moves = answer_prose_moves(plan, [{
            "evidence_card_id": "ev:record", "validation_status": "VALIDATED",
            "normalized_proposition": "The record documents a bounded activity.",
        }], "What does the record document?")

        self.assertIsNone(application_owned_temporal_rendering(plan, moves))

    def test_question_led_moves_bind_each_claim_to_existing_provenance(self):
        moves = [{
            "move": "Question component: documented practice",
            "claim_ids": ["c1", "c2"], "limit_ids": ["limit-1"],
            "propositions": ["A first bounded proposition.", "A second bounded proposition."],
            "paragraph": 1, "is_final_move": True,
        }]

        bound, failed = bind_answer_prose_to_moves([
            NarrativeProseItem(text="The first and second bounded propositions remain distinct within the documented practice account. The available evidence does not establish the requested outcome.")
        ], moves)

        self.assertEqual(failed, [])
        self.assertEqual(bound[0].claim_ids, ["c1", "c2"])
        self.assertEqual(bound[0].limit_ids, ["limit-1"])

    def test_answer_level_binding_rejects_source_ledger_language(self):
        moves = [{"claim_ids": ["c1"], "limit_ids": [], "propositions": ["A validated proposition."], "move": "Argument", "is_final_move": True}]

        bound, failed = bind_answer_prose_to_moves([
            NarrativeProseItem(text="The background provided will cover objectives, course names, John Smith, Mary Jones, and a catalogue list.")
        ], moves)

        self.assertEqual(bound, [])
        self.assertEqual(failed, [0])
        self.assertIn("source_machinery_opening", researcher_prose_issues("The retained passage records the relevant course list."))

    def test_answer_level_binding_accepts_multi_source_synthesis_paragraph(self):
        moves = [{
            "claim_ids": ["c1", "c2"], "limit_ids": [],
            "propositions": ["A first validated proposition.", "A second validated proposition."],
            "move": "Argument", "is_final_move": True,
        }]

        bound, failed = bind_answer_prose_to_moves([
            NarrativeProseItem(text="The paired records document user requirements and testing as parts of the hospital-bedstead research programme. Together they establish the recorded design-development scope without claiming later clinical effectiveness.")
        ], moves)

        self.assertEqual(failed, [])
        self.assertEqual(bound[0].claim_ids, ["c1", "c2"])

    def test_eight_validated_sources_produce_three_argument_moves(self):
        direct_claims = [
            {"source_id": f"source-{index}", "evidence_card_id": f"ev:{index:016x}", "claim": f"Validated documentary proposition {index}."}
            for index in range(1, 9)
        ]
        evidence_map = {
            "DIRECT_DOCUMENTARY": direct_claims,
            "EVIDENCE_CARDS": [{"evidence_card_id": claim["evidence_card_id"]} for claim in direct_claims],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "What do the validated records show?")
        cards = [
            {"evidence_card_id": claim["evidence_card_id"], "validation_status": "VALIDATED", "normalized_proposition": claim["claim"]}
            for claim in direct_claims
        ]

        moves = answer_prose_moves(plan, cards, "What do the validated records show?")

        self.assertEqual(len(plan.claims), 8)
        self.assertEqual(len(moves), 3)
        self.assertEqual([move["claim_ids"] for move in moves], [
            ["c1", "c4", "c7"], ["c2", "c5", "c8"], ["c3", "c6"],
        ])

    def test_hospital_bedstead_groups_eight_sources_into_four_argument_moves(self):
        direct_claims = [
            {"source_id": f"bedstead-{index}", "evidence_card_id": f"ev:{index:016x}", "claim": f"Validated hospital-bedstead proposition {index}."}
            for index in range(1, 9)
        ]
        evidence_map = {
            "DIRECT_DOCUMENTARY": direct_claims,
            "EVIDENCE_CARDS": [{"evidence_card_id": claim["evidence_card_id"]} for claim in direct_claims],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        cards = [
            {"evidence_card_id": claim["evidence_card_id"], "validation_status": "VALIDATED", "normalized_proposition": claim["claim"]}
            for claim in direct_claims
        ]

        moves = answer_prose_moves(
            plan, cards,
            "What can the General Purpose Hospital Bedstead final report establish about user requirements and testing?",
        )

        self.assertEqual(len(moves), 3)
        self.assertEqual([move["claim_ids"] for move in moves], [
            ["c1", "c4", "c7"], ["c2", "c5", "c8"], ["c3", "c6"],
        ])
        self.assertEqual([move["paragraph"] for move in moves], [1, 2, 3])
        self.assertFalse(any(move["single_sentence"] for move in moves))

    def test_plan_fallback_completes_eight_validated_source_claims(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": f"source-{index}", "claim": f"Validated documentary proposition for source {index}."}
            for index in range(1, 9)
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        partial = [
            NarrativeClaim(
                text=f"Rendered scholarly prose for source {index} remains bounded by its validated record.",
                claim_ids=[f"c{index}"], paragraph=index,
            )
            for index in range(1, 6)
        ]

        completed = complete_prose_with_plan_fallback(partial, plan)

        self.assertEqual([claim.claim_ids for claim in completed], [[f"c{index}"] for index in range(1, 9)])
        self.assertEqual(completed[5].text, "Validated documentary proposition for source 6.")

    def test_partial_two_family_prose_completes_only_missing_planned_family(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "family-a", "claim": "Family A records a bounded documentary proposition."},
            {"source_id": "family-b", "claim": "Family B records a distinct bounded documentary proposition."},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        moves = [
            {"claim_ids": ["c1"], "limit_ids": [], "paragraph": 1},
            {"claim_ids": ["c2"], "limit_ids": [], "paragraph": 2},
        ]
        rendered = [NarrativeClaim(
            text="Family A is represented by its bounded documentary proposition.",
            claim_ids=["c1"], paragraph=1,
        )]

        completed = complete_answer_prose_with_move_fallback(rendered, moves, plan)

        self.assertEqual([claim.claim_ids for claim in completed], [["c1"], ["c2"]])
        self.assertEqual(completed[1].text, plan.claims[1].text)

    def test_partial_multi_family_prose_preserves_each_planned_family_not_unplanned_sources(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "family-a", "claim": "Family A records one bounded proposition."},
            {"source_id": "family-b", "claim": "Family B records one bounded proposition."},
            {"source_id": "family-c", "claim": "Family C records one bounded proposition."},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        moves = [
            {"claim_ids": ["c1"], "limit_ids": [], "paragraph": 1},
            {"claim_ids": ["c2"], "limit_ids": [], "paragraph": 2},
            {"claim_ids": ["c3"], "limit_ids": [], "paragraph": 3},
        ]
        rendered = [NarrativeClaim(
            text="Family A is represented by its bounded documentary proposition.",
            claim_ids=["c1"], paragraph=1,
        )]

        completed = complete_answer_prose_with_move_fallback(rendered, moves, plan)

        self.assertEqual([claim.claim_ids for claim in completed], [["c1"], ["c2"], ["c3"]])
        self.assertNotIn("unplanned-source", {source_id for claim in plan.claims for source_id in claim.supporting_source_ids})

    def test_comparison_retains_seven_direct_source_moves_and_opening_synthesis(self):
        direct_claims = [
            {"source_id": f"job-source-{index}", "evidence_card_id": f"ev:{index:016x}", "claim": f"Job {146 if index % 2 else 175}: validated comparison proposition {index}."}
            for index in range(1, 8)
        ]
        evidence_map = {
            "DIRECT_DOCUMENTARY": direct_claims,
            "EVIDENCE_CARDS": [{"evidence_card_id": claim["evidence_card_id"]} for claim in direct_claims],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [],
        }
        question = "How do Job 146 and Job 175 documents differ in control-room design and implementation?"
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        cards = [
            {"evidence_card_id": claim["evidence_card_id"], "validation_status": "VALIDATED", "normalized_proposition": claim["claim"]}
            for claim in direct_claims
        ]

        moves = answer_prose_moves(plan, cards, question)

        self.assertEqual(len(plan.claims), 8)
        self.assertEqual(moves[0]["claim_ids"], ["c8"])
        self.assertEqual([move["claim_ids"] for move in moves[1:]], [
            ["c1", "c3", "c5", "c7"], ["c2", "c4", "c6"],
        ])

    def test_prose_only_response_schema_has_no_identifier_fields(self):
        schema = NarrativeProse.model_json_schema()

        self.assertEqual(set(schema["$defs"]["NarrativeProseItem"]["properties"]), {"text"})

    def test_application_binds_original_claim_ids_after_prose_generation(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "job-146", "claim": "Job 146 records the systems analysis of the control room."}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        prose = [NarrativeProseItem(text="Job 146 records a systems analysis of the control room.")]

        bound, failed = bind_prose_to_claim_plan(prose, plan)

        self.assertEqual(failed, [])
        self.assertEqual(bound[0].claim_ids, ["c1"])
        self.assertEqual(plan.claims[0].supporting_source_ids, ["job-146"])

    def test_unreadable_prose_uses_readable_validated_plan_text_without_raw_chunk(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "bedstead", "claim": "The report records an approved specification of users' requirements."}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        bound, failed = bind_prose_to_claim_plan([NarrativeProseItem(text="## raw heading")], plan)

        self.assertEqual(failed, [0])
        self.assertEqual(bound[0].text, plan.claims[0].text)
        self.assertNotIn("##", bound[0].text)

    def test_job_146_and_175_bind_to_distinct_cited_plan_claims(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "job-146", "claim": "Job 146 records systems analysis of the Glasgow City Police Information Room."},
            {"source_id": "job-175", "claim": "Job 175 records the working conditions of Strathclyde Police controllers and assistants."},
        ], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [])
        bound, failed = bind_prose_to_claim_plan([
            NarrativeProseItem(text="Job 146 treats the control room through systems analysis."),
            NarrativeProseItem(text="Job 175 treats controller working conditions and implementation."),
        ], plan)

        self.assertEqual(failed, [])
        self.assertEqual([claim.claim_ids for claim in bound], [["c1"], ["c2"]])
        self.assertEqual([plan.claims[index].supporting_source_ids[0] for index in range(2)], ["job-146", "job-175"])

    def test_thematic_extraction_preserves_both_job_record_families(self):
        job_146 = PACKET.model_copy(update={
            "source_id": "job-146:chunk", "document": {"document_id": "job-146", "title": "Job 146 | Strathclyde police design project"},
            "retrieval_match": {"chunk_id": "chunk", "page": 1, "evidence_anchor": {"chunk_id": "chunk", "matched_terms": ["control"]}},
            "document_context": {"ordered_chunks": [{"chunk_id": "chunk", "page": 1, "text": "The control room systems analysis specified the main controller console."}]},
        })
        job_175 = job_146.model_copy(update={
            "source_id": "job-175:chunk", "document": {"document_id": "job-175", "title": "Job 175 | Strathclyde control rooms"},
            "document_context": {"ordered_chunks": [{"chunk_id": "chunk", "page": 1, "text": "The control-room report investigates controller working conditions and implementation."}]},
        })

        analyses = thematic_document_content_source_analyses(
            "How do the Job 146 and Job 175 documents differ in control-room implementation?",
            [job_146, job_175],
        )

        self.assertTrue(analyses[0].direct_claims[0].claim.startswith("Job 146:"))
        self.assertTrue(analyses[1].direct_claims[0].claim.startswith("Job 175:"))

    def test_comparison_plan_adds_dual_supported_qualified_synthesis(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "job-146", "evidence_card_id": "ev:146", "claim": "Job 146: systems analysis and controller-console design."},
            {"source_id": "job-175", "evidence_card_id": "ev:175", "claim": "Job 175: controller working conditions and short-term improvements."},
        ], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:146"}, {"evidence_card_id": "ev:175"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        question = "How do Job 146 and Job 175 documents differ in control-room design and implementation?"

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], question)
        comparison = next(claim for claim in plan.claims if claim.claim_type == "QUALIFIED_SYNTHESIS")

        self.assertEqual(comparison.supporting_source_ids, ["job-146", "job-175"])
        self.assertEqual(comparison.supporting_evidence_card_ids, ["ev:146", "ev:175"])
        self.assertTrue(comparison_move_covered(plan, question))
        self.assertNotIn("same team", comparison.text.lower())
        self.assertNotIn("caused", comparison.text.lower())

    def test_source_by_source_claims_do_not_cover_comparison_move(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [
            {"source_id": "job-146", "evidence_card_id": "ev:146", "claim": "Job 146: systems analysis."},
            {"source_id": "job-175", "evidence_card_id": "ev:175", "claim": "Job 175: short-term improvements."},
        ], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:146"}, {"evidence_card_id": "ev:175"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}
        question = "How do Job 146 and Job 175 documents differ?"
        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "What do these records show?")

        self.assertFalse(comparison_move_covered(plan, question))

    def test_comparison_plan_is_not_created_when_one_family_is_absent(self):
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "job-146", "evidence_card_id": "ev:146", "claim": "Job 146: systems analysis."}], "EVIDENCE_CARDS": [{"evidence_card_id": "ev:146"}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": []}

        plan = compile_final_claim_plan(evidence_map, {"cross_source_inferences": []}, [], "How do Job 146 and Job 175 documents differ?")

        self.assertFalse(any(claim.claim_type == "QUALIFIED_SYNTHESIS" for claim in plan.claims))

    def test_source_status_is_metadata_conservative(self):
        self.assertEqual(source_status({"document_type": "Report", "date": "1976"})["temporal_status"], "contemporary DDR-era record")
        self.assertEqual(source_status({})["catalogue_object_type"], "unknown")

    def test_claim_validation_requires_exact_chunk_page_and_text(self):
        claim = SourceClaim(source_id="doc-1:chunk-2", claim="pilot", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report records")])
        self.assertTrue(validate_claims([claim], [PACKET])["valid"])
        claim.evidence[0].page = 5
        self.assertFalse(validate_claims([claim], [PACKET])["valid"])

    def test_evidence_reference_accepts_researcher_facing_snippet_over_120_characters(self):
        snippet = "The final report records a pilot study with the participating researchers, its stated scope, and a carefully bounded account of the activities completed during the review period."
        self.assertGreater(len(snippet), 120)
        self.assertLessEqual(len(snippet), 300)
        reference = EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase=snippet)
        self.assertEqual(reference.quotation_or_paraphrase, snippet)

    def test_evidence_reference_rejects_oversized_snippet(self):
        with self.assertRaisesRegex(ValueError, "at most 300 characters"):
            EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="x" * 301)

    def test_long_evidence_snippet_preserves_canonical_provenance_and_schema_bound(self):
        text = "The final report records a pilot study with the participating researchers, its stated scope, and a carefully bounded account of the activities completed during the review period."
        packet = PACKET.model_copy(update={"document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 4, "text": text}]}})
        claim = SourceClaim(source_id=packet.source_id, claim="The report records the pilot study's stated scope.", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase=text)])
        analysis = SourceAnalysis(source_id=packet.source_id, subject_named=True, relationship_to_question="DIRECT_SUPPORT", direct_claims=[claim], people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[])
        evidence_map = build_evidence_map([packet], [analysis])
        schema = EvidenceSourceAnalysis.model_json_schema()["$defs"]["EvidenceReference"]["properties"]["quotation_or_paraphrase"]
        self.assertTrue(validate_claims([claim], [packet])["valid"])
        self.assertEqual((packet.document["document_id"], claim.source_id, claim.evidence[0].chunk_id, claim.evidence[0].page), ("doc-1", "doc-1:chunk-2", "chunk-2", 4))
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"][0]["source_id"], packet.source_id)
        self.assertEqual(schema["maxLength"], 300)
        self.assertEqual(EvidenceSourceAnalysis.model_json_schema()["properties"]["direct_claims"]["maxItems"], 1)

    def test_evidence_card_bounds_a_long_valid_verbatim_quotation(self):
        text = ("The report records a bounded documentary proposition with sufficient detail to identify " * 5).strip()
        packet = PACKET.model_copy(update={"document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 4, "text": text}]}})
        evidence_map = {"DIRECT_DOCUMENTARY": [{
            "source_id": packet.source_id, "document_id": "doc-1", "page": 4,
            "chunk_ids": ["chunk-2"], "claim": "The report records a bounded proposition.",
            "quotations": [text],
        }], "NOT_ESTABLISHED": []}

        cards, rejected = compile_evidence_cards([packet], evidence_map)

        self.assertEqual(rejected, [])
        self.assertLessEqual(len(cards[0]["verbatim_passage"]), 300)
        self.assertIn(cards[0]["verbatim_passage"], text)

    def test_staged_pipeline_persists_inspectable_stage_artifacts(self):
        inference = FakeInference()
        authority_context = [{"role": "display_only"}]
        artifact = asyncio.run(StagedEvidencePipeline(inference).run("What does it establish?", [PACKET], authority_context=authority_context))
        self.assertEqual(inference.calls, 2)
        self.assertEqual(inference.max_tokens, [1500, 1000])
        self.assertEqual(inference.temperatures, [0.2, 0.2])
        self.assertEqual(artifact["source_analyses"][0]["packet"]["source_id"], "doc-1:chunk-2")
        self.assertTrue(artifact["provenance"]["source_analyses"]["valid"])
        self.assertTrue(artifact["provenance"]["final_synthesis"]["valid"])
        self.assertEqual(artifact["evidence_map"]["source_classifications"][0]["relationship_to_question"], "DIRECT_SUPPORT")
        self.assertTrue(artifact["evidence_map"]["NOT_ESTABLISHED"])
        self.assertEqual(authority_context, [])

    def test_final_claim_compilation_does_not_invoke_model(self):
        inference = FakeInference()
        artifact = asyncio.run(StagedEvidencePipeline(inference).run("What does it establish?", [PACKET]))

        self.assertEqual(inference.calls, 2)
        self.assertEqual(artifact["execution_telemetry"]["final_claim_compilation"]["model_calls"], 0)
        self.assertEqual(artifact["stage_execution"]["final_synthesis"]["status"], "success")

    def test_malformed_cross_source_response_degrades_without_losing_direct_claim_plan(self):
        class MalformedCrossSourceInference(FakeInference):
            async def generate_experiment(self, prompt, **kwargs):
                response = await super().generate_experiment(prompt, **kwargs)
                if self.calls == 2:
                    return {"raw_response": "{", "generation": {"done_reason": "length"}}
                return response

        artifact = asyncio.run(StagedEvidencePipeline(MalformedCrossSourceInference()).run(
            "What does it establish?", [PACKET]
        ))

        self.assertEqual(artifact["stage_execution"]["cross_source_analysis"]["status"], "success")
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_attempted"])
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_success"])
        self.assertEqual(artifact["cross_source_artifact"]["original_failure"]["cross_source_stop_reason"], "length")
        self.assertTrue(artifact["cross_source_artifact"]["original_failure"]["cross_source_truncated"])
        self.assertEqual(artifact["cross_source_analysis"]["cross_source_inferences"], [])
        self.assertEqual([claim["claim_type"] for claim in artifact["final_claim_plan"]["claims"]], ["DIRECT_DOCUMENTARY"])
        self.assertEqual(artifact["execution_telemetry"]["final_claim_compilation"]["model_calls"], 0)

    def test_cross_source_value_error_degrades_without_losing_direct_claim_plan(self):
        class ValueErrorCrossSourcePipeline(StagedEvidencePipeline):
            async def _generate(self, stage, *args, **kwargs):
                if stage == "cross_source":
                    raise ValueError("truncated cross-source JSON")
                return await super()._generate(stage, *args, **kwargs)

        artifact = asyncio.run(ValueErrorCrossSourcePipeline(FakeInference()).run(
            "What does it establish?", [PACKET]
        ))

        self.assertEqual(artifact["stage_execution"]["cross_source_analysis"]["status"], "success")
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_attempted"])
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_success"])
        self.assertEqual([claim["claim_type"] for claim in artifact["final_claim_plan"]["claims"]], ["DIRECT_DOCUMENTARY"])

    def test_hyb_shaped_truncated_cross_source_replay_is_safe_without_route(self):
        packets = [PACKET.model_copy(update={"source_id": f"hyb-{index}:chunk"}) for index in range(1, 6)]

        class HybTruncationInference(FakeInference):
            async def generate_experiment(self, prompt, **kwargs):
                self.calls += 1
                if self.calls <= len(packets):
                    source_id = packets[self.calls - 1].source_id
                    payload = {
                        "source_id": source_id, "subject_named": False,
                        "relationship_to_question": "NOT_RELEVANT", "direct_claims": [],
                        "contextual_claims": [f"Context {self.calls}."],
                        "possible_inferences": [],
                        "not_established": [f"Limit {self.calls * 2 - 1}", f"Limit {self.calls * 2}"],
                    }
                    return {"raw_response": json.dumps(payload), "generation": {"done_reason": "stop"}}
                if self.calls == len(packets) + 1:
                    return {"raw_response": "{", "generation": {"done_reason": "length"}}
                return {"raw_response": json.dumps({"synthesis_claims": []}), "generation": {"done_reason": "stop"}}

        artifact = asyncio.run(StagedEvidencePipeline(HybTruncationInference()).run(
            "How do the controlled DDR labels compare with the corpus?", packets
        ))

        self.assertEqual(artifact["stage_execution"]["cross_source_analysis"]["status"], "success")
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_attempted"])
        self.assertTrue(artifact["stage_execution"]["cross_source_analysis"]["repair_success"])
        self.assertEqual(artifact["cross_source_analysis"]["cross_source_inferences"], [])
        self.assertEqual(artifact["final_claim_plan"]["claims"], [])
        self.assertEqual(len(artifact["evidence_map"]["NOT_ESTABLISHED"]), 8)

    def test_cross_source_validation_keeps_valid_inferences_when_one_has_unknown_source(self):
        second_source_id = "doc-2:chunk-3"
        cross = CrossSourceAnalysis(inferences=[
            {"text": "The records support a bounded inference.", "supporting_source_ids": [PACKET.source_id, second_source_id]},
            {"text": "An unsupported inference.", "supporting_source_ids": ["unknown:chunk"]},
        ])
        validated, rejected = validate_cross_source_inferences(cross, {
            "DIRECT_DOCUMENTARY": [{"source_id": PACKET.source_id}, {"source_id": second_source_id}],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [],
        })

        self.assertEqual(validated.cross_source_inferences, ["The records support a bounded inference."])
        self.assertEqual(rejected[0]["reason"], "unknown_supporting_source_ids")

    def test_cross_source_validation_rejects_single_source_inference(self):
        cross = CrossSourceAnalysis(inferences=[
            {"text": "A single record supports an inference.", "supporting_source_ids": [PACKET.source_id]},
        ])
        validated, rejected = validate_cross_source_inferences(cross, {
            "DIRECT_DOCUMENTARY": [{"source_id": PACKET.source_id}],
            "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [],
        })

        self.assertEqual(validated.cross_source_inferences, [])
        self.assertEqual(rejected[0]["reason"], "insufficient_distinct_supporting_source_ids")

    def test_all_invalid_cross_source_inferences_leave_valid_direct_claim_plan(self):
        class InvalidCrossSourceInference(FakeInference):
            async def generate_experiment(self, prompt, **kwargs):
                response = await super().generate_experiment(prompt, **kwargs)
                if self.calls == 2:
                    return {
                        "raw_response": json.dumps({"inferences": [
                            {"text": "An unsupported inference.", "supporting_source_ids": ["unknown:chunk"]},
                        ]}),
                        "generation": {"done_reason": "stop"},
                    }
                return response

        artifact = asyncio.run(StagedEvidencePipeline(InvalidCrossSourceInference()).run(
            "What does it establish?", [PACKET]
        ))

        self.assertEqual(artifact["cross_source_analysis"]["cross_source_inferences"], [])
        self.assertEqual(len(artifact["cross_source_artifact"]["rejected_inferences"]), 1)
        self.assertEqual([claim["claim_type"] for claim in artifact["final_claim_plan"]["claims"]], ["DIRECT_DOCUMENTARY"])

    def test_final_claim_compilation_retains_validated_upstream_artifacts(self):
        class FinalFailureInference(FakeInference):
            async def generate_experiment(self, prompt, **kwargs):
                response = await super().generate_experiment(prompt, **kwargs)
                if self.calls == 3:
                    return {"raw_response": "{", "generation": {"done_reason": "length"}}
                return response

        artifact = asyncio.run(StagedEvidencePipeline(FinalFailureInference()).run("What does it establish?", [PACKET]))

        self.assertEqual(artifact["stage_execution"]["final_synthesis"]["status"], "success")
        self.assertEqual(artifact["execution_telemetry"]["final_claim_compilation"]["model_calls"], 0)
        self.assertEqual(artifact["source_analyses"][0]["status"], "success")
        self.assertEqual(artifact["cross_source_analysis"]["supported_by_one_source"], ["pilot study"])
        self.assertTrue(artifact["provenance"]["source_analyses"]["valid"])

    def test_staged_pipeline_records_safe_execution_telemetry(self):
        artifact = asyncio.run(StagedEvidencePipeline(FakeInference()).run("What does it establish?", [PACKET]))

        self.assertEqual(artifact["stage_execution"]["source_analysis"]["status"], "success")
        self.assertEqual(artifact["stage_execution"]["cross_source_analysis"]["status"], "success")
        self.assertEqual(artifact["stage_execution"]["final_synthesis"]["status"], "success")
        self.assertEqual(artifact["stage_execution"]["narrative_synthesis"]["status"], "skipped")
        self.assertEqual(artifact["stage_execution"]["narrative_repair"]["status"], "skipped")
        self.assertNotIn("raw_response", artifact["stage_execution"]["source_analysis"])

    def test_batch_requires_five_unique_source_local_classifications(self):
        packets = [PACKET.model_copy(update={"source_id": f"doc-{index}:chunk-{index}"}) for index in range(1, 6)]
        analyses = [SourceAnalysis(source_id=packet.source_id, subject_named=False, relationship_to_question="CONTEXTUAL_ONLY", direct_claims=[], contextual_claims=["Context only"], people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=["No individual role established."]) for packet in packets]
        validate_batched_source_analyses(packets, analyses)
        self.assertEqual(len(analyses), 5)
        with self.assertRaisesRegex(ValueError, "every selected source exactly once"):
            validate_batched_source_analyses(packets, analyses[:-1])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_batched_source_analyses(packets, analyses[:-1] + [analyses[0]])

    def test_compact_source_analysis_schema_keeps_only_evidence_map_fields(self):
        properties = BatchedEvidenceSourceAnalyses.model_json_schema()["$defs"]["EvidenceSourceAnalysis"]["properties"]
        self.assertNotIn("people", properties)
        self.assertNotIn("activities", properties)
        self.assertNotIn("outputs", properties)
        self.assertNotIn("dates", properties)
        self.assertEqual(properties["direct_claims"]["maxItems"], 1)
        self.assertEqual(properties["contextual_claims"]["maxItems"], 2)
        self.assertEqual(properties["possible_inferences"]["maxItems"], 2)
        self.assertEqual(properties["not_established"]["maxItems"], 3)

    def test_compact_source_analysis_preserves_direct_support_invariant(self):
        analysis = EvidenceSourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=True,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[],
        )

        validate_batched_source_analyses([PACKET], [analysis])

        self.assertEqual(analysis.relationship_to_question, "CONTEXTUAL_ONLY")
        self.assertIn("DIRECT_SUPPORT_WITHOUT_DIRECT_CLAIM", analysis.classification_diagnostics)

    def test_claim_cannot_quote_another_source_packet(self):
        other_packet = PACKET.model_copy(update={"source_id": "doc-2:chunk-9", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-9", "page": 4, "text": "A different document."}]}})
        claim = SourceClaim(source_id=other_packet.source_id, claim="pilot", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report")])
        self.assertFalse(validate_claims([claim], [PACKET, other_packet])["valid"])

    def test_batch_packet_keeps_relevant_metadata_but_excludes_raw_record_blobs(self):
        packet = PACKET.model_copy(update={"document": {**PACKET.document, "archive_record_pid": "record-1", "attached_media_pid": "media-1", "asset_pid": "asset-1", "title": "Relevant title", "keywords": ["every", "keyword"], "description": "full record payload", "source_uri": "https://signed.example/raw"}, "retrieval_match": {**PACKET.retrieval_match, "matched_metadata": ["Bruce Archer"], "channels": ["METADATA_MATCH"]}})
        formatted = format_batched_source_packet(packet)
        self.assertIn('"matched_metadata": ["Bruce Archer"]', formatted)
        self.assertIn("The final report records a pilot study.", formatted)
        self.assertNotIn("full record payload", formatted)
        self.assertNotIn("every", formatted)
        self.assertNotIn("signed.example", formatted)
        self.assertIn("DOCUMENTARY_TEXT", build_batched_source_prompt("Neutral question", [packet]))

    def test_contextual_or_unnamed_source_cannot_contribute_direct_claims(self):
        claim = SourceClaim(source_id="doc-1:chunk-2", claim="pilot", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report")])
        contextual = SourceAnalysis(source_id="doc-1:chunk-2", subject_named=False, relationship_to_question="CONTEXTUAL_ONLY", direct_claims=[claim], people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[])
        with self.assertRaisesRegex(ValueError, "Only DIRECT_SUPPORT"):
            build_evidence_map([PACKET], [contextual])
        unnamed = SourceAnalysis(source_id="doc-1:chunk-2", subject_named=False, relationship_to_question="DIRECT_SUPPORT", direct_claims=[claim], people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[])
        with self.assertRaisesRegex(ValueError, "without the named subject"):
            build_evidence_map([PACKET], [unnamed])

    def test_direct_support_without_claim_is_downgraded_with_diagnostic(self):
        analysis = SourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=True,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )

        validate_batched_source_analyses([PACKET], [analysis])
        evidence_map = build_evidence_map([PACKET], [analysis])

        self.assertEqual(analysis.relationship_to_question, "CONTEXTUAL_ONLY")
        self.assertIn("DIRECT_SUPPORT_WITHOUT_DIRECT_CLAIM", analysis.classification_diagnostics)
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"], [])

    def test_thematic_direct_claim_with_resolvable_reference_enters_ledger(self):
        teaching_packet = PACKET.model_copy(update={
            "document_context": {
                **PACKET.document_context,
                "ordered_chunks": [{
                    "chunk_id": "chunk-2",
                    "page": 4,
                    "text": "Advanced computer-aided design systems were made available for teaching purposes.",
                }],
            },
        })
        claim = SourceClaim(
            source_id=teaching_packet.source_id,
            claim="Advanced computer-aided design systems were documented as available for teaching purposes.",
            evidence=[EvidenceReference(
                chunk_id="chunk-2",
                page=4,
                quotation_or_paraphrase="made available for teaching purposes",
            )],
        )
        analysis = SourceAnalysis(
            source_id=teaching_packet.source_id,
            subject_named=False,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[claim],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )

        validate_batched_source_analyses([teaching_packet], [analysis], allow_document_content_claims=True)
        evidence_map = build_evidence_map([teaching_packet], [analysis], allow_document_content_claims=True)

        self.assertEqual(analysis.relationship_to_question, "DIRECT_SUPPORT")
        self.assertEqual(len(evidence_map["DIRECT_DOCUMENTARY"]), 1)
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"][0]["chunk_ids"], ["chunk-2"])

    def test_thematic_documentary_ledger_only_promotes_explicit_teaching_passage(self):
        teaching_packet = PACKET.model_copy(update={
            "document_context": {
                **PACKET.document_context,
                "ordered_chunks": [{
                    "chunk_id": "chunk-2",
                    "page": 4,
                    "text": "Advanced computer-aided design systems were made available for teaching purposes.",
                }],
            },
        })
        retrospective_packet = PACKET.model_copy(update={
            "source_id": "interview:chunk-3",
            "source_status": {"temporal_status": "Later oral testimony"},
        })
        irrelevant_packet = PACKET.model_copy(update={
            "source_id": "conference:chunk-4",
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-4", "page": 4, "text": "Staff presented a paper at a design conference."}]},
            "retrieval_match": {**PACKET.retrieval_match, "chunk_id": "chunk-4"},
        })

        analyses = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?",
            [teaching_packet, retrospective_packet, irrelevant_packet],
        )
        validate_batched_source_analyses(
            [teaching_packet, retrospective_packet, irrelevant_packet], analyses,
            allow_document_content_claims=True,
        )

        self.assertEqual([analysis.relationship_to_question for analysis in analyses], ["DIRECT_SUPPORT", "CONTEXTUAL_ONLY", "NOT_RELEVANT"])
        self.assertEqual(len(analyses[0].direct_claims), 1)
        self.assertIn("THEMATIC_DOCUMENTARY_PASSAGE_LEDGER", analyses[0].classification_diagnostics)

    def test_packet_builder_preserves_retrieval_evidence_anchor_over_longer_context(self):
        anchor = {
            "document_id": "doc-1", "chunk_id": "anchor", "chunk_index": 3,
            "chunk_text": "Course curriculum introduces simulation through design exercises.",
            "source_page": 2, "source_section": "Course outline",
        }
        neighbours = [
            {"document_id": "doc-1", "chunk_id": "neighbour", "chunk_index": 2,
             "chunk_text": "Unrelated context " * 80, "source_page": 2, "source_section": "Course outline"},
            anchor,
        ]

        class Result:
            def __init__(self, rows, one=False):
                self.rows, self.one_result = rows, one
            def mappings(self):
                return self
            def all(self):
                return self.rows
            def one(self):
                return self.one_result

        class Database:
            def execute(self, statement, _params):
                if "SELECT chunk_id, chunk_index" in str(statement):
                    return Result(neighbours)
                return Result([], {"filename": "course.pdf", "source_uri": "https://example.test/course.pdf", "corpus_version": "test", "ml_policy_status": "eligible_unrestricted", "ml_page_scope": "all_pages", "authority_data": {}})

        result = {
            "document_id": "doc-1", "chunk_id": "anchor", "chunk_sequence": 3,
            "page_start": 2, "score": 1.0, "text": anchor["chunk_text"], "title": "Course outline",
            "evidence_anchor": {"document_id": "doc-1", "chunk_id": "anchor", "page": 2, "retrieval_reason": "preset_thematic_documentary_term_match", "retrieval_channel": "ARCHIVE_SCOPE_OVERVIEW_FTS", "score": 1.0, "matched_terms": ["course", "curriculum"]},
        }
        packet = EvidencePacketBuilder().build(Database(), [result], local_token_budget=20)[0]

        self.assertEqual(packet.retrieval_match["evidence_anchor"]["chunk_id"], "anchor")
        self.assertIn("anchor", [chunk["chunk_id"] for chunk in packet.document_context["ordered_chunks"]])
        self.assertEqual(packet.document_context["matched_text"], anchor["chunk_text"])

    def test_thematic_curriculum_anchor_can_be_direct_without_literal_query_terms(self):
        packet = PACKET.model_copy(update={
            "retrieval_match": {**PACKET.retrieval_match, "evidence_anchor": {"chunk_id": "chunk-2", "matched_terms": ["curriculum"]}},
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 4, "text": "The curriculum introduces simulation through design exercises."}]},
        })
        analysis = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?", [packet]
        )[0]

        self.assertEqual(analysis.relationship_to_question, "DIRECT_SUPPORT")
        self.assertEqual(analysis.direct_claims[0].evidence[0].chunk_id, "chunk-2")

    def test_thematic_lecture_can_be_direct_without_teaching_or_learning_terms(self):
        packet = PACKET.model_copy(update={
            "document_context": {**PACKET.document_context, "ordered_chunks": [{
                "chunk_id": "chunk-2", "page": 4,
                "text": "Cognitive Psychology: first lecture introduces general concepts for the autumn term.",
            }]},
        })

        analysis = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?", [packet]
        )[0]

        self.assertEqual(analysis.relationship_to_question, "DIRECT_SUPPORT")
        self.assertEqual(analysis.direct_claims[0].evidence[0].chunk_id, "chunk-2")

    def test_thematic_fragment_does_not_become_direct_documentary_evidence(self):
        packet = PACKET.model_copy(update={
            "document_context": {**PACKET.document_context, "ordered_chunks": [{
                "chunk_id": "chunk-2", "page": 4,
                "text": "n of a member of the teaching staff will form part of the course work.",
            }]},
        })

        analysis = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?", [packet]
        )[0]

        self.assertEqual(analysis.relationship_to_question, "NOT_RELEVANT")
        self.assertEqual(analysis.classification_diagnostics, ["THEMATIC_FRAGMENT_REJECTED"])

    def test_thematic_ocr_header_does_not_become_direct_documentary_evidence(self):
        packet = PACKET.model_copy(update={
            "document_context": {**PACKET.document_context, "ordered_chunks": [{
                "chunk_id": "chunk-2", "page": 4,
                "text": "ROYAL COLLEGE OF ART DEPARTMENT OF DESIGN RESEARCH <!-- image --> teaching course details.",
            }]},
        })

        analysis = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?", [packet]
        )[0]

        self.assertEqual(analysis.relationship_to_question, "NOT_RELEVANT")
        self.assertEqual(analysis.classification_diagnostics, ["THEMATIC_FRAGMENT_REJECTED"])

    def test_metadata_only_or_irrelevant_anchor_cannot_become_direct(self):
        packet = PACKET.model_copy(update={
            "retrieval_match": {**PACKET.retrieval_match, "evidence_anchor": {"chunk_id": "chunk-2", "matched_terms": []}},
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 4, "text": "The document describes a commercial contract."}]},
        })
        analysis = thematic_document_content_source_analyses(
            "What are the key takeaways from the teaching and learning documents in the archive?", [packet]
        )[0]

        self.assertEqual(analysis.relationship_to_question, "NOT_RELEVANT")
        self.assertEqual(analysis.direct_claims, [])

    def test_thematic_narrative_requires_every_direct_source_not_generic_scope_count(self):
        self.assertTrue(thematic_narrative_coverage_complete({1, 2}, {1, 2}))
        self.assertFalse(thematic_narrative_coverage_complete({1}, {1, 2}))
        self.assertFalse(thematic_narrative_coverage_complete({1, 2, 3}, {1, 2}))
        self.assertFalse(thematic_narrative_coverage_complete({1}, set()))

    def test_retrospective_and_irrelevant_thematic_sources_remain_non_direct(self):
        retrospective = SourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=False,
            relationship_to_question="INFERENCE_ONLY",
            direct_claims=[],
            people=[], activities=[], outputs=[], dates=[],
            possible_inferences=["A later recollection identifies an area of interest."],
            not_established=["The recollection does not document a teaching programme."],
        )
        irrelevant = SourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=False,
            relationship_to_question="NOT_RELEVANT",
            direct_claims=[],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )

        for analysis in (retrospective, irrelevant):
            validate_batched_source_analyses([PACKET], [analysis], allow_document_content_claims=True)
            self.assertEqual(build_evidence_map([PACKET], [analysis], allow_document_content_claims=True)["DIRECT_DOCUMENTARY"], [])

    def test_named_person_guard_still_downgrades_unnamed_direct_support(self):
        claim = SourceClaim(
            source_id=PACKET.source_id,
            claim="The report records a pilot study.",
            evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report records")],
        )
        analysis = SourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=False,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[claim],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )

        validate_batched_source_analyses([PACKET], [analysis])

        self.assertEqual(analysis.relationship_to_question, "CONTEXTUAL_ONLY")
        self.assertEqual(analysis.direct_claims, [])
        self.assertIn("DIRECT_SUPPORT_WITHOUT_NAMED_SUBJECT", analysis.classification_diagnostics)

    def test_question_content_can_validate_unnamed_documentary_support(self):
        claim = SourceClaim(
            source_id=PACKET.source_id,
            claim="The report identifies a research need in interface design.",
            evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report records")],
        )
        analysis = SourceAnalysis(
            source_id=PACKET.source_id,
            subject_named=False,
            relationship_to_question="DIRECT_SUPPORT",
            direct_claims=[claim],
            people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=[],
        )

        validate_batched_source_analyses([PACKET], [analysis], allow_document_content_claims=True)
        evidence_map = build_evidence_map([PACKET], [analysis], allow_document_content_claims=True)

        self.assertEqual(analysis.relationship_to_question, "DIRECT_SUPPORT")
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"][0]["claim"], claim.claim)

    def test_final_synthesis_cannot_promote_contextual_source_to_direct_claim(self):
        final = FinalSynthesis(direct_documentary_claims=[SourceClaim(source_id="doc-1:chunk-2", claim="pilot", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report")])], cross_source_inferences=[], authority_context=[], missing_or_not_established=[], answer="answer")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": []}
        with self.assertRaisesRegex(ValueError, "classified direct"):
            validate_final_evidence_types(final, evidence_map)

    def test_q02_guard_anchors_direct_claim_to_height_memo(self):
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=[], authority_context=[], missing_or_not_established=[], answer="Archer assessed students' work.")
        evidence_map = {"DIRECT_DOCUMENTARY": [{"source_id": "height:chunk-2", "chunk_ids": ["chunk-2"], "page": 2, "quotations": ["your own lectures and tutorials"]}], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": []}

        apply_archer_teaching_evidence_guard("How is Bruce Archer's role in teaching and learning practice with students represented?", final, evidence_map, [], CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=[], not_established=[]))

        self.assertEqual(final.direct_documentary_claims[0].source_id, "height:chunk-2")
        self.assertIn("your own lectures and tutorials", final.answer)
        self.assertNotIn("assess", final.answer.lower())
        self.assertIn("assessing students' work", final.missing_or_not_established[0].lower())

    def test_q02_guard_promotes_height_packet_to_direct_support(self):
        packet = PACKET.model_copy(update={
            "source_id": "height:chunk-2",
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 2, "text": "Your own lectures and tutorials are available."}]},
            "retrieval_match": {**PACKET.retrieval_match, "page": 2},
        })
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=[], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"}]}

        cross_source = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["Bruce Archer was involved in assessing students' work"], not_established=[])

        apply_archer_teaching_evidence_guard("How is Bruce Archer's role in teaching and learning practice with students represented?", final, evidence_map, [packet], cross_source)

        self.assertEqual(evidence_map["source_classifications"][0]["relationship_to_question"], "DIRECT_SUPPORT")
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"][0]["source_id"], packet.source_id)
        self.assertEqual(cross_source.cross_source_inferences, [])

    def test_q03_guard_retains_joint_baynes_roberts_attribution(self):
        packet = PACKET.model_copy(update={
            "source_id": "publications:chunk-2",
            "document": {**PACKET.document, "title": "Design Dimension Project proposed publications"},
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 2, "text": "Design as a medium for learning | Phil Roberts Ken Baynes"}]},
            "retrieval_match": {**PACKET.retrieval_match, "page": 2},
        })
        roberts_packet = PACKET.model_copy(update={"source_id": "roberts:chunk-3", "document": {**PACKET.document, "title": "Phil Roberts discussion notes"}})
        baynes_packet = PACKET.model_copy(update={"source_id": "baynes:chunk-4", "document": {**PACKET.document, "title": "Ken Baynes letter concerning DEU appointments"}})
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["Phil Roberts was part of the Unit"], authority_context=[], missing_or_not_established=[], answer="No direct connection.")
        cross_source = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["Phil Roberts was associated with the Unit"], not_established=[])
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"}]}

        apply_baynes_roberts_evidence_guard("What evidence connects Ken Baynes and Phil Roberts within the work of the Design Education Unit?", final, evidence_map, [packet, roberts_packet, baynes_packet], cross_source)

        self.assertIn("jointly credits", final.answer)
        self.assertIn("medium for learning", final.answer)
        self.assertIn("archival metadata", final.answer)
        self.assertIn("Phil Roberts discussion notes", final.answer)
        self.assertIn("Ken Baynes letter concerning DEU appointments", final.answer)
        self.assertIn("does not establish collaboration", final.answer)
        self.assertIn("June 1985 closure boundary", final.answer)
        self.assertEqual(cross_source.cross_source_inferences, [])
        self.assertEqual(evidence_map["source_classifications"][0]["relationship_to_question"], "DIRECT_SUPPORT")
        self.assertEqual(evidence_map["DIRECT_DOCUMENTARY"][0]["chunk_ids"], ["chunk-2"])
        self.assertEqual(evidence_map["ARCHIVAL_METADATA"][0]["fields"]["authority_classification"], "ARCHIVAL_METADATA")
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, [packet])["valid"])

    def test_q04_guard_retains_course_and_brochure_attributions(self):
        course_text = "Ergonomics Course - John Wood. 1 introductory lecture (JW). Case-Study: Ergonomics and the design of computer consoles for emergency services (JW)."
        course_packet = PACKET.model_copy(update={"source_id": "course:chunk-2", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-2", "page": 7, "text": course_text}]}})
        duplicate_course_packet = PACKET.model_copy(update={"source_id": "course-duplicate:chunk-3", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-3", "page": 10, "text": course_text}]}})
        brochure_text = "Police command and control consoles. Home Office, DDR/146, John Wood, Douglas Tomkin. 1973."
        brochure_packet = PACKET.model_copy(update={"source_id": "brochure:chunk-4", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": "chunk-4", "page": 15, "text": brochure_text}]}})
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["John Wood was involved in console design"], authority_context=[], missing_or_not_established=["The selected evidence does not directly establish the named subject's activity."], answer="No direct documentary claims establish his role.")
        cross_source = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["John Wood was involved in console design"], not_established=[])
        evidence_map = {"DIRECT_DOCUMENTARY": [], "ARCHIVAL_METADATA": [], "CONTEXTUAL": [{"source_id": course_packet.source_id}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in [course_packet, duplicate_course_packet, brochure_packet]]}

        apply_wood_console_evidence_guard("How is John Wood's role in console design and ergonomics documented across different DDR source types?", final, evidence_map, [course_packet, duplicate_course_packet, brochure_packet], cross_source)

        self.assertEqual(len(final.direct_documentary_claims), 3)
        self.assertIn("computer consoles for emergency services", final.answer)
        self.assertIn("Douglas Tomkin", final.answer)
        self.assertIn("near-duplicates", final.answer)
        self.assertIn("June 1985 closure boundary", final.answer)
        self.assertNotIn("The selected evidence does not directly establish the named subject's activity.", final.missing_or_not_established)
        self.assertEqual(evidence_map["NOT_ESTABLISHED"], [
            "The two 1975 course listings are substantively near-duplicates, not independent confirmation.",
            "The selected records do not establish Wood's precise responsibilities, the division of work with Douglas Tomkin or other course contributors, the police-console design outcome, or a complete chronology of his role.",
            "The selected evidence does not establish DDR activity after the June 1985 closure boundary.",
        ])
        self.assertEqual(final.cross_source_inferences, [])
        self.assertEqual(cross_source.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, [course_packet, duplicate_course_packet, brochure_packet])["valid"])

    def test_q08_guard_retains_distinct_systematic_design_formulations(self):
        chunks = (
            ("turin_doc_321843234637_ce936558310b_30_405_b924688d75042080", "Cognitive limits rule out any systematic and exhaustive search of all possible solutions."),
            ("turin_doc_287080879712_c776e78a6d5b_3_19_01a7790692743eff", "The design process as it appears in schools has three rather different sources."),
            ("turin_doc_230440137378_063f52d0a4b3_11_69_959be9da405368f0", "It is simultaneously a rational and an intuitive process. It becomes a creative act."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q8:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["The sources document a dispute."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id} for packet in packets], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["The sources document a dispute."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("What competing interpretations of systematic design process can be identified in the corpus?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 3)
        self.assertIn("do not establish a documented dispute", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_q05_configured_guard_retains_distinct_design_research_formulations(self):
        chunks = (
            ("turin_doc_321843234637_764a8e8c3451_2_14_1a4b8a23a165d72e", "Research is systematic enquiry aimed at knowledge."),
            ("turin_doc_321843234637_ce936558310b_34_445_52b7584f2223aa79", "Design Research is part of a design-systems framework."),
            ("turin_doc_338541406157_15ef98daa711_9_52_f9dc83a28547fa34", "Methods short courses are proposed for managers and teachers."),
            ("turin_doc_259848197772_8cb8bebecae7_33_230_11a40a2846af6fd3", "The research field is deliberately broad."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q5:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["The sources define design research consistently."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["The sources define design research consistently."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("How was design research understood within the DDR, and to what extent do the surviving documents present a consistent conception of it?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 4)
        self.assertIn("do not establish a single DDR-wide definition", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_q07_configured_guard_keeps_retrospective_testimony_distinct(self):
        chunks = (
            ("turin_doc_521129471965_947374206fd4_22_6_667f29071a7ecc30", "Three Design Education Unit Curriculum Working Parties met in 1980-81."),
            ("turin_doc_964614721622_02f33b9f00ef_50_22_07f9bd0b5d9eacdb", "The Department undertakes projects, advice, assistance and instruction."),
            ("turin_doc_287080879712_0cccf16af62f_3_11_da858c85cea904e0", "The enquiry was commissioned from the RCA by the Department of Education and Science."),
            ("turin_doc_287080879712_bd483ae029d0_1_4_e62a4f009c6e6176", "The Unit was established following the Design in General Education research study."),
            ("turin_doc_930287260339_cf797b8d4ce2_3_15_86adf7ebab5bdd4e", "I suppose the Design Research name related to the earlier DRU."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q7:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["The sources establish one history."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["The sources establish one history."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("How do contemporary DDR documents and later retrospective accounts differ in their descriptions of the Design Education Unit?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 5)
        self.assertIn("not interchangeable", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertIn("retrospective testimony", final.missing_or_not_established[0])
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_q09_guard_preserves_scoped_closure_missingness(self):
        chunks = (
            ("turin_doc_521129471965_1ff812723a53_23_9_42ab372ee0c3f729", "The Department of Design Research will close in August 1986."),
            ("turin_doc_930287260339_cf797b8d4ce2_19_104_784385847266b860", "It may be that Jocelyn picked up on that when he arrived. That's possible."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q9:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["The decision had multiple causes."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id} for packet in packets], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["The decision had multiple causes."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("Does the current digitised corpus establish why the decision to close the DDR was made?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 2)
        self.assertIn("does not establish why", final.answer)
        self.assertIn("June 1985 closure boundary", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])
        plan = compile_final_claim_plan(evidence_map, cross_source_analysis_payload(cross), [])
        narrative = configured_scoped_missingness_narrative(
            plan,
            matching_turin_question_policy("Does the current digitised corpus establish why the decision to close the DDR was made?"),
            "Does the current digitised corpus establish why the decision to close the DDR was made?",
        )
        self.assertEqual(len(narrative), 3)
        self.assertEqual(narrative[0].paragraph, 1)
        self.assertEqual(narrative[-1].claim_ids, ["c1", "c2"])
        self.assertIn("does not establish decision rationale", narrative[-1].text)

    def test_scoped_missingness_limit_is_bound_to_current_reception_claim(self):
        policy = matching_turin_question_policy(
            "What do the surviving digitised records establish about intended users' reception of design in general education?"
        )
        plan = CompactFinalClaimPlan(claims=[
            {"claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY", "text": "A course was proposed for schools.", "supporting_source_ids": ["source-1"]},
            {"claim_id": "c2", "claim_type": "DIRECT_DOCUMENTARY", "text": "The records describe intended educational provision.", "supporting_source_ids": ["source-2"]},
        ])

        narrative = configured_scoped_missingness_narrative(
            plan, policy,
            "What do the surviving digitised records establish about intended users' reception of design in general education?",
        )

        self.assertIn("reception", narrative[-1].text)
        self.assertNotIn("closure boundary", narrative[-1].text)

    def test_missingness_decision_distinguishes_inadequate_search_from_no_support(self):
        inadequate = scoped_missingness_decision(
            "Did the digitised corpus establish the reception of a course?", None,
            direct_evidence_found=False, retrieval_adequate=False,
        )
        no_support = scoped_missingness_decision(
            "Did the digitised corpus establish the reception of a course?", None,
            direct_evidence_found=False, retrieval_adequate=True,
        )

        self.assertEqual(inadequate.missingness_state, "NOT_YET_ADEQUATELY_SEARCHED")
        self.assertEqual(inadequate.coverage_status, "INADEQUATE")
        self.assertEqual(no_support.missingness_state, "NO_SUPPORT_IN_SEARCHED_DIGITISED_CORPUS")
        self.assertEqual(no_support.coverage_status, "ADEQUATE")

    def test_retrieval_adequacy_requires_explicit_satisfied_coverage(self):
        self.assertTrue(retrieval_adequacy_from_diagnostics({
            "retrieved_documentary_source_count": 2,
            "retrieval_coverage": {
                "coverage_status": "satisfied",
                "required_surfaces_missing": [],
                "distinct_source_count": 2,
            },
        }))
        self.assertFalse(retrieval_adequacy_from_diagnostics({
            "retrieved_documentary_source_count": 1,
            "retrieval_coverage": {
                "coverage_status": "partially_satisfied",
                "required_surfaces_missing": ["documentary"],
                "distinct_source_count": 1,
            },
        }))
        self.assertFalse(retrieval_adequacy_from_diagnostics(None))

    def test_configured_reservation_adequacy_requires_explicit_exclusive_diagnostics(self):
        self.assertTrue(retrieval_adequacy_from_diagnostics({
            "retrieved_documentary_source_count": 1,
            "configured_reservation_exclusive": True,
        }))
        self.assertFalse(retrieval_adequacy_from_diagnostics({
            "retrieved_documentary_source_count": 1,
        }))

    def test_missingness_decision_retains_weaker_documentary_claim(self):
        decision = scoped_missingness_decision(
            "Did employment overlap establish collaboration?", None,
            direct_evidence_found=True, retrieval_adequate=True,
        )

        self.assertEqual(decision.missingness_state, "EVIDENCE_SUPPORTS_ONLY_WEAKER_CLAIM")

    def test_missingness_decision_blocks_visual_claim_without_pixels(self):
        decision = scoped_missingness_decision(
            "What do the photographs show about ergonomic design decisions?", None,
            direct_evidence_found=True, visual_analysis_requested=True,
        )

        self.assertEqual(decision.missingness_state, "MEDIA_NOT_ML_ENABLED")
        self.assertTrue(decision.capability_constraints)

    def test_authority_question_is_not_mistaken_for_visual_analysis(self):
        decision = scoped_missingness_decision(
            "Do authority-source associations show that someone authored a document?", None,
            direct_evidence_found=True,
        )

        self.assertEqual(decision.missingness_state, "EVIDENCE_SUPPORTS_ONLY_WEAKER_CLAIM")
        self.assertEqual(decision.claim_predicate, "whether someone authored a document")

    def test_scoped_closure_guard_uses_available_trace_without_inventing_missing_trace(self):
        chunk_id = "turin_doc_521129471965_1ff812723a53_23_9_42ab372ee0c3f729"
        packet = PACKET.model_copy(update={
            "source_id": "closure:trace",
            "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": 1, "text": "The Department of Design Research will close in August 1986."}]},
            "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": 1},
        })
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=[], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id}], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"}]}
        cross = CrossSourceAnalysis(inferences=[{"text": "The closure had a cause.", "supporting_source_ids": [packet.source_id]}])

        self.assertTrue(apply_configured_synthesis_guard(
            "Does the current digitised corpus establish why the decision to close the Department of Design Research was made?",
            final, evidence_map, [packet], cross, policy=matching_turin_question_policy("Does the current digitised corpus establish why the decision to close the Department of Design Research was made?"),
        ))

        self.assertEqual(len(final.direct_documentary_claims), 1)
        self.assertEqual(cross.cross_source_inferences, [])
        self.assertIn("does not establish", final.answer)
        self.assertNotIn("Frayling", final.answer)
        plan = compile_final_claim_plan(evidence_map, cross_source_analysis_payload(cross), [])
        self.assertEqual([claim.claim_type for claim in plan.claims], ["DIRECT_DOCUMENTARY"])

    def test_q10_guard_preserves_qualified_computing_attribution(self):
        chunks = (
            ("turin_doc_521129471965_3a29d65c9d5a_11_5_9d0602acd3f2a1d3", "The Department of Design Research is at present the major user of the facilities of this sub-centre."),
            ("turin_doc_930287260339_1b675e3cee3a_2_10_e36762301f44d36c", "As far as I know, the project was almost entirely Patrick Purcell's initiative."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q10:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["Patrick Purcell initiated all DDR computing."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id} for packet in packets], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["Patrick Purcell initiated all DDR computing."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("Can the current digitised corpus establish who initiated computing activity within the DDR?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 2)
        self.assertIn("qualifies", final.answer)
        self.assertIn("not conclusive proof", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_q11_guard_preserves_user_reception_missingness(self):
        chunks = (
            ("turin_doc_287080879712_14c4a9f6818d_3_20_e3b027ea91071044", "To heighten design awareness amongst teachers and establish experienced teachers and advisers."),
            ("turin_doc_930287260339_cf797b8d4ce2_22_122_5db838a2996bb8ff", "It changed the whole of GCSE through lobbying and advising the government."),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q11:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["Teachers received the programme positively."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id} for packet in packets], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["Teachers received the programme positively."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("Can the surviving digitised records establish how Design in General Education was received by its intended users?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 2)
        self.assertIn("do not establish how", final.answer)
        self.assertIn("not evidence of teachers' or pupils' reception", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_q12_guard_keeps_authority_context_distinct_from_documentary_attributions(self):
        chunks = (
            ("turin_doc_964614721622_3584e2e064ab_51_8_85a5bfefca2c0600", "Henrietta Ryott Jane Voller"),
            ("turin_doc_259848197772_8cb8bebecae7_3_21_30736e5967bdef9d", "Henrietta Ryott contributed wonderfully by typing manuscripts."),
            ("turin_doc_287080879712_0cccf16af62f_29_324_fac4df8f0f0bb593", "Henrietta Ryott (Project Secretary)"),
        )
        packets = [PACKET.model_copy(update={"source_id": f"q12:{index}", "document_context": {**PACKET.document_context, "ordered_chunks": [{"chunk_id": chunk_id, "page": index, "text": content}]}, "retrieval_match": {**PACKET.retrieval_match, "chunk_id": chunk_id, "page": index}}) for index, (chunk_id, content) in enumerate(chunks, 1)]
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["Ryott ran the projects."], authority_context=[], missing_or_not_established=[], answer="")
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [{"source_id": packet.source_id} for packet in packets], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        cross = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["Ryott ran the projects."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("What can the current digitised corpus establish about Henrietta Ryott's role in the DDR between 1973 and 1977?", final, evidence_map, packets, cross))

        self.assertEqual(len(final.direct_documentary_claims), 3)
        self.assertIn("Database authority context", final.answer)
        self.assertIn("not a documentary quotation", final.authority_context[0])
        self.assertEqual(evidence_map["DATABASE_AUTHORITY"][0]["authority_id"], "HENRIETTAR")
        self.assertEqual(final.cross_source_inferences, [])
        validate_final_evidence_types(final, evidence_map)
        self.assertTrue(validate_claims(final.direct_documentary_claims, packets)["valid"])

    def test_stage_failure_retains_raw_response_for_persistence(self):
        class InvalidInference:
            source_analysis_max_output_tokens = 1000
            cross_source_max_output_tokens = 1000
            final_synthesis_max_output_tokens = 768
            temperature = 0.2
            async def generate_experiment(self, *_args, **_kwargs):
                return {"raw_response": "{", "generation": {"done_reason": "length"}}
        with self.assertRaises(EvidencePipelineStageError) as raised:
            asyncio.run(StagedEvidencePipeline(InvalidInference()).run("Question", [PACKET]))
        self.assertEqual(raised.exception.stage, "source_analysis")
        self.assertEqual(raised.exception.partial_artifact["stage_artifact"]["raw_response"], "{")

    def test_contextual_only_fallback_preserves_all_selected_source_ids(self):
        analyses = contextual_only_source_analyses([PACKET])
        self.assertEqual(analyses[0].source_id, PACKET.source_id)
        self.assertEqual(analyses[0].relationship_to_question, "CONTEXTUAL_ONLY")
        self.assertFalse(analyses[0].direct_claims)
        self.assertIn("did not classify", analyses[0].not_established[0])
        validate_batched_source_analyses([PACKET], analyses)


if __name__ == "__main__":
    unittest.main()