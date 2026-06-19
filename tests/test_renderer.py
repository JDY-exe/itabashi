from pathlib import Path

from PIL import Image, ImageDraw

from itabashi.display import PNGDisplay
from itabashi.models import RenderPayload, Track
from itabashi.renderer import (
    HEIGHT,
    META_FONT_SIZE,
    REGULAR_FONT_SIZE,
    SMALL_FONT_SIZE,
    TITLE_FONT_SIZE,
    WIDTH,
    Renderer,
    _paginate_lines,
    _page_index_for_progress,
    _text_width,
    _wrap_to_width,
)


def test_png_output_dimensions_exactly_800x480(tmp_path: Path):
    output = tmp_path / "current.png"
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics="hello"))
    PNGDisplay(output).show(image)

    with Image.open(output) as rendered:
        assert rendered.size == (WIDTH, HEIGHT)


def test_long_lyrics_pagination_renders():
    lyrics = "\n".join(f"line {index}" for index in range(200))
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics=lyrics))

    assert image.size == (800, 480)
    assert image.getbbox() is not None


def test_missing_art_fallback_renders():
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics="lyrics", album_art_path=None))

    assert image.size == (800, 480)
    assert image.getpixel((550, 24)) == (0, 0, 0)


def test_render_does_not_draw_vertical_divider():
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics="lyrics", album_art_path=None))

    assert image.getpixel((528, 10)) == (255, 255, 255)


def test_missing_lyrics_fallback_renders():
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics=None))

    assert image.size == (800, 480)
    assert image.getbbox() is not None


def test_font_sizes_are_increased_by_50_percent():
    renderer = Renderer()

    assert renderer.font_regular.size == REGULAR_FONT_SIZE == 18
    assert renderer.font_small.size == SMALL_FONT_SIZE == 14
    assert renderer.font_title.size == TITLE_FONT_SIZE == 33
    assert renderer.font_meta.size == META_FONT_SIZE == 24


def test_unicode_text_renders():
    image = Renderer().render(RenderPayload(Track("坂本龍一", "戦場のメリークリスマス"), lyrics="こんにちは\nありがとう"))

    assert image.size == (800, 480)
    assert image.getbbox() is not None


def test_wrap_uses_rendered_pixel_width():
    renderer = Renderer()
    image = Image.new("RGB", (300, 100), "white")
    draw = ImageDraw.Draw(image)
    width = _text_width(draw, "WWWW", renderer.font_regular) + 1

    lines = _wrap_to_width(draw, "WWWW WWWW iiii iiii", width, renderer.font_regular)

    assert len(lines) > 2
    assert all(_text_width(draw, line, renderer.font_regular) <= width for line in lines)


def test_wrap_breaks_long_unspaced_text_to_fit():
    renderer = Renderer()
    image = Image.new("RGB", (300, 100), "white")
    draw = ImageDraw.Draw(image)
    width = _text_width(draw, "super", renderer.font_regular) + 1

    lines = _wrap_to_width(draw, "supercalifragilistic", width, renderer.font_regular)

    assert len(lines) > 1
    assert all(_text_width(draw, line, renderer.font_regular) <= width for line in lines)


def test_paginate_lines_preserves_rough_30_percent_overlap():
    lines = [f"line {index}" for index in range(20)]

    pages = _paginate_lines(lines, capacity=10)

    assert pages[0] == lines[:10]
    assert pages[1][:3] == pages[0][-3:]


def test_page_index_tracks_song_progress():
    pages = [["a"], ["b"], ["c"], ["d"]]
    track = Track("Artist", "Title", started_at_epoch=100.0, duration_ms=200_000)

    assert _page_index_for_progress(pages, RenderPayload(track, lyrics="x", now_epoch=100.0)) == 0
    assert _page_index_for_progress(pages, RenderPayload(track, lyrics="x", now_epoch=200.0)) == 2
    assert _page_index_for_progress(pages, RenderPayload(track, lyrics="x", now_epoch=400.0)) == 3


def test_pagination_info_reports_line_range_and_percentages():
    renderer = Renderer()
    lyrics = "\n".join(f"line {index}" for index in range(120))
    track = Track("Artist", "Title", started_at_epoch=100.0, duration_ms=200_000)

    info = renderer.pagination_info(RenderPayload(track, lyrics=lyrics, now_epoch=200.0))

    assert info.total_lines == 120
    assert info.page_count > 1
    assert info.progress_percent == 50.0
    assert info.start_line is not None
    assert info.end_line is not None
    assert info.start_line <= info.end_line
    assert info.end_line_percent == info.end_line / info.total_lines * 100
    assert info.displayed_lines
    assert len(info.displayed_lines) == info.end_line - info.start_line + 1
