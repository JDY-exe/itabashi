import pytest
from requests.exceptions import Timeout

from itabashi.http import TransientHTTPError
from itabashi.lyrics import GeniusLyricsProvider, clean_genius_lyrics, title_variants
from itabashi.models import Track


class Song:
    def __init__(self, lyrics):
        self.lyrics = lyrics


class FakeGenius:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search_song(self, title=None, artist="", song_id=None, get_full_info=True):
        self.calls.append((title, artist, get_full_info))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_successful_lyrics_are_cleaned():
    client = FakeGenius([Song("Song Title Lyrics\n12 Contributors\nline one\nYou might also like\nline two\n3Embed")])
    provider = GeniusLyricsProvider("token", client=client)

    assert provider.lyrics_for(Track(artist="Artist", title="Song Title")) == "line one\nline two"
    assert client.calls == [("Song Title", "Artist", False)]


def test_no_match_returns_none():
    provider = GeniusLyricsProvider("token", client=FakeGenius([None]))

    assert provider.lyrics_for(Track(artist="Artist", title="Song")) is None


def test_title_variants_try_cleaner_title_after_no_match():
    client = FakeGenius([None, Song("Song Lyrics\nactual lyric")])
    provider = GeniusLyricsProvider("token", client=client)

    result = provider.lyrics_for(Track(artist="Artist", title="Song (feat. Other Artist)"))

    assert result == "actual lyric"
    assert client.calls[0] == ("Song (feat. Other Artist)", "Artist", False)
    assert client.calls[1] == ("Song", "Artist", False)


def test_timeout_maps_to_transient_error():
    provider = GeniusLyricsProvider("token", client=FakeGenius([Timeout("slow")]))

    with pytest.raises(TransientHTTPError):
        provider.lyrics_for(Track(artist="Artist", title="Song"))


def test_clean_genius_lyrics_handles_empty_and_boilerplate():
    assert clean_genius_lyrics(None, title="Song") is None
    assert clean_genius_lyrics("Song Lyrics\nEmbed", title="Song") is None


def test_title_variants_are_deduplicated():
    assert title_variants("Song - Live") == ["Song - Live", "Song"]
