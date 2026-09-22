from __future__ import annotations

import shutil
import sys
from pathlib import Path

import tables

from backend.services.job_runner import Job, run_process, start_job

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def start_fcn_training(dataset_path: Path, loss: str, epochs: int):
    if not 1 <= epochs <= 500:
        raise ValueError("训练轮数应在 1 到 500 之间")
    with tables.open_file(str(dataset_path), mode="r") as h5_file:
        if not hasattr(h5_file.root, "data") or not hasattr(h5_file.root, "truth"):
            raise ValueError("FCN 训练数据必须同时包含 /data 与 /truth")
        if int(h5_file.root.data.shape[0]) < 91:
            raise ValueError("当前 FCN 训练实现至少需要 91 个样本")

    def worker(job: Job) -> None:
        source = job.workdir / "training_dataset.h5"
        shutil.move(str(dataset_path), str(source))
        model_path = job.workdir / "fcn_model.hdf5"
        preview_path = job.workdir / "training_preview.png"
        run_process(
            job,
            [
                sys.executable, PROJECT_ROOT / "core" / "crop_model.py", "--mode", "train",
                "--data_path", source, "--out_loss", loss, "--epochs", str(epochs),
                "--model_path", model_path, "--img_path", preview_path,
            ],
            PROJECT_ROOT,
        )
        for key, artifact in {"model": model_path, "preview": preview_path}.items():
            if artifact.exists():
                job.artifacts[key] = artifact.name

    return start_job("fcn-training", worker)
