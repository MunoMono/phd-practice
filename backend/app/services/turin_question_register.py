"""Approved immutable Turin core research questions for formal production runs."""

from __future__ import annotations

from typing import Literal


TurinQuestion = tuple[Literal["known_relationship", "contested_interpretation", "scoped_missingness"], str]


TURIN_QUESTION_REGISTER: dict[str, TurinQuestion] = {
    "KR1": ("known_relationship", "What documentary traces connect Job 171, “Designer-computer interaction in the early stages of design”, to the people, activities and outputs associated with it?"),
    "KR2": ("known_relationship", "How is Bruce Archer’s role in teaching and learning practice with students represented across multiple DDR documents, and what aspects of that role are directly evidenced rather than inferred?"),
    "KR3": ("known_relationship", "What evidence connects Ken Baynes and Phil Roberts within the work of the Design Education Unit?"),
    "KR4": ("known_relationship", "How is John Wood’s role in console design and ergonomics documented across different DDR source types?"),
    "CI1": ("contested_interpretation", "How was “design research” understood within the DDR, and to what extent do the surviving documents present a consistent conception of it?"),
    "CI2": ("contested_interpretation", "How do different contributors describe the relationship between design, science and research?"),
    "CI3": ("contested_interpretation", "How do contemporary DDR documents and later retrospective accounts differ in their descriptions of the Design Education Unit?"),
    "CI4": ("contested_interpretation", "What competing interpretations of systematic design process can be identified in the corpus?"),
    "SM1": ("scoped_missingness", "Does the current digitised corpus establish why the decision to close the DDR was made?"),
    "SM2": ("scoped_missingness", "Can the current digitised corpus establish who initiated computing activity within the DDR?"),
    "SM3": ("scoped_missingness", "Can the surviving digitised records establish how Design in General Education was received by its intended users?"),
    "SM4": ("scoped_missingness", "What can the current digitised corpus establish about Henrietta Ryott’s role in the DDR between 1973 and 1977?"),
}


def validate_registered_question(question_id: str, research_case: str, research_question: str) -> None:
    registered = TURIN_QUESTION_REGISTER.get(question_id)
    if registered is None:
        raise ValueError("Formal Turin runs require an approved question/register ID.")
    expected_case, expected_question = registered
    if research_case != expected_case or research_question != expected_question:
        raise ValueError("Formal Turin runs must use the exact approved question text and research case for the question/register ID.")