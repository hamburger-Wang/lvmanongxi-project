from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests


def parse_download_form(html: str) -> tuple[str, dict[str, str]]:
    action_match = re.search(r'<form[^>]+id="download-form"[^>]+action="([^"]+)"', html)
    if not action_match:
        raise RuntimeError("Could not find Google Drive download confirmation form.")

    action = action_match.group(1).replace("&amp;", "&")
    params: dict[str, str] = {}
    for name, value in re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', html):
        params[name] = value
    return action, params


def human_size(value: int | None) -> str:
    if value is None:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{value}B"


def download(file_id: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".part")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    warning = session.get(
        "https://drive.google.com/uc",
        params={"export": "download", "id": file_id},
        timeout=60,
    )
    warning.raise_for_status()

    if "download-form" in warning.text:
        action, params = parse_download_form(warning.text)
        url = urljoin(warning.url, action)
        display_size = re.search(r"\(([^()]+)\)</span> is too large", warning.text)
        if display_size:
            print(f"Google Drive reports file size: {display_size.group(1)}")
        request_params = params
    else:
        url = warning.url
        request_params = {}

    existing = partial.stat().st_size if partial.exists() else 0
    headers = {}
    if existing:
        headers["Range"] = f"bytes={existing}-"
        print(f"Resuming from {human_size(existing)}")

    with session.get(url, params=request_params, headers=headers, stream=True, timeout=60) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type.lower():
            sample = response.text[:300]
            raise RuntimeError(f"Download returned an HTML page instead of file data: {sample}")

        mode = "ab" if existing and response.status_code == 206 else "wb"
        if existing and response.status_code != 206:
            print("Server did not honor Range request; restarting download.")
            existing = 0

        content_length = response.headers.get("Content-Length")
        total = int(content_length) + existing if content_length and existing else int(content_length or 0) or None
        downloaded = existing
        started = time.time()
        last_report = 0.0

        with partial.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                if now - last_report >= 5:
                    elapsed = max(now - started, 0.001)
                    speed = (downloaded - existing) / elapsed
                    if total:
                        pct = downloaded / total * 100
                        print(f"{pct:5.1f}%  {human_size(downloaded)} / {human_size(total)}  {human_size(int(speed))}/s", flush=True)
                    else:
                        print(f"{human_size(downloaded)} downloaded  {human_size(int(speed))}/s", flush=True)
                    last_report = now

    partial.replace(output)
    print(f"Saved to {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    download(args.file_id, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
