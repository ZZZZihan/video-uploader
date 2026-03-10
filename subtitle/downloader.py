from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from config.config import AppConfig


class YouTubeSubtitleDownloader:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def list_available_subtitles(self, url: str) -> dict[str, dict[str, object]]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp is not installed. Run `pip install -r requirements.txt`.") from exc

        options = {
            "skip_download": True,
            "quiet": True,
            "proxy": self.config.proxy,
        }
        cookie_path = self.config.youtube_cookies_path
        if cookie_path.exists():
            options["cookiefile"] = str(cookie_path)

        with YoutubeDL({key: value for key, value in options.items() if value is not None}) as ydl:
            info = ydl.extract_info(url, download=False)

        subtitles = info.get("subtitles", {}) or {}
        automatic = info.get("automatic_captions", {}) or {}
        results: dict[str, dict[str, object]] = {}

        for language, items in subtitles.items():
            results[language] = {
                "source": "manual",
                "formats": sorted({entry.get("ext", "unknown") for entry in items}),
            }
        for language, items in automatic.items():
            results.setdefault(language, {})
            results[language].update(
                {
                    "source": "manual+auto" if results[language].get("source") == "manual" else "automatic",
                    "formats": sorted(
                        set(results[language].get("formats", [])) | {entry.get("ext", "unknown") for entry in items}
                    ),
                }
            )
        return dict(sorted(results.items()))

    def download_subtitle(
        self,
        url: str,
        language: str = "zh",
        output_path: str | Path | None = None,
    ) -> Path:
        available = self.list_available_subtitles(url)
        if language not in available:
            raise ValueError(f"Subtitle language `{language}` not available. Found: {', '.join(available) or 'none'}")

        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp is not installed. Run `pip install -r requirements.txt`.") from exc

        requested_output = Path(output_path) if output_path is not None else self.config.output_dir / f"{language}.srt"
        output_is_file = bool(requested_output.suffix)
        target_dir = requested_output.parent if output_is_file else requested_output
        target_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=str(self.config.temp_dir)) as temp_dir:
            temp_dir_path = Path(temp_dir)
            options = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [language],
                "subtitlesformat": "srt/best",
                "proxy": self.config.proxy,
                "outtmpl": str(temp_dir_path / "%(title)s [%(id)s].%(ext)s"),
                "quiet": False,
            }
            cookie_path = self.config.youtube_cookies_path
            if cookie_path.exists():
                options["cookiefile"] = str(cookie_path)

            with YoutubeDL({key: value for key, value in options.items() if value is not None}) as ydl:
                ydl.download([url])

            subtitle_file = self._find_downloaded_subtitle(temp_dir_path, language)
            if subtitle_file.suffix.lower() == ".vtt":
                converted = subtitle_file.with_suffix(".srt")
                converted.write_text(self._convert_vtt_to_srt(subtitle_file.read_text(encoding="utf-8")), encoding="utf-8")
                subtitle_file = converted

            if output_is_file:
                requested_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(subtitle_file), str(requested_output))
                return requested_output

            target_path = target_dir / subtitle_file.name
            shutil.move(str(subtitle_file), str(target_path))
            return target_path

    @staticmethod
    def _find_downloaded_subtitle(directory: Path, language: str) -> Path:
        patterns = [
            f"*{language}*.srt",
            f"*{language}*.vtt",
            "*.srt",
            "*.vtt",
        ]
        for pattern in patterns:
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[0]
        raise FileNotFoundError("yt-dlp did not produce a subtitle file.")

    @staticmethod
    def _convert_vtt_to_srt(content: str) -> str:
        lines = []
        cue_lines: list[str] = []
        index = 1

        def flush_cue() -> None:
            nonlocal index
            if not cue_lines:
                return
            lines.append(str(index))
            lines.extend(cue_lines)
            lines.append("")
            cue_lines.clear()
            index += 1

        for raw_line in content.splitlines():
            line = raw_line.strip("\ufeff")
            if not line or line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:") or line.startswith("NOTE"):
                if cue_lines:
                    flush_cue()
                continue
            if "-->" in line:
                line = line.replace(".", ",")
            cue_lines.append(line)

        flush_cue()
        return "\n".join(lines).strip() + "\n"
