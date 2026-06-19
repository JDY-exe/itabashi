from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

from .http import APIError, JSONHTTPClient, TransientHTTPError
from .models import Track


LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
DEFAULT_DURATION_MS = 240_000
logger = logging.getLogger(__name__)


@dataclass
class LastFMClient:
    api_key: str
    user: str
    http: JSONHTTPClient
    api_url: str = LASTFM_API

    def current_track(self) -> Track | None:
        logger.info("Polling Last.fm for current track", extra={"lastfm_user": self.user})
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
        observed_at = time.time()
        track = parse_current_track(payload, observed_at_epoch=observed_at)
        if track is None:
            return None
        return self._with_duration(track)

    def _with_duration(self, track: Track) -> Track:
        try:
            payload = self.http.get_json(
                self.api_url,
                {
                    "method": "track.getInfo",
                    "artist": track.artist,
                    "track": track.title,
                    "api_key": self.api_key,
                    "autocorrect": 1,
                    "format": "json",
                },
            )
            duration_ms = parse_track_duration(payload) or DEFAULT_DURATION_MS
        except (APIError, TransientHTTPError):
            logger.info(
                "Last.fm track duration unavailable; using default",
                extra={"artist": track.artist, "title": track.title},
            )
            return _copy_track(track, duration_ms=DEFAULT_DURATION_MS)
        return _copy_track(track, duration_ms=duration_ms)


def parse_current_track(payload: Any, observed_at_epoch: float | None = None) -> Track | None:
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
        started_at = _date_uts(item.get("date")) or observed_at_epoch
        return Track(
            artist=artist,
            title=title,
            album=album,
            album_art_url=_best_image(item.get("image")),
            started_at_epoch=started_at,
            observed_at_epoch=observed_at_epoch,
        )
    return None


def parse_track_duration(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        raise APIError("malformed Last.fm response")
    if "error" in payload:
        _raise_api_error(payload)
    track = payload.get("track")
    if not isinstance(track, dict):
        raise APIError("malformed Last.fm response")
    try:
        duration = int(track.get("duration") or 0)
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


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


def _date_uts(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    try:
        uts = int(value.get("uts") or 0)
    except (TypeError, ValueError):
        return None
    return float(uts) if uts > 0 else None


def _best_image(images: Any) -> str:
    if not isinstance(images, list):
        return ""
    for image in reversed(images):
        if isinstance(image, dict):
            url = _text(image.get("#text"))
            if url:
                return url
    return ""


def _copy_track(track: Track, duration_ms: int) -> Track:
    return Track(
        artist=track.artist,
        title=track.title,
        album=track.album,
        album_art_url=track.album_art_url,
        started_at_epoch=track.started_at_epoch,
        duration_ms=duration_ms,
        observed_at_epoch=track.observed_at_epoch,
    )
