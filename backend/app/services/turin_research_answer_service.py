"""Documentary answer construction and independent, passage-bound review."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


class SupportingQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    exact_quote: str = Field(min_length=1, max_length=200)


class ClaimReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_number: int = Field(ge=1)
    verdict: Literal["supported", "unsupported", "uncertain"]
    evidence_ids: list[str] = Field(default_factory=list)
    supporting_quotes: list[SupportingQuote] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=200)


class AnswerReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimReview]


class DocumentaryProposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposition_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    actor: str | None
    qualifications: str
    evidence_ids: list[str] = Field(min_length=1)


class DocumentaryRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposition_ids: list[str] = Field(min_length=2)
    basis: Literal["direct_documentary_statement", "qualified_interpretation"]
    interpretation: str = Field(min_length=1)
    limits: str = Field(min_length=1)
    documentary_basis: str = Field(min_length=1)


class DocumentaryAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    propositions: list[DocumentaryProposition] = Field(min_length=1)
    relationships: list[DocumentaryRelationship]
    unsupported_conclusions: list[str] = Field(min_length=1)


MAX_VERIFICATION_OUTPUT_TOKENS = 2048
MIN_VERIFICATION_OUTPUT_TOKENS = 256
VERIFICATION_CONTEXT_RESERVE_TOKENS = 256
_CITATION_MARKER = re.compile(r"\[(EV-[0-9a-f]{12}(?:\s*,\s*EV-[0-9a-f]{12})*)\]")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")
_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_STOP_WORDS = {
    "about", "after", "also", "among", "and", "are", "been", "being", "but",
    "can", "could", "did", "does", "during", "each", "from", "have", "into",
    "its", "more", "most", "not", "only", "other", "over", "same", "some",
    "such", "than", "that", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "upon", "using", "was", "were", "what",
    "when", "where", "which", "while", "will", "with", "would", "you", "how",
    "connect", "connected", "connecting", "relate", "related", "relating",
    "link", "linked", "linking", "integrate", "integrated", "integrating",
    "teaching", "teach", "did", "does",
}


def _normalise_text(value: str) -> str:
    return " ".join(value.split()).replace("’", "'").casefold()


def _source_passages_overlap(left: str, right: str) -> bool:
    left_terms = set(_WORD.findall(_normalise_text(left)))
    right_terms = set(_WORD.findall(_normalise_text(right)))
    smaller_count = min(len(left_terms), len(right_terms))
    return (
        smaller_count >= 12
        and len(left_terms & right_terms) / smaller_count >= 0.55
    )


def _content_terms(value: str) -> set[str]:
    terms: set[str] = set()
    for word in _WORD.findall(value.casefold()):
        if word in _STOP_WORDS:
            continue
        if word.endswith("ally"):
            word = word[:-4]
        elif word.endswith("ies") and len(word) > 5:
            word = word[:-3] + "y"
        elif word.endswith(("ing", "ed")) and len(word) > 5:
            word = word[:-3] if word.endswith("ing") else word[:-2]
            if len(word) > 3 and word[-1] == word[-2]:
                word = word[:-1]
        elif word.endswith("s") and len(word) > 4:
            word = word[:-1]
        terms.add(word)
    return terms


def _question_facets(question: str) -> list[set[str]]:
    action = re.search(
        r"\b(?:connect|relate|link|integrate|apply|use|examine|compare|describe)\w*\b",
        question,
        flags=re.IGNORECASE,
    )
    focus = question[action.end():] if action else question
    phrases = re.split(
        r",|;|\b(?:and|or|to|with|through|between|across|into)\b",
        focus,
        flags=re.IGNORECASE,
    )
    facets: list[set[str]] = []
    seen: set[frozenset[str]] = set()
    for phrase in phrases:
        terms = _content_terms(phrase)
        if not terms or frozenset(terms) in seen:
            continue
        facets.append(terms)
        seen.add(frozenset(terms))
    if not facets:
        terms = _content_terms(question)
        if terms:
            facets.append(terms)
    return facets


def _complete_relevant_context_sentences(
    text: str, facets: list[set[str]]
) -> list[tuple[int, str, frozenset[int], frozenset[int], int, bool, bool]]:
    candidates: list[
        tuple[int, str, frozenset[int], frozenset[int], int, bool, bool]
    ] = []
    start = 0
    boundaries = list(_SENTENCE_BOUNDARY.finditer(text))
    for boundary in [*boundaries, None]:
        end = boundary.start() if boundary else len(text)
        fragment = text[start:end]
        sentence_start = start
        if boundary:
            start = boundary.end()

        leading = len(fragment) - len(fragment.lstrip())
        sentence_start += leading
        fragment = fragment.strip()
        page_prefix = re.match(r"^\d{1,3}\s*\n+", fragment)
        if page_prefix:
            sentence_start += page_prefix.end()
            fragment = fragment[page_prefix.end():].lstrip()
            leading = len(text[sentence_start:end]) - len(text[sentence_start:end].lstrip())
            sentence_start += leading

        sentence = fragment
        if len(sentence) < 35 or not re.match(r"^[A-Z“\"']", sentence):
            continue
        if not re.search(r"[.!?][”\"')\]]*$", sentence):
            continue
        if re.search(r"(?:_{2,}|[�]{1,}|\\[\\?\\]|<!--|\\b(?:Figure|Fig\\.)\\s*\\d+\\s*:)", sentence):
            continue

        terms = _content_terms(sentence)
        matching_facets = frozenset(
            index
            for index, facet in enumerate(facets)
            if terms & facet
        )
        complete_facets = frozenset(
            index for index in matching_facets if facets[index] <= terms
        )
        qualified = bool(re.search(
            r"\b(if|may|might|only|intended|insofar|however|although|unless|whereas)\b",
            sentence,
            flags=re.IGNORECASE,
        ))
        bounded_condition = bool(re.search(
            r"\bon those occasions when\b|\bonly when\b|\bonly if\b",
            sentence,
            flags=re.IGNORECASE,
        ))
        strong_qualification = bounded_condition or bool(re.search(
            r"\b(if|intended|insofar|unless)\b|may or may not",
            sentence,
            flags=re.IGNORECASE,
        ))
        if not complete_facets and not qualified:
            continue
        score = (
            2 * len(matching_facets)
            + 5 * len(complete_facets)
            + 18 * int(bounded_condition)
            + 12 * int(strong_qualification and not bounded_condition)
            + 2 * int(qualified and not strong_qualification)
        )
        candidates.append((
            sentence_start,
            sentence,
            matching_facets,
            complete_facets,
            score,
            qualified,
            strong_qualification,
        ))
    return candidates


def _evidence_records(packets: list[Any], question: str = "") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    identity_by_content: dict[str, str] = {}
    passages_by_source_page: dict[tuple[str, Any], list[tuple[str, str]]] = {}
    seen_source_ids: set[str] = set()
    facets = _question_facets(question)
    candidates: list[dict[str, Any]] = []
    for packet in packets:
        source_id = str(packet.source_id)
        if source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)
        match = packet.retrieval_match
        hit_id = str(match.get("chunk_id") or "")
        chunks = packet.document_context.get("ordered_chunks") or []
        hit = next((chunk for chunk in chunks if str(chunk.get("chunk_id")) == hit_id), None)
        if hit is None or not str(hit.get("text") or "").strip():
            raise ValueError(f"Retrieved evidence {source_id} has no complete matching passage.")

        document = packet.document
        content_identity = str(
            document.get("source_content_identity")
            or document.get("asset_id")
            or document.get("asset_pid")
            or source_id
        )
        provenance = dict(match.get("provenance") or {})
        source_uri = provenance.get("source_uri") or document.get("source_uri")
        asset_pid = (
            document.get("asset_pid")
            or provenance.get("asset_pid")
            or document.get("asset_id")
        )
        document_id = str(document.get("document_id") or source_id.split(":")[0])
        base_record = {
            "source_id": source_id,
            "document_id": document_id,
            "archive_record_pid": (
                document.get("archive_record_pid")
                or provenance.get("archive_record_pid")
                or provenance.get("record_pid")
            ),
            "attached_media_pid": (
                document.get("attached_media_pid")
                or provenance.get("attached_media_pid")
                or document.get("pid")
            ),
            "asset_pid": asset_pid,
            "pdf_master_asset_pid": asset_pid if (
                source_uri
                and "/master/" in str(source_uri)
                and "__pdf_master__" in str(source_uri)
            ) else None,
            "asset_id": document.get("asset_id") or provenance.get("asset_id"),
            "source_uri": source_uri,
            "title": document.get("title") or match.get("title"),
            "date": document.get("date") or match.get("display_date"),
            "evidence_status": (
                packet.source_status.get("temporal_status")
                or document.get("evidence_status")
                or "not classified in the retrieved record"
            ),
            "source_content_identity": content_identity,
        }
        anchor_id = "EV-" + hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:12]
        spans = [{
            "evidence_id": anchor_id,
            "source_id": source_id,
            "document_id": document_id,
            "chunk_id": hit_id,
            "page": match.get("page") or hit.get("page"),
            "text": str(hit["text"]),
            "evidence_role": "retrieved_match",
        }]
        span_page = spans[0]["page"]
        context_candidates = []
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id") or "")
            chunk_text = str(chunk.get("text") or "")
            for (
                offset, sentence, matched_facets, complete_facets, score,
                qualified, strong_qualification
            ) in (
                _complete_relevant_context_sentences(chunk_text, facets)
            ):
                context_candidates.append({
                    **base_record,
                    "source_id": f"{document_id}:{chunk_id}:{offset}",
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "page": chunk.get("page"),
                    "text": sentence,
                    "evidence_role": (
                        "selected_complete_sentence_from_retrieved_match"
                        if chunk_id == hit_id
                        else "promoted_complete_neighbor_sentence"
                    ),
                    "selected_facet_indexes": sorted(complete_facets),
                    "selected_facets": [
                        " ".join(sorted(facets[index]))
                        for index in sorted(complete_facets)
                    ],
                    "matched_facet_indexes": sorted(matched_facets),
                    "matched_question_facets": [
                        " ".join(sorted(facets[index]))
                        for index in sorted(matched_facets)
                    ],
                    "selection_score": score,
                    "has_explicit_qualification": qualified,
                    "has_strong_qualification": strong_qualification,
                })
        for span in spans:
            passage_identity = hashlib.sha256(
                _normalise_text(span["text"]).encode("utf-8")
            ).hexdigest()
            duplicate_of = identity_by_content.get(passage_identity)
            source_page_key = (content_identity, span_page)
            if duplicate_of is None:
                duplicate_of = next((
                    evidence_id
                    for evidence_id, prior_text in passages_by_source_page.get(
                        source_page_key, []
                    )
                    if _source_passages_overlap(span["text"], prior_text)
                ), None)
            identity_by_content.setdefault(passage_identity, span["evidence_id"])
            if duplicate_of is None:
                passages_by_source_page.setdefault(source_page_key, []).append(
                    (span["evidence_id"], span["text"])
                )
            records.append({
                **base_record,
                **span,
                "duplicate_of": duplicate_of,
            })
        candidates.extend(context_candidates)

    selected: list[dict[str, Any]] = []
    selected_texts = {
        _normalise_text(item["text"])
        for item in records
        if item.get("duplicate_of") is None
    }
    selected_per_document: dict[str, int] = {}
    selected_per_source_identity: dict[str, int] = {}
    selected_per_source_identity_facet: dict[tuple[str, int], int] = {}
    selected_per_facet = [0 for _ in facets]
    maximum_spans = min(12, max(2, 2 * len(facets)))
    while len(selected) < maximum_spans:
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for candidate in candidates:
            normalized_text = _normalise_text(candidate["text"])
            if normalized_text in selected_texts:
                continue
            document_id = candidate["document_id"]
            source_identity = candidate["source_content_identity"]
            if selected_per_document.get(document_id, 0) >= 2:
                continue
            if selected_per_source_identity.get(source_identity, 0) >= 2:
                continue
            eligible_facets = [
                index
                for index in candidate["selected_facet_indexes"]
                if selected_per_facet[index] < 3
                and selected_per_source_identity_facet.get(
                    (source_identity, index), 0
                ) == 0
            ]
            qualified_facets = [
                index
                for index in candidate["matched_facet_indexes"]
                if candidate["has_strong_qualification"]
                and selected_per_source_identity_facet.get(
                    (source_identity, index), 0
                ) > 0
            ] if candidate["has_explicit_qualification"] else []
            if not eligible_facets and not qualified_facets:
                continue
            coverage_gain = sum(
                2 if selected_per_facet[index] == 0 else 1
                for index in eligible_facets
            )
            diversity_bonus = int(
                selected_per_source_identity.get(source_identity, 0) == 0
            )
            rank = (
                100 * coverage_gain
                + candidate["selection_score"]
                + 3 * diversity_bonus
            )
            ranked.append((rank, candidate["selection_score"], candidate))
        if not ranked:
            break
        _, _, chosen = max(
            ranked,
            key=lambda item: (
                item[0],
                item[1],
                -selected_per_source_identity.get(
                    item[2]["source_content_identity"], 0
                ),
                item[2]["source_id"],
            ),
        )
        normalized_text = _normalise_text(chosen["text"])
        selected_texts.add(normalized_text)
        selected.append(chosen)
        selected_per_document[chosen["document_id"]] = (
            selected_per_document.get(chosen["document_id"], 0) + 1
        )
        source_identity = chosen["source_content_identity"]
        selected_per_source_identity[source_identity] = (
            selected_per_source_identity.get(source_identity, 0) + 1
        )
        for index in chosen["selected_facet_indexes"]:
            if selected_per_facet[index] < 3:
                selected_per_facet[index] += 1
        for index in chosen["matched_facet_indexes"]:
            selected_per_source_identity_facet[(source_identity, index)] = 1
        records.append({
            **chosen,
            "evidence_id": "EV-" + hashlib.sha256(
                f"{chosen['source_id']}:{chosen['text']}".encode("utf-8")
            ).hexdigest()[:12],
            "duplicate_of": None,
        })
    return records


def build_research_answer_prompt(question: str, evidence: list[dict[str, Any]]) -> str:
    packet = json.dumps([
        {
            "evidence_id": item["evidence_id"],
            "document_id": item.get("document_id"),
            "archive_record_pid": item.get("archive_record_pid"),
            "attached_media_pid": item.get("attached_media_pid"),
            "asset_pid": item.get("asset_pid"),
            "asset_id": item.get("asset_id"),
            "source_uri": item.get("source_uri"),
            "title": item.get("title"),
            "date": item.get("date"),
            "evidence_status": item.get("evidence_status"),
            "evidence_role": item["evidence_role"],
            "source_content_identity": item.get("source_content_identity"),
            "selected_facet_indexes": item.get("selected_facet_indexes", []),
            "selected_facets": item.get("selected_facets", []),
            "matched_question_facets": item.get("matched_question_facets", []),
            "chunk_id": item["chunk_id"],
            "page": item.get("page"),
            "passage_text": item["text"],
            "duplicate_of": item.get("duplicate_of"),
        }
        for item in evidence
        if item.get("duplicate_of") is None
    ], ensure_ascii=False, separators=(",", ":"))
    return (
        "You are writing a scholarly archival research answer. Answer the research question "
        "using only the documentary passages in EVIDENCE. Write coherent academic prose of "
        "approximately 300–450 words when the evidence permits; do not pad to reach a target. "
        "Interpret relationships where the passages justify them, and distinguish documentary "
        "statements from qualified interpretation. Cite each material historical assertion "
        "with one or more exact evidence identifiers in square brackets, such as [EV-0123456789ab]. "
        "ARCHIVAL_METADATA establishes source identity and provenance only; it does not establish "
        "historical action, intent, responsibility, influence, or implementation. Use evidence_status "
        "to distinguish contemporary records from later testimony; do not convert metadata dates into "
        "undocumented chronology. "
        "Preserve named actors, chronology, conditional antecedents, modality and category boundaries. "
        "A conditional example is not proof of general or implemented practice. Similar terminology, "
        "catalogue proximity, or repeated/duplicate text does not establish influence, causation, "
        "collaboration, institutional implementation, intent, or independent corroboration. "
        "Every evidence item is an independently identified source span. Selection priority and "
        "question-facet labels help locate passages; lexical overlap is not historical support. Use "
        "only the exact passage and its documentary role to support each claim. A teaching or lecture "
        "statement establishes what that document says, not that a method was implemented in teaching "
        "or practice. A conditional example does not establish actual use, and a book recommendation "
        "does not establish influence or reception. Duplicate text does not establish independent "
        "corroboration. Distinguish documented content, implementation, "
        "and later reception. State evidential limits without claiming historical non-existence. Do "
        "not invent citations or historical facts. Return prose only; no JSON or bibliography.\n\n"
        f"RESEARCH QUESTION:\n{question}\n\nEVIDENCE:\n{packet}"
    )


def _documentary_reading_packet(evidence: list[dict[str, Any]]) -> str:
    return json.dumps([
        {
            "evidence_id": item["evidence_id"],
            "source_identity": item.get("title"),
            "date": item.get("date"),
            "page": item.get("page"),
            "evidence_status": item.get("evidence_status"),
            "evidence_role": item["evidence_role"],
            "passage_text": item["text"],
        }
        for item in evidence if item.get("duplicate_of") is None
    ], ensure_ascii=False, separators=(",", ":"))


def build_documentary_analysis_prompt(
    question: str, evidence: list[dict[str, Any]]
) -> str:
    return (
        "Read EVIDENCE to prepare a compact scholarly argument. Return JSON matching the schema. "
        "For each documentary proposition, state only what its source says, name its actor if "
        "established (otherwise null), preserve conditions, possibility, uncertainty and time "
        "limits, and reference the exact evidence_ids. Do NOT copy quotations: the application "
        "retains the original source spans. Do not complete damaged or cut-off text. Source "
        "identity establishes attribution, not delivery or implementation. Cover the question's "
        "distinct concepts using concise, non-redundant propositions with unique IDs. "
        "Keep documentary propositions separate from proposed interpretative relationships. "
        "For each meaningful comparison explain the documentary_basis: what specific statements "
        "connect or differ, what that warrants analytically, and what it does not establish. "
        "Label a relationship direct_documentary_statement only if a source states it; otherwise "
        "qualified_interpretation. A limitation cannot rescue an unwarranted historical claim. "
        "The presence of related concepts in separate documents is not evidence of a unified "
        "curriculum, institutional integration, influence, implementation or historical agreement. "
        "Compare methodological differences without forcing agreement or a coherent narrative. "
        "Do not force a numerical number of relationships. List unsupported conclusions to "
        "exclude. These notes are proposed reasoning for independent assessment, not validated "
        "history. Keep the complete analysis brief; spend words on documentary reasoning, not "
        "administrative repetition.\n\n"
        f"RESEARCH QUESTION:\n{question}\n\nEVIDENCE:\n{_documentary_reading_packet(evidence)}"
    )


def validate_documentary_analysis(
    raw_analysis: str, evidence: list[dict[str, Any]]
) -> DocumentaryAnalysis:
    """Check structure and immutable references, not semantic or historical support."""
    analysis = DocumentaryAnalysis.model_validate_json(raw_analysis)
    available = {
        item["evidence_id"]: item
        for item in evidence
        if item.get("duplicate_of") is None
    }
    if len(available) != sum(item.get("duplicate_of") is None for item in evidence):
        raise ValueError("Duplicate evidence identifiers in the documentary packet.")
    proposition_ids = [item.proposition_id for item in analysis.propositions]
    if len(set(proposition_ids)) != len(proposition_ids):
        raise ValueError("Duplicate proposition identifiers in the documentary analysis.")
    for proposition in analysis.propositions:
        if len(set(proposition.evidence_ids)) != len(proposition.evidence_ids):
            raise ValueError("A proposition repeats an evidence identifier.")
        for evidence_id in proposition.evidence_ids:
            if evidence_id not in available:
                raise ValueError(f"Unknown or duplicate evidence reference: {evidence_id}")
    for relationship in analysis.relationships:
        references = relationship.proposition_ids
        if len(set(references)) != len(references):
            raise ValueError("A relationship repeats a proposition identifier.")
        if not set(references) <= set(proposition_ids):
            raise ValueError("A relationship refers to an unknown proposition.")
    return analysis


def build_documentary_composition_prompt(
    question: str, evidence: list[dict[str, Any]], analysis: DocumentaryAnalysis
) -> str:
    return (
        "Write a scholarly archival answer using only the supplied passages. "
        f"\n\nRESEARCH QUESTION:\n{question}\n\nEVIDENCE:\n"
        + _documentary_reading_packet(evidence)
        + "\n\nEVIDENCE-TO-CLAIM ANALYSIS:\n"
        + analysis.model_dump_json()
        + "\n\nCOMPOSITION TASK:\n"
        "Write 300–450 words in two or three substantive paragraphs where supported. "
        "Answer directly through meaningful relationships, not serial document summaries. "
        "The analysis is model-generated planning, not additional historical evidence. Its "
        "structure and identifiers have been checked; semantic support has NOT been "
        "proved. No model classification constitutes independent validation. "
        "Use the proposed propositions and relationships, checking their "
        "meaning against the original passages. Do not add substantive historical claims or "
        "relationships to fill gaps. If a planned claim exceeds the source, state the scoped "
        "limit instead of presenting it as history. Preserve actors, "
        "conditional antecedents, permissive modality and temporal limits. Present your "
        "qualified comparisons explicitly as interpretations, retaining their limits. "
        "Attribute source statements and cite every material assertion with its existing EV ID "
        "in square brackets. Paraphrase faithfully; do not generate direct quotations. "
        "Distinguish conceptual links and proposed applications from demonstrated delivery, "
        "implementation and reception. Do not convert ongoing development or possible use "
        "into operational deployment. Exclude the unsupported conclusions in the analysis. "
        "Do not assert a coherent framework or unified curriculum merely because the concepts "
        "occur in teaching documents. State which requested connections remain unestablished "
        "in this packet, without claiming that they never existed. Return prose only."
    )


async def generate_documentary_synthesis(
    question: str, evidence: list[dict[str, Any]], inference_service: Any
) -> dict[str, Any]:
    """Two construction calls, no review call or automatic repair; human review required."""
    if not evidence:
        raise ValueError("No source passages are available for documentary synthesis.")
    started = time.monotonic()
    analysis_prompt = build_documentary_analysis_prompt(question, evidence)
    analysis_result = await inference_service.generate_experiment(
        analysis_prompt, max_tokens=2048, temperature=0.2, do_sample=False,
        response_schema=DocumentaryAnalysis.model_json_schema(),
        stage="documentary_evidence_analysis",
    )
    if analysis_result.get("generation", {}).get("done_reason") == "length":
        raise RuntimeError("Documentary analysis was truncated; composition was not attempted.")
    analysis = validate_documentary_analysis(analysis_result["raw_response"], evidence)
    composition_prompt = build_documentary_composition_prompt(question, evidence, analysis)
    answer_result = await inference_service.generate_experiment(
        composition_prompt, max_tokens=1200, temperature=0.2, do_sample=False,
        stage="documentary_scholarly_composition",
    )
    answer = answer_result["raw_response"]
    if not answer.strip():
        raise RuntimeError("Documentary composition returned an empty answer.")
    return {
        "original_draft": answer,
        "answer": None,
        "verified_answer": None,
        "analysis_raw": analysis_result["raw_response"],
        "analysis": analysis.model_dump(),
        "proposition_source_spans": {
            item.proposition_id: [
                dict(source) for source in evidence if source["evidence_id"] in item.evidence_ids
            ]
            for item in analysis.propositions
        },
        "citation_bindings": [
            {
                **sentence,
                "source_spans": [
                    dict(source) for source in evidence
                    if source["evidence_id"] in sentence["evidence_ids"]
                ],
                "unknown_evidence_ids": [
                    evidence_id for evidence_id in sentence["evidence_ids"]
                    if evidence_id not in {source["evidence_id"] for source in evidence}
                ],
                "semantic_status": "UNASSESSED",
            }
            for sentence in _draft_sentences(answer)
        ],
        "binding_status": "REFERENCES_CHECKED_NOT_SEMANTICALLY_VERIFIED",
        "candidate_state": "SCHOLARLY_CANDIDATE_REQUIRES_RESEARCHER_REVIEW",
        "human_acceptance_status": "UNASSESSED",
        "evidence_sources": evidence,
        "inference_call_count": 2,
        "inference_calls": [
            {"stage": stage, **result.get("generation", {})}
            for stage, result in (
                ("documentary_evidence_analysis", analysis_result),
                ("documentary_scholarly_composition", answer_result),
            )
        ],
        "prompt_hashes": {
            "version": "documentary-two-stage-v2",
            "analysis": hashlib.sha256(analysis_prompt.encode()).hexdigest(),
            "composition": hashlib.sha256(composition_prompt.encode()).hexdigest(),
        },
        "total_seconds": time.monotonic() - started,
    }


def build_verification_prompt(
    question: str, claims: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> str:
    cited_ids = {
        evidence_id
        for claim in claims
        for evidence_id in claim["evidence_ids"]
    }
    candidate_scores: dict[str, int] = {}
    for claim in claims:
        terms = _content_terms(claim["assertion"])
        for item in evidence:
            score = len(terms & _content_terms(item["text"]))
            candidate_scores[item["evidence_id"]] = max(
                candidate_scores.get(item["evidence_id"], 0), score
            )
    candidate_ids = {
        evidence_id
        for evidence_id, score in sorted(
            candidate_scores.items(), key=lambda pair: pair[1], reverse=True
        )
        if score >= 2
    }
    selected_ids = cited_ids | set(list(candidate_ids)[:12])
    verification_evidence = [{
        "evidence_id": item["evidence_id"],
        "document_id": item.get("document_id"),
        "title": item.get("title"),
        "date": item.get("date"),
        "evidence_status": item.get("evidence_status"),
        "evidence_role": item["evidence_role"],
        "chunk_id": item["chunk_id"],
        "page": item.get("page"),
        "passage_text": item["text"],
        "duplicate_of": item.get("duplicate_of"),
    } for item in evidence if item["evidence_id"] in selected_ids]
    expected_numbers = [claim["claim_number"] for claim in claims]
    return (
        "Audit every listed draft sentence independently. Return exactly one JSON claim entry for "
        "each expected claim number and no others. Evidence_ids must list the source spans that "
        "support the complete assertion, whether or not the draft cited them; this allows citation "
        "errors to be distinguished from absent support. Mark supported only if the evidence supports "
        "the entire assertion, including actor, chronology, scope, modality and evidence role. "
        "Preserve conditional and permissive qualifications. Metadata is provenance, not evidence of "
        "action. Duplicate spans are not independent corroboration. For every evidence ID relied upon, "
        "provide a short exact quote copied from that span's passage_text. Do not infer support from "
        "shared vocabulary alone. For unsupported/uncertain claims, provide no quote and give a concise "
        "reason. Do not rewrite the draft. No extra keys or prose.\n\n"
        "JSON shape: {\"claims\":[{\"claim_number\":1,\"verdict\":\"supported\","
        "\"evidence_ids\":[\"EV-0123456789ab\"],\"supporting_quotes\":["
        "{\"evidence_id\":\"EV-0123456789ab\",\"exact_quote\":\"exact passage text\"}],"
        "\"rationale\":\"\"}]}\n\n"
        f"QUESTION:\n{question}\n\nEXPECTED_CLAIMS:\n"
        + json.dumps(claims, ensure_ascii=False, separators=(",", ":"))
        + "\n\nEXPECTED_CLAIM_NUMBERS:\n"
        + json.dumps(expected_numbers)
        + "\n\nEVIDENCE:\n"
        + json.dumps(verification_evidence, ensure_ascii=False, separators=(",", ":"))
    )


def _verification_output_budget(
    prompt: str, claim_count: int, inference_service: Any
) -> int:
    estimated_input_tokens = (len(prompt) + 3) // 4
    max_input_tokens = int(getattr(inference_service, "max_input_tokens", 30_000))
    context_window_tokens = int(getattr(inference_service, "qwen_num_ctx", 40_960))
    if estimated_input_tokens > max_input_tokens:
        raise RuntimeError(
            "The compact verification prompt exceeds the active runtime input budget "
            f"({estimated_input_tokens} estimated tokens; limit {max_input_tokens})."
        )

    available_context_tokens = (
        context_window_tokens - estimated_input_tokens - VERIFICATION_CONTEXT_RESERVE_TOKENS
    )
    if available_context_tokens < MIN_VERIFICATION_OUTPUT_TOKENS:
        raise RuntimeError(
            "Insufficient active context remains for a complete verifier response "
            f"({available_context_tokens} tokens available after input and reserve)."
        )
    schema_budget = min(
        MAX_VERIFICATION_OUTPUT_TOKENS,
        256 + 48 * max(claim_count, 1),
    )
    return min(schema_budget, available_context_tokens)


def _draft_sentences(draft: str) -> list[dict[str, Any]]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", draft.strip()) if paragraph.strip()]
    sentences: list[dict[str, Any]] = []
    boundary = re.compile(
        r"(?<=[.!?])(?:\s*\[EV-[0-9a-f]{12}(?:\s*,\s*EV-[0-9a-f]{12})*\])*(?=\s+[A-Z0-9\"'“])"
    )
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        start = 0
        spans = []
        for match in boundary.finditer(paragraph):
            if match.end() > start:
                spans.append(paragraph[start:match.end()])
                start = match.end()
        if start < len(paragraph):
            spans.append(paragraph[start:])
        for text in spans:
            sentence = text.strip()
            if not sentence:
                continue
            evidence_ids = list(dict.fromkeys(
                evidence_id
                for marker in _CITATION_MARKER.findall(sentence)
                for evidence_id in re.split(r"\s*,\s*", marker)
            ))
            assertion = re.sub(r"\s+([.!?])", r"\1", _CITATION_MARKER.sub("", sentence).strip())
            if assertion:
                sentences.append({
                    "claim_number": len(sentences) + 1,
                    "paragraph": paragraph_index,
                    "text": sentence,
                    "assertion": assertion,
                    "evidence_ids": evidence_ids,
                })
    return sentences


def _qualification_issues(
    sentence: str, review: ClaimReview, evidence_by_id: Mapping[str, dict[str, Any]]
) -> list[str]:
    issues: list[str] = []
    assertion = sentence.casefold()
    cited_chunks = []
    for quote in review.supporting_quotes:
        evidence = evidence_by_id.get(quote.evidence_id)
        if evidence is None:
            continue
        passage = evidence["text"]
        if _normalise_text(quote.exact_quote) in _normalise_text(passage):
            cited_chunks.append(passage)
    source_text = " ".join(cited_chunks).casefold()
    if re.search(r"\bmay\b", source_text) and re.search(
        r"\b(must|requires?|always|necessarily|is required to)\b", assertion
    ):
        issues.append("possible_permissive_modality_broadening")
    if re.search(r"\b(suffices|sufficient)\b", source_text) and re.search(
        r"\b(essential|necessary|must|required|requires?)\b", assertion
    ):
        issues.append("possible_sufficiency_to_necessity_broadening")
    if re.search(r"\b(if|when|whenever|on those occasions when|intended to)\b", source_text) and not re.search(
        r"\b(if|when|where|conditional|hypothetical|could|would|may|might|example)\b",
        assertion,
    ):
        issues.append("possible_conditional_scope_broadening")
    duplicate_ids = {
        evidence_by_id[evidence_id].get("duplicate_of")
        for evidence_id in review.evidence_ids
        if evidence_id in evidence_by_id and evidence_by_id[evidence_id].get("duplicate_of")
    }
    if duplicate_ids and re.search(
        r"\b(independent corroboration|independently confirmed|multiple independent sources)\b",
        assertion,
    ):
        issues.append("duplicate_passages_claimed_as_independent_corroboration")
    return issues


def validate_answer_review(
    draft: str,
    evidence: list[dict[str, Any]],
    review: AnswerReview,
    batch_integrity_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    sentences = _draft_sentences(draft)
    reviews_by_number: dict[int, list[ClaimReview]] = {}
    for item in review.claims:
        reviews_by_number.setdefault(item.claim_number, []).append(item)

    results = []
    integrity_findings = list(batch_integrity_issues or [])
    disposition_counts = {
        "VERIFIED": 0,
        "UNSUPPORTED": 0,
        "MISATTRIBUTED": 0,
        "UNREVIEWED": 0,
    }
    for index, sentence in enumerate(sentences, start=1):
        candidates = reviews_by_number.get(index, [])
        issues: list[str] = []
        matched = candidates[0] if len(candidates) == 1 else None
        if not candidates:
            issues.append("verifier_omitted_or_changed_assertion")
        elif len(candidates) > 1:
            issues.append("verifier_duplicated_claim_review")
        if matched is not None:
            unknown_ids = sorted(set(matched.evidence_ids) - evidence_by_id.keys())
            if unknown_ids:
                issues.append("unknown_evidence_ids:" + ",".join(unknown_ids))
            if not sentence["evidence_ids"]:
                issues.append("assertion_has_no_inline_citation")
            if set(sentence["evidence_ids"]) != set(matched.evidence_ids):
                issues.append("verifier_citations_do_not_match_draft")
            if matched.verdict != "supported":
                issues.append("verifier_verdict_" + matched.verdict)
            if not matched.supporting_quotes:
                issues.append("verifier_provided_no_passage_quote")
            quoted_evidence_ids = {quote.evidence_id for quote in matched.supporting_quotes}
            if set(matched.evidence_ids) - quoted_evidence_ids:
                issues.append("cited_source_has_no_supporting_quote")
            verified_quotes = []
            for quote in matched.supporting_quotes:
                evidence_item = evidence_by_id.get(quote.evidence_id)
                if evidence_item is None:
                    issues.append("quote_uses_unknown_evidence_id")
                    continue
                passage = evidence_item["text"]
                if not quote.exact_quote.strip() or (
                    _normalise_text(quote.exact_quote) not in _normalise_text(passage)
                ):
                    issues.append("supporting_quote_not_found_in_source_span")
                else:
                    verified_quotes.append({
                        "evidence_id": quote.evidence_id,
                        "chunk_id": evidence_item["chunk_id"],
                        "page": evidence_item.get("page"),
                        "document_id": evidence_item.get("document_id"),
                        "exact_quote": quote.exact_quote,
                    })
            issues.extend(_qualification_issues(sentence["assertion"], matched, evidence_by_id))
        quote_evidence_ids = {
            quote["evidence_id"] for quote in verified_quotes
        } if matched is not None else set()
        inline_ids = set(sentence["evidence_ids"])
        alternate_support = bool(quote_evidence_ids - inline_ids)
        citation_problem = (
            "assertion_has_no_inline_citation" in issues
            or "verifier_citations_do_not_match_draft" in issues
        )
        if not candidates or len(candidates) != 1:
            disposition = "UNREVIEWED"
        elif citation_problem and alternate_support and matched.verdict == "supported":
            disposition = "MISATTRIBUTED"
        elif matched.verdict != "supported" or any(
            issue in issues for issue in (
                "supporting_quote_not_found_in_source_span",
                "verifier_provided_no_passage_quote",
                "cited_source_has_no_supporting_quote",
                "possible_permissive_modality_broadening",
                "possible_sufficiency_to_necessity_broadening",
                "possible_conditional_scope_broadening",
            )
        ) or any(issue.startswith("unknown_evidence_ids:") for issue in issues):
            disposition = "UNSUPPORTED"
        elif citation_problem or issues:
            disposition = "MISATTRIBUTED"
        else:
            disposition = "VERIFIED"
        disposition_counts[disposition] += 1
        results.append({
            "claim_id": f"claim-{index}",
            "assertion": sentence["assertion"],
            "rendered_text": sentence["text"],
            "paragraph": sentence["paragraph"],
            "evidence_ids": sentence["evidence_ids"],
            "review_evidence_ids": matched.evidence_ids if matched else [],
            "verdict": matched.verdict if matched else "unreviewed",
            "rationale": matched.rationale if matched else (
                "The independent reviewer did not complete this claim; this is not a finding "
                "that the claim is unsupported."
            ),
            "supporting_quotes": verified_quotes if matched else [],
            "issues": sorted(set(issues)),
            "disposition": disposition,
            "verified": disposition == "VERIFIED",
        })
    unexpected_reviews = sum(
        len(items) if number > len(sentences) else max(0, len(items) - 1)
        for number, items in reviews_by_number.items()
    )
    if unexpected_reviews:
        integrity_findings.append({
            "batch": None,
            "issue": "unexpected_or_duplicate_claim_numbers",
            "claim_numbers": sorted(
                number for number, items in reviews_by_number.items()
                if number > len(sentences) or len(items) > 1
            ),
        })
    if integrity_findings:
        results.append({
            "claim_id": "review-integrity",
            "assertion": "",
            "rendered_text": "",
            "paragraph": None,
            "evidence_ids": [],
            "verdict": "uncertain",
            "rationale": "One or more verifier batches did not match their expected claim-number set.",
            "supporting_quotes": [],
            "issues": ["verifier_batch_claim_coverage_mismatch"],
            "disposition": "UNREVIEWED",
            "verified": False,
        })
    return {
        "valid": bool(sentences) and all(item["verified"] for item in results),
        "status": "complete" if (
            disposition_counts["UNREVIEWED"] == 0 and not integrity_findings
        ) else "incomplete",
        "claim_count": len(sentences),
        "verified_claim_count": disposition_counts["VERIFIED"],
        "disposition_counts": disposition_counts,
        "integrity_findings": integrity_findings,
        "claims": results,
    }


def _unreviewed_validation(draft: str, status: str) -> dict[str, Any]:
    claims = [
        {
            "claim_id": f"claim-{index}",
            "assertion": sentence["assertion"],
            "rendered_text": sentence["text"],
            "paragraph": sentence["paragraph"],
            "evidence_ids": sentence["evidence_ids"],
            "review_evidence_ids": [],
            "verdict": "unreviewed",
            "rationale": (
                f"Verification did not complete ({status}); this is not a finding "
                "that the claim is unsupported."
            ),
            "supporting_quotes": [],
            "issues": [status],
            "disposition": "UNREVIEWED",
            "verified": False,
        }
        for index, sentence in enumerate(_draft_sentences(draft), start=1)
    ]
    return {
        "valid": False,
        "status": status,
        "claim_count": len(claims),
        "verified_claim_count": 0,
        "disposition_counts": {
            "VERIFIED": 0,
            "UNSUPPORTED": 0,
            "MISATTRIBUTED": 0,
            "UNREVIEWED": len(claims),
        },
        "integrity_findings": [],
        "claims": claims,
    }


async def verify_research_answer(
    question: str,
    draft: str,
    evidence: list[dict[str, Any]],
    inference_service: Any,
) -> dict[str, Any]:
    sentences = _draft_sentences(draft)
    if not sentences:
        raise ValueError("The saved research-answer draft contains no verifiable claims.")
    batches = [
        sentences[offset:offset + 3]
        for offset in range(0, len(sentences), 3)
    ]
    reviews: list[ClaimReview] = []
    integrity_findings: list[dict[str, Any]] = []
    verifier_calls: list[dict[str, Any]] = []
    batch_diagnostics: list[dict[str, Any]] = []
    for batch_number, batch in enumerate(batches, start=1):
        prompt = build_verification_prompt(question, batch, evidence)
        budget: int | None = None
        try:
            budget = _verification_output_budget(
                prompt, len(batch), inference_service
            )
            result = await inference_service.generate_experiment(
                prompt,
                max_tokens=budget,
                temperature=0.0,
                do_sample=False,
                response_schema=AnswerReview.model_json_schema(),
                stage="research_answer_verification",
            )
        except (RuntimeError, ValueError) as exc:
            finding = {
                "batch": batch_number,
                "issue": "verifier_batch_failed",
                "expected_claim_numbers": [item["claim_number"] for item in batch],
                "message": f"{type(exc).__name__}: {exc}",
            }
            integrity_findings.append(finding)
            batch_diagnostics.append({
                **finding,
                "raw_output_characters": 0,
                "max_output_tokens": budget,
                "status": "failed",
            })
            verifier_calls.append({
                "stage": "research_answer_verification",
                "model": inference_service.model_name,
                "provider": inference_service.provider,
                "status": "failed",
                "error": finding["message"],
                "max_output_tokens": budget,
                "batch": batch_number,
            })
            continue

        raw_review = str(result.get("raw_response") or "")
        generation = result.get("generation") or {}
        stop_reason = generation.get("done_reason")
        output_tokens = generation.get("eval_count")
        reported_budget = int(generation.get("max_tokens") or budget or 0)
        call = {
            "stage": "research_answer_verification",
            "model": inference_service.model_name,
            "provider": inference_service.provider,
            "request_id": generation.get("request_id"),
            "started_at_utc": generation.get("request_started_at_utc"),
            "ended_at_utc": generation.get("request_ended_at_utc"),
            "actual_input_tokens": generation.get("prompt_eval_count"),
            "actual_output_tokens": output_tokens,
            "estimated_input_tokens": generation.get("estimated_input_tokens"),
            "max_output_tokens": reported_budget,
            "context_window_tokens": generation.get("num_ctx"),
            "duration_ms": generation.get("request_elapsed_ms"),
            "stop_reason": stop_reason,
            "status": "completed",
            "batch": batch_number,
        }
        verifier_calls.append(call)
        truncated = stop_reason == "length" or (
            output_tokens is not None and reported_budget > 0
            and int(output_tokens) >= reported_budget
        )
        batch_status = "complete"
        batch_issue: dict[str, Any] | None = None
        if truncated:
            batch_status = "truncated"
            batch_issue = {
                "batch": batch_number,
                "issue": "verifier_batch_truncated",
                "expected_claim_numbers": [item["claim_number"] for item in batch],
            }
        else:
            try:
                decoded_review = json.loads(raw_review)
                parsed_review = AnswerReview.model_validate(decoded_review)
            except (json.JSONDecodeError, ValueError) as exc:
                batch_status = "invalid_review"
                batch_issue = {
                    "batch": batch_number,
                    "issue": "verifier_batch_invalid",
                    "expected_claim_numbers": [item["claim_number"] for item in batch],
                    "message": str(exc),
                }
            else:
                expected_numbers = {item["claim_number"] for item in batch}
                returned_numbers = [item.claim_number for item in parsed_review.claims]
                returned_set = set(returned_numbers)
                missing = sorted(expected_numbers - returned_set)
                duplicated = sorted(
                    number for number in expected_numbers
                    if returned_numbers.count(number) > 1
                )
                unexpected = sorted(returned_set - expected_numbers)
                if missing or duplicated or unexpected:
                    batch_status = "coverage_mismatch"
                    batch_issue = {
                        "batch": batch_number,
                        "issue": "verifier_claim_number_coverage_mismatch",
                        "expected_claim_numbers": sorted(expected_numbers),
                        "missing_claim_numbers": missing,
                        "duplicate_claim_numbers": duplicated,
                        "unexpected_claim_numbers": unexpected,
                    }
                reviews.extend(parsed_review.claims)
        if batch_issue is not None:
            integrity_findings.append(batch_issue)
        batch_diagnostics.append({
            "batch": batch_number,
            "expected_claim_numbers": [item["claim_number"] for item in batch],
            "status": batch_status,
            "raw_output_characters": len(raw_review),
            "stop_reason": stop_reason,
            "output_tokens": output_tokens,
            "output_token_budget": reported_budget,
            "issue": batch_issue,
        })

    validation = validate_answer_review(
        draft,
        evidence,
        AnswerReview(claims=reviews),
        batch_integrity_issues=integrity_findings,
    )
    validation["verification_calls"] = len(verifier_calls)
    overall_status = validation["status"]
    diagnostics = {
        "status": overall_status,
        "message": None if overall_status == "complete" else (
            "At least one verifier batch was incomplete or did not match its expected claim numbers."
        ),
        "expected_claim_count": len(sentences),
        "batch_count": len(batches),
        "batches": batch_diagnostics,
    }
    return {
        "verification_report": validation,
        "verification_diagnostics": diagnostics,
        "inference_calls": verifier_calls,
    }


async def generate_research_answer(
    question: str, packets: list[Any], inference_service: Any
) -> dict[str, Any]:
    evidence = _evidence_records(packets, question)
    if not evidence:
        raise ValueError("No source passages are available for the research-answer path.")
    draft_result = await inference_service.generate_experiment(
        build_research_answer_prompt(question, evidence),
        max_tokens=900,
        temperature=0.2,
        do_sample=False,
        stage="research_answer_generation",
    )
    draft = str(draft_result.get("raw_response") or "")
    if not draft.strip():
        raise RuntimeError("The research-answer generation returned an empty draft.")
    verified_result = await verify_research_answer(
        question, draft, evidence, inference_service
    )
    validation = verified_result["verification_report"]
    verification_diagnostics = verified_result["verification_diagnostics"]
    source_numbers = {item["evidence_id"]: index for index, item in enumerate(evidence, start=1)}
    diagnostic_paragraphs = []
    paragraph_claims: dict[int, list[dict[str, Any]]] = {}
    for claim in validation["claims"]:
        if not claim["rendered_text"]:
            continue
        paragraph_claims.setdefault(claim["paragraph"], []).append({
            "text": claim["rendered_text"],
            "claim_ids": [claim["claim_id"]],
            "evidence_ids": claim["evidence_ids"],
            "source_numbers": sorted({
                source_numbers[evidence_id]
                for evidence_id in claim["evidence_ids"]
                if evidence_id in source_numbers
            }),
        })
    for index in sorted(paragraph_claims):
        diagnostic_paragraphs.append({"claims": paragraph_claims[index]})

    generation = draft_result.get("generation") or {}
    generation_calls = [{
        "stage": "research_answer_generation",
        "model": inference_service.model_name,
        "provider": inference_service.provider,
        "request_id": generation.get("request_id"),
        "started_at_utc": generation.get("request_started_at_utc"),
        "ended_at_utc": generation.get("request_ended_at_utc"),
        "actual_input_tokens": generation.get("prompt_eval_count"),
        "actual_output_tokens": generation.get("eval_count"),
        "estimated_input_tokens": generation.get("estimated_input_tokens"),
        "max_output_tokens": generation.get("max_tokens"),
        "context_window_tokens": generation.get("num_ctx"),
        "duration_ms": generation.get("request_elapsed_ms"),
        "stop_reason": generation.get("done_reason"),
        "status": "completed",
    }, *verified_result["inference_calls"]]
    verified = validation["valid"]
    verification_status = verification_diagnostics["status"]
    verified_answer = draft if verified else None
    verified_paragraphs = diagnostic_paragraphs if verified else []
    researcher_facing = {
        "answer": verified_answer,
        "verified_answer": verified_answer,
        "original_draft": draft,
        "answer_paragraphs": verified_paragraphs,
        "verification_report": validation,
        "answer_origin": "qwen_research_answer_verified" if verified else None,
        "verification_status": "claims_verified" if verified else verification_status,
        "human_acceptance_status": "UNASSESSED",
    }
    return {
        "answer": verified_answer,
        "verified_answer": verified_answer,
        "answer_paragraphs": verified_paragraphs,
        "diagnostic_paragraphs": diagnostic_paragraphs,
        "researcher_facing": researcher_facing,
        "answer_origin": researcher_facing["answer_origin"],
        "answer_state": "synthesis_valid" if verified else "synthesis_partial",
        "candidate_state": (
            "CLAIMS_VERIFIED_NOT_HUMAN_ACCEPTED"
            if verified else "CLAIMS_REVIEWED_NOT_VERIFIED"
            if verification_status == "complete" else "VERIFICATION_INCOMPLETE"
        ),
        "human_acceptance_status": "UNASSESSED",
        "evidence_sources": evidence,
        "claim_verification": validation,
        "original_draft": draft,
        "verification_diagnostics": verification_diagnostics,
        "verification_status": verification_status,
        "inference_calls": generation_calls,
        "inference_call_count": len(generation_calls),
        "model_token_totals": {
            "input": sum(call.get("actual_input_tokens") or 0 for call in generation_calls),
            "output": sum(call.get("actual_output_tokens") or 0 for call in generation_calls),
        },
    }
