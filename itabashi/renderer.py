from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

from PIL import Image, ImageDraw, ImageFont

from .models import RenderPayload


WIDTH = 800
HEIGHT = 480
FONT_SCALE = 0.9
REGULAR_FONT_SIZE = round(20 * FONT_SCALE)
SMALL_FONT_SIZE = round(16 * FONT_SCALE)
TITLE_FONT_SIZE = round(28 * FONT_SCALE * 1.3)
META_FONT_SIZE = round(18 * FONT_SCALE * 1.5)
DEFAULT_DURATION_MS = 240_000
PAGE_OVERLAP = 0.3


@dataclass(frozen=True)
class PaginationInfo:
    page_index: int
    page_count: int
    total_lines: int
    start_line: int | None
    end_line: int | None
    progress_percent: float
    end_line_percent: float
    displayed_lines: tuple[str, ...]


class Renderer:
    def __init__(self, size: tuple[int, int] = (WIDTH, HEIGHT)) -> None:
        self.size = size
        self.font_regular = _font(REGULAR_FONT_SIZE)
        self.font_small = _font(SMALL_FONT_SIZE)
        self.font_title = _font(TITLE_FONT_SIZE)
        self.font_meta = _font(META_FONT_SIZE)

    def render(self, payload: RenderPayload) -> Image.Image:
        image = Image.new("RGB", self.size, "white")
        draw = ImageDraw.Draw(image)
        w, h = self.size
        left_w = int(w * 0.66)
        gutter = 22

        self._draw_lyrics(draw, payload, (24, 24, left_w - 24, h - 24))
        self._draw_meta(image, draw, payload, (left_w + gutter, 24, w - 24, h - 24))
        return image

    def page_index(self, payload: RenderPayload) -> int:
        return self.pagination_info(payload).page_index

    def pagination_info(self, payload: RenderPayload) -> PaginationInfo:
        image = Image.new("RGB", self.size, "white")
        draw = ImageDraw.Draw(image)
        w, h = self.size
        left_w = int(w * 0.66)
        _, info = self._lyric_page(draw, payload, (24, 24, left_w - 24, h - 24))
        return info

    def _draw_lyrics(self, draw: ImageDraw.ImageDraw, payload: RenderPayload, box: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = box
        if not payload.lyrics:
            draw.text((x0, y0), "No lyrics found", font=self.font_title, fill="black")
            return

        page, _ = self._lyric_page(draw, payload, box)
        column_gap = 22
        column_width = (x1 - x0 - column_gap) // 2
        line_height = _font_size(self.font_regular) + 3
        max_lines_per_col = max(1, (y1 - y0) // line_height)

        for index, line in enumerate(page):
            column = index // max_lines_per_col
            row = index % max_lines_per_col
            x = x0 + column * (column_width + column_gap)
            y = y0 + row * line_height
            draw.text((x, y), line, font=self.font_regular, fill="black")

    def _lyric_page(
        self,
        draw: ImageDraw.ImageDraw,
        payload: RenderPayload,
        box: tuple[int, int, int, int],
    ) -> tuple[list[str], PaginationInfo]:
        x0, y0, x1, y1 = box
        if not payload.lyrics:
            return [], PaginationInfo(
                page_index=0,
                page_count=1,
                total_lines=0,
                start_line=None,
                end_line=None,
                progress_percent=_progress_percent(payload),
                end_line_percent=0.0,
                displayed_lines=(),
            )

        column_gap = 22
        column_width = (x1 - x0 - column_gap) // 2
        line_height = _font_size(self.font_regular) + 3
        max_lines_per_col = max(1, (y1 - y0) // line_height)
        capacity = max_lines_per_col * 2
        lines = _wrapped_lyrics(draw, payload.lyrics, column_width, self.font_regular)
        if not lines:
            return [], PaginationInfo(
                page_index=0,
                page_count=1,
                total_lines=0,
                start_line=None,
                end_line=None,
                progress_percent=_progress_percent(payload),
                end_line_percent=0.0,
                displayed_lines=(),
            )
        pages = _paginate_lines(lines, capacity)
        ranges = _paginate_line_ranges(len(lines), capacity)
        page_index = _page_index_for_progress(pages, payload)
        start_index, end_index = ranges[page_index]
        end_line = end_index + 1
        info = PaginationInfo(
            page_index=page_index,
            page_count=len(pages),
            total_lines=len(lines),
            start_line=start_index + 1,
            end_line=end_line,
            progress_percent=_progress_percent(payload),
            end_line_percent=(end_line / len(lines) * 100) if lines else 0.0,
            displayed_lines=tuple(pages[page_index]),
        )
        return pages[page_index], info

    def _draw_meta(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        payload: RenderPayload,
        box: tuple[int, int, int, int],
    ) -> None:
        x0, y0, x1, _ = box
        art_size = min(220, x1 - x0)
        if payload.album_art_path and payload.album_art_path.exists():
            with Image.open(payload.album_art_path) as art:
                image.paste(art.convert("RGB").resize((art_size, art_size)), (x0, y0))
        else:
            draw.rectangle((x0, y0, x0 + art_size, y0 + art_size), outline="black", width=3)
            draw.line((x0, y0, x0 + art_size, y0 + art_size), fill="black", width=2)
            draw.line((x0 + art_size, y0, x0, y0 + art_size), fill="black", width=2)

        y = y0 + art_size + 22
        y = self._wrapped_text(draw, payload.track.title, x0, y, x1 - x0, self.font_title, max_lines=3)
        y += 10
        y = self._wrapped_text(draw, payload.track.artist, x0, y, x1 - x0, self.font_meta, max_lines=2)
        if payload.track.album:
            y += 8
            self._wrapped_text(draw, payload.track.album, x0, y, x1 - x0, self.font_small, max_lines=3)

    def _wrapped_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        width: int,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        max_lines: int,
    ) -> int:
        lines = _wrap_to_width(draw, text or "-", width, font)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = _ellipsize_to_width(draw, lines[-1], width, font)
        for line in lines:
            draw.text((x, y), line, font=font, fill="black")
            y += _font_size(font) + 3
        return y


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _font_size(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    return getattr(font, "size", REGULAR_FONT_SIZE)


def _wrapped_lyrics(
    draw: ImageDraw.ImageDraw,
    lyrics: str,
    width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[str]:
    wrapped: list[str] = []
    for raw_line in lyrics.splitlines():
        line = raw_line.strip()
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(_wrap_to_width(draw, line, width, font) or [""])
    return wrapped


def _paginate_lines(lines: list[str], capacity: int) -> list[list[str]]:
    return [lines[start : end + 1] for start, end in _paginate_line_ranges(len(lines), capacity)]


def _paginate_line_ranges(line_count: int, capacity: int) -> list[tuple[int, int]]:
    capacity = max(1, capacity)
    if line_count <= 0:
        return [(0, 0)]
    if line_count <= capacity:
        return [(0, line_count - 1)]

    overlap = min(capacity - 1, max(1, round(capacity * PAGE_OVERLAP)))
    step = max(1, capacity - overlap)
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < line_count:
        end = min(line_count - 1, start + capacity - 1)
        ranges.append((start, end))
        if start + capacity >= line_count:
            break
        start += step
    return ranges


def _page_index_for_progress(pages: list[list[str]], payload: RenderPayload) -> int:
    if len(pages) <= 1:
        return 0

    progress = _progress_percent(payload) / 100
    return min(len(pages) - 1, int(progress * len(pages)))


def _progress_percent(payload: RenderPayload) -> float:
    duration_ms = payload.track.duration_ms if payload.track and payload.track.duration_ms else DEFAULT_DURATION_MS
    duration_seconds = max(1.0, duration_ms / 1000)
    started_at = payload.track.started_at_epoch if payload.track and payload.track.started_at_epoch is not None else None
    now = payload.now_epoch if payload.now_epoch is not None else time.time()
    if started_at is None:
        started_at = now

    progress = min(0.999, max(0.0, (now - started_at) / duration_seconds))
    return progress * 100


def _wrap_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[str]:
    words = re.findall(r"\S+\s*", text.strip())
    if not words:
        return [""]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = current + word
        if _text_width(draw, candidate.rstrip(), font) <= width:
            current = candidate
            continue

        if current:
            lines.append(current.rstrip())
            current = ""

        if _text_width(draw, word.rstrip(), font) <= width:
            current = word
            continue

        pieces = _break_word_to_width(draw, word.rstrip(), width, font)
        lines.extend(pieces[:-1])
        current = pieces[-1] + (" " if word.endswith(" ") else "")

    if current:
        lines.append(current.rstrip())
    return lines


def _break_word_to_width(
    draw: ImageDraw.ImageDraw,
    word: str,
    width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in word:
        candidate = current + char
        if current and _text_width(draw, candidate, font) > width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces or [word]


def _ellipsize_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> str:
    marker = "..."
    if _text_width(draw, marker, font) > width:
        return ""

    text = text.rstrip()
    while text and _text_width(draw, f"{text}{marker}", font) > width:
        text = text[:-1].rstrip()
    return f"{text}{marker}" if text else marker


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left
