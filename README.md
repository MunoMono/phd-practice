# Testamentary Traces Research Platform

**🌐 [View Live Site](https://munomono.github.io/phd-practice/)**

**Source of truth & deploy:**
- Code lives in `git@github.com:MunoMono/phd-practice.git` (no GitHub Actions).
- Work locally on any machine, push to GitHub, and deploy directly from your machine to the droplet via the deploy scripts; GitHub does not touch the droplet.

A cybernetic research platform for analyzing testamentary traces in academic literature using human-AI collaboration with IBM's Granite LLM.

## Architecture

This project implements a three-layer architecture for second-order cybernetic research:

### Presentation Layer - Research Interface
**Standalone React App** with IBM Carbon Design System
- **Technology**: React 18 + Vite, IBM Carbon 11/12, D3.js
- **Components**:
  - Research Dashboard with temporal drift visualizations
  - Evidence Tracer: Interactive D3.js force-directed graphs showing reasoning paths
  - Session Recorder: Complete audit trail of human-AI interactions
  - Experimental Log: Training metrics and model performance tracking

### Logic Layer - The Cybernetic Brain
**FastAPI Backend** with Granite LLM Agent
- **Technology**: FastAPI, Python 3.11+
- **Components**:
  - Granite-4.0-H-Small-Instruct (32B/9B MoE) for analytical reasoning
  - Tools for retrieval, analysis, and structured logging
  - Agentic workflows with function calling
  - Comprehensive session logging for methodological transparency

### Data Layer - Research Foundation
**Vector Database & S3 Storage**
- **PostgreSQL with pgvector**: Document and image embeddings
- **S3-Compatible Storage**: PDFs, TIFFs, JPG derivatives, logs
- **Training Data**: Fine-tuning examples and model weights

## Theoretical Framework

This project sits at the convergence of three academic fields:

1. **Second-Order Cybernetics & Epistemology** (Heinz von Foerster)
   - The observer (researcher) is part of the system being studied
   - Transactional causality between human and AI agent
   - Reflexive methodology where the tool itself is an object of study

2. **Studies of Epistemic & Academic Drift**
   - Analysis of how research priorities and knowledge criteria shift over time
   - Applied to document analysis using AI collaboration
   - Framework: "Epistemic Densa Drift" in LLMs (Nov 2025 working paper)

3. **Human-AI Collaboration & Critical AI Studies**
   - Epistemology of working with AI
   - Dialectical, iterative analysis as knowledge co-creation
   - Documentation of cybernetic loops

## Installation

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create logs directory
mkdir -p logs/sessions

# Run the server
python -m app.main
```

The API will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### Environment Configuration

Create a `.env` file in the `backend` directory:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=testamentary-traces

# Granite Model
GRANITE_MODEL_PATH=ibm-granite/granite-4.0-h-small-instruct
GRANITE_DEVICE=cuda  # or cpu

# S3 Storage
S3_BUCKET=testamentary-traces-research
S3_ENDPOINT=your_s3_endpoint
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
```

## IBM Carbon Design Compliance

This project adheres to IBM Carbon Design System guidelines:

- **Typography**: IBM Plex Sans, IBM Plex Mono
- **Color Tokens**: g100 theme (dark mode optimized for research)
- **Spacing**: Carbon spacing scale ($spacing-03, $spacing-05, etc.)
- **Grid System**: 16-column responsive grid
- **Components**: All UI components from @carbon/react
- **SCSS Mixins**: Full use of Carbon tokens, mixins, and utilities

## Key Features

### 1. Evidence Tracer
Interactive D3.js visualization showing how the Granite agent constructs reasoning:
- Query → Retrieved Document Chunks → Agent Response
- Force-directed graph with weighted edges (relevance scores)
- Click to inspect source documents and reasoning steps

### 2. Session Recorder
Complete audit trail for methodological transparency:
- Every query, retrieval, and response logged to JSON
- Structured logging for cybernetic research documentation
- Queryable session history with full context

### 3. Experimental Log
Integration with Python notebooks for training documentation:
- Training loss curves (D3.js line charts)
- Hyperparameter tracking
- Qualitative evaluations of model performance
- Carbon-styled charts for thesis inclusion

### 4. Temporal Drift Analysis
Multi-line charts showing evolution of key terms over time:
- Normalized frequency of rival theoretical frameworks
- Citation network evolution
- Agent confidence over successive fine-tuning runs

## Development Workflow

### Normal Daily Workflow

```bash
git checkout main
git pull origin main
./pull-from-production.sh --yes
```

Rules for the daily refresh flow:

- Git is the source of truth for code.
- Production is the source of truth for runtime data.
- Normal mode starts the code-driven local Docker Compose stack.
- Offline or image-only workflows are fallback-only and must stay explicit.
- Do not start development unless the command ends with `READY FOR DEVELOPMENT`.

### Turin Development Preflight

```bash
./scripts/turin-dev-start.sh
```

Expected result: `TURIN DEVELOPMENT ENVIRONMENT: READY`.

### Frontend Development
```bash
cd frontend
npm run dev      # Development server with hot reload
npm run build    # Production build
npm run preview  # Preview production build
```

### Backend Development
```bash
cd backend
# With auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the main script
python -m app.main
```

## Project Structure

```
phd-practice/
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header/
│   │   │   └── visualizations/
│   │   │       ├── TemporalDriftChart.jsx
│   │   │       ├── EvidenceGraph.jsx
│   │   │       └── TrainingMetricsChart.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard/
│   │   │   ├── EvidenceTracer/
│   │   │   ├── SessionRecorder/
│   │   │   └── ExperimentalLog/
│   │   ├── App.jsx
│   │   └── index.scss
│   ├── package.json
│   └── vite.config.js
│
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── agent.py         # Granite agent queries
│   │   │       ├── sessions.py      # Session logging
│   │   │       └── experiments.py   # Training tracking
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   └── main.py
│   └── requirements.txt
│
└── README.md
```

## Next Steps

### Immediate TODOs
1. **Vector Database Integration**: Implement pgvector for document embeddings
2. **Granite Model Loading**: Set up Hugging Face integration for model inference
3. **Document Processing**: Integrate Granite-Docling for PDF/image processing
4. **Fine-tuning Pipeline**: Create training data generation workflow
5. **S3 Storage**: Connect to S3-compatible storage for document repository

### PhD Methodology Integration
1. Create Jupyter notebooks for experimental logs
2. Document baseline testamentary traces hypothesis
3. Build first synthetic training examples
4. Validate document processing pipeline with sample PDFs
5. Design evaluation metrics for agent performance

## Research Context

This platform enables a novel methodological approach to studying testamentary traces:

- **Input**: 500 PDFs + 300 images (~1000 pages of academic literature)
- **Process**: Human-researcher + Granite agent collaborative analysis
- **Output**: Documented cybernetic research process + findings on testamentary traces
- **Contribution**: Both the findings AND the methodology are research contributions

## License

[Specify License]

## Citations & References

- von Foerster, H. (1979). *Cybernetics of Cybernetics*
- "Historical Perspectives on Epistemic and Academic Drift" (2013)
- "The Lattice Case Study: An Analogic Framework for Diagnosing Epistemic Densa Drift in Large Language Models" (Nov 2025 working paper)
- IBM Granite Models: https://github.com/ibm-granite

## Contact

[Your contact information]

---

**Note**: This is a research project for PhD methodology development. The system is designed for transparency, auditability, and methodological rigor in human-AI collaboration.
