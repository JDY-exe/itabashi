import pytest

from itabashi.http import APIError, TransientHTTPError
from itabashi.lastfm import DEFAULT_DURATION_MS, LASTFM_API, LastFMClient, parse_current_track, parse_track_duration


def payload(track):
    return {"recenttracks": {"track": [track]}}


class FakeHTTP:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_parse_now_playing_track():
    track = parse_current_track(
        payload(
            {
                "@attr": {"nowplaying": "true"},
                "name": "Song",
                "artist": {"#text": "Artist"},
                "album": {"#text": "Album"},
                "date": {"uts": "12345"},
                "image": [
                    {"#text": "", "size": "small"},
                    {"#text": "https://example.test/art.jpg", "size": "extralarge"},
                ],
            }
        )
    )

    assert track.title == "Song"
    assert track.artist == "Artist"
    assert track.album == "Album"
    assert track.album_art_url == "https://example.test/art.jpg"
    assert track.started_at_epoch == 12345.0


def test_current_track_logs_poll_and_fetches_duration(caplog):
    http = FakeHTTP(
        payload({"@attr": {"nowplaying": "true"}, "name": "Song", "artist": {"#text": "Artist"}}),
        {"track": {"duration": "180000"}},
    )
    client = LastFMClient("api-key", "lastfm-user", http)

    with caplog.at_level("INFO", logger="itabashi.lastfm"):
        track = client.current_track()

    assert track.title == "Song"
    assert track.duration_ms == 180_000
    assert http.calls[0][0] == LASTFM_API
    assert http.calls[1][1]["method"] == "track.getInfo"
    assert "Polling Last.fm for current track" in caplog.text


def test_current_track_uses_poll_time_without_date():
    http = FakeHTTP(
        payload({"@attr": {"nowplaying": "true"}, "name": "Song", "artist": {"#text": "Artist"}}),
        {"track": {"duration": "180000"}},
    )

    track = LastFMClient("api-key", "lastfm-user", http).current_track()

    assert track.started_at_epoch is not None
    assert track.observed_at_epoch is not None


def test_current_track_defaults_duration_when_lookup_fails():
    http = FakeHTTP(
        payload({"@attr": {"nowplaying": "true"}, "name": "Song", "artist": {"#text": "Artist"}}),
        TransientHTTPError(500, "server"),
    )

    track = LastFMClient("api-key", "lastfm-user", http).current_track()

    assert track.duration_ms == DEFAULT_DURATION_MS


def test_parse_no_current_track_returns_none():
    assert parse_current_track(payload({"name": "Old Song", "artist": {"#text": "Artist"}})) is None


def test_parse_missing_album_and_art_fields():
    track = parse_current_track(
        payload({"@attr": {"nowplaying": "true"}, "name": "Song", "artist": {"#text": "Artist"}})
    )

    assert track.album == ""
    assert track.album_art_url == ""


@pytest.mark.parametrize("bad_payload", [None, {}, {"recenttracks": {"track": "bad"}}])
def test_parse_malformed_response(bad_payload):
    with pytest.raises(APIError):
        parse_current_track(bad_payload)


def test_parse_api_error_payload():
    with pytest.raises(APIError, match="Invalid API key"):
        parse_current_track({"error": 10, "message": "Invalid API key"})


def test_parse_rate_limit_payload_is_transient():
    with pytest.raises(TransientHTTPError):
        parse_current_track({"error": 29, "message": "Rate Limit Exceeded"})


def test_parse_track_duration():
    assert parse_track_duration({"track": {"duration": "240000"}}) == 240_000
    assert parse_track_duration({"track": {"duration": "0"}}) is None
    assert parse_track_duration({"track": {"duration": "bad"}}) is None
