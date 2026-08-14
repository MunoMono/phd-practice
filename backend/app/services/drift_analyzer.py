"""
Testamentary traces analysis service
Measures conceptual change over time using embeddings and Granite
"""
import logging
from typing import List, Dict, Optional
import uuid
from datetime import datetime

from app.core.database import LocalSessionLocal
from app.models.document import Document, DocumentChunk, DriftAnalysis
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class DriftAnalyzer:
    """Analyze testamentary traces between time periods"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    async def analyze_temporal_drift(
        self,
        start_year: int,
        end_year: int,
        window_size: int = 5
    ) -> Dict:
        """
        Analyze drift between time periods
        
        Args:
            start_year: Start of analysis period
            end_year: End of analysis period
            window_size: Years per comparison window
            
        Returns:
            Drift analysis results
        """
        try:
            db = LocalSessionLocal()
            
            # Get all chunks in period
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.publication_year >= start_year,
                DocumentChunk.publication_year <= end_year
            ).all()
            
            if not chunks:
                return {
                    "error": "No documents found in period",
                    "start_year": start_year,
                    "end_year": end_year
                }
            
            # Group by time windows
            windows = self._create_time_windows(
                chunks, 
                start_year, 
                end_year, 
                window_size
            )
            
            # Calculate drift between windows
            drift_scores = []
            for i in range(len(windows) - 1):
                window1 = windows[i]
                window2 = windows[i + 1]
                
                embeddings1 = [chunk.embedding_vector for chunk in window1['chunks']]
                embeddings2 = [chunk.embedding_vector for chunk in window2['chunks']]
                
                drift = self.embedding_service.calculate_drift_score(
                    embeddings1,
                    embeddings2
                )
                
                drift_scores.append({
                    'period1': f"{window1['start']}-{window1['end']}",
                    'period2': f"{window2['start']}-{window2['end']}",
                    'drift_score': drift
                })
            
            # Save analysis
            analysis_id = f"drift_{uuid.uuid4().hex[:12]}"
            analysis = DriftAnalysis(
                analysis_id=analysis_id,
                period_start_year=start_year,
                period_end_year=end_year,
                document_count=len(set(c.document_id for c in chunks)),
                drift_score=sum(d['drift_score'] for d in drift_scores) / len(drift_scores),
                analysis_method='embedding_comparison',
                model_used=self.embedding_service.model_name,
                results={'drift_scores': drift_scores}
            )
            
            db.add(analysis)
            db.commit()
            
            db.close()
            
            return {
                'analysis_id': analysis_id,
                'start_year': start_year,
                'end_year': end_year,
                'document_count': analysis.document_count,
                'drift_score': analysis.drift_score,
                'drift_scores': drift_scores
            }
            
        except Exception as e:
            logger.error(f"Error analyzing drift: {e}")
            return {'error': str(e)}
    
    def _create_time_windows(
        self,
        chunks: List[DocumentChunk],
        start_year: int,
        end_year: int,
        window_size: int
    ) -> List[Dict]:
        """Group chunks into time windows"""
        windows = []
        
        current_start = start_year
        while current_start < end_year:
            current_end = min(current_start + window_size - 1, end_year)
            
            window_chunks = [
                c for c in chunks
                if current_start <= c.publication_year <= current_end
            ]
            
            if window_chunks:
                windows.append({
                    'start': current_start,
                    'end': current_end,
                    'chunks': window_chunks
                })
            
            current_start = current_end + 1
        
        return windows
    
    async def compare_documents(
        self,
        doc_id1: str,
        doc_id2: str
    ) -> Dict:
        """
        Compare two documents directly
        
        Args:
            doc_id1: First document ID
            doc_id2: Second document ID
            
        Returns:
            Comparison results
        """
        try:
            db = LocalSessionLocal()
            
            # Get chunks for both documents
            chunks1 = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc_id1
            ).all()
            
            chunks2 = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc_id2
            ).all()
            
            if not chunks1 or not chunks2:
                return {'error': 'One or both documents have no chunks'}
            
            # Get embeddings
            embeddings1 = [chunk.embedding_vector for chunk in chunks1]
            embeddings2 = [chunk.embedding_vector for chunk in chunks2]
            
            # Calculate drift
            drift = self.embedding_service.calculate_drift_score(
                embeddings1,
                embeddings2
            )
            
            db.close()
            
            return {
                'document1': doc_id1,
                'document2': doc_id2,
                'drift_score': drift,
                'chunks_compared': {
                    'doc1': len(chunks1),
                    'doc2': len(chunks2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error comparing documents: {e}")
            return {'error': str(e)}
