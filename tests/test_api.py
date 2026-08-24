import asyncio
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from app.main import app, intensity_model, repository


class ASGITestClient:
    """Small synchronous facade over HTTPX's current async ASGI transport."""

    @staticmethod
    def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)


client = ASGITestClient()
STORM_ID = repository.list_storms()[0]["storm_id"]


def _image_bytes(size: tuple[int, int] = (300, 300)) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", size, (70, 110, 160))
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_status_and_model_metadata() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "historical_demo"
    assert body["model"]["status"] == "ready"
    assert body["model"]["validation_status"] == "prototype_trained"
    assert intensity_model.ready

    active = client.get("/api/v1/models/active")
    assert active.status_code == 200
    assert active.json()["id"] == body["model"]["id"]


def test_storm_and_nearest_analysis() -> None:
    storm_response = client.get(f"/api/v1/storms/{STORM_ID}")
    assert storm_response.status_code == 200
    storm = storm_response.json()
    assert storm["name"] == "PHAILIN"
    assert len(storm["track"]) == storm["observation_count"]

    analysis_response = client.get(
        f"/api/v1/storms/{STORM_ID}/analysis",
        params={"valid_time": "2013-10-10T13:00:00Z"},
    )
    assert analysis_response.status_code == 200
    assert analysis_response.json()["point"]["valid_time"] == "2013-10-10T12:00:00Z"


def test_upload_runs_real_onnx_model_and_is_honest_about_uncertainty() -> None:
    response = client.post(
        "/api/v1/analysis/upload",
        files={"file": ("insat.png", _image_bytes(), "image/png")},
        data={"valid_time": "2026-08-23T12:00:00Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["method"]["trained_model"] is True
    assert body["result"]["method"]["replaceable"] is True
    assert body["result"]["uncertainty_status"] == "not_calibrated"
    assert body["result"]["confidence"] is None
    assert 0 <= body["result"]["vmax_kt"] <= 170


def test_upload_rejects_unsupported_and_tiny_files() -> None:
    unsupported = client.post(
        "/api/v1/analysis/upload",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert unsupported.status_code == 415

    tiny = client.post(
        "/api/v1/analysis/upload",
        files={"file": ("tiny.png", _image_bytes((32, 32)), "image/png")},
    )
    assert tiny.status_code == 422


def test_alert_review_and_report() -> None:
    alert_list = client.get("/api/v1/alerts").json()["items"]
    assert alert_list
    alert_id = alert_list[0]["alert_id"]
    transition = client.post(
        f"/api/v1/alerts/{alert_id}/transition",
        json={"action": "acknowledge", "reviewer": "Test analyst"},
    )
    assert transition.status_code == 200
    assert transition.json()["status"] == "acknowledged"

    report = client.get(
        f"/api/v1/reports/{STORM_ID}",
        params={"valid_time": "2013-10-10T12:00:00Z"},
    )
    assert report.status_code == 200
    assert "not an official forecast" in report.text
    assert "Past-only trend guidance" in report.text
