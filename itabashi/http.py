from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TransientHTTPError(Exception):
    def __init__(self, status: int | None, message: str = "") -> None:
        super().__init__(message or f"transient HTTP error: {status}")
        self.status = status


class APIError(Exception):
    pass


@dataclass
class JSONHTTPClient:
    timeout: float = 10.0
    user_agent: str = "itabashi/0.1"

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code <= 599:
                raise TransientHTTPError(exc.code, str(exc)) from exc
            raise APIError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise TransientHTTPError(None, str(exc)) from exc
        except json.JSONDecodeError as exc:
            raise APIError("malformed JSON response") from exc

    def get_bytes(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code <= 599:
                raise TransientHTTPError(exc.code, str(exc)) from exc
            raise APIError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise TransientHTTPError(None, str(exc)) from exc
