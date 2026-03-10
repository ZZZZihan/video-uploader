from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import os


@dataclass
class APISettings:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: float = 120.0


@dataclass
class AppConfig:
    output_dir: Path = Path("output")
    temp_dir: Path = Path("tmp")
    youtube_cookies_path: Path = Path("cookies/youtube.txt")
    bilibili_cookies_path: Path = Path("cookies/bilibili.json")
    proxy: str | None = None
    openai: APISettings = field(
        default_factory=lambda: APISettings(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )
    )
    minimax: APISettings = field(
        default_factory=lambda: APISettings(
            api_key=os.getenv("MINIMAX_API_KEY", ""),
            base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1/text/chatcompletion_v2"),
            model=os.getenv("MINIMAX_MODEL", "MiniMax-Text-01"),
        )
    )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        config = cls()
        if path is None:
            return config

        path = Path(path)
        if not path.exists():
            return config

        yaml = cls._require_yaml()
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.from_dict(raw_data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        openai_data = data.get("openai", {})
        minimax_data = data.get("minimax", {})
        return cls(
            output_dir=Path(data.get("output_dir", "output")),
            temp_dir=Path(data.get("temp_dir", "tmp")),
            youtube_cookies_path=Path(data.get("youtube_cookies_path", "cookies/youtube.txt")),
            bilibili_cookies_path=Path(data.get("bilibili_cookies_path", "cookies/bilibili.json")),
            proxy=data.get("proxy"),
            openai=APISettings(
                api_key=str(openai_data.get("api_key", os.getenv("OPENAI_API_KEY", ""))),
                base_url=str(openai_data.get("base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))),
                model=str(openai_data.get("model", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))),
                timeout=float(openai_data.get("timeout", 120.0)),
            ),
            minimax=APISettings(
                api_key=str(minimax_data.get("api_key", os.getenv("MINIMAX_API_KEY", ""))),
                base_url=str(minimax_data.get("base_url", os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1/text/chatcompletion_v2"))),
                model=str(minimax_data.get("model", os.getenv("MINIMAX_MODEL", "MiniMax-Text-01"))),
                timeout=float(minimax_data.get("timeout", 120.0)),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_dir"] = str(self.output_dir)
        data["temp_dir"] = str(self.temp_dir)
        data["youtube_cookies_path"] = str(self.youtube_cookies_path)
        data["bilibili_cookies_path"] = str(self.bilibili_cookies_path)
        return data

    def save(self, path: str | Path) -> Path:
        yaml = self._require_yaml()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def ensure_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.youtube_cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.bilibili_cookies_path.parent.mkdir(parents=True, exist_ok=True)

    def resolve_output(self, *parts: str) -> Path:
        return self.output_dir.joinpath(*parts)

    @staticmethod
    def _require_yaml() -> Any:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("pyyaml is required to load or save YAML config files.") from exc
        return yaml
