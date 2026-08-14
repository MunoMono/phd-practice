# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Option 1: Docker (Recommended)

**One-command setup:**

```bash
./docker-setup.sh setup
./docker-setup.sh start
```

Visit `http://localhost:3000` - Everything is ready!

**What you get:**
- Frontend at `http://localhost:3000`
- Backend API at `http://localhost:8000`
- PostgreSQL with pgvector at `localhost:5432`
- MinIO (S3) at `http://localhost:9001`

**Useful commands:**
```bash
./docker-setup.sh logs        # View all logs
./docker-setup.sh shell-be    # Backend shell
./docker-setup.sh shell-db    # Database shell
./docker-setup.sh stop        # Stop services
./docker-setup.sh clean       # Clean everything
```

### Option 2: Local Development

**Quick start:**
```bash
./scripts/start-dev.sh
```

This automatically:
- Installs dependencies (first run)
- Starts backend on port 8000
- Starts frontend on port 3000
- Shows combined logs

**Stop services:**
```bash
./scripts/stop-dev.sh
# or Ctrl+C in the terminal running start-dev.sh
```

#### Manual Setup (if preferred)

#### Step 1: Install Frontend Dependencies

```bash
cd frontend
npm install
```

### Step 2: Install Backend Dependencies

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs/sessions
```

### Step 3: Configure Environment

```bash
cd backend
cp .env.template .env
# Edit .env with your database credentials
```

### Step 4: Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python -m app.main
```
Backend runs at: `http://localhost:8000`
API Docs: `http://localhost:8000/docs`

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```
Frontend runs at: `http://localhost:3000`

### Step 5: Explore the Platform

Visit `http://localhost:3000` to see:
- **Dashboard**: Overview with temporal drift visualization
- **Evidence Tracer**: Interactive D3.js reasoning path visualization
- **Session Recorder**: Audit trail of all AI interactions
- **Experimental Log**: Training metrics and fine-tuning documentation

## 📋 What You Have Now

### ✅ Complete Frontend
- IBM Carbon Design System fully integrated
- D3.js visualizations for testamentary traces analysis
- 4 main pages with routing
- Dark theme (g100) optimized for research

### ✅ Complete Backend
- FastAPI with structured logging
- Session recording for cybernetic research documentation
- RESTful API for agent queries, sessions, and experiments
- Ready for Granite model integration

### ✅ Documentation
- Comprehensive README with theoretical framework
- Architecture aligned with your diagram
- TODO list for next integration steps

## 🎯 Next Steps (When Ready)

1. **Database Setup**: Install PostgreSQL with pgvector extension
2. **Granite Model**: Download and configure Granite-4.0-H-Small-Instruct
3. **Document Processing**: Integrate Granite-Docling for PDF/image processing
4. **Vector Database**: Implement embedding and retrieval pipeline
5. **Fine-tuning**: Create training data for testamentary traces analysis

## 📚 Key URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- API Health Check: http://localhost:8000/health

## 🎨 IBM Carbon Compliance

All components use:
- IBM Plex Sans font family
- Carbon spacing tokens
- Carbon color tokens (g100 theme)
- Carbon Grid system (16 columns)
- Full SCSS mixins and utilities

## 💡 Philosophy

This platform embodies second-order cybernetics:
- You (observer) are part of the research system
- The AI agent is both tool AND object of study
- Every interaction is logged for methodological transparency
- Human-AI collaboration creates knowledge dialectically

Ready to analyze testamentary traces! 🔬
