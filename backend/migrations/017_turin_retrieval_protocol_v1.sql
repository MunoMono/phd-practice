-- Versioned Retrieval Protocol v1.0 snapshots. Existing experiment runs remain unchanged.

ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS question_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS retrieval_protocol_version VARCHAR(128),
    ADD COLUMN IF NOT EXISTS retrieval_plan_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS retrieval_plan_version VARCHAR(128),
    ADD COLUMN IF NOT EXISTS retrieval_plan_approval_state VARCHAR(32),
    ADD COLUMN IF NOT EXISTS retrieval_plan_json JSONB,
    ADD COLUMN IF NOT EXISTS retrieval_scope VARCHAR(64),
    ADD COLUMN IF NOT EXISTS retrieval_run_classification VARCHAR(64),
    ADD COLUMN IF NOT EXISTS execution_environment VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_question_id ON experiment_runs(question_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_retrieval_plan_id ON experiment_runs(retrieval_plan_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_runs_primary_question_protocol
    ON experiment_runs(question_id, retrieval_protocol_version)
    WHERE retrieval_run_classification = 'primary' AND retrieval_scope = 'corpus_wide';

CREATE TABLE IF NOT EXISTS turin_retrieval_plans (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) NOT NULL UNIQUE,
    question_id VARCHAR(64) NOT NULL,
    protocol_version VARCHAR(128) NOT NULL,
    plan_version VARCHAR(128) NOT NULL,
    researcher_approval_state VARCHAR(32) NOT NULL,
    researcher_approved_at TIMESTAMP,
    run_classification VARCHAR(64) NOT NULL,
    supersedes_plan_id VARCHAR(255),
    plan_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (question_id, plan_version)
);

CREATE TABLE IF NOT EXISTS turin_authority_document_links (
    id SERIAL PRIMARY KEY,
    link_id VARCHAR(255) NOT NULL UNIQUE,
    authority_source VARCHAR(255) NOT NULL,
    authority_type VARCHAR(128) NOT NULL,
    authority_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    archive_record_pid VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(128) NOT NULL,
    provenance_source TEXT NOT NULL,
    rationale TEXT NOT NULL,
    approval_state VARCHAR(32) NOT NULL,
    approved_by VARCHAR(255),
    approved_at TIMESTAMP,
    link_version VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (relationship_type IN ('archive_record_pid', 'asset_media_pid', 'explicit_project_record_relation', 'provenance_backed_archive_relation')),
    CHECK (approval_state IN ('approved', 'pending', 'rejected')),
    CHECK (approval_state <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_turin_authority_document_links_authority
    ON turin_authority_document_links(authority_type, authority_id);
CREATE INDEX IF NOT EXISTS idx_turin_authority_document_links_document
    ON turin_authority_document_links(document_id);

CREATE OR REPLACE FUNCTION reject_executed_retrieval_plan_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM experiment_runs WHERE retrieval_plan_id = OLD.plan_id) THEN
        RAISE EXCEPTION 'Executed retrieval plans are immutable; create a new plan version instead.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_executed_retrieval_plan_update ON turin_retrieval_plans;
CREATE TRIGGER reject_executed_retrieval_plan_update
BEFORE UPDATE OR DELETE ON turin_retrieval_plans
FOR EACH ROW EXECUTE FUNCTION reject_executed_retrieval_plan_mutation();