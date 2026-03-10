from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.config import AppConfig


@dataclass
class WhisperSegment:
    index: int
    start: float
    end: float
    text: str


class WhisperTranscriber:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def transcribe(
        self,
        media_path: str | Path,
        output_path: str | Path | None = None,
        language: str | None = None,
        model_size: str = "small",
    ) -> Path:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed. Run `pip install -r requirements.txt`.") from exc

        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(media_path)

        target_path = Path(output_path) if output_path is not None else self.config.output_dir / f"{media_path.stem}.srt"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        model = WhisperModel(model_size, device="auto", compute_type="int8")
        # Disable vad_filter which may cause empty results for some videos
        segments, _info = model.transcribe(
            str(media_path),
            language=language,
            vad_filter=False,
            beam_size=5,
        )

        srt_segments = []
        for index, segment in enumerate(segments, start=1):
            text = segment.text.strip()
            if not text:
                continue
            srt_segments.append(
                WhisperSegment(
                    index=index,
                    start=float(segment.start),
                    end=float(segment.end),
                    text=text,
                )
            )

        target_path.write_text(self._to_srt(srt_segments), encoding="utf-8")
        return target_path

    @staticmethod
    def _to_srt(segments: list[WhisperSegment]) -> str:
        blocks = []
        for segment in segments:
            blocks.append(
                "\n".join(
                    [
                        str(segment.index),
                        f"{WhisperTranscriber._format_timestamp(segment.start)} --> {WhisperTranscriber._format_timestamp(segment.end)}",
                        segment.text,
                    ]
                )
            )
        return "\n\n".join(blocks).strip() + "\n"

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total_milliseconds = max(int(seconds * 1000), 0)
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
