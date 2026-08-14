# PhD Research Methods - Implementation Roadmap

## Core Infrastructure ✅ COMPLETE
- [x] React frontend with IBM Carbon Design System
- [x] FastAPI backend with structured logging
- [x] Docker containerization
- [x] Development and production scripts
- [x] Database schema (PostgreSQL + pgvector)
- [x] Session logging for cybernetic documentation

## Critical Missing Integrations

### 1. Granite Model Integration (PRIORITY 1)
**What**: Load and run IBM Granite-4.0-H-Small-Instruct model

**Implementation needed**:
```python
# backend/app/services/granite_service.py
- Load model from HuggingFace
- Initialize tokenizer
- Create inference pipeline
- Implement prompt templates for testamentary traces analysis
- Add streaming support for real-time responses
```

**Files to create**:
- `backend/app/services/granite_service.py` - Model loading and inference
- `backend/app/services/prompts.py` - Prompt templates for analysis
- `backend/app/models/granite_models.py` - Pydantic models for I/O

### 2. Vector Database Integration (PRIORITY 1)
**What**: pgvector for document chunk retrieval

**Implementation needed**:
```python
# backend/app/services/vector_db.py
- Connect to PostgreSQL with pgvector
- Embedding generation (sentence-transformers)
- Similarity search functions
- Chunk storage and retrieval
- Metadata filtering
```

**Files to create**:
- `backend/app/services/vector_db.py` - Vector operations
- `backend/app/services/embeddings.py` - Embedding generation
- `backend/app/db/database.py` - DB connection pool

### 3. Document Processing Pipeline (PRIORITY 2)
**What**: Granite-Docling for PDF/image processing

**Implementation needed**:
```python
# backend/app/services/document_processor.py
- PDF text extraction with layout preservation
- Image OCR for scanned documents  
- Table extraction from papers
- Chunking strategy (semantic vs. fixed-size)
- Metadata extraction (title, authors, year)
```

**Files to create**:
- `backend/app/services/document_processor.py` - Main processor
- `backend/app/services/chunking.py` - Chunking strategies
- `backend/app/api/routes/documents.py` - Upload/process endpoints

### 4. S3 Storage Integration (PRIORITY 2)
**What**: Store original PDFs, processed chunks, logs

**Implementation needed**:
```python
# backend/app/services/s3_storage.py
- Upload PDFs and images
- Download for processing
- Store processed outputs
- Organize by date/experiment
```

**Files to create**:
- `backend/app/services/s3_storage.py` - S3 operations

### 5. Fine-tuning Infrastructure (PRIORITY 3)
**What**: Generate training data and track experiments

**Implementation needed**:
```python
# notebooks/01_training_data_generation.ipynb
- Create testamentary traces examples
- Prompt engineering for annotation
- Quality control workflow

# backend/app/services/experiment_tracker.py
- Log hyperparameters
- Track loss/metrics
- Save checkpoints
- Compare runs
```

**Files to create**:
- `notebooks/01_training_data_generation.ipynb`
- `notebooks/02_fine_tuning.ipynb`
- `backend/app/services/experiment_tracker.py`

## Quick Wins (Can Implement Immediately)

### A. Database Connection Layer
```python
# backend/app/db/database.py
```
- SQLAlchemy setup
- Connection pooling
- Session management

### B. API Client for Frontend
```javascript
// frontend/src/services/api.js
```
- Axios wrapper
- Error handling
- Authentication (if needed later)

### C. Environment Validation
```python
# backend/app/core/startup.py
```
- Check model availability
- Verify DB connection
- Validate S3 credentials

## Recommended Implementation Order

**Week 1: Core Data Flow**
1. Database connection setup
2. Basic vector database operations
3. Connect Granite model (inference only)
4. Wire up Evidence Tracer frontend → backend

**Week 2: Document Processing**
5. Implement document upload endpoint
6. Basic PDF text extraction
7. Chunk and embed pipeline
8. Test with 5-10 sample PDFs

**Week 3: Full Integration**
9. S3 storage for documents
10. Session logging to database
11. Experiment tracking basics
12. End-to-end test with real queries

**Week 4: Fine-tuning Prep**
13. Jupyter notebook setup
14. Training data generation workflow
15. First fine-tuning experiment
16. Document in Experimental Log page

## PhD Methodology Specifics

### Research Documentation Needs
- [ ] Notebook template for experiment documentation
- [ ] Prompt templates that embody your theoretical framework
- [ ] Evaluation rubric for "testamentary traces" detection quality
- [ ] Citation extraction from retrieved chunks
- [ ] Temporal metadata tracking (publication year)

### Cybernetic Loop Documentation
- [ ] Extend session logging to capture your interpretive notes
- [ ] Add "researcher reflection" field to sessions
- [ ] Build timeline view of how your understanding evolved
- [ ] Export sessions for thesis inclusion

## Next Immediate Steps

1. **Install Granite dependencies**:
   ```bash
   pip install transformers torch accelerate
   ```

2. **Create basic model service**:
   ```python
   # Test if model loads
   from transformers import AutoModelForCausalLM, AutoTokenizer
   model = AutoModelForCausalLM.from_pretrained("ibm-granite/granite-4.0-h-small-instruct")
   ```

3. **Set up vector DB connection**:
   ```python
   # Test pgvector connection
   from sqlalchemy import create_engine
   from pgvector.sqlalchemy import Vector
   ```

4. **Wire first real query**:
   - Frontend sends query
   - Backend retrieves from vector DB
   - Granite generates response
   - Log full trace

Would you like me to implement any of these specific components now?
