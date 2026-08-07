"""
Authority Service - Fetch and validate PIDs from DDR Archive GraphQL
Ensures only authority-linked assets enter the training corpus
"""
import logging
import requests
from typing import Any, Optional, Dict, List
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

    PUBLISHED_RECORDS_QUERY = """
    query GetPublishedRecords($status: String!) {
        records_v1(status: $status) {
            id
            pid
            title
            public_uri
            language_codes
            reference_code
            location_repository
            location_accession
            location_box
            box_title
            location_note
            access_level
            rights_owner
            rights_holders
            copyright_holder
            copyright_holder_other
            data_rights
            data_rights_holder
            image_rights
            image_rights_holder
            rights_statement_uri
            current_consent_status
            current_consent_scope
            consent_evidence_uri
            takedown_contact
            attached_media {
                id
                pid
                title
                public_uri
                creator_agent_label
                creators
                level
                fonds_code
                language_codes
                date_begin
                date_end
                series_id
                ddr_period
                artefact_date_from
                artefact_date_to
                category
                reference_code
                extent_number
                extent_unit
                scope_and_content
                methodology
                project_theme
                project_title
                location_repository
                location_accession
                location_box
                box_title
                location_note
                current_consent_status
                current_consent_scope
                consent_evidence_uri
                takedown_contact
                access_level
                rights_owner
                copyright_holder
                copyright_holder_other
                rights_holders
                data_rights
                data_rights_holder
                image_rights
                image_rights_holder
                rights_statement_uri
                abstract
                caption
                subjects
                keywords {
                    id
                    label
                }
                parent_collection
                used_for_ml
                ml_annotation
                pdf_files {
                    filename
                    role
                    url
                    label
                }
                digital_assets {
                    role
                    filename
                    assetId
                    pid
                    use_for_ml
                    ml_pages
                    ml_annotation
                    mime
                    bytes
                    status
                    sequence
                    label
                    display_date
                    normalized_date
                    date_qualifier
                    date_unknown
                    copyright_holder
                    rights_holders
                    data_rights
                    data_rights_holder
                    image_rights
                    image_rights_holder
                    extent_number
                    extent_unit
                    location_repository
                    location_accession
                    location_box
                    location_note
                    language_codes
                    keywords {
                        id
                        label
                    }
                }
            }
        }
    }
    """

    RECORD_BY_PID_QUERY = """
    query GetRecordByPid($pid: ID!) {
        record_v1(id: $pid) {
            id
            pid
            title
            public_uri
            language_codes
            reference_code
            location_repository
            location_accession
            location_box
            box_title
            location_note
            access_level
            rights_owner
            rights_holders
            copyright_holder
            copyright_holder_other
            data_rights
            data_rights_holder
            image_rights
            image_rights_holder
            rights_statement_uri
            current_consent_status
            current_consent_scope
            consent_evidence_uri
            takedown_contact
            attached_media {
                id
                pid
                title
                public_uri
                creator_agent_label
                creators
                level
                fonds_code
                language_codes
                date_begin
                date_end
                series_id
                ddr_period
                artefact_date_from
                artefact_date_to
                category
                reference_code
                extent_number
                extent_unit
                scope_and_content
                methodology
                project_theme
                project_title
                location_repository
                location_accession
                location_box
                box_title
                location_note
                current_consent_status
                current_consent_scope
                consent_evidence_uri
                takedown_contact
                access_level
                rights_owner
                copyright_holder
                copyright_holder_other
                rights_holders
                data_rights
                data_rights_holder
                image_rights
                image_rights_holder
                rights_statement_uri
                abstract
                caption
                subjects
                keywords {
                    id
                    label
                }
                parent_collection
                used_for_ml
                ml_annotation
                pdf_files {
                    filename
                    role
                    url
                    label
                }
                digital_assets {
                    role
                    filename
                    assetId
                    pid
                    use_for_ml
                    ml_pages
                    ml_annotation
                    mime
                    bytes
                    status
                    sequence
                    label
                    display_date
                    normalized_date
                    date_qualifier
                    date_unknown
                    copyright_holder
                    rights_holders
                    data_rights
                    data_rights_holder
                    image_rights
                    image_rights_holder
                    extent_number
                    extent_unit
                    location_repository
                    location_accession
                    location_box
                    location_note
                    language_codes
                    keywords {
                        id
                        label
                    }
                }
            }
        }
    }
    """

    SEARCH_MEDIA_ITEMS_QUERY = """
    query SearchMediaItems($query: String, $excludeAttached: Boolean!, $limit: Int!) {
        search_media_items(query: $query, exclude_attached: $excludeAttached, limit: $limit) {
            id
            pid
            title
            public_uri
            creator_agent_label
            creators
            date_begin
            date_end
            level
            fonds_code
            language_codes
            series_id
            ddr_period
            artefact_date_from
            artefact_date_to
            category
            reference_code
            extent_number
            extent_unit
            scope_and_content
            methodology
            project_theme
            project_title
            location_repository
            location_accession
            location_box
            box_title
            location_note
            current_consent_status
            current_consent_scope
            consent_evidence_uri
            takedown_contact
            access_level
            rights_owner
            copyright_holder
            copyright_holder_other
            rights_holders
            data_rights
            data_rights_holder
            image_rights
            image_rights_holder
            rights_statement_uri
            abstract
            caption
            subjects
            keywords {
                id
                label
            }
            parent_collection
            used_for_ml
            ml_annotation
            pdf_files {
                filename
                role
                url
                label
            }
            digital_assets {
                role
                filename
                assetId
                pid
                use_for_ml
                ml_pages
                ml_annotation
                mime
                bytes
                status
                sequence
                label
                display_date
                normalized_date
                date_qualifier
                date_unknown
                copyright_holder
                rights_holders
                data_rights
                data_rights_holder
                image_rights
                image_rights_holder
                extent_number
                extent_unit
                location_repository
                location_accession
                location_box
                location_note
                language_codes
                keywords {
                    id
                    label
                }
            }
        }
    }
    """

    ALL_MEDIA_ITEMS_QUERY = """
    query GetAllMediaItems {
        all_media_items {
            pid
        }
    }
    """
    
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

    @staticmethod
    def _unwrap_data(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not result:
            return {}
        return result.get('data') or {}

    def search_media_items(
        self,
        query_text: str,
        limit: int = 10,
        exclude_attached: bool = False,
    ) -> List[Dict[str, Any]]:
        result = self._make_graphql_request(
            self.SEARCH_MEDIA_ITEMS_QUERY,
            {
                'query': query_text,
                'excludeAttached': exclude_attached,
                'limit': limit,
            },
        )
        data = self._unwrap_data(result)
        return data.get('search_media_items') or []

    def get_media_item_metadata(self, pid: str) -> Optional[Dict[str, Any]]:
        candidates = self.search_media_items(pid, limit=10, exclude_attached=False)
        exact_matches = [item for item in candidates if item.get('pid') == pid]
        if exact_matches:
            return exact_matches[0]
        return None

    def fetch_published_records(self, status: str = 'published') -> List[Dict[str, Any]]:
        result = self._make_graphql_request(self.PUBLISHED_RECORDS_QUERY, {'status': status})
        data = self._unwrap_data(result)
        records = data.get('records_v1') or []
        logger.info("Fetched %s published archive records from GraphQL", len(records))
        return records

    def fetch_record_by_pid(self, pid: str) -> Optional[Dict[str, Any]]:
        result = self._make_graphql_request(self.RECORD_BY_PID_QUERY, {'pid': pid})
        data = self._unwrap_data(result)
        record = data.get('record_v1')
        if record:
            logger.info("Fetched archive record %s from GraphQL", pid)
        else:
            logger.warning("No archive record found for PID %s", pid)
        return record
    
    def validate_pid(self, pid: str) -> bool:
        """
        Validate that a PID exists in DDR Archive authorities
        
        Args:
            pid: Postgres authority PID to validate
        
        Returns:
            True if PID is valid and exists in authorities
        """
        metadata = self.get_media_item_metadata(pid)
        if metadata is None:
            logger.warning(f"Could not validate PID {pid} - GraphQL unavailable")
            return False

        if metadata.get('pid') == pid:
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
        authority = self.get_media_item_metadata(pid)
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
        result = self._make_graphql_request(self.ALL_MEDIA_ITEMS_QUERY)
        if not result:
            logger.error("Could not fetch PIDs from DDR Archive")
            return []

        data = self._unwrap_data(result)
        authorities = data.get('all_media_items', [])

        pids = sorted({auth['pid'] for auth in authorities if auth.get('pid')})
        if limit:
            pids = pids[:limit]
        
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
            doc.metadata_source = 'archive_graphql.search_media_items'
            
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
