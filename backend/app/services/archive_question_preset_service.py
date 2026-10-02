"""Controlled archive-scope presets for broad evidence-led questions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchiveQuestionPreset:
    preset_id: str
    record_pid: str
    required_terms: tuple[str, ...]
    documentary_terms: tuple[str, ...]

    def matches(self, question: str) -> bool:
        normalized = " ".join(question.lower().split())
        return all(term in normalized for term in self.required_terms)


ARCHIVE_QUESTION_PRESETS: tuple[ArchiveQuestionPreset, ...] = (
    ArchiveQuestionPreset(
        preset_id="general_purpose_hospital_bedstead",
        record_pid="232731654562",
        required_terms=("general purpose hospital bedstead",),
        documentary_terms=(
            "ergonomics", "testing", "test", "user", "users", "needs",
            "bedstead", "hospital", "design development",
        ),
    ),
    ArchiveQuestionPreset(
        preset_id="richard_langdon_teaching_ephemera",
        record_pid="475236004017",
        required_terms=("richard langdon", "teaching"),
        documentary_terms=(
            "richard", "langdon", "curriculum", "course", "teaching",
            "practice", "autumn", "spring", "tutorial",
        ),
    ),
    ArchiveQuestionPreset(
        preset_id="ddr_teaching_learning_practice",
        record_pid="989478384551",
        required_terms=("teaching",),
        documentary_terms=(
            "course", "lecture", "curriculum", "education", "teaching", "tutorial",
            "computing", "computer-aided", "programming", "human factors", "simulation",
            "action research", "methodology", "measurement",
        ),
    ),
)


def matching_archive_question_preset(question: str) -> ArchiveQuestionPreset | None:
    return next((preset for preset in ARCHIVE_QUESTION_PRESETS if preset.matches(question)), None)
