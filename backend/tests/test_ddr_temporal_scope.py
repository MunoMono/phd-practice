from datetime import date

from app.core.ddr_temporal_scope import is_within_ddr_scope


def test_allows_the_documented_ddr_boundary_dates():
    assert is_within_ddr_scope(1965, date(1965, 1, 1))
    assert is_within_ddr_scope(1985, date(1985, 7, 31))


def test_excludes_data_outside_the_documented_ddr_boundary():
    assert not is_within_ddr_scope(1964, date(1964, 12, 31))
    assert not is_within_ddr_scope(1985)
    assert not is_within_ddr_scope(1985, date(1985, 8, 1))
    assert not is_within_ddr_scope(1986, date(1986, 1, 1))
