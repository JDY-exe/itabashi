import threading
import time

from itabashi.http import TransientHTTPError
from itabashi.models import Track
from itabashi.scheduler import LatestWinsWorker, PollingService


def test_no_duplicate_refresh_for_same_track():
    calls = []
    worker = LatestWinsWorker(calls.append)

    track = Track("Artist", "Song")
    assert worker.submit(track) is True
    assert worker.submit(track) is False
    assert worker.pending == track


def test_latest_wins_during_active_refresh():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def render(track):
        calls.append(track.title)
        if track.title == "one":
            started.set()
            release.wait(2)

    worker = LatestWinsWorker(render)
    worker.start()
    worker.submit(Track("Artist", "one"))
    assert started.wait(2)
    worker.submit(Track("Artist", "two"))
    worker.submit(Track("Artist", "three"))
    release.set()

    deadline = time.time() + 2
    while time.time() < deadline and calls != ["one", "three"]:
        time.sleep(0.01)
    worker.stop()

    assert calls == ["one", "three"]


def test_rate_limit_backoff_and_recovery():
    calls = iter(
        [
            TransientHTTPError(429, "rate limited"),
            TransientHTTPError(500, "server"),
            Track("Artist", "Song"),
        ]
    )
    worker = LatestWinsWorker(lambda track: None)
    submitted = []
    worker.submit = lambda track: submitted.append(track) or True

    def poll():
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item

    service = PollingService(poll, worker, poll_seconds=20, sleep=lambda seconds: None)

    assert service.poll_once() == 30
    assert service.poll_once() == 60
    assert service.poll_once() == 20
    assert submitted == [Track("Artist", "Song")]
