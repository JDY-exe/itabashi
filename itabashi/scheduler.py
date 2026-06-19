from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Condition, Event, Thread
import time
from typing import Callable

from .http import TransientHTTPError
from .models import Track


RenderTrack = Callable[[Track], None]
PollCurrent = Callable[[], Track | None]
logger = logging.getLogger(__name__)


@dataclass
class Backoff:
    base_seconds: int = 20
    current_seconds: int = 20

    def success(self) -> None:
        self.current_seconds = self.base_seconds

    def transient_failure(self) -> None:
        if self.current_seconds < 30:
            self.current_seconds = 30
        else:
            self.current_seconds = min(120, self.current_seconds * 2)


class LatestWinsWorker:
    def __init__(self, render_track: RenderTrack) -> None:
        self.render_track = render_track
        self.condition = Condition()
        self.pending: Track | None = None
        self.inflight_identity: str | None = None
        self.rendered_identity: str | None = None
        self.stop_event = Event()
        self.thread = Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self, timeout: float | None = 5) -> None:
        self.stop_event.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=timeout)

    def submit(self, track: Track) -> bool:
        with self.condition:
            render_identity = track.render_identity
            pending_identity = self.pending.render_identity if self.pending else None
            if render_identity in {self.rendered_identity, self.inflight_identity, pending_identity}:
                return False
            self.pending = track
            self.condition.notify()
            return True

    def _run(self) -> None:
        while not self.stop_event.is_set():
            with self.condition:
                while self.pending is None and not self.stop_event.is_set():
                    self.condition.wait(0.5)
                if self.stop_event.is_set():
                    return
                track = self.pending
                self.pending = None
                self.inflight_identity = track.render_identity
            self.render_track(track)
            with self.condition:
                self.rendered_identity = track.render_identity
                self.inflight_identity = None


class PollingService:
    def __init__(
        self,
        poll_current: PollCurrent,
        worker: LatestWinsWorker,
        poll_seconds: int = 20,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.poll_current = poll_current
        self.worker = worker
        self.backoff = Backoff(base_seconds=poll_seconds, current_seconds=poll_seconds)
        self.sleep = sleep
        self.stop_event = Event()

    def run_forever(self) -> None:
        self.worker.start()
        try:
            while not self.stop_event.is_set():
                delay = self.poll_once()
                self.sleep(delay)
        finally:
            self.worker.stop()

    def stop(self) -> None:
        self.stop_event.set()

    def poll_once(self) -> int:
        try:
            track = self.poll_current()
        except TransientHTTPError:
            self.backoff.transient_failure()
            return self.backoff.current_seconds
        self.backoff.success()
        if track is not None:
            if self.worker.submit(track):
                logger.info(
                    "Song change detected: %s - %s",
                    track.artist,
                    track.title,
                    extra={"artist": track.artist, "title": track.title, "album": track.album},
                )
        return self.backoff.current_seconds
