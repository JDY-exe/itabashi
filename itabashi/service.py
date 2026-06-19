from __future__ import annotations

from .cache import AssetCache
from .display import make_display
from .http import JSONHTTPClient
from .lastfm import LastFMClient
from .lyrics import GeniusLyricsProvider
from .models import Config, RenderPayload, Track
from .renderer import Renderer
from .scheduler import LatestWinsWorker, PollingService


def build_service(config: Config) -> PollingService:
    http = JSONHTTPClient()
    lastfm = LastFMClient(config.lastfm_api_key, config.lastfm_user, http)
    lyrics = GeniusLyricsProvider(config.genius_access_token)
    cache = AssetCache(config.cache_dir, http)
    renderer = Renderer()
    display = make_display(config.output_mode, config.png_output)

    def render_track(track: Track) -> None:
        text = cache.get_lyrics(track, lyrics.lyrics_for, provider="genius")
        art_path = cache.get_album_art(track.album_art_url)
        display.show(renderer.render(RenderPayload(track=track, lyrics=text, album_art_path=art_path)))

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
    display.show(renderer.render(RenderPayload(track=track, lyrics=text, album_art_path=art_path)))
    return True


def main() -> None:
    service = build_service(Config.from_env())
    service.run_forever()


def dry_run_main() -> None:
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
