from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx

from config.config import AppConfig
from utils.cookie import CookieManager


QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


@dataclass
class QRLoginSession:
    qrcode_key: str
    qr_url: str


class BilibiliUploader:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def request_qr_login(self) -> QRLoginSession:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(QR_GENERATE_URL)
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data") or {}
        qrcode_key = data.get("qrcode_key")
        qr_url = data.get("url")
        if not qrcode_key or not qr_url:
            raise RuntimeError(f"Unexpected Bilibili QR login response: {payload}")
        return QRLoginSession(qrcode_key=qrcode_key, qr_url=qr_url)

    def wait_for_qr_login(self, qrcode_key: str, timeout_seconds: int = 180, interval_seconds: int = 2) -> Path:
        deadline = time.time() + timeout_seconds
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            while time.time() < deadline:
                response = client.get(QR_POLL_URL, params={"qrcode_key": qrcode_key})
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data") or {}
                status_code = int(data.get("code", -1))
                if status_code == 0:
                    CookieManager.save_httpx_cookies(self.config.bilibili_cookies_path, client.cookies)
                    return self.config.bilibili_cookies_path
                if status_code == 86038:
                    raise RuntimeError("Bilibili QR code expired before login completed.")
                time.sleep(interval_seconds)

        raise TimeoutError("Timed out waiting for Bilibili QR login confirmation.")

    def upload_video(
        self,
        video_path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        cover_path: str | Path | None = None,
        tid: str | None = None,
    ) -> str:
        video_path = Path(video_path)
        cover_path = Path(cover_path) if cover_path is not None else None
        tags = tags or []

        command = self._build_biliup_command(video_path, title, description, tags, cover_path, tid)
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                "biliup upload failed. Ensure biliup is installed and verify CLI flags for your version.\n"
                f"Command: {' '.join(command)}\n"
                f"Details: {stderr}"
            )

        output = completed.stdout.strip() or f"Uploaded {video_path.name} via biliup."
        return output

    def _build_biliup_command(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        cover_path: Path | None,
        tid: str | None,
    ) -> list[str]:
        module_cmd = [sys.executable, "-m", "biliup"]
        direct_cmd = ["biliup"]
        base_cmd = direct_cmd if shutil.which("biliup") else module_cmd

        command = [*base_cmd, "upload", str(video_path), "--title", title]
        if description:
            command.extend(["--desc", description])
        if tags:
            command.extend(["--tag", ",".join(tags)])
        if cover_path is not None:
            command.extend(["--cover", str(cover_path)])
        if tid is not None:
            command.extend(["--tid", str(tid)])
        if self.config.bilibili_cookies_path.exists():
            command.extend(["--cookies", str(self.config.bilibili_cookies_path)])
        return command
