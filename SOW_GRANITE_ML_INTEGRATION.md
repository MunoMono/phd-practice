# Statement of Work: Granite ML Model Integration for Epistemic Drift Analysis

**Project Title:** Multimodal Document Processing and Granite LLM Integration for PhD Research  
**Principal Investigator:** Graham Newman, RCA PhD Candidate  
**Project Period:** January 2026 - March 2026 (Q1 2026)  
**Status:** Beta Proof of Concept  
**Document Version:** 1.0  
**Date:** 21 January 2026

---

## 1. Executive Summary

This Statement of Work defines the scope, deliverables, and implementation approach for integrating IBM Granite language model capabilities into the existing Epistemic Drift Research Platform. The project will establish a complete pipeline from raw archival documents (PDF/TIFF) through automated processing, vector embedding generation, semantic analysis, and culminate in user acceptance testing of the Granite-powered analytical interface.

**Core Objective:** Enable automated semantic analysis of design methods literature (1965-1985) using IBM Granite LLM, with full provenance tracking and explainable AI outputs suitable for doctoral research standards.

**Key Deliverable:** Production-ready system capable of processing curated archival materials, generating embeddings, and providing traceable analytical insights through human-AI collaboration.

---

## 2. Project Scope

### 2.1 In Scope

**Infrastructure & Data Pipeline:**
- Complete Docling integration for PDF text extraction and TIFF OCR processing
- Automated document chunking with semantic boundaries
- Vector embedding generation using sentence-transformers (384-dimensional)
- PostgreSQL pgvector storage with IVFFlat indexing
- S3 sync service for master file retrieval from DigitalOcean Spaces

**Granite Model Integration:**
- IBM Granite-4.0-H-Small-Instruct model deployment
- Inference pipeline for epistemic drift analysis
- Prompt engineering for domain-specific analytical tasks
- Citation generation linking AI outputs to source documents
- Session logging for cybernetic research methodology

**User Interface & Testing:**
- React-based research dashboard with IBM Carbon Design System
- Evidence Tracer visualization (D3.js force-directed graphs)
- Session Recorder for complete audit trails
- User acceptance testing with representative research queries
- Performance benchmarking and accuracy validation

**Quality Assurance:**
- PID-gated ingestion (only curated archival materials)
- Full provenance tracking (chunk → embedding → inference → citation)
- Corpus versioning with SHA-256 checksums
- Reproducibility validation for academic rigor

### 2.2 Out of Scope

- Multi-modal vision analysis (CLIP-based image understanding)
- Real-time collaborative editing features
- Public API for third-party integrations
- Mobile application development
- Automated curation/acquisition of new archival materials
- Fine-tuning Granite model (deferred to Q2 2026)

### 2.3 Assumptions

- DDR Archive GraphQL API remains accessible with current schema
- DigitalOcean Spaces contains 3 initial PIDs for testing, scaling to 50-100 PIDs
- TIFF metadata will be added to GraphQL responses during implementation phase
- Sufficient computational resources available on deployment infrastructure
- Researcher (Graham) available for domain expertise and validation testing

---

## 3. Technical Architecture Decisions

### 3.1 Deployment Strategy: Local vs Cloud Granite

**Critical Decision:** Where to run IBM Granite model inference?

#### Option A: Watson X Cloud (IBM SaaS)

**Pros:**
- Zero infrastructure management
- Automatic scaling for concurrent requests
- Latest model versions maintained by IBM
- No GPU hardware requirements locally
- Enterprise-grade uptime and support

**Cons:**
- **Recurring API costs**: Pay-per-token pricing (~$0.50-2.00 per million tokens)
- **Budget risk for PhD**: Unpredictable monthly costs during experimentation phase
- Network latency for every inference call
- Dependency on external service availability
- Data privacy considerations (sending corpus to external API)

**Estimated Monthly Cost:** $50-200 for 10-50K queries (highly variable based on usage)

#### Option B: Local Deployment on DigitalOcean Droplet

