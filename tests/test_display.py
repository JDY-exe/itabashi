from pathlib import Path

from PIL import Image

from itabashi.display import DebugDisplay, make_display


def test_debug_display_does_not_write_png(tmp_path: Path):
    output = tmp_path / "current.png"
    display = make_display("debug", output)

    assert isinstance(display, DebugDisplay)
    display.show(Image.new("RGB", (10, 10), "white"))

    assert not output.exists()
