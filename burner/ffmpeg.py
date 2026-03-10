from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from config.config import AppConfig

SRT_BLOCK_PATTERN = re.compile(
    r"(?ms)^\s*(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n{2,}|\Z)"
)


@dataclass
class BurnStyle:
    FontName: str = "Arial"
    FontSize: str = "20"
    PrimaryColour: str = "&H00FFFFFF"
    OutlineColour: str = "&H00000000"
    BackColour: str = "&H64000000"
    Outline: str = "1"
    Shadow: str = "0"
    Alignment: str = "2"
    MarginV: str = "28"


class SubtitleBurner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def burn(
        self,
        video_path: str | Path,
        subtitle_path: str | Path,
        output_path: str | Path,
        secondary_subtitle_path: str | Path | None = None,
        style_overrides: dict[str, str] | None = None,
    ) -> Path:
        try:
            import ffmpeg
        except ImportError as exc:
            raise RuntimeError("ffmpeg-python is not installed. Run `pip install -r requirements.txt`.") from exc

        video_path = Path(video_path)
        subtitle_path = Path(subtitle_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        subtitle_to_use = subtitle_path
        temp_path: Path | None = None
        if secondary_subtitle_path is not None:
            temp_path = self._build_bilingual_subtitles(subtitle_path, Path(secondary_subtitle_path))
            subtitle_to_use = temp_path

        style = BurnStyle()
        for key, value in (style_overrides or {}).items():
            if hasattr(style, key):
                setattr(style, key, str(value))

        try:
            source = ffmpeg.input(str(video_path))
            video_stream = source.video.filter(
                "subtitles",
                self._escape_subtitle_path(subtitle_to_use),
                force_style=self._force_style(style),
            )
            audio_stream = source.audio
            (
                ffmpeg.output(
                    video_stream,
                    audio_stream,
                    str(output_path),
                    vcodec="libx264",
                    acodec="copy",
                    movflags="+faststart",
                )
                .overwrite_output()
                .run()
            )
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

        return output_path

    def _build_bilingual_subtitles(self, primary_path: Path, secondary_path: Path) -> Path:
        primary_blocks = self._parse_srt(primary_path.read_text(encoding="utf-8"))
        secondary_blocks = self._parse_srt(secondary_path.read_text(encoding="utf-8"))
        merged_blocks = []
        secondary_index = 0

        for primary in primary_blocks:
            secondary_text = ""
            while secondary_index < len(secondary_blocks):
                secondary = secondary_blocks[secondary_index]
                if self._timestamp_distance(primary["start"], secondary["start"]) <= 2.0:
                    secondary_text = "\n".join(secondary["text"])
                    secondary_index += 1
                    break
                if self._timestamp_to_seconds(secondary["start"]) > self._timestamp_to_seconds(primary["end"]):
                    break
                secondary_index += 1

            text_lines = primary["text"][:]
            if secondary_text:
                text_lines.append(secondary_text)
            merged_blocks.append(
                "\n".join(
                    [
                        str(primary["index"]),
                        f"{primary['start']} --> {primary['end']}",
                        *text_lines,
                    ]
                )
            )

        handle = tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, dir=str(self.config.temp_dir), encoding="utf-8")
        handle.write("\n\n".join(merged_blocks).strip() + "\n")
        handle.close()
        return Path(handle.name)

    @staticmethod
    def _parse_srt(content: str) -> list[dict[str, object]]:
        parsed: list[dict[str, object]] = []
        normalized = content.replace("\r\n", "\n")
        for match in SRT_BLOCK_PATTERN.finditer(normalized):
            parsed.append(
                {
                    "index": int(match.group(1)),
                    "start": match.group(2),
                    "end": match.group(3),
                    "text": [line.strip() for line in match.group(4).splitlines() if line.strip()],
                }
            )
        return parsed

    @staticmethod
    def _force_style(style: BurnStyle) -> str:
        return ",".join(f"{key}={value}" for key, value in style.__dict__.items())

    @staticmethod
    def _escape_subtitle_path(path: Path) -> str:
        return str(path).replace("\\", "\\\\").replace(":", r"\:").replace(",", r"\,")

    @staticmethod
    def _timestamp_distance(left: str, right: str) -> float:
        return abs(SubtitleBurner._timestamp_to_seconds(left) - SubtitleBurner._timestamp_to_seconds(right))

    @staticmethod
    def _timestamp_to_seconds(timestamp: str) -> float:
        hours, minutes, seconds, milliseconds = timestamp.replace(",", ":").split(":")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
