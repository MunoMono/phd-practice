"""
Database Authorities Sync Service

Syncs controlled vocabulary authorities from DDR Archive GraphQL API.

5 Core Intended Categories (provenance/attribution):
  - agent_employment: DDR staff with roles and tenure
  - ddr_projects: Project register with funders and leads
  - ref_students: Students with degrees and thesis titles
  - ref_fonds: Archival fonds groupings
  - ref_publication_type: Publication type taxonomy

6 Critical Categories (ML ground truth labels):
  - ref_epistemic_stance: Epistemological positioning
  - ref_methodology: Research methodologies
  - ref_project_theme: Research themes/domains
  - ref_ddr_period: Historical periods
  - ref_beneficiary_audience: Intended audiences
  - ref_project_outcome: Project outcome types

Usage:
    python -m app.services.database_authorities_sync
"""

import requests
import json
from sqlalchemy import text
from app.core.database import LocalSessionLocal
from app.core.logging import logger

DDR_GRAPHQL_URL = "https://api.ddrarchive.org/graphql"

# Define all 11 authority types with their queries and mappings
AUTHORITY_DEFINITIONS = {
    # 5 CORE INTENDED CATEGORIES (provenance)
    "agent_employment": {
        "category": "core",
        "query": """
        {
          agent_employment {
            staff_code
            agent_name
            job_title_code
            job_title_label
            start_date
            end_date
            is_primary
          }
        }
        """,
        "id_field": "staff_code",
        "label_field": "agent_name",
        "metadata_fields": ["job_title_code", "job_title_label", "start_date", "end_date", "is_primary"]
    },
    "ddr_projects": {
        "category": "core",
        "query": """
        {
          ddr_projects {
            job_number
            title
            funder_name
            duration_text
            project_lead_name
          }
        }
        """,
        "id_field": "job_number",
        "label_field": "title",
        "metadata_fields": ["funder_name", "duration_text", "project_lead_name"]
    },
    "ref_students": {
        "category": "core",
        "query": """
        {
          ref_students {
            label
            year
            degree
            thesis_title
          }
        }
        """,
        "id_field": "label",  # Use label as ID since no explicit ID field
        "label_field": "label",
        "metadata_fields": ["year", "degree", "thesis_title"]
    },
    "ref_fonds": {
        "category": "core",
        "query": """
        {
          ref_fonds {
            id
            code
            label
            notes
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "code_field": "code",
        "description_field": "notes",
        "metadata_fields": []
    },
    "ref_publication_type": {
        "category": "core",
        "query": """
        {
          ref_publication_type {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    
    # 6 CRITICAL CATEGORIES (ML labels)
    "ref_epistemic_stance": {
        "category": "critical",
        "query": """
        {
          ref_epistemic_stance {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    "ref_methodology": {
        "category": "critical",
        "query": """
        {
          ref_methodology {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    "ref_project_theme": {
        "category": "critical",
        "query": """
        {
          ref_project_theme {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    "ref_ddr_period": {
        "category": "critical",
        "query": """
        {
          ref_ddr_period {
            slug
            label
            description
          }
        }
        """,
        "id_field": "slug",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    "ref_beneficiary_audience": {
        "category": "critical",
        "query": """
        {
          ref_beneficiary_audience {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    },
    "ref_project_outcome": {
        "category": "critical",
        "query": """
        {
          ref_project_outcome {
            id
            label
            description
          }
        }
        """,
        "id_field": "id",
        "label_field": "label",
        "description_field": "description",
        "metadata_fields": []
    }
}


def fetch_authority_data(authority_type: str, query: str) -> list:
    """Fetch authority data from DDR GraphQL API."""
    try:
        response = requests.post(DDR_GRAPHQL_URL, json={"query": query}, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            logger.error(f"GraphQL errors for {authority_type}: {result['errors']}")
            return []
        
        if "data" not in result or not result["data"]:
            logger.warning(f"No data returned for {authority_type}")
            return []
        
        data = result["data"].get(authority_type, [])
        logger.info(f"Fetched {len(data)} records for {authority_type}")
        return data
    
    except Exception as e:
        logger.error(f"Failed to fetch {authority_type}: {e}")
        return []


def sync_authority(db, authority_type: str, config: dict):
    """Sync a single authority type to the database."""
    logger.info(f"Syncing {authority_type}...")
    
    # Fetch data from GraphQL
    data = fetch_authority_data(authority_type, config["query"])
    if not data:
        logger.warning(f"No data to sync for {authority_type}")
        return 0
    
    category = config["category"]
    id_field = config["id_field"]
    label_field = config["label_field"]
    code_field = config.get("code_field")
    description_field = config.get("description_field")
    metadata_fields = config.get("metadata_fields", [])
    
    synced_count = 0
    
    for item in data:
        authority_id = str(item.get(id_field))
        if not authority_id:
            continue
        
        label = item.get(label_field, "")
        code = item.get(code_field) if code_field else None
        description = item.get(description_field) if description_field else None
        
        # Build metadata JSON from specified fields
        metadata = {}
        for field in metadata_fields:
            if field in item:
                metadata[field] = item[field]
        
        # Upsert the authority record
        try:
            db.execute(
                text("""
                    INSERT INTO database_authorities 
                        (authority_type, authority_id, code, label, description, category, metadata, synced_at)
                    VALUES 
                        (:type, :id, :code, :label, :desc, :cat, CAST(:meta AS jsonb), NOW())
                    ON CONFLICT (authority_type, authority_id) 
                    DO UPDATE SET
                        code = EXCLUDED.code,
                        label = EXCLUDED.label,
                        description = EXCLUDED.description,
                        metadata = EXCLUDED.metadata,
                        synced_at = NOW()
                """),
                {
                    "type": authority_type,
                    "id": authority_id,
                    "code": code,
                    "label": label,
                    "desc": description,
                    "cat": category,
                    "meta": json.dumps(metadata) if metadata else "{}"
                }
            )
            synced_count += 1
        except Exception as e:
            logger.error(f"Failed to insert {authority_type}/{authority_id}: {e}")
            continue
    
    db.commit()
    logger.info(f"✓ Synced {synced_count} {authority_type} records")
    return synced_count


def sync_all_authorities():
    """Sync all 11 database authority types."""
    logger.info("=" * 70)
    logger.info("DATABASE AUTHORITIES SYNC - Starting")
    logger.info("=" * 70)
    
    db = LocalSessionLocal()
    
    try:
        total_synced = 0
        core_count = 0
        critical_count = 0
        
        for authority_type, config in AUTHORITY_DEFINITIONS.items():
            count = sync_authority(db, authority_type, config)
            total_synced += count
            
            if config["category"] == "core":
                core_count += count
            else:
                critical_count += count
        
        logger.info("=" * 70)
        logger.info(f"SYNC COMPLETE: {total_synced} total records")
        logger.info(f"  Core authorities: {core_count} records (5 types)")
        logger.info(f"  Critical authorities: {critical_count} records (6 types)")
        logger.info("=" * 70)
        
        return total_synced
    
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sync_all_authorities()
