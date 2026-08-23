"""Manifest-driven ONNX intensity model adapter.

The API depends only on a scalar ``vmax_kt`` contract. Model identity,
artefact, checksum, input shape, colour order, scaling and validation status
live in a JSON manifest. A future trained model can therefore replace the
legacy model without changing API or UI code, provided it exports one scalar
wind estimate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


class ModelIntegrityError(RuntimeError):
    """Raised when the configured model cannot be trusted or executed."""


class OnnxIntensityModel:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.manifest: dict[str, Any] = {}
        self.model_path: Path | None = None
        self.sha256: str | None = None
        self.session: ort.InferenceSession | None = None
        self.load_error: str | None = None
        self._load()

    def _fail(self, code: str) -> None:
        self.session = None
        self.load_error = code

    def _load(self) -> None:
        if not self.manifest_path.is_file():
            self._fail("MODEL_MANIFEST_MISSING")
            return
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            artifact = self.manifest["artifact"]
            configured_path = Path(artifact["path"])
            self.model_path = (
                configured_path
                if configured_path.is_absolute()
                else self.manifest_path.parent / configured_path
            ).resolve()
            expected_digest = artifact["sha256"]
            input_config = self.manifest["input"]
            output_config = self.manifest["output"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._fail("MODEL_MANIFEST_INVALID")
            return

        if not self.model_path.is_file():
            self._fail("MODEL_FILE_MISSING")
            return
        digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        self.sha256 = digest
        if digest != expected_digest:
            self._fail("MODEL_DIGEST_MISMATCH")
            return
        try:
            self.session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"]
            )
        except Exception:  # ONNX Runtime exception types vary by release.
            self._fail("MODEL_LOAD_FAILED")
            return

        runtime_input = self.session.get_inputs()[0]
        expected_shape = [
            1,
            int(input_config.get("channels", 3)),
            int(input_config["height"]),
            int(input_config["width"]),
        ]
        if input_config.get("layout", "NCHW") != "NCHW":
            self._fail("MODEL_LAYOUT_UNSUPPORTED")
            return
        if runtime_input.name != input_config["name"] or runtime_input.shape != expected_shape:
            self._fail("MODEL_SIGNATURE_MISMATCH")
            return
        runtime_outputs = {item.name for item in self.session.get_outputs()}
        if output_config["name"] not in runtime_outputs:
            self._fail("MODEL_OUTPUT_MISMATCH")

    @property
    def ready(self) -> bool:
        return self.session is not None and self.load_error is None

    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.manifest.get("id", "unconfigured"),
            "status": "ready" if self.ready else "unavailable",
            "task": self.manifest.get("task", "intensity_regression"),
            "sha256": self.sha256,
            "source_repository": self.manifest.get("source_repository"),
            "training_dataset": self.manifest.get("training_dataset"),
            "runtime": "ONNX Runtime / CPU",
            "input_signature": self.manifest.get("input"),
            "output_contract": self.manifest.get("output"),
            "validation_status": self.manifest.get("validation_status", "unknown"),
            "model_card": self.manifest.get("model_card"),
            "replaceable_via": str(self.manifest_path),
            "load_error": self.load_error,
        }

    def preprocess(self, image: Image.Image) -> np.ndarray:
        if not self.manifest:
            raise ModelIntegrityError(self.load_error or "MODEL_NOT_CONFIGURED")
        config = self.manifest["input"]
        width, height = int(config["width"]), int(config["height"])
        rgb = ImageOps.fit(
            ImageOps.exif_transpose(image).convert("RGB"),
            (width, height),
            method=Image.Resampling.BILINEAR,
        )
        values = np.asarray(rgb, dtype=np.float32)
        if config.get("color_order", "RGB") == "BGR":
            values = values[:, :, ::-1]
        elif config.get("color_order", "RGB") != "RGB":
            raise ModelIntegrityError("MODEL_COLOR_ORDER_UNSUPPORTED")
        values = values * float(config.get("scale", 1.0 / 255.0))
        mean = np.asarray(config.get("mean", [0.0, 0.0, 0.0]), dtype=np.float32)
        std = np.asarray(config.get("std", [1.0, 1.0, 1.0]), dtype=np.float32)
        if np.any(std == 0):
            raise ModelIntegrityError("MODEL_PREPROCESS_STD_INVALID")
        values = (values - mean) / std
        return np.ascontiguousarray(values.transpose(2, 0, 1)[None, ...])

    def predict(self, image: Image.Image) -> float:
        if not self.session:
            raise ModelIntegrityError(self.load_error or "MODEL_NOT_READY")
        input_name = self.manifest["input"]["name"]
        output_name = self.manifest["output"]["name"]
        output = self.session.run([output_name], {input_name: self.preprocess(image)})[0]
        estimate = float(output.reshape(-1)[0])
        if not np.isfinite(estimate):
            raise ModelIntegrityError("MODEL_OUTPUT_NOT_FINITE")
        return estimate


def load_intensity_model(manifest_path: Path) -> OnnxIntensityModel:
    """Factory kept as the only construction point for future adapter types."""

    return OnnxIntensityModel(manifest_path)
