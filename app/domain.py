"""Meteorological domain helpers used by the Cyclone-AI MVP.

The thresholds in this module are an explicit *demo policy*. They are kept out
of the user interface and returned with a policy identifier so that a reviewed
institutional profile can replace them without changing API consumers.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable

CATEGORY_PROFILE_ID = "imd-demo-scale@1.0"
RI_DEFINITION_ID = "delta-vmax-gte-30kt-in-24h@1.0"
RI_ALERT_THRESHOLD = 0.65

# Lower-bound thresholds in knots. Values are evaluated from strongest to
# weakest, which avoids gaps for fractional/interpolated wind speeds.
IMD_CATEGORY_THRESHOLDS: tuple[tuple[float, str, str], ...] = (
    (120.0, "Super Cyclonic Storm", "SuCS"),
    (90.0, "Extremely Severe Cyclonic Storm", "ESCS"),
    (64.0, "Very Severe Cyclonic Storm", "VSCS"),
    (48.0, "Severe Cyclonic Storm", "SCS"),
    (34.0, "Cyclonic Storm", "CS"),
    (28.0, "Deep Depression", "DD"),
    (17.0, "Depression", "D"),
    (0.0, "Low Pressure Area", "LPA"),
)

CATEGORY_TONE = {
    "Low Pressure Area": "slate",
    "Depression": "cyan",
    "Deep Depression": "blue",
    "Cyclonic Storm": "amber",
    "Severe Cyclonic Storm": "orange",
    "Very Severe Cyclonic Storm": "red",
    "Extremely Severe Cyclonic Storm": "crimson",
    "Super Cyclonic Storm": "purple",
    "Unknown": "slate",
}


def imd_category(vmax_kt: float) -> dict[str, str]:
    """Return the demo IMD category for a continuous wind value.

    Fractional values are intentionally supported; the former prototype used
    inclusive integer ranges and classified 27.5 kt as ``Unknown``.
    """

    if not math.isfinite(vmax_kt) or vmax_kt < 0:
        return {"name": "Unknown", "code": "UNK", "tone": "slate"}
    for lower_bound, name, code in IMD_CATEGORY_THRESHOLDS:
        if vmax_kt >= lower_bound:
            return {"name": name, "code": code, "tone": CATEGORY_TONE[name]}
    return {"name": "Unknown", "code": "UNK", "tone": "slate"}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def parse_utc(value: str) -> datetime:
    """Parse repository timestamps and return an aware UTC datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def median(values: Iterable[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("median requires at least one value")
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(
        phi2
    ) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def compass_direction(bearing: float) -> str:
    directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return directions[round(bearing / 45.0) % 8]


def logistic(value: float) -> float:
    # Avoid overflow when a malformed/extreme input reaches the demo rule.
    bounded = clamp(value, -60.0, 60.0)
    return 1.0 / (1.0 + math.exp(-bounded))
