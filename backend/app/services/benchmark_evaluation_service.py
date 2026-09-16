"""Collection-neutral evaluation of configured archival evidence benchmarks."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping

from app.services.archival_benchmark_policy import QuestionEvidencePolicy


def _is_asserted_inference(text: str, inference_class: str) -> bool:
    phrase = inference_class.replace("_", " ")
    for clause in re.split(r"[.;]", text.lower()):
        if phrase not in clause:
            continue
        if re.search(rf"\b(?:no|without|not)\s+{re.escape(phrase)}\b", clause):
            continue
        if re.search(r"\b(?:does not|do not|cannot|can't|not)\s+(?:directly\s+)?(?:establish|prove|show|demonstrate|support|provide)\b", clause):
            continue
        return True
    return False


def evaluate_benchmark_artifact(policy: QuestionEvidencePolicy, artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Report evidence-policy compliance without treating a benchmark as model input."""
    evidence_map = artifact.get("evidence_map") or {}
    final = artifact.get("final_synthesis") or {}
    provenance = artifact.get("provenance") or {}
    direct_claims = list(evidence_map.get("DIRECT_DOCUMENTARY") or [])
    classifications = list(evidence_map.get("source_classifications") or [])
    direct_ids = {claim.get("source_id") for claim in direct_claims}
    selected_ids = {item.get("source_id") for item in classifications}
    final_claims = list(final.get("direct_documentary_claims") or [])
    missingness = list(evidence_map.get("NOT_ESTABLISHED") or [])
    inference_text = " ".join(
        str(value)
        for value in [
            *(artifact.get("cross_source_analysis") or {}).get("cross_source_inferences", []),
            *final.get("cross_source_inferences", []),
            final.get("answer", ""),
        ]
    ).lower()
    source_documents = [claim.get("document_id") for claim in direct_claims if claim.get("document_id")]
    duplicate_documents = sorted(document_id for document_id, count in Counter(source_documents).items() if count > 1)
    prohibited_matches = [
        prohibited for prohibited in policy.prohibited_inference_classes
        if _is_asserted_inference(inference_text, prohibited)
    ]
    missingness_recovered = [
        expected for expected in policy.expected_missingness
        if any(expected.lower() in str(limit).lower() for limit in missingness)
    ]
    direct_text = " ".join(str(claim.get("claim", "")) for claim in direct_claims + final_claims)
    expected_direct_facts_recovered = [
        fact for fact in policy.expected_direct_facts
        if fact.lower() in direct_text.lower()
    ]
    retrieval_diagnostics = artifact.get("retrieval_diagnostics") or {}
    family_diagnostics = retrieval_diagnostics.get("source_family_diversity")
    selected_families = set((family_diagnostics or {}).get("selected", []))
    source_family_policy = (policy.source_selection or {}).get("required_source_families", [])
    source_family_unmet = sorted(set(source_family_policy) - selected_families) if source_family_policy and family_diagnostics is not None else []
    stage_artifacts = [artifact.get("cross_source_artifact") or {}, artifact.get("final_artifact") or {}]
    fallback_stages = [stage.get("deterministic_fallback") for stage in stage_artifacts if stage.get("deterministic_fallback")]
    malformed_stage_failures = [stage.get("parse_error") for stage in stage_artifacts if stage.get("parse_error") and not stage.get("deterministic_fallback")]
    temporal_rules = [str(boundary.get("rule", "")) for boundary in policy.temporal_boundaries]
    temporal_boundary_violations = [
        rule for rule in temporal_rules
        if rule and "cannot establish" in rule.lower() and "after" in rule.lower()
        and re.search(r"\b(?:establishes|proves|shows)\b[^.]{0,80}\b(?:198[6-9]|199\d|20\d{2})\b", inference_text)
    ]
    authority_audit = retrieval_diagnostics.get("authority_asset_coverage", {})
    source_validation = provenance.get("source_analyses") or {}
    final_validation = provenance.get("final_synthesis") or {}
    return {
        "policy_id": policy.policy_id,
        "research_case": policy.research_case,
        "policy_version": "archival-evidence-benchmark-v1",
        "retained_source_count": len(selected_ids),
        "direct_documentary_claim_count": len(direct_claims),
        "final_direct_claim_count": len(final_claims),
        "source_classification_counts": dict(Counter(item.get("relationship_to_question", "UNKNOWN") for item in classifications)),
        "source_asset_diversity": len(set(source_documents)),
        "duplicate_document_ids": duplicate_documents,
        "prohibited_inference_matches": prohibited_matches,
        "expected_missingness": {"recovered": missingness_recovered, "total": len(policy.expected_missingness)},
        "expected_direct_facts": {"recovered": expected_direct_facts_recovered, "total": len(policy.expected_direct_facts)},
        "source_family_policy": {"required": source_family_policy, "unmet": source_family_unmet},
        "temporal_boundary_violations": temporal_boundary_violations,
        "stage_fallback": {"used": fallback_stages, "malformed_without_fallback": malformed_stage_failures},
        "authority_asset_coverage": authority_audit,
        "provenance": {
            "source_analyses_valid": bool(source_validation.get("valid")),
            "final_synthesis_valid": bool(final_validation.get("valid")),
            "final_checked_references": final_validation.get("checked_references", 0),
        },
        "valid": not prohibited_matches and not temporal_boundary_violations and not source_family_unmet and not malformed_stage_failures and bool(final_validation.get("valid")) and all(
            claim.get("source_id") in direct_ids for claim in final_claims
        ),
    }


def render_evaluation_matrix(results: list[Mapping[str, Any]]) -> str:
    """Render a compact researcher-readable report alongside machine JSON output."""
    lines = [
        "# Archival Evidence Benchmark Evaluation",
        "",
        "| Policy | Result | Retained sources | Direct claims | Provenance | Unsupported inference |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for result in results:
        provenance = "PASS" if result["provenance"]["final_synthesis_valid"] else "FAIL"
        inference = ", ".join(result["prohibited_inference_matches"]) or "None"
        lines.append(
            f"| {result['policy_id']} | {'PASS' if result['valid'] else 'FAIL'} | "
            f"{result['retained_source_count']} | {result['final_direct_claim_count']} | {provenance} | {inference} |"
        )
    return "\n".join(lines) + "\n"
