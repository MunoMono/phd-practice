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
    "agent_employment": re.compile(r"\b(?:role|involvement|work|tenure|staff|position|employment|held)\b", re.IGNORECASE),
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
        question_terms = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", question)} - AUTHORITY_INTENT_TERMS - {
            "what", "which", "who", "when", "where", "work", "worked", "available", "first", "take", "took", "into", "with", "from", "that", "this", "about", "under", "were", "was", "are", "did", "does", "led", "lead",
        }
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
            if authority_type == "ref_ddr_period":
                matched = self._period_matches(question, rows)
            elif authority_type == "ddr_projects":
                matched = self._project_matches(question, question_terms, rows)
            elif not question_terms and not spec.direct_lookup:
                matched = rows
            else:
                matched = self._best_matches(question_terms, rows)
            if authority_type != "ref_ddr_period" and self._is_collection_request(question, authority_type):
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
    def _project_matches(question: str, question_terms: set[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        job_match = re.search(r"\bjob(?: number)?\s+(\d+)\b", question, re.IGNORECASE)
        if job_match:
            return [row for row in rows if str(row["authority_id"]) == job_match.group(1)]
        scored_rows = []
        for row in rows:
            haystack = " ".join(str(value or "") for value in (row["authority_id"], row["code"], row["label"], row["description"], *dict(row["metadata"] or {}).values())).lower()
            matched_terms = question_terms & set(re.findall(r"[a-z]{3,}", haystack))
            if matched_terms:
                scored_rows.append((len(matched_terms), row))
        if not scored_rows:
            return []
        best_score = max(score for score, _row in scored_rows)
        return [row for score, row in scored_rows if score == best_score]

    @staticmethod
    def _best_matches(question_terms: set[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored_rows = []
        for row in rows:
            haystack = " ".join(str(value or "") for value in (row["authority_id"], row["code"], row["label"], row["description"], *dict(row["metadata"] or {}).values())).lower()
            score = len(question_terms & set(re.findall(r"[a-z]{3,}", haystack)))
            if score:
                scored_rows.append((score, row))
        if not scored_rows:
            return []
        best_score = max(score for score, _row in scored_rows)
        return [row for score, row in scored_rows if score == best_score]

    @staticmethod
    def _is_collection_request(question: str, authority_type: str) -> bool:
        patterns = {
            "ref_students": r"\b(?:which|what|list|show)\s+(?:all\s+)?students?\b",
            "ref_fonds": r"\b(?:which|what|list|show)\s+(?:all\s+)?fonds?\b",
            "ref_publication_type": r"\b(?:which|what|list|show)\s+(?:all\s+)?(?:publication types?|reports?|working papers?|prospectuses|interviews?)\b",
        }
        pattern = patterns.get(authority_type)
        return bool(pattern and re.search(pattern, question, re.IGNORECASE))

    @staticmethod
    def _period_matches(question: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", question)]
        if not years:
            if re.search(r"\b(?:formally )?constitut(?:ed|ion)\b", question, re.IGNORECASE):
                return [row for row in rows if "formal constitution" in f"{row['label']} {row['description']}".lower()]
            question_lower = question.lower()
            return [
                row for row in rows
                if len(str(row["label"] or "").split()) >= 2
                and str(row["label"]).lower() in question_lower
            ]
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