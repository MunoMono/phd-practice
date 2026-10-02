# Deployment Preflight Ready

This is a preparation checklist only. Do not deploy, access production, apply a
migration, or alter a production backup from this document.

## Frozen release facts

- Current git commit: `689ed68175abdadf91c74fcd36abaf49288c85fa`
- Effective corpus: `corpus_turin_targeted_5b176946674f`
- Local backend image: `innovation-design-backend:latest`
- Local backend runtime: `ollama`, model `qwen3:8b-q4_K_M`
- Canonical UAT manifest is mounted at `/app/ml_triage_uat_50.csv`
- Local frontend is served by Vite at `http://localhost:5174`

## Before deployment

- [ ] Record the production git commit and current deployed image tag.
- [ ] Confirm the production effective corpus remains
  `corpus_turin_targeted_5b176946674f`.
- [ ] Confirm the production model/runtime configuration matches the frozen
  release, including the UAT manifest path or packaged equivalent.
- [ ] Take and verify a production database snapshot/backup before service
  change.
- [ ] Identify and record the rollback image/tag and frontend build currently
  serving production.
- [ ] Confirm frontend build inputs point to the intended production API URL.

## Expected service changes

- Backend application image/configuration: expected to change.
- Frontend static build/deployment: expected to change.
- Database migrations: **not required**.
- Corpus materialisation, prompts, model configuration, and authority data:
  **not required and must not change**.

## Production smoke questions

1. Authority: `According to the project authorities, who led Jobs 146 and 175, who funded each, and what durations are recorded?`
2. Documentary: `What does the general purpose hospital bedstead final report show about the role of ergonomics, testing and user needs in DDR design development?`
3. Hybrid: `What does the database record establish about Richard Langdon’s formal DDR role, and what do his surviving teaching records show about his curriculum and teaching practice?`
4. Scoped missingness: `Do the surviving DDR closure records establish that Bruce Archer was responsible for the department’s closure?`

## Rollback

If a smoke test reveals a blocking defect, restore the recorded backend image,
frontend build, and configuration from the pre-deployment snapshot. Do not use
data migration rollback because no migration is planned.