**Pros:**
- **Fixed cost**: Droplet upgrade is predictable monthly expense
- No per-query fees - unlimited inference at no additional cost
- Full data sovereignty (corpus stays on your infrastructure)
- Faster inference (no network round-trip)
- Better for iterative experimentation and debugging

**Cons:**
- Requires GPU-capable droplet or CPU-based inference (slower)
- Model management and updates are your responsibility
- Initial setup complexity for model loading/caching
- Potential memory constraints with Granite-4.0-H-Small (32B/9B MoE)

**Estimated Monthly Cost:** $48-96 (droplet upgrade from current to 16GB-32GB RAM instance)

#### **RECOMMENDATION: Local Deployment (Option B)**

**Rationale for PhD Budget:**

For a beta proof-of-concept and PhD research budget, **local deployment on the DigitalOcean droplet is strongly recommended** for the following reasons:

1. **Cost Predictability:** PhD research requires fixed budgeting. A $48/month droplet upgrade is far more manageable than variable API costs that could spike during intensive experimentation phases.

2. **Unlimited Experimentation:** You'll be iterating on prompts, testing different analytical approaches, and debugging - activities that generate thousands of queries. Local deployment removes financial friction from experimentation.

3. **Academic Data Control:** Your corpus contains curated archival materials. Keeping all processing local ensures institutional compliance and avoids third-party data agreements.

4. **Acceptable Performance Trade-off:** For batch analysis of 50-100 documents, CPU-based inference (10-30 seconds per query) is acceptable. This is research, not production user-facing service.

5. **Model Quantization Options:** Use `transformers` with 8-bit or 4-bit quantization (bitsandbytes) to run Granite-4.0-H-Small on 16GB RAM with minimal accuracy loss.

6. **Cloud Migration Path:** If research scales or requires real-time interfaces for thesis defense demos, you can migrate to Watson X in Q2-Q3 2026 when needs are clearer.

**Implementation Approach:**
- Start with Granite 7B model (smaller variant) for proof-of-concept
- Use CPU inference with `torch` optimizations
- Implement model caching (HuggingFace cache already configured in docker-compose)
- Evaluate performance; upgrade to GPU droplet only if batch processing exceeds acceptable thresholds (e.g., >5 minutes per document)

**Droplet Specification Recommendation:**
- **Current:** Basic droplet (likely 2GB-4GB RAM)
- **Upgrade to:** 16GB RAM / 4 vCPU droplet ($48/month) or 32GB RAM / 8 vCPU ($96/month)
- **GPU option (if needed):** $300-600/month (defer unless CPU proves insufficient)

---

## 4. Implementation Roadmap (Agile Sprints)

### Sprint 0: Pre-Implementation Setup (Week 1: Jan 21-27)

**Objective:** Validate infrastructure readiness and finalize technical specifications

**Tasks:**
1. Audit current Digital Ocean droplet resources (CPU, RAM, storage)
2. Benchmark existing PostgreSQL pgvector performance with synthetic data
3. Verify S3 bucket connectivity and PID-linked file availability
4. Review GraphQL API response schema for 3 test PIDs
5. Document current docker-compose configuration and dependencies

**Deliverables:**
- Infrastructure audit report with resource allocation plan
- Confirmed droplet upgrade specification (if required)
- Validated S3 file inventory for initial corpus

**Acceptance Criteria:**
- Database connection tests pass for all services
- S3 sync service successfully retrieves test files
- GraphQL API returns valid responses for 3 PIDs

---

### Sprint 1: Document Processing Pipeline (Week 2-3: Jan 28 - Feb 10)

**Objective:** Complete PDF/TIFF ingestion with text extraction and chunking

**Tasks:**

**Story 1.1: Docling Integration** (5 points)
- Remove placeholder TODOs in `backend/app/services/docling_processor.py`
- Implement PDF text extraction with layout preservation
- Configure OCR pipeline for TIFF processing (PID 001808484369)
- Handle edge cases: scanned PDFs, mixed text/image pages
- Unit tests for extraction accuracy

