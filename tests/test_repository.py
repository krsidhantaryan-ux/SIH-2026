from pathlib import Path

from app.repository import StormRepository

ROOT = Path(__file__).resolve().parents[1]


def test_committed_dataset_loads_without_unknown_categories() -> None:
    repository = StormRepository(ROOT / "data/processed/index.csv")
    storms = repository.list_storms()
    assert len(storms) == 1
    storm = repository.get_storm(storms[0]["storm_id"])
    assert storm is not None
    assert storm["name"] == "PHAILIN"
    assert storm["observation_count"] > 40
    assert all(point["category"]["name"] != "Unknown" for point in storm["track"])


def test_forecast_uses_only_current_and_past_but_exposes_historical_reference() -> None:
    repository = StormRepository(ROOT / "data/processed/index.csv")
    storm_id = repository.list_storms()[0]["storm_id"]
    analysis = repository.get_analysis(storm_id, "2013-10-10T12:00:00Z")
    assert analysis is not None
    point = analysis["point"]
    assert [item["horizon_hours"] for item in point["forecasts"]] == [6, 12, 24]
    assert point["ri"]["method"] == "Past-only linear-trend baseline"
    assert point["forecasts"][0]["historical_reference_kt"] is not None
