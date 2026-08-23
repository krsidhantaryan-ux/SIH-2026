from math import nan

import pytest

from app.domain import imd_category


@pytest.mark.parametrize(
    ("wind", "expected"),
    [
        (0.0, "Low Pressure Area"),
        (16.9, "Low Pressure Area"),
        (17.0, "Depression"),
        (27.5, "Depression"),
        (28.0, "Deep Depression"),
        (33.9, "Deep Depression"),
        (34.0, "Cyclonic Storm"),
        (48.0, "Severe Cyclonic Storm"),
        (64.0, "Very Severe Cyclonic Storm"),
        (90.0, "Extremely Severe Cyclonic Storm"),
        (120.0, "Super Cyclonic Storm"),
        (-1.0, "Unknown"),
        (nan, "Unknown"),
    ],
)
def test_category_boundaries_are_continuous(wind: float, expected: str) -> None:
    assert imd_category(wind)["name"] == expected
