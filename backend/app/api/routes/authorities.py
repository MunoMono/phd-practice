import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.database import LocalSessionLocal
from app.services.database_authorities_sync import get_authority_inventory, sync_all_authorities_with_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/inventory')
async def authority_inventory():
    inventory = get_authority_inventory()
    return {
        'count': len(inventory),
        'authority_types': inventory,
    }


@router.get('/register')
async def authority_register(authority_type: Optional[str] = None, category: Optional[str] = None, limit: int = 200):
    db = LocalSessionLocal()
    try:
        clauses = []
        params = {'limit': limit}
        if authority_type:
            clauses.append('authority_type = :authority_type')
            params['authority_type'] = authority_type
        if category:
            clauses.append('category = :category')
            params['category'] = category

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        rows = db.execute(
            text(
                f"""
                SELECT authority_type, authority_id, code, label, description, category, metadata, synced_at
                FROM database_authorities
                {where_clause}
                ORDER BY authority_type, label
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()

        inventory_map = {item['authority_type']: item for item in get_authority_inventory()}
        records = [
            {
                'authority_type': row[0],
                'authority_id': row[1],
                'code': row[2],
                'label': row[3],
                'description': row[4],
                'category': row[5],
                'metadata': row[6] or {},
                'synced_at': row[7].isoformat() if row[7] else None,
                'allowed_roles': inventory_map.get(row[0], {}).get('allowed_roles', ['structural_context']),
            }
            for row in rows
        ]

        return {
            'count': len(records),
            'records': records,
        }
    except Exception as exc:
        logger.error(f'Failed to load authority register: {exc}')
        raise HTTPException(status_code=500, detail='Failed to load authority register')
    finally:
        db.close()


@router.get('/summary')
async def authority_summary():
    db = LocalSessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT authority_type, category, COUNT(*) AS count, MAX(synced_at) AS last_synced_at
                FROM database_authorities
                GROUP BY authority_type, category
                ORDER BY authority_type
                """
            )
        ).fetchall()
        inventory_map = {item['authority_type']: item for item in get_authority_inventory()}
        summary = [
            {
                'authority_type': row[0],
                'category': row[1],
                'count': row[2],
                'last_synced_at': row[3].isoformat() if row[3] else None,
                'allowed_roles': inventory_map.get(row[0], {}).get('allowed_roles', ['structural_context']),
            }
            for row in rows
        ]
        return {
            'count': len(summary),
            'authority_types': summary,
        }
    except Exception as exc:
        logger.error(f'Failed to load authority summary: {exc}')
        raise HTTPException(status_code=500, detail='Failed to load authority summary')
    finally:
        db.close()


@router.post('/sync')
async def sync_authority_register():
    try:
        return sync_all_authorities_with_report()
    except Exception as exc:
        logger.error(f'Authority register sync failed: {exc}')
        raise HTTPException(status_code=500, detail=f'Authority register sync failed: {exc}')