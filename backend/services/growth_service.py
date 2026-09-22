from __future__ import annotations

from pathlib import Path

from backend.services.agri_analysis import analyze_crop_supervision_sample


def compare_periods(
    first_path: Path,
    first_sample: int,
    first_label: str,
    second_path: Path,
    second_sample: int,
    second_label: str,
) -> dict:
    first = analyze_crop_supervision_sample(first_path, first_sample, display_name=first_label)
    second = analyze_crop_supervision_sample(second_path, second_sample, display_name=second_label)
    before = first["summary"]
    after = second["summary"]
    return {
        "firstPeriod": first,
        "secondPeriod": second,
        "comparison": {
            "firstLabel": first_label,
            "secondLabel": second_label,
            "avgGrowthDelta": round(after["avgGrowth"] - before["avgGrowth"], 3),
            "healthyRatioDelta": round(after["healthyRatio"] - before["healthyRatio"], 3),
            "riskRatioDelta": round(after["riskRatio"] - before["riskRatio"], 3),
            "estimatedYieldDeltaKg": round(after["estimatedYieldKg"] - before["estimatedYieldKg"], 2),
            "methodology": "对两个带 /truth 标签的 HDF5 样本使用同一归一化与网格聚合规则进行比较。",
        },
    }
