# Turin Experiment Manual UAT

`turin-experiment-uat-v0.1.csv` is the first-pass manual User Acceptance Test inventory for the currently deployed Turin Experiment research instrument.

This is a production, researcher-facing functional UAT. Each row identifies one independently observable interaction or output to test in a browser. It does not assert that a function works merely because code exists, and it does not assess the academic correctness of Granite-generated historical interpretation.

The `status`, `actual_result`, `severity`, and `notes` columns are intentionally blank. The researcher completes them during manual production testing, recording `PASS` or `FAIL` and any observed result.

Use non-destructive test data where an interaction persists a researcher note, assessment, passage, mapping, claim, or missingness review. Record failed links, unavailable APIs, unexpected empty states, and lost refresh/query state in the corresponding CSV row; do not fix them during this UAT pass.