**Story 1.2: Semantic Chunking** (3 points)
- Implement paragraph-based chunking (preserve semantic boundaries)
- Configure chunk size: 256-512 tokens with 50-token overlap
- Extract metadata: page number, section headings, document position
- Store chunks in `document_chunks` table with PID lineage

**Story 1.3: PID Validation Pipeline** (3 points)
- Integrate `authority_service.py` validation in document upload route
- Test triple-gated filtering: GraphQL sync, S3 sync, manual upload
- Verify rejection of non-PID materials
- End-to-end test: Upload PDF → validate PID → extract chunks → store

**Deliverables:**
- Functional Docling service processing PDFs and TIFFs
- Database populated with chunks from 3 test PIDs
- Automated test suite for ingestion pipeline

**Acceptance Criteria:**
- Successfully process 2 PDFs and 1 TIFF collection
- Generate 200-500 chunks across 3 documents
- 100% PID validation accuracy (no false positives in database)
- OCR accuracy >90% for TIFF lecture slides

---

### Sprint 2: Embedding Generation & Vector Storage (Week 4: Feb 11-17)

**Objective:** Transform text chunks into searchable vector embeddings

**Tasks:**

**Story 2.1: Embedding Service Setup** (3 points)
- Initialize `sentence-transformers/all-MiniLM-L6-v2` model
- Implement batch embedding generation (chunks → 384-dim vectors)
- Configure model caching in docker volume (`model_cache:/root/.cache/huggingface`)
- Optimize batch size for memory constraints

**Story 2.2: pgvector Integration** (5 points)
- Create vector column in `document_chunks` table: `embedding VECTOR(384)`
- Build IVFFlat index for cosine similarity search
- Implement similarity query functions (top-k retrieval)
- Benchmark query performance: 100ms target for 10K vectors

**Story 2.3: Corpus Processing** (2 points)
- Generate embeddings for all chunks from Sprint 1
- Verify embedding quality with sample similarity searches
- Create corpus snapshot with SHA-256 checksum

**Deliverables:**
- Embedding service integrated into document processing pipeline
- Indexed vector database with 200-500 embeddings
- Performance benchmark report

**Acceptance Criteria:**
- All chunks have valid 384-dimensional embeddings
- Similarity search returns relevant results (<100ms)
- Embeddings reproducible from same source chunks

---

### Sprint 3: Granite Model Deployment (Week 5-6: Feb 18 - Mar 3)

**Objective:** Deploy and configure IBM Granite for inference

**Tasks:**

**Story 3.1: Model Selection & Quantization** (3 points)
- Download Granite-4.0-H-Small-Instruct (or 7B variant for testing)
- Implement 8-bit quantization using `bitsandbytes`
- Configure model loading in `backend/app/services/granite_service.py`
- Test inference latency on target hardware

**Story 3.2: Inference Pipeline** (5 points)
- Build prompt templates for epistemic drift analysis
- Implement context injection (retrieved chunks → prompt)
- Create streaming response handler for real-time feedback
- Add error handling and timeout management

**Story 3.3: Provenance Integration** (3 points)
- Log all inference calls to `inference_logs` table
- Link predictions to source chunks (XAI attribution)
- Implement citation generation (chunk ID → formal citation)
- Test end-to-end: Query → retrieval → inference → cited response

**Deliverables:**
- Functional Granite inference service
- Prompt engineering templates for research queries
- Provenance system linking AI outputs to archival sources

**Acceptance Criteria:**
- Granite generates responses within 30 seconds per query (CPU acceptable)
- Every prediction traces back to specific PID and page number
- Citation format matches academic standards

---

### Sprint 4: API Integration & Backend Testing (Week 7: Mar 4-10)

**Objective:** Expose ML capabilities through FastAPI endpoints

**Tasks:**

**Story 4.1: API Endpoints** (5 points)
- `POST /api/analyze` - Submit research query, return Granite analysis
- `GET /api/search` - Semantic search across corpus
- `GET /api/provenance/inference/{id}` - Retrieve citation chain
- OpenAPI documentation updates

**Story 4.2: Session Management** (3 points)
- Implement session logging for cybernetic research tracking
- Store complete interaction history (queries + responses)
- Build session replay capability for methodology documentation

