"""
GraphQL-based sync service - Import authority records with media attachments
This is the PRIMARY ingestion method for the training corpus
"""
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime

from app.core.config import settings
from app.core.database import LocalSessionLocal
from app.models.document import Document

logger = logging.getLogger(__name__)


class GraphQLSyncService:
    """
    Sync documents from DDR Archive GraphQL API
    
    This service:
    1. Fetches all media items with PIDs from GraphQL
    2. Filters for training-eligible formats (PDFs, TIFFs)
    3. Creates document records with PID linkage
    4. Validates allowlist (only PID-linked assets)
    """
    
    def __init__(self):
        self.graphql_endpoint = settings.DDR_GRAPHQL_ENDPOINT
        self.api_token = settings.DDR_API_TOKEN
    
    def parse_graphql_media_response(self, json_data: Dict) -> Dict:
        """
        Parse GraphQL media items response and categorize by training eligibility
        
        CRITICAL: Training corpus includes PDFs AND TIFFs (master files)
        JPG derivatives are for web display only, not training
        
        Args:
            json_data: GraphQL response with all_media_items
        
        Returns:
            Dict with stats and categorized items
        """
        all_items = json_data.get('all_media_items', [])
        
        training_eligible = []  # Has PDF or TIFF master
        jpg_only = []  # Has only JPG derivatives (masters should be in DO Spaces)
        no_media = []  # Has no attachments
        
        for item in all_items:
            pid = item.get('pid')
            has_pdf = len(item.get('pdf_files', [])) > 0
            has_tiff = len(item.get('tiff_files', [])) > 0  # TIFF masters
            has_jpg = len(item.get('jpg_derivatives', [])) > 0
            
            if not pid:
                logger.warning(f"Item {item.get('id')} has no PID - skipping")
                continue
            
            if has_pdf:
                # PDFs are training-eligible
                training_eligible.append({
                    'type': 'pdf',
                    'item': item,
                    'master_files': item.get('pdf_files', [])
                })
            elif has_tiff:
                # TIFFs are training-eligible (rich visual historiography)
                training_eligible.append({
                    'type': 'tiff',
                    'item': item,
                    'master_files': item.get('tiff_files', [])
                })
            elif has_jpg:
                # JPG-only (masters should be TIFFs in DO Spaces PID folder)
                # Flag for manual review - TIFF masters may exist but not in GraphQL
                jpg_only.append(item)
            else:
                # No media attachments
                no_media.append(item)
        
        return {
            'total_items': len(all_items),
            'training_eligible_count': len(training_eligible),
            'jpg_only_count': len(jpg_only),
            'no_media_count': len(no_media),
            'training_eligible': training_eligible,
            'jpg_only': jpg_only,
            'no_media': no_media
        }
    
    def sync_graphql_item_to_database(
        self,
        item: Dict,
        master_file: Dict,
        file_type: str = 'pdf',
        dry_run: bool = False
    ) -> Optional[str]:
        """
        Create/update document record from GraphQL media item
        
        Args:
            item: GraphQL media item
            master_file: Master file dict (PDF or TIFF)
            file_type: 'pdf' or 'tiff'
            dry_run: If True, don't actually insert to database
        
        Returns:
            document_id if successful, None otherwise
        """
        pid = item.get('pid')
        if not pid:
            logger.error("Cannot sync item without PID")
            return None
        
        db = LocalSessionLocal()
        try:
            # Check if already exists by PID
            existing = db.query(Document).filter(
                Document.pid == pid
            ).first()
            
            if existing:
                logger.info(f"Document with PID {pid} already exists: {existing.document_id}")
                return existing.document_id
            
            # Extract metadata
            title = item.get('title', 'Untitled')
            authority_id = item.get('id')
            s3_key = master_file.get('url', '')
            filename = master_file.get('filename', f'unknown.{file_type}')
            
            # Determine file type
            if file_type == 'tiff':
                mime_type = 'image/tiff'
            else:
                mime_type = 'application/pdf'
            
            # Extract year from title if possible
            import re
            year_match = re.search(r'(19[6-8][0-9])', title)
            publication_year = int(year_match.group(1)) if year_match else 1970
            
            # Build authority_data from GraphQL response
            authority_data = {
                'id': authority_id,
                'pid': pid,
                'title': title,
                'file_type': file_type,
                'public_uri': item.get('public_uri'),
                'copyright_holder': item.get('copyright_holder'),
                'rights_holders': item.get('rights_holders'),
                'master_label': master_file.get('label'),
                'master_url': master_file.get('url'),
                'scope_and_content': item.get('scope_and_content'),
                'project_title': item.get('project_title'),
                'creator_agent_label': item.get('creator_agent_label'),
            }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would create document: PID={pid}, title={title}")
                return f"dry_run_{pid}"
            
            # Generate document ID
            import uuid
            document_id = f"doc_{uuid.uuid4().hex[:12]}"
            
            # Create document record
            doc = Document(
                document_id=document_id,
                pid=pid,  # CRITICAL: Authority linkage
                authority_id=authority_id,
                authority_data=authority_data,  # Cached GraphQL metadata
                title=title,
                publication_year=publication_year,
                filename=filename,
                file_type=mime_type,  # application/pdf or image/tiff
                s3_key=s3_key,
                file_size_bytes=0,  # Unknown from GraphQL
                processing_status='pending'
            )
            
            db.add(doc)
            db.commit()
            db.refresh(doc)
            
            logger.info(f"Created document {document_id} with PID {pid}: {title}")
            return document_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing GraphQL item {pid}: {e}")
            return None
        finally:
            db.close()
    
    def bulk_sync_from_graphql_response(
        self,
        json_data: Dict,
        dry_run: bool = False
    ) -> Dict:
        """
        Bulk sync all training-eligible items from GraphQL response
        
        Args:
            json_data: GraphQL response JSON
            dry_run: If True, don't actually insert to database
        
        Returns:
            Sync statistics
        """
        parsed = self.parse_graphql_media_response(json_data)
        
        logger.info(f"""
GraphQL Sync Summary:
  Total items: {parsed['total_items']}
  Training-eligible (PDFs): {parsed['training_eligible_count']}
  JPG-only (not eligible): {parsed['jpg_only_count']}
  No media: {parsed['no_media_count']}
        """)
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for eligible in parsed['training_eligible']:
            item = eligible['item']
            file_type = eligible['type']  # 'pdf' or 'tiff'
            master_files = eligible['master_files']
            
            # Sync the first master file (primary)
            if master_files:
                master_file = master_files[0]  # Take first master
                
                result = self.sync_graphql_item_to_database(
                    item,
                    master_file,
                    file_type=file_type,
                    dry_run=dry_run
                )
                
                if result:
                    synced_count += 1
                    logger.info(f"Synced {file_type.upper()} for PID {item.get('pid')}")
                elif result is None:
                    error_count += 1
            else:
                skipped_count += 1
        
        return {
            'total_items': parsed['total_items'],
            'training_eligible': parsed['training_eligible_count'],
            'synced': synced_count,
            'skipped': skipped_count,
            'errors': error_count,
            'dry_run': dry_run
        }
    
    def get_training_corpus_pids(self) -> List[str]:
        """
        Get list of all PIDs currently in training corpus
        
        Returns:
            List of PID strings
        """
        db = LocalSessionLocal()
        try:
            from sqlalchemy import text
            result = db.execute(text(
                "SELECT pid FROM documents WHERE pid IS NOT NULL ORDER BY pid"
            ))
            pids = [row[0] for row in result]
            return pids
        finally:
            db.close()
    
    def validate_graphql_against_database(self, json_data: Dict) -> Dict:
        """
        Validate GraphQL response against current database state
        
        Shows which PIDs are in GraphQL but not in DB (need sync)
        and which PIDs are in DB but not in GraphQL (orphaned)
        
        Args:
            json_data: GraphQL response JSON
        
        Returns:
            Validation report
        """
        parsed = self.parse_graphql_media_response(json_data)
        
        # Get PIDs from GraphQL
        graphql_pids = set()
        for eligible in parsed['training_eligible']:
            pid = eligible['item'].get('pid')
            if pid:
                graphql_pids.add(pid)
        
        # Get PIDs from database
        db_pids = set(self.get_training_corpus_pids())
        
        # Compare
        needs_sync = graphql_pids - db_pids  # In GraphQL but not DB
        orphaned = db_pids - graphql_pids  # In DB but not GraphQL
        in_both = graphql_pids & db_pids  # Already synced
        
        return {
            'graphql_pid_count': len(graphql_pids),
            'database_pid_count': len(db_pids),
            'needs_sync': list(needs_sync),
            'needs_sync_count': len(needs_sync),
            'orphaned': list(orphaned),
            'orphaned_count': len(orphaned),
            'already_synced': list(in_both),
            'already_synced_count': len(in_both)
        }
