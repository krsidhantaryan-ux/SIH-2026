"""
PyTorch Dataset and Data Loading utilities for Tropical Cyclone Intensity Estimation.
Supports physics-informed augmentations (cyclone spin rotations) and strict storm-disjoint splits.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset


class CycloneDataset(Dataset):
    """
    Dataset for cyclone intensity estimation from satellite infrared imagery.
    Supports either pre-extracted NumPy arrays (.npz) or raw image files.
    """

    def __init__(
        self,
        samples: Sequence[tuple[np.ndarray | str | Path, float, str]],
        transform: Callable | None = None,
        image_size: int = 301,
        normalize_method: str = "standard",  # 'standard', 'kelvin', or 'unit'
    ):
        """
        samples: List of tuples (image_path_or_array, vmax_kt, storm_id)
        """
        self.samples = samples
        self.transform = transform
        self.image_size = image_size
        self.normalize_method = normalize_method

    def __len__(self) -> int:
        return len(self.samples)

    def _load_image(self, item: np.ndarray | str | Path) -> np.ndarray:
        if isinstance(item, np.ndarray):
            arr = item
        else:
            path = Path(item)
            if not path.is_file():
                raise FileNotFoundError(f"Image not found: {path}")
            with Image.open(path) as img:
                arr = np.array(img.convert("L"), dtype=np.float32)

        # Ensure 2D float32
        if arr.ndim == 3:
            arr = arr.mean(axis=2)
        return arr.astype(np.float32)

    def _normalize(self, img: np.ndarray) -> np.ndarray:
        if self.normalize_method == "kelvin":
            # Expected input: Brightness temp 180K - 310K -> normalized [-1, 1]
            img = np.clip(img, 180.0, 310.0)
            return (img - 245.0) / 65.0
        elif self.normalize_method == "unit":
            # 0-255 -> [0, 1]
            return img / 255.0
        else:
            # Standard ImageNet / Zero-mean
            mean, std = img.mean(), img.std() + 1e-6
            return (img - mean) / std

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, str]:
        item, vmax, sid = self.samples[idx]
        img_arr = self._load_image(item)

        # Apply physics-informed transform if specified
        if self.transform is not None:
            img_arr = self.transform(img_arr)
        else:
            img_arr = self._normalize(img_arr)

        # Expand channel dim: (H, W) -> (1, H, W)
        if img_arr.ndim == 2:
            img_tensor = torch.from_numpy(img_arr).unsqueeze(0).float()
        else:
            img_tensor = torch.from_numpy(img_arr).permute(2, 0, 1).float()

        vmax_tensor = torch.tensor(vmax, dtype=torch.float32)
        return img_tensor, vmax_tensor, sid


class CycloneAugmentations:
    """
    Physics-informed meteorological augmentations:
    1. Cyclones rotate, so 0-360 deg rotation preserves physical structure.
    2. Random horizontal and vertical flips preserve thermal spiral dynamics.
    3. Small random scaling simulates slight satellite altitude / crop variations.
    """

    def __init__(self, is_train: bool = True, output_size: int = 301):
        self.is_train = is_train
        self.output_size = output_size

    def __call__(self, img: np.ndarray) -> np.ndarray:
        pil_img = Image.fromarray(img.astype(np.uint8) if img.max() > 1.0 else (img * 255).astype(np.uint8))

        if self.is_train:
            # 1. Random 0-360 degree rotation (cyclone vortex symmetry)
            angle = float(np.random.uniform(0, 360))
            pil_img = pil_img.rotate(angle, resample=Image.Resampling.BILINEAR)

            # 2. Random horizontal/vertical flip
            if np.random.random() > 0.5:
                pil_img = pil_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if np.random.random() > 0.5:
                pil_img = pil_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # Resize to standard model input dimensions
        if pil_img.size != (self.output_size, self.output_size):
            pil_img = pil_img.resize((self.output_size, self.output_size), Image.Resampling.BILINEAR)

        arr = np.array(pil_img, dtype=np.float32) / 255.0
        # Standard normalization
        return (arr - 0.5) / 0.5


def make_storm_disjoint_split(
    manifest_df: pd.DataFrame,
    storm_col: str = "name",
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Partitions the dataset strictly by Storm Identity (SID / Storm Name).
    Guarantees zero data leakage between training, validation, and test sets.
    """
    np.random.seed(random_seed)
    unique_storms = np.array(sorted(manifest_df[storm_col].unique()))
    np.random.shuffle(unique_storms)

    n_storms = len(unique_storms)
    n_test = max(1, int(n_storms * test_ratio))
    n_val = max(1, int(n_storms * val_ratio))

    test_storms = set(unique_storms[:n_test])
    val_storms = set(unique_storms[n_test : n_test + n_val])
    train_storms = set(unique_storms[n_test + n_val :])

    train_df = manifest_df[manifest_df[storm_col].isin(train_storms)].copy()
    val_df = manifest_df[manifest_df[storm_col].isin(val_storms)].copy()
    test_df = manifest_df[manifest_df[storm_col].isin(test_storms)].copy()

    return train_df, val_df, test_df
