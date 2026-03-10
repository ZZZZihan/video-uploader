from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import click

from config.config import AppConfig

DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


def _runtime_config(
    base_config: AppConfig,
    output_override: Path | None = None,
    proxy_override: str | None = None,
) -> AppConfig:
    config = copy.deepcopy(base_config)
    if output_override and not output_override.suffix:
        config.output_dir = output_override
    if proxy_override:
        config.proxy = proxy_override
    config.ensure_directories()
    return config


def _normalize_output_path(command_output: Path | None, default_dir: Path, default_name: str) -> Path:
    if command_output is None:
        return default_dir / default_name
    if command_output.suffix:
        command_output.parent.mkdir(parents=True, exist_ok=True)
        return command_output
    command_output.mkdir(parents=True, exist_ok=True)
    return command_output / default_name


def _parse_style_option(raw_style: str | None) -> dict[str, str]:
    if not raw_style:
        return {}

    parsed: dict[str, str] = {}
    for item in raw_style.split(","):
        if "=" not in item:
            raise click.BadParameter("Style must be key=value pairs separated by commas.")
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


@click.group()
@click.option(
    "--config-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=DEFAULT_CONFIG_PATH,
    show_default=True,
    help="YAML config file path.",
)
@click.option(
    "--output",
    "root_output",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Default output directory override.",
)
@click.option("--proxy", "root_proxy", default=None, help="Default network proxy.")
@click.pass_context
def main(ctx: click.Context, config_file: Path, root_output: Path | None, root_proxy: str | None) -> None:
    """Video upload automation CLI."""
    config = AppConfig.load(config_file)
    if root_output is not None:
        config.output_dir = root_output
    if root_proxy:
        config.proxy = root_proxy
    config.ensure_directories()

    ctx.obj = {
        "config": config,
        "config_file": config_file,
    }


@main.command()
@click.option("--url", required=True, help="YouTube video URL.")
@click.option("--proxy", default=None, help="Per-command proxy override.")
@click.option(
    "--output",
    "command_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory or explicit file path.",
)
@click.option(
    "--format",
    "format_selector",
    default="bestvideo+bestaudio/best",
    show_default=True,
    help="yt-dlp format selector.",
)
@click.option(
    "--cookies",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Override YouTube cookies file.",
)
@click.pass_obj
def download(
    obj: dict[str, Any],
    url: str,
    proxy: str | None,
    command_output: Path | None,
    format_selector: str,
    cookies: Path | None,
) -> None:
    """Download a video from YouTube."""
    from downloader.youtube import YouTubeDownloader

    config = _runtime_config(obj["config"], command_output, proxy)
    if cookies is not None:
        config.youtube_cookies_path = cookies

    downloader = YouTubeDownloader(config)
    destination = command_output or config.output_dir
    file_path = downloader.download(
        url=url,
        output_path=destination,
        format_selector=format_selector,
    )
    click.echo(str(file_path))


