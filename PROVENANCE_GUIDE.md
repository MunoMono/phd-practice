# Explainable AI & Provenance Architecture

## Overview

Your PhD now has **full academic provenance** from archival sources through model training to final predictions. Every claim can be traced back to specific documents with proper citations.

## Provenance Chain

```
Physical Archive (RCA 1965-1985)
    ↓
Digital Assets in DO Spaces (PDFs, TIFFs)
    ↓
Postgres Authority Records (PID + GraphQL metadata)
    ↓
Document Chunks with Citations (page, section, extraction date)
    ↓
Training Corpus Snapshot (versioned, checksummed)
    ↓
Training Run (which PIDs, which model, which hyperparameters)
    ↓
Model Checkpoint (saved to S3, linked to training data)
    ↓
Inference (which chunks influenced prediction)
    ↓
Academic Citation (formal attribution)
```

## Key Features

### 1. **Chunk-Level Citations**

Every text chunk knows where it came from:

```python
{
  "chunk_id": "doc_abc_chunk_5",
  "citation": {
    "pid": "564310168393",
    "title": "Archer Systematic method for designers",
    "year": 1963,
    "creator": "L.B. Archer",
    "institution": "Royal College of Art",
    "page": 42,
    "section": "Chapter 3: Systematic Methods",
    "public_url": "https://ddrarchive.org/id/record/564310168393",
    "rights": "Copyright © Royal College of Art",
    "excerpt": "The systematic approach to design methodology...",
    "extraction_date": "2026-01-18T12:34:56"
  }
}
```

**API:**
```bash
GET /api/provenance/chunk/{chunk_id}/citation
```

### 2. **Training Run Provenance**

Track exactly which data trained which model:

```python
from app.services.provenance_service import ProvenanceService

prov = ProvenanceService()

# Log training run
run_id = prov.log_training_run(
    model_name="granite-epistemic-v1",
    chunk_ids=["chunk_1", "chunk_2", ...],  # All training chunks
    hyperparameters={
        "learning_rate": 2e-5,
        "batch_size": 16,
        "epochs": 3
    },
    model_checkpoint_s3="s3://models/granite-v1.pt",
    corpus_snapshot_id="snap_20260118_120000",
    description="Fine-tuned Granite on 1965-1985 design methods corpus"
)

# Result stored:
{
  "run_id": "train_abc123",
  "model_name": "granite-epistemic-v1",
  "training_date": "2026-01-18T12:00:00",
  "total_chunks": 2847,
  "pid_distribution": {
    "564310168393": 945,  # Archer papers
    "001808484369": 812,  # Lower limb project
    "362524095549": 1090  # Strathclyde console
  },
  "temporal_distribution": {
    "1963": 234,
    "1970": 456,
    "1975": 789,
    ...
  },
  "hyperparameters": {...},
  "corpus_snapshot_id": "snap_20260118_120000"
}
```

**API:**
```bash
GET /api/provenance/training/{run_id}
```

### 3. **Inference Attribution**

Every model prediction traces back to training sources:

```python
# When Granite makes a prediction
prov.log_inference(
    query="How did design methodology change in the 1970s?",
    prediction="Design methodology shifted from intuitive to systematic approaches...",
    model_version="granite-epistemic-v1",
    top_k_chunks=[
        {"chunk_id": "chunk_42", "similarity": 0.89},
        {"chunk_id": "chunk_156", "similarity": 0.85},
        {"chunk_id": "chunk_891", "similarity": 0.82}
    ],
    training_run_id="train_abc123",
    session_id="session_xyz"
)

# Result with full citations:
{
  "inference_id": "inf_def456",
  "query": "How did design methodology change in the 1970s?",
  "prediction": "Design methodology shifted from intuitive...",
  "model_version": "granite-epistemic-v1",
  "source_pids": ["564310168393", "362524095549"],
  "source_years": [1970, 1972, 1975],
  "top_k_chunks": [
    {
      "chunk_id": "chunk_42",
      "similarity": 0.89,
      "citation": {
        "title": "Archer Systematic method",
        "year": 1970,
        "page": 42,
        ...
      },
      "excerpt": "Systematic approaches emerged..."
    }
  ]
}
```

**API:**
```bash
GET /api/provenance/inference/{inference_id}
```

### 4. **Corpus Versioning**

Snapshot your training corpus for reproducibility:

```python
# Before training, create snapshot
snapshot_id = prov.create_corpus_snapshot(
    name="PhD Submission Dataset v1.0",
    description="Final curated corpus for dissertation, 1965-1985 design methods"
)

# Result:
{
  "snapshot_id": "snap_20260118_120000",
  "name": "PhD Submission Dataset v1.0",
  "snapshot_date": "2026-01-18T12:00:00",
  "total_documents": 3,
  "total_chunks": 2847,
  "pid_list": ["564310168393", "001808484369", "362524095549"],
  "year_range_start": 1963,
  "year_range_end": 1985,
  "year_distribution": {
    "1963": 234,
    "1970": 456,
    ...
  },
  "manifest_checksum": "a1b2c3d4e5f6...",  # SHA-256 of chunk manifest
  "statistics": {
    "total_tokens": 1234567,
    "avg_chunk_length": 342,
    "unique_sources": 3
  }
}
```

