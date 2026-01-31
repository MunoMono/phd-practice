"""
Semantic Search API using pgvector
Advanced search with embeddings, entities, and themes
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import LocalSessionLocal

router = APIRouter()


class SearchResult(BaseModel):
    document_id: str
    pid: str
    title: str
    similarity: float
    summary: Optional[str]
    themes: List[str]
    entities: Optional[dict]
    year: Optional[int]
    pdf_count: int
    highlights: List[str]


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_similarity: float = 0.5
    filter_themes: Optional[List[str]] = None
    filter_years: Optional[List[int]] = None


@router.post("/semantic", response_model=List[SearchResult])
async def semantic_search(request: SemanticSearchRequest):
    """
    Vector similarity search using document embeddings.
    
    TODO: Implement actual embedding generation for query
    For now, returns example structure
    """
    db = LocalSessionLocal()
    
    try:
        # In production, generate embedding for query text
        # query_embedding = generate_embedding(request.query)
        
        # For now, search by text similarity in summaries and themes
        query_sql = """
        SELECT 
            document_id,
            pid,
            title,
            ml_summary,
            ml_themes,
            ml_entities,
            publication_year,
            pdf_count,
            ml_confidence,
            -- Placeholder similarity score based on text matching
            CASE 
                WHEN LOWER(title) LIKE LOWER(:query_pattern) THEN 0.9
                WHEN LOWER(ml_summary) LIKE LOWER(:query_pattern) THEN 0.7
                WHEN EXISTS (
                    SELECT 1 FROM unnest(ml_themes) AS theme 
                    WHERE LOWER(theme) LIKE LOWER(:query_pattern)
                ) THEN 0.6
                ELSE 0.4
            END as similarity
        FROM documents
        WHERE pid IS NOT NULL
            AND (
                LOWER(title) LIKE LOWER(:query_pattern)
                OR LOWER(ml_summary) LIKE LOWER(:query_pattern)
                OR EXISTS (
                    SELECT 1 FROM unnest(ml_themes) AS theme 
                    WHERE LOWER(theme) LIKE LOWER(:query_pattern)
                )
            )
        """
        
        if request.filter_themes:
            theme_list = "', '".join(request.filter_themes)
            query_sql += f" AND ml_themes && ARRAY['{theme_list}']"
        
        if request.filter_years:
            years = ", ".join(map(str, request.filter_years))
            query_sql += f" AND publication_year IN ({years})"
        
        query_sql += """
        ORDER BY similarity DESC
        LIMIT :limit
        """
        
        result = db.execute(
            text(query_sql),
            {
                "query_pattern": f"%{request.query}%",
                "limit": request.limit
            }
        )
        
        results = []
        for row in result:
            # Generate highlights from summary
            highlights = []
            if row.ml_summary:
                summary_lower = row.ml_summary.lower()
                query_lower = request.query.lower()
                if query_lower in summary_lower:
                    idx = summary_lower.index(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(row.ml_summary), idx + len(request.query) + 50)
                    highlight = row.ml_summary[start:end]
                    if start > 0:
                        highlight = "..." + highlight
                    if end < len(row.ml_summary):
                        highlight = highlight + "..."
                    highlights.append(highlight)
            
            results.append(SearchResult(
                document_id=row.document_id,
                pid=row.pid,
                title=row.title,
                similarity=float(row.similarity),
                summary=row.ml_summary,
                themes=row.ml_themes or [],
                entities=row.ml_entities,
                year=row.publication_year,
                pdf_count=row.pdf_count or 0,
                highlights=highlights
            ))
        
        return results
        
    finally:
        db.close()


@router.get("/similar-documents/{document_id}")
async def find_similar_documents(
    document_id: str,
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.6, ge=0.0, le=1.0)
):
    """
    Find documents similar to a given document using pgvector.
    Uses precomputed similarity matrix for performance.
    """
    db = LocalSessionLocal()
    
    try:
        # Check if document exists
        check_query = "SELECT document_id, title FROM documents WHERE document_id = :doc_id"
        check_result = db.execute(text(check_query), {"doc_id": document_id})
        source_doc = check_result.fetchone()
        
        if not source_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get similar documents
        similarity_query = """
        SELECT 
            CASE 
                WHEN ds.document_id_a = :doc_id THEN ds.document_id_b
                ELSE ds.document_id_a
            END as similar_doc_id,
            ds.combined_score as similarity,
            d.title,
            d.pid,
            d.ml_themes,
            d.pdf_count,
            d.publication_year
        FROM document_similarities ds
        JOIN documents d ON (
            CASE 
                WHEN ds.document_id_a = :doc_id THEN ds.document_id_b
                ELSE ds.document_id_a
            END = d.document_id
        )
        WHERE (ds.document_id_a = :doc_id OR ds.document_id_b = :doc_id)
            AND ds.combined_score >= :threshold
        ORDER BY ds.combined_score DESC
        LIMIT :limit
        """
        
        result = db.execute(
            text(similarity_query),
            {
                "doc_id": document_id,
                "threshold": threshold,
                "limit": limit
            }
        )
        
        similar_docs = [
            {
                "documentId": row.similar_doc_id,
                "pid": row.pid,
                "title": row.title,
                "similarity": float(row.similarity),
                "themes": row.ml_themes or [],
                "pdfCount": row.pdf_count or 0,
                "year": row.publication_year
            }
            for row in result
        ]
        
        return {
            "sourceDocument": {
                "documentId": source_doc.document_id,
                "title": source_doc.title
            },
            "similarDocuments": similar_docs,
            "metadata": {
                "count": len(similar_docs),
                "threshold": threshold
            }
        }
        
    finally:
        db.close()


@router.get("/entity-search")
async def search_by_entity(
    entity: str,
    entity_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Find documents containing specific entities.
    """
    db = LocalSessionLocal()
    
    try:
        query = """
        SELECT 
            d.document_id,
            d.pid,
            d.title,
            d.ml_themes,
            d.publication_year,
            e.entity_text,
            e.entity_type,
            de.occurrences,
            de.confidence,
            de.pages
        FROM document_entities de
        JOIN entities e ON de.entity_id = e.id
        JOIN documents d ON de.document_id = d.document_id
        WHERE LOWER(e.entity_text) LIKE LOWER(:entity_pattern)
        """
        
        if entity_type:
            query += " AND e.entity_type = :entity_type"
        
        query += """
        ORDER BY de.occurrences DESC, de.confidence DESC
        LIMIT :limit
        """
        
        params = {"entity_pattern": f"%{entity}%", "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        
        result = db.execute(text(query), params)
        
        return [
            {
                "documentId": row.document_id,
                "pid": row.pid,
                "title": row.title,
                "themes": row.ml_themes or [],
                "year": row.publication_year,
                "entity": {
                    "text": row.entity_text,
                    "type": row.entity_type,
                    "occurrences": row.occurrences,
                    "confidence": float(row.confidence) if row.confidence else 0.0,
                    "pages": row.pages or []
                }
            }
            for row in result
        ]
        
    finally:
        db.close()


@router.get("/autocomplete")
async def search_autocomplete(
    q: str = Query(..., min_length=2),
    categories: Optional[List[str]] = Query(None)
):
    """
    Autocomplete suggestions for search.
    Returns documents, themes, and entities.
    """
    db = LocalSessionLocal()
    
    try:
        suggestions = {
            "documents": [],
            "themes": [],
            "entities": []
        }
        
        # Document titles
        doc_query = """
        SELECT DISTINCT title, pid
        FROM documents
        WHERE LOWER(title) LIKE LOWER(:pattern)
            AND pid IS NOT NULL
        ORDER BY title
        LIMIT 5
        """
        
        doc_result = db.execute(text(doc_query), {"pattern": f"%{q}%"})
        suggestions["documents"] = [
            {"text": row.title, "pid": row.pid, "type": "document"}
            for row in doc_result
        ]
        
        # Themes
        theme_query = """
        SELECT DISTINCT unnest(ml_themes) as theme
        FROM documents
        WHERE ml_themes IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM unnest(ml_themes) AS t
                WHERE LOWER(t) LIKE LOWER(:pattern)
            )
        LIMIT 5
        """
        
        theme_result = db.execute(text(theme_query), {"pattern": f"%{q}%"})
        suggestions["themes"] = [
            {"text": row.theme, "type": "theme"}
            for row in theme_result
        ]
        
        # Entities
        entity_query = """
        SELECT entity_text, entity_type, frequency
        FROM entities
        WHERE LOWER(entity_text) LIKE LOWER(:pattern)
        ORDER BY frequency DESC
        LIMIT 5
        """
        
        entity_result = db.execute(text(entity_query), {"pattern": f"%{q}%"})
        suggestions["entities"] = [
            {
                "text": row.entity_text,
                "type": "entity",
                "entityType": row.entity_type,
                "frequency": row.frequency
            }
            for row in entity_result
        ]
        
        return suggestions
        
    finally:
        db.close()
