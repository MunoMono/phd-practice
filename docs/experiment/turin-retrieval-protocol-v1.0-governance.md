# Turin Retrieval Protocol v1.0 Governance

## Run classification

`corpus_wide` is the first formal execution of an approved Turin research question under the currently approved retrieval protocol. It is production-only, searches the corpus-wide eligible documentary surface, and is the primary Turin experimental evidence.

`protocol_revision` is used only when a changed retrieval methodology is intended to govern the main experiment going forward. It must use a new protocol or plan version, record the superseded plan, and never makes earlier immutable runs interchangeable without qualification.

`sensitivity_or_diagnostic` deliberately varies one factor without replacing the primary result. This includes authority-linked candidate-document restriction, one controlled expansion, or alternative facet composition. It is supplementary and cannot overwrite a corpus-wide result.

## Authority-document links

An authority-document link requires a stable archive record PID, asset/media PID, explicit project-record relationship, or another provenance-backed archive relation. Title similarity, fuzzy matching, inferred semantic similarity, LLM judgement, and unrecorded researcher intuition are prohibited.

Each approved link records authority source/type/ID, document and archive identifiers, relationship type, provenance source, rationale, approval state, approver/date, and version. Only a visibly labelled `sensitivity_or_diagnostic` plan may restrict documents through approved link IDs. Main `corpus_wide` retrieval never does so.