**Story 4.3: Integration Testing** (3 points)
- End-to-end tests: Upload document → query analysis → verify citation
- Load testing: 10 concurrent requests, measure response times
- Error scenario testing: Invalid PIDs, malformed queries, timeout handling

**Deliverables:**
- RESTful API with documented endpoints
- Comprehensive test suite (unit + integration)
- Session logging for all ML interactions

**Acceptance Criteria:**
- API returns valid JSON responses for all endpoints
- 95% test coverage for critical paths
- Session logs capture complete provenance chain

---

### Sprint 5: Frontend Integration (Week 8: Mar 11-17)

**Objective:** Build user-facing research interface

**Tasks:**

**Story 5.1: Evidence Tracer Updates** (5 points)
- Integrate Granite analysis into existing D3.js visualization
- Display reasoning paths: Query → Retrieved Chunks → Analysis
- Interactive citation links to source documents
- Real-time streaming response display

**Story 5.2: Session Recorder Enhancement** (3 points)
- Show complete audit trail of queries and AI responses
- Export session logs for methodology chapter
- Filter by date, PID, or research topic

**Story 5.3: Experimental Log** (2 points)
- Display corpus statistics (document count, chunk count, date range)
- Show model configuration (Granite version, quantization settings)
- Training metrics placeholder (for future fine-tuning)

**Deliverables:**
- Updated React frontend components
- Interactive research interface with Granite integration
- User documentation for research workflows

**Acceptance Criteria:**
- Users can submit queries and view AI analysis with citations
- Evidence graphs render reasoning paths correctly
- Session history persists across browser sessions

---

### Sprint 6: User Acceptance Testing (Week 9-10: Mar 18-31)

**Objective:** Validate system with real research use cases

**Tasks:**

**Story 6.1: Research Query Testing** (5 points)
- Prepare 20 representative research questions about epistemic drift
- Execute queries through frontend interface
- Manually validate AI outputs against source PDFs
- Measure accuracy: Do citations match claimed content?

**Story 6.2: Usability Testing** (3 points)
- Conduct think-aloud sessions with researcher (Graham)
- Test navigation flows: Dashboard → Query → Results → Citation
- Gather feedback on interface clarity and analytical utility
- Document pain points and enhancement requests

**Story 6.3: Performance Validation** (2 points)
- Benchmark end-to-end query latency (target: <60 seconds)
- Measure database query times under load
- Verify memory usage stays within droplet limits
- Stress test with 50 sequential queries

**Story 6.4: Academic Rigor Audit** (5 points)
- Validate provenance system: Can every claim be traced to source?
- Test reproducibility: Re-run analysis, verify identical results
- Check citation format compliance with academic standards
- Supervisor review session (if available)

**Deliverables:**
- UAT test plan with 20 research queries
- Performance benchmark report
- Academic validation documentation
- Prioritized backlog for enhancements

**Acceptance Criteria:**
- 90% of AI outputs are factually accurate when checked against sources
- 100% of outputs have valid citations to archival materials
- Query-to-response time <60 seconds for 95% of requests
- Researcher confirms system meets PhD research standards

---

## 5. Deliverables Summary

### Technical Deliverables

| Component | Description | Acceptance Test |
|-----------|-------------|-----------------|
| **Document Processor** | Docling-based PDF/TIFF extraction with chunking | Process 3 PIDs without errors |
| **Embedding Service** | Generate 384-dim vectors for all chunks | Similarity search returns relevant results |
| **Granite Service** | Local LLM inference with 8-bit quantization | Generate analysis in <60 seconds |
| **Provenance System** | Full XAI lineage tracking | Every output traces to PID + page |
| **REST API** | FastAPI endpoints for query, search, citation | OpenAPI docs complete, tests pass |
| **React Frontend** | Evidence Tracer, Session Recorder, Dashboard | User can submit query and view cited results |
| **Database Schema** | pgvector storage with IVFFlat indexes | 100K vectors searchable in <100ms |

### Documentation Deliverables

