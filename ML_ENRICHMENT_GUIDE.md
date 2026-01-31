# ML Enrichment System Documentation

## Overview
Comprehensive ML enrichment and visualization platform for the RCA PhD research corpus. This system provides semantic search, entity extraction, theme analysis, and interactive D3.js visualizations styled with IBM Carbon Design.

## Architecture

### Database Schema (Migration 004)
Located at: `backend/migrations/004_ml_enrichment_schema.sql`

#### Core Tables
- **documents.embeddings**: 1536-dimensional vectors for semantic search (pgvector)
- **documents.ml_entities**: JSONB storage for named entities (people, orgs, concepts)
- **documents.ml_summary**: AI-generated document summaries
- **documents.ml_themes**: TEXT[] for topic extraction
- **documents.ml_keywords**: TEXT[] for enhanced search

#### Relationship Tables
- **entities**: Reference table for all extracted entities
  - Columns: entity_text, entity_type (PERSON, ORG, CONCEPT, METHOD, LOCATION), frequency
- **document_entities**: Many-to-many relationships with confidence scores
  - Columns: document_id, entity_id, occurrences, pages, confidence, context_snippets
- **document_similarities**: Precomputed similarity matrix for performance
  - Scores: embedding_similarity, entity_overlap, theme_overlap, combined_score

#### Analytics Tables
- **ml_processing_log**: Audit trail for ML pipeline
  - Tracks: stage, status, start/end times, tokens_used, cost_usd, error messages
- **theme_clusters**: Groupings for visualization
- **temporal_trends**: Time-series data (year, month, themes, entities)

#### Materialized View
- **ml_dashboard_stats**: Real-time statistics for dashboard performance
  - Auto-refreshed after bulk processing
  - Manual refresh: `SELECT refresh_ml_dashboard_stats();`

### API Endpoints

#### Visualization API (`/api/viz`)
Located at: `backend/app/api/routes/viz.py`

- **GET /viz/document-network**: Force-directed graph data
  ```json
  {
    "nodes": [{"id": 1, "title": "...", "pdf_count": 4, "year": 1967}],
    "links": [{"source": 1, "target": 2, "weight": 0.85}],
    "clusters": [{"theme": "Design Methods", "documents": [...]}]
  }
  ```

- **GET /viz/theme-distribution**: Carbon DonutChart/BarChart data
  ```json
  {
    "themes": [{"theme": "Innovation", "count": 12, "color": "#0f62fe"}]
  }
  ```

- **GET /viz/temporal-trends**: LineChart time-series
  ```json
  {
    "trends": [{"year": 1967, "document_count": 3, "pdf_count": 4}]
  }
  ```

- **GET /viz/entity-network**: Entity co-occurrence network
  ```json
  {
    "nodes": [{"id": 1, "entity_text": "Bruce Archer", "entity_type": "PERSON"}],
    "links": [{"source": 1, "target": 2, "weight": 5}]
  }
  ```

- **GET /viz/dashboard-stats**: Real-time ML statistics
- **POST /viz/refresh-stats**: Trigger materialized view refresh

#### Search API (`/api/search`)
Located at: `backend/app/api/routes/search.py`

- **POST /search/semantic**: Vector similarity search
  ```json
  {
    "query": "design innovation methods",
    "limit": 10,
    "theme_filter": ["Design Methods"],
    "year_filter": [1967, 1968]
  }
  ```

- **GET /search/similar-documents/{id}**: Find related documents
- **GET /search/entity-search**: Filter by entities
  ```
  ?entity=Bruce Archer&entity_type=PERSON
  ```

- **GET /search/autocomplete**: Search suggestions
  ```
  ?query=arch
  → {"documents": [...], "themes": [...], "entities": [...]}
  ```

### Frontend Components

#### ML Dashboard (`/ml-dashboard`)
Located at: `frontend/src/pages/MLDashboard/MLDashboard.jsx`

**Features:**
- Real-time stats cards (documents, embeddings, entities, themes)
- ProgressBar showing ML processing completion
- Tabbed visualizations (Network, Themes, Timeline, Entities)
- Recent activity DataTable with status Tags
- Refresh button for materialized view update

