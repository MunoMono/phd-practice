# Multimodal NLP ML for PhD Year 1 - Architecture Baseline

**Date:** January 2026  
**Project:** Epistemic Drift in Design Methods (1965-1985)  
**Researcher:** Graham  
**Status:** Architecture Complete, Implementation Phase

---

## Executive Summary

This document provides a comprehensive baseline of the current machine learning infrastructure for my PhD research on epistemic drift in design methods literature. The system implements a **PID-gated ingestion pipeline** with **full provenance tracking** to ensure academic rigor, reproducibility, and explainable AI outputs suitable for doctoral examination.

### Core Architecture Principles
1. **Quality Control**: Only curated archival materials (linked to Persistent Identifiers) enter the training corpus
2. **Academic Attribution**: Every AI prediction traces back to specific archival sources with formal citations
3. **Reproducibility**: Complete lineage tracking from raw documents through training to inference
4. **Text-Focused NLP**: BERT-based embeddings for semantic analysis (not multi-modal CLIP)

---

## 1. Research Context

### 1.1 Academic Focus
- **Temporal Scope**: Design methods literature 1965-1985
- **Research Question**: How did epistemic assumptions in design theory evolve during this formative period?
- **Methodology**: Computational text analysis with manual validation against archival sources
- **Output**: Traceable evidence for peer review and PhD examination

### 1.2 Data Sources
- **Primary Archive**: DDR Archive (Design Research Repository)
- **GraphQL API**: Authority records with Persistent Identifiers (PIDs)
- **Storage**: DigitalOcean Spaces (S3-compatible) for master files
- **Current Corpus**: 3 PIDs (2 PDFs, 1 TIFF collection)
- **Year 1 Target**: 50-100 curated PIDs

---

## 2. Technical Architecture

### 2.1 NLP Approach: Text-Focused BERT (Not CLIP)

**Clarification**: Despite "multimodal" in the project title, this is a **text-only NLP system**:

- **Primary Analysis**: Text extraction and semantic embeddings
- **Image Handling**: OCR for diagrams/slides → text extraction only
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional)
- **Visual Content**: Treated as documentation/context, not analytical targets
- **Rationale**: 90% of content value is textual; images are "eye candy" for human readers

**Why Not CLIP?**  
CLIP (multi-modal vision-language) would be used for image-text alignment tasks like:
- Matching diagrams to captions
- Visual similarity search
- Image classification

Our research analyzes **semantic shifts in written discourse**, not visual semantics.

### 2.2 Technology Stack

```yaml
Backend:
  - FastAPI 0.115.0 (REST + GraphQL)
  - PostgreSQL 14+ with pgvector 0.3.5
  - Python 3.11+
  
NLP Pipeline:
  - Docling 2.15.0 (PDF extraction, TIFF OCR)
  - sentence-transformers 3.3.0 (embeddings)
  - IBM Granite (planned fine-tuning)
  
Storage:
  - DigitalOcean Spaces (master files)
  - PostgreSQL (structured metadata + vectors)
  
Infrastructure:
  - Docker + docker-compose
  - nginx reverse proxy
  - Automated backups
```

### 2.3 Database Schema (with Provenance)

**Core Tables:**
- `documents`: Master file records with **PID linkage**
- `document_chunks`: Text segments with **384-dim vector embeddings**
- `training_runs`: Model provenance (which PIDs trained which model)
- `inference_logs`: XAI attribution (which chunks produced which predictions)
- `corpus_snapshots`: Dataset versioning with SHA-256 checksums

**Key Constraints:**
- `documents.pid`: **REQUIRED, UNIQUE** - no non-curated materials
- `documents.authority_id`: Links to GraphQL authority record
- `document_chunks.embedding`: pgvector `Vector(384)` type with IVFFlat index

---

## 3. PID-Gated Ingestion Pipeline

### 3.1 The Allowlist Problem (Now Solved)

**Original Risk**: S3 bucket contains PDFs/TIFFs for various purposes (drafts, admin docs, unvetted uploads). Without filtering, the ML model could train on "junk" data.

**Solution**: **Triple-gated PID validation** at every ingestion point:

1. **GraphQL Sync** (`backend/app/services/graphql_sync.py`):
   - Only syncs items with valid PIDs from DDR Archive
   - Filters for `pdf_files` and `tiff_files` (master quality only)
   - Rejects JPG derivatives and uncurated materials

2. **S3 Sync** (`backend/app/services/s3_sync.py`):
   - Extracts PIDs from filenames (e.g., `001808484369_master.pdf`)
   - Validates against Postgres authority records
   - Rejects files without valid PID linkage

3. **Manual Upload** (`backend/app/api/routes/documents.py`):
   - Requires PID parameter at upload endpoint
   - Validates PID exists in authority database
   - Fails upload if PID validation fails

