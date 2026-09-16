"""Versioned, data-driven evidence policies for Turin benchmark questions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.services.archival_benchmark_policy import QuestionEvidencePolicy, load_question_policies, validate_question_policies

TURIN_QUESTION_POLICY_VERSION = "turin-question-policy-v1"


LEGACY_TURIN_QUESTION_POLICIES: tuple[QuestionEvidencePolicy, ...] = (
    QuestionEvidencePolicy(
        policy_id="CI3",
        research_case="contested_interpretation",
        trigger_all=("contemporary ddr documents", "later retrospective accounts", "design education unit"),
        reservation_type="TEMPORAL_COMPARISON",
        chunk_ids=(
            "turin_doc_521129471965_947374206fd4_22_6_667f29071a7ecc30",
            "turin_doc_964614721622_02f33b9f00ef_50_22_07f9bd0b5d9eacdb",
            "turin_doc_287080879712_0cccf16af62f_3_11_da858c85cea904e0",
            "turin_doc_287080879712_bd483ae029d0_1_4_e62a4f009c6e6176",
            "turin_doc_930287260339_cf797b8d4ce2_3_15_86adf7ebab5bdd4e",
        ),
        prohibited_inference_classes=("retrospective_as_contemporary_fact", "post_closure_activity"),
    ),
    QuestionEvidencePolicy(
        policy_id="CI4",
        research_case="contested_interpretation",
        trigger_all=("competing interpretations", "systematic design process", "corpus"),
        reservation_type="CONCEPT_FORMULATION",
        chunk_ids=(
            "turin_doc_321843234637_ce936558310b_30_405_b924688d75042080",
            "turin_doc_287080879712_c776e78a6d5b_3_19_01a7790692743eff",
            "turin_doc_230440137378_063f52d0a4b3_11_69_959be9da405368f0",
        ),
        prohibited_inference_classes=("documented_dispute",),
    ),
    QuestionEvidencePolicy(
        policy_id="SM1",
        research_case="scoped_missingness",
        trigger_all=("current digitised corpus", "decision to close", "ddr"),
        reservation_type="SCOPED_MISSINGNESS",
        chunk_ids=(
            "turin_doc_521129471965_1ff812723a53_23_9_42ab372ee0c3f729",
            "turin_doc_930287260339_cf797b8d4ce2_19_104_784385847266b860",
        ),
        prohibited_inference_classes=("decision_rationale", "causation", "post_closure_activity"),
        expected_missingness=("decision rationale", "contemporaneous explanation"),
    ),
    QuestionEvidencePolicy(
        policy_id="SM2",
        research_case="scoped_missingness",
        trigger_all=("current digitised corpus", "initiated computing activity", "ddr"),
        reservation_type="SCOPED_MISSINGNESS",
        chunk_ids=(
            "turin_doc_521129471965_3a29d65c9d5a_11_5_9d0602acd3f2a1d3",
            "turin_doc_930287260339_1b675e3cee3a_2_10_e36762301f44d36c",
        ),
        prohibited_inference_classes=("sole_initiator", "post_closure_activity"),
        expected_missingness=("unique initiator", "decision process"),
    ),
    QuestionEvidencePolicy(
        policy_id="SM3",
        research_case="scoped_missingness",
        trigger_all=("surviving digitised records", "design in general education", "intended users"),
        reservation_type="SCOPED_MISSINGNESS",
        chunk_ids=(
            "turin_doc_287080879712_14c4a9f6818d_3_20_e3b027ea91071044",
            "turin_doc_930287260339_cf797b8d4ce2_22_122_5db838a2996bb8ff",
        ),
        prohibited_inference_classes=("user_reception", "measured_impact", "post_closure_activity"),
        expected_missingness=("teachers' or pupils' views", "representative account of intended-user reception"),
    ),
    QuestionEvidencePolicy(
        policy_id="SM4",
        research_case="scoped_missingness",
        trigger_all=("henrietta ryott", "ddr", "1973", "1977"),
        reservation_type="AUTHORITY_AND_DOCUMENTARY_ROLE",
        chunk_ids=(
            "turin_doc_964614721622_3584e2e064ab_51_8_85a5bfefca2c0600",
            "turin_doc_259848197772_8cb8bebecae7_3_21_30736e5967bdef9d",
            "turin_doc_287080879712_0cccf16af62f_29_324_fac4df8f0f0bb593",
        ),
        prohibited_inference_classes=("complete_role_history", "research_authorship", "post_closure_activity"),
        expected_missingness=("full duties", "decision-making authority"),
        authority_context={
            "authority_type": "agent_employment",
            "authority_id": "HENRIETTAR",
            "source": "database_authorities.agent_employment",
            "fields": {
                "name": "Henrietta Ryott",
                "job_title_label": "Departmental Secretary (Research & Practice)",
                "start_date": "1973-01-01",
                "end_date": "1977-12-31",
            },
        },
    ),
)


TURIN_QUESTION_POLICIES = load_question_policies(
    Path(__file__).resolve().parents[2] / "config" / "benchmark_questions" / "turin-v1.json"
)


def matching_turin_question_policy(question: str) -> QuestionEvidencePolicy | None:
    return next((policy for policy in TURIN_QUESTION_POLICIES if policy.matches(question)), None)


def validate_turin_question_policies() -> None:
    validate_question_policies(TURIN_QUESTION_POLICIES)
