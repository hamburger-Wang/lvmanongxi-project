from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.agri_analysis import analyze_crop_supervision_sample, analyze_image, demo_analysis


UPLOAD_DIR = PROJECT_ROOT / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="农业智能分析系统 Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class AdviceChatRequest(BaseModel):
    question: str
    analysis: dict | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agri-web-api"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, str]:
    if not payload.username.strip() or not payload.password.strip():
        raise HTTPException(status_code=400, detail="请输入用户名和密码")
    return {
        "token": f"local-demo-{uuid4().hex}",
        "name": payload.username.strip(),
        "role": "农业分析员",
    }


@app.post("/api/advice/chat")
def advice_chat(payload: AdviceChatRequest) -> dict[str, str]:
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
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        return analyze_image(target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"图片分析失败：{exc}") from exc


@app.post("/api/analysis/dataset")
async def analyze_uploaded_dataset(file: UploadFile = File(...), sample_index: int = 0) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".hdf5", ".h5", ".tif", ".tiff", ".img"}:
        raise HTTPException(status_code=400, detail="请上传 HDF5、GeoTIFF 或 IMG 遥感数据文件")

    safe_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if suffix in {".hdf5", ".h5"}:
            return analyze_crop_supervision_sample(target, sample_index=sample_index, display_name=file.filename)
        return analyze_image(target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"遥感数据分析失败：{exc}") from exc


def _build_analysis_context(analysis: dict | None) -> str:
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