| Document | Purpose | Target Audience |
|----------|---------|-----------------|
| **API Reference** | OpenAPI specification for all endpoints | Developers, future integrators |
| **User Guide** | How to use research interface | Researcher (Graham), supervisors |
| **Methodology Chapter Draft** | Technical description for PhD thesis | Examiners, academic reviewers |
| **Provenance Audit Trail** | Sample session logs with citations | Peer reviewers, validation |
| **Performance Report** | Benchmarks, resource usage, limitations | Supervisors, infrastructure planning |

### Research Outputs

| Output | Description | Timeline |
|--------|-------------|----------|
| **Initial Corpus** | 3 PIDs processed and analyzed | End Sprint 2 (Feb 17) |
| **Sample Analysis** | 20 research queries with validated outputs | End Sprint 6 (Mar 31) |
| **Drift Metrics** | Preliminary semantic distance measurements | Q2 2026 (future work) |

---

## 6. Resource Requirements

### Infrastructure

**Current State:**
- Digital Ocean droplet: 104.248.170.26 (current specs unknown)
- PostgreSQL 14+ with pgvector
- S3-compatible storage (DigitalOcean Spaces)

**Required Upgrades:**

| Resource | Current | Required | Monthly Cost |
|----------|---------|----------|--------------|
| Droplet RAM | TBD | 16GB minimum, 32GB recommended | $48-96 |
| Storage | TBD | 50GB SSD (20GB for models + 30GB for data) | Included |
| Bandwidth | TBD | 3TB/month | Included |
| Spaces Storage | TBD | 100GB (50-100 PDFs/TIFFs) | ~$5 |

**Total Estimated Monthly Cost:** $53-101 (one-time upgrade, fixed thereafter)

### Software Dependencies

All required packages already specified in `backend/requirements.txt`:
- ✅ FastAPI, Uvicorn (API framework)
- ✅ Transformers, Torch (ML libraries)
- ✅ Sentence-transformers (embeddings)
- ✅ Docling 2.15.0 (document processing)
- ✅ pgvector, SQLAlchemy (database)
- ✅ boto3 (S3 integration)

**Additional Dependencies (to add):**
- `bitsandbytes` (for 8-bit quantization)
- `accelerate` (for model loading optimizations)

### Human Resources

**Researcher Time Commitment:**
- Sprint 0-4 (Backend): 5-10 hours/week for requirements clarification
- Sprint 5-6 (Frontend/UAT): 15-20 hours/week for testing and validation
- **Total:** ~60-80 hours over 10 weeks

**External Support (if needed):**
- DDR Archive maintainers: GraphQL schema updates for TIFF metadata
- RCA supervisors: Academic validation review sessions

---

## 7. Risk Management

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Granite model too large for droplet** | Medium | High | Start with 7B model; use quantization; CPU fallback acceptable |
| **Inference too slow for usability** | Medium | Medium | Batch processing acceptable for research; optimize prompts |
| **pgvector performance degrades at scale** | Low | Medium | Benchmark early (Sprint 2); IVFFlat indexes proven to 1M vectors |
| **TIFF OCR accuracy insufficient** | Low | Low | Manual validation for critical documents; flag low-confidence extractions |
| **S3 bandwidth costs exceed budget** | Low | Low | Cache frequently accessed files locally; optimize download patterns |

### Academic Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **AI outputs lack academic rigor** | Medium | High | Provenance system mandatory; manual validation of all claims |
| **Corpus size insufficient for analysis** | Low | Medium | Quality over quantity; 50 PIDs validated as adequate in literature |
| **Reproducibility fails in peer review** | Low | Critical | Corpus snapshots, SHA-256 checksums, version all dependencies |
| **Ethical concerns about AI attribution** | Low | Medium | Transparent methodology; AI as tool, not author; full disclosure |

### Budget Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Droplet upgrade exceeds PhD budget** | Low | Medium | $48/month is within typical student allowances; request supervisor funding if needed |
| **Unexpected API costs if using Watson X** | High (if cloud) | High | **Mitigated by local deployment decision** |
| **Storage costs grow with corpus expansion** | Low | Low | 100GB Spaces = $5/month; archive old experiments to local backup |

