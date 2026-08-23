#!/usr/bin/env python3
"""Convert CycloNet's legacy PyTorch state dictionary to portable ONNX.

This converter intentionally does not import PyTorch. It reads the documented
ZIP-based state-dict format into NumPy and reconstructs the architecture from
the original MIT-licensed training/application source.

Source project:
  https://github.com/cycloneintensity/CrossKnotHacks-Cyclonet

Usage:
  python scripts/convert_legacy_cyclonet.py \
    models/legacy/cyclonet_insat3d_state_dict.pt \
    models/cyclonet_insat3d_legacy.onnx
"""

from __future__ import annotations

import argparse
import collections
import io
import pickle
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


@dataclass(frozen=True)
class StorageType:
    dtype: np.dtype[Any]


@dataclass(frozen=True)
class Storage:
    values: np.ndarray[Any, Any]


def rebuild_tensor(
    storage: Storage,
    storage_offset: int,
    size: tuple[int, ...],
    stride: tuple[int, ...],
    *_: Any,
) -> np.ndarray[Any, Any]:
    """Rebuild a dense/strided tensor from a PyTorch storage descriptor."""

    base = storage.values[storage_offset:]
    byte_strides = tuple(value * base.dtype.itemsize for value in stride)
    return np.lib.stride_tricks.as_strided(
        base, shape=size, strides=byte_strides
    ).copy()


class TorchStateUnpickler(pickle.Unpickler):
    def __init__(self, payload: bytes, archive: zipfile.ZipFile):
        super().__init__(io.BytesIO(payload))
        self.archive = archive

    def find_class(self, module: str, name: str) -> Any:
        if module == "collections" and name == "OrderedDict":
            return collections.OrderedDict
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return rebuild_tensor
        if module == "torch" and name == "FloatStorage":
            return StorageType(np.dtype("<f4"))
        if module == "torch" and name == "LongStorage":
            return StorageType(np.dtype("<i8"))
        raise pickle.UnpicklingError(f"Unsupported global: {module}.{name}")

    def persistent_load(self, saved_id: Any) -> Storage:
        if not isinstance(saved_id, tuple) or saved_id[0] != "storage":
            raise pickle.UnpicklingError(f"Unsupported persistent id: {saved_id!r}")
        _, storage_type, key, _location, element_count = saved_id
        if not isinstance(storage_type, StorageType):
            raise pickle.UnpicklingError("Unknown storage type")
        raw = self.archive.read(f"archive/data/{key}")
        values = np.frombuffer(raw, dtype=storage_type.dtype, count=element_count)
        return Storage(values)


def load_state_dict(path: Path) -> collections.OrderedDict[str, np.ndarray[Any, Any]]:
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("archive/data.pkl")
        state = TorchStateUnpickler(payload, archive).load()
    if not isinstance(state, collections.OrderedDict):
        raise TypeError("Expected an OrderedDict state dictionary")
    return state


def initializer(name: str, array: np.ndarray[Any, Any]) -> onnx.TensorProto:
    return numpy_helper.from_array(array.astype(np.float32), name=name)


def build_onnx(
    state: collections.OrderedDict[str, np.ndarray[Any, Any]], output_path: Path
) -> None:
    nodes: list[onnx.NodeProto] = []
    initializers: list[onnx.TensorProto] = []
    current = "input"

    # Sequential module indices from the original MIT-licensed Model class.
    stages = (
        (0, 1),
        (3, 4),
        (7, 8),
        (10, 11),
        (14, 15),
        (17, 18),
        (21, 22),
        (24, 25),
        (28, 29),
        (31, 32),
    )
    pool_after = {3, 10, 17, 24, 31}

    for conv_index, bn_index in stages:
        conv_output = f"conv_{conv_index}_out"
        weight_name = f"conv_{conv_index}_weight"
        bias_name = f"conv_{conv_index}_bias"
        initializers.extend(
            [
                initializer(weight_name, state[f"model.{conv_index}.weight"]),
                initializer(bias_name, state[f"model.{conv_index}.bias"]),
            ]
        )
        nodes.append(
            helper.make_node(
                "Conv",
                [current, weight_name, bias_name],
                [conv_output],
                name=f"conv_{conv_index}",
                kernel_shape=[3, 3],
                pads=[1, 1, 1, 1],
                strides=[1, 1],
            )
        )

        bn_output = f"bn_{bn_index}_out"
        bn_inputs = []
        for suffix in ("weight", "bias", "running_mean", "running_var"):
            onnx_name = f"bn_{bn_index}_{suffix}"
            initializers.append(
                initializer(onnx_name, state[f"model.{bn_index}.{suffix}"])
            )
            bn_inputs.append(onnx_name)
        nodes.append(
            helper.make_node(
                "BatchNormalization",
                [conv_output, *bn_inputs],
                [bn_output],
                name=f"batch_norm_{bn_index}",
                epsilon=1e-5,
            )
        )
        relu_output = f"relu_{bn_index}_out"
        nodes.append(
            helper.make_node(
                "Relu", [bn_output], [relu_output], name=f"relu_{bn_index}"
            )
        )
        current = relu_output

        if conv_index in pool_after:
            pool_output = f"pool_{conv_index}_out"
            nodes.append(
                helper.make_node(
                    "MaxPool",
                    [current],
                    [pool_output],
                    name=f"max_pool_{conv_index}",
                    kernel_shape=[2, 2],
                    strides=[2, 2],
                )
            )
            current = pool_output

    nodes.append(helper.make_node("Flatten", [current], ["features"], axis=1))
    linear_weight = state["model.36.weight"]
    linear_bias = state["model.36.bias"]
    initializers.extend(
        [
            initializer("linear_weight", linear_weight),
            initializer("linear_bias", linear_bias),
        ]
    )
    nodes.append(
        helper.make_node(
            "Gemm",
            ["features", "linear_weight", "linear_bias"],
            ["vmax_kt"],
            name="intensity_regression",
            transB=1,
        )
    )

    graph = helper.make_graph(
        nodes,
        "CycloNet INSAT-3D legacy intensity regressor",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 250, 250])],
        [helper.make_tensor_value_info("vmax_kt", TensorProto.FLOAT, [1, 1])],
        initializer=initializers,
    )
    model = helper.make_model(
        graph,
        producer_name="cyclone-ai/legacy-converter",
        producer_version="1.0",
        opset_imports=[helper.make_opsetid("", 18)],
        doc_string=(
            "Converted from cycloneintensity/CrossKnotHacks-Cyclonet. "
            "Legacy demonstration baseline; no held-out validation was published."
        ),
    )
    model.ir_version = 9  # Compatible with broadly available ONNX Runtime versions.
    onnx.checker.check_model(model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    state = load_state_dict(args.source)
    print(f"Loaded {len(state)} tensors from {args.source}")
    build_onnx(state, args.output)
    print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