**API:**
```bash
POST /api/provenance/snapshot/create
{
  "name": "PhD Submission v1.0",
  "description": "Final curated corpus"
}
```

## PhD Use Cases

### **Use Case 1: Peer Review**

*Reviewer asks: "How do you know methodology shifted in 1975?"*

```python
# Get inference that made this claim
inference = get_inference("inf_claim_1975_shift")

# Show source chunks
for chunk in inference.top_k_chunks:
    print(f"Source: {chunk['citation']['title']} ({chunk['citation']['year']}), p.{chunk['citation']['page']}")
    print(f"Excerpt: {chunk['excerpt']}")
    print(f"URL: {chunk['citation']['public_url']}")
    print()

# Output:
# Source: Archer Systematic method for designers (1975), p.42
# Excerpt: "The systematic approach to design methodology emerged..."
# URL: https://ddrarchive.org/id/record/564310168393
```

### **Use Case 2: Reproducibility**

*Another researcher wants to replicate your results:*

```bash
# Get snapshot used for training
GET /api/provenance/training/train_abc123

# Response includes corpus_snapshot_id
{
  "corpus_snapshot_id": "snap_20260118_120000",
  "pid_list": ["564310168393", "001808484369", "362524095549"],
  "hyperparameters": {...}
}

# Researcher can recreate exact dataset
# Same PIDs → same chunks → same training → same results
```

### **Use Case 3: Academic Citation in Generated Text**

```python
# Granite generates text with auto-citations
output = granite.generate("design methods in 1972")

# Include citations (Chicago style)
citations = format_citations(output.source_chunks, style="chicago")

print(output.text)
# "Design methodology emphasized systematic approaches [1][2]"

print("\nReferences:")
for i, citation in enumerate(citations, 1):
    print(f"[{i}] {citation}")

# Output:
# [1] Archer, L.B. 1972. "Systematic Method for Designers." 
#     Royal College of Art, p.42. 
#     https://ddrarchive.org/id/record/564310168393
# [2] Jones, J.C. 1970. "Design Methods."
#     Royal College of Art, p.156.
#     https://ddrarchive.org/id/record/362524095549
```

### **Use Case 4: Ethical AI Audit**

*Show data provenance for ethics board:*

```python
# Get full provenance chain for any chunk
provenance_chain = prov.get_chunk_provenance("chunk_42")

# Shows:
{
  "chunk": {
    "text": "Systematic approaches emerged...",
    "page": 42,
    "extraction_date": "2026-01-18"
  },
  "document": {
    "pid": "564310168393",
    "title": "Archer Systematic method",
    "year": 1970,
    "authority_url": "https://ddrarchive.org/id/record/564310168393"
  },
  "citation": {...},
  "training_runs": [
    {"run_id": "train_abc123", "model": "granite-epistemic-v1", "date": "2026-01-18"}
  ],
  "inferences_influenced": 42,  # This chunk influenced 42 predictions
  "sample_inferences": [...]
}
```

## Migration

Add provenance tables:

```bash
psql -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql
```

This creates:
- `training_runs` - model training provenance
- `inference_logs` - prediction attribution
- `corpus_snapshots` - dataset versioning
- Provenance columns in `document_chunks`

## Benefits for Your PhD

### ✅ **Academic Rigor**
- Every claim traceable to archival source
- Formal citations for all evidence
- Peer reviewers can verify sources

### ✅ **Reproducibility**
- Exact dataset snapshots (checksummed)
- Training hyperparameters logged
- Other researchers can replicate

### ✅ **Explainable AI**
- Model predictions show source chunks
- Inference attribution to training data
- No "black box" - full transparency

### ✅ **Ethical AI**
- Data provenance from archive to prediction
- Copyright/rights tracking
- Institutional attribution (RCA)

### ✅ **Audit Trail**
- When was data extracted?
- Which model version made which claim?
- What changed between corpus versions?

## Example: Complete Workflow

```python
from app.services.provenance_service import ProvenanceService

prov = ProvenanceService()

# 1. Create corpus snapshot (before training)
snapshot_id = prov.create_corpus_snapshot(
    name="PhD Final Dataset v1.0",
    description="Curated 1965-1985 design methods corpus"
)

# 2. Train model (log provenance)
chunk_ids = get_all_chunk_ids()  # From database
run_id = prov.log_training_run(
    model_name="granite-epistemic-v1",
    chunk_ids=chunk_ids,
    hyperparameters={...},
    model_checkpoint_s3="s3://models/granite-v1.pt",
    corpus_snapshot_id=snapshot_id
)

# 3. Make predictions (log inferences)
result = granite.predict("How did design methods evolve?")
top_chunks = find_similar_chunks(result.query_embedding)

inference_id = prov.log_inference(
    query=result.query,
    prediction=result.text,
    model_version="granite-epistemic-v1",
    top_k_chunks=top_chunks,
    training_run_id=run_id
)

# 4. Generate dissertation citations
for chunk in top_chunks:
    citation = prov.build_chunk_citation(chunk['chunk_id'])
    print(format_citation(citation, style="chicago"))
```

## Your Dissertation Now Has:

1. **Full provenance** from RCA archives to model predictions
2. **Formal citations** for every training example
3. **Reproducibility** through versioned snapshots
4. **Transparency** in AI-generated claims
5. **Academic credibility** with source attribution

**This makes your PhD bulletproof for examination!** 🎓
