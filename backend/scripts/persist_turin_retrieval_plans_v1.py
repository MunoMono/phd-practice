"""Persist approved Turin Retrieval Protocol v1.0 plans without creating runs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent if (BACKEND_ROOT.parent / "docs").exists() else BACKEND_ROOT
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import TurinRetrievalPlan
from app.services.retrieval_protocol import (
    AuthorityDerivedVariant,
    ResearcherSynonym,
    ResolvedAuthority,
    RetrievalFacet,
    RetrievalPlan,
    RETRIEVAL_PROTOCOL_VERSION,
)
from app.services.turin_question_register import TURIN_QUESTION_REGISTER, validate_registered_question


FINAL_PLANS = REPO_ROOT / "docs/turin_experiment/turin_retrieval_plans_v1.0_FINAL.md"
FINDINGS_MATRIX = REPO_ROOT / "docs/turin_experiment/findings_matrix.csv"
CORPUS_VERSION = "corpus_f40d78dbce52"


def authority(facet_id: str, source: str, authority_type: str, authority_id: str, field: str, value: str) -> AuthorityDerivedVariant:
    return AuthorityDerivedVariant(
        facet_id=facet_id,
        authority_source=source,
        authority_type=authority_type,
        authority_id=authority_id,
        field=field,
        value=value,
        role="controlled_query_expansion",
        rationale="Researcher-approved controlled authority variant recorded in the final Turin Retrieval Plans v1.0 document.",
        approval_state="approved",
    )


def synonym(facet_id: str, value: str) -> ResearcherSynonym:
    return ResearcherSynonym(
        facet_id=facet_id,
        value=value,
        rationale="Researcher-approved lexical alternative recorded in the final Turin Retrieval Plans v1.0 document.",
        approval_state="approved",
    )


PLAN_SPECS = [
    ("Q01", "KR1", "Known relationship case 1", "Multi-document reconstruction; whether retrieval can assemble people, activity and outputs around a known archival anchor.", [("project_person", ["171", "Pierre Goumain"]), ("computing", ["man-computer interaction", "man computer interaction", "man-computer design systems"])], [authority("project_person", "database_authorities.ddr_projects", "ddr_projects", "171", "project_number", "171"), authority("project_person", "database_authorities.ddr_projects", "ddr_projects", "171", "project_lead", "Pierre Goumain")], [synonym("computing", value) for value in ["man-computer interaction", "man computer interaction", "man-computer design systems"]], ["Job 171", "designer computer interaction", "designer-computer interaction"], "Uses the controlled project identity, documented person, and pre-run evidenced computing wording; the canonical project title remains authority context only.", ["`171` can occur as a reference number outside the project context.", "The computing facet can exclude administrative/output traces without technical wording."], None),
    ("Q02", "KR2", "Known relationship case 2", "Retrieval versus inference; whether Granite distinguishes documented activity from its own synthesis.", [("person", ["Bruce Archer"]), ("teaching_learning", ["teaching", "learning", "student", "students", "tutorial"])], [authority("person", "database_authorities.agent_employment", "agent_employment", "Bruce Archer", "person_name", "Bruce Archer")], [synonym("teaching_learning", value) for value in ["teaching", "learning", "student", "students", "tutorial"]], ["Archer", "education"], "Combines the canonical person with the researcher-approved contemporary teaching context while preserving the distinction between retrieved activity and inference.", ["The broad student/teaching alternatives can retrieve general educational material.", "Relevant Archer material may omit the contextual term in a given chunk."], None),
    ("Q03", "KR3", "Known relationship case 3", "Relationship synthesis across dispersed records; whether a connection can be reconstructed without exaggerating its significance.", [("contributors", ["Ken Baynes", "Phil Roberts"]), ("unit", ["Design Education Unit", "DEU"])], [authority("unit", "database_authorities.ref_fonds", "ref_fonds", "DEU", "label", "Design Education Unit"), authority("unit", "database_authorities.ref_fonds", "ref_fonds", "DEU", "code", "DEU")], [], [], "The person alternatives preserve dispersed evidence while the unit facet maintains archival context.", ["Neither named person has a matching person-authority record.", "The connection may be distributed across separate records."], None),
    ("Q04", "KR4", "Known relationship case 4", "Cross-source retrieval; whether different document types contribute complementary rather than duplicated evidence.", [("person", ["John Wood"]), ("console_ergonomics", ["console", "consoles", "control room", "ergonomics", "ergonomic", "human factors"])], [authority("person", "database_authorities.agent_employment", "agent_employment", "John Wood", "person_name", "John Wood")], [synonym("console_ergonomics", value) for value in ["console", "consoles", "control room", "ergonomics", "ergonomic", "human factors"]], [], "Combines the canonical person with researcher-approved technical and project wording; source-type comparison remains an evidence-review task.", ["`console` has computer-utility uses beyond the relevant projects.", "Ergonomics vocabulary also appears in curricular material."], None),
    ("Q05", "CI1", "Contested interpretation case 1", "False coherence; whether multiple formulations are preserved or collapsed into a single institutional definition.", [("institution", ["Department of Design Research", "DDR"]), ("design_research", ["design research", "research in design"])], [authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [synonym("design_research", value) for value in ["design research", "research in design"]], ["Design Research Department", "design methodology", "methodology", "research programme"], "Pairs the evidenced institutional setting with the two researcher-approved formulations without inserting curricular/methodological language.", ["`design research` is prevalent and may cover multiple senses.", "`research in design` is scarce and could under-represent alternate formulations."], None),
    ("Q06", "CI2", "Contested interpretation case 2", "Preservation of distinct voices and positions; resistance to synthesising disagreement into consensus.", [("institution", ["Department of Design Research", "DDR"]), ("design_science", ["design science", "science of design", "scientific method"])], [authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [synonym("design_science", value) for value in ["design science", "science of design", "scientific method"]], ["design method", "research"], "Uses the researcher-approved, relatively specific source formulations rather than generic research vocabulary.", ["The three formulations are relatively scarce and may privilege theoretical material.", "Contributor differences must be assessed from sources, not inferred from the facet."], None),
    ("Q07", "CI3", "Contested interpretation case 3", "Temporal and retrospective interpretation; whether later accounts are improperly allowed to stabilise contemporary ambiguity.", [("unit", ["Design Education Unit", "DEU"]), ("archive_context", ["DDR", "Department of Design Research"])], [authority("unit", "database_authorities.ref_fonds", "ref_fonds", "DEU", "label", "Design Education Unit"), authority("unit", "database_authorities.ref_fonds", "ref_fonds", "DEU", "code", "DEU"), authority("archive_context", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [], ["account", "history", "retrospective", "recollection", "memoir"], "Retrieves DEU material in its institutional context. Contemporary/retrospective classification is made after retrieval through document date, source type, provenance, and researcher assessment.", ["The archive-context facet can omit DEU records that do not name DDR.", "Post-retrieval temporal classification must be applied consistently."], None),
    ("Q08", "CI4", "Contested interpretation case 4", "Contestation detection; whether the system identifies genuinely different positions rather than generating a unified doctrine.", [("institution", ["Department of Design Research", "DDR"]), ("systematic_process", ["systematic design", "design process"])], [authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [synonym("systematic_process", value) for value in ["systematic design", "design process"]], ["systematic design process", "design method", "methodology"], "Uses the two approved source formulations without requiring a literal composite phrase that has no corpus occurrence.", ["`design process` may have broad procedural uses.", "Interpretation remains a comparison of retrieved positions, not an asserted result."], None),
    ("Q09", "SM1", "Scoped missingness case 1", "Causal restraint; whether partial evidence is wrongly converted into a definitive explanation.", [("institution", ["Department of Design Research", "DDR"]), ("institutional_decision_status", ["The Department of Design Research will close in August 1986", "Senate resolved that the departments of Design Research and Environmental Design should close", "Department of Architectural and Design Studies", "conversion of some or all of the activities of the Department of Design Research"])], [authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [], ["closure", "close", "closed", "cease", "discontinue", "termination", "winding up", "Design Research Department"], "Uses exact wording from the 1985 Rector's report (record PID `788065484899`) and `The future of the Department of Design Research` memo (record PID `873981573030`) to retrieve institutional closure status, decision-process material, and merger/reorganisation proposals across the corpus. The known records establish the legitimacy of the wording; they do not restrict candidate documents.", ["The retrieval plan is designed to surface documentary evidence about the institutional decision process and closure status. It does not presume that the retrieved corpus will establish a single or complete causal explanation for why the DDR closed.", "The memorandum records a proposed merger that was later abandoned; a proposed arrangement must not be reported as final implementation.", "The source-backed phrases are concentrated in two records, while primary retrieval remains corpus-wide."], "READY WITH CAUTION"),
    ("Q10", "SM2", "Scoped missingness case 2", "Origin claims; whether the earliest retrieved trace is mistakenly turned into evidence of historical initiation.", [("institution", ["Department of Design Research", "DDR"]), ("computing", ["man-computer interaction", "man computer interaction", "man-computer design systems"])], [authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [synonym("computing", value) for value in ["man-computer interaction", "man computer interaction", "man-computer design systems"]], ["Design Research Department"], "Retrieves documented computing traces in an evidenced institutional setting without asking FTS to prove origin or priority.", ["The vocabulary may foreground one computing strand.", "The earliest surviving trace is not evidence of initiation."], None),
    ("Q11", "SM3", "Scoped missingness case 3", "Evidence-boundary recognition; distinguishing documented intentions and activities from evidence of actual reception.", [("programme", ["Design in General Education"]), ("audience_reception", ["teachers", "pupils", "evaluation", "feedback"])], [authority("programme", "database_authorities.ddr_projects", "ddr_projects", "Design in General Education", "title", "Design in General Education")], [synonym("audience_reception", value) for value in ["teachers", "pupils", "evaluation", "feedback"]], ["DGE", "schools", "users", "students"], "Combines the named programme with researcher-approved audience/evaluation wording without using unverified abbreviations or generic user terms.", ["The context terms can document intended audiences or activities rather than reception.", "A missingness conclusion still depends on bounded evidence review."], None),
    ("Q12", "SM4", "Scoped missingness case 4", "Uneven personal visibility; whether sparse or indirect documentary evidence produces appropriately bounded conclusions.", [("person", ["Henrietta Ryott"]), ("institution", ["Department of Design Research", "DDR"])], [authority("person", "database_authorities.agent_employment", "agent_employment", "Henrietta Ryott", "person_name", "Henrietta Ryott"), authority("institution", "database_authorities.ref_fonds", "ref_fonds", "DDR", "code", "DDR")], [], ["Ryott", "Design Research Department"], "Uses the full canonical name and institutional setting while leaving documentary sparsity visible.", ["Direct name occurrence is sparse.", "Date interpretation is performed through record metadata after retrieval."], None),
]


def validate_final_document() -> None:
    plan_text = FINAL_PLANS.read_text(encoding="utf-8")
    plan_sections = re.split(r"^## Q\d{2} - ", plan_text, flags=re.MULTILINE)[1:]
    matrix_rows = list(csv.DictReader(FINDINGS_MATRIX.open(encoding="utf-8")))
    plan_questions = [re.search(r"^### Exact research question\n(.+)$", section, re.MULTILINE).group(1) for section in plan_sections]
    matrix_questions = [row["Core research question"] for row in matrix_rows]
    if len(plan_sections) != 12 or plan_questions != matrix_questions:
        raise ValueError("Final plan questions do not exactly match findings_matrix.csv.")
    if any("`corpus_wide`" not in section or "`primary`" not in section for section in plan_sections):
        raise ValueError("All final plans must be primary and corpus-wide.")
    q09 = plan_sections[8]
    if "READY WITH CAUTION" not in q09 or "It does not presume that the retrieved corpus will establish a single or complete causal explanation for why the DDR closed." not in q09:
        raise ValueError("Q09 methodological caution is missing.")


def build_plans(approval_time: datetime) -> list[RetrievalPlan]:
    plans = []
    for display_id, question_id, research_case_label, stress_test, facet_specs, variants, synonyms, rejected_terms, rationale, risks, caution in PLAN_SPECS:
        research_case, research_question = TURIN_QUESTION_REGISTER[question_id]
        validate_registered_question(question_id, research_case, research_question)
        facets = [RetrievalFacet(facet_id=facet_id, alternatives=alternatives) for facet_id, alternatives in facet_specs]
        resolved_authorities = [ResolvedAuthority(authority_source=item.authority_source, authority_type=item.authority_type, authority_id=item.authority_id, resolution_status="resolved") for item in variants]
        plan = RetrievalPlan(
            plan_id=f"{question_id}-v1",
            question_id=question_id,
            plan_version="1.0",
            researcher_approval_state="approved",
            researcher_approved_at=approval_time,
            lexical_facets=facets,
            resolved_authorities=resolved_authorities,
            authority_variants=variants,
            researcher_synonyms=synonyms,
            retrieval_scope="corpus_wide",
            run_classification="primary",
            rationale=rationale,
            notes=json.dumps({
                "display_question_id": display_id,
                "research_case": research_case_label,
                "primary_stress_test": stress_test,
                "rejected_terms": rejected_terms,
                "methodological_risks": risks,
                "final_readiness_state": "READY FOR RESEARCHER APPROVAL",
                "q09_qualification": caution,
                "intended_corpus_version": CORPUS_VERSION,
            }, ensure_ascii=True, sort_keys=True),
        )
        plan.require_formal_approval()
        plans.append(plan)
    return plans


def persist(plans: list[RetrievalPlan]) -> None:
    db = LocalSessionLocal()
    try:
        existing_count = db.execute(text("SELECT count(*) FROM turin_retrieval_plans WHERE protocol_version = :version"), {"version": RETRIEVAL_PROTOCOL_VERSION}).scalar_one()
        run_count = db.execute(text("SELECT count(*) FROM experiment_runs WHERE retrieval_protocol_version = :version"), {"version": RETRIEVAL_PROTOCOL_VERSION}).scalar_one()
        if existing_count or run_count:
            raise ValueError(f"Refusing persistence: existing_v1_plans={existing_count}, formal_v1_runs={run_count}.")
        for plan in plans:
            db.add(TurinRetrievalPlan(
                plan_id=plan.plan_id,
                question_id=plan.question_id,
                protocol_version=plan.protocol_version,
                plan_version=plan.plan_version,
                researcher_approval_state=plan.researcher_approval_state,
                researcher_approved_at=plan.researcher_approved_at,
                run_classification=plan.run_classification,
                supersedes_plan_id=plan.supersedes_plan_id,
                plan_json=plan.model_dump(mode="json"),
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-at", required=True, help="ISO-8601 researcher approval timestamp.")
    parser.add_argument("--apply", action="store_true", help="Persist after all validation passes.")
    args = parser.parse_args()
    approval_time = datetime.fromisoformat(args.approval_at.replace("Z", "+00:00"))
    validate_final_document()
    plans = build_plans(approval_time)
    if not args.apply:
        print(f"validated_plans={len(plans)} protocol={RETRIEVAL_PROTOCOL_VERSION} corpus={CORPUS_VERSION} apply=false")
        return
    persist(plans)
    print(f"persisted_plans={len(plans)} protocol={RETRIEVAL_PROTOCOL_VERSION} corpus={CORPUS_VERSION}")


if __name__ == "__main__":
    main()