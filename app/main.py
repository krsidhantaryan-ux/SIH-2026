"""Cyclone-AI MVP API and production static-file host.

Run for development:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

The application intentionally labels every result as historical/demo guidance.
No endpoint issues an official forecast or public warning.
"""

from __future__ import annotations

import html
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from app import __version__
from app.domain import CATEGORY_PROFILE_ID, clamp, imd_category, iso_utc
from app.model import ModelIntegrityError, load_intensity_model
from app.repository import DatasetError, StormRepository

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = Path(
    os.getenv("CYCLONE_DATA_INDEX", BASE_DIR / "data/processed/index.csv")
)
MODEL_MANIFEST_PATH = Path(
    os.getenv(
        "CYCLONE_MODEL_MANIFEST",
        BASE_DIR / "models/active-model.json",
    )
)
WEB_DIST = BASE_DIR / "web/dist"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

repository = StormRepository(INDEX_PATH)
intensity_model = load_intensity_model(MODEL_MANIFEST_PATH)

app = FastAPI(
    title="Cyclone-AI MVP API",
    version=__version__,
    description=(
        "Historical tropical-cyclone replay and transparent baseline analysis "
        "for the SIH demonstration. Not an official forecast or warning."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

allowed_origins = [
    value.strip()
    for value in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if value.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

# Review transitions are deliberately in-memory for the single-process demo.
# The API tells the UI this; a pilot must use the append-only persistent model
# specified in docs/SRS.md.
_alert_reviews: dict[str, dict[str, Any]] = {}


class AlertTransition(BaseModel):
    action: Literal["acknowledge", "escalate", "dismiss", "resolve"]
    reason: str | None = Field(default=None, max_length=300)
    reviewer: str = Field(default="Demo analyst", min_length=1, max_length=80)


class APIMessage(BaseModel):
    status: str
    message: str


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", f"demo-{id(request):x}")


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "cyclone-ai-api",
        "version": __version__,
        "dataset": "ready",
        "time": iso_utc(datetime.now(timezone.utc)),
    }


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    summary = repository.dataset_summary()
    return {
        "environment": os.getenv("APP_ENV", "demo"),
        "mode": "historical_demo",
        "release": __version__,
        "overall_status": "demo_ready",
        "disclaimer": "Historical prototype guidance only — not an official forecast or public warning.",
        "dataset": summary,
        "model": intensity_model.metadata(),
        "sources": [
            {
                "id": "hursat-b1",
                "name": "HURSAT-B1 infrared imagery",
                "status": "ready",
                "mode": "archived",
                "detail": "Four verified Phailin keyframes and indexed observations",
            },
            {
                "id": "ibtracs",
                "name": "IBTrACS best-track archive",
                "status": "ready",
                "mode": "archived",
                "detail": f"{summary['source_row_count']} source rows loaded",
            },
            {
                "id": "insat",
                "name": "INSAT-3D/3DR via MOSDAC",
                "status": "not_configured",
                "mode": "planned_adapter",
                "detail": "Requires approved data access; not simulated",
            },
        ],
        "capabilities": [
            {
                "id": "historical-replay",
                "name": "Historical storm replay",
                "status": "ready",
            },
            {
                "id": "trend-baseline",
                "name": "Past-only trend and persistence guidance",
                "status": "ready",
            },
            {
                "id": "upload-analysis",
                "name": "INSAT-3D upload analysis",
                "status": "ready" if intensity_model.ready else "degraded",
            },
            {
                "id": "legacy-cnn",
                "name": "Legacy Kaggle-trained CNN baseline",
                "status": "ready" if intensity_model.ready else "unavailable",
                "qualification": "demonstration_only_unvalidated",
            },
        ],
    }


@app.get("/api/v1/models/active")
def active_model() -> dict[str, Any]:
    return intensity_model.metadata()


@app.get("/api/v1/storms")
def list_storms() -> dict[str, Any]:
    storms = repository.list_storms()
    return {"items": storms, "count": len(storms)}


@app.get("/api/v1/storms/{storm_id}")
def get_storm(storm_id: str) -> dict[str, Any]:
    storm = repository.get_storm(storm_id)
    if not storm:
        raise HTTPException(status_code=404, detail="Storm not found")
    result = dict(storm)
    result["alerts"] = [
        {**alert, **_alert_reviews.get(alert["alert_id"], {})}
        for alert in storm["alerts"]
    ]
    return result


@app.get("/api/v1/storms/{storm_id}/analysis")
def get_analysis(
    storm_id: str,
    valid_time: str | None = Query(
        default=None,
        description="RFC 3339 valid time; nearest indexed observation is selected",
    ),
) -> dict[str, Any]:
    try:
        analysis = repository.get_analysis(storm_id, valid_time)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail="Invalid valid_time") from exc
    if not analysis:
        raise HTTPException(status_code=404, detail="Storm not found")
    return analysis


@app.get("/api/v1/alerts")
def list_alerts() -> dict[str, Any]:
    alerts: list[dict[str, Any]] = []
    for storm in repository.list_storms():
        full_storm = repository.get_storm(storm["storm_id"])
        if full_storm:
            alerts.extend(
                {**alert, **_alert_reviews.get(alert["alert_id"], {})}
                for alert in full_storm["alerts"]
            )
    alerts.sort(key=lambda item: item["valid_time"], reverse=True)
    return {"items": alerts, "count": len(alerts), "persistence": "in_memory_demo"}


@app.post("/api/v1/alerts/{alert_id}/transition")
def transition_alert(
    alert_id: str, transition: AlertTransition, request: Request
) -> dict[str, Any]:
    available = {
        alert["alert_id"]
        for storm in repository.list_storms()
        for alert in (repository.get_storm(storm["storm_id"]) or {}).get("alerts", [])
    }
    if alert_id not in available:
        raise HTTPException(status_code=404, detail="Alert not found")
    if transition.action == "dismiss" and not (transition.reason or "").strip():
        raise HTTPException(
            status_code=422, detail="A reason is required to dismiss an alert"
        )
    status_by_action = {
        "acknowledge": "acknowledged",
        "escalate": "escalated",
        "dismiss": "dismissed",
        "resolve": "resolved",
    }
    review = {
        "status": status_by_action[transition.action],
        "review": {
            "action": transition.action,
            "reason": transition.reason,
            "reviewer": transition.reviewer,
            "reviewed_at": iso_utc(datetime.now(timezone.utc)),
            "request_id": _request_id(request),
        },
    }
    _alert_reviews[alert_id] = review
    return {"alert_id": alert_id, **review, "persistence": "in_memory_demo"}


def _mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _analyse_image(image: Image.Image) -> dict[str, Any]:
    """Run the legacy CNN and compute transparent morphology context.

    The CNN supplies the intensity estimate. The hand-computed morphology
    metrics are explanatory context only and do not alter the prediction.
    Because the source project published no held-out validation or calibrated
    uncertainty, this endpoint returns no confidence interval.
    """

    sample = ImageOps.fit(image.convert("L"), (128, 128))
    pixels = list(sample.get_flattened_data())
    center: list[int] = []
    inner_ring: list[int] = []
    outer: list[int] = []
    for y in range(128):
        for x in range(128):
            distance = (((x - 63.5) ** 2 + (y - 63.5) ** 2) ** 0.5) / 64.0
            value = pixels[y * 128 + x]
            if distance < 0.14:
                center.append(value)
            elif distance < 0.36:
                inner_ring.append(value)
            elif 0.58 < distance < 0.88:
                outer.append(value)

    rotated = list(sample.rotate(180).get_flattened_data())
    symmetry = 1.0 - sum(
        abs(value - opposite) for value, opposite in zip(pixels, rotated, strict=True)
    ) / (len(pixels) * 255.0)
    bright_fraction = sum(value >= 175 for value in pixels) / len(pixels)
    center_mean = _mean(center)
    ring_mean = _mean(inner_ring)
    outer_mean = _mean(outer)
    eye_signal = clamp((ring_mean - center_mean) / 95.0, 0.0, 1.0)
    central_dense_overcast = clamp((center_mean - outer_mean) / 100.0, 0.0, 1.0)

    raw_estimate = intensity_model.predict(image)
    estimate = clamp(raw_estimate, 0.0, 170.0)

    if eye_signal >= 0.35:
        pattern = "Eye pattern candidate"
    elif central_dense_overcast >= 0.22:
        pattern = "Central dense overcast candidate"
    elif symmetry >= 0.72:
        pattern = "Organised curved-band candidate"
    else:
        pattern = "Weak or asymmetric organisation"

    return {
        "vmax_kt": round(estimate, 1),
        "raw_model_output_kt": round(raw_estimate, 3),
        "lower_kt": None,
        "upper_kt": None,
        "confidence": None,
        "uncertainty_status": "not_calibrated",
        "category": imd_category(estimate),
        "pattern": pattern,
        "metrics": {
            "cold_cloud_fraction": round(bright_fraction, 3),
            "rotational_symmetry": round(symmetry, 3),
            "eye_contrast": round(eye_signal, 3),
            "central_overcast": round(central_dense_overcast, 3),
        },
        "method": {
            **intensity_model.metadata(),
            "type": "legacy_pretrained_cnn",
            "trained_model": True,
            "replaceable": True,
            "limitations": [
                "The source project did not publish a cyclone-separated held-out evaluation.",
                "No calibrated confidence interval is available.",
                "Input must resemble the INSAT-3D imagery used by the legacy training pipeline.",
                "Morphology metrics are explanatory context and do not drive the CNN output.",
                "Demonstration use only; not validated meteorological guidance.",
            ],
        },
    }


def _decode_upload(content: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(content)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(content)) as opened:
            return ImageOps.exif_transpose(opened).convert("RGB").copy()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="The file is not a valid image"
        ) from exc