### 3.2 TIFF Support (for Lecture Slides)

**Use Case**: PID `001808484369` has TIFF scans of lecture slides/diagrams

**Implementation**:
- Docling configured with `PipelineOptions(do_ocr=True)`
- OCR extracts text from visual elements
- Text → chunks → embeddings (same pipeline as PDFs)
- Images archived for human reference only

**Current Status**: Code complete, pending TIFF metadata addition to GraphQL response

---

## 4. Provenance & Explainable AI

### 4.1 Academic Requirements

**PhD Examination Needs**:
- Trace every claim back to specific archival sources
- Provide formal citations for manual validation
- Enable peer review of methodology
- Document reproducibility for other researchers

### 4.2 Provenance System (`backend/app/services/provenance_service.py`)

**Four-Layer Lineage Tracking**:

1. **Chunk Citations** (`build_chunk_citation()`):
   ```python
   # Generates formal academic citations:
   # "Design Methods in Architecture (1965), Chapter 2, Page 47, 
   #  para. 3. DDR Archive PID: 001808484369. 
   #  Source: https://ddr.archive.example/items/001808484369"
   ```

2. **Training Provenance** (`log_training_run()`):
   - Records which PIDs were used to train which model version
   - Links to corpus snapshots for reproducibility
   - Timestamps and hyperparameters stored

3. **Inference Attribution** (`log_inference()`):
   - For every AI prediction, log which source chunks contributed
   - Enables "Show your work" validation by supervisors
   - Links predictions → embeddings → chunks → PIDs → archives

4. **Corpus Versioning** (`create_corpus_snapshot()`):
   - SHA-256 checksums of entire dataset at training time
   - Metadata: PID list, document count, chunk count, date range
   - Enables exact reproduction of experiments

### 4.3 API Endpoints

```
GET  /api/provenance/chunk/{id}/citation          # Get formal citation
GET  /api/provenance/chunk/{id}/provenance        # Get full lineage
GET  /api/provenance/training/{run_id}            # Audit training data
GET  /api/provenance/inference/{id}               # Explain prediction
POST /api/provenance/snapshot/create              # Version dataset
```

---

## 5. Implementation Status

### 5.1 ✅ Completed (Production-Ready)

| Component | Status | Evidence |
|-----------|--------|----------|
| PID-gated architecture | ✅ Complete | All ingestion points validate PIDs |
| Database schema | ✅ Complete | Migration script with pgvector + provenance tables |
| GraphQL sync service | ✅ Complete | PDF/TIFF filtering, PID validation |
| S3 sync service | ✅ Complete | Allowlist enforcement, filename parsing |
| Authority validation | ✅ Complete | `authority_service.py` validates against GraphQL |
| Provenance system | ✅ Complete | Full XAI with 4-layer lineage tracking |
| API endpoints | ✅ Complete | Sync + provenance routes registered |
| Documentation | ✅ Complete | `PID_ARCHITECTURE.md`, `PROVENANCE_GUIDE.md`, `TESTING_GUIDE.md` |

### 5.2 🚧 In Progress

| Component | Status | Next Steps |
|-----------|--------|------------|
| Docling integration | Placeholder | Replace TODOs with actual PDF/TIFF extraction |
| TIFF metadata | GraphQL missing | Add `tiff_files` array for PID 001808484369 |
| Corpus expansion | 3 PIDs → 50-100 | Curate additional authority records |
| Embedding generation | Not started | Process all chunks after Docling complete |

### 5.3 📋 Planned (Year 1)

- **Drift Analysis**: Implement semantic distance metrics, topic modeling, concept extraction
- **Semantic Search**: Build similarity search interface with citation display
- **Granite Fine-Tuning**: Export HuggingFace datasets, train domain-specific LLM
- **Temporal Visualization**: Dashboard for drift patterns over time
- **Frontend**: React interface for evidence tracing (in progress)

---

## 6. Current Corpus Data

### 6.1 Sample PIDs (Test Data)

| PID | Title | Format | Status |
|-----|-------|--------|--------|
| `001808484369` | Design Thinking Workshop Slides | TIFF (OCR) | GraphQL metadata pending |
| `002345678901` | Design Methods Reader | PDF | Ready for ingestion |
| `003456789012` | Conference Proceedings 1970 | PDF | Ready for ingestion |

### 6.2 Metadata Example (GraphQL Response)

```json
{
  "pid": "002345678901",
  "title": "Design Methods Reader",
  "date_created": "1970-01-01",
  "pdf_files": [
    {
      "url": "https://spaces.example.com/002345678901_master.pdf",
      "role": "master"
    }
  ]
}
```

---

## 7. Validation & Testing

### 7.1 PID Filter Tests

