"""ML eligibility policy helpers for archive PDF assets."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_RANGE_TOKEN_RE = re.compile(r"^([1-9]\d*)(?:\s*-\s*([1-9]\d*))?$")


def normalize_page_scope(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    return text or None


def parse_ml_pages(raw_value: Any) -> Dict[str, Any]:
    """Parse the observed archive page-scope syntax conservatively.

    Supported syntax is limited to the patterns observed in live data:
    comma-separated positive page numbers and inclusive ranges like
    "10, 23-24" or "19-20, 22-23". Blank means unrestricted.
    """
    normalized = normalize_page_scope(raw_value)
    if normalized is None:
        return {
            'is_restricted': False,
            'normalized_scope': None,
            'allowed_pages': None,
            'error': None,
        }

    allowed_pages: List[int] = []
    normalized_tokens: List[str] = []
    seen_pages = set()
    for token in normalized.split(','):
        part = token.strip()
        if not part:
            return {
                'is_restricted': True,
                'normalized_scope': normalized,
                'allowed_pages': None,
                'error': 'empty_page_token',
            }

        match = _RANGE_TOKEN_RE.match(part)
        if not match:
            return {
                'is_restricted': True,
                'normalized_scope': normalized,
                'allowed_pages': None,
                'error': 'unsupported_page_token',
            }

        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start:
            return {
                'is_restricted': True,
                'normalized_scope': normalized,
                'allowed_pages': None,
                'error': 'descending_page_range',
            }

        normalized_tokens.append(str(start) if start == end else f'{start}-{end}')
        for page_number in range(start, end + 1):
            if page_number not in seen_pages:
                seen_pages.add(page_number)
                allowed_pages.append(page_number)

    return {
        'is_restricted': True,
        'normalized_scope': ', '.join(normalized_tokens),
        'allowed_pages': allowed_pages,
        'error': None,
    }


def evaluate_ml_policy(
    *,
    asset_present: bool,
    asset_use_for_ml: Optional[bool],
    ml_pages: Any,
) -> Dict[str, Any]:
    """Evaluate archive ML policy using asset metadata as the authoritative source."""
    if not asset_present:
        return {
            'use_for_ml': None,
            'ml_page_scope': normalize_page_scope(ml_pages),
            'ml_allowed_pages': None,
            'ml_policy_status': 'policy_unresolved',
            'ml_exclusion_reason': 'missing_matching_pdf_master_asset',
        }

    if asset_use_for_ml is False:
        return {
            'use_for_ml': False,
            'ml_page_scope': normalize_page_scope(ml_pages),
            'ml_allowed_pages': None,
            'ml_policy_status': 'excluded_use_for_ml_false',
            'ml_exclusion_reason': 'asset_marked_use_for_ml_false',
        }

    if asset_use_for_ml is not True:
        return {
            'use_for_ml': None,
            'ml_page_scope': normalize_page_scope(ml_pages),
            'ml_allowed_pages': None,
            'ml_policy_status': 'policy_unresolved',
            'ml_exclusion_reason': 'missing_asset_use_for_ml_flag',
        }

    parsed = parse_ml_pages(ml_pages)
    if parsed['error']:
        return {
            'use_for_ml': True,
            'ml_page_scope': parsed['normalized_scope'],
            'ml_allowed_pages': None,
            'ml_policy_status': 'policy_unresolved',
            'ml_exclusion_reason': f"invalid_ml_pages:{parsed['error']}",
        }

    if not parsed['is_restricted']:
        return {
            'use_for_ml': True,
            'ml_page_scope': 'all_pages',
            'ml_allowed_pages': None,
            'ml_policy_status': 'eligible_unrestricted',
            'ml_exclusion_reason': None,
        }

    return {
        'use_for_ml': True,
        'ml_page_scope': parsed['normalized_scope'],
        'ml_allowed_pages': parsed['allowed_pages'],
        'ml_policy_status': 'eligible_page_restricted',
        'ml_exclusion_reason': None,
    }