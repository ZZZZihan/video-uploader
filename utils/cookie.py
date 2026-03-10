from __future__ import annotations

from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path
from typing import Iterable
import json

import httpx


class CookieManager:
    @staticmethod
    def load_json(path: str | Path) -> list[dict[str, str]]:
        path = Path(path)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Cookie JSON must contain a list of cookie objects.")
        return data

    @staticmethod
    def save_json(path: str | Path, cookies: Iterable[dict[str, str]]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(cookies), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def save_httpx_cookies(path: str | Path, cookies: httpx.Cookies) -> Path:
        serialized = []
        for cookie in cookies.jar:
            serialized.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain or "",
                    "path": cookie.path or "/",
                    "secure": bool(cookie.secure),
                }
            )
        return CookieManager.save_json(path, serialized)

    @staticmethod
    def load_netscape(path: str | Path) -> MozillaCookieJar:
        jar = MozillaCookieJar(str(path))
        if Path(path).exists():
            jar.load(ignore_discard=True, ignore_expires=True)
        return jar

    @staticmethod
    def save_netscape(path: str | Path, cookies: Iterable[dict[str, str]]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        jar = MozillaCookieJar(str(path))
        for item in cookies:
            jar.set_cookie(
                Cookie(
                    version=0,
                    name=item["name"],
                    value=item["value"],
                    port=None,
                    port_specified=False,
                    domain=item.get("domain", ""),
                    domain_specified=bool(item.get("domain")),
                    domain_initial_dot=str(item.get("domain", "")).startswith("."),
                    path=item.get("path", "/"),
                    path_specified=True,
                    secure=bool(item.get("secure", False)),
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
        jar.save(ignore_discard=True, ignore_expires=True)
        return path

    @staticmethod
    def to_cookie_header(cookies: Iterable[dict[str, str]]) -> str:
        return "; ".join(f"{item['name']}={item['value']}" for item in cookies)
