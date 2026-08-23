from pathlib import Path

import numpy as np
from PIL import Image

from app.model import load_intensity_model


ROOT = Path(__file__).resolve().parents[1]


def test_active_model_integrity_signature_and_determinism() -> None:
    model = load_intensity_model(ROOT / "models/active-model.json")
    assert model.ready, model.load_error
    assert model.metadata()["validation_status"] == "legacy_unvalidated"
    image = Image.fromarray(np.full((250, 250, 3), 128, dtype=np.uint8), "RGB")
    first = model.predict(image)
    second = model.predict(image)
    assert np.isfinite(first)
    assert first == second


def test_model_preprocessing_contract() -> None:
    model = load_intensity_model(ROOT / "models/active-model.json")
    image = Image.new("RGB", (400, 300), (10, 20, 30))
    tensor = model.preprocess(image)
    assert tensor.shape == (1, 3, 250, 250)
    assert tensor.dtype == np.float32
    # Legacy pipeline uses BGR ordering.
    assert np.allclose(tensor[0, :, 0, 0], [30 / 255, 20 / 255, 10 / 255])
