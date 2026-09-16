import asyncio
import json
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_evidence_pipeline_service import (
    CrossSourceAnalysis, EvidenceReference, FinalSynthesis, SourceClaim, SourceEvidencePacket,
    EvidencePipelineStageError, StagedEvidencePipeline, SourceAnalysis, apply_archer_teaching_evidence_guard, apply_baynes_roberts_evidence_guard, apply_wood_console_evidence_guard, apply_systematic_design_interpretation_guard, apply_configured_synthesis_guard, apply_closure_missingness_guard, apply_computing_initiation_missingness_guard, apply_user_reception_missingness_guard, apply_ryott_role_guard, build_batched_source_prompt, contextual_only_source_analyses, format_batched_source_packet, build_evidence_map, validate_batched_source_analyses, validate_final_evidence_types, source_status, validate_claims,
)
from app.services.turin_evidence_pipeline_service import NarrativeSynthesis, parse_structured_response


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
        self.source_analysis_max_output_tokens = 1000
        self.cross_source_max_output_tokens = 1000
        self.final_synthesis_max_output_tokens = 768
        self.temperature = 0.2
    async def generate_experiment(self, prompt, **_kwargs):
        self.calls += 1
        self.max_tokens.append(_kwargs["max_tokens"])
        self.temperatures.append(_kwargs["temperature"])
        payloads = [
            {"sources": [{"source_id": "doc-1:chunk-2", "subject_named": True, "relationship_to_question": "DIRECT_SUPPORT", "direct_claims": [{"source_id": "doc-1:chunk-2", "claim": "A pilot study is recorded.", "evidence": [{"chunk_id": "chunk-2", "page": 4, "quotation_or_paraphrase": "The final report records a pilot study."}]}], "contextual_claims": [], "people": [], "activities": [], "outputs": ["final report"], "dates": [], "possible_inferences": [], "not_established": ["The report does not establish outcomes."]}]},
            {"supported_by_multiple_sources": [], "supported_by_one_source": ["pilot study"], "differences_or_contradictions": [], "cross_source_inferences": [], "not_established": []},
            {"direct_documentary_claims": [{"source_id": "doc-1:chunk-2", "claim": "A pilot study is recorded.", "evidence": [{"chunk_id": "chunk-2", "page": 4, "quotation_or_paraphrase": "The final report records a pilot study."}]}], "cross_source_inferences": [], "authority_context": [], "missing_or_not_established": [], "answer": "The report directly records a pilot study."},
        ]
        return {"raw_response": json.dumps(payloads[self.calls - 1]), "generation": {"done": True}}


class EvidencePipelineTests(unittest.TestCase):
    def test_structured_response_accepts_markdown_fenced_json(self):
        parsed = parse_structured_response(
            NarrativeSynthesis,
            '```json\n{"synthesis_claims": [{"text": "A cited synthesis.", "source_numbers": [1], "paragraph": 1}]}\n```',
        )
        self.assertEqual(parsed.synthesis_claims[0].source_numbers, [1])

    def test_source_status_is_metadata_conservative(self):
        self.assertEqual(source_status({"document_type": "Report", "date": "1976"})["temporal_status"], "contemporary DDR-era record")
        self.assertEqual(source_status({})["catalogue_object_type"], "unknown")

    def test_claim_validation_requires_exact_chunk_page_and_text(self):
        claim = SourceClaim(source_id="doc-1:chunk-2", claim="pilot", evidence=[EvidenceReference(chunk_id="chunk-2", page=4, quotation_or_paraphrase="final report records")])
        self.assertTrue(validate_claims([claim], [PACKET])["valid"])
        claim.evidence[0].page = 5
        self.assertFalse(validate_claims([claim], [PACKET])["valid"])

    def test_staged_pipeline_persists_inspectable_stage_artifacts(self):
        inference = FakeInference()
        authority_context = [{"role": "display_only"}]
        artifact = asyncio.run(StagedEvidencePipeline(inference).run("What does it establish?", [PACKET], authority_context=authority_context))
        self.assertEqual(inference.calls, 3)
        self.assertEqual(inference.max_tokens, [1500, 1000, 768])
        self.assertEqual(inference.temperatures, [0.2, 0.2, 0.2])
        self.assertEqual(artifact["source_analyses"][0]["packet"]["source_id"], "doc-1:chunk-2")
        self.assertTrue(artifact["provenance"]["source_analyses"]["valid"])
        self.assertTrue(artifact["provenance"]["final_synthesis"]["valid"])
        self.assertEqual(artifact["evidence_map"]["source_classifications"][0]["relationship_to_question"], "DIRECT_SUPPORT")
        self.assertTrue(artifact["evidence_map"]["NOT_ESTABLISHED"])
        self.assertEqual(authority_context, [])

    def test_batch_requires_five_unique_source_local_classifications(self):
        packets = [PACKET.model_copy(update={"source_id": f"doc-{index}:chunk-{index}"}) for index in range(1, 6)]
        analyses = [SourceAnalysis(source_id=packet.source_id, subject_named=False, relationship_to_question="CONTEXTUAL_ONLY", direct_claims=[], contextual_claims=["Context only"], people=[], activities=[], outputs=[], dates=[], possible_inferences=[], not_established=["No individual role established."]) for packet in packets]
        validate_batched_source_analyses(packets, analyses)
        self.assertEqual(len(analyses), 5)
        with self.assertRaisesRegex(ValueError, "every selected source exactly once"):
            validate_batched_source_analyses(packets, analyses[:-1])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_batched_source_analyses(packets, analyses[:-1] + [analyses[0]])

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