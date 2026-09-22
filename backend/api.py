from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.agri_analysis import analyze_crop_supervision_sample, analyze_image, demo_analysis
from backend.services import growth_service, model_inference, qgis_jobs, rf_service, training_jobs
from backend.services.job_runner import get_job, job_to_dict, stop_job


UPLOAD_DIR = PROJECT_ROOT / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "512")) * 1024 * 1024
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="农业智能分析系统 Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class AdviceChatRequest(BaseModel):
    question: str
    analysis: Optional[dict] = None


@app.get("/api/health")
def health() -> Dict[str, Any]:
    has_aliyun_key = bool(os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY"))
    return {
        "status": "ok",
        "service": "agri-web-api",
        "modelInference": model_inference.model_file_exists(),
        "randomForest": rf_service.is_available(),
        "qgis": qgis_jobs.qgis_info(),
        "adviceProvider": "aliyun-dashscope" if has_aliyun_key else "local-fallback",
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Dict[str, str]:
    if not payload.username.strip() or not payload.password.strip():
        raise HTTPException(status_code=400, detail="请输入用户名和密码")
    return {
        "token": f"local-demo-{uuid4().hex}",
        "name": payload.username.strip(),
        "role": "农业分析员",
    }


@app.post("/api/advice/chat")
def advice_chat(payload: AdviceChatRequest) -> Dict[str, str]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="请输入咨询问题")

    context = _build_analysis_context(payload.analysis)
    answer, provider = _call_aliyun_advice(question, context)
    return {"answer": answer, "provider": provider}


@app.get("/api/analysis/demo")
def get_demo_analysis() -> dict:
    return demo_analysis()


@app.get("/api/analysis/crop-supervision/sample")
def get_crop_supervision_sample(sample_index: int = 0) -> dict:
    dataset_path = PROJECT_ROOT / "datasets" / "CropSupervision" / "SiteC_train.hdf5"
    try:
        return analyze_crop_supervision_sample(dataset_path, sample_index=sample_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取 CropSupervision 样本失败：{exc}") from exc


@app.post("/api/analysis/image")
async def analyze_uploaded_image(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="请上传图片文件")

    safe_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    try:
        await _save_upload(file, target)
        return await run_in_threadpool(analyze_image, target)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"图片分析失败：{exc}") from exc
    finally:
        target.unlink(missing_ok=True)


@app.post("/api/analysis/dataset")
async def analyze_uploaded_dataset(file: UploadFile = File(...), sample_index: int = 0) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".hdf5", ".h5", ".tif", ".tiff", ".img"}:
        raise HTTPException(status_code=400, detail="请上传 HDF5、GeoTIFF 或 IMG 遥感数据文件")

    safe_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    try:
        await _save_upload(file, target)
        if suffix in {".hdf5", ".h5"}:
            return await run_in_threadpool(
                analyze_crop_supervision_sample,
                target,
                sample_index,
                32,
                file.filename,
            )
        return await run_in_threadpool(analyze_image, target)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"遥感数据分析失败：{exc}") from exc
    finally:
        target.unlink(missing_ok=True)


@app.post("/api/analysis/model")
async def analyze_with_fcn_model(file: UploadFile = File(...), sample_index: int = 0) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".hdf5", ".h5", ".tif", ".tiff", ".img"}:
        raise HTTPException(status_code=400, detail="请上传 HDF5、GeoTIFF 或 IMG 遥感数据文件")
    if not model_inference.model_file_exists():
        raise HTTPException(status_code=503, detail=f"未找到模型文件：{model_inference.MODEL_PATH}")
    if not model_inference.is_model_ready():
        raise HTTPException(status_code=503, detail="当前 Python 环境缺少 TensorFlow，无法执行模型推理，请在安装 tensorflow 的环境中启动后端")

    safe_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    try:
        await _save_upload(file, target)
        return await run_in_threadpool(
            model_inference.analyze_with_model,
            target,
            sample_index,
            32,
            file.filename,
        )
    except HTTPException:
        raise
    except (IndexError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=f"模型推理失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型推理失败：{exc}") from exc
    finally:
        target.unlink(missing_ok=True)


@app.post("/api/analysis/random-forest")
async def analyze_with_random_forest(
    file: UploadFile = File(...),
    samples: Optional[UploadFile] = None,
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".tif", ".tiff", ".img"}:
        raise HTTPException(status_code=400, detail="随机森林分类需要上传多光谱 GeoTIFF/IMG 影像")
    if not rf_service.is_available():
        raise HTTPException(status_code=503, detail="当前 Python 环境缺少 scikit-learn/rasterio/pandas/scipy")

    image_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    sample_path = UPLOAD_DIR / f"{uuid4().hex}.csv"
    try:
        await _save_upload(file, image_path)
        if samples is not None and (samples.filename or "").strip():
            await _save_upload(samples, sample_path)
        return await run_in_threadpool(
            rf_service.analyze_random_forest,
            image_path,
            sample_path if sample_path.exists() else None,
        )
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=f"随机森林分类失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"随机森林分类失败：{exc}") from exc
    finally:
        image_path.unlink(missing_ok=True)
        sample_path.unlink(missing_ok=True)


