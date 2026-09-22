from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

import numpy as np
import tables

from backend.services import agri_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.getenv("FCN_MODEL_PATH", PROJECT_ROOT / "models" / "B.hdf5"))


def model_file_exists() -> bool:
    return MODEL_PATH.is_file()


def is_model_ready() -> bool:
    return importlib.util.find_spec("tensorflow") is not None


def analyze_with_model(path: Path, sample_index: int, grid_size: int, display_name: str) -> dict[str, Any]:
    if path.suffix.lower() not in {".h5", ".hdf5"}:
        raise ValueError("当前 FCN 模型仅接收含 /data 的 HDF5 时序数据")
    with tables.open_file(str(path), mode="r") as h5_file:
        if not hasattr(h5_file.root, "data"):
            raise ValueError("HDF5 缺少 /data 节点")
        sample_count = int(h5_file.root.data.shape[0])
        if not 0 <= sample_index < sample_count:
            raise IndexError(f"样本索引超出范围: 0-{sample_count - 1}")
        series = np.asarray(h5_file.root.data[sample_index])

    if series.ndim != 4:
        raise ValueError(f"FCN 需要 (H, W, T, C) 单样本，当前形状为 {series.shape}")
    from core.crop_model import F1_Loss, IOU_Loss, SupCon_Loss
    from tensorflow.keras.models import load_model

    model = load_model(
        MODEL_PATH,
        custom_objects={"IOU_Loss": IOU_Loss, "F1_Loss": F1_Loss, "SupCon_Loss": SupCon_Loss},
    )
    prediction = model.predict(np.expand_dims(series, axis=0), verbose=0)
    if isinstance(prediction, list):
        prediction = prediction[0]
    labels = np.argmax(np.asarray(prediction)[0], axis=-1).astype(int)
    growth_pixels = agri_analysis._growth_from_timeseries(series)
    moisture_pixels = agri_analysis._moisture_from_timeseries(series)
    class_map, growth_map, moisture_map = agri_analysis._aggregate_crop_supervision_grid(
        labels, growth_pixels, moisture_pixels, grid_size
    )
    cells = agri_analysis._crop_supervision_cells(class_map, growth_map, moisture_map)
    crop_stats = agri_analysis._crop_supervision_stats(class_map, growth_map)
    avg_growth = float(growth_map.mean())
    return {
        "source": {
            "filename": f"{display_name}#sample{sample_index}",
            "width": int(labels.shape[1]),
            "height": int(labels.shape[0]),
            "gridSize": grid_size,
            "format": "HDF5 FCN inference",
            "analysisMode": "model-inference",
            "labelSource": f"FCN 模型预测：{MODEL_PATH.name}",
            "sampleIndex": sample_index,
            "sampleCount": sample_count,
        },
        "summary": {
            "avgGrowth": round(avg_growth, 3),
            "healthyRatio": round(float(np.mean(growth_map >= 0.72)), 3),
            "warningRatio": round(float(np.mean((growth_map >= 0.45) & (growth_map < 0.72))), 3),
            "riskRatio": round(float(np.mean(growth_map < 0.45)), 3),
            "estimatedYieldKg": round(float(np.sum(growth_map[class_map > 0]) * 1.6), 2),
            "mainCrop": max(crop_stats, key=lambda item: item["area"])["name"] if crop_stats else "未知",
        },
        "cropStats": crop_stats,
        "abnormalCells": sorted(cells, key=lambda item: item["anomaly"], reverse=True)[:12],
        "scene": {"cells": cells, "cropProfiles": agri_analysis._crop_profiles()},
        "methodology": agri_analysis._methodology(
            classification=f"由 FCN 模型 {MODEL_PATH.name} 预测",
            growth="对输入时序多通道信号做 5%-95% 分位归一化",
            estimated_yield="按网格面积、归一化长势与演示系数估算",
            model_inference=True,
        ),
        "advice": agri_analysis.build_advice(avg_growth, crop_stats),
    }
