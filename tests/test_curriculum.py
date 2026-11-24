"""School year groundwork."""
from datetime import date

from custom_components.learning_games.engine import curriculum as C


def test_academic_year_start():
    assert C.academic_year_start(date(2026, 11, 24)) == 2026
    assert C.academic_year_start(date(2027, 8, 31)) == 2026
    assert C.academic_year_start(date(2027, 9, 1)) == 2027


def test_year_moves_up_each_september():
    assert C.current_school_year(5, 2026, date(2026, 11, 24)) == 5
    assert C.current_school_year(5, 2026, date(2027, 8, 31)) == 5
    assert C.current_school_year(5, 2026, date(2027, 9, 1)) == 6
    assert C.current_school_year(5, 2026, date(2029, 9, 2)) == 8
    assert C.current_school_year(12, 2026, date(2030, 9, 2)) == 13  # capped
    assert C.current_school_year(5, None, date(2030, 9, 2)) == 5  # never set: no drift


def test_starting_bands():
    assert C.starting_band(5) == 1
    assert C.starting_band(6) == 2
    assert C.starting_band(7) == 3
    assert C.starting_band(9) == 3
    assert C.label(6) == "Year 6"