@app.post("/api/analysis/growth-comparison")
async def compare_growth_periods(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    sample1: int = Form(0),
    sample2: int = Form(0),
    label1: str = Form("时期一"),
    label2: str = Form("时期二"),
) -> dict:
    allowed = {".hdf5", ".h5"}
    paths: list[Path] = []
    try:
        for upload in (file1, file2):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in allowed:
                raise HTTPException(status_code=400, detail="长势对比需要上传含 /truth 标签的 HDF5 数据集")
            target = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
            await _save_upload(upload, target)
            paths.append(target)
        return await run_in_threadpool(
            growth_service.compare_periods,
            paths[0], sample1, label1.strip() or "时期一",
            paths[1], sample2, label2.strip() or "时期二",
        )
    except HTTPException:
        raise
    except (IndexError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=f"长势对比失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"长势对比失败：{exc}") from exc
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


@app.post("/api/jobs/train-fcn")
async def create_fcn_training_job(
    file: UploadFile = File(...),
    loss: str = Form("Cross-entropy"),
    epochs: int = Form(10),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".hdf5", ".h5"}:
        raise HTTPException(status_code=400, detail="FCN 训练需要上传 HDF5 数据集（含 /data 与 /truth）")

    target = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    try:
        await _save_upload(file, target)
        job = await run_in_threadpool(training_jobs.start_fcn_training, target, loss, epochs)
    except HTTPException:
        raise
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"训练任务创建失败：{exc}") from exc
    return {"jobId": job.id, **job_to_dict(job)}


@app.post("/api/preprocess/qgis")
async def create_qgis_preprocess_job(
    file: UploadFile = File(...),
    epsg: str = Form("EPSG:32650"),
    resolution: float = Form(10.0),
    tileSize: int = Form(128),
    resampling: str = Form("双线性（Bilinear）"),
    maxSamples: int = Form(300),
) -> dict:
    if not qgis_jobs.qgis_ready():
        raise HTTPException(status_code=503, detail="服务器未检测到 QGIS（设置 QGIS_ROOT 环境变量后重启后端）")
    if Path(file.filename or "").suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="请上传 ZIP：每个时相一个子目录，内含 B02.tif 等单波段影像")

    target = UPLOAD_DIR / f"{uuid4().hex}.zip"
    try:
        await _save_upload(file, target)
        job = await run_in_threadpool(
            qgis_jobs.start_preprocess_job,
            target, epsg.strip(), resolution, tileSize, resampling, maxSamples,
        )
    except HTTPException:
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"QGIS 预处理任务创建失败：{exc}") from exc
    return {"jobId": job.id, **job_to_dict(job)}


@app.get("/api/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或后端已重启")
    return job_to_dict(job)


@app.post("/api/jobs/{job_id}/stop")
def stop_running_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或后端已重启")
    stop_job(job)
    return {"status": "stopping"}


@app.get("/api/jobs/{job_id}/artifacts/{name}")
def download_job_artifact(job_id: str, name: str) -> FileResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或后端已重启")
    filename = job.artifacts.get(name)
    if filename:
        path = job.workdir / filename
        if path.exists() and path.resolve().parent == job.workdir.resolve():
            media_type = "application/octet-stream"
            if filename.endswith(".png"):
                media_type = "image/png"
            elif filename.endswith((".h5", ".hdf5")):
                media_type = "application/x-hdf5"
            return FileResponse(str(path), media_type=media_type, filename=filename)
    raise HTTPException(status_code=404, detail="产物不存在")


async def _save_upload(file: UploadFile, target: Path) -> None:
    written = 0
    try:
        with target.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise HTTPException(status_code=413, detail=f"文件超过 {max_mb} MB 上传限制，请上传单样本文件")
                buffer.write(chunk)
    finally:
        await file.close()


def _build_analysis_context(analysis: Optional[dict]) -> str:
    if not analysis:
        return "当前尚未上传影像或生成分析结果。"

    summary = analysis.get("summary", {})
    crop_stats = analysis.get("cropStats", [])
    abnormal = analysis.get("abnormalCells", [])[:5]
    return json.dumps(
        {
            "summary": summary,
            "cropStats": crop_stats,
            "topRiskCells": abnormal,
        },
        ensure_ascii=False,
    )


def _call_aliyun_advice(question: str, context: str) -> tuple[str, str]:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
    model = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    if not api_key:
        return (_local_advice_fallback(question, context), "local-fallback")

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是农业遥感与作物长势分析助手。请基于用户问题和系统分析结果，"
                    "给出务实、可执行、审慎的农业管理建议。不要编造没有出现在上下文中的地块数据。"
                ),
            },
            {
                "role": "user",
                "content": f"当前分析结果：{context}\n\n用户问题：{question}",
            },
        ],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        answer = data["choices"][0]["message"]["content"]
        return answer, "aliyun-dashscope"
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        return (f"阿里云问答暂时不可用，已使用本地建议兜底。\n\n{_local_advice_fallback(question, context)}\n\n错误摘要：{exc}", "local-fallback")


def _local_advice_fallback(question: str, context: str) -> str:
    return (
        "当前后端没有检测到阿里云 DashScope API Key，因此先返回本地兜底建议。\n"
        "请先完成影像上传与长势分析，再结合右侧分类结果、风险区域和三维场景中的黄色/红色地块进行判断。\n"
        f"你的问题是：{question}\n"
        "后续只需要在服务器环境中配置 DASHSCOPE_API_KEY，就可以让这个接口切换到阿里云正式问答。"
    )