def _run_upload_model(image: Image.Image) -> dict[str, Any]:
    if image.width < 64 or image.height < 64:
        raise HTTPException(
            status_code=422, detail="Image must be at least 64 × 64 pixels"
        )
    try:
        return _analyse_image(image)
    except ModelIntegrityError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Intensity model is unavailable: {exc}",
        ) from exc


def _parse_optional_valid_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid valid_time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return iso_utc(parsed)


@app.post("/api/v1/analysis/upload")
async def analyse_upload(
    file: Annotated[UploadFile, File(description="PNG, JPEG, or WebP image")],
    valid_time: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=415, detail="Supported formats are PNG, JPEG, and WebP"
        )
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded image is empty")

    image = _decode_upload(content)
    analysis = _run_upload_model(image)
    width, height = image.size
    return {
        "analysis_id": f"upload-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "mode": "user_supplied_demo",
        "status": "succeeded",
        "filename": Path(file.filename or "upload").name,
        "media_type": file.content_type,
        "size_bytes": len(content),
        "dimensions": {"width": width, "height": height},
        "valid_time": _parse_optional_valid_time(valid_time),
        "quality": {
            "status": "valid" if min(width, height) >= 256 else "degraded",
            "reason_codes": [] if min(width, height) >= 256 else ["LOW_RESOLUTION"],
        },
        "result": analysis,
        "category_profile_id": CATEGORY_PROFILE_ID,
        "disclaimer": "Legacy pretrained CNN demonstration only — independently unvalidated and not an official forecast or warning.",
    }


