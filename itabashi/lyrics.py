from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Protocol

from requests.exceptions import RequestException

from .http import TransientHTTPError
from .models import Track


class GeniusClient(Protocol):
    def search_song(self, title: str | None = None, artist: str = "", song_id: int | None = None, get_full_info: bool = True):
        ...


@dataclass
class GeniusLyricsProvider:
    access_token: str
    client: GeniusClient | None = None
    timeout: int = 10
    retries: int = 2
    excluded_terms: list[str] = field(default_factory=lambda: ["remix", "live", "instrumental", "karaoke"])

    def __post_init__(self) -> None:
        if self.client is None:
            import lyricsgenius

            self.client = lyricsgenius.Genius(
                self.access_token,
                timeout=self.timeout,
                retries=self.retries,
                remove_section_headers=True,
                skip_non_songs=True,
                excluded_terms=self.excluded_terms,
                user_agent="itabashi/0.1",
                per_page=5,
            )

    def lyrics_for(self, track: Track) -> str | None:
        assert self.client is not None
        for title in title_variants(track.title):
            try:
                song = self.client.search_song(title, track.artist, get_full_info=False)
            except RequestException as exc:
                raise TransientHTTPError(None, str(exc)) from exc
            if song is None:
                continue
            lyrics = clean_genius_lyrics(getattr(song, "lyrics", None), title=title)
            if lyrics:
                return lyrics
        return None


def title_variants(title: str) -> list[str]:
    candidates = [title.strip()]
    without_parens = re.sub(r"\s*[\[(].*?(?:feat\.?|ft\.?|with|live|remix|edit|version).*?[\])]", "", title, flags=re.I).strip()
    without_after_dash = re.sub(r"\s+-\s+(live|remix|edit|radio edit|remastered|acoustic).*$", "", title, flags=re.I).strip()
    without_feat = re.sub(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", "", title, flags=re.I).strip()
    candidates.extend([without_parens, without_after_dash, without_feat])

    seen: set[str] = set()
    variants: list[str] = []
    for candidate in candidates:
        key = re.sub(r"\s+", " ", candidate).casefold()
        if candidate and key not in seen:
            seen.add(key)
            variants.append(candidate)
    return variants


def clean_genius_lyrics(raw: str | None, title: str) -> str | None:
    if not raw:
        return None
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return None

    lines = [line.strip() for line in text.splitlines()]
    lines = _drop_leading_title_line(lines, title)

    cleaned: list[str] = []
    for line in lines:
        if not line:
            if cleaned and cleaned[-1]:
                cleaned.append("")
            continue
        if _is_boilerplate(line):
            continue
        line = re.sub(r"\s*\d*Embed$", "", line).strip()
        line = re.sub(r"^\d+\s+Contributors?(?:Translations?.*)?$", "", line, flags=re.I).strip()
        line = re.sub(r"^Translations?.*Lyrics$", "", line, flags=re.I).strip()
        if line:
            cleaned.append(line)

    while cleaned and not cleaned[-1]:
        cleaned.pop()
    result = "\n".join(cleaned).strip()
    return result or None


def _drop_leading_title_line(lines: list[str], title: str) -> list[str]:
    if not lines:
        return lines
    title_key = _plain_key(title)
    first_key = _plain_key(lines[0])
    if first_key.endswith("lyrics") and title_key and title_key in first_key:
        return lines[1:]
    return lines


def _is_boilerplate(line: str) -> bool:
    return bool(
        re.fullmatch(r"You might also like", line, flags=re.I)
        or re.fullmatch(r"Read More", line, flags=re.I)
        or re.fullmatch(r"Embed", line, flags=re.I)
        or re.fullmatch(r"See .* LiveGet tickets.*", line, flags=re.I)
    )


def _plain_key(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return re.sub(r"\s+", " ", value).strip()
