from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def cache_key(*parts: str | None) -> str:
    import hashlib

    joined = "\x1f".join(normalize_text(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Track:
    artist: str
    title: str
    album: str = ""
    album_art_url: str = ""

    @property
    def identity(self) -> str:
        return cache_key(self.artist, self.title, self.album)


@dataclass(frozen=True)
class RenderPayload:
    track: Track
    lyrics: str | None
    album_art_path: Path | None = None


@dataclass(frozen=True)
class Config:
    lastfm_api_key: str
    lastfm_user: str
    genius_access_token: str
    poll_seconds: int = 20
    output_mode: str = "inky"
    png_output: Path = Path("out/current.png")
    cache_dir: Path = Path(".cache/itabashi")

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        api_key = os.environ.get("LASTFM_API_KEY", "").strip()
        user = os.environ.get("LASTFM_USER", "").strip()
        genius_access_token = os.environ.get("GENIUS_ACCESS_TOKEN", "").strip()
        if not api_key:
            raise ValueError("LASTFM_API_KEY is required")
        if not user:
            raise ValueError("LASTFM_USER is required")
        if not genius_access_token:
            raise ValueError("GENIUS_ACCESS_TOKEN is required")

        poll_seconds = int(os.environ.get("POLL_SECONDS", "20"))
        output_mode = os.environ.get("OUTPUT_MODE", "inky").strip().lower()
        if output_mode not in {"inky", "png"}:
            raise ValueError("OUTPUT_MODE must be 'inky' or 'png'")

        return cls(
            lastfm_api_key=api_key,
            lastfm_user=user,
            genius_access_token=genius_access_token,
            poll_seconds=poll_seconds,
            output_mode=output_mode,
            png_output=Path(os.environ.get("PNG_OUTPUT", "out/current.png")),
            cache_dir=Path(os.environ.get("CACHE_DIR", ".cache/itabashi")),
        )


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        os.environ.setdefault(key, _parse_env_value(value))


def _parse_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