@main.command()
@click.option("--url", default=None, help="Video URL for fetching platform subtitles.")
@click.option(
    "--video",
    "video_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Local video/audio file for Whisper fallback.",
)
@click.option("--proxy", default=None, help="Per-command proxy override.")
@click.option(
    "--output",
    "command_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output subtitle file or directory.",
)
@click.option(
    "--language",
    default="zh",
    show_default=True,
    help="Subtitle language code, e.g. zh or en.",
)
@click.option(
    "--source",
    type=click.Choice(["auto", "youtube", "whisper"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Subtitle source selection.",
)
@click.option(
    "--model-size",
    default="small",
    show_default=True,
    help="faster-whisper model size.",
)
@click.option(
    "--correct-with",
    type=click.Choice(["none", "openai", "minimax"], case_sensitive=False),
    default="none",
    show_default=True,
    help="LLM provider for subtitle correction.",
)
@click.pass_obj
def subtitle(
    obj: dict[str, Any],
    url: str | None,
    video_path: Path | None,
    proxy: str | None,
    command_output: Path | None,
    language: str,
    source: str,
    model_size: str,
    correct_with: str,
) -> None:
    """Fetch or generate subtitles."""
    from subtitle.handler import SubtitleHandler

    if not url and not video_path:
        raise click.UsageError("Either --url or --video is required.")

    config = _runtime_config(obj["config"], command_output if command_output and not command_output.suffix else None, proxy)
    handler = SubtitleHandler(config)
    default_name = (video_path.stem if video_path else "subtitle") + ".srt"
    output_path = _normalize_output_path(command_output, config.output_dir, default_name) if command_output else None
    result = handler.process(
        url=url,
        video_path=video_path,
        output_path=output_path,
        language=language,
        source=source.lower(),
        model_size=model_size,
        correction_provider=correct_with.lower(),
    )
    click.echo(f"{result.source}: {result.path}")


@main.command()
@click.option(
    "--video",
    "video_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="Input video file.",
)
@click.option(
    "--subtitle",
    "subtitle_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="Primary subtitle file (SRT).",
)
@click.option(
    "--secondary-subtitle",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Optional second subtitle file for bilingual burn-in.",
)
@click.option(
    "--output",
    "command_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output video file or directory.",
)
@click.option(
    "--style",
    default=None,
    help="ASS style overrides, e.g. FontName=Noto Sans CJK SC,FontSize=18,MarginV=28.",
)
@click.pass_obj
def burn(
    obj: dict[str, Any],
    video_path: Path,
    subtitle_path: Path,
    secondary_subtitle: Path | None,
    command_output: Path | None,
    style: str | None,
) -> None:
    """Burn subtitles into a video."""
    from burner.ffmpeg import SubtitleBurner

    config = _runtime_config(obj["config"])
    burner = SubtitleBurner(config)
    output_path = _normalize_output_path(command_output, config.output_dir, f"{video_path.stem}.burned.mp4")
    burned_path = burner.burn(
        video_path=video_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        secondary_subtitle_path=secondary_subtitle,
        style_overrides=_parse_style_option(style),
    )
    click.echo(str(burned_path))


@main.command("upload-bilibili")
@click.option(
    "--video",
    "video_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="Video file to upload.",
)
@click.option("--title", required=True, help="Bilibili title.")
@click.option("--description", default="", help="Video description.")
@click.option("--tags", default="", help="Comma-separated tags.")
@click.option(
    "--cover",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Optional cover image.",
)
@click.option("--tid", default=None, help="Bilibili category/tid.")
@click.option(
    "--scan-login/--no-scan-login",
    default=True,
    show_default=True,
    help="Start QR login before upload.",
)
@click.pass_obj
def upload_bilibili(
    obj: dict[str, Any],
    video_path: Path,
    title: str,
    description: str,
    tags: str,
    cover: Path | None,
    tid: str | None,
    scan_login: bool,
) -> None:
    """Upload a video to Bilibili."""
    from uploader.bilibili import BilibiliUploader

    config = _runtime_config(obj["config"])
    uploader = BilibiliUploader(config)

    if scan_login:
        session = uploader.request_qr_login()
        click.echo("Scan this QR URL in the Bilibili app and confirm login:")
        click.echo(session.qr_url)
        cookie_path = uploader.wait_for_qr_login(session.qrcode_key)
        click.echo(f"Saved cookies to {cookie_path}")

    result = uploader.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=[item.strip() for item in tags.split(",") if item.strip()],
        cover_path=cover,
        tid=tid,
    )
    click.echo(result)


@main.command("upload-douyin")
@click.option(
    "--video",
    "video_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="Local video file.",
)
@click.option("--caption", default="", help="Suggested Douyin caption.")
@click.option(
    "--generate-watermark/--no-generate-watermark",
    default=False,
    show_default=True,
    help="Generate a watermarked export before manual upload.",
)
@click.option(
    "--watermark-text",
    default="搬运自 YouTube",
    show_default=True,
    help="Watermark text when watermark export is enabled.",
)
@click.option(
    "--output",
    "command_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Watermarked output file or directory.",
)
@click.pass_obj
def upload_douyin(
    obj: dict[str, Any],
    video_path: Path,
    caption: str,
    generate_watermark: bool,
    watermark_text: str,
    command_output: Path | None,
) -> None:
    """Prepare a Douyin upload guide."""
    from uploader.douyin import DouyinUploaderGuide

    config = _runtime_config(obj["config"], command_output if command_output and not command_output.suffix else None)
    guide = DouyinUploaderGuide(config)

    final_video = video_path
    if generate_watermark:
        output_path = _normalize_output_path(command_output, config.output_dir, f"{video_path.stem}.douyin.mp4")
        final_video = guide.generate_watermarked_version(
            video_path=video_path,
            output_path=output_path,
            watermark_text=watermark_text,
        )
        click.echo(f"Watermarked video: {final_video}")

    click.echo(guide.render_manual_instructions(final_video, caption))


if __name__ == "__main__":
    main()
