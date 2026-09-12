"""Canonical temporal boundary for Department of Design Research research data."""

from datetime import date, datetime
from typing import Optional, Union

DDR_START_DATE = date(1965, 1, 1)
DDR_END_DATE = date(1985, 7, 31)
DDR_END_EXCLUSIVE_DATE = date(1985, 8, 1)
DDR_START_YEAR = DDR_START_DATE.year
DDR_END_YEAR = DDR_END_DATE.year

PublicationDate = Union[date, datetime]


def parse_publication_date(value: Optional[Union[str, PublicationDate]]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip().replace("Z", "+00:00")[:10])


def is_within_ddr_scope(publication_year: Optional[int], publication_date: Optional[Union[str, PublicationDate]] = None) -> bool:
    if publication_year is None:
        return False
    if publication_year < DDR_START_YEAR or publication_year > DDR_END_YEAR:
        return False
    if publication_year < DDR_END_YEAR:
        return True

    dated_value = parse_publication_date(publication_date)
    return dated_value is not None and DDR_START_DATE <= dated_value <= DDR_END_DATE


DDR_DOCUMENT_SQL_SCOPE = """
    (d.publication_year BETWEEN 1965 AND 1984
     OR (d.publication_year = 1985
         AND d.publication_date >= DATE '1985-01-01'
         AND d.publication_date < DATE '1985-08-01'))
"""