---

## 8. Success Criteria

### Minimum Viable Product (MVP) - End of Sprint 6

**Must Have:**
- ✅ Process 3 PIDs (2 PDFs, 1 TIFF) without errors
- ✅ Generate embeddings for all extracted chunks
- ✅ Granite model produces analytical outputs within 60 seconds
- ✅ Every AI response includes valid citations to source documents
- ✅ Frontend interface allows query submission and result visualization
- ✅ Provenance system traces all outputs to PIDs

**Should Have:**
- Similarity search returns top-5 relevant chunks in <1 second
- Session logs persist for methodology documentation
- API documentation complete and accurate
- Performance benchmarks documented

**Could Have:**
- Temporal drift metrics (deferred to Q2)
- Automated corpus expansion pipeline
- Advanced visualization options

### Academic Validation

**PhD Research Standards:**
- Supervisor confirms methodology meets doctoral examination requirements
- Manual validation of 20 sample outputs shows 90% accuracy
- Reproducibility test: Re-run analysis yields identical results
- Citation format complies with academic standards (APA/Chicago/MLA)

### User Acceptance

**Researcher Satisfaction:**
- Graham confirms system provides useful analytical insights
- Interface reduces manual literature review time by 30%
- Evidence graphs help identify conceptual connections
- System trustworthy enough to cite in thesis

---

## 9. Timeline & Milestones

```
Sprint 0: Setup              [Jan 21-27]  ██░░░░░░░░ 10%
Sprint 1: Document Pipeline  [Jan 28-Feb 10] ██░░░░░░░░ 20%
Sprint 2: Embeddings         [Feb 11-17]  ██░░░░░░░░ 30%
Sprint 3: Granite Deploy     [Feb 18-Mar 3] ██░░░░░░░░ 60%
Sprint 4: API Integration    [Mar 4-10]   ██░░░░░░░░ 75%
Sprint 5: Frontend           [Mar 11-17]  ██░░░░░░░░ 90%
Sprint 6: UAT                [Mar 18-31]  ██████████ 100%
```

**Key Milestones:**

| Date | Milestone | Deliverable |
|------|-----------|-------------|
| **Jan 27** | Sprint 0 Complete | Infrastructure ready, specs finalized |
| **Feb 10** | Documents Processed | 3 PIDs ingested with PID validation |
| **Feb 17** | Embeddings Generated | Vector search operational |
| **Mar 3** | Granite Live | AI inference producing cited outputs |
| **Mar 10** | API Ready | Backend integration tests passing |
| **Mar 17** | Frontend Complete | User interface functional |
| **Mar 31** | UAT Passed | System validated for research use |

---

## 10. Budget Summary

### One-Time Costs
- Droplet upgrade (if needed): $0 (billed monthly, not upfront)
- Development time: In-kind (PhD researcher labor)

### Recurring Monthly Costs

| Item | Cost (USD) | Notes |
|------|-----------|-------|
| **Digital Ocean Droplet** | $48-96 | 16GB-32GB RAM tier |
| **Spaces Storage** | $5 | 100GB for corpus + backups |
| **Bandwidth** | $0 | Included in droplet |
| **Domain/SSL** | $0 | Already configured |
| **Watson X API** | $0 | **Not using - local deployment** |
| **Total** | **$53-101** | **Fixed, predictable cost** |

### Annual Budget Projection (Q1-Q4 2026)

- **Q1 (Current SoW):** $53-101/month × 3 months = **$159-303**
- **Q2-Q4:** Same infrastructure supports fine-tuning and expanded corpus
- **Total Year 1:** ~**$636-1,212** (infrastructure only)

**PhD Budget Feasibility:** ✅ **Highly affordable**  
Most UK/EU PhD programs provide £1,000-3,000/year for research expenses. This infrastructure represents 25-50% of typical annual allowance, leaving budget for conference travel, books, and equipment.

**Cost Avoidance vs. Watson X Cloud:**  
Estimated savings: $600-2,400/year by avoiding per-token API fees

