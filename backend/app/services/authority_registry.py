"""Single registry for the bounded Turin database-authority surface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.services.database_authorities_sync import AUTHORITY_ALLOWED_ROLES, AUTHORITY_DEFINITIONS
from app.services.turin_experiment_service import AuthorityContext


@dataclass(frozen=True)
class AuthoritySpec:
    authority_type: str
    epistemic_type: str
    direct_lookup: bool
    temporal_fields: tuple[str, ...] = ()


AUTHORITY_SPECS = {
    "agent_employment": AuthoritySpec("agent_employment", "administrative_structural", True, ("start_date", "end_date")),
    "ddr_projects": AuthoritySpec("ddr_projects", "administrative_structural", True, ("start_year", "end_year")),
    "ref_students": AuthoritySpec("ref_students", "administrative_structural", True, ("year",)),
    "ref_fonds": AuthoritySpec("ref_fonds", "administrative_structural", True),
    "ref_publication_type": AuthoritySpec("ref_publication_type", "descriptive_catalogue", True),
    "ref_ddr_period": AuthoritySpec("ref_ddr_period", "administrative_structural", True, ("slug",)),
    "ref_methodology": AuthoritySpec("ref_methodology", "interpretative_analytical", False),
    "ref_project_theme": AuthoritySpec("ref_project_theme", "interpretative_analytical", False),
    "ref_project_outcome": AuthoritySpec("ref_project_outcome", "interpretative_analytical", False),
    "ref_beneficiary_audience": AuthoritySpec("ref_beneficiary_audience", "interpretative_analytical", False),
    "ref_epistemic_stance": AuthoritySpec("ref_epistemic_stance", "interpretative_analytical", False),
}

INTENT_HINTS = {
    "ref_students": re.compile(r"\bstudent(?:s)?\b", re.IGNORECASE),
    "ref_fonds": re.compile(r"\bfonds?\b", re.IGNORECASE),
    "ref_publication_type": re.compile(r"\b(publication type|reports?|working papers?|prospectuses|interviews?)\b", re.IGNORECASE),
    "ref_ddr_period": re.compile(r"\b(ddr )?period|later ddr|early ddr|formation|peak productivity|institutional decline\b", re.IGNORECASE),
    "ref_methodology": re.compile(r"\bmethodolog(?:y|ies)|method(s)?\b", re.IGNORECASE),
    "ref_project_theme": re.compile(r"\btheme|disability|healthcare|computing and design|design education\b", re.IGNORECASE),
    "ref_project_outcome": re.compile(r"\boutcome|prototype|toolkit|software|publication\b", re.IGNORECASE),
    "ref_beneficiary_audience": re.compile(r"\bbeneficiar(?:y|ies)|audience|patients|clinicians|government departments\b", re.IGNORECASE),
    "ref_epistemic_stance": re.compile(r"\bepistemic|stance|cybernetic|systematic|participatory\b", re.IGNORECASE),
}

AUTHORITY_INTENT_TERMS = {
    "student", "students", "fond", "fonds", "publication", "publications", "report", "reports",
    "period", "periods", "methodology", "methodologies", "theme", "themes", "outcome", "outcomes",
    "beneficiary", "beneficiaries", "audience", "audiences", "epistemic", "stance", "stances", "classified", "classification", "classifications",
}


class AuthorityRegistry:
    """Discovers selected authority records without treating them as documents."""

    def inventory(self) -> list[dict[str, Any]]:
        return [
            {
                "authority_type": authority_type,
                "source": f"database_authorities.{authority_type}",
                "epistemic_type": spec.epistemic_type,
                "direct_lookup": spec.direct_lookup,
                "temporal_fields": list(spec.temporal_fields),
                "allowed_roles": AUTHORITY_ALLOWED_ROLES[authority_type],
                "sync_definition": AUTHORITY_DEFINITIONS[authority_type],
            }
            for authority_type, spec in AUTHORITY_SPECS.items()
        ]

    def selected_types(self, question: str) -> list[str]:
        return [authority_type for authority_type, pattern in INTENT_HINTS.items() if pattern.search(question)]

    def resolve(self, db: Any, question: str, authority_types: list[str] | None = None) -> list[AuthorityContext]:
        selected = authority_types if authority_types is not None else self.selected_types(question)
        contexts: list[AuthorityContext] = []
        question_terms = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", question)} - AUTHORITY_INTENT_TERMS
        for authority_type in selected:
            spec = AUTHORITY_SPECS[authority_type]
            rows = db.execute(
                text("""
                    SELECT authority_id, code, label, description, metadata
                    FROM database_authorities
                    WHERE authority_type = :authority_type
                    ORDER BY label
                """),
                {"authority_type": authority_type},
            ).mappings().all()
            matched = self._period_matches(question, rows) if authority_type == "ref_ddr_period" else [row for row in rows if self._matches(question_terms, row)]
            if authority_type != "ref_ddr_period" and self._is_collection_request(question):
                matched = rows
            for row in matched:
                contexts.append(
                    AuthorityContext(
                        source=f"database_authorities.{authority_type}",
                        authority_type=authority_type,
                        authority_id=str(row["authority_id"]),
                        role="structural_context",
                        fields={
                            "label": row["label"],
                            "code": row["code"],
                            "description": row["description"],
                            **dict(row["metadata"] or {}),
                            "epistemic_type": spec.epistemic_type,
                            "authority_classification": "database authority classification" if spec.epistemic_type == "interpretative_analytical" else "database authority record",
                        },
                    )
                )
        return contexts

    @staticmethod
    def _is_collection_request(question: str) -> bool:
        return bool(re.search(r"\b(?:which|what|list|show|find|search|represented|classified)\b", question, re.IGNORECASE))

    @staticmethod
    def _period_matches(question: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", question)]
        if not years:
            return []
        matched = []
        for row in rows:
            range_match = re.fullmatch(r"(\d{4})-(\d{2,4})", str(row["authority_id"]))
            if not range_match:
                continue
            start = int(range_match.group(1))
            end_token = range_match.group(2)
            end = int(end_token) if len(end_token) == 4 else (start // 100) * 100 + int(end_token)
            if any(start <= year <= end for year in years):
                matched.append(row)
        return matched

    @staticmethod
    def _matches(question_terms: set[str], row: dict[str, Any]) -> bool:
        haystack = " ".join(str(value or "") for value in (row["authority_id"], row["code"], row["label"], row["description"], *dict(row["metadata"] or {}).values())).lower()
        return bool(question_terms & {term for term in re.findall(r"[a-z]{3,}", haystack)})