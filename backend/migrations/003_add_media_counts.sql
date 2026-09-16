-- Add media asset counts to documents table
-- These track PDF and TIFF files attached to each PID authority

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS pdf_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS tiff_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_media_count INTEGER GENERATED ALWAYS AS (pdf_count + tiff_count) STORED;

-- Add helpful comment
COMMENT ON COLUMN documents.pdf_count IS 'Number of PDF files attached to this PID authority';
COMMENT ON COLUMN documents.tiff_count IS 'Number of TIFF master files attached to this PID authority';
COMMENT ON COLUMN documents.total_media_count IS 'Total media assets (PDFs + TIFFs) for provenance tracking';

-- Create index for performance on queries grouping by PID
CREATE INDEX IF NOT EXISTS idx_documents_pid_media_counts ON documents(pid, pdf_count, tiff_count) WHERE pid IS NOT NULL;
