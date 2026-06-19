from __future__ import annotations

import logging
import time

from .cache import AssetCache
from .display import make_display
from .http import JSONHTTPClient
from .lastfm import LastFMClient
from .lyrics import GeniusLyricsProvider
from .models import Config, RenderPayload, Track
from .renderer import Renderer
from .scheduler import LatestWinsWorker, PollingService


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_service(config: Config) -> PollingService:
    http = JSONHTTPClient()
    lastfm = LastFMClient(config.lastfm_api_key, config.lastfm_user, http)
    lyrics = GeniusLyricsProvider(config.genius_access_token)
    cache = AssetCache(config.cache_dir, http)
    renderer = Renderer()
    display = make_display(config.output_mode, config.png_output)
    last_displayed: tuple[str, int] | None = None

    def render_track(track: Track) -> None:
        nonlocal last_displayed
        text = cache.get_lyrics(track, lyrics.lyrics_for, provider="genius")
        art_path = cache.get_album_art(track.album_art_url)
        payload = RenderPayload(track=track, lyrics=text, album_art_path=art_path, now_epoch=track.observed_at_epoch)
        page_index = renderer.page_index(payload)
        page_key = (track.identity, page_index)
        elapsed_seconds = _elapsed_seconds(track, payload.now_epoch)
        duration_seconds = (track.duration_ms or 240_000) / 1000
        if page_key == last_displayed:
            logger.info(
                "Lyric page unchanged; display refresh skipped: %s - %s page %s",
                track.artist,
                track.title,
                page_index + 1,
                extra={
                    "artist": track.artist,
                    "title": track.title,
                    "album": track.album,
                    "page_index": page_index,
                    "elapsed_seconds": elapsed_seconds,
                    "duration_seconds": duration_seconds,
                },
            )
            return
        logger.info(
            "Rendering lyric page: %s - %s page %s",
            track.artist,
            track.title,
            page_index + 1,
            extra={
                "artist": track.artist,
                "title": track.title,
                "album": track.album,
                "page_index": page_index,
                "elapsed_seconds": elapsed_seconds,
                "duration_seconds": duration_seconds,
            },
        )
        display.show(renderer.render(payload))
        last_displayed = page_key

    return PollingService(
        poll_current=lastfm.current_track,
        worker=LatestWinsWorker(render_track),
        poll_seconds=config.poll_seconds,
    )


def render_current_once(config: Config) -> bool:
    http = JSONHTTPClient()
    track = LastFMClient(config.lastfm_api_key, config.lastfm_user, http).current_track()
    if track is None:
        return False

    lyrics = GeniusLyricsProvider(config.genius_access_token)
    cache = AssetCache(config.cache_dir, http)
    renderer = Renderer()
    display = make_display(config.output_mode, config.png_output)
    text = cache.get_lyrics(track, lyrics.lyrics_for, provider="genius")
    art_path = cache.get_album_art(track.album_art_url)
    display.show(
        renderer.render(
            RenderPayload(track=track, lyrics=text, album_art_path=art_path, now_epoch=track.observed_at_epoch or time.time())
        )
    )
    return True


def main() -> None:
    configure_logging()
    service = build_service(Config.from_env())
    service.run_forever()


def dry_run_main() -> None:
    configure_logging()
    config = Config.from_env()
    config = Config(
        lastfm_api_key=config.lastfm_api_key,
        lastfm_user=config.lastfm_user,
        genius_access_token=config.genius_access_token,
        poll_seconds=config.poll_seconds,
        output_mode="png",
        png_output=config.png_output,
        cache_dir=config.cache_dir,
    )
    render_current_once(config)


def _elapsed_seconds(track: Track, now_epoch: float | None) -> float | None:
    if track.started_at_epoch is None or now_epoch is None:
        return None
    return max(0.0, now_epoch - track.started_at_epoch)