**Carbon Components Used:**
- Grid, Column, Tile, Loading, ProgressBar
- DataTable, TableContainer, Table, Tag, Button
- Tabs, TabList, Tab, TabPanels, TabPanel
- Icons: Analytics, Document, ModelAlt, DataVis_1, Network_3, ChartLine, Search, Renew

#### D3 Visualizations

##### DocumentNetwork
`frontend/src/components/visualizations/DocumentNetwork.jsx`

- Force-directed graph showing document relationships
- Node size = PDF count, color = theme cluster
- Interactive: hover for details, drag to reposition, zoom/pan
- Legend showing theme clusters
- Uses precomputed similarity matrix for performance

##### ThemeDistribution
`frontend/src/components/visualizations/ThemeDistribution.jsx`

- Toggle between Donut chart and Bar chart
- Animated transitions using D3 tweens
- IBM Carbon color palette
- Hover tooltips with percentages

##### TemporalTrends
`frontend/src/components/visualizations/TemporalTrends.jsx`

- Dual-axis line chart (documents vs PDFs)
- Area fills with opacity
- Animated line drawing effect
- Interactive points with tooltips

##### EntityNetwork
`frontend/src/components/visualizations/EntityNetwork.jsx`

- Filter by entity type (PERSON, ORG, CONCEPT, METHOD, LOCATION)
- Node size = frequency, color = entity type
- Co-occurrence links weighted by shared documents
- Carbon Tag filters at top

### Theme Integration
`frontend/src/utils/carbonD3Theme.js`

**Exports:**
- `carbonColors`: Complete IBM palette (primary, status, gray, viz, sequential, diverging)
- `carbonTypography`: IBM Plex fonts (mono, sans, serif) with sizes
- `d3Scales`: Factory functions for categorical, sequential, diverging scales
- `chartStyles`: Presets for network, timeline, heatmap
- `animations`: Duration (fast 200ms, normal 400ms, slow 800ms), easing
- `breakpoints`: Carbon grid (sm 320, md 672, lg 1056, xlg 1312, max 1584)
- `utils`: getColorByIndex(), getContrastColor(), formatNumber(), truncate()

**Color Palette:**
- Primary: #0f62fe (blue), #8a3ffc (purple), #0072c3 (cyan)
- Visualization: 15-color palette for chart variety
- Sequential: blue-10 to blue-100, purple-10 to purple-100
- Diverging: purple → blue, red → green

## Installation

### 1. Apply Database Migration
```bash
# SSH to production server
ssh root@104.248.170.26

# Apply migration 004
docker exec -i epistemic-drift-db psql -U postgres -d epistemic_drift < /path/to/004_ml_enrichment_schema.sql

# Verify pgvector extension
docker exec epistemic-drift-db psql -U postgres -d epistemic_drift -c "\dx"
```

### 2. Update Backend Dependencies
Migration 004 requires **pgvector** extension (already included in `ankane/pgvector:latest` Docker image).

No Python package changes needed - routes use existing SQLAlchemy and FastAPI.

### 3. Rebuild Containers
```bash
# On production server
cd ~/epistemic-drift
docker-compose down
docker-compose up -d --build

# Verify routes are registered
curl https://innovationdesign.io/api/docs
```

### 4. Frontend Build
Frontend already has all dependencies (d3@7.9.0 installed in package.json).

```bash
# Local development
npm run dev

# Production build
npm run build
docker-compose restart frontend
```

## Usage

### ML Processing Pipeline

**Stage 1: Generate Embeddings**
```python
# Use OpenAI API or local model to generate embeddings
# Store in documents.embeddings (1536-dim vector)
# Log to ml_processing_log
```

**Stage 2: Extract Entities**
```python
# NER using spaCy/Granite/GPT
# Store in entities table + document_entities relationships
# Log confidence scores and context snippets
```

**Stage 3: Analyze Themes**
```python
# Topic modeling (LDA/BERTopic/GPT)
# Store in documents.ml_themes (TEXT[])
# Create theme_clusters for visualization
```

**Stage 4: Calculate Similarities**
```python
# Compute document_similarities matrix
# Use calculate_document_similarity() function
# Combines embedding cosine, entity overlap, theme overlap
```

**Stage 5: Generate Summaries**
```python
# AI-generated summaries via Granite/GPT
# Store in documents.ml_summary (TEXT)
# Extract ml_keywords (TEXT[])
```

**Stage 6: Build Temporal Trends**
```python
# Aggregate by year/month
# Store in temporal_trends table
# Track theme evolution over time
```

