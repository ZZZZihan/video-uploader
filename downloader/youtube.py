from __future__ import annotations

from pathlib import Path
import shutil

from config.config import AppConfig


class YouTubeDownloader:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def download(
        self,
        url: str,
        output_path: str | Path | None = None,
        format_selector: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        proxy: str | None = None,
    ) -> Path:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp is not installed. Run `pip install -r requirements.txt`.") from exc

        destination = Path(output_path) if output_path is not None else self.config.output_dir
        output_is_file = bool(destination.suffix)
        working_dir = destination.parent if output_is_file else destination
        working_dir.mkdir(parents=True, exist_ok=True)

        options = {
            "format": format_selector,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "proxy": proxy or self.config.proxy,
            "outtmpl": str(working_dir / "%(title)s [%(id)s].%(ext)s"),
            "restrictfilenames": True,
            "quiet": False,
        }

        cookie_path = self.config.youtube_cookies_path
        if cookie_path.exists():
            options["cookiefile"] = str(cookie_path)

        # Try primary format first, fallback to format 18 (360p) if failed
        try:
            with YoutubeDL({key: value for key, value in options.items() if value is not None}) as ydl:
                info = ydl.extract_info(url, download=True)
                guessed_path = Path(info.get("_filename") or ydl.prepare_filename(info))
        except Exception as primary_error:
            # Fallback to format 18 (360p) which usually works even with bot protection
            fallback_options = options.copy()
            fallback_options["format"] = "18"
            print(f"⚠️ 高级格式下载失败，回退到360p: {str(primary_error)[:100]}...")
            with YoutubeDL({key: value for key, value in fallback_options.items() if value is not None}) as ydl:
                info = ydl.extract_info(url, download=True)
                guessed_path = Path(info.get("_filename") or ydl.prepare_filename(info))

        final_path = self._resolve_download_path(working_dir, guessed_path)
        if output_is_file:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(final_path), str(destination))
            return destination
        return final_path

    @staticmethod
    def _resolve_download_path(working_dir: Path, guessed_path: Path) -> Path:
        candidates = [
            working_dir / guessed_path.name,
            working_dir / f"{guessed_path.stem}.mp4",
            working_dir / f"{guessed_path.stem}.mkv",
            working_dir / f"{guessed_path.stem}.webm",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Downloaded file not found in {working_dir}")
