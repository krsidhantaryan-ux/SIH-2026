"""CSV-backed historical storm repository for the Cyclone-AI demonstration."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from app.domain import (
    CATEGORY_PROFILE_ID,
    RI_ALERT_THRESHOLD,
    RI_DEFINITION_ID,
    bearing_degrees,
    clamp,
    compass_direction,
    haversine_km,
    imd_category,
    iso_utc,
    logistic,
    median,
    parse_utc,
)


@dataclass(frozen=True)
class SourceRow:
    sid: str
    name: str
    valid_time: datetime
    satellite: str
    vmax_kt: float
    latitude: float
    longitude: float
    eye_probability: float | None


class DatasetError(RuntimeError):
    """Raised when the committed demonstration dataset is unavailable/invalid."""


class StormRepository:
    """Loads and derives a compact historical replay from the committed index."""

    REQUIRED_COLUMNS: ClassVar[frozenset[str]] = frozenset(
        {"sid", "name", "time", "sat", "vmax", "lat", "lon", "eye_prob"}
    )

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.loaded_at: datetime | None = None
        self._storms: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        if not self.index_path.is_file():
            raise DatasetError(f"Dataset index not found: {self.index_path}")

        with self.index_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = self.REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise DatasetError(
                    f"Dataset index is missing columns: {', '.join(sorted(missing))}"
                )
            rows = [self._parse_row(raw) for raw in reader]

        if not rows:
            raise DatasetError("Dataset index contains no observations")

        grouped: dict[str, list[SourceRow]] = defaultdict(list)
        for row in rows:
            grouped[row.sid].append(row)

        self._storms = {
            sid: self._build_storm(sid, storm_rows)
            for sid, storm_rows in grouped.items()
        }
        self.loaded_at = datetime.now().astimezone()

    @staticmethod
    def _optional_float(value: str | None) -> float | None:
        if value is None or not value.strip():
            return None
        return float(value)

    @classmethod
    def _parse_row(cls, raw: dict[str, str]) -> SourceRow:
        try:
            return SourceRow(
                sid=raw["sid"].strip(),
                name=raw["name"].strip(),
                valid_time=parse_utc(raw["time"].strip()),
                satellite=raw["sat"].strip(),
                vmax_kt=float(raw["vmax"]),
                latitude=float(raw["lat"]),
                longitude=float(raw["lon"]),
                eye_probability=cls._optional_float(raw.get("eye_prob")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetError(f"Invalid dataset row: {raw!r}") from exc

    @staticmethod
    def _find_prior(
        points: list[dict[str, Any]], index: int, hours: float
    ) -> dict[str, Any] | None:
        target = parse_utc(points[index]["valid_time"]) - timedelta(hours=hours)
        candidates = [
            point
            for point in points[: index + 1]
            if parse_utc(point["valid_time"]) <= target
        ]
        return candidates[-1] if candidates else None

    @staticmethod
    def _find_nearest(
        points: list[dict[str, Any]], target: datetime
    ) -> dict[str, Any] | None:
        if not points:
            return None
        nearest = min(
            points,
            key=lambda point: abs(
                (parse_utc(point["valid_time"]) - target).total_seconds()
            ),
        )
        if abs((parse_utc(nearest["valid_time"]) - target).total_seconds()) > 4 * 3600:
            return None
        return nearest

    @staticmethod
    def _linear_slope(points: list[dict[str, Any]], index: int) -> float:
        """Least-squares intensity trend using only the latest five past points."""

        window = points[max(0, index - 4) : index + 1]
        if len(window) < 2:
            return 0.0
        origin = parse_utc(window[0]["valid_time"])
        x = [
            (parse_utc(point["valid_time"]) - origin).total_seconds() / 3600.0
            for point in window
        ]
        y = [float(point["vmax_kt"]) for point in window]
        x_mean, y_mean = sum(x) / len(x), sum(y) / len(y)
        denominator = sum((value - x_mean) ** 2 for value in x)
        if denominator == 0:
            return 0.0
        return (
            sum(
                (x_value - x_mean) * (y_value - y_mean)
                for x_value, y_value in zip(x, y, strict=True)
            )
            / denominator
        )

    def _add_derived_values(self, points: list[dict[str, Any]]) -> None:
        for index, point in enumerate(points):
            if index:
                previous = points[index - 1]
                elapsed_hours = max(
                    0.01,
                    (
                        parse_utc(point["valid_time"])
                        - parse_utc(previous["valid_time"])
                    ).total_seconds()
                    / 3600.0,
                )
                distance = haversine_km(
                    previous["latitude"],
                    previous["longitude"],
                    point["latitude"],
                    point["longitude"],
                )
                bearing = bearing_degrees(
                    previous["latitude"],
                    previous["longitude"],
                    point["latitude"],
                    point["longitude"],
                )
                point["motion"] = {
                    "speed_kmh": round(distance / elapsed_hours, 1),
                    "bearing_degrees": round(bearing, 0),
                    "direction": compass_direction(bearing),
                }
            else:
                point["motion"] = {
                    "speed_kmh": 0.0,
                    "bearing_degrees": 0.0,
                    "direction": "—",
                }

            prior_12 = self._find_prior(points, index, 12)
            prior_24 = self._find_prior(points, index, 24)
            point["change_12h_kt"] = (
                round(point["vmax_kt"] - prior_12["vmax_kt"], 1) if prior_12 else None
            )
            point["change_24h_kt"] = (
                round(point["vmax_kt"] - prior_24["vmax_kt"], 1) if prior_24 else None
            )

            slope = clamp(self._linear_slope(points, index), -5.0, 5.0)
            projected_change = slope * 24.0 * 0.62
            ri_probability = clamp(
                logistic((projected_change - 30.0) / 8.0), 0.02, 0.96
            )
            point["trend_kt_per_hour"] = round(slope, 2)
            point["ri"] = {
                "probability": round(ri_probability, 3),
                "threshold": RI_ALERT_THRESHOLD,
                "definition_id": RI_DEFINITION_ID,
                "definition": "Increase of at least 30 kt within 24 hours",
                "alert_eligible": ri_probability >= RI_ALERT_THRESHOLD,
                "method": "Past-only linear-trend baseline",
            }

            forecasts = []
            base_time = parse_utc(point["valid_time"])
            for horizon in (6, 12, 24):
                damping = 0.82 if horizon == 6 else 0.72 if horizon == 12 else 0.62
                change = clamp(slope * horizon * damping, -45.0, 45.0)
                central = clamp(point["vmax_kt"] + change, 10.0, 160.0)
                uncertainty = 7.0 + horizon * 0.45
                target_time = base_time + timedelta(hours=horizon)
                actual = self._find_nearest(points[index + 1 :], target_time)
                forecasts.append(
                    {
                        "horizon_hours": horizon,
                        "valid_time": iso_utc(target_time),
                        "vmax_kt": round(central, 1),
                        "change_kt": round(change, 1),
                        "lower_kt": round(max(0.0, central - uncertainty), 1),
                        "upper_kt": round(central + uncertainty, 1),
                        "persistence_kt": round(point["vmax_kt"], 1),
                        "historical_reference_kt": round(actual["vmax_kt"], 1)
                        if actual
                        else None,
                    }
                )
            point["forecasts"] = forecasts

    @staticmethod
    def _keyframes_for_storm(
        sid: str, name: str, points: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        slug = name.lower()
        if not points:
            return []
        peak_idx = max(range(len(points)), key=lambda i: points[i]["vmax_kt"])
        n = len(points)
        idx_0 = 0
        idx_1 = max(1, min(peak_idx // 2, n - 1))
        idx_2 = peak_idx
        idx_3 = (
            max(peak_idx + 1, min(peak_idx + (n - peak_idx) // 2, n - 1))
            if peak_idx < n - 1
            else n - 1
        )
        selected_indices = [idx_0, idx_1, idx_2, idx_3]
        labels = [
            "Early organisation",
            "Rapid organisation",
            "Mature eye structure",
            "Post-landfall decay",
        ]
        suffixes = ["formation", "intensifying", "peak", "decaying"]
        keyframes = []
        for i, (p_idx, label, suffix) in enumerate(
            zip(selected_indices, labels, suffixes, strict=True), 1
        ):
            p = points[p_idx]
            fname = f"{slug}-0{i}-{suffix}.png"
            keyframes.append(
                {
                    "valid_time": p["valid_time"],
                    "url": f"/imagery/{fname}",
                    "label": label,
                    "source": "HURSAT-B1 / Meteosat-7"
                    if sid == "2013281N12098"
                    else "INSAT-3D / HURSAT-B1",
                    "embedded_wind_kt": round(p["vmax_kt"]),
                }
            )
        return keyframes

    def _build_storm(self, sid: str, rows: list[SourceRow]) -> dict[str, Any]:
        by_time: dict[datetime, list[SourceRow]] = defaultdict(list)
        for row in rows:
            by_time[row.valid_time].append(row)

        points: list[dict[str, Any]] = []
        for valid_time, observations in sorted(by_time.items()):
            eye_values = [
                row.eye_probability
                for row in observations
                if row.eye_probability is not None
            ]
            vmax = median(row.vmax_kt for row in observations)
            points.append(
                {
                    "valid_time": iso_utc(valid_time),
                    "vmax_kt": round(vmax, 1),
                    "latitude": round(median(row.latitude for row in observations), 3),
                    "longitude": round(
                        median(row.longitude for row in observations), 3
                    ),
                    "category": imd_category(vmax),
                    "satellites": sorted({row.satellite for row in observations}),
                    "source_count": len(observations),
                    "eye_signal": round(median(eye_values), 1) if eye_values else None,
                    "quality": {
                        "status": "valid",
                        "reason_codes": [],
                        "coverage": round(len(observations) / 3.0, 2),
                    },
                }
            )

        self._add_derived_values(points)
        peak = max(points, key=lambda point: point["vmax_kt"])
        first, last = points[0], points[-1]
        name = rows[0].name
        alerts = [
            {
                "alert_id": self._alert_id(sid, point["valid_time"]),
                "type": "rapid_intensification",
                "severity": "high" if point["ri"]["probability"] >= 0.8 else "medium",
                "status": "open",
                "storm_id": sid,
                "storm_name": name,
                "valid_time": point["valid_time"],
                "probability": point["ri"]["probability"],
                "threshold": RI_ALERT_THRESHOLD,
                "definition": point["ri"]["definition"],
                "method": point["ri"]["method"],
            }
            for point in points
            if point["ri"]["alert_eligible"]
        ]

        return {
            "storm_id": sid,
            "sid": sid,
            "name": name,
            "basin": "Arabian Sea"
            if name in ("TAUKTAE", "BIPARJOY")
            else "Bay of Bengal",
            "mode": "historical_demo",
            "status": "historical",
            "category_profile_id": CATEGORY_PROFILE_ID,
            "first_valid_time": first["valid_time"],
            "last_valid_time": last["valid_time"],
            "peak": {
                "vmax_kt": peak["vmax_kt"],
                "valid_time": peak["valid_time"],
                "category": peak["category"],
            },
            "track": points,
            "observation_count": len(points),
            "source_row_count": len(rows),
            "satellites": sorted({row.satellite for row in rows}),
            "alerts": alerts,
            "imagery_keyframes": self._keyframes_for_storm(sid, name, points),
        }

    @staticmethod
    def _alert_id(storm_id: str, valid_time: str) -> str:
        compact_time = (
            valid_time.replace("-", "")
            .replace(":", "")
            .replace("T", "-")
            .replace("Z", "")
        )
        return f"ri-{storm_id}-{compact_time}"

    def list_storms(self) -> list[dict[str, Any]]:
        return [
            {
                key: storm[key]
                for key in (
                    "storm_id",
                    "sid",
                    "name",
                    "basin",
                    "mode",
                    "status",
                    "first_valid_time",
                    "last_valid_time",
                    "peak",
                    "observation_count",
                    "satellites",
                )
            }
            for storm in self._storms.values()
        ]

    def get_storm(self, storm_id: str) -> dict[str, Any] | None:
        return self._storms.get(storm_id)

    def get_analysis(
        self, storm_id: str, valid_time: str | None = None
    ) -> dict[str, Any] | None:
        storm = self.get_storm(storm_id)
        if not storm:
            return None
        points = storm["track"]
        if valid_time:
            requested = parse_utc(valid_time)
            point = min(
                points,
                key=lambda item: abs(
                    (parse_utc(item["valid_time"]) - requested).total_seconds()
                ),
            )
        else:
            point = points[-1]
        index = points.index(point)
        return {
            "analysis_id": f"hist-{storm_id}-{point['valid_time']}",
            "storm_id": storm_id,
            "storm_name": storm["name"],
            "mode": "historical_demo",
            "status": "succeeded",
            "selected_index": index,
            "point": point,
            "category_profile_id": CATEGORY_PROFILE_ID,
            "disclaimer": "Historical machine-guidance prototype; not an official forecast or warning.",
        }

    def dataset_summary(self) -> dict[str, Any]:
        storms = list(self._storms.values())
        return {
            "storm_count": len(storms),
            "observation_count": sum(storm["observation_count"] for storm in storms),
            "source_row_count": sum(storm["source_row_count"] for storm in storms),
            "satellites": sorted(
                {satellite for storm in storms for satellite in storm["satellites"]}
            ),
            "index_path": str(self.index_path),
            "category_profile_id": CATEGORY_PROFILE_ID,
        }
