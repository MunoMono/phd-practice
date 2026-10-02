BEGIN;

ALTER TABLE visual_annotations
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255);

UPDATE visual_annotations
SET owner_id = COALESCE(owner_id, reviewer)
WHERE owner_id IS NULL AND reviewer IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_visual_annotations_owner_id ON visual_annotations (owner_id);

COMMIT;