### Accessing the Dashboard
1. Navigate to https://innovationdesign.io/ml-dashboard
2. View stats cards showing ML processing progress
3. Explore visualizations in tabs:
   - **Document Network**: Semantic relationships between documents
   - **Theme Distribution**: Topic breakdown across corpus
   - **Temporal Trends**: Publication timeline with themes
   - **Entity Network**: People, orgs, concepts co-occurrence

### Running Queries

**Find Similar Documents:**
```sql
SELECT * FROM find_similar_documents(
  1,  -- document_id
  10, -- limit
  0.7 -- min_similarity
);
```

**Search by Vector:**
```sql
SELECT id, title,
  1 - (embeddings <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM documents
WHERE embeddings IS NOT NULL
ORDER BY embeddings <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

**Theme Distribution:**
```sql
SELECT theme, COUNT(*) as count
FROM documents, unnest(ml_themes) as theme
WHERE ml_themes IS NOT NULL
GROUP BY theme
ORDER BY count DESC;
```

## Performance Optimization

### Indexes (Already Created in Migration 004)
- `ivfflat` index on embeddings (100 lists) for vector search
- GIN index on ml_entities for JSONB queries
- GIN index on ml_themes and ml_keywords for array search
- Composite indexes on (entity_id, confidence) and (year, month)

### Materialized View
- `ml_dashboard_stats` pre-aggregates expensive queries
- Refresh after bulk processing: `POST /api/viz/refresh-stats`
- Automatic refresh on migration apply

### Query Tips
- Use `find_similar_documents()` function instead of raw vector queries
- Filter by year/theme before vector search to reduce search space
- Limit results to top-K (default 10)
- Use EXPLAIN ANALYZE to profile slow queries

## Data Flow

```
DDR Archive GraphQL
        ↓
quick_sync_pids.py (4 parent PIDs)
        ↓
PostgreSQL documents table
        ↓
ML Processing Pipeline (6 stages)
        ↓
pgvector + ML tables (embeddings, entities, themes, similarities)
        ↓
Visualization API (/api/viz) + Search API (/api/search)
        ↓
React Frontend (MLDashboard + D3 components)
        ↓
User explores corpus via Carbon-styled visualizations
```

## Future Enhancements

**Phase 2: Advanced ML**
- Fine-tune Granite for RCA domain-specific embeddings
- Implement citation network analysis
- Add image processing for diagrams/figures in PDFs
- Multi-modal embeddings (text + images)

**Phase 3: Collaboration**
- Annotation interface for manual entity tagging
- User feedback loop for ML model improvement
- Export visualizations as PNG/SVG for publications
- API authentication for external researchers

**Phase 4: Scale**
- Implement incremental indexing for new documents
- Add caching layer (Redis) for frequent queries
- Optimize vector index (HNSW instead of ivfflat)
- Batch processing pipeline for thousands of PDFs

## Troubleshooting

**pgvector not available:**
```bash
# Check if extension is installed
docker exec epistemic-drift-db psql -U postgres -d epistemic_drift -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Slow vector queries:**
```sql
-- Check if ivfflat index exists
SELECT indexname FROM pg_indexes WHERE tablename = 'documents' AND indexname LIKE '%embeddings%';

-- Rebuild index if needed
DROP INDEX IF EXISTS idx_documents_embeddings;
CREATE INDEX idx_documents_embeddings ON documents USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100);
```

**Dashboard stats not updating:**
```bash
# Manually refresh materialized view
curl -X POST https://innovationdesign.io/api/viz/refresh-stats
```

**D3 visualizations not rendering:**
- Check browser console for errors
- Verify API endpoints return data: `/api/viz/document-network`
- Ensure ResizeObserver has valid dimensions
- Check Carbon theme tokens are loaded

## Credits

**Built for:** Graham Newman's RCA PhD Research  
**Technologies:** PostgreSQL + pgvector, FastAPI, React, D3.js, IBM Carbon Design  
**Data Source:** DDR Archive (https://api.ddrarchive.org/graphql)  
**Corpus:** 47 PDFs spanning 1967-1985 (Bruce Archer, Kenneth Agnew, RCA Prospectuses, RCA Rector's Reports)

This is the legacy of design methods research at the Royal College of Art. 🎓
