from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.config import AppConfig
from subtitle.downloader import YouTubeSubtitleDownloader
from subtitle.llm_correction import SubtitleCorrector
from subtitle.whisper import WhisperTranscriber


@dataclass
class SubtitleResult:
    path: Path
    source: str
    corrected: bool = False


class SubtitleHandler:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.youtube = YouTubeSubtitleDownloader(config)
        self.whisper = WhisperTranscriber(config)
        self.corrector = SubtitleCorrector(config)

    def process(
        self,
        url: str | None = None,
        video_path: str | Path | None = None,
        output_path: str | Path | None = None,
        language: str = "zh",
        source: str = "auto",
        model_size: str = "small",
        correction_provider: str = "none",
    ) -> SubtitleResult:
        destination = Path(output_path) if output_path is not None else None
        video_path = Path(video_path) if video_path is not None else None

        source = source.lower()
        correction_provider = correction_provider.lower()
        if source not in {"auto", "youtube", "whisper"}:
            raise ValueError(f"Unsupported subtitle source: {source}")

        subtitle_path: Path | None = None
        source_used = source
        youtube_error: Exception | None = None

        if source in {"auto", "youtube"} and url:
            try:
                subtitle_path = self.youtube.download_subtitle(
                    url=url,
                    language=language,
                    output_path=destination,
                )
                source_used = "youtube"
            except Exception as exc:
                youtube_error = exc
                if source == "youtube":
                    raise

        if subtitle_path is None:
            if video_path is None:
                if youtube_error is None:
                    raise ValueError("A local --video is required when Whisper fallback is needed.")
                raise RuntimeError(f"YouTube subtitles unavailable and Whisper fallback requires --video: {youtube_error}") from youtube_error

            whisper_output = destination
            if whisper_output is None:
                whisper_output = self.config.output_dir / f"{video_path.stem}.srt"

            subtitle_path = self.whisper.transcribe(
                media_path=video_path,
                output_path=whisper_output,
                language=language if language in {"zh", "en"} else None,
                model_size=model_size,
            )
            source_used = "whisper"

        corrected = False
        if correction_provider != "none":
            corrected_output = destination
            if corrected_output is None:
                corrected_output = subtitle_path.with_name(f"{subtitle_path.stem}.corrected.srt")
            subtitle_path = self.corrector.correct_file(
                input_path=subtitle_path,
                output_path=corrected_output,
                provider=correction_provider,
            )
            corrected = True

        return SubtitleResult(path=subtitle_path, source=source_used, corrected=corrected)
