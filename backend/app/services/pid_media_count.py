"""
PID Media Count Service - Query DDR Archive GraphQL API for media asset counts

This service queries the DDR Archive GraphQL API to get counts of PDF and TIFF
files attached to each PID authority. This provides provenance tracking for
what will be ingested by Docling.
"""
import logging
import requests
from typing import Dict, List, Optional
from sqlalchemy import text

from app.core.database import LocalSessionLocal

logger = logging.getLogger(__name__)


class PIDMediaCountService:
    """Query DDR Archive GraphQL API for media asset counts per PID"""
    
    def __init__(self, graphql_endpoint: str = "https://api.ddrarchive.org/graphql"):
        self.graphql_endpoint = graphql_endpoint
    
    def get_media_counts_for_pid(self, pid: str) -> Dict[str, int]:
        """
        Query DDR Archive GraphQL API for media counts for a specific PID
        
        Args:
            pid: The PID to query (e.g., "124881079617")
        
        Returns:
            Dict with pdf_count, tiff_count, total_count
        """
        query = """
        query GetMediaForPID($pid: ID!) {
            record_v1(id: $pid) {
                pid
                title
                attached_media {
                    id
                    pid
                    title
                    used_for_ml
                    ml_annotation
                    digital_assets {
                        role
                        filename
                        use_for_ml
                        ml_pages
                        ml_annotation
                    }
                    pdf_files {
                        filename
                    }
                    jpg_derivatives {
                        filename
                        role
                    }
                }
            }
        }
        """
        
        try:
            response = requests.post(
                self.graphql_endpoint,
                json={
                    'query': query,
                    'variables': {'pid': pid}
                },
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Handle errors in GraphQL response
            if 'errors' in data:
                logger.error(f"GraphQL errors for PID {pid}: {data['errors']}")
                return {'pdf_count': 0, 'tiff_count': 0, 'total_count': 0}
            
            # Parse response
            record = data.get('data', {}).get('record_v1')
            
            if not record:
                logger.warning(f"No record found for PID {pid}")
                return {'pdf_count': 0, 'tiff_count': 0, 'total_count': 0}
            
            attached_media = record.get('attached_media')
            
            if not attached_media:
                logger.info(f"No attached media found for PID {pid}")
                return {'pdf_count': 0, 'tiff_count': 0, 'total_count': 0}
            
            # Count PDF files and JPG derivatives (which may include TIFFs as source)
            # PERMANENT FILTER: ONLY include media items marked as used_for_ml: true
            # This ensures we exclude hi-res TIFFs of photographs and other non-relevant
            # assets that have been manually flagged in DDR Archive admin.
            # This filter is critical for Docling ingestion quality control.
            pdf_count = 0
            tiff_count = 0
            ml_filtered_count = 0
            
            for media_item in attached_media:
                # Skip items not marked for ML use (permanent gate)
                if not media_item.get('used_for_ml', False):
                    ml_filtered_count += 1
                    logger.debug(f"Skipping media item {media_item.get('id')} '{media_item.get('title')}' - not marked for ML (used_for_ml=false)")
                    continue
                
                pdf_files = media_item.get('pdf_files') or []
                jpg_derivatives = media_item.get('jpg_derivatives') or []
                
                pdf_count += len(pdf_files)
                # JPG derivatives are generated from source images (often TIFFs)
                # Count master/preservation derivatives as potential TIFF sources
                for deriv in jpg_derivatives:
                    if deriv.get('role') in ['master', 'preservation', 'access-master']:
                        tiff_count += 1
            
            result = {
                'pdf_count': pdf_count,
                'tiff_count': tiff_count,
                'total_count': pdf_count + tiff_count
            }
            
            ml_included = len(attached_media) - ml_filtered_count
            logger.info(f"PID {pid}: {result['pdf_count']} PDFs, {result['tiff_count']} TIFF-source derivatives from {ml_included}/{len(attached_media)} attached media items (used_for_ml filter applied)")
            if ml_filtered_count > 0:
                logger.info(f"PID {pid}: Filtered out {ml_filtered_count} media items not marked for ML use")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error querying DDR Archive for PID {pid}: {e}")
            return {'pdf_count': 0, 'tiff_count': 0, 'total_count': 0}
        except Exception as e:
            logger.error(f"Unexpected error querying media counts for PID {pid}: {e}")
            return {'pdf_count': 0, 'tiff_count': 0, 'total_count': 0}
    
    def get_media_counts_bulk(self, pids: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Get media counts for multiple PIDs
        
        Args:
            pids: List of PID strings
        
        Returns:
            Dict mapping PID -> {pdf_count, tiff_count, total_count}
        """
        results = {}
        
        for pid in pids:
            results[pid] = self.get_media_counts_for_pid(pid)
        
        return results
    
    def update_database_media_counts(self, pid: str, pdf_count: int, tiff_count: int, db=None):
        """
        Update documents table with media counts for a PID
        
        Args:
            pid: The PID to update
            pdf_count: Number of PDF files
            tiff_count: Number of TIFF files
            db: Optional database session (if None, creates new one)
        """
        close_session = False
        if db is None:
            db = LocalSessionLocal()
            close_session = True
        
        try:
            # Update all documents with this PID
            result = db.execute(
                text("""
                    UPDATE documents 
                    SET pdf_count = :pdf_count, 
                        tiff_count = :tiff_count
                    WHERE pid = :pid
                """),
                {
                    'pid': pid,
                    'pdf_count': pdf_count,
                    'tiff_count': tiff_count
                }
            )
            db.commit()
            
            rows_updated = result.rowcount
            logger.info(f"Updated {rows_updated} documents for PID {pid} with media counts")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating media counts for PID {pid}: {e}")
            raise
        finally:
            if close_session:
                db.close()
    
    def sync_all_pid_media_counts(self, db=None) -> Dict[str, any]:
        """
        Query all PIDs in database and update their media counts
        
        Args:
            db: Optional database session (if None, creates new one)
        
        Returns:
            Summary statistics
        """
        close_session = False
        if db is None:
            db = LocalSessionLocal()
            close_session = True
        
        try:
            # Get all unique PIDs
            result = db.execute(text(
                "SELECT DISTINCT pid FROM documents WHERE pid IS NOT NULL"
            ))
            pids = [row[0] for row in result.fetchall()]
            
            logger.info(f"Syncing media counts for {len(pids)} PIDs...")
            
            stats = {
                'pids_processed': 0,
                'total_pdfs': 0,
                'total_tiffs': 0,
                'errors': 0
            }
            
            for pid in pids:
                counts = self.get_media_counts_for_pid(pid)
                
                if counts['total_count'] > 0:
                    self.update_database_media_counts(
                        pid, 
                        counts['pdf_count'], 
                        counts['tiff_count'],
                        db=db
                    )
                    
                    stats['pids_processed'] += 1
                    stats['total_pdfs'] += counts['pdf_count']
                    stats['total_tiffs'] += counts['tiff_count']
                else:
                    stats['errors'] += 1
            
            logger.info(f"Media count sync complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing all PID media counts: {e}")
            raise
        finally:
            if close_session:
                db.close()
