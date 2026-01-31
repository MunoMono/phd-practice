"""
Visualization API - Data endpoints for D3.js visualizations
Carbon Design System compatible data structures
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

from app.core.database import LocalSessionLocal

router = APIRouter()


@router.get("/document-network")
async def get_document_network(
    min_similarity: float = Query(0.6, ge=0.0, le=1.0),
    max_nodes: int = Query(50, ge=10, le=200),
    theme_filter: Optional[str] = None
):
    """
    Generate network graph data for D3 force-directed layout.
    
    Returns:
        - nodes: Documents with metadata
        - links: Similarity relationships
        - clusters: Theme-based groupings
    
    Carbon component: Custom D3 visualization
    """
    db = LocalSessionLocal()
    
    try:
        # Get documents with embeddings
        query = """
        SELECT 
            document_id,
            pid,
            title,
            pdf_count,
            ml_themes,
            publication_year,
            ml_confidence,
            embeddings
        FROM documents
        WHERE embeddings IS NOT NULL
            AND pid IS NOT NULL
        """
        
        if theme_filter:
            query += f" AND '{theme_filter}' = ANY(ml_themes)"
        
        query += f" LIMIT {max_nodes}"
        
        result = db.execute(text(query))
        documents = result.fetchall()
        
        if not documents:
            return {"nodes": [], "links": [], "clusters": []}
        
        # Build nodes
        nodes = []
        doc_map = {}
        
        for i, doc in enumerate(documents):
            node = {
                "id": doc.document_id,
                "pid": doc.pid,
                "name": doc.title,
                "pdfCount": doc.pdf_count or 0,
                "themes": doc.ml_themes or [],
                "year": doc.publication_year,
                "confidence": float(doc.ml_confidence) if doc.ml_confidence else 0.0,
                "group": doc.ml_themes[0] if doc.ml_themes else "uncategorized",
                "size": (doc.pdf_count or 1) * 3  # Node size based on PDF count
            }
            nodes.append(node)
            doc_map[doc.document_id] = i
        
        # Calculate similarity links
        links = []
        link_query = """
        SELECT 
            document_id_a,
            document_id_b,
            combined_score
        FROM document_similarities
        WHERE combined_score >= :min_similarity
            AND (document_id_a IN :doc_ids OR document_id_b IN :doc_ids)
        ORDER BY combined_score DESC
        LIMIT 200
        """
        
        doc_ids = tuple([d.document_id for d in documents])
        if len(doc_ids) > 1:
            similarity_result = db.execute(
                text(link_query),
                {"min_similarity": min_similarity, "doc_ids": doc_ids}
            )
            
            for row in similarity_result:
                if row.document_id_a in doc_map and row.document_id_b in doc_map:
                    links.append({
                        "source": row.document_id_a,
                        "target": row.document_id_b,
                        "value": float(row.combined_score),
                        "strength": float(row.combined_score)
                    })
        
        # Get theme clusters
        cluster_query = """
        SELECT 
            theme_name,
            description,
            color_hex,
            document_count
        FROM theme_clusters
        ORDER BY document_count DESC
        """
        
        cluster_result = db.execute(text(cluster_query))
        clusters = [
            {
                "id": row.theme_name,
                "name": row.theme_name,
                "description": row.description,
                "color": row.color_hex or "#0f62fe",
                "count": row.document_count
            }
            for row in cluster_result
        ]
        
        return {
            "nodes": nodes,
            "links": links,
            "clusters": clusters,
            "metadata": {
                "totalDocuments": len(nodes),
                "totalLinks": len(links),
                "minSimilarity": min_similarity,
                "generatedAt": datetime.now().isoformat()
            }
        }
        
    finally:
        db.close()


@router.get("/theme-distribution")
async def get_theme_distribution():
    """
    Theme distribution data for Carbon DonutChart/BarChart.
    
    Returns Carbon-compatible dataset structure.
    """
    db = LocalSessionLocal()
    
    try:
        query = """
        SELECT 
            unnest(ml_themes) as theme,
            COUNT(*) as count
        FROM documents
        WHERE ml_themes IS NOT NULL
            AND pid IS NOT NULL
        GROUP BY theme
        ORDER BY count DESC
        LIMIT 15
        """
        
        result = db.execute(text(query))
        data = result.fetchall()
        
        # Carbon color palette
        carbon_colors = [
            "#0f62fe", "#8a3ffc", "#33b1ff", "#24a148", "#f1c21b",
            "#da1e28", "#ff832b", "#fa4d56", "#570408", "#198038",
            "#002d9c", "#ee538b", "#b28600", "#009d9a", "#005d5d"
        ]
        
        return {
            "labels": [row.theme for row in data],
            "datasets": [{
                "label": "Documents per Theme",
                "data": [int(row.count) for row in data],
                "backgroundColor": carbon_colors[:len(data)]
            }],
            "total": sum(row.count for row in data)
        }
        
    finally:
        db.close()


@router.get("/temporal-trends")
async def get_temporal_trends(
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
):
    """
    Time series data for Carbon LineChart.
    Shows document publication trends over time.
    """
    db = LocalSessionLocal()
    
    try:
        query = """
        SELECT 
            publication_year as year,
            COUNT(*) as document_count,
            SUM(pdf_count) as total_pdfs,
            AVG(ml_confidence) as avg_confidence,
            array_agg(DISTINCT ml_themes[1]) FILTER (WHERE ml_themes IS NOT NULL) as top_themes
        FROM documents
        WHERE publication_year IS NOT NULL
            AND pid IS NOT NULL
        """
        
        if start_year:
            query += f" AND publication_year >= {start_year}"
        if end_year:
            query += f" AND publication_year <= {end_year}"
        
        query += """
        GROUP BY publication_year
        ORDER BY publication_year
        """
        
        result = db.execute(text(query))
        data = result.fetchall()
        
        return {
            "labels": [str(row.year) for row in data],
            "datasets": [
                {
                    "label": "Documents Published",
                    "data": [int(row.document_count) for row in data],
                    "borderColor": "#0f62fe",
                    "backgroundColor": "rgba(15, 98, 254, 0.1)"
                },
                {
                    "label": "Total PDFs",
                    "data": [int(row.total_pdfs or 0) for row in data],
                    "borderColor": "#8a3ffc",
                    "backgroundColor": "rgba(138, 63, 252, 0.1)"
                }
            ],
            "trends": [
                {
                    "year": row.year,
                    "themes": row.top_themes or []
                }
                for row in data
            ]
        }
        
    finally:
        db.close()


@router.get("/entity-network")
async def get_entity_network(
    entity_type: Optional[str] = None,
    min_frequency: int = 2,
    max_entities: int = 100
):
    """
    Entity co-occurrence network for D3 visualization.
    Shows relationships between people, organizations, concepts.
    """
    db = LocalSessionLocal()
    
    try:
        # Get top entities
        entity_query = """
        SELECT 
            e.id,
            e.entity_text,
            e.entity_type,
            e.frequency,
            COUNT(DISTINCT de.document_id) as document_count
        FROM entities e
        JOIN document_entities de ON e.id = de.entity_id
        WHERE e.frequency >= :min_freq
        """
        
        if entity_type:
            entity_query += f" AND e.entity_type = '{entity_type}'"
        
        entity_query += """
        GROUP BY e.id, e.entity_text, e.entity_type, e.frequency
        ORDER BY e.frequency DESC
        LIMIT :max_entities
        """
        
        result = db.execute(
            text(entity_query),
            {"min_freq": min_frequency, "max_entities": max_entities}
        )
        entities = result.fetchall()
        
        nodes = [
            {
                "id": f"entity_{e.id}",
                "name": e.entity_text,
                "type": e.entity_type,
                "frequency": e.frequency,
                "documentCount": e.document_count,
                "size": min(e.frequency * 2, 50)
            }
            for e in entities
        ]
        
        # Get co-occurrence links
        entity_ids = tuple([e.id for e in entities])
        
        if len(entity_ids) > 1:
            cooccurrence_query = """
            SELECT 
                de1.entity_id as entity_a,
                de2.entity_id as entity_b,
                COUNT(*) as cooccurrence_count
            FROM document_entities de1
            JOIN document_entities de2 
                ON de1.document_id = de2.document_id
                AND de1.entity_id < de2.entity_id
            WHERE de1.entity_id IN :entity_ids
                AND de2.entity_id IN :entity_ids
            GROUP BY de1.entity_id, de2.entity_id
            HAVING COUNT(*) >= 2
            ORDER BY cooccurrence_count DESC
            LIMIT 200
            """
            
            link_result = db.execute(
                text(cooccurrence_query),
                {"entity_ids": entity_ids}
            )
            
            links = [
                {
                    "source": f"entity_{row.entity_a}",
                    "target": f"entity_{row.entity_b}",
                    "value": row.cooccurrence_count,
                    "strength": min(row.cooccurrence_count / 10, 1.0)
                }
                for row in link_result
            ]
        else:
            links = []
        
        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "entityType": entity_type or "all",
                "totalEntities": len(nodes),
                "totalLinks": len(links)
            }
        }
        
    finally:
        db.close()


@router.get("/dashboard-stats")
async def get_dashboard_stats():
    """
    Real-time ML processing statistics for dashboard.
    Optimized using materialized view.
    """
    db = LocalSessionLocal()
    
    try:
        # Get cached stats
        stats_query = "SELECT * FROM ml_dashboard_stats"
        result = db.execute(text(stats_query))
        stats = result.fetchone()
        
        # Get recent processing activity
        activity_query = """
        SELECT 
            stage,
            status,
            COUNT(*) as count,
            AVG(duration_seconds) as avg_duration
        FROM ml_processing_log
        WHERE started_at > NOW() - INTERVAL '24 hours'
        GROUP BY stage, status
        ORDER BY stage, status
        """
        
        activity_result = db.execute(text(activity_query))
        
        return {
            "overview": {
                "totalDocuments": stats.total_documents,
                "totalPdfs": stats.total_pdfs,
                "yearRange": stats.year_range
            },
            "mlProcessing": {
                "documentsWithEmbeddings": stats.documents_with_embeddings,
                "documentsWithSummaries": stats.documents_with_summaries,
                "documentsWithEntities": stats.documents_with_entities,
                "avgConfidence": float(stats.avg_confidence) if stats.avg_confidence else 0.0,
                "completionRate": round(
                    (stats.documents_with_embeddings / stats.total_documents * 100) 
                    if stats.total_documents > 0 else 0, 2
                )
            },
            "themes": {
                "uniqueThemes": stats.unique_themes
            },
            "recentActivity": stats.recent_activity or [],
            "lastUpdated": stats.last_updated.isoformat() if stats.last_updated else None
        }
        
    finally:
        db.close()


@router.post("/refresh-stats")
async def refresh_dashboard_stats():
    """
    Manually trigger refresh of materialized view.
    Use after bulk ML processing.
    """
    db = LocalSessionLocal()
    
    try:
        db.execute(text("SELECT refresh_ml_dashboard_stats()"))
        db.commit()
        return {"status": "success", "message": "Dashboard stats refreshed"}
    finally:
        db.close()
