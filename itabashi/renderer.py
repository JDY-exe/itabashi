from __future__ import annotations

from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

from .models import RenderPayload


WIDTH = 800
HEIGHT = 480
FONT_SCALE = 0.6
REGULAR_FONT_SIZE = round(20 * FONT_SCALE)
SMALL_FONT_SIZE = round(16 * FONT_SCALE)
TITLE_FONT_SIZE = round(28 * FONT_SCALE)
META_FONT_SIZE = round(18 * FONT_SCALE)


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

        draw.rectangle((left_w, 0, left_w + 1, h), fill="black")
        self._draw_lyrics(draw, payload.lyrics, (24, 24, left_w - 24, h - 24))
        self._draw_meta(image, draw, payload, (left_w + gutter, 24, w - 24, h - 24))
        return image

    def _draw_lyrics(self, draw: ImageDraw.ImageDraw, lyrics: str | None, box: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = box
        if not lyrics:
            draw.text((x0, y0), "No lyrics found", font=self.font_title, fill="black")
            return

        column_gap = 22
        column_width = (x1 - x0 - column_gap) // 2
        line_height = 15
        max_lines_per_col = max(1, (y1 - y0) // line_height)
        wrapped: list[str] = []
        for raw_line in lyrics.splitlines():
            line = raw_line.strip()
            if not line:
                wrapped.append("")
                continue
            wrapped.extend(textwrap.wrap(line, width=55) or [""])

        capacity = max_lines_per_col * 2
        truncated = len(wrapped) > capacity
        if truncated:
            wrapped = wrapped[: max(0, capacity - 1)] + ["..."]

        for index, line in enumerate(wrapped):
            column = index // max_lines_per_col
            row = index % max_lines_per_col
            x = x0 + column * (column_width + column_gap)
            y = y0 + row * line_height
            draw.text((x, y), line, font=self.font_regular, fill="black")

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

    def _wrapped_text(self, draw, text: str, x: int, y: int, width: int, font, max_lines: int) -> int:
        chars = max(8, width // 7)
        lines = textwrap.wrap(text or "-", width=chars)[:max_lines]
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
