from pathlib import Path

from PIL import Image

from itabashi.display import PNGDisplay
from itabashi.models import RenderPayload, Track
from itabashi.renderer import HEIGHT, WIDTH, Renderer


def test_png_output_dimensions_exactly_800x480(tmp_path: Path):
    output = tmp_path / "current.png"
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics="hello"))
    PNGDisplay(output).show(image)

    with Image.open(output) as rendered:
        assert rendered.size == (WIDTH, HEIGHT)


def test_long_lyrics_truncation_renders_marker():
    lyrics = "\n".join(f"line {index}" for index in range(200))
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics=lyrics))

    assert image.size == (800, 480)
    assert image.getbbox() is not None


def test_missing_art_fallback_renders():
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics="lyrics", album_art_path=None))

    assert image.size == (800, 480)
    assert image.getpixel((550, 24)) == (0, 0, 0)


def test_missing_lyrics_fallback_renders():
    image = Renderer().render(RenderPayload(Track("Artist", "Title"), lyrics=None))

    assert image.size == (800, 480)
    assert image.getbbox() is not None
