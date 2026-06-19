from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image


logger = logging.getLogger(__name__)


class Display:
    def show(self, image: Image.Image) -> None:
        raise NotImplementedError


class PNGDisplay(Display):
    def __init__(self, path: Path) -> None:
        self.path = path

    def show(self, image: Image.Image) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        image.save(self.path)


class InkyDisplay(Display):
    def __init__(self) -> None:
        try:
            from inky.auto import auto
        except ImportError as exc:
            raise RuntimeError("inky is required for OUTPUT_MODE=inky") from exc
        self.display = auto(ask_user=True, verbose=True)

    def show(self, image: Image.Image) -> None:
        self.display.set_image(image)
        self.display.show()


class DebugDisplay(Display):
    def show(self, image: Image.Image) -> None:
        logger.info("Debug display suppressed hardware render", extra={"image_size": image.size})


def make_display(output_mode: str, png_output: Path) -> Display:
    if output_mode == "png":
        return PNGDisplay(png_output)
    if output_mode == "debug":
        return DebugDisplay()
    if output_mode == "inky":
        return InkyDisplay()
    raise ValueError("unknown output mode")
