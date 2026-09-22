from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOB_ROOT = PROJECT_ROOT / "backend" / "jobs"
JOB_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class Job:
    id: str
    kind: str
    workdir: Path
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    logs: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    stop_requested: threading.Event = field(default_factory=threading.Event, repr=False)


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def start_job(kind: str, worker) -> Job:
    job_id = uuid4().hex
    job = Job(id=job_id, kind=kind, workdir=JOB_ROOT / job_id)
    job.workdir.mkdir(parents=True, exist_ok=False)
    with _jobs_lock:
        _jobs[job_id] = job

    def run() -> None:
        job.status = "running"
        job.started_at = time.time()
        try:
            worker(job)
            if job.stop_requested.is_set():
                job.status = "stopped"
            elif job.status == "running":
                job.status = "completed"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            append_log(job, f"ERROR: {exc}")
        finally:
            job.finished_at = time.time()

    threading.Thread(target=run, name=f"agri-{kind}-{job_id[:8]}", daemon=True).start()
    return job


def append_log(job: Job, message: str) -> None:
    job.logs.append(message.rstrip())
    if len(job.logs) > 300:
        del job.logs[:-300]


def run_process(job: Job, args: list[str], cwd: Path) -> None:
    append_log(job, "运行命令: " + " ".join(str(part) for part in args))
    process = subprocess.Popen(
        [str(part) for part in args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        append_log(job, line)
        if job.stop_requested.is_set() and process.poll() is None:
            process.terminate()
    exit_code = process.wait()
    if job.stop_requested.is_set():
        return
    if exit_code != 0:
        raise RuntimeError(f"子进程退出码为 {exit_code}")


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def stop_job(job: Job) -> None:
    job.stop_requested.set()
    if job.status in {"queued", "running"}:
        job.status = "stopping"


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "createdAt": job.created_at,
        "startedAt": job.started_at,
        "finishedAt": job.finished_at,
        "error": job.error,
        "logs": job.logs[-80:],
        "artifacts": list(job.artifacts),
    }
