"""
Export PyTorch intensity models to portable ONNX format and generate matching active manifests.

Usage:
    python -m src.export_onnx --checkpoint models/checkpoints/seconvnet_best.pt --output models/cyclone_resnet18_v1.onnx
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import onnx
import onnxruntime as ort
import torch

from src.models import get_model


def export_to_onnx(
    model: torch.nn.Module,
    output_path: Path,
    input_shape: tuple = (1, 1, 301, 301),
    opset_version: int = 18,
) -> str:
    model.eval()
    dummy_input = torch.randn(*input_shape, dtype=torch.float32)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["vmax_kt"],
        dynamic_axes={"input": {0: "batch_size"}, "vmax_kt": {0: "batch_size"}},
    )

    # Verify model with onnx checker
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)

    # Verify inference with ONNX Runtime
    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    ort_inputs = {session.get_inputs()[0].name: dummy_input.numpy()}
    ort_outputs = session.run(None, ort_inputs)
    assert ort_outputs[0].shape == (1, 1), f"Unexpected output shape: {ort_outputs[0].shape}"

    # Compute SHA-256
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    print(f"[+] ONNX export verified successfully: {output_path}")
    print(f"    SHA-256: {digest}")
    print(f"    File size: {output_path.stat().st_size / (1024 * 1024):.2f} MB")
    return digest


def generate_manifest(
    onnx_path: Path,
    sha256_digest: str,
    manifest_path: Path,
    model_id: str = "cyclone-resnet18-nio@1.0.0",
    in_channels: int = 1,
    height: int = 301,
    width: int = 301,
) -> None:
    manifest = {
        "schema_version": "1.0",
        "id": model_id,
        "task": "intensity_regression",
        "artifact": {
            "path": onnx_path.name,
            "sha256": sha256_digest,
            "format": "onnx",
            "opset": 18,
        },
        "input": {
            "name": "input",
            "layout": "NCHW",
            "channels": in_channels,
            "width": width,
            "height": height,
            "color_order": "RGB" if in_channels == 3 else "GRAY",
            "scale": 0.00392156862745098,
            "mean": [0.5] * in_channels,
            "std": [0.5] * in_channels,
        },
        "output": {
            "name": "vmax_kt",
            "unit": "kt",
            "shape": [1, 1],
        },
        "source_repository": "https://github.com/krsidhantaryan-ux/SIH-2026",
        "training_dataset": "NOAA HURSAT-B1 + IBTrACS (North Indian Ocean Basin)",
        "validation_status": "storm_disjoint_validated",
        "model_card": "models/MODEL_CARD.md",
        "approved_modes": ["demo", "historical_demo", "user_supplied_demo", "operational_shadow"],
        "operational_use": False,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[+] Active model manifest written to {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained model to ONNX")
    parser.add_argument("--model-name", type=str, default="seconvnet")
    parser.add_argument("--in-channels", type=int, default=1)
    parser.add_argument("--image-size", type=int, default=301)
    parser.add_argument("--output", type=str, default="models/cyclone_intensity_resnet.onnx")
    parser.add_argument("--manifest", type=str, default="models/active-model-resnet.json")
    args = parser.parse_args()

    model = get_model(args.model_name, in_channels=args.in_channels)
    onnx_path = Path(args.output)
    digest = export_to_onnx(model, onnx_path, input_shape=(1, args.in_channels, args.image_size, args.image_size))

    manifest_path = Path(args.manifest)
    generate_manifest(
        onnx_path,
        digest,
        manifest_path,
        in_channels=args.in_channels,
        height=args.image_size,
        width=args.image_size,
    )


if __name__ == "__main__":
    main()
