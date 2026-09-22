from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np

from backend.services import agri_analysis


def is_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("rasterio", "sklearn", "pandas", "scipy"))


def analyze_random_forest(image_path: Path, sample_path: Path | None) -> dict[str, Any]:
    if sample_path is None:
        raise ValueError("随机森林需要同时上传带 red、green、blue、nir、label 列的地面样本 CSV")
    from core.crop_model_dry import CropClassificationSystem

    classifier = CropClassificationSystem(n_estimators=100)
    features, labels = classifier.load_training_data(str(sample_path))
    if len(np.unique(labels)) < 2:
        raise ValueError("训练样本至少应包含两类作物标签")
    classifier.train(features, labels)
    label_pixels = classifier.predict_image(str(image_path))
    with __import__("rasterio").open(image_path) as dataset:
        bands = dataset.read().astype(float)
    signal = np.nanmean(bands, axis=0)
    low, high = np.nanpercentile(signal, [5, 95])
    growth_pixels = np.clip((signal - low) / max(high - low, 1e-6), 0.05, 0.98)
    moisture_pixels = growth_pixels
    class_map, growth_map, moisture_map = agri_analysis._aggregate_crop_supervision_grid(
        label_pixels, growth_pixels, moisture_pixels, 32
    )
    cells = agri_analysis._crop_supervision_cells(class_map, growth_map, moisture_map)
    crop_stats = agri_analysis._crop_supervision_stats(class_map, growth_map)
    avg_growth = float(growth_map.mean())
    return {
        "source": {
            "filename": image_path.name,
            "width": int(label_pixels.shape[1]),
            "height": int(label_pixels.shape[0]),
            "gridSize": 32,
            "format": image_path.suffix.lstrip(".").upper(),
            "analysisMode": "random-forest",
            "labelSource": f"随机森林；训练样本 {sample_path.name}",
            "sampleIndex": 0,
            "sampleCount": 1,
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
            classification="以用户提供的带标签样本训练随机森林后进行分类",
            growth="以多光谱波段均值做归一化长势代理指标",
            estimated_yield="按网格面积、归一化长势与演示系数估算",
            model_inference=True,
        ),
        "advice": agri_analysis.build_advice(avg_growth, crop_stats),
    }