def _report_html(storm: dict[str, Any], analysis: dict[str, Any]) -> str:
    point = analysis["point"]
    category = point["category"]["name"]
    forecasts = "".join(
        f"<tr><td>{item['horizon_hours']} h</td><td>{item['valid_time']}</td>"
        f"<td>{item['vmax_kt']:.1f} kt</td><td>{item['lower_kt']:.1f}–{item['upper_kt']:.1f} kt</td></tr>"
        for item in point["forecasts"]
    )
    satellites = ", ".join(point["satellites"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Cyclone-AI historical analysis — {html.escape(storm["name"])}</title>
<style>
body{{font:15px/1.55 Inter,system-ui,sans-serif;color:#172033;max-width:900px;margin:40px auto;padding:0 24px}}
header{{border-bottom:3px solid #335cff;padding-bottom:18px}} .warning{{background:#fff4d6;border:1px solid #e6b84a;padding:12px 16px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}} .card{{border:1px solid #d8deea;border-radius:10px;padding:14px}}
.label{{font-size:12px;color:#667085;text-transform:uppercase;letter-spacing:.06em}} .value{{font-size:24px;font-weight:700;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin:16px 0}} th,td{{border-bottom:1px solid #d8deea;text-align:left;padding:10px}} th{{background:#f5f7fb}}
small{{color:#667085}} @media print{{body{{margin:0}} .no-print{{display:none}}}}
</style></head><body>
<header><div class="label">Cyclone-AI · SIH 2026 demonstration</div><h1>{html.escape(storm["name"])} historical analysis</h1>
<p>Generated {iso_utc(datetime.now(timezone.utc))} · Analysis valid {point["valid_time"]}</p></header>
<p class="warning"><strong>Machine-generated historical prototype.</strong> This is not an official forecast or public warning.</p>
<div class="grid"><div class="card"><div class="label">Best-track reference</div><div class="value">{point["vmax_kt"]:.0f} kt</div></div>
<div class="card"><div class="label">Demo category profile</div><div class="value" style="font-size:18px">{html.escape(category)}</div></div>
<div class="card"><div class="label">RI trend indicator</div><div class="value">{point["ri"]["probability"] * 100:.0f}%</div></div></div>
<h2>Past-only trend guidance</h2><table><thead><tr><th>Horizon</th><th>Valid time</th><th>Guidance</th><th>Indicative interval</th></tr></thead><tbody>{forecasts}</tbody></table>
<h2>Observation and provenance</h2><table><tbody>
<tr><th>Position</th><td>{point["latitude"]:.2f}°, {point["longitude"]:.2f}°</td></tr>
<tr><th>Satellite records</th><td>{html.escape(satellites)}</td></tr>
<tr><th>Category profile</th><td>{CATEGORY_PROFILE_ID}</td></tr>
<tr><th>RI definition</th><td>{html.escape(point["ri"]["definition"])}; threshold {point["ri"]["threshold"] * 100:.0f}%</td></tr>
<tr><th>Method</th><td>Historical best-track display plus a past-only linear-trend/persistence baseline. The separate upload laboratory uses the legacy CNN; it does not generate this historical forecast.</td></tr>
</tbody></table><p><small>Analysis ID: {html.escape(analysis["analysis_id"])}<br>Source index: HURSAT-B1/IBTrACS demonstration data committed with the Cyclone-AI repository.</small></p>
<p class="no-print"><button onclick="window.print()">Print / save as PDF</button></p></body></html>"""


@app.get("/api/v1/reports/{storm_id}", response_class=HTMLResponse)
def report(
    storm_id: str,
    valid_time: str | None = Query(default=None),
) -> HTMLResponse:
    storm = repository.get_storm(storm_id)
    if not storm:
        raise HTTPException(status_code=404, detail="Storm not found")
    try:
        analysis = repository.get_analysis(storm_id, valid_time)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail="Invalid valid_time") from exc
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return HTMLResponse(_report_html(storm, analysis))


def _ensure_demo_admin() -> None:
    # These endpoints are intentionally unauthenticated only in local/demo.
    # Do not expose them as-is in shadow or pilot deployments.
    if os.getenv("APP_ENV", "demo") not in {"local", "demo", "test"}:
        raise HTTPException(status_code=403, detail="Reload is disabled")


@app.post("/api/v1/admin/reload-dataset", response_model=APIMessage)
def reload_dataset() -> APIMessage:
    _ensure_demo_admin()
    try:
        repository.reload()
    except DatasetError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return APIMessage(status="ok", message="Dataset reloaded")


@app.post("/api/v1/admin/reload-model", response_model=APIMessage)
def reload_model() -> APIMessage:
    """Atomically activate a newly written and verified model manifest."""

    global intensity_model
    _ensure_demo_admin()
    candidate = load_intensity_model(MODEL_MANIFEST_PATH)
    if not candidate.ready:
        raise HTTPException(
            status_code=500,
            detail=f"Candidate model failed validation: {candidate.load_error}",
        )
    intensity_model = candidate
    return APIMessage(status="ok", message=f"Activated {candidate.metadata()['id']}")


# Serve the production web build when it exists. During frontend development,
# Vite serves the same paths and proxies /api to this process.
if WEB_DIST.is_dir():
    assets_dir = WEB_DIST / "assets"
    imagery_dir = WEB_DIST / "imagery"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if imagery_dir.is_dir():
        app.mount("/imagery", StaticFiles(directory=imagery_dir), name="imagery")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        requested = (WEB_DIST / path).resolve()
        try:
            requested.relative_to(WEB_DIST.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(WEB_DIST / "index.html")
