from __future__ import annotations

from pathlib import Path

from config.config import AppConfig


class DouyinUploaderGuide:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def generate_watermarked_version(
        self,
        video_path: str | Path,
        output_path: str | Path,
        watermark_text: str = "搬运自 YouTube",
    ) -> Path:
        try:
            import ffmpeg
        except ImportError as exc:
            raise RuntimeError("ffmpeg-python is not installed. Run `pip install -r requirements.txt`.") from exc

        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        drawtext = (
            "drawtext="
            f"text='{self._escape_drawtext(watermark_text)}':"
            "x=w-tw-28:y=28:fontsize=28:"
            "fontcolor=white:borderw=2:bordercolor=black@0.7"
        )
        (
            ffmpeg.input(str(video_path))
            .output(str(output_path), vf=drawtext, acodec="copy", vcodec="libx264", movflags="+faststart")
            .overwrite_output()
            .run()
        )
        return output_path

    def render_manual_instructions(self, video_path: str | Path, caption: str = "") -> str:
        video_path = Path(video_path)
        lines = [
            "Douyin manual upload guide:",
            f"1. Open Douyin creator center or the mobile app and select upload.",
            f"2. Choose the prepared file: {video_path}",
        ]
        if caption:
            lines.append(f"3. Suggested caption: {caption}")
            lines.append("4. Review cover, topic tags, and publishing time before posting.")
        else:
            lines.append("3. Add caption, topic tags, and cover before posting.")
        return "\n".join(lines)

    @staticmethod
    def _escape_drawtext(value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")
