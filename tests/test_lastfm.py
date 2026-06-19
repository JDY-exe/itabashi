import pytest

from itabashi.http import APIError, TransientHTTPError
from itabashi.lastfm import LASTFM_API, LastFMClient, parse_current_track


def payload(track):
    return {"recenttracks": {"track": [track]}}


class FakeHTTP:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        return self.response


def test_parse_now_playing_track():
    track = parse_current_track(
        payload(
            {
                "@attr": {"nowplaying": "true"},
                "name": "Song",
                "artist": {"#text": "Artist"},
                "album": {"#text": "Album"},
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


def test_current_track_logs_poll(caplog):
    http = FakeHTTP(payload({"@attr": {"nowplaying": "true"}, "name": "Song", "artist": {"#text": "Artist"}}))
    client = LastFMClient("api-key", "lastfm-user", http)

    with caplog.at_level("INFO", logger="itabashi.lastfm"):
        track = client.current_track()

    assert track.title == "Song"
    assert http.calls[0][0] == LASTFM_API
    assert "Polling Last.fm for current track" in caplog.text


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
