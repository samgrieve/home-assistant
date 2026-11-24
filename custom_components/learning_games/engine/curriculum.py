"""School-year groundwork: which UK year group she's in, and where unpractised
skills should start. Pure Python.

The year moves up automatically every 1 September, counted from the academic
year in which a parent last set it.
"""
from __future__ import annotations

from datetime import date

MIN_YEAR = 3
MAX_YEAR = 13
SETTABLE_YEARS = range(3, 10)  # Year 3 to Year 9 in the options flow
DEFAULT_YEAR = 5

# Current question content spans roughly Year 4 (band 1) to Year 6 (band 5).
# Years 7+ need new KS3 content (a later release); until then they start high.
_START_BANDS = {3: 1, 4: 1, 5: 1, 6: 2}
START_BAND_KS3 = 3


def academic_year_start(today: date) -> int:
    """Calendar year in which the current academic year began (1 September)."""
    return today.year if today.month >= 9 else today.year - 1


def current_school_year(base_year: int, set_in: int | None, today: date) -> int:
    if set_in is None:
        set_in = academic_year_start(today)
    year = base_year + max(0, academic_year_start(today) - set_in)
    return max(MIN_YEAR, min(MAX_YEAR, year))


def starting_band(school_year: int) -> int:
    return _START_BANDS.get(school_year, START_BAND_KS3 if school_year >= 7 else 1)


def label(school_year: int) -> str:
    return f"Year {school_year}"
