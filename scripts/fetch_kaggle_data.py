#!/usr/bin/env python3
"""Download and validate the selected Kaggle INSAT-3D dataset.

The script is intentionally separate from application startup. By default it
downloads with ``kagglehub`` and keeps raw images under ``data/raw`` (never
committed). With ``--local-root`` it instead validates a dataset that already
exists on disk — for example the repo-committed copy under
``data/kaggle_insat3d`` — so no network or Kaggle credentials are needed.

Authentication (only for download mode; never commit or print values):
  KAGGLE_USERNAME / KAGGLE_KEY, or KAGGLE_API_TOKEN
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

DEFAULT_HANDLE = "sshubam/insat3d-infrared-raw-cyclone-images-20132021"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def find_label_csv(root: Path) -> Path:
    candidates = sorted(root.rglob("*.csv"))
    if not candidates:
        raise RuntimeError("No label CSV was found in the downloaded dataset")
    preferred = [path for path in candidates if "sheet" in path.name.lower()]
    return (preferred or candidates)[0]


def resolve_columns(fieldnames: list[str]) -> tuple[str, str]:
    normalized = {name.lower().strip(): name for name in fieldnames}
    image_candidates = ("img_name", "img_namesort", "image", "filename", "name")
    label_candidates = ("label", "intensity", "vmax", "wind", "wind_speed")
    image_column = next(
        (normalized[name] for name in image_candidates if name in normalized), None
    )
    label_column = next(
        (normalized[name] for name in label_candidates if name in normalized), None
    )
    if not image_column or not label_column:
        if len(fieldnames) == 2:
            return fieldnames[0], fieldnames[1]
        raise RuntimeError(f"Could not identify image/label columns: {fieldnames}")
    return image_column, label_column


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", default=DEFAULT_HANDLE)
    parser.add_argument(
        "--local-root",
        type=Path,
        default=None,
        help=(
            "Validate an already-downloaded dataset directory (e.g. the "
            "repo-committed data/kaggle_insat3d) instead of downloading."
        ),
    )
    parser.add_argument("--output", type=Path, default=Path("data/raw/kaggle_insat3d"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/processed/kaggle_insat3d_manifest.csv"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.local_root:
        if not args.local_root.is_dir():
            raise SystemExit(f"--local-root is not a directory: {args.local_root}")
        root = args.local_root
    else:
        try:
            import kagglehub
        except ImportError as error:
            raise SystemExit(
                "kagglehub is not installed. Run `pip install kagglehub`, or "
                "pass --local-root to validate an already-downloaded dataset."
            ) from error
        args.output.mkdir(parents=True, exist_ok=True)
        downloaded = Path(
            kagglehub.dataset_download(
                args.handle,
                output_dir=str(args.output),
                force_download=args.force,
            )
        )
        root = downloaded if downloaded.is_dir() else args.output
    label_path = find_label_csv(root)
    images = {
        path.name: path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }

    with label_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError("Label CSV has no header")
        image_column, label_column = resolve_columns(reader.fieldnames)
        labels = list(reader)

    valid: list[dict[str, str | int | float]] = []
    missing: list[str] = []
    invalid: list[str] = []
    for row in labels:
        filename = Path(row[image_column].strip()).name
        image_path = images.get(filename)
        if not image_path:
            missing.append(filename)
            continue
        try:
            vmax = float(row[label_column])
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                width, height = image.size
                mode = image.mode
        except (ValueError, OSError, UnidentifiedImageError):
            invalid.append(filename)
            continue
        valid.append(
            {
                "sample_id": hashlib.sha256(filename.encode()).hexdigest()[:16],
                "filename": filename,
                "image_path": str(image_path),
                "vmax_kt": vmax,
                "width": width,
                "height": height,
                "mode": mode,
                "sha256": sha256(image_path),
                "dataset_handle": args.handle,
            }
        )

    if missing or invalid:
        print(f"Missing labelled images: {len(missing)}", file=sys.stderr)
        print(f"Invalid labelled images: {len(invalid)}", file=sys.stderr)
    if not valid:
        raise RuntimeError("No valid labelled image pairs were produced")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(valid[0]))
        writer.writeheader()
        writer.writerows(valid)

    print(f"Kaggle dataset: {args.handle}")
    print(f"Label CSV: {label_path}")
    print(f"Discovered image files: {len(images)}")
    print(f"Valid labelled pairs: {len(valid)}")
    print(f"Manifest: {args.manifest}")
    print(
        "IMPORTANT: the source labels do not reliably expose storm IDs. Do not "
        "claim storm-disjoint validation until samples are enriched with a "
        "reviewed storm/time identity."
    )


if __name__ == "__main__":
    main()