---

## 11. Governance & Communication

### Weekly Check-ins
- **Format:** Asynchronous updates via GitHub issues/project board
- **Cadence:** End of each sprint (Sundays)
- **Content:** Completed tasks, blockers, decisions needed

### Sprint Reviews
- **Format:** Demo + retrospective
- **Cadence:** Every 2 weeks
- **Attendees:** Graham (researcher), supervisor (optional)
- **Deliverables:** Working software demo, updated documentation

### Decision Log
All major technical decisions documented in:
- `IMPLEMENTATION_ROADMAP.md` (updated per sprint)
- GitHub commit messages with issue references
- Sprint retrospective notes

### Escalation Path
- **Technical blockers:** Document in GitHub issue, research solutions for 24 hours, then seek community/supervisor input
- **Budget overruns:** Notify supervisor immediately if costs exceed $100/month
- **Academic concerns:** Schedule supervisor meeting within 1 week

---

## 12. Acceptance & Sign-off

### Completion Criteria

This Statement of Work is considered **complete** when:

1. ✅ All Sprint 6 acceptance criteria met
2. ✅ UAT test plan executed with 90% pass rate
3. ✅ Supervisor review session conducted (if required by program)
4. ✅ Documentation deliverables submitted
5. ✅ System running in production on Digital Ocean droplet
6. ✅ Researcher (Graham) confirms readiness for Q2 corpus expansion

### Signoff

**Prepared by:**  
Graham Newman, PhD Candidate  
Date: 21 January 2026

**Approved by (if applicable):**  
PhD Supervisor Name: _______________________  
Date: _______________________

**Technical Review (optional):**  
Systems Administrator/DevOps: _______________________  
Date: _______________________

---

## 13. Appendices

### Appendix A: Glossary

- **PID:** Persistent Identifier - unique code linking research materials to archival records
- **Epistemic Drift:** Changes in knowledge assumptions and research priorities over time
- **Docling:** IBM's document processing library for PDF/TIFF extraction
- **pgvector:** PostgreSQL extension for vector similarity search
- **IVFFlat:** Indexing algorithm for approximate nearest neighbor search
- **Quantization:** Reducing model precision (32-bit → 8-bit) to save memory
- **XAI:** Explainable AI - making model predictions interpretable and traceable

### Appendix B: Reference Documents

- `README.md` - Project overview and installation guide
- `IMPLEMENTATION_ROADMAP.md` - Detailed technical plan
- `PID_ARCHITECTURE.md` - PID-gated ingestion design
- `PROVENANCE_GUIDE.md` - Lineage tracking specifications
- `TESTING_GUIDE.md` - QA procedures
- `DEPLOYMENT.md` - Production deployment procedures

### Appendix C: Technology Stack Summary

**Backend:**
- Python 3.11+, FastAPI 0.115.0, Uvicorn
- PostgreSQL 14+ with pgvector 0.3.5
- SQLAlchemy 2.0.36 (ORM)

**Machine Learning:**
- IBM Granite-4.0-H-Small-Instruct (or 7B variant)
- sentence-transformers/all-MiniLM-L6-v2 (embeddings)
- Transformers 4.46.2, PyTorch 2.0+
- Docling 2.15.0 (document processing)

**Frontend:**
- React 18, Vite (build tool)
- IBM Carbon Design System 11/12
- D3.js (visualizations)
- Auth0 (authentication)

**Infrastructure:**
- Docker + docker-compose
- nginx (reverse proxy)
- DigitalOcean Droplet + Spaces (S3)

### Appendix D: Contact Information

**Principal Investigator:**  
Graham Newman  
Email: [Your email]  
Institution: Royal College of Art (RCA)  
Project Site: https://innovationdesign.io

**Technical Support:**  
Repository: https://github.com/MunoMono/phd-practice  
Issue Tracker: GitHub Issues  
Documentation: In-repo markdown files

---

**End of Statement of Work**

*This document is a living specification and may be updated during implementation based on technical discoveries or changing requirements. All changes will be versioned and tracked in the project repository.*
