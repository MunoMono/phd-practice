-- Preserve full Source Interrogation provenance and researcher follow-up work.
ALTER TABLE missingness_events
    ADD COLUMN IF NOT EXISTS source_document_ids_json JSONB,
    ADD COLUMN IF NOT EXISTS source_chunk_ids_json JSONB,
    ADD COLUMN IF NOT EXISTS follow_up_action TEXT;