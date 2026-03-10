from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

import httpx

from config.config import APISettings, AppConfig

SRT_BLOCK_PATTERN = re.compile(
    r"(?ms)^\s*(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n{2,}|\Z)"
)


@dataclass
class SubtitleBlock:
    index: int
    start: str
    end: str
    text_lines: list[str]


class SubtitleCorrector:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def correct_file(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        provider: str = "openai",
        chunk_char_limit: int = 3200,
    ) -> Path:
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(input_path)

        blocks = self.parse_srt(input_path.read_text(encoding="utf-8"))
        if not blocks:
            raise ValueError(f"No SRT blocks found in {input_path}")

        corrected_blocks: list[SubtitleBlock] = []
        for chunk in self.chunk_blocks(blocks, chunk_char_limit):
            corrected_blocks.extend(self._correct_chunk(chunk, provider))

        destination = Path(output_path) if output_path is not None else input_path.with_name(f"{input_path.stem}.corrected.srt")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.serialize_srt(corrected_blocks), encoding="utf-8")
        return destination

    def _correct_chunk(self, chunk: list[SubtitleBlock], provider: str) -> list[SubtitleBlock]:
        raw_chunk = self.serialize_srt(chunk)
        response_text = self._call_provider(provider.lower(), raw_chunk)
        corrected_chunk = self.parse_srt(self._strip_code_fences(response_text))
        if len(corrected_chunk) != len(chunk):
            return chunk

        merged: list[SubtitleBlock] = []
        for original, corrected in zip(chunk, corrected_chunk):
            merged.append(
                SubtitleBlock(
                    index=original.index,
                    start=original.start,
                    end=original.end,
                    text_lines=corrected.text_lines or original.text_lines,
                )
            )
        return merged

    def _call_provider(self, provider: str, srt_chunk: str) -> str:
        system_prompt = (
            "You correct subtitle grammar and punctuation. Preserve subtitle count, numbering, "
            "timestamps, and SRT layout. Only edit subtitle text. Return plain SRT only."
        )
        user_prompt = (
            "Fix obvious recognition mistakes, punctuation, capitalization, and spacing without changing meaning.\n\n"
            f"{srt_chunk}"
        )

        if provider == "openai":
            return self._call_openai(self.config.openai, system_prompt, user_prompt)
        if provider == "minimax":
            return self._call_minimax(self.config.minimax, system_prompt, user_prompt)
        raise ValueError(f"Unsupported correction provider: {provider}")

    @staticmethod
    def parse_srt(content: str) -> list[SubtitleBlock]:
        blocks: list[SubtitleBlock] = []
        normalized = content.replace("\r\n", "\n")
        for match in SRT_BLOCK_PATTERN.finditer(normalized):
            text = match.group(4).strip()
            blocks.append(
                SubtitleBlock(
                    index=int(match.group(1)),
                    start=match.group(2),
                    end=match.group(3),
                    text_lines=[line.rstrip() for line in text.splitlines() if line.strip()],
                )
            )
        return blocks

    @staticmethod
    def serialize_srt(blocks: list[SubtitleBlock]) -> str:
        rendered = []
        for block in blocks:
            rendered.append(
                "\n".join(
                    [
                        str(block.index),
                        f"{block.start} --> {block.end}",
                        *block.text_lines,
                    ]
                )
            )
        return "\n\n".join(rendered).strip() + "\n"

    @staticmethod
    def chunk_blocks(blocks: list[SubtitleBlock], char_limit: int) -> list[list[SubtitleBlock]]:
        chunks: list[list[SubtitleBlock]] = []
        current_chunk: list[SubtitleBlock] = []
        current_length = 0

        for block in blocks:
            rendered = SubtitleCorrector.serialize_srt([block])
            if current_chunk and current_length + len(rendered) > char_limit:
                chunks.append(current_chunk)
                current_chunk = []
                current_length = 0
            current_chunk.append(block)
            current_length += len(rendered)

            if block.text_lines and block.text_lines[-1].endswith(("。", "！", "？", ".", "!", "?")) and current_length >= char_limit * 0.7:
                chunks.append(current_chunk)
                current_chunk = []
                current_length = 0

        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    @staticmethod
    def _call_openai(settings: APISettings, system_prompt: str, user_prompt: str) -> str:
        if not settings.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai is not installed. Run `pip install -r requirements.txt`.") from exc

        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
        )
        response = client.chat.completions.create(
            model=settings.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        message = response.choices[0].message.content
        if isinstance(message, str):
            return message
        if isinstance(message, list):
            return "\n".join(part.text for part in message if getattr(part, "type", "") == "text")
        raise RuntimeError("OpenAI response did not contain text content.")

    @staticmethod
    def _call_minimax(settings: APISettings, system_prompt: str, user_prompt: str) -> str:
        if not settings.api_key:
            raise RuntimeError("MINIMAX_API_KEY is missing.")

        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        }
        payload = SubtitleCorrector._build_minimax_payload(settings.model, system_prompt, user_prompt, settings.base_url)

        with httpx.Client(timeout=settings.timeout) as client:
            response = client.post(settings.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return SubtitleCorrector._extract_minimax_text(data)

    @staticmethod
    def _build_minimax_payload(model: str, system_prompt: str, user_prompt: str, base_url: str) -> dict[str, Any]:
        # Check for OpenAI-compatible endpoints (chat/completions or chatcompletion)
        normalized_url = base_url.rstrip("/").lower()
        is_openai_compatible = "chat/completions" in normalized_url or "chatcompletion" in normalized_url

        if is_openai_compatible:
            return {
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        return {
            "model": model,
            "temperature": 0.2,
            "tokens_to_generate": 2048,
            "messages": [
                {"sender_type": "SYSTEM", "text": system_prompt},
                {"sender_type": "USER", "text": user_prompt},
            ],
        }

    @staticmethod
    def _extract_minimax_text(payload: dict[str, Any]) -> str:
        if "reply" in payload and isinstance(payload["reply"], str):
            return payload["reply"]
        if "choices" in payload:
            message = payload["choices"][0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "\n".join(parts)
        if "data" in payload and isinstance(payload["data"], dict):
            for key in ("reply", "text", "content"):
                value = payload["data"].get(key)
                if isinstance(value, str):
                    return value
        raise RuntimeError(f"Unsupported MiniMax response format: {json.dumps(payload)[:400]}")

    @staticmethod
    def _strip_code_fences(content: str) -> str:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return cleaned
