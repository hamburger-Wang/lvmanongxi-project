from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from config import (
    GIS_DATASET_SCRIPT,
    GIS_PREPROCESS_SCRIPT,
    QGIS_PREFIX_PATH,
    GIS_RESAMPLING_OPTIONS,
    QGIS_PYTHON,
)
from backend.services.job_runner import Job, append_log, run_process, start_job


def qgis_ready() -> bool:
    return bool(QGIS_PYTHON and Path(QGIS_PYTHON).is_file() and GIS_PREPROCESS_SCRIPT.is_file())


def qgis_info() -> dict:
    return {"ready": qgis_ready(), "python": QGIS_PYTHON or None, "prefixPath": QGIS_PREFIX_PATH or None}


def start_preprocess_job(
    archive_path: Path,
    epsg: str,
    resolution: float,
    tile_size: int,
    resampling: str,
    max_samples: int,
):
    if not 1 <= tile_size <= 2048:
        raise ValueError("切片尺寸应在 1 到 2048 之间")
    if max_samples < 0:
        raise ValueError("最大样本数不能为负数")
    def worker(job: Job) -> None:
        archive = job.workdir / "source_imagery.zip"
        shutil.move(str(archive_path), str(archive))
        input_dir = job.workdir / "input"
        tiles_dir = job.workdir / "tiles"
        temp_dir = job.workdir / "temp"
        output_dir = job.workdir / "dataset"
        _extract_archive(archive, input_dir)
        append_log(job, "已安全解压影像 ZIP，开始 QGIS 预处理。")
        run_process(
            job,
            [
                QGIS_PYTHON, GIS_PREPROCESS_SCRIPT, "--input-dir", input_dir,
                "--tiles-dir", tiles_dir, "--temp-dir", temp_dir, "--prefix-path", QGIS_PREFIX_PATH,
                "--epsg", epsg, "--resolution", str(resolution), "--tile-size", str(tile_size),
                "--resampling", str(GIS_RESAMPLING_OPTIONS.get(resampling, 1)),
            ],
            job.workdir,
        )
        run_process(
            job,
            [
                sys.executable, GIS_DATASET_SCRIPT, "--tiles-dir", tiles_dir, "--out-dir", output_dir,
                "--max-samples", str(max_samples),
            ],
            job.workdir,
        )
        for key, artifact in {"dataset": output_dir / "data.h5", "labels": output_dir / "label.csv"}.items():
            if artifact.exists():
                target = job.workdir / artifact.name
                shutil.copy2(artifact, target)
                job.artifacts[key] = target.name

    return start_job("qgis-preprocess", worker)


def _extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if target != base and base not in target.parents:
                raise ValueError("ZIP 包含越界路径，已拒绝解压")
        package.extractall(destination)