**Test Script**: `backend/test_graphql_sync.py`

**Verification**:
1. Sync authority records from GraphQL
2. Validate only PID-linked items are processed
3. Confirm TIFFs and PDFs both accepted
4. Verify JPG derivatives rejected

### 7.2 Provenance Tests

**Manual Validation**:
1. Ingest sample PID → Generate chunks
2. Train model → Check `training_runs` table
3. Run inference → Verify `inference_logs` entries
4. Retrieve citation → Validate against archive URL

---

## 8. Discussion Points for Supervisors

### 8.1 Corpus Design Decisions

**Question 1: Corpus Size**  
- Current: 3 PIDs (proof of concept)
- Proposal: 50-100 PIDs for Year 1
- Trade-off: Quality (manual curation) vs. Quantity (statistical power)
- **Ask supervisors**: Is 50 adequate for meaningful drift analysis?

**Question 2: Temporal Granularity**  
- Option A: Year-by-year analysis (1965, 1966, 1967...)
- Option B: 5-year periods (1965-1969, 1970-1974, 1975-1979, 1980-1985)
- Option C: Decade-level (1960s vs. 1970s vs. 1980s)
- **Ask supervisors**: What temporal resolution supports the research question?

**Question 3: Drift Metrics**  
- Semantic distance (cosine similarity between time periods)
- Topic modeling (LDA/NMF topic evolution)
- Concept extraction (tracking specific terms/ideas)
- **Ask supervisors**: Which metrics align with design theory literature?

### 8.2 Academic Rigor Validation

**Provenance System Review**:
- Citation format follows academic standards?
- Lineage tracking sufficient for peer review?
- Reproducibility meets open science requirements?
- Ethics: All source materials properly attributed?

**Explainability for Examination**:
- Can examiners manually verify AI claims against archives?
- Is the "black box" sufficiently transparent for PhD defense?
- Documentation adequate for methods chapter?

### 8.3 Technical Feasibility

**Resource Planning**:
- Database: pgvector scales to 100K+ chunks?
- Compute: Embedding generation time estimates?
- Storage: DO Spaces costs for 50-100 PDFs/TIFFs?
- **Ask supervisors**: Budget constraints for Year 1?

**LLM Fine-Tuning Strategy**:
- IBM Granite 13B vs. Granite 7B (model size trade-offs)
- Domain adaptation: Pre-train on design corpus before fine-tuning?
- Evaluation: How to measure domain-specific performance?

---

## 9. Year 1 Roadmap

### Q1 2026 (Current Quarter)
- ✅ Architecture design complete
- ✅ Provenance system implemented
- 🚧 Complete Docling integration
- 🚧 Expand corpus to 10-20 PIDs

### Q2 2026
- Implement drift analysis algorithms
- Generate embeddings for full corpus
- Export first training dataset
- Begin Granite fine-tuning experiments

### Q3 2026
- Semantic search interface
- Temporal visualization dashboard
- First draft of methodology chapter
- Mid-year supervisor review

### Q4 2026
- Comparative analysis across time periods
- Validate findings against manual close reading
- Conference paper submission
- Year 1 report

---

## 10. Technical Debt & Risks

### 10.1 Known Issues

1. **Docling Placeholder**: Current implementation has TODOs - need real PDF/TIFF extraction
2. **TIFF Metadata**: GraphQL response missing `tiff_files` array for one PID
3. **Scalability Testing**: pgvector performance untested at 50K+ chunks
4. **Backup Strategy**: Automated backups configured but not stress-tested

### 10.2 Mitigation Strategies

- **Docling**: Priority #1 for next sprint (Week 1-2)
- **GraphQL**: Contact archive maintainers to add TIFF metadata
- **Scalability**: Benchmark IVFFlat indexes with synthetic data before corpus expansion
- **Backups**: Run restore test on non-production database

---

## 11. Conclusion

The current architecture provides a **solid foundation for academically rigorous ML research**:

✅ **Quality Control**: PID-gated ingestion prevents data contamination  
✅ **Provenance**: Full lineage tracking for XAI and peer review  
✅ **Text-Focused**: BERT embeddings for semantic analysis (not CLIP)  
✅ **Reproducibility**: Corpus snapshots enable exact experiment replication  

**Next Milestone**: Complete Docling integration → Enable full corpus ingestion → Generate first training dataset

**Supervisor Input Needed**:
1. Corpus size target (50 vs. 100 PIDs)?
2. Temporal granularity for drift analysis?
3. Preferred drift metrics (semantic distance vs. topic modeling)?
4. Budget approval for compute resources?

---

**Document Version**: 1.0  
**Last Updated**: January 18, 2026  
**Contact**: graham@example.edu  
**Repository**: https://github.com/graham/phd-practice (private)
