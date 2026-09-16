#!/usr/bin/env python3
"""Run the bounded source-interrogation UAT against a local backend endpoint."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


QUESTIONS = [
    "What documents mention Janet Daley?",
    "What documents mention Richard Langdon?",
    "What documents mention Pierre Gourmain?",
    "What documents mention Bruce Archer?",
    "What documents mention Eileen Adams?",
    "What documents mention Ken Baynes?",
    "What projects did Bruce Archer work on?",
    "What projects did Kenneth Agnew work on?",
    "What projects did Richard Langdon work on?",
    "What documents by Richard Langdon are available?",
    "What documents by Bruce Archer are available?",
    "When did DEU take in its first students?",
    "When was the DDR formally constituted?",
    "Which students are recorded in the DDR register?",
    "What was Eileen Adams's degree?",
    "What was Kenneth Agnew's thesis title?",
    "Who led the Design of battery operated appliances project?",
    "What is Job 31?",
    "What did the Peak productivity period cover?",
    "What projects were funded by the National Council for Educational Technology?",
    "What documents mention hospital bedstead?",
    "What records mention design research courses?",
    "How did DDR documents describe design research?",
]

EXTENDED_QUESTIONS = [
    "What was Bruce Archer's involvement at DDR?",
    "What role did Bruce Archer hold?",
    "When did Bruce Archer work at DDR?",
    "List the documents Bruce Archer worked on",
]

DOCUMENT_GROUNDED_QUESTIONS = [
    ("DG01", "doc_338541406157_72774d03522b", "What categories or relationships are shown in Archer's Fig. 5 taxonomy diagram?"),
    ("DG02", "doc_287080879712_f1d3b8ea4fcc", "What appointment matter does Ken Baynes discuss in this August 1984 letter?"),
    ("DG03", "doc_546216480663_d30d6979348e", "What aspect of the Design Analysis project is addressed in Job 170 report 108.4?"),
    ("DG04", "doc_404613335296_abe79cd10b57", "Whose biography is this April 1970 document, and what biographical facts does it explicitly record?"),
    ("DG05", "doc_338541406157_1cb3d7b8e15f", "How does Archer introduce or define design research in this February 1976 paper?"),
    ("DG06", "doc_546216480663_d284c46b5001", "What problem, method, or result is documented in Job 170 report 108.2?"),
    ("DG07", "doc_940221533316_403ace0e8414", "How does this design game propose that playing cards are used in modelling layout decisions?"),
    ("DG08", "doc_287080879712_1f266fad7f24", "What role or decisions are recorded for the Design Dimension project advisory group?"),
    ("DG09", "doc_287080879712_e68aa903d7c8", "What scope or structure is proposed in the March 1984 curriculum report outline?"),
    ("DG10", "doc_287080879712_c776e78a6d5b", "What aims, methods, or content does this Design Dimension paper identify?"),
    ("DG11", "doc_546216480663_37a7e8b448e6", "What does Job 170 report 108.3 record about the Design Analysis project?"),
    ("DG12", "doc_512813169945_c4c92a4138cc", "What course content, participants, or aims are recorded in The management of design course report?"),
    ("DG13", "doc_767973606400_989abba82642", "What feasibility question does Job 97 report 97.4 address?"),
    ("DG14", "doc_338541406157_fde8dc3a316d", "What issues, attendees, actions, or unresolved matters are recorded in these confidential working-party minutes?"),
    ("DG15", "doc_321843234637_b514872d126c", "What concepts, examples, or teaching activities appear in the March 1976 Computers in design course notes?"),
    ("DG16", "doc_338541406157_3c95cfa4ad23", "How are learning curves, entropy, or cybernetics used in this ICI business-modelling paper?"),
    ("DG17", "doc_930287260339_cf797b8d4ce2", "What does Christopher Frayling say about the topic asked in this June 2013 interview?"),
    ("DG18", "doc_338541406157_ba2e3cef8801", "What account of design practice is presented in Archer's How designers design paper?"),
    ("DG19", "doc_287080879712_7061158bd9df", "Which participating institutions, commitments, or governance arrangements are set out in the heads of agreement?"),
    ("DG20", "doc_338541406157_c12bf4363463", "What programme or stages of product development does Archer set out in this handout?"),
    ("DG21", "doc_404613335296_2ccc52ae1737", "What construction problem, materials, measurements, or instructions appear in these handwritten notes?"),
    ("DG22", "doc_287080879712_14c4a9f6818d", "What objectives, participants, or planned activities does the second draft of this five-year programme set out?"),
    ("DG23", "doc_338541406157_908ca994a9f9", "What international issues, recommendations, or remit are discussed in this August 1980 IDAC committee paper?"),
    ("DG24", "doc_338541406157_d55a4a64a6df", "What method of design does this reprint describe, and what additional material is included?"),
    ("DG25", "doc_321843234637_3dafa63de05f", "What scientific framework for understanding design does George Mallen set out in this September 1979 paper?"),
    ("DG26", "doc_338541406157_3355b11af2f5", "What is the key takeaway from Archer's Electrohome lectures?"),
]


def interrogate(
    base_url: str,
    question: str,
    question_id: str | None = None,
    target_document_id: str | None = None,
) -> tuple[int, dict]:
    payload = {"query": question, "top_k": 5, "mode": "exploratory"}
    if question_id:
        payload["question_id"] = question_id
    if target_document_id:
        payload["target_document_ids"] = [target_document_id]
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/analysis/interrogate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.status, json.load(response)


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    document_grounded = "--document-grounded" in sys.argv
    if document_grounded:
        question_set = DOCUMENT_GROUNDED_QUESTIONS
    elif "--extended" in sys.argv:
        question_set = QUESTIONS + EXTENDED_QUESTIONS
    else:
        question_set = QUESTIONS
    numeric_args = [argument for argument in sys.argv[2:] if argument not in {"--document-grounded", "--extended"}]
    start = int(numeric_args[0]) if numeric_args else 1
    end = int(numeric_args[1]) if len(numeric_args) > 1 else len(question_set)
    for number, item in enumerate(question_set[start - 1:end], start=start):
        if document_grounded:
            question_id, expected_document_id, question = item
        else:
            question_id, expected_document_id, question = None, None, item
        try:
            status, result = interrogate(base_url, question, question_id, expected_document_id)
            stage = result.get("stage_execution") or {}
            answer = " ".join(str(result.get("answer", "")).split())
            retrieved_evidence = result.get("retrieved_evidence") or []
            returned_document_ids = sorted({
                evidence.get("document_id")
                for evidence in retrieved_evidence
                if evidence.get("document_id")
            })
            provenance_validation = result.get("provenance_validation") or {}
            print(json.dumps({
                "number": number,
                "question_id": question_id,
                "question": question,
                "expected_document_id": expected_document_id,
                "http_status": status,
                "query_id": result.get("query_id"),
                "answer_origin": result.get("answer_origin"),
                "model_call_count": stage.get("call_count"),
                "retrieved_evidence_count": len(retrieved_evidence),
                "returned_document_ids": returned_document_ids,
                "authority_evidence_count": len(result.get("authority_evidence") or []),
                "provenance_valid": provenance_validation.get("valid"),
                "provenance_source_count": provenance_validation.get("source_count"),
                "missingness_count": len(result.get("missingness") or []),
                "answer": answer,
            }, ensure_ascii=True), flush=True)
        except (OSError, urllib.error.HTTPError, urllib.error.URLError, ValueError) as error:
            print(json.dumps({"number": number, "question": question, "error": str(error)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())