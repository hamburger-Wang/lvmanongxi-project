from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import warnings

import numpy as np
from PIL import Image
import tables
import tifffile

from core.growth_comparison import GrowthComparison


CROP_LABELS = {
    1: {"key": "corn", "name": "玉米"},
    2: {"key": "wheat", "name": "小麦"},
    3: {"key": "rice", "name": "水稻"},
    4: {"key": "potato", "name": "马铃薯"},
    5: {"key": "other", "name": "其他"},
}


@dataclass
class Cell:
    x: int
    z: int
    crop_id: int
    growth: float
    moisture: float
    anomaly: float

    def to_dict(self) -> dict[str, Any]:
        crop = CROP_LABELS[self.crop_id]
        return {
            "x": self.x,
            "z": self.z,
            "cropId": self.crop_id,
            "crop": crop["key"],
            "cropName": crop["name"],
            "growth": round(self.growth, 3),
            "moisture": round(self.moisture, 3),
            "anomaly": round(self.anomaly, 3),
            "height": round(0.2 + self.growth * _crop_height_factor(self.crop_id), 3),
        }


def analyze_image(image_path: Path, grid_size: int = 26) -> dict[str, Any]:
    """Convert a single aerial image into semantic crop-growth scene data.

    This is a lightweight bridge for the current project: it uses image color
    and texture cues to produce the same kind of classified grid that the
    existing growth comparison module expects. A trained model can later replace
    this function while keeping the API contract unchanged.
    """
    image = _open_remote_image(image_path)
    image.thumbnail((720, 720))
    arr = np.asarray(image).astype(np.float32) / 255.0

    h, w, _ = arr.shape
    cell_h = max(1, h // grid_size)
    cell_w = max(1, w // grid_size)

    cells: list[Cell] = []
    class_map = np.zeros((grid_size, grid_size), dtype=int)
    growth_map = np.zeros((grid_size, grid_size), dtype=float)

    for z in range(grid_size):
        for x in range(grid_size):
            patch = arr[z * cell_h : min((z + 1) * cell_h, h), x * cell_w : min((x + 1) * cell_w, w)]
            if patch.size == 0:
                continue

            mean = patch.mean(axis=(0, 1))
            std = patch.std(axis=(0, 1)).mean()
            r, g, b = mean.tolist()
            brightness = float(mean.mean())
            excess_green = float(2 * g - r - b)
            ndvi_like = float((g - r) / max(g + r, 0.001))
            moisture = float(np.clip((b + g * 0.7 - r * 0.35), 0, 1))
            growth = float(np.clip(0.46 + ndvi_like * 1.15 + excess_green * 0.45 + brightness * 0.08 - std * 0.18, 0.05, 0.98))
            crop_id = _infer_crop_id(r, g, b, brightness, std, moisture, growth)
            anomaly = float(np.clip(0.72 - growth + max(0, r - g) * 0.5, 0, 1))

            class_map[z, x] = crop_id
            growth_map[z, x] = growth
            cells.append(Cell(x=x, z=z, crop_id=crop_id, growth=growth, moisture=moisture, anomaly=anomaly))

    comparison = GrowthComparison()
    area = comparison.calculate_area(class_map)
    yield_prediction = comparison.predict_yield(area, pixel_size=1.0)

    crop_stats = _build_crop_stats(class_map, growth_map, area, yield_prediction)
    abnormal_cells = [cell.to_dict() for cell in sorted(cells, key=lambda item: item.anomaly, reverse=True)[:12]]
    avg_growth = float(growth_map.mean()) if growth_map.size else 0

    return {
        "source": {
            "filename": image_path.name,
            "width": image.width,
            "height": image.height,
            "gridSize": grid_size,
            "format": image_path.suffix.lstrip(".").upper() or "IMAGE",
            "analysisMode": "heuristic",
            "labelSource": "颜色与纹理规则",
            "sampleIndex": 0,
            "sampleCount": 1,
        },
        "summary": {
            "avgGrowth": round(avg_growth, 3),
            "healthyRatio": round(float(np.mean(growth_map >= 0.72)), 3),
            "warningRatio": round(float(np.mean((growth_map >= 0.45) & (growth_map < 0.72))), 3),
            "riskRatio": round(float(np.mean(growth_map < 0.45)), 3),
            "estimatedYieldKg": round(float(sum(yield_prediction.values())), 2),
            "mainCrop": max(crop_stats, key=lambda item: item["area"])["name"] if crop_stats else "未知",
        },
        "cropStats": crop_stats,
        "abnormalCells": abnormal_cells,
        "scene": {
            "cells": [cell.to_dict() for cell in cells],
            "cropProfiles": _crop_profiles(),
        },
        "methodology": _methodology(
            classification="基于影像颜色与纹理的启发式分类",
            growth="基于可见光通道构造的归一化长势指标",
            estimated_yield="按分类面积与项目内置系数估算",
            model_inference=False,
        ),
        "advice": build_advice(avg_growth, crop_stats),
    }


def _open_remote_image(image_path: Path) -> Image.Image:
    if image_path.suffix.lower() not in {".tif", ".tiff", ".img"}:
        return Image.open(image_path).convert("RGB")

    raw = np.asarray(tifffile.imread(image_path))
    raw = np.squeeze(raw)
    if raw.ndim == 2:
        raw = np.repeat(raw[..., np.newaxis], 3, axis=-1)
    elif raw.ndim == 3:
        if raw.shape[0] <= 32 and raw.shape[1] > 32 and raw.shape[2] > 32:
            raw = np.moveaxis(raw, 0, -1)
        if raw.shape[-1] == 1:
            raw = np.repeat(raw, 3, axis=-1)
        elif raw.shape[-1] == 2:
            raw = np.concatenate([raw, raw[..., :1]], axis=-1)
        else:
            raw = raw[..., :3]
    else:
        raise ValueError(f"不支持的遥感影像维度: {raw.shape}")

    rgb = np.zeros(raw.shape, dtype=np.float32)
    for channel in range(3):
        values = raw[..., channel].astype(np.float32)
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            continue
        low, high = np.percentile(finite, [2, 98])
        if high <= low:
            high = low + 1
        rgb[..., channel] = np.clip((values - low) / (high - low), 0, 1)
    return Image.fromarray((rgb * 255).astype(np.uint8), mode="RGB")


def demo_analysis() -> dict[str, Any]:
    grid = 26
    y, x = np.mgrid[0:grid, 0:grid]
    class_map = np.where(x < grid * 0.34, 1, np.where(y < grid * 0.52, 3, np.where(x > grid * 0.7, 2, 4)))
    wave = np.sin(x / 3.2) * 0.1 + np.cos(y / 4.6) * 0.08
    growth_map = np.clip(0.72 + wave - ((x - 19) ** 2 + (y - 17) ** 2) / 900, 0.22, 0.96)

    cells = [
        Cell(
            x=int(cx),
            z=int(cz),
            crop_id=int(class_map[cz, cx]),
            growth=float(growth_map[cz, cx]),
            moisture=float(np.clip(0.62 + np.sin(cx / 4) * 0.12, 0.2, 0.95)),
            anomaly=float(np.clip(0.78 - growth_map[cz, cx], 0, 1)),
        )
        for cz in range(grid)
        for cx in range(grid)
    ]
    comparison = GrowthComparison()
    area = comparison.calculate_area(class_map)
    yield_prediction = comparison.predict_yield(area, pixel_size=1.0)
    crop_stats = _build_crop_stats(class_map, growth_map, area, yield_prediction)
    avg_growth = float(growth_map.mean())

    return {
        "source": {
            "filename": "系统示例地块",
            "width": grid,
            "height": grid,
            "gridSize": grid,
            "format": "SYNTHETIC",
            "analysisMode": "demo",
            "labelSource": "程序生成的演示数据",
            "sampleIndex": 0,
            "sampleCount": 1,
        },
        "summary": {
            "avgGrowth": round(avg_growth, 3),
            "healthyRatio": round(float(np.mean(growth_map >= 0.72)), 3),
            "warningRatio": round(float(np.mean((growth_map >= 0.45) & (growth_map < 0.72))), 3),
            "riskRatio": round(float(np.mean(growth_map < 0.45)), 3),
            "estimatedYieldKg": round(float(sum(yield_prediction.values())), 2),
            "mainCrop": max(crop_stats, key=lambda item: item["area"])["name"],
        },
        "cropStats": crop_stats,
        "abnormalCells": [cell.to_dict() for cell in sorted(cells, key=lambda item: item.anomaly, reverse=True)[:12]],
        "scene": {"cells": [cell.to_dict() for cell in cells], "cropProfiles": _crop_profiles()},
        "methodology": _methodology(
            classification="程序生成的演示分类网格",
            growth="程序生成的演示长势曲面",
            estimated_yield="按分类面积与项目内置系数估算",
            model_inference=False,
        ),
        "advice": build_advice(avg_growth, crop_stats),
    }


def analyze_crop_supervision_sample(
    hdf5_path: Path,
    sample_index: int = 0,
    grid_size: int = 32,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Read one CropSupervision HDF5 sample and convert it to UI scene data."""
    if not hdf5_path.exists():
        raise FileNotFoundError(f"未找到数据集文件: {hdf5_path}")

    with tables.open_file(str(hdf5_path), mode="r") as hdf5_file:
        if not hasattr(hdf5_file.root, "data"):
            raise ValueError("HDF5 缺少 /data 节点")
        if not hasattr(hdf5_file.root, "truth"):
            raise ValueError("HDF5 缺少 /truth 标签；当前尚未接入模型，无法对无标签样本分类")
        sample_count = int(hdf5_file.root.data.shape[0])
        if sample_index < 0 or sample_index >= sample_count:
            raise IndexError(f"样本索引超出范围: {sample_index}, 可用范围 0-{sample_count - 1}")
        image_series = hdf5_file.root.data[sample_index]
        labels = hdf5_file.root.truth[sample_index]

    growth_pixels = _growth_from_timeseries(image_series)
    moisture_pixels = _moisture_from_timeseries(image_series)
    class_map, growth_map, moisture_map = _aggregate_crop_supervision_grid(labels, growth_pixels, moisture_pixels, grid_size)
    cells = _crop_supervision_cells(class_map, growth_map, moisture_map)
    crop_stats = _crop_supervision_stats(class_map, growth_map)
    avg_growth = float(growth_map.mean()) if growth_map.size else 0

    return {
        "source": {
            "filename": f"{display_name or hdf5_path.name}#sample{sample_index}",
            "width": int(labels.shape[1]),
            "height": int(labels.shape[0]),
            "gridSize": grid_size,
            "format": "CropSupervision HDF5",
            "analysisMode": "dataset-label",
            "labelSource": "HDF5 /truth 标注",
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
        "scene": {
            "cells": cells,
            "cropProfiles": _crop_profiles()
            | {
                "class_one": {"name": "作物类别 1", "baseColor": "#2f8f45", "healthyColor": "#1f7a3b", "riskColor": "#d4a832"},
                "class_two": {"name": "作物类别 2", "baseColor": "#42a36d", "healthyColor": "#2f9161", "riskColor": "#c5bd52"},
            },
        },
        "methodology": _methodology(
            classification="读取 CropSupervision 数据集 /truth 人工标注",
            growth="对 /data 时序多通道信号做 5%-95% 分位归一化",
            estimated_yield="按网格面积、归一化长势与演示系数估算",
            model_inference=False,
        ),
        "advice": build_advice(avg_growth, crop_stats),
    }


def _methodology(
    classification: str,
    growth: str,
    estimated_yield: str,
    model_inference: bool,
) -> dict[str, Any]:
    return {
        "classification": classification,
        "growth": growth,
        "estimatedYield": estimated_yield,
        "modelInference": model_inference,
        "notice": "当前结果用于系统联调与可视化研究，长势和产量尚未经过田间标定，不能直接作为生产决策依据。",
    }


def class_map_to_weighted_area(class_map: np.ndarray, growth_map: np.ndarray) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for crop_id, crop in CROP_LABELS.items():
        mask = class_map == crop_id
        weighted[crop["name"]] = float(growth_map[mask].sum()) if np.any(mask) else 0
    return weighted


def build_advice(avg_growth: float, crop_stats: list[dict[str, Any]]) -> list[str]:
    advice = []
    if avg_growth >= 0.76:
        advice.append("整体长势良好，建议维持当前水肥管理节奏，并持续监测边缘区域。")
    elif avg_growth >= 0.52:
        advice.append("长势处于中等水平，建议结合土壤墒情进行分区追肥和补水。")
    else:
        advice.append("存在明显长势风险，建议优先核查低长势区的灌溉、病虫害和苗情。")

    weak = [item for item in crop_stats if item["avgGrowth"] < 0.58]
    if weak:
        names = "、".join(item["name"] for item in weak[:3])
        advice.append(f"{names} 区域平均长势偏低，可作为巡田和复核采样的优先区域。")
    advice.append("三维场景中的黄色和红色区域代表重点关注地块，可点击查看作物类型和长势评分。")
    return advice


def _build_crop_stats(
    class_map: np.ndarray,
    growth_map: np.ndarray,
    area: dict[str, float],
    yield_prediction: dict[str, float],
) -> list[dict[str, Any]]:
    total = max(int(class_map.size), 1)
    stats = []
    for crop_id, crop in CROP_LABELS.items():
        mask = class_map == crop_id
        if not np.any(mask):
            continue
        name = crop["name"]
        stats.append(
            {
                "id": crop_id,
                "key": crop["key"],
                "name": name,
                "area": int(area.get(name, 0)),
                "ratio": round(float(np.sum(mask) / total), 3),
                "avgGrowth": round(float(growth_map[mask].mean()), 3),
                "estimatedYieldKg": round(float(yield_prediction.get(name, 0)), 2),
            }
        )
    return sorted(stats, key=lambda item: item["area"], reverse=True)


def _growth_from_timeseries(image_series: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        signal = np.nanmean(np.where(image_series > 0, image_series, np.nan), axis=(2, 3))
        fallback = np.nanmean(image_series, axis=(2, 3))
    signal = np.where(np.isfinite(signal), signal, fallback)
    valid = signal[np.isfinite(signal)]
    if valid.size == 0:
        return np.zeros(signal.shape, dtype=float)
    low, high = np.percentile(valid, [5, 95])
    if high <= low:
        return np.full(signal.shape, 0.5, dtype=float)
    return np.clip((signal - low) / (high - low), 0.05, 0.98)


def _moisture_from_timeseries(image_series: np.ndarray) -> np.ndarray:
    channel_count = image_series.shape[-1]
    selected = image_series[..., min(2, channel_count - 1)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        signal = np.nanmean(np.where(selected > 0, selected, np.nan), axis=2)
        fallback = np.nanmean(selected, axis=2)
    signal = np.where(np.isfinite(signal), signal, fallback)
    valid = signal[np.isfinite(signal)]
    if valid.size == 0:
        return np.zeros(signal.shape, dtype=float)
    low, high = np.percentile(valid, [5, 95])
    if high <= low:
        return np.full(signal.shape, 0.5, dtype=float)
    return np.clip((signal - low) / (high - low), 0.05, 0.98)


def _aggregate_crop_supervision_grid(
    labels: np.ndarray,
    growth_pixels: np.ndarray,
    moisture_pixels: np.ndarray,
    grid_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = labels.shape
    cell_h = max(1, height // grid_size)
    cell_w = max(1, width // grid_size)
    class_map = np.zeros((grid_size, grid_size), dtype=int)
    growth_map = np.zeros((grid_size, grid_size), dtype=float)
    moisture_map = np.zeros((grid_size, grid_size), dtype=float)

    for z in range(grid_size):
        for x in range(grid_size):
            row_slice = slice(z * cell_h, height if z == grid_size - 1 else min((z + 1) * cell_h, height))
            col_slice = slice(x * cell_w, width if x == grid_size - 1 else min((x + 1) * cell_w, width))
            label_patch = labels[row_slice, col_slice]
            values, counts = np.unique(label_patch, return_counts=True)
            class_map[z, x] = int(values[np.argmax(counts)])
            growth_map[z, x] = float(np.nanmean(growth_pixels[row_slice, col_slice]))
            moisture_map[z, x] = float(np.nanmean(moisture_pixels[row_slice, col_slice]))
    return class_map, growth_map, moisture_map


def _crop_supervision_cells(class_map: np.ndarray, growth_map: np.ndarray, moisture_map: np.ndarray) -> list[dict[str, Any]]:
    label_meta = {
        0: {"crop": "other", "name": "背景/非目标", "heightFactor": 0.22},
        1: {"crop": "class_one", "name": "作物类别 1", "heightFactor": 1.2},
        2: {"crop": "class_two", "name": "作物类别 2", "heightFactor": 0.9},
    }
    cells = []
    for z in range(class_map.shape[0]):
        for x in range(class_map.shape[1]):
            label = int(class_map[z, x])
            meta = label_meta.get(label, label_meta[0])
            growth = float(np.clip(growth_map[z, x], 0.05, 0.98))
            moisture = float(np.clip(moisture_map[z, x], 0.05, 0.98))
            anomaly = float(np.clip(0.72 - growth + (0.25 if label == 0 else 0), 0, 1))
            cells.append(
                {
                    "x": int(x),
                    "z": int(z),
                    "cropId": label,
                    "crop": meta["crop"],
                    "cropName": meta["name"],
                    "growth": round(growth, 3),
                    "moisture": round(moisture, 3),
                    "anomaly": round(anomaly, 3),
                    "height": round(0.16 + growth * meta["heightFactor"], 3),
                }
            )
    return cells


def _crop_supervision_stats(class_map: np.ndarray, growth_map: np.ndarray) -> list[dict[str, Any]]:
    labels = {
        0: {"key": "other", "name": "背景/非目标"},
        1: {"key": "class_one", "name": "作物类别 1"},
        2: {"key": "class_two", "name": "作物类别 2"},
    }
    total = max(int(class_map.size), 1)
    stats = []
    for label, meta in labels.items():
        mask = class_map == label
        if not np.any(mask):
            continue
        area = int(np.sum(mask))
        avg_growth = float(growth_map[mask].mean())
        stats.append(
            {
                "id": label,
                "key": meta["key"],
                "name": meta["name"],
                "area": area,
                "ratio": round(area / total, 3),
                "avgGrowth": round(avg_growth, 3),
                "estimatedYieldKg": round(float(area * avg_growth * (0.6 if label else 0.05)), 2),
            }
        )
    return sorted(stats, key=lambda item: item["area"], reverse=True)


def _infer_crop_id(r: float, g: float, b: float, brightness: float, texture: float, moisture: float, growth: float) -> int:
    if growth < 0.2 or brightness < 0.16:
        return 5
    if moisture > 0.58 and b > r * 0.72:
        return 3
    if texture > 0.13 and g > r:
        return 1
    if r > g * 0.92 and brightness > 0.34:
        return 2
    if brightness < 0.3:
        return 4
    return 1 if g >= b else 3


def _crop_height_factor(crop_id: int) -> float:
    return {
        1: 1.4,
        2: 0.74,
        3: 0.55,
        4: 0.42,
        5: 0.24,
    }.get(crop_id, 0.3)


def _crop_profiles() -> dict[str, dict[str, Any]]:
    return {
        "corn": {"name": "玉米", "baseColor": "#2f8f45", "healthyColor": "#1f7a3b", "riskColor": "#d4a832"},
        "wheat": {"name": "小麦", "baseColor": "#8aa83f", "healthyColor": "#6f9b37", "riskColor": "#d6b44b"},
        "rice": {"name": "水稻", "baseColor": "#42a36d", "healthyColor": "#2f9161", "riskColor": "#c5bd52"},
        "potato": {"name": "马铃薯", "baseColor": "#6a9d48", "healthyColor": "#4f883f", "riskColor": "#bd8947"},
        "other": {"name": "其他", "baseColor": "#7c8276", "healthyColor": "#6f7d69", "riskColor": "#a05d4b"},
    }
