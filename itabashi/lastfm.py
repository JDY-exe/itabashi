from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .http import APIError, JSONHTTPClient, TransientHTTPError
from .models import Track


LASTFM_API = "https://ws.audioscrobbler.com/2.0/"


@dataclass
class LastFMClient:
    api_key: str
    user: str
    http: JSONHTTPClient
    api_url: str = LASTFM_API

    def current_track(self) -> Track | None:
        payload = self.http.get_json(
            self.api_url,
            {
                "method": "user.getRecentTracks",
                "user": self.user,
                "api_key": self.api_key,
                "limit": 1,
                "format": "json",
            },
        )
        return parse_current_track(payload)


def parse_current_track(payload: Any) -> Track | None:
    if not isinstance(payload, dict):
        raise APIError("malformed Last.fm response")
    if "error" in payload:
        _raise_api_error(payload)

    recent_tracks = payload.get("recenttracks")
    if not isinstance(recent_tracks, dict):
        raise APIError("malformed Last.fm response")
    tracks = recent_tracks.get("track")
    if isinstance(tracks, dict):
        tracks = [tracks]
    if not isinstance(tracks, list):
        raise APIError("malformed Last.fm response")

    for item in tracks:
        if not isinstance(item, dict):
            continue
        attr = item.get("@attr")
        if not isinstance(attr, dict) or attr.get("nowplaying") != "true":
            continue
        title = _text(item.get("name"))
        artist = _named_text(item.get("artist"))
        if not title or not artist:
            raise APIError("malformed Last.fm track")
        album = _named_text(item.get("album"))
        return Track(
            artist=artist,
            title=title,
            album=album,
            album_art_url=_best_image(item.get("image")),
        )
    return None


def _raise_api_error(payload: dict[str, Any]) -> None:
    code = payload.get("error")
    message = str(payload.get("message") or code)
    if code in {8, 11, 16, 29}:
        status = 429 if code == 29 else None
        raise TransientHTTPError(status, message)
    raise APIError(message)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _named_text(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("#text"))
    return _text(value)


def _best_image(images: Any) -> str:
    if not isinstance(images, list):
        return ""
    for image in reversed(images):
        if isinstance(image, dict):
            url = _text(image.get("#text"))
            if url:
                return url
    return ""
