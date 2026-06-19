from __future__ import annotations

from pathlib import Path
from PIL import Image
from io import BytesIO

from .http import JSONHTTPClient
from .models import Track, cache_key


class AssetCache:
    def __init__(self, root: Path, http: JSONHTTPClient) -> None:
        self.root = root
        self.http = http
        self.lyrics_dir = root / "lyrics"
        self.art_dir = root / "art"

    def get_lyrics(self, track: Track, fetcher, provider: str = "default") -> str | None:
        lyrics_dir = self.lyrics_dir / provider
        lyrics_dir.mkdir(parents=True, exist_ok=True)
        path = lyrics_dir / f"{track.identity}.txt"
        if path.exists():
            value = path.read_text(encoding="utf-8")
            return value if value else None
        lyrics = fetcher(track)
        path.write_text(lyrics or "", encoding="utf-8")
        return lyrics

    def get_album_art(self, url: str) -> Path | None:
        if not url:
            return None
        self.art_dir.mkdir(parents=True, exist_ok=True)
        path = self.art_dir / f"{cache_key(url)}.png"
        if path.exists():
            return path
        data = self.http.get_bytes(url)
        with Image.open(BytesIO(data)) as image:
            image.convert("RGB").resize((220, 220), Image.Resampling.LANCZOS).save(path)
        return path
