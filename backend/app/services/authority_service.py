"""
Authority Service - Fetch and validate PIDs from DDR Archive GraphQL
Ensures only authority-linked assets enter the training corpus
"""
import logging
import requests
from typing import Optional, Dict, List
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthorityService:
    """
    Service for interacting with DDR Archive GraphQL API
    
    Validates PIDs and fetches authority metadata to enrich documents
    """
    
    def __init__(self):
        self.graphql_endpoint = settings.DDR_GRAPHQL_ENDPOINT
        self.api_token = settings.DDR_API_TOKEN
    
    def _make_graphql_request(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Make GraphQL request to DDR Archive API"""
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            
            if self.api_token:
                headers['Authorization'] = f'Bearer {self.api_token}'
            
            payload = {
                'query': query,
                'variables': variables or {}
            }
            
            response = requests.post(
                self.graphql_endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"GraphQL request failed: {e}")
            return None
    
    def validate_pid(self, pid: str) -> bool:
        """
        Validate that a PID exists in DDR Archive authorities
        
        Args:
            pid: Postgres authority PID to validate
        
        Returns:
            True if PID is valid and exists in authorities
        """
        query = """
        query ValidatePID($pid: String!) {
            authority(pid: $pid) {
                pid
                id
            }
        }
        """
        
        result = self._make_graphql_request(query, {'pid': pid})
        
        if not result:
            logger.warning(f"Could not validate PID {pid} - GraphQL unavailable")
            return False
        
        # Check if authority exists
        data = result.get('data', {})
        authority = data.get('authority')
        
        if authority and authority.get('pid') == pid:
            logger.info(f"PID {pid} validated successfully")
            return True
        
        logger.warning(f"PID {pid} not found in DDR Archive authorities")
        return False
    
    def get_authority_metadata(self, pid: str) -> Optional[Dict]:
        """
        Fetch full authority metadata for a PID from DDR Archive
        
        This enriches document records with captions, descriptive metadata,
        and contextual information from the authorities database
        
        Args:
            pid: Postgres authority PID
        
        Returns:
            Authority metadata dict or None if not found
        """
        query = """
        query GetAuthority($pid: String!) {
            authority(pid: $pid) {
                pid
                id
                title
                description
                caption
                creator
                date
                subject
                type
                format
                language
                coverage
                rights
                digitalAssets {
                    s3Key
                    fileType
                    fileSize
                    caption
                }
            }
        }
        """
        
        result = self._make_graphql_request(query, {'pid': pid})
        
        if not result:
            return None
        
        data = result.get('data', {})
        authority = data.get('authority')
        
        if authority:
            logger.info(f"Fetched authority metadata for PID {pid}")
            return authority
        
        logger.warning(f"No authority metadata found for PID {pid}")
        return None
    
    def get_all_valid_pids(self, limit: int = 10000) -> List[str]:
        """
        Fetch all valid PIDs from DDR Archive authorities
        
        Use this to build the allowlist of training-eligible assets
        
        Args:
            limit: Maximum number of PIDs to fetch
        
        Returns:
            List of valid PID strings
        """
        query = """
        query GetAllPIDs($limit: Int!) {
            authorities(limit: $limit) {
                pid
            }
        }
        """
        
        result = self._make_graphql_request(query, {'limit': limit})
        
        if not result:
            logger.error("Could not fetch PIDs from DDR Archive")
            return []
        
        data = result.get('data', {})
        authorities = data.get('authorities', [])
        
        pids = [auth['pid'] for auth in authorities if auth.get('pid')]
        
        logger.info(f"Fetched {len(pids)} valid PIDs from DDR Archive")
        return pids
    
    def sync_authority_to_document(self, document_id: str, pid: str) -> bool:
        """
        Fetch authority metadata and sync to document record
        
        Enriches document with GraphQL metadata (captions, descriptive data)
        
        Args:
            document_id: Local document ID to enrich
            pid: Authority PID to fetch metadata for
        
        Returns:
            True if sync successful
        """
        from app.core.database import LocalSessionLocal
        from app.models.document import Document
        
        # Fetch authority metadata
        metadata = self.get_authority_metadata(pid)
        
        if not metadata:
            logger.error(f"Cannot sync - no metadata for PID {pid}")
            return False
        
        # Update document with authority data
        db = LocalSessionLocal()
        try:
            doc = db.query(Document).filter(
                Document.document_id == document_id
            ).first()
            
            if not doc:
                logger.error(f"Document {document_id} not found")
                return False
            
            # Cache authority metadata
            doc.authority_data = metadata
            doc.authority_id = metadata.get('id')
            
            # Enrich title if not set
            if not doc.title and metadata.get('title'):
                doc.title = metadata['title']
            
            db.commit()
            logger.info(f"Synced authority metadata for document {document_id} (PID: {pid})")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing authority to document: {e}")
            return False
        finally:
            db.close()
